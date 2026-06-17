#!/usr/bin/env bash
set -euo pipefail

action="${1:?missing action}"

case "$action" in
  shutdown)
    can_method="CanPowerOff"
    human_label="power off"
    cmd=(systemctl poweroff)
    ;;
  reboot)
    can_method="CanReboot"
    human_label="reboot"
    cmd=(systemctl reboot)
    ;;
  suspend)
    can_method="CanSuspend"
    human_label="suspend"
    cmd=(systemctl suspend)
    ;;
  hibernate)
    can_method="CanHibernate"
    human_label="hibernate"
    cmd=(systemctl hibernate)
    ;;
  *)
    printf 'unknown action: %s\n' "$action" >&2
    exit 2
    ;;
esac

notify() {
  if command -v notify-send >/dev/null 2>&1; then
    notify-send "Waybar power menu" "$1"
  fi
}

request_session_bridge() {
  local bridge_fifo="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/waybar-power-menu/action.fifo"

  if [ ! -p "$bridge_fifo" ]; then
    return 1
  fi

  timeout 2s bash -c 'printf "%s\n" "$1" >"$2"' _ "$action" "$bridge_fifo"
}

can_value="$(
  busctl call \
    org.freedesktop.login1 \
    /org/freedesktop/login1 \
    org.freedesktop.login1.Manager \
    "$can_method" |
    awk -F'"' 'NF >= 2 { print $2 }'
)"

case "$can_value" in
  yes)
    exec "${cmd[@]}"
    ;;
  no)
    notify "logind reports that ${human_label} is not allowed"
    exit 1
    ;;
  challenge)
    if request_session_bridge; then
      notify "requested ${human_label}"
      exit 0
    fi

    direct_error="$("${cmd[@]}" 2>&1)" && exit 0

    notify "failed to ${human_label}: ${direct_error}"
    printf '%s\n' "$direct_error" >&2
    exit 1
    ;;
  *)
    notify "unexpected logind response for ${human_label}: ${can_value}"
    exit 1
    ;;
esac
