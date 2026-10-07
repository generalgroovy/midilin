import unittest
from unittest.mock import Mock, patch
from traktor_controller.gui import MidiLinGui


class ClarityTests(unittest.TestCase):
    def view(self):
        view = MidiLinGui.__new__(MidiLinGui)
        view.profile_check = "unchecked"
        view.detection = "Devices not checked"
        view.next_button = Mock()
        view.next_hint = Mock()
        view.run_once = Mock()
        return view

    def test_next_step_tracks_checked_profile_and_detection_without_starting_actions(self):
        view = self.view()
        view.take_next_step()
        view.run_once.assert_called_once_with(["--validate-config"])
        view.profile_check = "valid"
        view.take_next_step()
        view.run_once.assert_called_with(["--list-devices"])
        view.detection = "Device check complete"
        view.start_monitor = Mock()
        view.take_next_step()
        view.start_monitor.assert_called_once_with()

    def test_checking_and_failure_have_recoverable_next_action(self):
        view = self.view()
        view.profile_check = "checking"
        view.refresh_next_action()
        self.assertEqual(view.next_button.configure.call_args.kwargs["state"], "disabled")
        view.profile_check = "failed"
        view.refresh_next_action()
        self.assertEqual(view.next_button.configure.call_args.kwargs["state"], "normal")
        self.assertIn("fix the file", view.next_hint.set.call_args.args[0])

    def test_late_profile_check_cannot_replace_latest_result_or_runtime_status(self):
        view = self.view()
        view.command_serial = view.validation_serial = 3
        view.detection_serial = 0
        view.status = Mock()
        view.append = Mock()
        view.session_status = Mock()
        view.handle_output(("command", 3, ["--validate-config"], 1, "Invalid"))
        view.handle_output(("command", 2, ["--validate-config"], 0, "Valid"))
        self.assertEqual(view.profile_check, "failed")
        view.session_status.set.assert_not_called()

    def test_clear_filters_resets_query_and_state_then_focuses_search(self):
        view = self.view()
        view.mapping_query = Mock()
        view.mapping_state = Mock()
        view.mapping_search = Mock()
        view.clear_mapping_filters()
        view.mapping_query.set.assert_called_once_with("")
        view.mapping_state.set.assert_called_once_with("All")
        view.mapping_search.focus_set.assert_called_once()
