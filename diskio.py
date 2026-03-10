#!/usr/bin/env python3

import json
import os
import subprocess
import time
from pathlib import Path


def _run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()


def _read_int(path: Path) -> int | None:
    try:
        return int(path.read_text().strip())
    except Exception:
        return None


def _list_devices() -> list[str]:
    override = os.environ.get("DISKIO_DEVICE", "").strip()
    if override:
        return [override.removeprefix("/dev/").strip()]

    devices: list[str] = []
    try:
        for entry in Path("/sys/block").iterdir():
            name = entry.name
            if name.startswith(("zram", "loop", "ram")):
                continue
            devices.append(name)
    except Exception:
        return []

    return sorted(devices)


def _read_diskstats(name: str) -> dict[str, int] | None:
    try:
        for line in Path("/proc/diskstats").read_text().splitlines():
            parts = line.split()
            if len(parts) < 14 or parts[2] != name:
                continue
            return {
                "reads": int(parts[3]),
                "read_sectors": int(parts[5]),
                "writes": int(parts[7]),
                "write_sectors": int(parts[9]),
                "io_ms": int(parts[12]),
            }
    except Exception:
        return None
    return None


def _fmt_rate(bps: float) -> str:
    if bps < 0:
        bps = 0.0
    if bps < 1:
        return "0".rjust(6)
    kib = bps / 1024.0
    mib = kib / 1024.0
    gib = mib / 1024.0
    if gib >= 1:
        return f"{gib:.1f}G".rjust(6)
    if mib >= 10:
        return f"{mib:.0f}M".rjust(6)
    if mib >= 1:
        return f"{mib:.1f}M".rjust(6)
    if kib >= 10:
        return f"{kib:.0f}K".rjust(6)
    if kib >= 1:
        return f"{kib:.1f}K".rjust(6)
    return f"{bps:.0f}B".rjust(6)


def _short_dev(name: str) -> str:
    if name.startswith("nvme") and "n" in name[4:]:
        return name.replace("nvme", "nv", 1).replace("n", "", 1)
    if name.startswith(("sd", "vd")):
        return name
    return name[:4]


def main() -> None:
    devices = _list_devices()
    if not devices:
        print(json.dumps({"text": "disk?", "class": "error", "tooltip": "diskio: no block devices found"}))
        return

    state_path = Path("/tmp/waybar-diskio.json")
    now_ns = time.monotonic_ns()

    prev = None
    try:
        prev = json.loads(state_path.read_text())
    except Exception:
        prev = None

    now: dict[str, object] = {"t_ns": now_ns, "devices": {}}
    now_devices: dict[str, dict[str, int]] = {}
    for dev in devices:
        stats = _read_diskstats(dev)
        if stats:
            now_devices[dev] = stats
    now["devices"] = now_devices
    state_path.write_text(json.dumps(now))

    if not prev or "t_ns" not in prev or "devices" not in prev:
        idle_text = "0/0"
        print(json.dumps({"text": idle_text, "tooltip": "Disk I/O: initializing", "class": "idle"}))
        return

    dt = (now_ns - int(prev["t_ns"])) / 1e9
    if dt <= 0:
        dt = 1.0

    prev_devices = prev.get("devices", {})
    active: list[dict[str, object]] = []
    max_util = 0.0

    for dev, stats in now_devices.items():
        prev_stats = prev_devices.get(dev) if isinstance(prev_devices, dict) else None
        if not isinstance(prev_stats, dict):
            continue

        sector_size = _read_int(Path(f"/sys/block/{dev}/queue/hw_sector_size")) or 512

        d_read_sectors = int(stats["read_sectors"]) - int(prev_stats.get("read_sectors", stats["read_sectors"]))
        d_write_sectors = int(stats["write_sectors"]) - int(prev_stats.get("write_sectors", stats["write_sectors"]))
        d_reads = int(stats["reads"]) - int(prev_stats.get("reads", stats["reads"]))
        d_writes = int(stats["writes"]) - int(prev_stats.get("writes", stats["writes"]))
        d_io_ms = int(stats["io_ms"]) - int(prev_stats.get("io_ms", stats["io_ms"]))

        if d_read_sectors < 0:
            d_read_sectors = 0
        if d_write_sectors < 0:
            d_write_sectors = 0
        if d_reads < 0:
            d_reads = 0
        if d_writes < 0:
            d_writes = 0
        if d_io_ms < 0:
            d_io_ms = 0

        read_bps = (d_read_sectors * sector_size) / dt
        write_bps = (d_write_sectors * sector_size) / dt
        if read_bps < 1 and write_bps < 1:
            continue

        read_iops = d_reads / dt
        write_iops = d_writes / dt
        util = (d_io_ms / 1000.0) / dt * 100.0
        if util < 0:
            util = 0.0
        if util > 100:
            util = 100.0
        if util > max_util:
            max_util = util

        active.append(
            {
                "dev": dev,
                "read_bps": read_bps,
                "write_bps": write_bps,
                "read_iops": read_iops,
                "write_iops": write_iops,
                "util": util,
            }
        )

    if not active:
        idle_text = "0/0"
        print(json.dumps({"text": idle_text, "tooltip": "Disk I/O: idle", "class": "idle"}))
        return

    active.sort(key=lambda d: float(d["read_bps"]) + float(d["write_bps"]), reverse=True)

    text_parts = []
    for d in active:
        rates_text = f'{_fmt_rate(float(d["read_bps"])).strip()}/{_fmt_rate(float(d["write_bps"])).strip()}'
        if len(active) == 1:
            text_parts.append(rates_text)
        else:
            text_parts.append(f'{_short_dev(str(d["dev"]))} {rates_text}')
    text = " ".join(text_parts)
    tooltip = "\n".join(
        (
            f'{d["dev"]}: '
            f'R {float(d["read_bps"]) / 1048576.0:.2f} MiB/s ({float(d["read_iops"]):.0f} IOPS), '
            f'W {float(d["write_bps"]) / 1048576.0:.2f} MiB/s ({float(d["write_iops"]):.0f} IOPS), '
            f'Util {float(d["util"]):.0f}%'
        )
        for d in active
    )

    klass = "active" if max_util >= 20 else "idle"
    if max_util >= 80:
        klass = "busy"

    print(json.dumps({"text": text, "tooltip": tooltip, "class": klass}))


if __name__ == "__main__":
    main()
