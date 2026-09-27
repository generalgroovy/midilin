from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from traktor_controller.common import ControlEvent, load_config
from traktor_controller.unified_actions import ActionDispatcher


class DisplayGuiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(Path("config.default.json"))

    def test_display_defaults_and_brightness_dry_run(self) -> None:
        settings = self.config["display_controls"]
        self.assertEqual("auto", settings["brightness"]["backend"])
        self.assertEqual(6500, settings["color_temperature"]["maximum_kelvin"])
        dispatcher = ActionDispatcher(self.config, dry_run=True)
        self.assertTrue(dispatcher.set_brightness_percent(50))
        dispatcher.dispatch(
            {"action": "brightness_absolute"},
            ControlEvent("f1", "knob_4", "absolute", 50, 0, 100),
        )

    def test_color_temperature_dry_run_is_non_mutating(self) -> None:
        dispatcher = ActionDispatcher(self.config, dry_run=True)
        with patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-test"}, clear=False), \
             patch("subprocess.Popen") as popen, \
             patch("subprocess.run") as run:
            self.assertTrue(dispatcher.set_color_temperature_kelvin(4500))
            popen.assert_not_called()
            run.assert_not_called()

    def test_color_preview_without_wayland_never_launches_processes(self) -> None:
        dispatcher = ActionDispatcher(self.config, dry_run=True)
        with patch.dict(os.environ, {}, clear=True), \
             patch('subprocess.Popen') as popen, \
             patch('subprocess.run') as run:
            self.assertTrue(dispatcher.set_color_temperature_kelvin(4500))
            self.assertTrue(dispatcher.set_color_temperature_kelvin(6500))
            popen.assert_not_called()
            run.assert_not_called()

    def test_active_color_requires_wayland(self) -> None:
        dispatcher = ActionDispatcher(self.config)
        with patch.dict(os.environ, {}, clear=True), \
             patch('subprocess.Popen') as popen, \
             patch('subprocess.run') as run:
            self.assertFalse(dispatcher.set_color_temperature_kelvin(4500))
            popen.assert_not_called()
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
