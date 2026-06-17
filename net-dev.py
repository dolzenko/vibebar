#!/usr/bin/env python3
import argparse
import json
import os
import re
import socket
import subprocess
import time
from pathlib import Path


STATE_ROOT = Path("/tmp")
EXCLUDED_PREFIXES = (
    "lo",
    "docker",
    "veth",
    "br-",
    "virbr",
    "vmnet",
    "vboxnet",
    "lxc",
    "lxd",
    "podman",
    "cni",
    "flannel",
    "tun",
    "tap",
    "wg",
    "tailscale",
    "nordlynx",
    "proton",
    "mullvad",
    "outline",
    "vpn",
    "ppp",
    "ipsec",
    "zt",
    "zerotier",
    "warp",
)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="ascii").strip()
    except OSError:
        return ""


def read_int(path: Path) -> int:
    try:
        return int(read_text(path))
    except ValueError:
        return 0


def interfaces() -> list[str]:
    try:
        return sorted(path.name for path in Path("/sys/class/net").iterdir())
    except OSError:
        return []


def operstate(name: str) -> str:
    return read_text(Path("/sys/class/net") / name / "operstate") or "unknown"


def has_ipv4(name: str) -> bool:
    proc = subprocess.run(
        ["ip", "-j", "-4", "addr", "show", "dev", name],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if proc.returncode != 0:
        return False
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return False
    return bool(data and data[0].get("addr_info"))


def ipv4_addr(name: str) -> str | None:
    proc = subprocess.run(
        ["ip", "-j", "-4", "addr", "show", "dev", name],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    for item in data:
        for addr in item.get("addr_info", []):
            local = addr.get("local")
            prefix = addr.get("prefixlen")
            if local:
                return f"{local}/{prefix}" if prefix is not None else local
    return None


def default_route_ifaces() -> list[str]:
    proc = subprocess.run(
        ["ip", "-j", "route", "show", "default"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if proc.returncode != 0:
        return []
    try:
        routes = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []
    return [route["dev"] for route in routes if "dev" in route]


def is_wifi(name: str) -> bool:
    return name.startswith("wl") or (Path("/sys/class/net") / name / "wireless").exists()


def is_eth_like(name: str) -> bool:
    lower = name.lower()
    if lower.startswith(EXCLUDED_PREFIXES) or is_wifi(name):
        return False
    return (Path("/sys/class/net") / name / "statistics").exists()


def wifi_ssid(name: str) -> str | None:
    proc = subprocess.run(
        ["iw", "dev", name, "link"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if proc.returncode != 0 or "Not connected" in proc.stdout:
        return None
    match = re.search(r"^\s*SSID:\s+(.+)$", proc.stdout, re.MULTILINE)
    return match.group(1).strip() if match else None


def pick_iface(kind: str) -> str | None:
    names = interfaces()
    defaults = default_route_ifaces()

    if kind == "eth":
        candidates = [name for name in names if is_eth_like(name) and has_ipv4(name)]
        for name in defaults:
            if name in candidates:
                return name
        for name in candidates:
            if operstate(name) in {"up", "unknown"}:
                return name
        return candidates[0] if candidates else None

    candidates = [name for name in names if is_wifi(name) and operstate(name) == "up" and has_ipv4(name)]
    for name in defaults:
        if name in candidates:
            return name
    return candidates[0] if candidates else None


def format_rate(value: float) -> str:
    units = ["B", "K", "M", "G"]
    rate = max(value, 0.0)
    for unit in units:
        if rate < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(rate)}{unit}"
            return f"{rate:.1f}{unit}"
        rate /= 1024
    return "0B"


def load_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="ascii"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(path: Path, state: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state), encoding="ascii")
    os.replace(tmp, path)


def rates(name: str, state_path: Path) -> tuple[str, str]:
    now = time.time()
    rx = read_int(Path("/sys/class/net") / name / "statistics" / "rx_bytes")
    tx = read_int(Path("/sys/class/net") / name / "statistics" / "tx_bytes")
    prev = load_state(state_path)
    save_state(state_path, {"ts": now, "iface": name, "rx": rx, "tx": tx})

    if prev.get("iface") != name:
        return "0B", "0B"

    dt = max(now - float(prev.get("ts", now)), 1e-6)
    return format_rate((rx - int(prev.get("rx", rx))) / dt), format_rate((tx - int(prev.get("tx", tx))) / dt)


def output_hidden(tooltip: str = "") -> None:
    print(json.dumps({"text": "", "tooltip": tooltip, "class": "hidden"}))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=["eth", "wifi"], required=True)
    args = parser.parse_args()

    name = pick_iface(args.kind)
    if name is None:
        output_hidden(f"{args.kind}: no active interface")
        return 0

    rx, tx = rates(name, STATE_ROOT / f"waybar-net-{args.kind}.json")
    addr = ipv4_addr(name) or "no IPv4"

    if args.kind == "wifi":
        ssid = wifi_ssid(name) or name
        text = f"wifi {rx} {tx}"
        tooltip = f"wifi {ssid} ({name})\n{addr}\n↓ {rx}/s\n↑ {tx}/s"
    else:
        text = f"{name} {rx} {tx}"
        tooltip = f"eth-like {name}\n{addr}\n↓ {rx}/s\n↑ {tx}/s"

    print(json.dumps({"text": text, "tooltip": tooltip, "class": args.kind}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"text": "net?", "tooltip": f"net-dev: {exc}", "class": "error"}))
        raise SystemExit(0)
