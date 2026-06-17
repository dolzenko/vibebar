#!/usr/bin/env bash
set -euo pipefail

script_path="${BASH_SOURCE[0]}"

if [[ "${1:-}" == "--event" ]]; then
  log_file="$2"
  name="$3"
  seen_file="$4"
  debug="${5:-0}"

  if [[ ! -e "$seen_file" ]]; then
    touch "$seen_file"
    message="$name initial event skipped"
    should_signal=0
  else
    message="$name changed, signaling waybar"
    should_signal=1
  fi

  printf '%s [clipboard-watch] %s\n' "$(date --iso-8601=seconds)" "$message" >>"$log_file"
  if ((debug)); then
    printf '[clipboard-watch] %s\n' "$message"
  fi
  if ((should_signal)); then
    pkill -RTMIN+10 waybar || true
  fi
  exit 0
fi

debug=0
if [[ "${1:-}" == "--debug" ]]; then
  debug=1
fi

log_root="${XDG_STATE_HOME:-$HOME/.local/state}/waybar"
mkdir -p "$log_root"
log_file="$log_root/clipboard-watch.log"
state_root="${XDG_RUNTIME_DIR:-/tmp}/waybar-clipboard-watch"
mkdir -p "$state_root"
log_max_bytes=$((1024 * 1024))
log_keep_lines=2000

rotate_log() {
  if [[ ! -f "$log_file" ]]; then
    return
  fi
  local size
  size="$(wc -c <"$log_file")"
  if ((size <= log_max_bytes)); then
    return
  fi
  local tmp
  tmp="$(mktemp "$log_root/.clipboard-watch.XXXXXX")" || return
  tail -n "$log_keep_lines" "$log_file" >"$tmp" && mv "$tmp" "$log_file"
}

log() {
  printf '%s [clipboard-watch] %s\n' "$(date --iso-8601=seconds)" "$*" >>"$log_file"
  if ((debug)); then
    printf '[clipboard-watch] %s\n' "$*"
  fi
}

watch_selection() {
  local name="$1"
  shift
  local seen_file="$state_root/$name.initial-seen"
  rm -f "$seen_file"
  wl-paste "$@" --watch "$script_path" --event "$log_file" "$name" "$seen_file" "$debug"
}

rotate_log
log "starting clipboard watchers; startup refresh and initial events intentionally skipped"

watch_selection clipboard &
watch_selection primary --primary &

wait
