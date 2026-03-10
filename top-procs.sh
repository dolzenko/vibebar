#!/usr/bin/env bash
set -euo pipefail

self_pid=$$

# --- Top CPU ---
cpu_top=$(ps -eo pid,ppid,comm,%cpu --sort=-%cpu --no-headers \
  | awk -v self="$self_pid" '
      $1==self || $2==self {next}
      {count++}
      count==1 {printf "%s %.1f%%", $3, $4}
    ')

cpu_tooltip=$(ps -eo pid,ppid,comm,%cpu --sort=-%cpu --no-headers \
  | awk -v self="$self_pid" '
      $1==self || $2==self {next}
      {count++}
      count<=3 {printf "%d. %s %s%%\n", count, $3, $4}
      count==3 {exit}
    ')

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
