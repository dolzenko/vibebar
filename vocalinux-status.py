#!/usr/bin/env python3
import json
from pathlib import Path
from typing import Iterable

STATE_PATH = Path("/tmp/waybar-vocalinux.json")
VOCALINUX_EXECUTABLES = {
    str(Path.home() / ".local/bin/vocalinux"),
    str(Path.home() / ".local/share/vocalinux/venv/bin/vocalinux"),
    "vocalinux",
}
HIDDEN_PAYLOAD = {
    "text": "",
    "tooltip": "Vocalinux idle",
    "class": "hidden",
}


def emit(payload):
    print(json.dumps(payload), flush=True)


def iter_proc_cmdlines() -> Iterable[str]:
    for proc_dir in Path("/proc").iterdir():
        if not proc_dir.name.isdigit():
            continue

        try:
            cmdline = (proc_dir / "cmdline").read_bytes()
        except OSError:
            continue

        if not cmdline:
            continue

        yield cmdline.replace(b"\x00", b" ").decode("utf-8", errors="ignore").strip()


def vocalinux_running() -> bool:
    for cmdline in iter_proc_cmdlines():
        parts = cmdline.split()
        if any(
            part in VOCALINUX_EXECUTABLES or Path(part).name == "vocalinux"
            for part in parts
        ):
            return True

    return False


def main():
    try:
        payload = json.loads(STATE_PATH.read_text())
    except Exception:
        emit(HIDDEN_PAYLOAD)
        return

    if not payload.get("active") or not vocalinux_running():
        emit(HIDDEN_PAYLOAD)
        return

    emit(
        {
            "text": str(payload.get("text") or "\uf130 DICT"),
            "tooltip": str(payload.get("tooltip") or "Vocalinux dictation active"),
            "class": str(payload.get("class") or "active"),
        }
    )


if __name__ == "__main__":
    main()
