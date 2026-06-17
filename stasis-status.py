#!/usr/bin/env python3

import json
import subprocess
import sys


LEGEND = (
    "\n\nLegend:\n"
    "- WAIT: armed, waiting for the session to become idle.\n"
    "- RUN: idle detected, countdown/plan is advancing toward the next action.\n"
    "- HOLD: inhibited, but the source is not classified more specifically.\n"
    "- DBUS: inhibited by a D-Bus/logind/screensaver-style inhibit.\n"
    "- CALL: inhibited by active media or call activity.\n"
    "- APP: inhibited by a matched app rule.\n"
    "- PAUSE: manually inhibited via `stasis toggle-inhibit`.\n"
    "- DOWN: `stasis` daemon unavailable or probe failed."
)


TOOLTIP_NOTES = (
    "\n\nNotes:\n"
    "- ignore_remote_media=true: remote players do not inhibit idle.\n"
    "- Browser audio is not treated as regular media inhibit.\n"
    "- Browser calls rely on D-Bus inhibit or active mic/source-output.\n"
    "- Without a real mic/source-output, browser/portal may drop inhibit mid-call."
)


STATE_MAP = {
    "idle_waiting": {
        "text": "WAIT",
        "class": "waiting",
        "tooltip_prefix": "Stasis: armed\n",
    },
    "idle_active": {
        "text": "RUN",
        "class": "active",
        "tooltip_prefix": "Stasis: armed and counting down\n",
    },
    "idle_inhibited": {
        "text": "HOLD",
        "class": "inhibited",
        "tooltip_prefix": "Stasis: blocked by app/media/dbus inhibit\n",
    },
    "manually_inhibited": {
        "text": "PAUSE",
        "class": "manual",
        "tooltip_prefix": "Stasis: manually paused\n",
    },
    "not_running": {
        "text": "DOWN",
        "class": "down",
        "tooltip_prefix": "Stasis: daemon unavailable\n",
    },
}


def parse_bool_line(text: str, key: str) -> bool:
    prefix = f"{key}: "
    for line in text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip().lower() == "yes"
    return False


def parse_int_line(text: str, key: str) -> int:
    prefix = f"{key}: "
    for line in text.splitlines():
        if line.startswith(prefix):
            try:
                return int(line[len(prefix) :].strip())
            except ValueError:
                return 0
    return 0


def resolve_display(alt: str, tooltip_body: str) -> tuple[str, str, str]:
    mapped = STATE_MAP.get(
        alt,
        {
            "text": alt.upper(),
            "class": "unknown",
            "tooltip_prefix": "Stasis: unknown state\n",
        },
    )

    if alt != "idle_inhibited":
        return mapped["text"], mapped["class"], mapped["tooltip_prefix"]

    if parse_bool_line(tooltip_body, "D-Bus Inhibiting"):
        return "DBUS", "inhibited dbus", "Stasis: blocked by D-Bus inhibit\n"

    if parse_int_line(tooltip_body, "Media Players Playing") > 0:
        return "CALL", "inhibited call", "Stasis: blocked by media/call activity\n"

    if parse_int_line(tooltip_body, "Apps Inhibiting") > 0:
        return "APP", "inhibited app", "Stasis: blocked by app inhibit\n"

    return mapped["text"], mapped["class"], mapped["tooltip_prefix"]


def main() -> int:
    try:
        proc = subprocess.run(
            ["stasis", "info", "--json"],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(proc.stdout)
    except Exception as exc:
        json.dump(
            {
                "text": "DOWN",
                "class": "down",
                "tooltip": f"Stasis status probe failed:\n{exc}",
            },
            sys.stdout,
            ensure_ascii=False,
        )
        sys.stdout.write("\n")
        return 0

    alt = payload.get("alt", "not_running")
    tooltip_body = payload.get("tooltip", "").strip()
    text, css_class, tooltip_prefix = resolve_display(alt, tooltip_body)
    tooltip = (tooltip_prefix + tooltip_body).strip() + LEGEND + TOOLTIP_NOTES
    json.dump(
        {
            "text": text,
            "class": css_class,
            "tooltip": tooltip,
        },
        sys.stdout,
        ensure_ascii=False,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
