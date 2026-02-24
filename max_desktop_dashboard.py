#!/usr/bin/env python3
"""
Max — Native Desktop Dashboard

Launches the MAXIMUS COMMAND CENTER as a native desktop window
using pywebview (no browser needed). The FastAPI server runs in
the background and the dashboard renders in a native GTK/WebKit window.

Usage:
    python max_desktop_dashboard.py              # Normal windowed mode
    python max_desktop_dashboard.py --wallpaper  # Fullscreen wallpaper mode
    python max_desktop_dashboard.py --frameless  # Borderless window
"""

import argparse
import os
import sys
import time
import threading
import logging

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("max.desktop")


def main():
    parser = argparse.ArgumentParser(description="MAXIMUS Desktop Dashboard")
    parser.add_argument("--wallpaper", action="store_true",
                        help="Run as fullscreen desktop wallpaper")
    parser.add_argument("--frameless", action="store_true",
                        help="Run as a borderless window")
    parser.add_argument("--port", type=int, default=7777,
                        help="Dashboard server port (default: 7777)")
    parser.add_argument("--width", type=int, default=1280,
                        help="Window width (default: 1280)")
    parser.add_argument("--height", type=int, default=800,
                        help="Window height (default: 800)")
    parser.add_argument("--on-top", action="store_true",
                        help="Keep window always on top")
    args = parser.parse_args()

    # ── Start the FastAPI backend server ──
    from core.dashboard_server import start_dashboard_server
    logger.info("Starting dashboard server on port %d...", args.port)
    start_dashboard_server(port=args.port)
    
    # Wait for server to bind to port
    import socket
    startup_wait = 0
    while startup_wait < 10.0:
        try:
            with socket.create_connection(("127.0.0.1", args.port), timeout=1.0):
                break
        except (ConnectionRefusedError, OSError, socket.timeout):
            time.sleep(0.5)
            startup_wait += 0.5
            
    if startup_wait >= 10.0:
        logger.error("Timed out waiting for dashboard server to start.")

    # ── Launch native window with pywebview ──
    import webview

    url = f"http://127.0.0.1:{args.port}"

    window = webview.create_window(
        title="MAXIMUS COMMAND CENTER",
        url=url,
        width=args.width,
        height=args.height,
        resizable=True,
        frameless=args.frameless or args.wallpaper,
        easy_drag=not args.wallpaper,
        fullscreen=args.wallpaper,
        on_top=args.on_top,
        background_color="#060a14",
        text_select=False,
    )

    logger.info("🖥  MAXIMUS Desktop Dashboard launching...")
    logger.info("   Mode: %s", "wallpaper" if args.wallpaper else "frameless" if args.frameless else "windowed")
    logger.info("   Size: %dx%d", args.width, args.height)
    logger.info("   URL:  %s", url)

    # Make dashboard sticky across all workspaces
    def make_sticky():
        time.sleep(3)
        os.system('wmctrl -r "MAXIMUS COMMAND CENTER" -b add,sticky')
        logger.info("Pinned dashboard to all workspaces.")
    
    threading.Thread(target=make_sticky, daemon=True).start()

    # Start the GUI event loop (blocks until window is closed)
    webview.start(
        gui="gtk",          # Use GTK backend on Linux
        debug=False,
    )


if __name__ == "__main__":
    main()
