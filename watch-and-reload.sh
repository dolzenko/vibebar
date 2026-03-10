#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONF_DIR="${CONF_DIR:-$SCRIPT_DIR}"

reload_waybar() {
  pkill -SIGUSR2 waybar || true
}

paths=()

[[ -f "$CONF_DIR/config" ]] && paths+=("$CONF_DIR/config")
[[ -f "$CONF_DIR/config.jsonc" ]] && paths+=("$CONF_DIR/config.jsonc")
[[ -f "$CONF_DIR/style.css" ]] && paths+=("$CONF_DIR/style.css")

# If nothing to watch, bail with message
if ((${#paths[@]} == 0)); then
  echo "No Waybar config/style files found in $CONF_DIR" >&2
  exit 1
fi

inotifywait -m -e close_write,create,delete,move "${paths[@]}" |
while read -r _; do
  reload_waybar
done
