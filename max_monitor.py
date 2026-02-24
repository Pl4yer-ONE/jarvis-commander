#!/usr/bin/env python3
"""
Max Live Monitor — Terminal Dashboard

A lightweight terminal-based live display of all Max data.
Run: python3 max_monitor.py
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
SENTINEL_STATE = DATA_DIR / "sentinel_state.json"


def clear():
    os.system("clear")


def color(text, code):
    return f"\033[{code}m{text}\033[0m"


def read_state():
    try:
        with open(SENTINEL_STATE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def get_service_status():
    try:
        r = subprocess.run(["systemctl", "--user", "is-active", "jarvis.service"],
                           capture_output=True, text=True, timeout=2)
        return r.stdout.strip()
    except Exception:
        return "unknown"


def render_bar(value, max_val=100, width=20):
    """Render a progress bar."""
    try:
        pct = float(value) / max_val
    except (ValueError, TypeError):
        return "?" * width
    filled = int(pct * width)
    bar = "█" * filled + "░" * (width - filled)
    if pct > 0.8:
        return color(bar, "31")  # Red
    elif pct > 0.5:
        return color(bar, "33")  # Yellow
    else:
        return color(bar, "32")  # Green


def main():
    while True:
        clear()
        state = read_state()
        now = datetime.now().strftime("%H:%M:%S")
        svc = get_service_status()
        svc_color = "32" if svc == "active" else "31"

        # Header
        print(color("╔══════════════════════════════════════════════════════════════════════╗", "36"))
        print(color("║", "36") + color("  ⚔ MAXIMUS DECIMUS MERIDIUS — COMMAND CENTER", "1;36") +
              f"      {now}  " + color(f"● {svc.upper()}", svc_color) +
              color("  ║", "36"))
        print(color("╚══════════════════════════════════════════════════════════════════════╝", "36"))
        print()

        # ── Sentinel Status ──
        print(color("🛡 SENTINEL STATUS", "1;32"))
        for key in ["camera", "yolo", "system", "usb", "self_update"]:
            s = state.get(key, {})
            status = s.get("status", "off")
            err = s.get("error")
            icon = color("●", "32") if status == "active" else color("○", "31")
            name = key.replace("_", " ").title().ljust(12)
            line = f"  {icon} {name}"
            if err:
                line += color(f" — {err[:50]}", "31")
            elif key == "yolo":
                dets = s.get("detections", [])
                if dets:
                    objs = ", ".join(f"{d['object']}({d['confidence']:.0%})" for d in dets[:5])
                    line += color(f" — {len(dets)} objects: {objs}", "33")
            elif key == "self_update":
                actions = s.get("actions", [])
                if actions:
                    line += color(f" — {actions[0]}", "90")
            print(line)

        print()

        # ── System Telemetry ──
        sys_data = state.get("system", {}).get("data", {})
        if sys_data:
            print(color("⚙ SYSTEM TELEMETRY", "1;36"))
            cpu = sys_data.get("cpu", "?")
            ram = sys_data.get("ram", "?")
            print(f"  CPU:     {render_bar(cpu)} {cpu}%")
            print(f"  RAM:     {render_bar(ram)} {ram}% ({sys_data.get('ram_used_gb', '?')}/{sys_data.get('ram_total_gb', '?')} GB)")
            print(f"  Disk:    {sys_data.get('disk_free', '?')} free")
            print(f"  Temp:    {sys_data.get('temp', '?')}")
            print(f"  Battery: {sys_data.get('battery', '?')}")
        print()

        # ── YOLO Vision ──
        yolo = state.get("yolo", {})
        dets = yolo.get("detections", [])
        print(color("🔍 YOLO VISION", "1;33"))
        cam = state.get("camera", {})
        cam_status = cam.get("status", "off")
        cam_icon = color("●", "32") if cam_status == "active" else color("○", "31")
        cam_time = ""
        try:
            cam_time = datetime.fromisoformat(cam.get("last_capture", "")).strftime("%H:%M:%S")
        except Exception:
            pass
        print(f"  {cam_icon} Camera  {color(cam_time, '90')}")

        if dets:
            for d in dets[:8]:
                conf = d.get("confidence", 0)
                conf_str = f"{conf:.0%}"
                conf_color = "32" if conf > 0.7 else "33" if conf > 0.4 else "31"
                cx, cy = d.get("center", [0, 0])
                print(f"    ▸ {color(d['object'].ljust(15), '1')} {color(conf_str, conf_color)}  @ ({cx},{cy})")
        else:
            print(color("    No objects detected", "90"))
        print()

        # ── USB Devices ──
        usb = state.get("usb", {})
        devices = usb.get("devices", [])
        new_dev = usb.get("new_device")
        print(color(f"🔌 USB DEVICES ({len(devices)})", "1;36"))
        for dev in devices:
            short = dev.split(": ID ")[1] if ": ID " in dev else dev
            is_new = new_dev and dev == new_dev
            prefix = color("★ NEW ", "32") if is_new else "  "
            print(f"  {prefix}• {short[:55]}")
        print()

        # ── Recent Logs ──
        print(color("🧠 RECENT LOGS (last 8)", "1;35"))
        try:
            r = subprocess.run(
                ["journalctl", "--user", "-u", "jarvis.service", "-n", "8", "-o", "cat", "--no-pager"],
                capture_output=True, text=True, timeout=3
            )
            skip = {"jack", "JackShm", "Cannot connect", "__pycache__"}
            for line in r.stdout.strip().split("\n"):
                if any(s in line for s in skip):
                    continue
                if not line.strip():
                    continue
                line = line[:80]
                if "ERROR" in line:
                    print(f"  {color(line, '31')}")
                elif "WARN" in line:
                    print(f"  {color(line, '33')}")
                else:
                    print(f"  {color(line, '90')}")
        except Exception:
            print(color("  Cannot read logs", "31"))

        print()
        print(color("  Refreshing every 3s... Press Ctrl+C to exit.", "90"))

        time.sleep(3)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n" + color("Strength and honor. Dashboard closed.", "36"))
