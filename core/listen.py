"""
Max — Ears Module (Speech-to-Text)

Captures audio from the microphone and converts it to text.
Primary: faster-whisper (CTranslate2 — 4x faster than openai-whisper, same accuracy)
Fallback: Google Speech Recognition API (free, no key)

All heavy I/O is designed to be run via asyncio.to_thread() from the main loop.
"""

import logging
import tempfile
import speech_recognition as sr

# Suppress ALSA error messages from PyAudio at module load
try:
    from ctypes import cdll, CFUNCTYPE, c_char_p, c_int
    _ERROR_HANDLER = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)(
        lambda *_: None
    )
    cdll.LoadLibrary("libasound.so.2").snd_lib_error_set_handler(_ERROR_HANDLER)
except Exception:
    pass

logger = logging.getLogger("max.listen")


class Listener:
    """Handles microphone input and speech-to-text conversion."""

    def __init__(self, config):
        self.config = config
        self.recognizer = sr.Recognizer()
        self._whisper_model = None
        self._mic = None
        self._use_faster_whisper = getattr(config, "faster_whisper", True)

        # Tune recognizer for snappy responsiveness
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.energy_threshold = 300
        self.recognizer.pause_threshold = 0.35
        self.recognizer.non_speaking_duration = 0.25

    # ── Microphone Setup ─────────────────────────────────────

    def _get_microphone(self) -> sr.Microphone:
        """Get or create a Microphone instance with error handling."""
        if self._mic is None:
            try:
                self._mic = sr.Microphone()
                logger.info("Microphone initialized successfully.")
            except OSError as e:
                raise RuntimeError(
                    f"No microphone found. Install portaudio19-dev and connect a mic. Error: {e}"
                ) from e
        return self._mic

    def calibrate(self):
        """Adjust for ambient noise. Call once at startup."""
        mic = self._get_microphone()
        logger.info("Calibrating for ambient noise (2s)...")
        try:
            with mic as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=2)
            logger.info("Calibration complete. Threshold: %.0f", self.recognizer.energy_threshold)
        except OSError as e:
            logger.warning("Calibration failed: %s", e)

    # ── Whisper Model Loading ────────────────────────────────

    def _get_whisper_model(self):
        """Lazy-load the Whisper model."""
        if self._whisper_model is not None:
            return self._whisper_model

        if self._use_faster_whisper:
            return self._load_faster_whisper()
        return None

    def _load_faster_whisper(self):
        """Load faster-whisper (CTranslate2-based, 4x faster)."""
        try:
            from faster_whisper import WhisperModel

            model_name = self.config.whisper_model
            logger.info("Loading faster-whisper '%s' (int8 CPU)...", model_name)
            self._whisper_model = WhisperModel(
                model_name,
                device="cpu",
                compute_type="int8",
                cpu_threads=4,
            )
            logger.info("faster-whisper '%s' loaded.", model_name)
            return self._whisper_model
        except ImportError:
            logger.warning("faster-whisper not installed. Using Google Speech API.")
            self._use_faster_whisper = False
            return None
        except Exception as e:
            logger.error("Failed to load faster-whisper: %s", e)
            self._use_faster_whisper = False
            return None

    # ── Transcription Engines ────────────────────────────────

    def _transcribe_whisper(self, audio: sr.AudioData) -> str | None:
        """Transcribe audio using faster-whisper."""
        model = self._get_whisper_model()
        if model is None:
            return None

        try:
            wav_bytes = audio.get_wav_data(convert_rate=16000, convert_width=2)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
                tmp.write(wav_bytes)
                tmp.flush()

                segments, info = model.transcribe(
                    tmp.name,
                    beam_size=1,
                    best_of=1,
                    vad_filter=False,
                    language=None,  # Auto-detect (English + Malayalam)
                    condition_on_previous_text=False,
                )

                texts = [seg.text.strip() for seg in segments if seg.text.strip()]
                full_text = " ".join(texts).strip()

                if full_text:
                    logger.debug(
                        "faster-whisper lang=%s prob=%.2f",
                        info.language,
                        info.language_probability,
                    )
                return full_text or None

        except Exception as e:
            logger.error("faster-whisper transcription failed: %s", e)
            return None

    def _transcribe_google(self, audio: sr.AudioData) -> str | None:
        """Transcribe using Google's free Speech Recognition API."""
        try:
            text = self.recognizer.recognize_google(audio)
            return text.strip() if text else None
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            logger.error("Google Speech API error: %s", e)
            return None

    # ── Public API ───────────────────────────────────────────

    def listen(self) -> str | None:
        """
        Listen for speech and return transcribed text.
        Returns None if no speech detected. This is a blocking call —
        run via asyncio.to_thread() in the async main loop.
        """
        mic = self._get_microphone()

        try:
            with mic as source:
                audio = self.recognizer.listen(
                    source,
                    timeout=self.config.listen_timeout,
                    phrase_time_limit=self.config.phrase_time_limit,
                )
        except sr.WaitTimeoutError:
            return None
        except OSError as e:
            logger.error("Microphone error: %s", e)
            # Try to reconnect
            self._mic = None
            return None

        # Try faster-whisper first
        text = self._transcribe_whisper(audio)
        if text:
            logger.info("[faster-whisper] %s", text)
            return text

        # Fallback to Google
        text = self._transcribe_google(audio)
        if text:
            logger.info("[Google] %s", text)
            return text

        return None

    @staticmethod
    def list_microphones() -> list[str]:
        """List available microphone device names."""
        return sr.Microphone.list_microphone_names()
