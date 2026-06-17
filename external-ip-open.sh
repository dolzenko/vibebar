#!/usr/bin/env bash
set -euo pipefail

state_path="/tmp/waybar-external-ip.json"

if [[ ! -s "$state_path" ]]; then
  exit 0
fi

url="$(
  python3 - "$state_path" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text())
url = payload.get("url", "")
if isinstance(url, str):
    print(url, end="")
PY
)"

if [[ -z "$url" ]]; then
  exit 0
fi

exec xdg-open "$url"
