#!/usr/bin/env bash
set -u

log_root="${XDG_STATE_HOME:-$HOME/.local/state}/waybar"
mkdir -p "$log_root/runs"
runs_retention_days=2
runs_retention_minutes=$((runs_retention_days * 24 * 60))
plain_log_max_bytes=$((1024 * 1024))
plain_log_keep_lines=2000

run_id="$(date +%Y%m%d-%H%M%S)"
run_dir="$log_root/runs/$run_id"
mkdir -p "$run_dir"

log_file="$run_dir/waybar.log"
meta_file="$run_dir/meta.log"
env_file="$run_dir/env.log"
systemd_env_file="$run_dir/systemd-environment.log"
systemd_status_file="$run_dir/systemd-status.log"
boot_journal_file="$run_dir/user-journal-boot.log"
session_journal_file="$run_dir/session-journal.log"
summary_file="$log_root/startup.log"

rotate_plain_log() {
  local file="$1"
  if [ ! -f "$file" ]; then
    return
  fi
  local size
  size="$(wc -c <"$file")"
  if [ "$size" -le "$plain_log_max_bytes" ]; then
    return
  fi
  local tmp
  tmp="$(mktemp "$log_root/.rotate.XXXXXX")" || return
  tail -n "$plain_log_keep_lines" "$file" >"$tmp" && mv "$tmp" "$file"
}

latest_link="$log_root/latest"
rm -f "$latest_link"
ln -s "$run_dir" "$latest_link"

find "$log_root/runs" -mindepth 1 -maxdepth 1 -type d -mmin +"$runs_retention_minutes" -exec rm -rf {} +
rotate_plain_log "$summary_file"
rotate_plain_log "$log_root/clipboard-watch.log"

start_iso="$(date --iso-8601=seconds)"
start_short="$(date '+%F %T')"

default_args=(
  -l warning
  -c "$HOME/.config/waybar/config.jsonc"
  -s "$HOME/.config/waybar/style.css"
)

if [ "$#" -gt 0 ]; then
  cmd=(/usr/bin/waybar "$@")
else
  cmd=(/usr/bin/waybar "${default_args[@]}")
fi

{
  printf 'run_dir=%s\n' "$run_dir"
  printf 'start=%s\n' "$start_iso"
  printf 'cwd=%s\n' "$(pwd)"
  printf 'WAYLAND_DISPLAY=%s\n' "${WAYLAND_DISPLAY:-}"
  printf 'DISPLAY=%s\n' "${DISPLAY:-}"
  printf 'XDG_CURRENT_DESKTOP=%s\n' "${XDG_CURRENT_DESKTOP:-}"
  printf 'XDG_SESSION_TYPE=%s\n' "${XDG_SESSION_TYPE:-}"
  printf 'XDG_SESSION_DESKTOP=%s\n' "${XDG_SESSION_DESKTOP:-}"
  printf 'DESKTOP_SESSION=%s\n' "${DESKTOP_SESSION:-}"
  printf 'NIRI_SOCKET=%s\n' "${NIRI_SOCKET:-}"
  printf 'PATH=%s\n' "${PATH:-}"
  printf 'cmd='
  printf '%q ' "${cmd[@]}"
  printf '\n'
} >"$meta_file"

{
  printf 'DISPLAY=%s\n' "${DISPLAY:-}"
  printf 'NIRI_SOCKET=%s\n' "${NIRI_SOCKET:-}"
  printf 'PATH=%s\n' "${PATH:-}"
  printf 'WAYLAND_DISPLAY=%s\n' "${WAYLAND_DISPLAY:-}"
  printf 'XDG_CURRENT_DESKTOP=%s\n' "${XDG_CURRENT_DESKTOP:-}"
  printf 'XDG_RUNTIME_DIR=%s\n' "${XDG_RUNTIME_DIR:-}"
  printf 'XDG_SESSION_TYPE=%s\n' "${XDG_SESSION_TYPE:-}"
} >"$env_file"
systemctl --user show-environment 2>/dev/null \
  | grep -E '^(DISPLAY|NIRI_SOCKET|PATH|WAYLAND_DISPLAY|XDG_CURRENT_DESKTOP|XDG_RUNTIME_DIR|XDG_SESSION_TYPE)=' \
  >"$systemd_env_file" || true
systemctl --user status waybar --no-pager >"$systemd_status_file" 2>&1 || true
journalctl --user -b --no-pager -o short-precise >"$boot_journal_file" 2>&1 || true

{
  printf '=== %s ===\n' "$start_iso"
  printf 'run_dir=%s\n' "$run_dir"
  printf 'log=%s\n' "$log_file"
  printf 'meta=%s\n' "$meta_file"
  printf 'journal=%s\n' "$session_journal_file"
} >>"$summary_file"

finish() {
  rc=$?
  end_iso="$(date --iso-8601=seconds)"
  {
    printf 'exit_code=%s\n' "$rc"
    printf 'end=%s\n' "$end_iso"
  } >>"$meta_file"
  systemctl --user status waybar --no-pager >>"$systemd_status_file" 2>&1 || true
  journalctl --user --since "$start_short" --no-pager -o short-precise >"$session_journal_file" 2>&1 || true
}

trap finish EXIT

{
  printf '[wrapper] exec start %s\n' "$start_iso"
  printf '[wrapper] run_dir=%s\n' "$run_dir"
} >>"$log_file"

unset G_MESSAGES_DEBUG
export WAYBAR_LOG_LEVEL=warning

"${cmd[@]}" >>"$log_file" 2>&1
