from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from typing import Any

from .actions import ActionDispatcher as BaseActionDispatcher
from .common import ControlEvent, log


class ActionDispatcher(BaseActionDispatcher):
    """Desktop, display, model, hardware-light and Sway window actions."""

    def __init__(self, config: dict[str, Any], dry_run: bool = False):
        super().__init__(config, dry_run=dry_run)
        self.color_temperature_timer: threading.Timer | None = None
        self.pointer_accel_timer: threading.Timer | None = None
        self.brightness_timer: threading.Timer | None = None

    def _display_settings(self, section: str) -> dict[str, Any]:
        controls = self.config.get("display_controls", {})
        if not isinstance(controls, dict):
            return {}
        value = controls.get(section, {})
        return value if isinstance(value, dict) else {}

    @classmethod
    def _active_outputs(cls) -> list[dict[str, Any]]:
        outputs = cls._sway_json("get_outputs")
        if not isinstance(outputs, list):
            return []
        return sorted(
            [output for output in outputs
             if isinstance(output, dict) and output.get("active", False)
             and isinstance(output.get("rect"), dict) and output.get("name")],
            key=lambda output: (int(output["rect"].get("x", 0)),
                                int(output["rect"].get("y", 0))),
        )

    def _run_checked(self, command: list[str], action: str,
                     timeout: float = 5.0) -> tuple[bool, str]:
        display = " ".join(command)
        if self.log_actions or self.dry_run:
            log(f"action={action} command={display}")
        if self.dry_run:
            return True, ""
        try:
            result = subprocess.run(
                command, stdin=subprocess.DEVNULL, text=True,
                capture_output=True, timeout=timeout, check=False,
                env=os.environ.copy(),
            )
        except FileNotFoundError:
            message = f"Command not found for action {action}: {command[0]}"
            log(message)
            return False, message
        except subprocess.TimeoutExpired:
            message = f"Command timed out for action {action}: {display}"
            log(message)
            return False, message
        output = (result.stderr or result.stdout or "").strip()
        if result.returncode != 0:
            message = output or f"exit status {result.returncode}"
            log(f"Action failed: {action}: {message}")
            return False, message
        return True, output

    def _run_sway_command(self, command: str, action: str) -> bool:
        ok, output = self._run_checked(["swaymsg", "-r", command], action)
        if not ok or self.dry_run:
            return ok
        try:
            replies = json.loads(output or "[]")
        except json.JSONDecodeError:
            log(f"Sway returned invalid JSON for {action}: {output}")
            return False
        if not isinstance(replies, list) or not replies:
            log(f"Sway returned no result for {action}: {command}")
            return False
        failures = [str(reply.get("error", "unspecified Sway error"))
                    for reply in replies
                    if isinstance(reply, dict) and not reply.get("success", False)]
        if failures:
            log(f"Sway rejected {action}: {'; '.join(failures)}")
            return False
        return True

    @classmethod
    def _pointer_identifiers(cls) -> list[str]:
        inputs = cls._sway_json("get_inputs")
        if not isinstance(inputs, list):
            return []
        result: list[str] = []
        for item in inputs:
            if not isinstance(item, dict):
                continue
            device_type = str(item.get("type", "")).lower()
            identifier = str(item.get("identifier", "")).strip()
            if identifier and device_type in {"pointer", "touchpad"}:
                result.append(identifier)
        return list(dict.fromkeys(result))

    @staticmethod
    def _quote_sway_identifier(identifier: str) -> str:
        return '"' + identifier.replace("\\", "\\\\").replace('"', '\\"') + '"'

    def _set_pointer_accel(self, mapping: dict[str, Any], event: ControlEvent) -> None:
        ratio = self.normalized_value(event, bool(mapping.get("invert", False)))
        value = -1.0 + ratio * 2.0
        delay = max(0.03, float(mapping.get("debounce_ms", 90)) / 1000.0)
        if self.log_actions or self.dry_run:
            log(f"action=pointer_accel_absolute value={value:.2f} debounce_ms={round(delay * 1000)}")
        if self.pointer_accel_timer:
            self.pointer_accel_timer.cancel()

        def apply() -> None:
            identifiers = self._pointer_identifiers()
            success = False
            for identifier in identifiers:
                selector = self._quote_sway_identifier(identifier)
                success = self._run_sway_command(
                    f"input {selector} pointer_accel {value:.2f}",
                    "pointer_accel_absolute",
                ) or success
            if not identifiers:
                for selector in ("type:pointer", "type:touchpad"):
                    success = self._run_sway_command(
                        f"input {selector} pointer_accel {value:.2f}",
                        "pointer_accel_absolute",
                    ) or success
            if not success and not self.dry_run:
                log("Pointer acceleration was not applied. Ensure the service has SWAYSOCK and inspect `swaymsg -t get_inputs -r`.")
            self.pointer_accel_timer = None

        if self.dry_run:
            apply()
        else:
            timer = threading.Timer(delay, apply)
            timer.daemon = True
            self.pointer_accel_timer = timer
            timer.start()

    def set_brightness_percent(self, percent: int,
                               mapping: dict[str, Any] | None = None) -> bool:
        mapping = mapping or {}
        settings = self._display_settings("brightness")
        backend = str(mapping.get("backend", settings.get("backend", "auto"))).lower()
        minimum = int(mapping.get("minimum_percent", settings.get("minimum_percent", 1)))
        percent = min(max(int(percent), minimum), 100)
        device = str(mapping.get("device", settings.get("device", ""))).strip()
        ddc_display = str(mapping.get("ddc_display", settings.get("ddc_display", ""))).strip()
        success = False
        errors: list[str] = []

        if backend in {"auto", "backlight", "brightnessctl"}:
            command = ["brightnessctl", "--class=backlight"]
            if device:
                command.extend(["--device", device])
            command.extend(["set", f"{percent}%"])
            ok, error = self._run_checked(command, "brightness_absolute", timeout=5)
            success = success or ok
            if not ok:
                errors.append(error)

        if backend in {"auto", "ddc", "ddcutil"} and (self.dry_run or shutil.which("ddcutil")):
            command = ["ddcutil"]
            if ddc_display:
                command.extend(["--display", ddc_display])
            command.extend(["setvcp", "10", str(percent)])
            ok, error = self._run_checked(command, "brightness_absolute:ddc", timeout=12)
            success = success or ok
            if not ok:
                errors.append(error)

        if not success and not self.dry_run:
            log("Display brightness was not applied. " + (" | ".join(errors) or
                "Install brightnessctl for laptop panels or ddcutil for DDC/CI monitors."))
        return success

    def _set_display_brightness(self, mapping: dict[str, Any], event: ControlEvent) -> None:
        ratio = self.normalized_value(event, bool(mapping.get("invert", False)))
        settings = self._display_settings("brightness")
        delay = max(0.03, float(mapping.get("debounce_ms", settings.get("debounce_ms", 100))) / 1000.0)
        percent = round(ratio * 100)
        if self.brightness_timer:
            self.brightness_timer.cancel()
        if self.dry_run:
            self.set_brightness_percent(percent, mapping)
            return
        def apply() -> None:
            self.set_brightness_percent(percent, mapping)
            self.brightness_timer = None
        timer = threading.Timer(delay, apply)
        timer.daemon = True
        self.brightness_timer = timer
        timer.start()

    def _stop_color_tools(self) -> None:
        if self.dry_run:
            return
        uid = str(os.getuid())
        for process in ("gammastep", "wlsunset"):
            subprocess.run(["pkill", "-u", uid, "-x", process],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=False)

    def _start_wlsunset(self, kelvin: int) -> bool:
        command = ["wlsunset", "-T", str(kelvin), "-t", str(kelvin),
                   "-S", "00:00", "-s", "23:59", "-d", "0"]
        if self.log_actions or self.dry_run:
            log(f"action=color_temperature_absolute command={' '.join(command)}")
        if self.dry_run:
            return True
        if not shutil.which("wlsunset"):
            return False
        try:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                       start_new_session=True, env=os.environ.copy(), text=True)
        except FileNotFoundError:
            return False
        time.sleep(0.2)
        if process.poll() is not None:
            error = process.stderr.read().strip() if process.stderr else ""
            log("wlsunset exited immediately" + (f": {error}" if error else "."))
            return False
        return True

    def _resolved_color_mapping(self, mapping: dict[str, Any]) -> dict[str, Any]:
        result = dict(self._display_settings("color_temperature"))
        result.update(mapping)
        return result

    def _apply_color_temperature(self, mapping: dict[str, Any], ratio: float,
                                 kelvin: int) -> bool:
        mapping = self._resolved_color_mapping(mapping)
        backend = str(mapping.get("backend", "auto")).lower()
        method = str(mapping.get("adjustment_method", "wayland"))
        takeover = bool(mapping.get("take_ownership", True))
        reset_at_max = bool(mapping.get("reset_at_max", True))
        if not self.dry_run and not os.environ.get("WAYLAND_DISPLAY"):
            log("Color temperature requires WAYLAND_DISPLAY in the user service. Run `systemctl --user import-environment WAYLAND_DISPLAY SWAYSOCK XDG_RUNTIME_DIR`.")
            return False
        if takeover:
            self._stop_color_tools()
        if reset_at_max and ratio >= 0.995:
            if self.dry_run or shutil.which("gammastep"):
                self._run_checked(["gammastep", "-m", method, "-x"],
                                  "color_temperature_reset")
            return True
        if backend in {"auto", "wlsunset"} and self._start_wlsunset(kelvin):
            return True
        if backend not in {"auto", "gammastep", "wlsunset"}:
            log(f"Unknown color-temperature backend {backend!r}; using Gammastep.")
        ok, error = self._run_checked(
            ["gammastep", "-P", "-m", method, "-O", str(kelvin)],
            "color_temperature_absolute",
        )
        if not ok:
            log(f"Color temperature could not be applied. Gammastep reported: {error or 'unknown error'}. Check compositor gamma-control support and WAYLAND_DISPLAY.")
        return ok

    def set_color_temperature_kelvin(self, kelvin: int) -> bool:
        settings = self._display_settings("color_temperature")
        minimum = max(1000, int(settings.get("minimum_kelvin", 2500)))
        maximum = min(25000, int(settings.get("maximum_kelvin", 6500)))
        kelvin = min(max(int(kelvin), minimum), maximum)
        ratio = (kelvin - minimum) / max(maximum - minimum, 1)
        return self._apply_color_temperature(settings, ratio, kelvin)

    def _set_color_temperature(self, mapping: dict[str, Any], event: ControlEvent) -> None:
        mapping = self._resolved_color_mapping(mapping)
        ratio = self.normalized_value(event, bool(mapping.get("invert", False)))
        minimum = max(1000, int(mapping.get("minimum_kelvin", 2500)))
        maximum = min(25000, int(mapping.get("maximum_kelvin", 6500)))
        if maximum <= minimum:
            maximum = minimum + 100
        kelvin = round(minimum + ratio * (maximum - minimum))
        delay = max(0.05, float(mapping.get("debounce_ms", 180)) / 1000.0)
        if self.log_actions or self.dry_run:
            log(f"action=color_temperature_absolute kelvin={kelvin} backend={mapping.get('backend', 'auto')} debounce_ms={round(delay * 1000)}")
        if self.color_temperature_timer:
            self.color_temperature_timer.cancel()
        if self.dry_run:
            self._apply_color_temperature(mapping, ratio, kelvin)
            return
        def apply() -> None:
            self._apply_color_temperature(mapping, ratio, kelvin)
            self.color_temperature_timer = None
        timer = threading.Timer(delay, apply)
        timer.daemon = True
        self.color_temperature_timer = timer
        timer.start()

    def diagnose_displays(self) -> list[str]:
        lines = [
            f"WAYLAND_DISPLAY={os.environ.get('WAYLAND_DISPLAY', '')}",
            f"SWAYSOCK={os.environ.get('SWAYSOCK', '')}",
            "tools=" + ", ".join(
                f"{name}:{shutil.which(name) or 'missing'}"
                for name in ("brightnessctl", "ddcutil", "wlsunset", "gammastep")
            ),
        ]
        for command, name, timeout in (
            (["brightnessctl", "--list", "--machine-readable"], "brightnessctl", 4),
            (["ddcutil", "detect", "--brief"], "ddcutil", 12),
        ):
            if not shutil.which(command[0]):
                continue
            ok, output = self._run_checked(command, f"diagnose:{name}", timeout=timeout)
            lines.append(f"{name}:\n{output if ok else 'ERROR: ' + output}")
        return lines

    def _window_output_absolute(self, mapping: dict[str, Any], event: ControlEvent) -> None:
        ratio = self.normalized_value(event, bool(mapping.get("invert", False)))
        if self.dry_run:
            log(f"action=window_output_absolute ratio={ratio:.3f}")
            return
        outputs = self._active_outputs()
        if not outputs:
            log("No active Sway outputs found.")
            return
        index = min(len(outputs) - 1, round(ratio * (len(outputs) - 1)))
        name = str(outputs[index]["name"])
        self._run(["swaymsg", f'move container to output "{name}", focus'],
                  "window_output_absolute")

    def dispatch(self, mapping: dict[str, Any], event: ControlEvent) -> None:
        action = str(mapping["action"])
        ratio = self.normalized_value(event, bool(mapping.get("invert", False)))
        if action == "brightness_absolute":
            self._set_display_brightness(mapping, event)
        elif action == "pointer_accel_absolute":
            self._set_pointer_accel(mapping, event)
        elif action == "color_temperature_absolute":
            self._set_color_temperature(mapping, event)
        elif action == "window_opacity_absolute":
            minimum = min(max(float(mapping.get("minimum", 0.2)), 0.0), 1.0)
            value = minimum + ratio * (1.0 - minimum)
            self._run(["swaymsg", "opacity", "set", f"{value:.2f}"], action)
        elif action == "window_border_absolute":
            maximum = max(0, int(mapping.get("maximum", 12)))
            pixels = round(ratio * maximum)
            command = ["swaymsg", "border", "none"] if pixels == 0 else ["swaymsg", "border", "pixel", str(pixels)]
            self._run(command, action)
        elif action == "window_output_absolute":
            self._window_output_absolute(mapping, event)
        else:
            super().dispatch(mapping, event)
