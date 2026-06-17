#!/usr/bin/env python3

import json
import math
import time
from pathlib import Path


STATE_PATH = Path("/tmp/waybar-cpu-temp.json")


def find_coretemp_package_sensor() -> tuple[Path, str] | None:
    for hwmon in sorted(Path("/sys/class/hwmon").glob("hwmon*")):
        try:
            name = (hwmon / "name").read_text(encoding="ascii").strip()
        except OSError:
            continue
        if name != "coretemp":
            continue

        for label_path in sorted(hwmon.glob("temp*_label")):
            try:
                label = label_path.read_text(encoding="ascii").strip()
            except OSError:
                continue
            if label != "Package id 0":
                continue

            temp_path = label_path.with_name(label_path.name.replace("_label", "_input"))
            if temp_path.exists():
                return temp_path, "coretemp Package id 0"

    return None


def find_sensor() -> tuple[Path, str]:
    coretemp_package = find_coretemp_package_sensor()
    if coretemp_package is not None:
        return coretemp_package

    for zone in sorted(Path("/sys/class/thermal").glob("thermal_zone*")):
        type_path = zone / "type"
        temp_path = zone / "temp"
        try:
            zone_type = type_path.read_text(encoding="ascii").strip()
        except OSError:
            continue
        if zone_type == "x86_pkg_temp" and temp_path.exists():
            return temp_path, zone_type

    for zone in sorted(Path("/sys/class/thermal").glob("thermal_zone*")):
        temp_path = zone / "temp"
        if temp_path.exists():
            try:
                zone_type = (zone / "type").read_text(encoding="ascii").strip()
            except OSError:
                zone_type = zone.name
            return temp_path, zone_type

    raise FileNotFoundError("no thermal zone with temp file found")


def read_temp_c(path: Path) -> float:
    raw = path.read_text(encoding="ascii").strip()
    return int(raw) / 1000.0


def load_state() -> dict[str, float | str]:
    try:
        data = json.loads(STATE_PATH.read_text(encoding="ascii"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    state: dict[str, float | str] = {}
    for key, value in data.items():
        if key == "sensor" and isinstance(value, str):
            state[key] = value
        elif isinstance(value, (int, float)):
            state[key] = float(value)
    return state


def save_state(state: dict[str, float | str]) -> None:
    tmp_path = STATE_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(state), encoding="ascii")
    tmp_path.replace(STATE_PATH)


def update_ema(prev: float, current: float, dt: float, tau_seconds: float) -> float:
    alpha = 1.0 - math.exp(-dt / tau_seconds)
    return prev + alpha * (current - prev)


def main() -> None:
    sensor_path, sensor_name = find_sensor()
    current_c = read_temp_c(sensor_path)
    now = time.monotonic()

    state = load_state()
    prev_ts = state.get("ts", now)
    dt = max(now - prev_ts, 1e-6)

    if state.get("sensor") == sensor_name:
        ema_60 = update_ema(state.get("ema_60", current_c), current_c, dt, 60.0)
        ema_300 = update_ema(state.get("ema_300", current_c), current_c, dt, 300.0)
    else:
        ema_60 = current_c
        ema_300 = current_c

    save_state({"ts": now, "sensor": sensor_name, "ema_60": ema_60, "ema_300": ema_300})

    trend_delta = ema_60 - ema_300
    if trend_delta >= 1.0:
        trend = "rising"
    elif trend_delta <= -1.0:
        trend = "falling"
    else:
        trend = "stable"

    if current_c >= 85.0:
        klass = "critical"
    elif current_c >= 75.0:
        klass = "hot"
    else:
        klass = "normal"

    text = f"{current_c:.0f}°/{ema_60:.0f}°"
    tooltip = "\n".join(
        [
            f"CPU package temp ({sensor_name})",
            f"Current: {current_c:.1f}C",
            f"1m EMA: {ema_60:.1f}C",
            f"5m EMA: {ema_300:.1f}C",
            f"Trend: {trend}",
            "Chip text: current / 1m average",
        ]
    )

    print(json.dumps({"text": text, "tooltip": tooltip, "class": klass}))


if __name__ == "__main__":
    main()
