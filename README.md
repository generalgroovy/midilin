# MIDILIN — Traktor X1/F1 Linux System Controller

Linux/Sway sibling of [MIDIWIN](https://github.com/generalgroovy/midiwin).

Use Native Instruments Traktor Kontrol F1 and X1 MK1 as complementary Garuda
Sway control surfaces for desktop, media, audio, display controls, scripts,
model parameters and focused-window management.

## Project at a glance

**Author: Michail Sendetskiy · Python · Linux/Sway · hardware integration**

MIDILIN repurposes Traktor controllers as tactile desktop controls: physical
knobs, faders, buttons, and encoders operate media, display settings, and
windows. A graphical console makes mappings, device status, and diagnostics
visible alongside the hardware.

| Component | Purpose |
| --- | --- |
| Controller runtime | Maps F1/X1 inputs to configured actions and modifier layers |
| Graphical console | Displays mappings, monitors input, and exposes backend diagnostics |
| Platform integration | Connects controller actions to Sway, display tools, and user services |
| Configuration and tests | Keeps mappings in JSON and checks controller/display behavior |

**Platform:** this repository targets Linux with Sway. The Windows companion is
[MIDIWIN](https://github.com/generalgroovy/midiwin).

Start with the controller diagram below, inspect the
[implementation](traktor_controller/) and [tests](tests/), or follow the
[installation instructions](#install-or-update). Configuration checks and
read-only monitoring are documented under [Verify](#verify).

For a first checkout, before the installation steps:

```bash
git clone https://github.com/generalgroovy/midilin.git
cd midilin
```

Run the later installation commands from this checkout; replace their example
directory with the location you chose.

![Unified physical controller overview](assets/layout-overview.svg)

## Controller console

The GUI provides:

- a representative front-panel layout for the F1 and X1;
- live control highlighting during read-only monitoring;
- brightness and blue-light backend configuration;
- live brightness and color-temperature testing;
- mapping and modifier-layer overview;
- device detection, configuration validation and backend diagnostics;
- safe service stop/start/restart and journal inspection.

After installation, open **MIDILIN Controller Console** from the application
launcher or run:

```fish
midilin-gui
```

## Install or update

```fish
cd ~/Projects/midilin
git pull --ff-only
sudo -v
bash ./install.sh --reset-config
```

The reset preserves the existing configuration with a timestamped backup and
installs schema 5 display settings. Then import the Sway environment and restart:

```fish
systemctl --user import-environment \
    WAYLAND_DISPLAY \
    SWAYSOCK \
    XDG_CURRENT_DESKTOP \
    XDG_RUNTIME_DIR

systemctl --user restart traktor-system-controller.service
```

## Repaired brightness behavior

F1 Knob 4 maps to `brightness_absolute`.

- `backend=backlight` uses `brightnessctl --class=backlight` for laptop panels.
- `backend=ddc` uses `ddcutil setvcp 10` for DDC/CI monitors.
- `backend=auto` attempts both and reports exact failures rather than suppressing
  stderr.
- A specific brightnessctl device or ddcutil display number can be selected in
  the GUI.

```fish
traktor-system-controller --diagnose-display
traktor-system-controller --set-brightness 50
```

## Repaired blue-light behavior

F1 Fader 3 maps to `color_temperature_absolute`.

- `backend=auto` tries Wlsunset first and Gammastep second.
- Wlsunset is started as a persistent wlroots gamma-control process.
- Gammastep uses the explicit Wayland adjustment method and clears stale gamma
  ramps before applying a temperature.
- Existing user-owned Wlsunset/Gammastep processes are stopped before a new value
  is applied.
- The maximum endpoint resets to neutral 6500 K.
- Missing `WAYLAND_DISPLAY`, compositor gamma support and command failures are
  shown in the service journal and GUI diagnostics.

```fish
traktor-system-controller --set-temperature 4500
journalctl --user -u traktor-system-controller.service -n 150 --no-pager
```

## Default highlights

- F1 Knob 3: controller-light brightness
- F1 Knob 4: screen brightness
- F1 Fader 3: blue-light/color temperature
- F1 Reverse: close focused Sway window
- F1 Shift knobs/faders: model parameters
- X1 FX knobs: position, size, opacity, borders, gaps and output
- X1 Browse/Loop encoders: move and resize focused windows
- X1 HOTCUE layer: monitoring and maintenance

## Verify

```fish
traktor-system-controller --validate-config
traktor-system-controller --show-layout
traktor-system-controller --list-devices
traktor-system-controller --diagnose-display
```

Read-only controller monitoring is available directly in the GUI. From the
terminal:

```fish
systemctl --user stop traktor-system-controller.service
traktor-system-controller --monitor --dry-run
```

Stop with `Ctrl+C`, then restart the service.

## Configuration

```text
~/.config/traktor-system-controller/config.json
```

The `display_controls` section selects brightness and color-temperature
backends. Mapping definitions remain in `defaults/f1.json` and
`defaults/x1.json`.

## Related project

- Linux/Sway: **MIDILIN** — this repository
- Windows: **[MIDIWIN](https://github.com/generalgroovy/midiwin)**

## License

MIT
