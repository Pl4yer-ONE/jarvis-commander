#!/usr/bin/env python3
"""
Max Overlay Chatbox

A lightweight, transparent, always-on-top GTK window that displays
the live transcript of conversations with Max.
"""

import os
import signal
import sys
import threading
import time
from datetime import datetime

import gi
gi.require_version("Gtk", "3.0")
import pango
from gi.repository import Gtk, Gdk, GLib, Pango


class ChatOverlay(Gtk.Window):
    def __init__(self, log_file: str):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.log_file = log_file
        
        # Window configuration (transparent, unmanaged, top-right)
        self.set_title("Maximus Overlay")
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
        
        # Scrolled window
        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)
        self.scroll.set_min_content_height(400)
        self.scroll.set_min_content_width(350)
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
        self.buffer.create_tag("user", 
                               foreground="#00FFCC",  # Cyan for user
                               font="Inter Bold 12",
                               pixels_above_lines=10)
                               
        self.buffer.create_tag("max", 
                               foreground="#FFFFFF",  # White for Max
                               font="Inter 11")
                               
        self.buffer.create_tag("sys", 
                               foreground="#AAAAAA",  # Gray for system messages
                               font="Inter Italic 10")
                               
        self.buffer.create_tag("error",
                               foreground="#FF5555",
                               font="Inter Bold 11")

        # Start tailing log file
        self._last_size = 0
        self._update_lock = threading.Lock()
        
        # Initialize text
        self._append_text("Maximus Online ⚔️", "sys")
        
        # Position window top right
        self.connect("realize", self._on_realize)
        self.show_all()
        
        # Thread to monitor the log file
        self.monitor_thread = threading.Thread(target=self._tail_log, daemon=True)
        self.monitor_thread.start()

    def _on_draw(self, widget, cr):
        """Paint semi-transparent black background."""
        cr.set_source_rgba(0.05, 0.05, 0.08, 0.65)  # Dark translucent background
        cr.set_operator(1)  # SOURCE
        cr.paint()
        return False

    def _on_realize(self, widget):
        """Position window in the top right corner of the primary monitor."""
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor()
        geometry = monitor.get_geometry()
        
        width = 380
        height = 450
        x = geometry.x + geometry.width - width - 20
        y = geometry.y + 40
        self.move(x, y)
        self.resize(width, height)

    def _append_text(self, text: str, tag_name: str):
        """Thread-safe text append to UI."""
        GLib.idle_add(self._append_text_gui, text + "\n", tag_name)

    def _append_text_gui(self, text: str, tag_name: str):
        """Append text and scroll to bottom."""
        end_iter = self.buffer.get_end_iter()
        self.buffer.insert_with_tags_by_name(end_iter, text, tag_name)
        
        # Auto-scroll
        mark = self.buffer.get_insert()
        self.text_view.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)
        
        # Prune old text if too long
        if self.buffer.get_line_count() > 100:
            start = self.buffer.get_start_iter()
            end = self.buffer.get_iter_at_line(20)
            self.buffer.delete(start, end)
            
        return False

    def _tail_log(self):
        """Monitor the chat log file continuously."""
        if not os.path.exists(self.log_file):
            os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
            with open(self.log_file, "w") as f:
                f.write(f"[{datetime.now().isoformat()}] SYS: Log initialized.\n")

        # Tail logic
        with open(self.log_file, "r") as f:
            # Jump to end initially
            f.seek(0, os.SEEK_END)
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.1)
                    continue
                    
                line = line.strip()
                if not line:
                    continue
                    
                # Parse timestamp and source (Format: [TIMESTAMP] USER: Hello)
                try:
                    parts = line.split("] ", 1)
                    if len(parts) == 2:
                        msg_part = parts[1]
                        src_parts = msg_part.split(": ", 1)
                        if len(src_parts) == 2:
                            src = src_parts[0].strip()
                            msg = src_parts[1].strip()
                            
                            if src == "USER":
                                self._append_text(f"You:\n {msg}", "user")
                            elif src == "MAX":
                                self._append_text(f"Max:\n {msg}", "max")
                            elif "ERROR" in src:
                                self._append_text(f"⚠️ {msg}", "error")
                            else:
                                self._append_text(f"⚔️ {msg}", "sys")
                        else:
                            self._append_text(msg_part, "sys")
                except Exception:
                    self._append_text(line, "sys")


def main():
    log_file = os.path.expanduser("~/.gemini/antigravity/scratch/jarvis/data/chat_log.txt")
    
    # Handle signals gracefully
    GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGINT, Gtk.main_quit)
    GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGTERM, Gtk.main_quit)
    
    app = ChatOverlay(log_file)
    Gtk.main()


if __name__ == "__main__":
    main()
