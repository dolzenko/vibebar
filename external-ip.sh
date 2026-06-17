#!/usr/bin/env bash
set -euo pipefail

state_path="/tmp/waybar-external-ip.json"
ip="$(
  env -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY \
    curl -s --max-time 2 ifconfig.me 2>/dev/null \
    | tr -d '\r\n' \
    | sed -E 's/[[:space:]]+//g'
)"

if [[ -z "${ip}" ]]; then
  payload='{"text":"?","tooltip":"External IP unavailable","class":"error"}'
  printf '%s\n' "$payload" | tee "$state_path"
  exit 0
fi

payload="$(printf '{"text":"%s","tooltip":"External IP: %s","url":"https://ipinfo.io/%s"}' "$ip" "$ip" "$ip")"
printf '%s\n' "$payload" | tee "$state_path"
