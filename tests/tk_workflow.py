"""Target-platform Tk acceptance in CI only; no hardware or process operations."""
import json
import os
import sys
import tempfile
import tkinter as tk
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from traktor_controller import gui
from traktor_controller.common import load_config


def run():
    if os.environ.get("CI") != "true":
        raise SystemExit("Run this target-platform UI workflow in CI; no local desktop interaction.")
    evidence = Path("artifacts/tk-quality")
    evidence.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        profile = Path(folder) / "profile.json"
        data = load_config(Path("config.default.json"))
        data.setdefault("custom_preserved", {"label": "音", "value": 17})
        profile.write_text(json.dumps(data), encoding="utf-8")
        root = tk.Tk()
        root.withdraw()
        try:
            with patch("subprocess.Popen", side_effect=AssertionError("UI launched a process")), patch("subprocess.run", side_effect=AssertionError("UI ran a command")):
                view = gui.MidiLinGui(root, profile)
                # Real widgets, synthetic completion messages: no controller/process activity.
                from PIL import ImageGrab
                root.geometry("1180x760+10+10")
                root.deiconify()
                root.update()
                assert view.book.select() == str(view.tabs["mappings"])
                assert view.next_button.cget("text") == "Check saved profile"
                assert str(view.inspect_button.cget("state")) == "disabled"
                def capture(name):
                    root.update()
                    x, y = root.winfo_rootx(), root.winfo_rooty()
                    ImageGrab.grab(bbox=(x, y, x + root.winfo_width(), y + root.winfo_height())).save(evidence / name)
                capture("mappings-full.png")
                handle = view.handle_output
                with patch.object(gui.threading, "Thread"):
                    view.next_button.invoke()
                    assert view.book.select() == str(view.tabs["monitor"])
                    assert str(view.next_button.cget("state")) == "disabled"
                    handle(("command", view.validation_serial, ["--validate-config"], 0, "Valid synthetic profile\n"))
                    assert view.next_button.cget("text") == "Detect devices"
                    view.next_button.invoke()
                    token = view.detection_serial
                    handle(("command", token, ["--list-devices"], 0, "No devices found (synthetic)\n"))
                    assert view.detection == "Device check complete"  # exit zero is not a hardware claim
                    assert view.next_button.cget("text") == "Monitor input"
                    assert view.session_status.get().startswith("Console idle")
                root.geometry("860x620+10+10")
                root.update()
                for widget in (view.next_button, view.detect_button, view.monitor_button, view.stop_button, view.log):
                    assert widget.winfo_ismapped()
                    assert widget.winfo_rootx() >= root.winfo_rootx()
                    assert widget.winfo_rootx() + widget.winfo_width() <= root.winfo_rootx() + root.winfo_width()
                    assert widget.winfo_rooty() + widget.winfo_height() <= root.winfo_rooty() + root.winfo_height()
                assert view.log.winfo_height() >= 150
                capture("monitor-narrow.png")
                view.show_tab("mappings")
                view.mapping_query.set("does-not-exist")
                view.mapping_state.set("Disabled")
                root.update()
                assert "No matches" in view.mapping_hint.get()
                capture("empty-search-narrow.png")
                view.clear_search_button.invoke()
                root.update()
                assert view.mapping_query.get() == "" and view.mapping_state.get() == "All"
                assert len(view.tree.get_children()) == len(data["mappings"])
                # Explicit tab navigation restores a useful focus target.
                root.focus_force()
                view.show_tab("mappings")
                root.update()
                assert root.focus_get() == view.mapping_search
                capture("mappings-narrow.png")
                view.book.select(view.tabs["layout"])
                root.update()
                assert view.canvas.xview()[1] < 1 and view.canvas.yview()[1] < 1
                view.canvas.xview_moveto(1)
                view.canvas.yview_moveto(1)
                assert view.canvas.xview()[1] == 1 and view.canvas.yview()[1] == 1
                view.show_tab("mappings")
                # Exercise live widget callbacks and the snapshot inspector.
                view.mapping_query.set("grid_1")
                root.update()
                keys = view.tree.get_children()
                assert keys
                layered = next(key for key in keys if view.config["mappings"][int(key)].get("requires"))
                view.tree.selection_set(layered)
                view.inspect_mapping()
                inspector = view.inspector
                root.update()
                assert "Hold f1.shift" in inspector.result.get("1.0", "end")
                inspector.held.set("f1.shift")
                inspector.try_button.invoke()
                assert "Eligible" in inspector.result.get("1.0", "end")
                selected = view.config["mappings"][int(layered)]
                assert str(selected["slot"]) in inspector.details.get("1.0", "end")
                assert "Control: grid_1" in inspector.details.get("1.0", "end")
                inspector.raw.set(True)
                inspector.show_details()
                assert '"control": "grid_1"' in inspector.details.get("1.0", "end")
                inspector.raw.set(False)
                inspector.show_details()
                inspector.kind.set("not-an-event")
                inspector.try_button.invoke()
                assert "Could not preview" in inspector.result.get("1.0", "end")
                inspector.kind.set("press")
                inspector.try_button.invoke()
                inspector.geometry("790x640+10+10")
                inspector.deiconify()
                root.update()
                assert inspector.try_button.winfo_ismapped()
                assert inspector.result.winfo_height() > 60
                for widget in (inspector.details, inspector.try_button, inspector.result):
                    assert widget.winfo_y() + widget.winfo_height() <= inspector.winfo_height()
                from PIL import ImageGrab
                x, y = inspector.winfo_rootx(), inspector.winfo_rooty()
                ImageGrab.grab(bbox=(x, y, x + inspector.winfo_width(), y + inspector.winfo_height())).save(evidence / "mapping-inspector.png")
                inspector.destroy()
                view.mapping_query.set("does-not-exist")
                assert view.mapping_count.get() == "0 shown"
                view.mapping_query.set("")
                assert len(view.tree.get_children()) == len(data["mappings"])
                # Cancelling reload and close retains the draft and monitor ownership.
                before = profile.read_bytes()
                view.min_brightness.set(13)
                assert view.draft_status.get() == "Unsaved display changes"
                with patch.object(gui.messagebox, "askyesnocancel", return_value=None):
                    assert not view.reload()
                    view.close()
                assert root.winfo_exists() and view.min_brightness.get() == 13
                assert profile.read_bytes() == before
                with patch.object(gui.messagebox, "askyesnocancel", return_value=True):
                    assert view.reload()
                assert load_config(profile)["display_controls"]["brightness"]["minimum_percent"] == 13
                assert load_config(profile)["custom_preserved"] == data["custom_preserved"]
                assert view.draft_status.get() == "No unsaved display changes"
                view.min_brightness.set(19)
                with patch.object(gui.messagebox, "askyesnocancel", return_value=False):
                    assert view.reload()
                assert view.min_brightness.get() == 13
                # Invalid draft Save must not overwrite or close; real Tcl variable validation.
                view.min_brightness.set("invalid")
                with patch.object(gui.messagebox, "showerror") as error, patch.object(gui.messagebox, "askyesnocancel", return_value=True):
                    view.close()
                    error.assert_called_once()
                assert root.winfo_exists()
                assert load_config(profile)["display_controls"]["brightness"]["minimum_percent"] == 13
                report = {"platform": sys.platform, "tk": str(root.tk.call("info", "patchlevel")), "checks": ["clear next readiness action", "diagnostic exit zero does not claim hardware", "inspection and active control separated", "narrow full window visibility", "recover both search filters", "mapping link focus", "scrollable controller diagram", "mapping search and stable indices", "layered preview", "full script details", "invalid event recovery", "visible inspector layout", "empty search recovery", "cancel reload and close", "save and discard reload", "invalid draft preserves profile", "no subprocess operations"]}
                (evidence / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
                print(json.dumps(report))
        finally:
            root.destroy()


if __name__ == "__main__":
    run()
