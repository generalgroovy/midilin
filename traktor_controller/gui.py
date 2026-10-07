from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

from .common import DEFAULT_CONFIG, load_config
from .cli import validate_config
from .gui_support import execute_command, mapping_rows, save_profile
from .mapping_inspector import MappingInspector

EVENT_RE = re.compile(r"device=(\w+) control=([^ ]+).*kind=([^ ]+).*value=(-?\d+)")
SERVICE = "traktor-system-controller.service"


def display_values(config: dict[str, Any]) -> dict[str, Any]:
    controls = config.get("display_controls", {})
    bright = controls.get("brightness", {})
    temp = controls.get("color_temperature", {})
    values = {
        "brightness_backend": str(bright.get("backend", "auto")),
        "brightness_device": str(bright.get("device", "")),
        "ddc_display": str(bright.get("ddc_display", "")),
        "min_brightness": int(bright.get("minimum_percent", 1)),
        "temp_backend": str(temp.get("backend", "auto")),
        "temp_min": int(temp.get("minimum_kelvin", 2500)),
        "temp_max": int(temp.get("maximum_kelvin", 6500)),
    }
    if not 0 <= values["min_brightness"] <= 100:
        raise ValueError("Minimum brightness must be between 0 and 100%.")
    if not 1000 <= values["temp_min"] < values["temp_max"] <= 25000:
        raise ValueError("Temperature must rise from a minimum of at least 1000 K to a neutral value of at most 25000 K.")
    return values


