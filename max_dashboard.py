#!/usr/bin/env python3
"""
Maximus Desktop Dashboard — Full Sentinel Edition

A full-screen, always-on-bottom GTK application that acts as a live interactive wallpaper.
Shows FIVE panes: Sentinel Status, System Telemetry, YOLO Vision, Processing Logs, and Chat.

All data refreshes in real-time from sentinel_state.json, journalctl, and chat_log.txt.
"""

import json
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango

JARVIS_DIR = Path(__file__).parent
DATA_DIR = JARVIS_DIR / "data"
SENTINEL_STATE = DATA_DIR / "sentinel_state.json"
CHAT_LOG = DATA_DIR / "chat_log.txt"

# ── Color Palette ────────────────────────────────────────────

COLORS = {
    "bg": (0.02, 0.03, 0.08, 0.93),
    "accent_cyan": "#00FFCC",
    "accent_purple": "#AA55FF",
    "accent_orange": "#FFAA00",
    "accent_red": "#FF5555",
    "accent_green": "#55FF55",
    "text_primary": "#EEEEEE",
    "text_dim": "#888888",
    "text_white": "#FFFFFF",
    "status_active": "#00FF88",
    "status_error": "#FF4444",
}


class MaximusDashboard(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)

        # Configure as desktop wallpaper level window
        self.set_title("MAXIMUS COMMAND CENTER")
        self.set_decorated(False)
        self.set_keep_below(True)
        self.set_accept_focus(False)
        self.set_can_focus(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_type_hint(Gdk.WindowTypeHint.DESKTOP)

        # RGBA transparency
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual and screen.is_composited():
            self.set_visual(visual)
        self.set_app_paintable(True)
        self.connect("draw", self._on_draw)

        # Main vertical layout
        self.main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.main_vbox.set_margin_top(50)
        self.main_vbox.set_margin_bottom(40)
        self.main_vbox.set_margin_start(30)
        self.main_vbox.set_margin_end(30)
        self.add(self.main_vbox)

        # Header bar
        self._create_header()

        # Top row: Sentinel Status + System Telemetry + YOLO
        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        self._create_sentinel_panel(top_row)
        self._create_telemetry_panel(top_row)
        self._create_yolo_panel(top_row)
        self.main_vbox.pack_start(top_row, False, False, 0)

        # Separator
        sep1 = Gtk.Separator()
        self.main_vbox.pack_start(sep1, False, False, 5)

        # Middle row: Thoughts + Vision Model + Camera
        mid_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        self._create_thoughts_panel(mid_row)
        self._create_vision_panel(mid_row)
        self._create_camera_panel(mid_row)
        self.main_vbox.pack_start(mid_row, False, False, 0)

        # Separator
        sep2 = Gtk.Separator()
        self.main_vbox.pack_start(sep2, False, False, 5)

        # Bottom row: Logs + Chat
        bottom_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        self._create_logs_panel(bottom_row)
        self._create_chat_panel(bottom_row)
        self.main_vbox.pack_start(bottom_row, True, True, 0)

        self.maximize()
        self.show_all()
        self._start_threads()

    def _on_draw(self, widget, cr):
        r, g, b, a = COLORS["bg"]
        cr.set_source_rgba(r, g, b, a)
        cr.set_operator(1)
        cr.paint()
        return False

    # ── Header ───────────────────────────────────────────────────

    def _create_header(self):
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        title = Gtk.Label()
        now = datetime.now().strftime("%H:%M:%S")
        title.set_markup(
            f"<span font_desc='Inter Bold 18' foreground='{COLORS['accent_cyan']}'>"
            f"⚔ MAXIMUS DECIMUS MERIDIUS</span>  "
            f"<span font_desc='Inter 12' foreground='{COLORS['text_dim']}'>— COMMAND CENTER</span>"
        )
        title.set_halign(Gtk.Align.START)
        hbox.pack_start(title, False, False, 0)

        self.clock_label = Gtk.Label()
        self.clock_label.set_halign(Gtk.Align.END)
        hbox.pack_end(self.clock_label, False, False, 0)

        self.main_vbox.pack_start(hbox, False, False, 5)

    # ── Sentinel Panel ───────────────────────────────────────────

    def _create_sentinel_panel(self, parent):
        frame = Gtk.Frame()
        frame.set_label_widget(self._make_title("🛡 SENTINEL STATUS", COLORS["accent_green"]))
        frame.set_shadow_type(Gtk.ShadowType.NONE)

        self.sentinel_label = Gtk.Label()
        self.sentinel_label.set_use_markup(True)
        self.sentinel_label.set_halign(Gtk.Align.START)
        self.sentinel_label.set_valign(Gtk.Align.START)
        self.sentinel_label.set_line_wrap(True)
        self.sentinel_label.set_margin_start(10)
        self.sentinel_label.set_margin_end(10)
        self.sentinel_label.set_margin_top(5)
        frame.add(self.sentinel_label)

        parent.pack_start(frame, True, True, 0)

    # ── System Telemetry Panel ───────────────────────────────────

    def _create_telemetry_panel(self, parent):
        frame = Gtk.Frame()
        frame.set_label_widget(self._make_title("⚙ SYSTEM TELEMETRY", COLORS["accent_cyan"]))
        frame.set_shadow_type(Gtk.ShadowType.NONE)

        self.telemetry_label = Gtk.Label()
        self.telemetry_label.set_use_markup(True)
        self.telemetry_label.set_halign(Gtk.Align.START)
        self.telemetry_label.set_valign(Gtk.Align.START)
        self.telemetry_label.set_line_wrap(True)
        self.telemetry_label.set_margin_start(10)
        self.telemetry_label.set_margin_end(10)
        self.telemetry_label.set_margin_top(5)
        frame.add(self.telemetry_label)

        parent.pack_start(frame, True, True, 0)

    # ── YOLO Vision Panel ────────────────────────────────────────

    def _create_yolo_panel(self, parent):
        frame = Gtk.Frame()
        frame.set_label_widget(self._make_title("🔍 YOLO VISION", COLORS["accent_orange"]))
        frame.set_shadow_type(Gtk.ShadowType.NONE)

        self.yolo_label = Gtk.Label()
        self.yolo_label.set_use_markup(True)
        self.yolo_label.set_halign(Gtk.Align.START)
        self.yolo_label.set_valign(Gtk.Align.START)
        self.yolo_label.set_line_wrap(True)
        self.yolo_label.set_margin_start(10)
        self.yolo_label.set_margin_end(10)
        self.yolo_label.set_margin_top(5)
        frame.add(self.yolo_label)

        parent.pack_start(frame, True, True, 0)

    # ── Logs Panel ───────────────────────────────────────────────

    def _create_logs_panel(self, parent):
        frame = Gtk.Frame()
        frame.set_label_widget(self._make_title("🧠 NEURAL PATHWAYS", COLORS["accent_purple"]))
        frame.set_shadow_type(Gtk.ShadowType.NONE)

        self.logs_view = Gtk.TextView()
        self.logs_view.set_editable(False)
        self.logs_view.set_cursor_visible(False)
        self.logs_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.logs_view.override_background_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0, 0, 0, 0))
        self.logs_view.override_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0.7, 0.7, 0.7, 1))
        self.logs_view.override_font(Pango.FontDescription("Monospace 9"))

        self.logs_buffer = self.logs_view.get_buffer()
        self.logs_buffer.create_tag("info", foreground="#AAAAAA")
        self.logs_buffer.create_tag("warn", foreground="#FFAA00")
        self.logs_buffer.create_tag("error", foreground="#FF5555", weight=Pango.Weight.BOLD)
        self.logs_buffer.create_tag("skill", foreground="#55AAFF")

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.logs_view)

        frame.add(scroll)
        parent.pack_start(frame, True, True, 0)

    # ── Chat Panel ───────────────────────────────────────────────

    def _create_chat_panel(self, parent):
        frame = Gtk.Frame()
        frame.set_label_widget(self._make_title("💬 LIVE DIALOGUE", COLORS["text_white"]))
        frame.set_shadow_type(Gtk.ShadowType.NONE)

        self.chat_view = Gtk.TextView()
        self.chat_view.set_editable(False)
        self.chat_view.set_cursor_visible(False)
        self.chat_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.chat_view.override_background_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0, 0, 0, 0))

        self.chat_buffer = self.chat_view.get_buffer()
        self.chat_buffer.create_tag("user", foreground="#00FFCC", font="Inter Bold 12",
                                     pixels_above_lines=10)
        self.chat_buffer.create_tag("max", foreground="#FFFFFF", font="Inter 12")
        self.chat_buffer.create_tag("sys", foreground="#8888AA", font="Inter Italic 10")
        self.chat_buffer.create_tag("tool", foreground="#FFAA55", font="Monospace 10")

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.chat_view)

        frame.add(scroll)
        parent.pack_start(frame, True, True, 0)

    # ── Thoughts Panel (NEW) ───────────────────────────────────

    def _create_thoughts_panel(self, parent):
        frame = Gtk.Frame()
        frame.set_label_widget(self._make_title("🧠 INNER THOUGHTS", COLORS["accent_purple"]))
        frame.set_shadow_type(Gtk.ShadowType.NONE)

        self.thoughts_view = Gtk.TextView()
        self.thoughts_view.set_editable(False)
        self.thoughts_view.set_cursor_visible(False)
        self.thoughts_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.thoughts_view.override_background_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(0, 0, 0, 0))

        self.thoughts_buffer = self.thoughts_view.get_buffer()
        self.thoughts_buffer.create_tag("thought", foreground="#CC99FF", font="Inter 10")
        self.thoughts_buffer.create_tag("category", foreground="#888899", font="Monospace Bold 8")
        self.thoughts_buffer.create_tag("high_speak", foreground="#FFAA55", font="Inter Bold 10")

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.thoughts_view)

        frame.add(scroll)
        parent.pack_start(frame, True, True, 0)

    # ── Vision Model Panel (NEW) ───────────────────────────────

    def _create_vision_panel(self, parent):
        frame = Gtk.Frame()
        frame.set_label_widget(self._make_title("🔮 VISION MODEL", COLORS["accent_cyan"]))
        frame.set_shadow_type(Gtk.ShadowType.NONE)

        self.vision_label = Gtk.Label()
        self.vision_label.set_use_markup(True)
        self.vision_label.set_halign(Gtk.Align.START)
        self.vision_label.set_valign(Gtk.Align.START)
        self.vision_label.set_line_wrap(True)
        self.vision_label.set_max_width_chars(50)
        self.vision_label.set_margin_start(10)
        self.vision_label.set_margin_end(10)
        self.vision_label.set_margin_top(5)
        frame.add(self.vision_label)

        parent.pack_start(frame, True, True, 0)

    # ── Camera Thumbnail Panel (NEW) ───────────────────────────

    def _create_camera_panel(self, parent):
        frame = Gtk.Frame()
        frame.set_label_widget(self._make_title("📷 CAMERA FEED", COLORS["accent_green"]))
        frame.set_shadow_type(Gtk.ShadowType.NONE)

        self.camera_image = Gtk.Image()
        self.camera_image.set_size_request(200, 150)
        frame.add(self.camera_image)

        parent.pack_start(frame, False, False, 0)

    # ── Helpers ──────────────────────────────────────────────────

    def _make_title(self, text, color):
        label = Gtk.Label()
        label.set_markup(f"<span font_desc='Inter Bold 12' foreground='{color}'>{text}</span>")
        return label

    def _append_to_view(self, view, buffer, text, tag, max_lines=300):
        end_iter = buffer.get_end_iter()
        buffer.insert_with_tags_by_name(end_iter, text, tag)
        mark = buffer.get_insert()
        view.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)
        if buffer.get_line_count() > max_lines:
            start = buffer.get_start_iter()
            end = buffer.get_iter_at_line(20)
            buffer.delete(start, end)
        return False

    # ── Background Workers ───────────────────────────────────────

    def _start_threads(self):
        threading.Thread(target=self._run_sentinel_updater, daemon=True).start()
        threading.Thread(target=self._run_clock, daemon=True).start()
        threading.Thread(target=self._tail_journal, daemon=True).start()
        threading.Thread(target=self._tail_chat, daemon=True).start()
        threading.Thread(target=self._run_thoughts_updater, daemon=True).start()
        threading.Thread(target=self._run_camera_updater, daemon=True).start()

    def _run_clock(self):
        while True:
            now = datetime.now().strftime("%H:%M:%S")
            service_status = "UNKNOWN"
            try:
                r = subprocess.run(["systemctl", "--user", "is-active", "jarvis.service"],
                                   capture_output=True, text=True, timeout=2)
                service_status = r.stdout.strip().upper()
            except Exception:
                pass

            status_color = COLORS["status_active"] if service_status == "ACTIVE" else COLORS["status_error"]
            markup = (
                f"<span font_desc='Monospace Bold 14' foreground='{COLORS['accent_cyan']}'>{now}</span>  "
                f"<span font_desc='Inter 11' foreground='{status_color}'>● {service_status}</span>"
            )
            GLib.idle_add(self.clock_label.set_markup, markup)
            time.sleep(1)

    def _run_sentinel_updater(self):
        """Reads sentinel_state.json every 2s and updates sentinel + telemetry + yolo panels."""
        while True:
            try:
                if SENTINEL_STATE.exists():
                    with open(SENTINEL_STATE, "r") as f:
                        state = json.load(f)

                    # ── Sentinel Status Panel ──
                    lines = []
                    for key in ["camera", "yolo", "system", "usb", "self_update"]:
                        s = state.get(key, {})
                        status = s.get("status", "off")
                        err = s.get("error")
                        icon = "●" if status == "active" else "○"
                        color = COLORS["status_active"] if status == "active" else COLORS["status_error"]
                        name = key.replace("_", " ").title()
                        line = f"<span foreground='{color}'>{icon}</span> <b>{name}</b>"
                        if err:
                            line += f"\n  <span foreground='{COLORS['accent_red']}' size='small'>  {err}</span>"
                        elif key == "self_update":
                            actions = s.get("actions", [])
                            if actions:
                                line += f"\n  <span foreground='{COLORS['text_dim']}' size='small'>  {actions[0]}</span>"
                        lines.append(line)

                    last_update = ""
                    sys_data = state.get("system", {}).get("last_check")
                    if sys_data:
                        try:
                            dt = datetime.fromisoformat(sys_data)
                            last_update = dt.strftime("%H:%M:%S")
                        except Exception:
                            pass

                    sentinel_markup = (
                        f"<span font_desc='Monospace 10' foreground='{COLORS['text_primary']}'>"
                        + "\n".join(lines)
                        + f"\n\n<span foreground='{COLORS['text_dim']}'>Last update: {last_update}</span>"
                        + "</span>"
                    )
                    GLib.idle_add(self.sentinel_label.set_markup, sentinel_markup)

                    # ── Telemetry Panel ──
                    sys_info = state.get("system", {}).get("data", {})
                    usb_devs = state.get("usb", {}).get("devices", [])
                    new_usb = state.get("usb", {}).get("new_device")

                    cpu = sys_info.get("cpu", "?")
                    ram = sys_info.get("ram", "?")
                    ram_used = sys_info.get("ram_used_gb", "?")
                    ram_total = sys_info.get("ram_total_gb", "?")
                    disk = sys_info.get("disk_free", "?")
                    temp = sys_info.get("temp", "?")
                    battery = sys_info.get("battery", "?")

                    # CPU color based on usage
                    cpu_color = COLORS["status_active"]
                    try:
                        if float(cpu) > 80:
                            cpu_color = COLORS["accent_red"]
                        elif float(cpu) > 50:
                            cpu_color = COLORS["accent_orange"]
                    except (ValueError, TypeError):
                        pass

                    telemetry_markup = (
                        f"<span font_desc='Monospace 10'>"
                        f"<span foreground='{cpu_color}'>CPU: {cpu}%</span>\n"
                        f"<span foreground='{COLORS['text_primary']}'>RAM: {ram}% ({ram_used}/{ram_total} GB)</span>\n"
                        f"<span foreground='{COLORS['text_primary']}'>Disk: {disk} free</span>\n"
                        f"<span foreground='{COLORS['text_primary']}'>Temp: {temp}</span>\n"
                        f"<span foreground='{COLORS['text_primary']}'>Battery: {battery}</span>\n"
                        f"\n<span foreground='{COLORS['accent_cyan']}'>USB ({len(usb_devs)} devices):</span>\n"
                    )
                    for dev in usb_devs:
                        # Shorten device name
                        short = dev.split(": ID ")[1] if ": ID " in dev else dev
                        short = short[:40]
                        is_new = new_usb and dev == new_usb
                        dev_color = COLORS["accent_green"] if is_new else COLORS["text_dim"]
                        telemetry_markup += f"<span foreground='{dev_color}'>  • {short}</span>\n"

                    telemetry_markup += "</span>"
                    GLib.idle_add(self.telemetry_label.set_markup, telemetry_markup)

                    # ── YOLO Vision Panel ──
                    yolo = state.get("yolo", {})
                    yolo_dets = yolo.get("detections", [])
                    yolo_time = yolo.get("last_scan", "")
                    cam = state.get("camera", {})
                    cam_time = cam.get("last_capture", "")

                    yolo_markup = f"<span font_desc='Monospace 10'>"

                    # Camera status
                    cam_status = cam.get("status", "off")
                    cam_icon = "●" if cam_status == "active" else "○"
                    cam_color = COLORS["status_active"] if cam_status == "active" else COLORS["status_error"]
                    cam_ts = ""
                    try:
                        cam_ts = datetime.fromisoformat(cam_time).strftime("%H:%M:%S")
                    except Exception:
                        pass
                    yolo_markup += f"<span foreground='{cam_color}'>{cam_icon} Camera</span> <span foreground='{COLORS['text_dim']}'>{cam_ts}</span>\n\n"

                    if yolo_dets:
                        yolo_markup += f"<span foreground='{COLORS['accent_orange']}'>{len(yolo_dets)} objects detected:</span>\n"
                        for det in yolo_dets[:10]:
                            obj = det.get("object", "?")
                            conf = det.get("confidence", 0)
                            cx, cy = det.get("center", [0, 0])
                            conf_color = COLORS["accent_green"] if conf > 0.7 else COLORS["accent_orange"]
                            yolo_markup += (
                                f"  <span foreground='{conf_color}'>▸ {obj}</span>"
                                f" <span foreground='{COLORS['text_dim']}'>{conf:.0%} @ ({cx},{cy})</span>\n"
                            )
                    else:
                        yolo_markup += f"<span foreground='{COLORS['text_dim']}'>No objects detected</span>\n"

                    yolo_ts = ""
                    try:
                        yolo_ts = datetime.fromisoformat(yolo_time).strftime("%H:%M:%S")
                    except Exception:
                        pass
                    yolo_markup += f"\n<span foreground='{COLORS['text_dim']}'>Last scan: {yolo_ts}</span>"
                    yolo_markup += "</span>"
                    GLib.idle_add(self.yolo_label.set_markup, yolo_markup)

            except Exception as e:
                pass

            time.sleep(2)

    def _tail_journal(self):
        """Continuously tail systemd service logs."""
        skip = {"JackShm", "jack server", "Cannot connect to server", "__pycache__"}
        cmd = ["journalctl", "--user", "-u", "jarvis.service", "-f", "-n", "40", "-o", "cat"]
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, bufsize=1)
            for line in iter(process.stdout.readline, ""):
                line = line.strip()
                if not line or any(s in line for s in skip):
                    continue

                tag = "info"
                if "ERROR" in line or "Traceback" in line or "CRITICAL" in line:
                    tag = "error"
                elif "WARN" in line:
                    tag = "warn"
                elif "skill" in line.lower() or "Tool:" in line:
                    tag = "skill"

                GLib.idle_add(self._append_to_view, self.logs_view, self.logs_buffer,
                              f"{line}\n", tag)
        except Exception:
            pass

    def _tail_chat(self):
        """Continuously tail the chat log file."""
        time.sleep(2)  # Wait for file creation
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            if not CHAT_LOG.exists():
                CHAT_LOG.touch()

            with open(CHAT_LOG, "r") as f:
                # Start at end of file
                f.seek(0, os.SEEK_END)
                while True:
                    line = f.readline()
                    if not line:
                        time.sleep(0.2)
                        continue
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        parts = line.split("] ", 1)
                        if len(parts) == 2:
                            msg_part = parts[1]
                            src_parts = msg_part.split(": ", 1)
                            if len(src_parts) == 2:
                                src, msg = src_parts[0].strip(), src_parts[1].strip()
                                if src == "USER":
                                    GLib.idle_add(self._append_to_view, self.chat_view,
                                                  self.chat_buffer, f"🎤 You: {msg}\n", "user")
                                elif src == "MAX":
                                    GLib.idle_add(self._append_to_view, self.chat_view,
                                                  self.chat_buffer, f"🤖 Max: {msg}\n", "max")
                                elif src == "TOOL":
                                    GLib.idle_add(self._append_to_view, self.chat_view,
                                                  self.chat_buffer, f"⚡ {msg}\n", "tool")
                                else:
                                    GLib.idle_add(self._append_to_view, self.chat_view,
                                                  self.chat_buffer, f"  {msg}\n", "sys")
                    except Exception:
                        pass
        except Exception:
            pass

    def _run_thoughts_updater(self):
        """Reads thought state and updates the thoughts panel."""
        while True:
            try:
                if SENTINEL_STATE.exists():
                    with open(SENTINEL_STATE, "r") as f:
                        state = json.load(f)

                    thoughts_data = state.get("thoughts", {})
                    recent = thoughts_data.get("recent", [])

                    if recent:
                        def update_thoughts():
                            self.thoughts_buffer.set_text("")  # Clear
                            for t in recent:
                                end = self.thoughts_buffer.get_end_iter()
                                cat = t.get("category", "?")
                                speak = t.get("speak_score", 0)
                                ts = ""
                                try:
                                    ts = datetime.fromisoformat(t.get("timestamp", "")).strftime("%H:%M:%S")
                                except Exception:
                                    pass

                                self.thoughts_buffer.insert_with_tags_by_name(
                                    end, f"[{ts}] [{cat}] ", "category"
                                )
                                end = self.thoughts_buffer.get_end_iter()
                                tag = "high_speak" if speak > 0.6 else "thought"
                                self.thoughts_buffer.insert_with_tags_by_name(
                                    end, f"{t.get('content', '')}\n", tag
                                )
                            return False

                        GLib.idle_add(update_thoughts)

                    # Vision Model panel
                    vision = state.get("vision_model", {})
                    desc = vision.get("last_description", "")
                    v_time = vision.get("last_update", "")
                    v_status = vision.get("status", "off")

                    v_ts = ""
                    try:
                        v_ts = datetime.fromisoformat(v_time).strftime("%H:%M:%S")
                    except Exception:
                        pass

                    if desc:
                        vision_markup = (
                            f"<span font_desc='Monospace 10'>"
                            f"<span foreground='{COLORS['status_active']}'>\u25cf Active</span> "
                            f"<span foreground='{COLORS['text_dim']}'>{v_ts}</span>\n\n"
                            f"<span foreground='{COLORS['text_primary']}'>{desc[:200]}</span>"
                            f"</span>"
                        )
                    else:
                        vision_markup = (
                            f"<span font_desc='Monospace 10' foreground='{COLORS['text_dim']}'>"
                            f"Vision model waiting for analysis...</span>"
                        )
                    GLib.idle_add(self.vision_label.set_markup, vision_markup)

            except Exception:
                pass

            time.sleep(3)

    def _run_camera_updater(self):
        """Updates the camera thumbnail in the dashboard."""
        from gi.repository import GdkPixbuf
        cam_path = str(JARVIS_DIR / "data" / "captures" / "cam_latest.jpg")

        while True:
            try:
                if os.path.exists(cam_path):
                    def update_cam():
                        try:
                            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                                cam_path, 200, 150, True
                            )
                            self.camera_image.set_from_pixbuf(pixbuf)
                        except Exception:
                            pass
                        return False
                    GLib.idle_add(update_cam)
            except Exception:
                pass

            time.sleep(2)


def main():
    GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGINT, Gtk.main_quit)
    GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGTERM, Gtk.main_quit)
    MaximusDashboard()
    Gtk.main()


if __name__ == "__main__":
    main()
