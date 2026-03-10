#!/usr/bin/env bash
set -euo pipefail

ip="$(
  curl -s --max-time 2 ifconfig.me 2>/dev/null \
    | tr -d '\r\n' \
    | sed -E 's/[[:space:]]+//g'
)"

if [[ -z "${ip}" ]]; then
  printf '{"text":"?","tooltip":"External IP unavailable","class":"error"}\n'
  exit 0
fi

printf '{"text":"%s","tooltip":"External IP: %s"}\n' "$ip" "$ip"
