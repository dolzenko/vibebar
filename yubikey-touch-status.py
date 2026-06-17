#!/usr/bin/env python3
import json
import os
from pathlib import Path


STALE_AFTER_SECONDS = 15


def state_path():
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir:
        return Path(runtime_dir) / "yubikey-touch-osd" / "waybar.json"

    return Path(f"/run/user/{os.getuid()}") / "yubikey-touch-osd" / "waybar.json"


def hidden():
    return {
        "text": "",
        "tooltip": "YubiKey touch: inactive",
        "class": "hidden",
    }


def main():
    path = state_path()
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print(json.dumps(hidden()), flush=True)
        return

    label = str(state.get("label") or "").strip()
    active = bool(state.get("active")) and bool(label)
    updated_at = float(state.get("updated_at") or 0)

    if not active:
        print(json.dumps(hidden()), flush=True)
        return

    age = max(0, int(__import__("time").time() - updated_at))
    if age > STALE_AFTER_SECONDS:
        payload = hidden()
        payload["tooltip"] = f"YubiKey touch: stale {label}"
        print(json.dumps(payload), flush=True)
        return

    print(
        json.dumps(
            {
                "text": f"YK {label}",
                "tooltip": f"YubiKey waits for touch: {label}",
                "class": ["active", label.lower()],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
