# My VibeBar

![Decorated Pakistan bus](assets/pakistan-bus.jpg)

Header image source: [Colorful bus Pakistani](https://commons.wikimedia.org/wiki/File:Colorful_bus_Pakistani.jpg) via Wikimedia Commons.

Bright, bus-art Waybar for `niri` on Wayland.

![Current bar screenshot](assets/waybar.png)

## What Is Here

- Loud per-chip gradients with compact, tooltip-heavy modules.
- A two-strip layout: the main working bar at the bottom and a compact telemetry strip at the top-left.
- Custom helpers for CPU temperature smoothing, disk I/O, clipboard preview, Codex quota display, VPN device display, media metadata, Bluetooth HID battery readings, external IP with click-through IP lookup, system and user `systemd` failure monitoring, Niri keyboard layout state, a hidden-by-default YubiKey touch chip, and a Vocalinux activity chip with separate listening and processing states.
- A `stasis` chip on the top strip shows idle-manager state as words instead of ambiguous icons: `WAIT`, `RUN`, `HOLD`, `DBUS`, `CALL`, `APP`, `PAUSE`, `DOWN`. Left click toggles manual inhibit, middle click reloads config, right click restarts the service. These user-triggered actions show their result through SwayOSD on the focused output.
- A screenshot helper so bar changes can be checked against the live UI instead of config-only guesses.

## Requirements

- `waybar`
- `niri`
- `python3`
- `playerctl` for the media chip
- `curl` for the external IP chip
- `wf-recorder` and `ffmpeg` for `capture-waybar.sh`
- `wl-gammarelay-rs` and optionally `wl-gammarelay-applet`
- `swayosd-client` if you want layout-switch, hardware-backlight, and
  gamma-brightness OSD
- `vocalinux` if you want the dictation activity chip
- `systemctl` for the `systemd` failure chip

## Install

This repo is meant to live at `~/.config/waybar`.

```bash
mkdir -p ~/.config/waybar
cp -r . ~/.config/waybar/
chmod +x ~/.config/waybar/*.py ~/.config/waybar/*.sh
~/.local/bin/restart-waybar
```

Private local values live in ignored `local.env`. Copy
`local.env.example` to `local.env` and fill a work-calendar URL there instead
of committing it to `config.jsonc`.

## Notes

- The config is pinned to `eDP-1` right now.
- Startup logging for login-time failures goes to `~/.local/state/waybar/startup.log`, and each launch also gets a dedicated run directory under `~/.local/state/waybar/runs/` with a small allowlisted environment snapshot, `systemd` status, user-journal snapshots, and the raw `waybar` warning-level log. `~/.local/state/waybar/latest` points at the newest run.
- Run directories older than 2 days are pruned by `start-with-log.sh` on each Waybar startup so diagnostics stay local and bounded.
- Flat helper logs such as `startup.log` and `clipboard-watch.log` are trimmed to the latest 2000 lines once they exceed 1 MiB.
- The default `niri` `spawn-at-startup "waybar"` is intentionally intercepted via `~/.local/bin/waybar`, which forwards into `start-with-log.sh` before starting the real binary so login-time failures survive after the session is gone.
- Waybar uses deterministic visibility signals: `SIGUSR1` shows the bars and
  `SIGUSR2` hides them. Config/style watch reloads must use
  `~/.local/bin/restart-waybar` instead of `SIGUSR2`.
- Right-clicking the bottom bar's power chip hides both bars.
- `Mod+A` toggles sticky Waybar visibility. Bare Mod opens Walker through
  `walker-with-waybar`; on a single active output that wrapper shows Waybar
  temporarily while Walker is open, but it will not hide a bar that was made
  sticky-visible by `Mod+A`.
- `Mod+D` launches `~/.local/bin/walker-with-waybar`; when Niri reports exactly
  one output, the wrapper shows Waybar temporarily before opening Walker and
  hides it again only if the wrapper itself showed it. Multi-output sessions
  leave Waybar visibility alone.
- `clipboard-watch.sh` does not signal Waybar immediately on startup and skips the first `wl-paste --watch` event for each selection. Waybar renders clipboard modules during its own startup, and an immediate `SIGRTMIN+10` can kill a just-spawned Waybar before it installs the custom signal handler. Later clipboard changes still signal Waybar and are logged in `~/.local/state/waybar/clipboard-watch.log`.
- The power chip uses `power-menu-action.sh` instead of raw `systemctl` calls so `challenge` responses from logind are handled cleanly. When Waybar runs outside the real logind session, the helper delegates the action through `power-menu-session-bridge.sh`, which is started by the login fish shell and listens on a private FIFO under `$XDG_RUNTIME_DIR/waybar-power-menu/`.
- The top strip owns the newer status chips first: Codex, `systemd`, Vocalinux, top-processes, clipboard preview, and external IP. The disk I/O chip stays on the bottom bar. When the bottom bar gets crowded, newer chips should move to the top before older baseline controls.
- Expensive polling chips are intentionally not 1 Hz: top-process sampling runs
  every 10 seconds, while disk/network/VPN/loopback and built-in CPU/memory
  refresh every 5 seconds. Keep the bar responsive through signals for eventful
  chips instead of returning to broad 1-second polling.
- Critical chips use static high-contrast colors and glow rather than infinite
  CSS blink animations. GTK keeps repainting animated Waybar CSS even while the
  bars are hidden, so avoid reintroducing always-on animations for status chips.
- The CPU temperature chip reads `coretemp` / `Package id 0` from `hwmon` first so it matches `sensors` package-temperature output; `x86_pkg_temp` thermal-zone data is only a fallback.
- The YubiKey chip is hidden by default. `~/.local/bin/yubikey-touch-osd` writes its state under `$XDG_RUNTIME_DIR/yubikey-touch-osd/waybar.json` and signals Waybar with `SIGRTMIN+11`; `yubikey-touch-status.py` only shows a blinking `YK ...` chip while the detector reports an active `GPG`, `U2F`, or `MAC` touch wait. On the inactive-to-active transition the same watcher plays the cached speech prompt `~/.local/share/yubikey-touch-osd/waiting-for-yubikey-v2.mp3` through `~/.local/bin/play-audio-with-afk-volume`.
- For `stasis`, `RUN` deliberately means "the idle plan is currently advancing" rather than "the monitor is off". It can correspond to a lock countdown or any later action stage, so the exact meaning lives in the tooltip, not in the short chip text. The tooltip also includes a full legend for every short state code.
- The `stasis` chip actions call `~/.local/bin/stasis-action-osd`. The helper
  reports pause/resume, config reload, restart, and failures through SwayOSD on
  the focused Niri output. Automatic idle-state transitions remain quiet.
- The audio chip uses private-use glyphs through Nerd Font. Keep its icons to codepoints present in `Symbols Nerd Font`; older Font Awesome glyphs such as `U+F590` and `U+F6A9` render as missing boxes on this machine.
- When the default sink is muted, the audio chip shows a blinking `MUTED` label instead of relying on a small icon, because mute can otherwise be easy to forget during speech-notification tests.
- The gamma-brightness chip scroll actions call
  `~/.local/bin/gamma-brightness-osd` instead of raw `busctl`, so Waybar scrolls
  use the shared `wl-gammarelay-rs` update and focused-output SwayOSD path.
- The hardware backlight chip scroll actions call
  `~/wb/radar/bin/adaptive-brightness-osd`. With only the built-in Niri output
  active, it controls `intel_backlight` through `hw-backlight-osd`; with any
  external output active, it controls `wl-gammarelay-rs` gamma brightness
  through `gamma-brightness-osd`. Both paths keep SwayOSD pinned to the focused
  Niri output.
- The top-strip Bluetooth HID battery chip reads connected Bluetooth devices
  from `bluetoothctl`, keeps keyboard/mouse-like HID devices with battery data,
  and hides itself when none are connected. It blinks only below 10% so low
  external-device battery is hard to miss without being noisy at normal charge
  levels.
- `capture-waybar.sh` still captures the bottom bar strip intentionally.
- Network chips use `net-dev.py` for the bottom-left Ethernet-like and Wi-Fi
  chips. The Ethernet-like chip prefers the active default-route non-Wi-Fi,
  non-VPN interface, so USB tethering interfaces such as `enp0s20f0u1` win over
  an unplugged onboard Ethernet port. The Wi-Fi chip is hidden when no Wi-Fi
  interface is up with an IPv4 address. Loopback still uses Waybar's built-in
  `network#loopback` module.
- Clipboard preview treats only real plain-text MIME types as text. Browser image copies often expose `text/html` plus `image/*`; in that case the chip should prefer the image path and render `[img]` instead of showing HTML preview markup.

## Screenshot Workflow

```bash
./capture-waybar.sh assets/waybar.png
```

That keeps the README screenshot aligned with the live bottom bar.
