import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from traktor_controller import cli, gui


class CliWorkflowTests(unittest.TestCase):
    def test_display_dry_runs_do_not_start_any_process(self):
        for option, value in [('--set-temperature', '4500'), ('--set-temperature', '6500'), ('--set-brightness', '50')]:
            with self.subTest(option=option, value=value), \
                 patch.dict(os.environ, {}, clear=True), \
                 patch('sys.argv', ['traktor-system-controller', '--config', 'config.default.json', '--dry-run', option, value]), \
                 patch('subprocess.run') as run, patch('subprocess.Popen') as popen:
                self.assertEqual(cli.main(), 0)
                run.assert_not_called()
                popen.assert_not_called()

    def test_cli_passes_selected_configuration_to_gui(self):
        with patch('sys.argv', ['traktor-system-controller', '--gui', '--config', 'custom.json']), \
             patch.object(gui, 'main', return_value=0) as launch:
            self.assertEqual(cli.main(), 0)
            launch.assert_called_once_with(config_path=Path('custom.json'))

    def test_gui_forwards_resolved_config_to_every_controller_command(self):
        with patch.object(gui.MidiLinGui, 'build'), patch('shutil.which', return_value='/usr/bin/traktor-system-controller'):
            instance = gui.MidiLinGui(Mock(), Path('config.default.json'))
            self.assertEqual(instance.command(), ['/usr/bin/traktor-system-controller', '--config', str(Path('config.default.json').resolve())])


if __name__ == '__main__':
    unittest.main()
