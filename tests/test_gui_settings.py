import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from traktor_controller import gui
from traktor_controller.common import load_config


class Value:
    def __init__(self, value): self.value = value
    def get(self): return self.value
    def set(self, value): self.value = value


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'profile.json'
        self.data = load_config(Path('config.default.json'))
        self.path.write_text(json.dumps(self.data), encoding='utf-8')
        self.view = gui.MidiLinGui.__new__(gui.MidiLinGui)
        self.view.config_path = self.path
        self.view.config = self.data
        for name, value in gui.display_values(self.data).items():
            setattr(self.view, name, Value(value))
        self.view.canvas = Mock()
        self.view.fill_mappings = Mock()
        self.view.status = Value('Ready')

    def test_reload_refreshes_fields_before_next_save(self):
        self.data['display_controls']['brightness']['minimum_percent'] = 8
        self.data['display_controls']['color_temperature']['minimum_kelvin'] = 3100
        self.path.write_text(json.dumps(self.data), encoding='utf-8')
        self.view.reload()
        self.assertEqual(self.view.min_brightness.get(), 8)
        self.assertEqual(self.view.temp_min.get(), 3100)
        self.view.save_settings()
        self.assertEqual(load_config(self.path)['display_controls']['brightness']['minimum_percent'], 8)
        self.assertEqual(self.view.status.get(), 'Display configuration saved')

    def test_invalid_ranges_never_overwrite_profile(self):
        for minimum, temperature in [(101, 2500), (-1, 2500), (1, 6500), (1, 999)]:
            with self.subTest(minimum=minimum, temperature=temperature), patch.object(gui.messagebox, 'showerror') as error:
                before = self.path.read_bytes()
                self.view.min_brightness.set(minimum)
                self.view.temp_min.set(temperature)
                self.view.save_settings()
                self.assertEqual(self.path.read_bytes(), before)
                error.assert_called_once()

    def test_bad_reload_keeps_working_fields_and_config(self):
        for text in ['{bad', '{"mappings":null}']:
            with self.subTest(text=text), patch.object(gui.messagebox, 'showerror') as error:
                before = self.view.config
                self.path.write_text(text, encoding='utf-8')
                self.view.reload()
                self.assertIs(self.view.config, before)
                self.assertEqual(self.view.temp_min.get(), 2500)
                self.view.canvas.redraw.assert_not_called()
                error.assert_called_once()


if __name__ == '__main__': unittest.main()
