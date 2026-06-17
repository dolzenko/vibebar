#!/usr/bin/env python3

import json
import subprocess
from collections import Counter
from dataclasses import dataclass
from typing import Final


MAX_TOOLTIP_UNITS: Final = 8
ACTIVE_STATES: Final = (
    "active",
    "activating",
    "deactivating",
    "failed",
    "inactive",
    "maintenance",
    "reloading",
    "refreshing",
)


@dataclass(frozen=True)
class UnitStats:
    total: int
    by_active_state: Counter[str]


def list_failed_units(args: list[str]) -> list[str]:
    proc = subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
    )
    units: list[str] = []
    for line in proc.stdout.splitlines():
        parts = line.split()
        if parts:
            units.append(parts[0])
    return units


def collect_service_stats(args: list[str]) -> UnitStats:
    proc = subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
    )
    counter: Counter[str] = Counter()
    total = 0
    for line in proc.stdout.splitlines():
        parts = line.split(None, 4)
        if len(parts) < 4:
            continue
        total += 1
        counter[parts[2]] += 1
    return UnitStats(total=total, by_active_state=counter)


def tooltip_block(title: str, units: list[str]) -> list[str]:
    if not units:
        return [f"{title}: none"]

    lines = [f"{title}: {len(units)}"]
    shown = units[:MAX_TOOLTIP_UNITS]
    lines.extend(f"  {unit}" for unit in shown)
    remaining = len(units) - len(shown)
    if remaining > 0:
        lines.append(f"  ... and {remaining} more")
    return lines


def stats_block(title: str, stats: UnitStats) -> list[str]:
    parts = [f"{state}={stats.by_active_state.get(state, 0)}" for state in ACTIVE_STATES]
    return [f"{title} services: total={stats.total}", "  " + " ".join(parts)]


def main() -> None:
    system_stats = collect_service_stats(
        ["systemctl", "list-units", "--type=service", "--all", "--no-legend", "--plain"]
    )
    user_stats = collect_service_stats(
        [
            "systemctl",
            "--user",
            "list-units",
            "--type=service",
            "--all",
            "--no-legend",
            "--plain",
        ]
    )
    system_units = list_failed_units(["systemctl", "--failed", "--no-legend", "--plain"])
    user_units = list_failed_units(
        ["systemctl", "--user", "--failed", "--no-legend", "--plain"]
    )

    system_count = len(system_units)
    user_count = len(user_units)
    total = system_count + user_count

    if total == 0:
        text = f"{system_stats.total}/{user_stats.total}"
        klass = "healthy"
    elif total < 3:
        text = f"(!){total} {system_stats.total}/{user_stats.total}"
        klass = "warn"
    else:
        text = f"(!){total} {system_stats.total}/{user_stats.total}"
        klass = "critical"

    tooltip = "\n".join(
        [
            f"systemd failures: {total}",
            *stats_block("System", system_stats),
            *stats_block("User", user_stats),
            *tooltip_block("System", system_units),
            *tooltip_block("User", user_units),
        ]
    )

    print(
        json.dumps(
            {
                "text": text,
                "tooltip": tooltip,
                "class": klass,
            }
        )
    )


if __name__ == "__main__":
    main()
