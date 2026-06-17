#!/usr/bin/env python3

import argparse
import json
import subprocess

MAX_TEXT = 36
MAX_TOOLTIP = 400
PLAIN_TEXT_MIME_TYPES = (
    "text/plain;charset=utf-8",
    "text/plain",
    "UTF8_STRING",
    "STRING",
    "TEXT",
)


def run_wl_paste(*args: str) -> str:
    proc = subprocess.run(
        ["wl-paste", "--no-newline", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return ""
    return proc.stdout


def compact_whitespace(text: str) -> str:
    return " ".join(text.split())


def clip_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def read_selection(*args: str) -> tuple[str, str]:
    mime_types_output = run_wl_paste(*args, "--list-types")
    if not mime_types_output:
        return "unavailable", ""

    mime_types = tuple(
        mime_type.strip()
        for mime_type in mime_types_output.splitlines()
        if mime_type.strip()
    )

    for mime_type in PLAIN_TEXT_MIME_TYPES:
        if mime_type not in mime_types:
            continue
        text = compact_whitespace(run_wl_paste(*args, "--type", mime_type))
        if text:
            return "text", text

    image_mime_types = tuple(
        mime_type for mime_type in mime_types if mime_type.startswith("image/")
    )
    if image_mime_types:
        return "image", ", ".join(image_mime_types[:3])

    return "binary", ""


def format_label(prefix: str, status: str, text: str) -> str:
    if status == "text":
        return f"{prefix}:{text}"
    if status == "image":
        return f"{prefix}:[img]"
    if status == "binary":
        return f"{prefix}:[bin]"
    return f"{prefix}:[-]"


def format_tooltip(title: str, status: str, text: str) -> str:
    if status == "text":
        return f"{title}: {clip_text(text, MAX_TOOLTIP)}"
    if status == "image":
        return f"{title}: image content ({text})"
    if status == "binary":
        return f"{title}: non-text content"
    return f"{title}: unavailable"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--selection",
        choices=("clipboard", "primary"),
        default="clipboard",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.selection == "primary":
        status, text = read_selection("--primary")
        label = format_label("P", status, text)
        tooltip = format_tooltip("Primary", status, text)
    else:
        status, text = read_selection()
        label = format_label("C", status, text)
        tooltip = format_tooltip("Clipboard", status, text)

    label = clip_text(label, MAX_TEXT)
    if status == "unavailable":
        klass = "empty"
    elif status in ("binary", "image"):
        klass = "binary"
    else:
        klass = "text"

    print(json.dumps({"text": label, "tooltip": tooltip, "class": klass}))


if __name__ == "__main__":
    main()
