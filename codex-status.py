#!/usr/bin/env python3
import json
import math
import os
from pathlib import Path
import time

SESSIONS_ROOT = Path.home() / ".codex" / "sessions"
BAR_WIDTH = 20
RECENT_SESSION_FILES = 24


def iter_lines_reverse(path):
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        position = handle.tell()
        buffer = b""

        while position > 0:
            chunk_size = min(8192, position)
            position -= chunk_size
            handle.seek(position)
            buffer = handle.read(chunk_size) + buffer
            lines = buffer.split(b"\n")
            buffer = lines[0]

            for line in reversed(lines[1:]):
                if line:
                    yield line

        if buffer:
            yield buffer


def find_recent_session_files():
    if not SESSIONS_ROOT.exists():
        return []

    paths = []
    for path in SESSIONS_ROOT.rglob("*.jsonl"):
        try:
            stat = path.stat()
        except OSError:
            continue
        paths.append((stat.st_mtime, path))

    paths.sort(reverse=True)
    return [path for _, path in paths[:RECENT_SESSION_FILES]]


def merge_limit(best_limit, candidate):
    if best_limit is None:
        return dict(candidate)

    if int(candidate.get("resets_at", 0)) != int(best_limit.get("resets_at", 0)):
        candidate_reset = int(candidate.get("resets_at", 0))
        best_reset = int(best_limit.get("resets_at", 0))
        return dict(candidate if candidate_reset > best_reset else best_limit)

    if float(candidate.get("used_percent", 0.0)) > float(best_limit.get("used_percent", 0.0)):
        return dict(candidate)

    return best_limit


def load_rate_limits():
    best = None

    for path in find_recent_session_files():
        for raw_line in iter_lines_reverse(path):
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError:
                continue

            if event.get("type") != "event_msg":
                continue

            payload = event.get("payload", {})
            if payload.get("type") != "token_count":
                continue

            rate_limits = payload.get("rate_limits")
            if not rate_limits:
                continue

            primary = rate_limits.get("primary")
            secondary = rate_limits.get("secondary")
            if primary and secondary:
                snapshot = {
                    "path": str(path),
                    "timestamp": event.get("timestamp", ""),
                    "primary": dict(primary),
                    "secondary": dict(secondary),
                    "plan_type": rate_limits.get("plan_type"),
                }
                if best is None:
                    best = snapshot
                    continue

                best["primary"] = merge_limit(best["primary"], snapshot["primary"])
                best["secondary"] = merge_limit(best["secondary"], snapshot["secondary"])

                if snapshot["timestamp"] > best["timestamp"]:
                    best["timestamp"] = snapshot["timestamp"]
                    best["path"] = snapshot["path"]
                    best["plan_type"] = snapshot["plan_type"]

                break

    return best


def left_percent(limit):
    used = float(limit.get("used_percent", 0.0))
    return max(0, min(100, int(round(100 - used))))


def format_bar(percent_left):
    filled = max(0, min(BAR_WIDTH, math.floor(percent_left * BAR_WIDTH / 100)))
    return "█" * filled + "░" * (BAR_WIDTH - filled)


def format_reset(epoch, include_date):
    stamp = time.localtime(epoch)
    if include_date:
        return time.strftime("%H:%M on %d %b", stamp)
    return time.strftime("%H:%M", stamp)


def build_tooltip(limit_name, limit, include_date):
    percent_left = left_percent(limit)
    reset_at = int(limit.get("resets_at", 0))
    return (
        f"{limit_name:<20} [{format_bar(percent_left)}] "
        f"{percent_left}% left (resets {format_reset(reset_at, include_date)})"
    )


def build_class(primary_left, secondary_left):
    remaining = min(primary_left, secondary_left)
    if remaining <= 10:
        return ["critical"]
    if remaining <= 25:
        return ["warning"]
    return ["healthy"]


def main():
    snapshot = load_rate_limits()
    if snapshot is None:
        print(json.dumps({"text": "", "tooltip": "", "class": ["hidden"]}))
        return

    primary_left = left_percent(snapshot["primary"])
    secondary_left = left_percent(snapshot["secondary"])
    text = f"ctx {primary_left}%/{secondary_left}%"
    tooltip = "\n".join(
        [
            build_tooltip("5h limit:", snapshot["primary"], include_date=False),
            build_tooltip("Weekly limit:", snapshot["secondary"], include_date=True),
        ]
    )

    print(
        json.dumps(
            {
                "text": text,
                "tooltip": tooltip,
                "class": build_class(primary_left, secondary_left),
            }
        )
    )


if __name__ == "__main__":
    main()
