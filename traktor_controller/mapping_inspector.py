"""Read-only Tk mapping inspection; never imports or creates an action runner."""
from __future__ import annotations

import copy
import json
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any

from .mapping_rules import SUPPORTS_PROFILES, preview_event


def mapping_details(config: dict[str, Any], mapping: dict[str, Any]) -> str:
    sections = ["Selected mapping\n" + json.dumps(mapping, ensure_ascii=False, indent=2)]
    model = config.get("model_controls", {})
    parameters = model.get("parameters", {}) if isinstance(model, dict) else {}
    references = [("Action definition", config.get("actions", {}), mapping.get("action")),
                  ("Script slot", config.get("script_slots", {}), mapping.get("slot")),
                  ("Model parameter", parameters, mapping.get("parameter"))]
    for label, container, key in references:
        if isinstance(container, dict) and isinstance(key, str) and key in container:
            sections.append(label + "\n" + json.dumps(container[key], ensure_ascii=False, indent=2))
    return "\n\n".join(sections)


def preview_text(report: dict[str, Any]) -> str:
    decisions = report["decisions"]
    eligible = sum(not reasons for _, _, reasons in decisions)
    heading = f"{eligible} eligible mapping(s) for {report['control']}"
    if report["profile"]:
        heading += f" · profile {report['profile']}"
    lines = [heading, "Routing only: no actions run. Values, timing and device response are not simulated.", ""]
    if not decisions:
        lines.append("No mappings for this device/control. Check its spelling or select a mapping from the list.")
    for index, mapping, reasons in decisions:
        action = str(mapping.get("action", ""))
        detail = mapping.get("slot") or mapping.get("parameter")
        if detail:
            action += ":" + str(detail)
        lines.append(f"#{index + 1} {action} — " + ("; ".join(reasons) if reasons else "Eligible"))
    if eligible > 1:
        lines.append("\nEvery eligible mapping is routed, in profile order.")
    return "\n".join(lines)


class MappingInspector(tk.Toplevel):
    def __init__(self, parent: tk.Misc, config: dict[str, Any], index: int):
        super().__init__(parent)
        self.title("Inspect mapping · offline")
        self.geometry("790x640")
        self.minsize(580, 480)
        self.config_snapshot = copy.deepcopy(config)
        mapping = self.config_snapshot["mappings"][index]
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(4, weight=1)
        ttk.Label(self, text="Review a mapping, then try its routing without a controller.", padding=10).grid(sticky="w")
        self.details = ScrolledText(self, height=9, wrap="word", font="TkFixedFont")
        self.details.grid(row=1, column=0, sticky="nsew", padx=10)
        self._write(self.details, mapping_details(self.config_snapshot, mapping))
        form = ttk.LabelFrame(self, text="Try an event · loaded profile snapshot", padding=8)
        form.grid(row=2, column=0, sticky="ew", padx=10, pady=8)
        form.columnconfigure(1, weight=1)
        self.device = tk.StringVar(value=str(mapping.get("device", "f1")))
        self.control = tk.StringVar(value=str(mapping.get("control", "")))
        self.kind = tk.StringVar(value=str(mapping.get("kind", "press")))
        self.held = tk.StringVar(value="")
        self.profile = tk.StringVar(value=str(config.get("active_profile", "")))
        devices = sorted({str(m.get("device", "")) for m in config.get("mappings", []) if isinstance(m, dict)})
        for row, (label, variable, values) in enumerate([
            ("Device", self.device, devices), ("Control", self.control, None),
            ("Event", self.kind, ("press", "release", "relative", "absolute")),
            ("Held before event", self.held, None),
        ]):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=2)
            widget = ttk.Combobox(form, textvariable=variable, values=values) if values else ttk.Entry(form, textvariable=variable)
            widget.grid(row=row, column=1, sticky="ew", pady=2)
        next_row = 4
        if SUPPORTS_PROFILES:
            ttk.Label(form, text="Profile").grid(row=next_row, column=0, sticky="w")
            ttk.Entry(form, textvariable=self.profile).grid(row=next_row, column=1, sticky="ew")
            next_row += 1
        ttk.Label(form, text="Held controls: e.g. f1.shift, x1.hotcue. Leave blank for none.").grid(row=next_row, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.try_button = ttk.Button(self, text="Try event", command=self.preview)
        self.try_button.grid(row=3, column=0, sticky="w", padx=10, pady=(0, 6))
        self.result = ScrolledText(self, height=7, wrap="word", font="TkDefaultFont")
        self.result.grid(row=4, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Return>", lambda _event: self.preview())
        self.preview()

    @staticmethod
    def _write(widget: tk.Text, text: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def preview(self) -> None:
        try:
            report = preview_event(self.config_snapshot, self.device.get(), self.control.get(), self.kind.get(), self.held.get(), self.profile.get())
            text = preview_text(report)
        except (ValueError, TypeError, AttributeError, KeyError) as error:
            text = f"Could not preview: {error}"
        self._write(self.result, text)
