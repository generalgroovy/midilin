import unittest
from unittest.mock import Mock, patch
from traktor_controller import gui


class InputInspectorTests(unittest.TestCase):
    def view(self):
        view = gui.MidiLinGui.__new__(gui.MidiLinGui)
        view.process = object()
        view.last_input = None
        view.last_input_text = Mock()
        view.input_inspect_button = Mock()
        view.append = Mock()
        view.status = Mock()
        view.canvas = Mock()
        return view

    def test_current_process_input_is_readable_and_stale_or_unrecognized_lines_are_ignored(self):
        view = self.view()
        view.handle_output(("line", view.process, "device=f1 control=grid_1 kind=press value=127\n"))
        self.assertEqual(view.last_input, ("f1", "grid_1", "press"))
        view.last_input_text.set.assert_called_with("Last received: f1.grid_1 · press · value 127")
        view.input_inspect_button.configure.assert_called_with(state="normal")
        for process, line in ((object(), "device=x1 control=play kind=press value=1"),
                              (view.process, "waiting for input"),
                              (view.process, "device=x1 control=play kind=unknown value=1")):
            view.handle_output(("line", process, line))
        self.assertEqual(view.last_input, ("f1", "grid_1", "press"))
        view.handle_output(("stopped", view.process, 0))
        self.assertEqual(view.last_input, ("f1", "grid_1", "press"))  # honestly labeled last received

    def test_inspect_input_opens_existing_offline_inspector_without_commands_or_profile_edits(self):
        view = self.view()
        view.root = Mock()
        view.config = {"mappings": [{"device": "f1", "control": "grid_1", "kind": "press", "action": "volume", "enabled": False}]}
        view.last_input = ("f1", "grid_1", "release")
        with patch.object(gui, "MappingInspector") as inspector, patch.object(gui.subprocess, "Popen") as start, patch.object(gui.subprocess, "run") as run:
            view.inspect_last_input()
            inspector.assert_called_once_with(view.root, view.config, event=("f1", "grid_1", "release"))
            start.assert_not_called()
            run.assert_not_called()
            self.assertFalse(view.config["mappings"][0]["enabled"])

    def test_restart_clears_last_input_and_disabled_action_is_a_noop(self):
        view = self.view()
        view.last_input = ("f1", "grid_1", "press")
        view.clear_last_input()
        self.assertIsNone(view.last_input)
        view.input_inspect_button.configure.assert_called_with(state="disabled")
        self.assertIn("Waiting", view.last_input_text.set.call_args.args[0])
        with patch.object(gui, "MappingInspector") as inspector:
            view.inspect_last_input()
            inspector.assert_not_called()
