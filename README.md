# MIDILIN

Use Traktor Kontrol F1 and X1 MK1 controls for Linux/Sway media, audio, display and window actions. A Tk console shows mappings, input activity and diagnostics. [MIDIWIN](https://github.com/generalgroovy/midiwin) is the Windows companion.

![Controller layout](assets/layout-overview.svg)

## Install on Garuda/Arch with Sway

The installer uses `pacman`, installs desktop/hardware tools and udev rules, and enables a systemd user service. It is not a distribution-independent installer.

```sh
git clone https://github.com/generalgroovy/midilin.git
cd midilin
bash ./install.sh
systemctl --user import-environment WAYLAND_DISPLAY SWAYSOCK XDG_CURRENT_DESKTOP XDG_RUNTIME_DIR
midilin-gui
```

Existing `config.json` is kept. For an update, use `git pull --ff-only`, then run the installer again. `bash ./install.sh --reset-config` deliberately replaces the profile with defaults after making a timestamped backup; it is not needed for an ordinary update.

Installation refreshes the shipped `defaults/` files even when `config.json` is kept. Before updating, back up the whole configuration directory if you edited those included mappings. Keep custom includes outside `defaults/` to avoid overwriting them on future installs.

After reviewing mappings, reconnect the controllers if newly installed rules require it, then start active control with:

```sh
systemctl --user restart traktor-system-controller.service
```

## Use the console

1. **Mappings** shows actions and modifier layers. **Validate** checks the selected configuration.
2. **Monitoring → Detect devices** shows available controllers. **Read-only monitor** temporarily stops an active service and displays input without applying mapped actions.
3. **Stop monitor**, or closing the console, resumes the service only if it was active when monitoring began. **Stop service** is the explicit control for leaving the background service stopped.
4. **Display controls** configures brightness and color-temperature backends. The test sliders apply live changes. Save changes to the profile, then restart the service to reload them.

Use a custom profile with `midilin-gui --config /path/to/config.json`. GUI diagnostics, monitoring and display commands use that resolved path. The **service controls still manage the installed default service**, whose profile is configured by its unit file; opening a custom GUI profile does not change the service definition.

## Inspect and preview

```sh
traktor-system-controller --validate-config
traktor-system-controller --show-layout
traktor-system-controller --list-devices
traktor-system-controller --diagnose-display
traktor-system-controller --dry-run --set-brightness 50
traktor-system-controller --dry-run --set-temperature 4500
```

Display dry runs print planned commands without launching display tools and do not need a Wayland session. Remove `--dry-run` to apply a value. Active color-temperature changes require `WAYLAND_DISPLAY` and compositor gamma-control support.

For terminal input monitoring:

```sh
systemctl --user stop traktor-system-controller.service
traktor-system-controller --monitor --dry-run
```

Stop with Ctrl+C; restart the service explicitly when finished. Unlike the GUI workflow, this terminal sequence does not automatically restore it.

## Configuration and recovery

The installed profile is `~/.config/traktor-system-controller/config.json`. Included mappings and other files live alongside it under `defaults/`, `hooks/` and `scripts/`. Back up the whole configuration directory if you customize included files. Model-control state may also be written to the configured state-file path.

Restore a selected backup while the service is stopped, validate it, then restart. Invalid/missing configuration and recursive includes are rejected. The console's **Reload** also refreshes editable display fields. A failed reload keeps the current view. **Save configuration** rejects brightness minimums outside 0–100% and temperature ranges that do not increase within 1000–25000 K, leaving the saved profile unchanged. Defaults for a checkout are in `config.default.json`; a hardware-free config check is:

```sh
python traktor-controller.py --config config.default.json --validate-config
```

## Display backends and controls

| Control/backend | Behavior |
| --- | --- |
| F1 Knob 4 | Absolute screen brightness |
| `backlight` | Uses `brightnessctl --class=backlight` |
| `ddc` | Uses `ddcutil setvcp 10` for DDC/CI displays |
| Brightness `auto` | Attempts available backends and reports failures |
| F1 Fader 3 | Color temperature; default maximum resets to neutral |
| Color `auto` | Tries Wlsunset, then Gammastep |
| F1 Reverse | Closes the focused Sway window |
| X1 Browse / Loop encoders | Move / resize the focused window |

Color-temperature ownership can stop the user's existing Wlsunset/Gammastep processes before applying a new value. Inspect `display_controls` if another application already manages display color. Read the journal for backend errors:

```sh
journalctl --user -u traktor-system-controller.service -n 150 --no-pager
```

## Development and limits

Python and Tk are supplied by the target distribution. Hardware access and desktop actions additionally require the packages installed by `install.sh`.

```sh
python -m unittest discover -s tests -v
python -m py_compile traktor-controller.py traktor-system-controller.py traktor_controller/*.py
bash -n install.sh helpers/system-actions examples/model-controls-updated
```

CI checks configuration, Python, tests, shell and SVG assets. Mocked tests establish routing and preview behavior; they do not establish Linux/Sway integration, physical controller input or display response on this Windows development host. [Source](traktor_controller/) · [Tests](tests/)

MIT license.