def _mapping_index(config: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for mapping in config.get("mappings", []):
        if isinstance(mapping, dict) and mapping.get("enabled", True):
            result.setdefault((str(mapping.get("device")), str(mapping.get("control"))), mapping)
    return result


class ControllerCanvas(tk.Canvas):
    def __init__(self, master: tk.Misc, config: dict[str, Any]):
        super().__init__(master, background="#15171a", highlightthickness=0)
        self.config_data = config
        self.items: dict[str, int] = {}
        self.fills: dict[int, str] = {}
        self.bind("<Configure>", lambda _event: self.redraw())

    def control(self, device: str, control: str, box: tuple[float, float, float, float],
                label: str, oval: bool = False) -> None:
        mapping = self.mapping_lookup.get((device, control), {})
        action = str(mapping.get("action", "unmapped"))
        fill = "#292d33" if action != "unmapped" else "#202327"
        item = (self.create_oval if oval else self.create_rectangle)(
            *box, fill=fill, outline="#7b8794", width=1)
        x1, y1, x2, y2 = box
        self.create_text((x1+x2)/2, (y1+y2)/2, text=label, fill="#f2f4f8", font=("Sans", 8))
        self.create_text((x1+x2)/2, y2+9, text=action[:20], fill="#9aa6b2", font=("Sans", 7))
        self.items[f"{device}.{control}"] = item
        self.fills[item] = fill

    def redraw(self) -> None:
        self.mapping_lookup = _mapping_index(self.config_data)
        self.delete("all"); self.items.clear(); self.fills.clear()
        width = max(self.winfo_width(), 920); height = max(self.winfo_height(), 560)
        self.configure(scrollregion=(0, 0, width, height))
        margin, gap = 24, 28
        f1w = (width - margin*2 - gap) * .55
        self.draw_f1(margin, 18, f1w, height-36)
        self.draw_x1(margin+f1w+gap, 18, width-margin*2-gap-f1w, height-36)

    def draw_f1(self, x: float, y: float, w: float, h: float) -> None:
        self.create_rectangle(x, y, x+w, y+h, fill="#0c0d0f", outline="#8e99a5", width=2)
        self.create_text(x+w/2, y+18, text="TRAKTOR F1 — MIDILIN", fill="white", font=("Sans", 11, "bold"))
        for i in range(4):
            cx = x+(i+.5)*w/4
            self.control("f1", f"knob_{i+1}", (cx-18,y+40,cx+18,y+76), f"K{i+1}", True)
            self.control("f1", f"fader_{i+1}", (cx-11,y+112,cx+11,y+242), f"F{i+1}")
        padw = (w-50)/4; padh = min(48,(h-390)/4)
        for row in range(4):
            for col in range(4):
                n = row*4+col+1; px=x+16+col*(padw+6); py=y+282+row*(padh+8)
                self.control("f1", f"grid_{n}", (px,py,px+padw,py+padh), str(n))
        controls = [("play_1","PLAY"),("play_2","PREV"),("play_3","NEXT"),
                    ("play_4","MUTE"),("reverse","CLOSE"),("shift","SHIFT")]
        bw=(w-28)/len(controls)
        for i,(control,label) in enumerate(controls):
            bx=x+8+i*bw
            self.control("f1", control, (bx,y+h-64,bx+bw-5,y+h-30), label)

    def draw_x1(self, x: float, y: float, w: float, h: float) -> None:
        self.create_rectangle(x, y, x+w, y+h, fill="#0c0d0f", outline="#8e99a5", width=2)
        self.create_text(x+w/2, y+18, text="TRAKTOR X1 — SWAY", fill="white", font=("Sans", 11, "bold"))
        knobs=["fx1_dry_wet","fx1_knob_1","fx1_knob_2","fx1_knob_3",
               "fx2_dry_wet","fx2_knob_1","fx2_knob_2","fx2_knob_3"]
        for i,control in enumerate(knobs):
            row,col=divmod(i,4); cx=x+(col+.5)*w/4; cy=y+66+row*84
            self.control("x1", control, (cx-17,cy-17,cx+17,cy+17), f"FX{i+1}", True)
        buttons=["fx1_on","fx1_button_1","fx1_button_2","fx1_button_3",
                 "fx2_on","fx2_button_1","fx2_button_2","fx2_button_3"]
        for i,control in enumerate(buttons):
            row,col=divmod(i,4); bx=x+8+col*(w-16)/4; by=y+190+row*48
            self.control("x1", control, (bx,by,bx+(w-16)/4-5,by+28), f"B{i+1}")
        encoders=["deck_a_browse_encoder","deck_b_browse_encoder","deck_a_loop_encoder","deck_b_loop_encoder"]
        for i,control in enumerate(encoders):
            cx=x+(i+.5)*w/4
            self.control("x1", control, (cx-20,y+300,cx+20,y+340), f"E{i+1}", True)
        deck=["deck_a_play","deck_a_cue","deck_a_in","deck_a_out",
              "deck_b_play","deck_b_cue","deck_b_in","deck_b_out"]
        for i,control in enumerate(deck):
            row,col=divmod(i,4); bx=x+8+col*(w-16)/4; by=y+380+row*58
            self.control("x1", control, (bx,by,bx+(w-16)/4-5,by+34), control.replace("deck_","").upper())

    def flash(self, device: str, control: str) -> None:
        item = self.items.get(f"{device}.{control}")
        if item:
            self.itemconfigure(item, fill="#00a6ff", outline="white", width=2)
            self.after(300, lambda: self.itemconfigure(item, fill=self.fills.get(item,"#292d33"), outline="#7b8794", width=1))


class MidiLinGui:
    def __init__(self, root: tk.Tk, config_path: Path = DEFAULT_CONFIG):
        self.root=root; self.root.title("MIDILIN Controller Console")
        self.config_path=config_path.expanduser().resolve(); self.config=load_config(self.config_path)
        self.process: subprocess.Popen[str] | None=None; self.service_was_active=False
        self.output: queue.Queue=queue.Queue(); self.bright_job=None; self.temp_job=None
        self.detection="Devices not checked"; self.command_serial=0; self.detection_serial=0
        self.build(); self.root.protocol("WM_DELETE_WINDOW", self.close); self.root.after(80,self.drain)

    def build(self) -> None:
        top=ttk.Frame(self.root,padding=8); top.pack(fill="x")
        ttk.Label(top,text="MIDILIN",font=("Sans",16,"bold")).pack(side="left")
        self.status=tk.StringVar(value="Ready"); ttk.Label(top,textvariable=self.status).pack(side="right")
        self.root.minsize(860, 620)
        self.root.geometry(f"{min(1180, self.root.winfo_screenwidth() - 48)}x{min(760, self.root.winfo_screenheight() - 100)}")
        self.profile_check = "unchecked"
        self.validation_serial = 0
        setup = ttk.Frame(self.root, padding=(8, 0, 8, 8))
        setup.pack(fill="x")
        self.readiness = tk.StringVar()
        self.readiness_label = ttk.Label(setup, textvariable=self.readiness, wraplength=820)
        self.readiness_label.pack(anchor="w")
        self.next_hint = tk.StringVar()
        ttk.Label(setup, textvariable=self.next_hint, wraplength=820).pack(anchor="w", pady=(4, 0))
        steps = ttk.Frame(setup)
        steps.pack(anchor="w", pady=(5, 0))
        self.next_button = ttk.Button(steps, command=self.take_next_step)
        self.next_button.pack(side="left", padx=(0, 6))
        ttk.Button(steps, text="Explore mappings", command=lambda: self.show_tab("mappings")).pack(side="left", padx=(0, 6))
        ttk.Button(steps, text="Monitor & runtime", command=lambda: self.show_tab("monitor")).pack(side="left")
        self.book = ttk.Notebook(self.root)
        self.book.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tabs = {name: ttk.Frame(self.book, padding=8) for name in ("mappings", "layout", "settings", "monitor")}
        for name, label in (("mappings", "Mappings"), ("layout", "Controller layout"), ("settings", "Display settings"), ("monitor", "Monitor & runtime")):
            self.book.add(self.tabs[name], text=label)
        self.canvas = ControllerCanvas(self.tabs["layout"], self.config)
        self.build_layout(self.tabs["layout"])
        self.build_settings(self.tabs["settings"])
        self.build_mappings(self.tabs["mappings"])
        self.build_monitor(self.tabs["monitor"])
        self.track_settings()
        self.refresh_readiness()


    def build_layout(self, parent: ttk.Frame) -> None:
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        horizontal = ttk.Scrollbar(parent, orient="horizontal", command=self.canvas.xview)
        vertical = ttk.Scrollbar(parent, command=self.canvas.yview)
        horizontal.grid(row=1, column=0, sticky="ew")
        vertical.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(xscrollcommand=horizontal.set, yscrollcommand=vertical.set)

    def show_tab(self, name: str) -> None:
        if not hasattr(self, "book"):
            return
        self.book.select(self.tabs[name])
        (self.mapping_search if name == "mappings" else self.detect_button).focus_set()

    def clear_mapping_filters(self) -> None:
        self.mapping_query.set("")
        self.mapping_state.set("All")
        self.mapping_search.focus_set()

    def update_mapping_action(self) -> None:
        if hasattr(self, "inspect_button"):
            self.inspect_button.configure(state="normal" if self.tree.selection() else "disabled")

    def refresh_next_action(self) -> None:
        if not hasattr(self, "next_button"):
            return
        check = getattr(self, "profile_check", "unchecked")
        if check == "checking":
            label, hint, state = "Checking profile…", "Checking the saved file. Your unsaved display draft stays here.", "disabled"
        elif check != "valid":
            label, hint, state = "Check saved profile", "Start here: check the saved profile, or explore mappings without a device.", "normal"
            if check == "failed":
                hint = "Profile needs attention. See Monitor & runtime for details, fix the file, then check again."
        elif self.detection == "Checking devices…":
            label, hint, state = "Detecting devices…", "Looking for controllers. Results appear in Monitor & runtime.", "disabled"
        elif self.detection != "Device check complete":
            label, hint, state = "Detect devices", "Profile checked. Connect a controller, then detect devices.", "normal"
        else:
            label, hint, state = "Monitor input", "Review the device list, then monitor input to see incoming controls.", "normal"
        self.next_button.configure(text=label, state=state)
        self.next_hint.set(hint)

    def take_next_step(self) -> None:
        if self.profile_check != "valid":
            self.run_once(["--validate-config"])
        elif self.detection != "Device check complete":
            self.run_once(["--list-devices"])
        else:
            self.start_monitor()

    def build_input_link(self, parent: ttk.Frame) -> None:
        self.last_input = None
        self.last_input_text = tk.StringVar(value="No input received in this console session.")
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(0, 8))
        self.input_inspect_button = ttk.Button(row, text="Inspect last input", state="disabled", command=self.inspect_last_input)
        self.input_inspect_button.pack(side="right", padx=(8, 0))
        ttk.Label(row, textvariable=self.last_input_text, wraplength=580).pack(side="left", fill="x", expand=True)

    def clear_last_input(self) -> None:
        self.last_input = None
        if hasattr(self, "last_input_text"):
            self.last_input_text.set("Waiting for input from this console process.")
            self.input_inspect_button.configure(state="disabled")

    def receive_input(self, match: re.Match) -> None:
        device, control, kind, value = match.groups()
        if kind not in {"press", "release", "relative", "absolute"}:
            return
        self.last_input = (device, control, kind)
        if hasattr(self, "last_input_text"):
            self.last_input_text.set(f"Last received: {device}.{control} · {kind} · value {value}")
            self.input_inspect_button.configure(state="normal")

    def inspect_last_input(self) -> None:
        event = getattr(self, "last_input", None)
        if event is None:
            return
        previous = getattr(self, "inspector", None)
        if previous is not None and previous.winfo_exists():
            previous.destroy()
        self.inspector = MappingInspector(self.root, self.config, event=event)

    def set_session_status(self, text: str) -> None:
        self.session_serial = getattr(self, "session_serial", 0) + 1
        if hasattr(self, "session_status"):
            self.session_status.set(text)

    def build_settings(self,parent:ttk.Frame)->None:
        ttk.Label(parent, text=f"Profile: {self.config_path}", wraplength=780).grid(row=14, column=0, columnspan=3, sticky="w", pady=8)
        controls=self.config.get("display_controls",{}); bright=controls.get("brightness",{}); temp=controls.get("color_temperature",{})
        self.brightness_backend=tk.StringVar(value=str(bright.get("backend","auto")))
        self.brightness_device=tk.StringVar(value=str(bright.get("device","")))
        self.ddc_display=tk.StringVar(value=str(bright.get("ddc_display","")))
        self.min_brightness=tk.IntVar(value=int(bright.get("minimum_percent",1)))
        self.temp_backend=tk.StringVar(value=str(temp.get("backend","auto")))
        self.temp_min=tk.IntVar(value=int(temp.get("minimum_kelvin",2500))); self.temp_max=tk.IntVar(value=int(temp.get("maximum_kelvin",6500)))
        fields=[("Brightness backend",self.brightness_backend,("auto","backlight","ddc")),
                ("brightnessctl device",self.brightness_device,None),("ddcutil display",self.ddc_display,None),
                ("Minimum brightness %",self.min_brightness,None),("Blue-light backend",self.temp_backend,("auto","wlsunset","gammastep")),
                ("Minimum temperature K",self.temp_min,None),("Neutral temperature K",self.temp_max,None)]
        for row,(label,var,values) in enumerate(fields):
            ttk.Label(parent,text=label).grid(row=row,column=0,sticky="w",pady=3)
            if values:
                widget = ttk.Combobox(parent, textvariable=var, values=values, state="readonly")
            elif isinstance(var, tk.IntVar):
                low, high = (0, 100) if var is self.min_brightness else (1000, 25000)
                widget = ttk.Spinbox(parent, from_=low, to=high, textvariable=var)
            else:
                widget = ttk.Entry(parent, textvariable=var)
            widget.grid(row=row,column=1,sticky="ew",pady=3)
        ttk.Button(parent,text="Save configuration",command=self.save_settings).grid(row=8,column=0,pady=10,sticky="w")
        ttk.Button(parent,text="Open config",command=lambda:subprocess.Popen(["xdg-open",str(self.config_path)])).grid(row=8,column=1,pady=10,sticky="w")
        ttk.Separator(parent).grid(row=9,column=0,columnspan=3,sticky="ew",pady=10)
        self.bright_test=tk.IntVar(value=50); self.temp_test=tk.IntVar(value=4500)
        ttk.Label(parent,text="Live brightness test").grid(row=10,column=0,sticky="w")
        ttk.Scale(parent,from_=1,to=100,variable=self.bright_test,command=lambda _v:self.schedule_brightness()).grid(row=10,column=1,sticky="ew")
        self.bright_value=ttk.Label(parent,text="50%"); self.bright_value.grid(row=10,column=2)
        ttk.Label(parent,text="Live blue-light test").grid(row=11,column=0,sticky="w")
        ttk.Scale(parent,from_=2500,to=6500,variable=self.temp_test,command=lambda _v:self.schedule_temperature()).grid(row=11,column=1,sticky="ew")
        self.temp_value=ttk.Label(parent,text="4500 K"); self.temp_value.grid(row=11,column=2)
        ttk.Button(parent,text="Diagnose display backends",command=lambda:self.run_once(["--diagnose-display"])).grid(row=12,column=0,pady=10,sticky="w")
        self.draft_status = tk.StringVar(value="No unsaved display changes")
        ttk.Label(parent, textvariable=self.draft_status).grid(row=13, column=0, columnspan=3, sticky="w", pady=8)
        parent.columnconfigure(1,weight=1)

    def build_mappings(self,parent:ttk.Frame)->None:
        search=ttk.Frame(parent); search.pack(fill="x",pady=(0,6))
        self.mapping_query=tk.StringVar(); self.mapping_state=tk.StringVar(value="All"); self.mapping_count=tk.StringVar()
        ttk.Label(search,text="Find mapping").pack(side="left")
        self.mapping_search = ttk.Entry(search, textvariable=self.mapping_query)
        self.mapping_search.pack(side="left", fill="x", expand=True, padx=6)
        self.clear_search_button = ttk.Button(search, text="Clear filters", command=self.clear_mapping_filters)
        self.clear_search_button.pack(side="left", padx=(0, 6))
        ttk.Combobox(search,textvariable=self.mapping_state,values=("All","Enabled","Disabled"),state="readonly",width=10).pack(side="left")
        ttk.Label(search,textvariable=self.mapping_count).pack(side="left",padx=6)
        self.mapping_hint = tk.StringVar(value="Select a mapping to rehearse it. No device or desktop action is needed.")
        ttk.Label(parent, textvariable=self.mapping_hint, wraplength=800).pack(anchor="w", pady=(0, 6))
        table=ttk.Frame(parent); table.pack(fill="both", expand=True)
        cols=("device","control","kind","action","layer","state"); self.tree=ttk.Treeview(table,columns=cols,show="headings",selectmode="browse")
        for name,width in zip(cols,(70,200,80,240,180,80)): self.tree.heading(name,text=name.title()); self.tree.column(name,width=width,anchor="w")
        self.mapping_scrollbars(table)
        self.fill_mappings()
        self.tree.bind("<Double-1>", lambda _event: self.inspect_mapping())
        self.tree.bind("<Return>", lambda _event: self.inspect_mapping())
        self.mapping_query.trace_add("write",lambda *_:self.fill_mappings())
        self.mapping_state.trace_add("write",lambda *_:self.fill_mappings())
        row=ttk.Frame(parent); row.pack(fill="x",pady=6)
        self.inspect_button = ttk.Button(row, text="Inspect / try event", command=self.inspect_mapping)
        self.inspect_button.pack(side="left", padx=(0, 6))
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self.update_mapping_action())
        self.update_mapping_action()
        ttk.Button(row,text="Reload",command=self.reload).pack(side="left")
        ttk.Button(row,text="Validate",command=lambda:self.run_once(["--validate-config"])).pack(side="left",padx=6)
        ttk.Button(row,text="Open config folder",command=lambda:subprocess.Popen(["xdg-open",str(self.config_path.parent)])).pack(side="left")

    def fill_mappings(self)->None:
        selected=self.tree.selection()
        for item in self.tree.get_children(): self.tree.delete(item)
        rows=mapping_rows(self.config,self.mapping_query.get(),self.mapping_state.get())
        for key,values in rows:self.tree.insert("","end",iid=key,values=values)
        self.mapping_count.set(f"{len(rows)} shown")
        for key in selected:
            if self.tree.exists(key):self.tree.selection_add(key)
        if hasattr(self, "mapping_hint"):
            filtered = bool(self.mapping_query.get().strip()) or self.mapping_state.get() != "All"
            self.mapping_hint.set("No matches. Clear filters to see all mappings." if not rows and filtered else
                                  "This profile has no mappings. Open the configuration to add controls." if not rows else
                                  "Select a mapping to rehearse it. No device or desktop action is needed.")
        self.update_mapping_action()

    def refresh_readiness(self)->None:
        if not hasattr(self,"readiness"):return
        enabled=sum(bool(m.get("enabled",True)) for m in self.config.get("mappings",[]) if isinstance(m,dict))
        self.readiness.set(f"{self.config_path.name} · {enabled} enabled mappings · {self.detection}")
        self.refresh_next_action()

    def build_monitor(self,parent:ttk.Frame)->None:
        self.session_status = tk.StringVar(value="Console idle · background service not checked")
        ttk.Label(parent, textvariable=self.session_status, wraplength=800, font=("Sans", 10, "bold")).pack(anchor="w", pady=(0, 8))
        inspect = ttk.LabelFrame(parent, text="Inspect input · mapped actions off", padding=8)
        inspect.pack(fill="x", pady=(0, 8))
        ttk.Button(inspect, text="Check profile", command=lambda: self.run_once(["--validate-config"])).pack(side="left", padx=(0, 6))
        self.detect_button = ttk.Button(inspect, text="Detect devices", command=lambda: self.run_once(["--list-devices"]))
        self.detect_button.pack(side="left", padx=(0, 6))
        self.monitor_button = ttk.Button(inspect, text="Read-only monitor", command=self.start_monitor)
        self.monitor_button.pack(side="left", padx=(0, 6))
        self.stop_button = ttk.Button(inspect, text="Stop monitor", command=self.stop_process)
        self.stop_button.pack(side="left")
        active = ttk.LabelFrame(parent, text="Apply mappings · controls your desktop", padding=8)
        active.pack(fill="x", pady=(0, 8))
        for label, action in (("Start service", "start"), ("Restart service", "restart"), ("Stop service", "stop")):
            ttk.Button(active, text=label, command=lambda value=action: self.service(value)).pack(side="left", padx=(0, 6))
        ttk.Button(active, text="Service logs", command=lambda: self.run_external(["journalctl", "--user", "-u", SERVICE, "-n", "200", "--no-pager"])).pack(side="left")
        ttk.Label(parent, text="Monitoring temporarily pauses an active service. Stop monitor or close to restore it.", wraplength=800).pack(anchor="w", pady=(0, 8))
        self.build_input_link(parent)
        log_frame = ttk.Frame(parent)
        log_frame.pack(fill="both", expand=True)
        self.log = tk.Text(log_frame, wrap="word", font=("Monospace", 9), state="disabled", height=8)
        self.log.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(log_frame, command=self.log.yview)
        scroll.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=scroll.set)

    def command(self)->list[str]:
        installed=shutil.which("traktor-system-controller")
        command = [installed] if installed else [sys.executable,str(Path(__file__).resolve().parents[1]/"traktor-controller.py")]
        return command + ["--config", str(self.config_path)]

    def service(self,action:str)->None: self.run_external(["systemctl","--user",action,SERVICE])
    def service_active(self)->bool: return subprocess.run(["systemctl","--user","is-active","--quiet",SERVICE],check=False,timeout=5).returncode==0

    def start_monitor(self)->None:
        self.show_tab("monitor")
        self.clear_last_input()
        restore_previous=self.service_was_active
        try:
            self.stop_process(restart_service=False); self.service_was_active=restore_previous
            self.service_was_active=self.service_active() or restore_previous
            if self.service_was_active: subprocess.run(["systemctl","--user","stop",SERVICE],check=True,timeout=5)
            command=self.command()+["--monitor","--dry-run"]; self.append("$ "+" ".join(command)+"\n")
            process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1,env=os.environ.copy())
        except (OSError,subprocess.SubprocessError) as error:
            self.status.set("Could not start; use Stop monitor to restore service" if self.service_was_active else "Could not start; see Monitor & runtime"); self.append(f"Could not start: {error}\n"); self.set_session_status("Monitor could not start · use Stop monitor to restore a paused service"); return
        self.process=process
        self.set_session_status("Read-only input running · mapped actions off" + (" · service resumes on Stop" if self.service_was_active else ""))
        threading.Thread(target=self.reader,args=(process,),daemon=True).start(); self.status.set("Read-only controller monitor")

    def reader(self,process:subprocess.Popen[str])->None:
        try:
            if process.stdout:
                for line in process.stdout:self.output.put(("line",process,line))
            code=process.wait()
        except (OSError,ValueError) as error:
            self.output.put(("line",process,f"Read error: {error}\n")); code=-1
        self.output.put(("stopped",process,code))

    def run_once(self,args:list[str])->None: self.run_external(self.command()+args)
    def run_external(self,command:list[str])->None:
        if not any(arg in command for arg in ("--set-brightness", "--set-temperature")):
            self.show_tab("monitor")
        self.command_serial+=1; token=self.command_serial; self.status.set("Checking…")
        if "--list-devices" in command:
            self.detection_serial=token
            self.detection="Checking devices…"
        if "--validate-config" in command:
            self.validation_serial=token
            self.profile_check="checking"
        self.refresh_readiness()
        if "systemctl" in command and SERVICE in command:
            self.service_feedback = (token, getattr(self, "session_serial", 0))
        def worker()->None:
            code,text=execute_command(command)
            self.output.put(("command",token,command,code,"$ "+" ".join(command)+"\n"+text))
        threading.Thread(target=worker,daemon=True).start()

    def handle_output(self,item:tuple)->None:
        if item[0]=="command":
            _,token,command,code,text=item
            self.append(text); self.append(f"[exit {code if code is not None else 'unavailable'}]\n")
            if "--list-devices" in command and token==self.detection_serial:
                self.detection="Device check complete" if code==0 else "Device check failed; see Monitor & runtime"
                self.refresh_readiness()
            if "--validate-config" in command and token==getattr(self, "validation_serial", 0):
                self.profile_check="valid" if code==0 else "failed"
                self.refresh_next_action()
            if "systemctl" in command and SERVICE in command and getattr(self, "service_feedback", None) == (token, getattr(self, "session_serial", 0)):
                self.set_session_status("Service request " + ("completed · see log" if code==0 else "failed · see log"))
            if token==self.command_serial:self.status.set("Check completed" if code==0 else "Check failed; see Monitor & runtime")
            return
        _,process,value=item
        if process is not self.process:return
        if item[0]=="stopped":
            self.process=None; self.set_session_status(f"Monitor ended (exit {value})" + (" · Stop monitor restores service" if getattr(self, "service_was_active", False) else " · mapped actions off")); self.status.set(f"Monitor stopped (exit {value})"); self.append(f"[monitor stopped: exit {value}]\n"); return
        self.append(value); match=EVENT_RE.search(value)
        if match:
            self.receive_input(match)
            self.canvas.flash(match.group(1),match.group(2))

    def drain(self)->None:
        try:
            for _ in range(200):self.handle_output(self.output.get_nowait())
        except queue.Empty: pass
        self.root.after(80,self.drain)

    def append(self,text:str)->None:
        self.log.configure(state="normal"); self.log.insert("end",text)
        if int(self.log.index("end-1c").split(".")[0])>2000:self.log.delete("1.0","end-2000l")
        self.log.see("end"); self.log.configure(state="disabled")

    def stop_process(self,restart_service:bool=True)->None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try: self.process.wait(timeout=2)
            except subprocess.TimeoutExpired: self.process.kill()
        self.process=None
        if restart_service and self.service_was_active:
            code,text=execute_command(["systemctl","--user","start",SERVICE],timeout=5)
            if code!=0:
                self.append(text); self.status.set("Could not restore service; retry Stop monitor"); self.set_session_status("Service restore failed · retry Stop monitor"); return
        self.set_session_status("Previous service restored" if restart_service and self.service_was_active else "Console monitor stopped · service status not checked")
        self.service_was_active=False; self.status.set("Stopped")

    def schedule_brightness(self)->None:
        value=int(float(self.bright_test.get())); self.bright_value.configure(text=f"{value}%")
        if self.bright_job: self.root.after_cancel(self.bright_job)
        self.bright_job=self.root.after(180,lambda:self.run_once(["--set-brightness",str(value)]))

    def schedule_temperature(self)->None:
        value=int(float(self.temp_test.get())); self.temp_value.configure(text=f"{value} K")
        if self.temp_job: self.root.after_cancel(self.temp_job)
        self.temp_job=self.root.after(220,lambda:self.run_once(["--set-temperature",str(value)]))

    def save_settings(self)->bool:
        try:
            raw=json.loads(self.config_path.read_text(encoding="utf-8")); display=raw.setdefault("display_controls",{})
            display.setdefault("brightness",{}).update({"backend":self.brightness_backend.get(),"device":self.brightness_device.get().strip(),"ddc_display":self.ddc_display.get().strip(),"minimum_percent":int(self.min_brightness.get())})
            display.setdefault("color_temperature",{}).update({"backend":self.temp_backend.get(),"minimum_kelvin":int(self.temp_min.get()),"maximum_kelvin":int(self.temp_max.get())})
            display_values(raw)
            candidate = load_config(self.config_path)
            candidate["display_controls"] = raw["display_controls"]
            errors = validate_config(candidate)
            if errors:
                raise ValueError("\n".join(errors))
            save_profile(self.config_path, raw)
            if self.reload(confirm=False):
                self.status.set("Display configuration saved")
                return True
        except (Exception, SystemExit) as exc: messagebox.showerror("MIDILIN",str(exc))
        return False

    def reload(self, confirm: bool = True)->bool:
        if confirm and not self.confirm_settings("reloading"):
            return False
        try:
            candidate = load_config(self.config_path)
            errors = validate_config(candidate)
            if errors:
                raise ValueError("\n".join(errors))
            values = display_values(candidate)
        except (OSError, ValueError, TypeError, AttributeError, SystemExit) as error:
            messagebox.showerror("Could not reload configuration", str(error))
            return False
        self.config = candidate
        self.profile_check = "unchecked"
        self.validation_serial = 0
        for name, value in values.items():
            getattr(self, name).set(value)
        self.canvas.config_data=self.config; self.canvas.redraw(); self.fill_mappings(); self.status.set("Configuration reloaded")
        self.refresh_readiness()
        self.remember_settings()
        return True

    def mapping_scrollbars(self, table: ttk.Frame) -> None:
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        horizontal = ttk.Scrollbar(table, orient="horizontal", command=self.tree.xview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)

    def inspect_mapping(self) -> None:
        selected = self.tree.selection()
        if not selected:
            self.status.set("Select a mapping, then Inspect / try event")
            self.tree.focus_set()
            return
        previous = getattr(self, "inspector", None)
        if previous is not None and previous.winfo_exists():
            previous.destroy()
        self.inspector = MappingInspector(self.root, self.config, int(selected[0]))

    def settings_snapshot(self) -> tuple[str, ...]:
        values = []
        for name in ("brightness_backend", "brightness_device", "ddc_display", "min_brightness", "temp_backend", "temp_min", "temp_max"):
            try:
                values.append(str(getattr(self, name).get()))
            except (tk.TclError, ValueError):
                values.append("<invalid>")
        return tuple(values)

    def track_settings(self) -> None:
        self.remember_settings()
        for name in ("brightness_backend", "brightness_device", "ddc_display", "min_brightness", "temp_backend", "temp_min", "temp_max"):
            getattr(self, name).trace_add("write", lambda *_: self.update_draft_status())

    def remember_settings(self) -> None:
        self.settings_baseline = self.settings_snapshot()
        self.update_draft_status()

    def update_draft_status(self) -> None:
        if hasattr(self, "draft_status"):
            dirty = self.settings_snapshot() != self.settings_baseline
            self.draft_status.set("Unsaved display changes" if dirty else "No unsaved display changes")

    def confirm_settings(self, action: str) -> bool:
        if not hasattr(self, "settings_baseline") or self.settings_snapshot() == self.settings_baseline:
            return True
        choice = messagebox.askyesnocancel("Unsaved display changes", f"Save your display changes before {action}?\nYes: save. No: discard. Cancel: keep editing.", parent=self.root)
        if choice is None:
            return False
        return self.save_settings() if choice else True

    def close(self)->None:
        if self.confirm_settings("closing"):
            self.stop_process(); self.root.destroy()


def main(config_path: Path = DEFAULT_CONFIG)->int:
    root=tk.Tk(); MidiLinGui(root, config_path); root.mainloop(); return 0


if __name__=="__main__": raise SystemExit(main())
