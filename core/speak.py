"""
Max — Voice Module (Text-to-Speech)

Converts text responses to spoken audio output.
Primary: Edge-TTS (Microsoft neural voices — deep male voice)
Fallback: espeak subprocess

Uses a single persistent asyncio event loop for Edge-TTS generation
to avoid the overhead of creating a new loop per call.
"""

import asyncio
import logging
import os
import queue
import subprocess
import tempfile
import threading

logger = logging.getLogger("max.speak")

# Deep male English voices (ranked by preference)
MALE_VOICES = [
    "en-US-GuyNeural",
    "en-GB-RyanNeural",
    "en-US-ChristopherNeural",
    "en-AU-WilliamNeural",
    "en-US-EricNeural",
]


class Speaker:
    """Handles text-to-speech output with thread-safe queuing."""

    def __init__(self, config):
        self.config = config
        self._speech_queue: queue.Queue[str | None] = queue.Queue()
        self._worker_thread: threading.Thread | None = None
        self._running = False
        self._voice = MALE_VOICES[0]
        self._use_edge_tts = False
        self._currently_speaking = False
        self._interrupt_flag = False
        self._audio_player: str = "mpv"
        # Persistent event loop for Edge-TTS async operations
        self._tts_loop: asyncio.AbstractEventLoop | None = None
        self._tts_loop_thread: threading.Thread | None = None

    # ── Engine Initialization ────────────────────────────────

    def _init_edge_tts(self) -> bool:
        """Check that edge-tts is available and find an audio player."""
        try:
            import edge_tts  # noqa: F401
            for player in ("mpv", "ffplay", "play", "paplay"):
                if self._which(player):
                    self._audio_player = player
                    logger.info("Edge-TTS ready — voice: %s, player: %s", self._voice, player)
                    return True
            logger.warning("No audio player found for Edge-TTS.")
            return False
        except ImportError:
            logger.warning("edge-tts not installed.")
            return False

    def _start_tts_loop(self):
        """Start a persistent asyncio event loop for Edge-TTS in a background thread."""
        self._tts_loop = asyncio.new_event_loop()

        def _run_loop():
            asyncio.set_event_loop(self._tts_loop)
            self._tts_loop.run_forever()

        self._tts_loop_thread = threading.Thread(
            target=_run_loop, daemon=True, name="tts-event-loop"
        )
        self._tts_loop_thread.start()

    @staticmethod
    def _which(cmd: str) -> bool:
        """Check if a command exists on PATH."""
        try:
            return subprocess.run(
                ["which", cmd], capture_output=True, timeout=3
            ).returncode == 0
        except Exception:
            return False

    # ── TTS Generation ───────────────────────────────────────

    def _speak_edge_tts(self, text: str):
        """Speak using Edge-TTS with a persistent event loop."""
        try:
            import edge_tts
            import re

            # Detect Malayalam script
            is_malayalam = bool(re.search(r"[\u0D00-\u0D7F]", text))
            voice = "ml-IN-MidhunNeural" if is_malayalam else self._voice

            async def _generate() -> str:
                communicate = edge_tts.Communicate(text, voice)
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    temp_path = f.name
                await communicate.save(temp_path)
                return temp_path

            # Run in the persistent TTS event loop
            future = asyncio.run_coroutine_threadsafe(_generate(), self._tts_loop)
            temp_path = future.result(timeout=30)

            if self._interrupt_flag:
                self._cleanup_tempfile(temp_path)
                return

            self._play_audio(temp_path)

        except Exception as e:
            logger.warning("Edge-TTS failed, falling back to espeak: %s", e)
            self._speak_espeak(text)

    def _play_audio(self, filepath: str):
        """Play an audio file with the configured player."""
        try:
            player = self._audio_player
            cmd_map = {
                "mpv": ["mpv", "--no-video", "--really-quiet", filepath],
                "ffplay": ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", filepath],
                "play": ["play", "-q", filepath],
            }
            cmd = cmd_map.get(player, [player, filepath])
            subprocess.run(cmd, check=True, capture_output=True, timeout=60)
        finally:
            self._cleanup_tempfile(filepath)

    @staticmethod
    def _cleanup_tempfile(path: str):
        """Remove a temp file silently."""
        try:
            os.unlink(path)
        except OSError:
            pass

    def _speak_espeak(self, text: str):
        """Fallback: speak using espeak subprocess."""
        try:
            subprocess.run(
                [
                    "espeak",
                    "-s", str(self.config.tts_rate),
                    "-a", str(int(self.config.tts_volume * 200)),
                    text,
                ],
                check=True,
                capture_output=True,
                timeout=30,
            )
        except FileNotFoundError:
            logger.error("espeak not found. Install: sudo apt install espeak")
        except subprocess.CalledProcessError as e:
            logger.error("espeak failed: %s", e)

    # ── Speech Worker ────────────────────────────────────────

    def _speech_worker(self):
        """Background worker that processes the speech queue sequentially."""
        while self._running:
            try:
                text = self._speech_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            if text is None:  # Poison pill
                break

            self._speak_sync(text)
            self._speech_queue.task_done()

    def _speak_sync(self, text: str):
        """Speak text synchronously (blocking)."""
        if not text or not text.strip():
            return

        # Truncate very long responses
        if len(text) > 500:
            text = text[:500] + "... and more."

        logger.debug("Speaking: %s", text[:80] + ("..." if len(text) > 80 else ""))
        self._currently_speaking = True
        self._interrupt_flag = False
        try:
            if self._use_edge_tts:
                self._speak_edge_tts(text)
            else:
                self._speak_espeak(text)
        finally:
            self._currently_speaking = False
            self._interrupt_flag = False

    # ── Public API ───────────────────────────────────────────

    def initialize(self):
        """Initialize the TTS engine and start workers."""
        if self._init_edge_tts():
            self._use_edge_tts = True
            self._start_tts_loop()
            logger.info("Using Edge-TTS (neural voice).")
        else:
            self._use_edge_tts = False
            logger.info("Using espeak for speech.")

        self._running = True
        self._worker_thread = threading.Thread(
            target=self._speech_worker, daemon=True, name="max-speaker"
        )
        self._worker_thread.start()
        logger.info("Speaker initialized.")

    def speak(self, text: str):
        """Queue text for speech output (non-blocking)."""
        if text and text.strip():
            self._speech_queue.put(text.strip())

    def speak_blocking(self, text: str):
        """Speak text immediately, blocking until done."""
        self._speak_sync(text)

    def wait_until_done(self):
        """Block until all queued speech has been spoken."""
        self._speech_queue.join()

    def cancel_all(self):
        """Cancel all pending speech and interrupt current playback."""
        # Drain the queue
        while not self._speech_queue.empty():
            try:
                self._speech_queue.get_nowait()
                self._speech_queue.task_done()
            except queue.Empty:
                break
        self.interrupt()

    def interrupt(self):
        """Interrupt current speech by killing audio processes."""
        self._interrupt_flag = True
        try:
            for proc in ("mpv", "ffplay", "play", "paplay", "espeak"):
                subprocess.run(["pkill", "-f", proc], capture_output=True, timeout=2)
        except Exception:
            pass
        logger.debug("Speech interrupted.")

    def shutdown(self):
        """Stop the speech worker and TTS loop."""
        self._running = False
        self._speech_queue.put(None)
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)
        if self._tts_loop:
            self._tts_loop.call_soon_threadsafe(self._tts_loop.stop)
        logger.info("Speaker shut down.")

    @property
    def is_speaking(self) -> bool:
        """Whether speech is currently playing."""
        return self._currently_speaking
