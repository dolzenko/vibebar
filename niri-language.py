#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import time


LAYOUT_MAP = {
    "English (US)": ("EN", "us"),
    "Russian": ("RU", "ru"),
}
PREFERRED_OSD_MONITOR = os.environ.get("VIBEBAR_OSD_MONITOR", "").strip()


def run_json(*args):
    proc = subprocess.run(
        args,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(proc.stdout)


def format_layout(names, idx):
    if not names:
        return {
            "text": "?",
            "tooltip": "Input layout: unknown",
            "class": "unknown",
        }

    safe_idx = max(0, min(idx, len(names) - 1))
    name = names[safe_idx]
    text, css_class = LAYOUT_MAP.get(name, (name, "unknown"))
    return {
        "text": text,
        "tooltip": f"Input layout: {name}",
        "class": css_class,
    }


def emit(payload):
    print(json.dumps(payload), flush=True)


def pick_osd_monitor():
    if PREFERRED_OSD_MONITOR:
        try:
            outputs = run_json("niri", "msg", "--json", "outputs")
        except Exception:
            outputs = None

        if isinstance(outputs, dict):
            if PREFERRED_OSD_MONITOR in outputs:
                return PREFERRED_OSD_MONITOR
        elif isinstance(outputs, list):
            for output in outputs:
                if isinstance(output, dict) and output.get("name") == PREFERRED_OSD_MONITOR:
                    return PREFERRED_OSD_MONITOR

    try:
        focused_output = run_json("niri", "msg", "--json", "focused-output")
    except Exception:
        focused_output = None

    if isinstance(focused_output, dict):
        return focused_output.get("name")

    return None


def show_osd(names, idx, text):
    client = shutil.which("swayosd-client")
    if client is None or not names:
        return

    monitor = pick_osd_monitor()

    segmented = f"{max(0, idx) + 1}:{len(names)}"
    cmd = [
        client,
        "--custom-segmented-progress",
        segmented,
        "--custom-progress-text",
        text,
        "--custom-icon",
        "input-keyboard-symbolic",
    ]
    if monitor:
        cmd.extend(["--monitor", monitor])

    subprocess.run(
        cmd,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def current_state():
    payload = run_json("niri", "msg", "--json", "keyboard-layouts")
    names = payload.get("names", [])
    current_idx = int(payload.get("current_idx", 0))
    return names, current_idx


def handle_event(event, names, current_idx):
    if "KeyboardLayoutsChanged" in event:
        keyboard_layouts = event["KeyboardLayoutsChanged"]["keyboard_layouts"]
        names = keyboard_layouts.get("names", names)
        current_idx = int(keyboard_layouts.get("current_idx", current_idx))
        return names, current_idx, True, False

    if "KeyboardLayoutSwitched" in event:
        current_idx = int(event["KeyboardLayoutSwitched"]["idx"])
        return names, current_idx, True, True

    return names, current_idx, False, False


def event_stream():
    proc = subprocess.Popen(
        ["niri", "msg", "--json", "event-stream"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        yield json.loads(line)
    proc.wait()
    raise RuntimeError(f"niri event stream exited with code {proc.returncode}")


def main():
    names = []
    current_idx = 0
    last_payload = None

    while True:
        try:
            names, current_idx = current_state()
            payload = format_layout(names, current_idx)
            emit(payload)
            last_payload = payload

            for event in event_stream():
                names, current_idx, changed, should_osd = handle_event(
                    event, names, current_idx
                )
                if not changed:
                    continue

                payload = format_layout(names, current_idx)
                if payload != last_payload:
                    emit(payload)
                    last_payload = payload

                if should_osd:
                    show_osd(names, current_idx, payload["text"])
        except KeyboardInterrupt:
            return
        except Exception as exc:
            print(f"niri-language watcher error: {exc}", file=sys.stderr, flush=True)
            time.sleep(1)


if __name__ == "__main__":
    main()
