#!/usr/bin/env bash
set -euo pipefail

refresh_waybar() {
  pkill -RTMIN+8 waybar || true
}

refresh_waybar

ip monitor link route |
while read -r _; do
  refresh_waybar
done
