#!/usr/bin/env python3

import json
import shutil
import subprocess


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
    )


def player_list() -> list[str]:
    proc = run("playerctl", "-l")
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def metadata_for(player: str) -> dict[str, str] | None:
    status = run("playerctl", "-p", player, "status")
    if status.returncode != 0:
        return None

    metadata = run(
        "playerctl",
        "-p",
        player,
        "metadata",
        "--format",
        "{{artist}}\t{{title}}\t{{album}}",
    )
    if metadata.returncode != 0:
        return None

    artist, title, album = (metadata.stdout.rstrip("\n").split("\t") + ["", "", ""])[:3]
    return {
        "player": player,
        "status": status.stdout.strip(),
        "artist": artist.strip(),
        "title": title.strip(),
        "album": album.strip(),
    }


def pick_now_playing() -> dict[str, str] | None:
    players = player_list()
    if not players:
        return None

    for wanted in ("Playing", "Paused"):
        for player in players:
            payload = metadata_for(player)
            if payload and payload["status"] == wanted:
                return payload
    return None


def main() -> None:
    if shutil.which("playerctl") is None:
        print(json.dumps({"text": "", "tooltip": "playerctl is not installed", "class": "empty"}))
        return

    payload = pick_now_playing()
    if payload is None:
        print(json.dumps({"text": "", "tooltip": "No active media player", "class": "empty"}))
        return

    artist = payload["artist"]
    title = payload["title"] or payload["player"]
    text = f"{artist} - {title}" if artist else title

    tooltip_lines = [
        f'Player: {payload["player"]}',
        f'Status: {payload["status"]}',
    ]
    if artist:
        tooltip_lines.append(f"Artist: {artist}")
    if payload["title"]:
        tooltip_lines.append(f'Title: {payload["title"]}')
    if payload["album"]:
        tooltip_lines.append(f'Album: {payload["album"]}')

    print(
        json.dumps(
            {
                "text": text,
                "tooltip": "\n".join(tooltip_lines),
                "alt": payload["player"],
                "class": payload["status"].lower(),
            }
        )
    )


if __name__ == "__main__":
    main()
