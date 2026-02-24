"""
Max — Camera Feed Monitor (Headless)

Monitors camera frame availability from the Sentinel camera thread.
Visual display is handled by the web dashboard.
This module is kept for backward compatibility but the main camera
work is done in sentinel.py.
"""

import logging
import threading
import time
from pathlib import Path

logger = logging.getLogger("max.camera_feed")

DATA_DIR = Path(__file__).parent.parent / "data" / "captures"


class CameraFeedWindow:
    """Camera feed monitor — headless mode."""

    def __init__(self, width: int = 280, height: int = 210, refresh_ms: int = 500):
        self.width = width
        self.height = height
        self.refresh_ms = refresh_ms
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run_feed, daemon=True, name="camera-feed",
        )
        self._thread.start()
        logger.info("📹 Camera feed monitor started (%dx%d)", self.width, self.height)

    def stop(self):
        self._running = False

    def _run_feed(self):
        """Monitor camera feed availability."""
        cam_path = DATA_DIR / "cam_latest.jpg"
        last_mtime = 0.0
        frame_count = 0

        while self._running:
            try:
                if cam_path.exists():
                    mtime = cam_path.stat().st_mtime
                    if mtime != last_mtime:
                        frame_count += 1
                        last_mtime = mtime
                        if frame_count % 20 == 0:
                            logger.debug("📹 Frame %d available", frame_count)
            except Exception as e:
                logger.debug("Camera feed monitor error: %s", e)
            time.sleep(self.refresh_ms / 1000.0)

        logger.info("📹 Camera feed monitor stopped.")
