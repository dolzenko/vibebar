#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
local_env="$script_dir/local.env"

if [[ -f "$local_env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$local_env"
  set +a
fi

case "${1:-google}" in
  google)
    calendar_url="https://calendar.google.com/"
    ;;
  work)
    calendar_url="${VIBEBAR_WORK_CALENDAR_URL:-}"
    ;;
  http://*|https://*)
    calendar_url="$1"
    ;;
  *)
    calendar_url=""
    ;;
esac

if [[ -z "$calendar_url" ]]; then
  exit 0
fi

focus_browser_window() {
  local window_id

  window_id="$(
    niri msg --json windows 2>/dev/null | jq -r '
      map(
        select(
          ((.app_id // "") | test("firefox|chrom|browser"; "i")) or
          ((.title // "") | test("firefox|chrome|chromium|calendar"; "i"))
        )
      )
      | sort_by(.focus_timestamp.secs, .focus_timestamp.nanos)
      | last
      | .id // empty
    '
  )"

  if [[ -n "$window_id" ]]; then
    niri msg action focus-window --id "$window_id" >/dev/null 2>&1 || true
    return 0
  fi

  return 1
}

if command -v firefox >/dev/null 2>&1; then
  firefox --new-tab "$calendar_url" >/dev/null 2>&1 &
else
  xdg-open "$calendar_url" >/dev/null 2>&1 &
fi

for _ in {1..15}; do
  if focus_browser_window; then
    exit 0
  fi
  sleep 0.2
done
