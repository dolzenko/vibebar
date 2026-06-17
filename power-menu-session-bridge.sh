#!/usr/bin/env bash
set -euo pipefail

runtime_dir="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
bridge_dir="$runtime_dir/waybar-power-menu"
fifo="$bridge_dir/action.fifo"
lock_file="$bridge_dir/bridge.lock"
log_file="${XDG_STATE_HOME:-$HOME/.local/state}/waybar/power-menu-bridge.log"

log() {
  mkdir -p "$(dirname "$log_file")"
  printf '%s %s\n' "$(date --iso-8601=seconds)" "$*" >>"$log_file"
}

if [[ -z "${XDG_SESSION_ID:-}" ]]; then
  log "refusing start without XDG_SESSION_ID"
  exit 0
fi

if [[ "$(loginctl show-session "$XDG_SESSION_ID" -P Remote 2>/dev/null || true)" != "no" ]]; then
  log "refusing remote session $XDG_SESSION_ID"
  exit 0
fi

if [[ "$(loginctl show-session "$XDG_SESSION_ID" -P Seat 2>/dev/null || true)" != "seat0" ]]; then
  log "refusing non-seat0 session $XDG_SESSION_ID"
  exit 0
fi

mkdir -p "$bridge_dir"
chmod 700 "$bridge_dir"

exec 9>"$lock_file"
if ! flock -n 9; then
  exit 0
fi

rm -f "$fifo"
mkfifo "$fifo"
chmod 600 "$fifo"

cleanup() {
  rm -f "$fifo"
}
trap cleanup EXIT

log "started for session $XDG_SESSION_ID at $fifo"

while true; do
  if ! IFS= read -r action <"$fifo"; then
    continue
  fi

  case "$action" in
    shutdown)
      log "poweroff requested"
      systemctl poweroff
      ;;
    reboot)
      log "reboot requested"
      systemctl reboot
      ;;
    suspend)
      log "suspend requested"
      systemctl suspend
      ;;
    hibernate)
      log "hibernate requested"
      systemctl hibernate
      ;;
    *)
      log "ignoring unknown action: $action"
      ;;
  esac
done
