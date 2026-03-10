#!/usr/bin/env python3
import json
import os
import time

STATE_PATH = "/tmp/waybar-vpn-dev.json"

EXCLUDE_PREFIXES = (
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
)

VPN_PREFIXES = (
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
    "utun",
)


def is_vpn_iface(name):
    lower = name.lower()
    if lower.startswith(EXCLUDE_PREFIXES):
        return False
    if lower.startswith(VPN_PREFIXES):
        return True
    device_path = f"/sys/class/net/{name}/device"
    return not os.path.exists(device_path)


def read_counter(path):
    try:
        with open(path, "r", encoding="ascii") as handle:
            return int(handle.read().strip())
    except (OSError, ValueError):
        return 0


def format_rate(value):
    units = ["B", "K", "M", "G", "T"]
    rate = float(value)
    for unit in units:
        if rate < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(rate)}{unit}".rjust(6)
            return f"{rate:.1f}{unit}".rjust(6)
        rate /= 1024


def load_state():
    try:
        with open(STATE_PATH, "r", encoding="ascii") as handle:
            return json.load(handle)
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def save_state(state):
    tmp_path = f"{STATE_PATH}.tmp"
    with open(tmp_path, "w", encoding="ascii") as handle:
        json.dump(state, handle)
    os.replace(tmp_path, STATE_PATH)


def main():
    now = time.time()
    state = load_state()
    last_ts = state.get("ts", now)
    last_ifaces = state.get("ifaces", {})
    dt = max(now - last_ts, 1e-6)

    ifaces = []
    for name in os.listdir("/sys/class/net"):
        if is_vpn_iface(name):
            ifaces.append(name)

    current = {}
    rates = {}
    for name in ifaces:
        rx = read_counter(f"/sys/class/net/{name}/statistics/rx_bytes")
        tx = read_counter(f"/sys/class/net/{name}/statistics/tx_bytes")
        current[name] = {"rx": rx, "tx": tx}

        last = last_ifaces.get(name, {})
        last_rx = last.get("rx", rx)
        last_tx = last.get("tx", tx)
        rx_rate = max((rx - last_rx) / dt, 0.0)
        tx_rate = max((tx - last_tx) / dt, 0.0)
        rates[name] = {"rx": rx_rate, "tx": tx_rate, "total": rx_rate + tx_rate}

    save_state({"ts": now, "ifaces": current})

    if not rates:
        print(json.dumps({"text": "none", "tooltip": "No VPN interfaces detected"}))
        return

    parts = []
    tooltip_lines = []
    for name, rate in sorted(rates.items(), key=lambda item: item[1]["total"], reverse=True):
        label = f"{name} {format_rate(rate['rx'])}↓ {format_rate(rate['tx'])}↑"
        parts.append(label)
        tooltip_lines.append(label)

    text = " | ".join(parts)
    print(json.dumps({"text": text, "tooltip": "\n".join(tooltip_lines)}))


if __name__ == "__main__":
    main()
