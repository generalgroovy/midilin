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
                report = {"platform": sys.platform, "tk": str(root.tk.call("info", "patchlevel")), "checks": ["mapping search and stable indices", "layered preview", "full script details", "invalid event recovery", "visible inspector layout", "empty search recovery", "cancel reload and close", "save and discard reload", "invalid draft preserves profile", "no subprocess operations"]}
                (evidence / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
                print(json.dumps(report))
        finally:
            root.destroy()


if __name__ == "__main__":
    run()
