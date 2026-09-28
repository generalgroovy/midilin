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

EVENT_RE = re.compile(r"device=(\w+) control=([^ ]+).*kind=([^ ]+).*value=(-?\d+)")
SERVICE = "traktor-system-controller.service"


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
        mapping = _mapping_index(self.config_data).get((device, control), {})
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
        self.delete("all"); self.items.clear(); self.fills.clear()
        width = max(self.winfo_width(), 920); height = max(self.winfo_height(), 560)
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
        self.root=root; self.root.title("MIDILIN Controller Console"); self.root.geometry("1180x760")
        self.config_path=config_path.expanduser().resolve(); self.config=load_config(self.config_path)
        self.process: subprocess.Popen[str] | None=None; self.service_was_active=False
        self.output: queue.Queue[str]=queue.Queue(); self.bright_job=None; self.temp_job=None
        self.build(); self.root.protocol("WM_DELETE_WINDOW", self.close); self.root.after(80,self.drain)

    def build(self) -> None:
        top=ttk.Frame(self.root,padding=8); top.pack(fill="x")
        ttk.Label(top,text="MIDILIN",font=("Sans",16,"bold")).pack(side="left")
        self.status=tk.StringVar(value="Ready"); ttk.Label(top,textvariable=self.status).pack(side="right")
        book=ttk.Notebook(self.root); book.pack(fill="both",expand=True,padx=8,pady=(0,8))
        tabs=[ttk.Frame(book),ttk.Frame(book,padding=12),ttk.Frame(book,padding=8),ttk.Frame(book,padding=8)]
        for tab,name in zip(tabs,("Controller layout","Display controls","Mappings","Monitoring")): book.add(tab,text=name)
        self.canvas=ControllerCanvas(tabs[0],self.config); self.canvas.pack(fill="both",expand=True)
        self.build_settings(tabs[1]); self.build_mappings(tabs[2]); self.build_monitor(tabs[3])

    def build_settings(self,parent:ttk.Frame)->None:
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
            widget=ttk.Combobox(parent,textvariable=var,values=values,state="readonly") if values else (ttk.Spinbox(parent,from_=0,to=25000,textvariable=var) if isinstance(var,tk.IntVar) else ttk.Entry(parent,textvariable=var))
            widget.grid(row=row,column=1,sticky="ew",pady=3)
        ttk.Button(parent,text="Save",command=self.save_settings).grid(row=8,column=0,pady=10,sticky="w")
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
        parent.columnconfigure(1,weight=1)

    def build_mappings(self,parent:ttk.Frame)->None:
        cols=("device","control","kind","action","layer"); self.tree=ttk.Treeview(parent,columns=cols,show="headings")
        for name,width in zip(cols,(70,220,80,300,180)): self.tree.heading(name,text=name.title()); self.tree.column(name,width=width,anchor="w")
        self.tree.pack(fill="both",expand=True); self.fill_mappings()
        row=ttk.Frame(parent); row.pack(fill="x",pady=6)
        ttk.Button(row,text="Reload",command=self.reload).pack(side="left")
        ttk.Button(row,text="Validate",command=lambda:self.run_once(["--validate-config"])).pack(side="left",padx=6)
        ttk.Button(row,text="Open config folder",command=lambda:subprocess.Popen(["xdg-open",str(self.config_path.parent)])).pack(side="left")

    def fill_mappings(self)->None:
        for item in self.tree.get_children(): self.tree.delete(item)
        for m in self.config.get("mappings",[]):
            if not isinstance(m,dict): continue
            action=str(m.get("action","")); action += (":"+str(m["slot"])) if m.get("slot") else (":"+str(m["parameter"]) if m.get("parameter") else "")
            layer=",".join(m.get("requires",[]) or m.get("unless",[]))
            self.tree.insert("","end",values=(m.get("device"),m.get("control"),m.get("kind"),action,layer))

    def build_monitor(self,parent:ttk.Frame)->None:
        row=ttk.Frame(parent); row.pack(fill="x",pady=(0,6))
        for text,command in [("Detect devices",lambda:self.run_once(["--list-devices"])),("Read-only monitor",self.start_monitor),
                             ("Stop monitor",self.stop_process),("Start service",lambda:self.service("start")),
                             ("Restart service",lambda:self.service("restart")),("Stop service",lambda:self.service("stop")),
                             ("Service logs",lambda:self.run_external(["journalctl","--user","-u",SERVICE,"-n","200","--no-pager"]))]:
            ttk.Button(row,text=text,command=command).pack(side="left",padx=3)
        self.log=tk.Text(parent,wrap="none",font=("Monospace",9),state="disabled"); self.log.pack(fill="both",expand=True)

    def command(self)->list[str]:
        installed=shutil.which("traktor-system-controller")
        command = [installed] if installed else [sys.executable,str(Path(__file__).resolve().parents[1]/"traktor-controller.py")]
        return command + ["--config", str(self.config_path)]

    def service(self,action:str)->None: self.run_external(["systemctl","--user",action,SERVICE])
    def service_active(self)->bool: return subprocess.run(["systemctl","--user","is-active","--quiet",SERVICE],check=False).returncode==0

    def start_monitor(self)->None:
        self.stop_process(restart_service=False); self.service_was_active=self.service_active()
        if self.service_was_active: subprocess.run(["systemctl","--user","stop",SERVICE],check=False)
        command=self.command()+["--monitor","--dry-run"]; self.append("$ "+" ".join(command)+"\n")
        self.process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1,env=os.environ.copy())
        threading.Thread(target=self.reader,daemon=True).start(); self.status.set("Read-only controller monitor")

    def reader(self)->None:
        assert self.process and self.process.stdout
        for line in self.process.stdout: self.output.put(line)
        self.output.put("[monitor stopped]\n")

    def run_once(self,args:list[str])->None: self.run_external(self.command()+args)
    def run_external(self,command:list[str])->None:
        def worker()->None:
            result=subprocess.run(command,text=True,capture_output=True,check=False,env=os.environ.copy())
            self.output.put("$ "+" ".join(command)+"\n"+(result.stdout or "")+(result.stderr or ""))
        threading.Thread(target=worker,daemon=True).start()

    def drain(self)->None:
        try:
            while True:
                line=self.output.get_nowait(); self.append(line); match=EVENT_RE.search(line)
                if match: self.canvas.flash(match.group(1),match.group(2))
        except queue.Empty: pass
        self.root.after(80,self.drain)

    def append(self,text:str)->None:
        self.log.configure(state="normal"); self.log.insert("end",text); self.log.see("end"); self.log.configure(state="disabled")

    def stop_process(self,restart_service:bool=True)->None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try: self.process.wait(timeout=2)
            except subprocess.TimeoutExpired: self.process.kill()
        self.process=None
        if restart_service and self.service_was_active: subprocess.run(["systemctl","--user","start",SERVICE],check=False)
        self.service_was_active=False; self.status.set("Stopped")

    def schedule_brightness(self)->None:
        value=int(float(self.bright_test.get())); self.bright_value.configure(text=f"{value}%")
        if self.bright_job: self.root.after_cancel(self.bright_job)
        self.bright_job=self.root.after(180,lambda:self.run_once(["--set-brightness",str(value)]))

    def schedule_temperature(self)->None:
        value=int(float(self.temp_test.get())); self.temp_value.configure(text=f"{value} K")
        if self.temp_job: self.root.after_cancel(self.temp_job)
        self.temp_job=self.root.after(220,lambda:self.run_once(["--set-temperature",str(value)]))

    def save_settings(self)->None:
        try:
            raw=json.loads(self.config_path.read_text(encoding="utf-8")); display=raw.setdefault("display_controls",{})
            display.setdefault("brightness",{}).update({"backend":self.brightness_backend.get(),"device":self.brightness_device.get().strip(),"ddc_display":self.ddc_display.get().strip(),"minimum_percent":int(self.min_brightness.get())})
            display.setdefault("color_temperature",{}).update({"backend":self.temp_backend.get(),"minimum_kelvin":int(self.temp_min.get()),"maximum_kelvin":int(self.temp_max.get()),"take_ownership":True,"reset_at_max":True})
            self.config_path.write_text(json.dumps(raw,indent=2)+"\n",encoding="utf-8"); self.reload(); self.status.set("Display configuration saved")
        except Exception as exc: messagebox.showerror("MIDILIN",str(exc))

    def reload(self)->None:
        self.config=load_config(self.config_path); self.canvas.config_data=self.config; self.canvas.redraw(); self.fill_mappings(); self.status.set("Configuration reloaded")

    def close(self)->None: self.stop_process(); self.root.destroy()


def main(config_path: Path = DEFAULT_CONFIG)->int:
    root=tk.Tk(); MidiLinGui(root, config_path); root.mainloop(); return 0


if __name__=="__main__": raise SystemExit(main())
