import io
import queue
import subprocess
from unittest.mock import Mock, patch

from traktor_controller.gui import MidiLinGui
from traktor_controller.gui_support import execute_command, mapping_rows


def test_mapping_search_includes_state_and_both_layer_constraints():
    config = {"mappings": [
        {"device": "f1", "control": "knob_1", "action": "volume", "requires": ["shift"], "unless": ["alt"]},
        {"device": "x1", "control": "play", "action": "script_slot", "slot": "editor", "enabled": False},
    ]}
    assert mapping_rows(config, "F1 VOLUME")[0][0] == "0"
    assert mapping_rows(config, "", "Disabled")[0][1][-1] == "Disabled"
    assert mapping_rows(config, "editor")[0][1][3] == "script_slot:editor"
    assert mapping_rows(config)[0][1][4] == "requires: shift; unless: alt"
    assert mapping_rows(config, "missing") == []


def test_command_timeout_missing_executable_and_nonzero_exit_are_reported():
    with patch("traktor_controller.gui_support.subprocess.run", side_effect=subprocess.TimeoutExpired("detect", 20)) as run:
        code, text = execute_command(["detect"])
        assert code is None and "Timed out" in text
        assert run.call_args.kwargs["timeout"] == 20
    with patch("traktor_controller.gui_support.subprocess.run", side_effect=FileNotFoundError("missing")):
        assert "Could not run" in execute_command(["missing"])[1]
    with patch("traktor_controller.gui_support.subprocess.run", return_value=subprocess.CompletedProcess([], 2, "", "No device")):
        assert execute_command(["detect"]) == (2, "No device")


def test_reader_binds_old_child_and_late_completion_does_not_stop_new_child():
    view = MidiLinGui.__new__(MidiLinGui)
    old = Mock(stdout=io.StringIO("old event\n")); old.wait.return_value = 7
    current = Mock(); view.process = current
    view.output = queue.Queue(); view.status = Mock(); view.append = Mock(); view.canvas = Mock()
    view.reader(old)
    while not view.output.empty(): view.handle_output(view.output.get_nowait())
    assert view.process is current
    view.status.set.assert_not_called(); view.append.assert_not_called()
    view.handle_output(("stopped", current, 0))
    assert view.process is None
    view.status.set.assert_called_with("Monitor stopped (exit 0)")


def test_old_detection_cannot_replace_new_success_and_unrelated_check_keeps_detection():
    view = MidiLinGui.__new__(MidiLinGui)
    view.command_serial = 3; view.detection_serial = 2; view.status = Mock(); view.append = Mock(); view.refresh_readiness = Mock()
    view.handle_output(("command", 2, ["--list-devices"], 0, "F1 controller"))
    view.handle_output(("command", 1, ["--list-devices"], 1, "No device"))
    assert view.detection == "Devices detected"
    view.status.set.assert_not_called()
    view.handle_output(("command", 3, ["--validate-config"], 0, "Valid"))
    assert view.detection == "Devices detected"
    view.status.set.assert_called_with("Check completed")


def test_saved_profile_check_does_not_reload_draft_and_detection_has_its_own_token():
    view = MidiLinGui.__new__(MidiLinGui)
    view.command_serial = view.detection_serial = 0
    view.status = Mock(); view.reload = Mock(); view.command = lambda: ["midiwin"]
    with patch("traktor_controller.gui.threading.Thread"):
        view.run_once(["--list-devices"])
        assert view.detection_serial == 1
        view.run_once(["--validate-config"])
        assert view.detection_serial == 1 and view.command_serial == 2
        view.run_once(["--list-devices"])
        assert view.detection_serial == 3
    view.reload.assert_not_called()
