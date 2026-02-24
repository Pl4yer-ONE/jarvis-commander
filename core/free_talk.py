"""
Max — Free Talk Controller

Autonomous speech system that allows Max to speak his thoughts freely.
Subscribes to the thought engine, filters by speakability, manages
interruption when the user speaks, and throttles to avoid overwhelming.
"""

import logging
import threading
import time

logger = logging.getLogger("max.free_talk")


class FreeTalkController:
    """Controls Max's autonomous speech output."""

    def __init__(self, speaker=None, min_interval: int = 30):
        self.speaker = speaker
        self.min_interval = min_interval
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_spoke = 0.0
        self._user_speaking = False
        self._paused = False

    def start(self):
        """Start the free talk controller."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._talk_loop, daemon=True, name="free-talk",
        )
        self._thread.start()
        logger.info("🗣️ Free Talk started (min interval: %ds)", self.min_interval)

    def stop(self):
        """Stop the free talk controller."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("🗣️ Free Talk stopped.")

    def pause(self):
        """Temporarily pause free talking."""
        self._paused = True

    def resume(self):
        """Resume free talking."""
        self._paused = False

    def notify_user_speaking(self):
        """Signal that the user has started speaking."""
        self._user_speaking = True
        if self.speaker and hasattr(self.speaker, "interrupt"):
            self.speaker.interrupt()

    def notify_user_done(self):
        """Signal that the user has finished speaking."""
        self._user_speaking = False

    def _talk_loop(self):
        """Main loop — checks for speakable thoughts."""
        time.sleep(10)  # Wait for initialization

        while self._running:
            try:
                if self._paused or self._user_speaking:
                    time.sleep(2)
                    continue

                # Throttle
                if time.time() - self._last_spoke < self.min_interval:
                    time.sleep(3)
                    continue

                # Get speakable thoughts
                from core.thought_engine import get_speakable_thoughts, mark_thought_spoken

                thoughts = get_speakable_thoughts(since_seconds=self.min_interval + 10)
                if not thoughts:
                    time.sleep(5)
                    continue

                # Pick the highest scoring thought
                best = max(thoughts, key=lambda t: t.get("speak_score", 0))

                if self._user_speaking:
                    continue

                content = best.get("content", "")
                if not content:
                    continue

                logger.info("🗣️ Speaking: %s", content[:80])

                try:
                    from core.memory import log_chat
                    log_chat("MAX_THOUGHT", content)
                except Exception:
                    pass

                if self.speaker:
                    self.speaker.speak_blocking(content)
                mark_thought_spoken(best["id"])
                self._last_spoke = time.time()

            except Exception as e:
                logger.error("Free talk error: %s", e)
                time.sleep(5)

            time.sleep(3)

    @property
    def is_active(self) -> bool:
        return self._running and not self._paused
