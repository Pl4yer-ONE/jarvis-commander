#!/usr/bin/env python3
"""
Max System Logs Overlay

A lightweight, transparent, always-on-top GTK window that displays
the live internal processing logs of the Maximus service.
"""

import os
import signal
import sys
import threading
import time
import subprocess
from datetime import datetime

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango


class LogOverlay(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        
        # Window configuration (transparent, unmanaged)
        self.set_title("Maximus Systems")
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_accept_focus(False)
        self.set_can_focus(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        
        # Make transparent
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual and screen.is_composited():
            self.set_visual(visual)
        self.set_app_paintable(True)
        
        # Connect draw event to paint transparent background
        self.connect("draw", self._on_draw)
        
        # Layout container
        self.vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.vbox.set_margin_top(15)
        self.vbox.set_margin_bottom(15)
        self.vbox.set_margin_start(15)
        self.vbox.set_margin_end(15)
        self.add(self.vbox)
        
        # Title
        title = Gtk.Label(label="<span font_desc='Inter Bold 10' foreground='#8888AA'>SYSTEM PROCESSES</span>")
        title.set_use_markup(True)
        title.set_halign(Gtk.Align.START)
        self.vbox.pack_start(title, False, False, 0)
        
        # Scrolled window
        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)
        self.scroll.set_min_content_height(250)
        self.scroll.set_min_content_width(500)
        self.vbox.pack_start(self.scroll, True, True, 0)
        
        # Text view
        self.text_view = Gtk.TextView()
        self.text_view.set_editable(False)
        self.text_view.set_cursor_visible(False)
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        
        # Make text view transparent
        rgba = Gdk.RGBA(0.0, 0.0, 0.0, 0.0)
        self.text_view.override_background_color(Gtk.StateFlags.NORMAL, rgba)
        
        self.buffer = self.text_view.get_buffer()
        self.scroll.add(self.text_view)
        
        # Tags for styling
        self.buffer.create_tag("info", foreground="#AAAAAA", font="Monospace 9")
        self.buffer.create_tag("warn", foreground="#FFAA00", font="Monospace 9")
        self.buffer.create_tag("error", foreground="#FF5555", font="Monospace Bold 9")
        self.buffer.create_tag("brain", foreground="#AA55FF", font="Monospace Bold 9")

        # Position window top left
        self.connect("realize", self._on_realize)
        self.show_all()
        
        # Thread to tail journalctl
        self.monitor_thread = threading.Thread(target=self._tail_journal, daemon=True)
        self.monitor_thread.start()

    def _on_draw(self, widget, cr):
        cr.set_source_rgba(0.05, 0.05, 0.08, 0.5)  # Make logs slightly more transparent
        cr.set_operator(1)
        cr.paint()
        return False

    def _on_realize(self, widget):
        # Position in top left, underneath top bar
        self.move(20, 40)
        self.resize(550, 300)

    def _append_text(self, text: str, tag_name: str = "info"):
        GLib.idle_add(self._append_text_gui, text + "\n", tag_name)

    def _append_text_gui(self, text: str, tag_name: str):
        end_iter = self.buffer.get_end_iter()
        self.buffer.insert_with_tags_by_name(end_iter, text, tag_name)
        
        mark = self.buffer.get_insert()
        self.text_view.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)
        
        if self.buffer.get_line_count() > 80:
            start = self.buffer.get_start_iter()
            end = self.buffer.get_iter_at_line(10)
            self.buffer.delete(start, end)
            
        return False

    def _tail_journal(self):
        """Continuously read from the systemd journal for jarvis.service"""
        cmd = ["journalctl", "--user", "-u", "jarvis.service", "-f", "-n", "10", "-o", "cat"]
        
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            
            for line in iter(process.stdout.readline, ""):
                line = line.strip()
                if not line:
                    continue
                
                # Filter out noisy ALSA errors we couldn't fully suppress
                if "JackShmReadWritePtr" in line or "jack server is not running" in line or "Cannot connect to server" in line:
                    continue
                    
                tag = "info"
                if "ERROR" in line or "Traceback" in line:
                    tag = "error"
                elif "WARN" in line:
                    tag = "warn"
                elif "brain" in line.lower() or "think" in line.lower():
                    tag = "brain"
                    
                self._append_text(line, tag)
                
        except Exception as e:
            self._append_text(f"Log monitor failed: {e}", "error")


def main():
    GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGINT, Gtk.main_quit)
    GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGTERM, Gtk.main_quit)
    
    app = LogOverlay()
    Gtk.main()


if __name__ == "__main__":
    main()
