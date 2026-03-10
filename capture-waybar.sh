#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
default_config="$script_dir/config.jsonc"
if [[ ! -f "$default_config" ]]; then
  default_config="${XDG_CONFIG_HOME:-$HOME/.config}/waybar/config.jsonc"
fi
config_file="${WAYBAR_CAPTURE_CONFIG:-$default_config}"
height="${WAYBAR_CAPTURE_HEIGHT:-40}"
outfile="${1:-/tmp/waybar-bottom.png}"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "missing required command: $1" >&2
    exit 1
  fi
}

require_cmd niri
require_cmd wf-recorder
require_cmd ffmpeg

if [[ ! -f "$config_file" ]]; then
  echo "waybar config not found: $config_file" >&2
  exit 1
fi

output_name="$(
  sed -n 's/.*"output":[[:space:]]*"\([^"]\+\)".*/\1/p' "$config_file" | head -n1
)"

if [[ -z "$output_name" ]]; then
  output_name="${WAYBAR_CAPTURE_OUTPUT:-}"
fi

if [[ -z "$output_name" ]]; then
  output_name="$(
    python3 - <<'PY'
import json
import subprocess

try:
    payload = subprocess.check_output(
        ["niri", "msg", "--json", "focused-output"],
        text=True,
    )
    data = json.loads(payload)
except Exception:
    data = {}

print(data.get("name", ""))
PY
  )"
fi

if [[ -z "$output_name" ]]; then
  echo "could not determine waybar output from config, env, or focused output" >&2
  exit 1
fi

geometry="$(
  python3 - "$output_name" <<'PY'
import json
import subprocess
import sys

target = sys.argv[1]
payload = subprocess.check_output(["niri", "msg", "--json", "outputs"], text=True)
data = json.loads(payload)
logical = data.get(target, {}).get("logical", {})

if logical:
    print(
        logical.get("x", ""),
        logical.get("y", ""),
        logical.get("width", ""),
        logical.get("height", ""),
    )
PY
)"

if [[ -z "$geometry" ]]; then
  echo "could not determine geometry for output $output_name" >&2
  exit 1
fi

read -r x y width output_height <<<"$geometry"

if (( height > output_height )); then
  height="$output_height"
fi

capture_y=$((y + output_height - height))
tmp_video="$(mktemp /tmp/waybar-bottom.XXXXXX.mp4)"
trap 'rm -f "$tmp_video"' EXIT

capture_status=0
timeout 2 wf-recorder -y -D -r 2 -g "$x,$capture_y ${width}x${height}" -f "$tmp_video" >/dev/null 2>&1 || capture_status=$?
if [[ "$capture_status" -ne 0 && "$capture_status" -ne 124 ]]; then
  exit "$capture_status"
fi

ffmpeg -loglevel error -y -i "$tmp_video" -frames:v 1 -update 1 "$outfile"

printf '%s\n' "$outfile"
