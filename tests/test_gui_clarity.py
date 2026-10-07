import unittest
from unittest.mock import Mock, patch
from traktor_controller.gui import MidiLinGui, SERVICE


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

    def test_pending_service_result_does_not_replace_new_monitor_state(self):
        view = self.view()
        view.command_serial = 0
        view.status = Mock()
        view.session_status = Mock()
        view.refresh_readiness = Mock()
        view.append = Mock()
        with patch("traktor_controller.gui.threading.Thread"):
            view.run_external(["systemctl", "--user", "start", SERVICE])
        token = view.command_serial
        view.set_session_status("Read-only input running · mapped actions off")
        view.session_status.set.reset_mock()
        view.handle_output(("command", token, ["systemctl", "--user", "start", SERVICE], 0, "Started"))
        view.session_status.set.assert_not_called()
        view.append.assert_called()  # Outcome is still available in the diagnostic log.

    def test_current_service_result_can_update_its_own_session_state(self):
        view = self.view()
        view.command_serial = 0
        view.status = Mock()
        view.session_status = Mock()
        view.refresh_readiness = Mock()
        view.append = Mock()
        with patch("traktor_controller.gui.threading.Thread"):
            view.run_external(["systemctl", "--user", "stop", SERVICE])
        view.handle_output(("command", view.command_serial, ["systemctl", "--user", "stop", SERVICE], 0, "Stopped"))
        view.session_status.set.assert_called_once_with("Service request completed · see log")
