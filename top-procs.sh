#!/usr/bin/env bash
set -euo pipefail

self_pid=$$

# --- Top CPU ---
sample_a=$(mktemp)
sample_b=$(mktemp)
trap 'rm -f "$sample_a" "$sample_b"' EXIT

sample_proc_cpu() {
  local output=$1

  for stat in /proc/[0-9]*/stat; do
    { IFS= read -r line <"$stat"; } 2>/dev/null || continue
    printf '%s\n' "$line"
  done | awk '
    function parse_stat(line, fields, matched, tail) {
      matched = match(line, /^([0-9]+) \((.*)\) ([A-Z]) (.*)$/, fields)
      if (!matched) {
        return
      }

      split(fields[4], tail, " ")
      # tail[1] is ppid, tail[11]/tail[12] are utime/stime.
      printf "%s\t%s\t%s\t%s\n", fields[1], tail[1], fields[2], tail[11] + tail[12]
    }

    { parse_stat($0) }
  ' >"$output"
}

sample_proc_cpu "$sample_a"
sleep 0.25
sample_proc_cpu "$sample_b"

cpu_rows=$(awk -v self="$self_pid" -v clk="$(getconf CLK_TCK)" '
  NR == FNR {
    ticks[$1] = $4
    next
  }

  $1 == self || $2 == self {
    next
  }

  $1 in ticks {
    delta = $4 - ticks[$1]
    if (delta < 0) {
      next
    }

    percent = delta / clk / 0.25 * 100
    printf "%s\t%.1f\n", $3, percent
  }
' "$sample_a" "$sample_b" | sort -t $'\t' -k2,2nr | awk 'NR <= 3')

cpu_top=$(awk -F '\t' 'NR == 1 {printf "%s %.1f%%", $1, $2}' <<<"$cpu_rows")
cpu_tooltip=$(awk -F '\t' '{printf "%d. %s %.1f%%\n", NR, $1, $2}' <<<"$cpu_rows")

# --- Top Memory ---
mem_top=$(ps -eo pid,ppid,comm,rss --sort=-rss --no-headers \
  | awk -v self="$self_pid" '
      $1==self || $2==self {next}
      {count++}
      count==1 {printf "%s %.1fG", $3, $4/1024/1024}
    ')

mem_tooltip=$(ps -eo pid,ppid,comm,rss --sort=-rss --no-headers \
  | awk -v self="$self_pid" '
      $1==self || $2==self {next}
      {count++}
      count<=3 {printf "%d. %s %.1fG\n", count, $3, $4/1024/1024}
      count==3 {exit}
    ')

# --- Output for Waybar ---
text="$cpu_top | $mem_top"
tooltip="Top CPU:\n$cpu_tooltip\nTop MEM:\n$mem_tooltip"

printf '{ "text": "%s", "tooltip": "%s" }\n' \
  "$(echo "$text" | sed 's/"/\\"/g')" \
  "$(echo "$tooltip" | sed ':a;N;$!ba;s/\n/\\n/g' | sed 's/"/\\"/g')"
