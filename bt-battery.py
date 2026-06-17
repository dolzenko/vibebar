#!/usr/bin/env python3
import json
import re
import subprocess


BATTERY_RE = re.compile(r"Battery Percentage:\s+0x[0-9a-fA-F]+\s+\((\d+)\)")
DEVICE_RE = re.compile(r"^Device\s+([0-9A-Fa-f:]{17})\s+(.+)$")
ICON_RE = re.compile(r"^\s*Icon:\s+(.+)$", re.MULTILINE)
NAME_RE = re.compile(r"^\s*Name:\s+(.+)$", re.MULTILINE)
HID_UUID_RE = re.compile(r"Human Interface Device")


def run_bluetoothctl(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bluetoothctl", *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=3,
    )


def connected_devices() -> list[tuple[str, str]]:
    proc = run_bluetoothctl("devices", "Connected")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "bluetoothctl failed")

    devices = []
    for line in proc.stdout.splitlines():
        match = DEVICE_RE.match(line)
        if match:
            devices.append((match.group(1), match.group(2)))
    return devices


def device_info(address: str) -> str:
    proc = run_bluetoothctl("info", address)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "bluetoothctl info failed")
    return proc.stdout


def hid_kind(info: str, fallback_name: str) -> str | None:
    icon_match = ICON_RE.search(info)
    icon = icon_match.group(1).strip() if icon_match else ""
    name = fallback_name.lower()

    if icon == "input-keyboard" or "keyboard" in name or "kbd" in name:
        return "keyboard"
    if icon == "input-mouse" or "mouse" in name:
        return "mouse"
    if icon.startswith("input-") and HID_UUID_RE.search(info):
        return "input"
    return None


def short_name(info: str, fallback_name: str) -> str:
    match = NAME_RE.search(info)
    name = match.group(1).strip() if match else fallback_name
    return name.split()[0] if name else "BT"


def battery_percent(info: str) -> int | None:
    match = BATTERY_RE.search(info)
    return int(match.group(1)) if match else None


def device_icon(kind: str) -> str:
    if kind == "keyboard":
        return ""
    if kind == "mouse":
        return "󰍽"
    return ""


def hidden_payload(tooltip: str = "") -> dict[str, object]:
    return {"text": "", "tooltip": tooltip, "class": ["hidden"]}


def main() -> int:
    entries = []
    classes = []

    for address, fallback_name in connected_devices():
        info = device_info(address)
        kind = hid_kind(info, fallback_name)
        if kind is None:
            continue

        percent = battery_percent(info)
        if percent is None:
            continue

        name = short_name(info, fallback_name)
        entries.append((kind, name, percent))
        if percent < 10:
            classes.append("critical")

    if not entries:
        print(json.dumps(hidden_payload("No connected Bluetooth keyboard or mouse with battery data")))
        return 0

    text = " ".join(f"{device_icon(kind)} {percent}%" for kind, _name, percent in entries)
    tooltip = "\n".join(f"{name}: {percent}%" for _kind, name, percent in entries)
    print(json.dumps({"text": text, "tooltip": tooltip, "class": classes}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.TimeoutExpired:
        print(json.dumps({"text": "BT --", "tooltip": "bluetoothctl timed out", "class": "error"}))
        raise SystemExit(0)
    except Exception as exc:
        print(json.dumps({"text": "BT --", "tooltip": str(exc), "class": "error"}))
        raise SystemExit(0)
