"""Read-only Tk mapping inspection; never imports or creates an action runner."""
from __future__ import annotations

import copy
import json
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any

from .mapping_rules import SUPPORTS_PROFILES, preview_event


def mapping_details(config: dict[str, Any], mapping: dict[str, Any], raw: bool = False) -> str:
    def describe(value: Any) -> str:
        if raw or not isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False, indent=2)
        labels = {"kind": "Event", "requires": "Hold", "unless": "Release", "enabled": "Enabled"}
        lines = []
        for key, item in value.items():
            label = labels.get(key, key.replace("_", " ").capitalize())
            text = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
            lines.append(f"{label}: {text}")
        return "\n".join(lines)
    sections = ["Selected mapping\n" + describe(mapping)]
    model = config.get("model_controls", {})
    parameters = model.get("parameters", {}) if isinstance(model, dict) else {}
    references = [("Action definition", config.get("actions", {}), mapping.get("action")),
                  ("Script slot", config.get("script_slots", {}), mapping.get("slot")),
                  ("Model parameter", parameters, mapping.get("parameter"))]
    for label, container, key in references:
        if isinstance(container, dict) and isinstance(key, str) and key in container:
            sections.append(label + "\n" + describe(container[key]))
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
    def __init__(self, parent: tk.Misc, config: dict[str, Any], index: int | None = None,
                 event: tuple[str, str, str] | None = None):
        super().__init__(parent)
        self.title("Inspect mapping · offline")
        self.geometry("790x640")
        self.minsize(580, 480)
        self.config_snapshot = copy.deepcopy(config)
        if event is not None:
            report = preview_event(self.config_snapshot, *event)
            decisions = report["decisions"]
            index = next((i for i, m, _ in decisions if m.get("kind") == event[2]), decisions[0][0] if decisions else None)
        mapping = self.config_snapshot["mappings"][index] if index is not None else {"device": event[0], "control": event[1], "kind": event[2]}
        self.unmapped_input = index is None
        self.mapping = mapping
        self.raw = tk.BooleanVar(value=False)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(4, weight=1)
        heading = ttk.Frame(self, padding=10)
        heading.grid(sticky="ew")
        heading.columnconfigure(0, weight=1)
        self.heading_label = ttk.Label(heading, text="Last received input · offline rehearsal. Set held controls below; they were not captured." if event else "Inspect, then try its routing without a controller.", wraplength=400)
        self.heading_label.grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.show_json = ttk.Checkbutton(heading, text="Show JSON", variable=self.raw, command=self.show_details)
        self.show_json.grid(row=0, column=1, sticky="ne")
        heading.bind("<Configure>", lambda e: self.heading_label.configure(wraplength=max(120, e.width - self.show_json.winfo_reqwidth() - 28)))
        self.details = ScrolledText(self, height=9, wrap="word", font="TkFixedFont")
        self.details.grid(row=1, column=0, sticky="nsew", padx=10)
        self.show_details()
        form = ttk.LabelFrame(self, text="Try an event · loaded profile snapshot", padding=8)
        form.grid(row=2, column=0, sticky="ew", padx=10, pady=8)
        form.columnconfigure(1, weight=1)
        self.device = tk.StringVar(value=event[0] if event else str(mapping.get("device", "f1")))
        self.control = tk.StringVar(value=event[1] if event else str(mapping.get("control", "")))
        self.kind = tk.StringVar(value=event[2] if event else str(mapping.get("kind", "press")))
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

    def show_details(self) -> None:
        prefix = "This received control has no mapping in the loaded profile.\n\n" if self.unmapped_input else ""
        self._write(self.details, prefix + mapping_details(self.config_snapshot, self.mapping, self.raw.get()))

    def preview(self) -> None:
        try:
            report = preview_event(self.config_snapshot, self.device.get(), self.control.get(), self.kind.get(), self.held.get(), self.profile.get())
            text = preview_text(report)
        except (ValueError, TypeError, AttributeError, KeyError) as error:
            text = f"Could not preview: {error}"
        self._write(self.result, text)
