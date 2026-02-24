#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗                   ║
║  ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝                   ║
║  ██║███████║██████╔╝██║   ██║██║███████╗                   ║
║  ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║                   ║
║  ██║██║  ██║██║  ██║ ╚████╔╝ ██║███████║                   ║
║  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝                   ║
║                                                              ║
║  Maximus Decimus Meridius — Your AI Commander v3.0          ║
╚══════════════════════════════════════════════════════════════╝

Usage:
    python main.py                  # Interactive mode
    python main.py --always-listen  # Continuous listening
    python main.py --autonomous     # Full autonomous mode
    python main.py --text           # Text-only mode
    python main.py --list-mics      # List microphones
"""

import argparse
import logging
import signal
import sys
import time

from config import load_config
from core.listen import Listener
from core.speak import Speaker
from core.brain import Brain
from core.sentinel import start_sentinel
from core.thought_engine import ThoughtEngine
from core.free_talk import FreeTalkController
from core.camera_feed import CameraFeedWindow
from core.dashboard_server import start_dashboard_server
from core.self_heal import start_self_healer
from core.event_bus import get_bus
from skills import SkillRegistry


# ── Logging ──────────────────────────────────────────────────

def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s │ %(name)-18s │ %(levelname)-7s │ %(message)s",
        datefmt="%H:%M:%S",
    )
    for noisy in ("urllib3", "httpx", "httpcore", "ultralytics", "PIL"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


# ── Banner ───────────────────────────────────────────────────

BANNER = """\033[36m
 ███╗   ███╗ █████╗ ██╗  ██╗██╗███╗   ███╗██╗   ██╗███████╗
 ████╗ ████║██╔══██╗╚██╗██╔╝██║████╗ ████║██║   ██║██╔════╝
 ██╔████╔██║███████║ ╚███╔╝ ██║██╔████╔██║██║   ██║███████╗
 ██║╚██╔╝██║██╔══██║ ██╔██╗ ██║██║╚██╔╝██║██║   ██║╚════██║
 ██║ ╚═╝ ██║██║  ██║██╔╝ ██╗██║██║ ╚═╝ ██║╚██████╔╝███████║
 ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝     ╚═╝ ╚═════╝ ╚══════╝
\033[0m\033[90m  Maximus Decimus Meridius — Your AI Commander v3.0\033[0m
"""


def print_status(config, skill_count: int):
    """Print system status after initialization."""
    model = getattr(config, f"{config.llm_backend.value if hasattr(config.llm_backend, 'value') else config.llm_backend}_model", "N/A")
    stt = "faster-whisper" if config.faster_whisper else "google-api"

    print(f"\033[90m{'─' * 58}\033[0m")
    print(f"  \033[33m⚡ LLM Backend:\033[0m  {config.llm_backend} ({model})")
    print(f"  \033[33m🎤 STT Engine:\033[0m   {stt} ({config.whisper_model})")
    print(f"  \033[33m🔊 TTS Engine:\033[0m   {config.tts_engine}")
    print(f"  \033[33m🔧 Skills:\033[0m       {skill_count} loaded")
    print(f"  \033[33m🛡  Safety:\033[0m      {'⚠ UNSAFE MODE' if config.unsafe_mode else '✅ Protected'}")
    print(f"  \033[33m👁  Sentinel:\033[0m    Camera + YOLO + System + USB + Self-Update")
    print(f"  \033[33m🧠 ThoughtEngine:\033[0m Every {config.thought_interval}s")
    print(f"  \033[33m🗣  Free Talk:\033[0m    {'✅ Enabled' if config.free_talk_enabled else '❌ Disabled'}")
    print(f"  \033[33m📹 Camera Feed:\033[0m  {'✅ Live' if config.camera_feed_enabled else '❌ Disabled'}")
    print(f"  \033[33m🔮 Vision Model:\033[0m {config.vision_model}")
    print(f"  \033[33m🌐 Dashboard:\033[0m    {'✅ http://localhost:' + str(config.dashboard_port) if config.dashboard_enabled else '❌ Disabled'}")
    print(f"  \033[33m📡 Event Bus:\033[0m    ✅ Active (capacity: {config.event_bus_capacity})")
    print(f"\033[90m{'─' * 58}\033[0m")


# ── Sentence Chunking Helper ────────────────────────────────

def stream_and_speak(brain: Brain, speaker: Speaker, user_input: str, label: str = "Max"):
    """
    Stream LLM response, print tokens, and send sentence chunks to TTS.
    Returns the full response text.
    """
    sentence_buffer = ""
    full_response = ""

    print(f"\r  \033[35m🤖 {label}:\033[0m ", end="", flush=True)
    for chunk in brain.think_stream(user_input):
        print(chunk, end="", flush=True)
        full_response += chunk
        sentence_buffer += chunk

        # Flush at sentence boundaries
        if any(p in sentence_buffer for p in [". ", "! ", "? ", "\n"]):
            for p in [". ", "! ", "? ", "\n"]:
                if p in sentence_buffer:
                    parts = sentence_buffer.split(p, 1)
                    sentence = parts[0] + p.strip()
                    speaker.speak(sentence.strip())
                    sentence_buffer = parts[1] if len(parts) > 1 else ""
                    break

    # Flush remaining text
    if sentence_buffer.strip():
        speaker.speak(sentence_buffer.strip())

    print()  # Newline after response
    return full_response


# ── Modes ────────────────────────────────────────────────────

def run_interactive(listener: Listener, speaker: Speaker, brain: Brain, config):
    """Interactive mode: press Enter to speak, type to send text."""
    print("\n\033[32m  Ready!\033[0m Press \033[1mEnter\033[0m to speak, or type a command.")
    print("  Type \033[1m'quit'\033[0m to exit, \033[1m'reset'\033[0m to clear memory.\n")

    while True:
        try:
            user_input = input("\033[36m  ❯ \033[0m").strip()

            if user_input.lower() in ("quit", "exit", "bye", "goodbye"):
                speaker.speak_blocking("Strength and honor. Farewell.")
                break
            elif user_input.lower() == "reset":
                brain.reset_memory()
                print("  \033[90m(Memory cleared)\033[0m")
                continue
            elif user_input == "":
                print("  \033[90m🎤 Listening...\033[0m", end="", flush=True)
                text = listener.listen()
                if not text:
                    print("\r  \033[90m🎤 (nothing detected)\033[0m")
                    continue
                print(f"\r  \033[90m🎤 You:\033[0m \033[1m{text}\033[0m")
                user_input = text

            print("  \033[90m🧠 Thinking...\033[0m", end="", flush=True)
            stream_and_speak(brain, speaker, user_input)
            speaker.wait_until_done()

        except KeyboardInterrupt:
            print("\n")
            speaker.speak_blocking("Strength and honor. Until we meet again.")
            break
        except EOFError:
            break


def run_always_listen(listener: Listener, speaker: Speaker, brain: Brain, config):
    """Continuous listening mode — Max processes ALL spoken input."""
    print(f"\n\033[32m  Always-on mode active.\033[0m Max is listening to everything.")
    print("  Press \033[1mCtrl+C\033[0m to exit.\n")

    # Start background subsystems
    print("  \033[90m🛡️ Starting Sentinel...\033[0m")
    start_sentinel(
        camera_interval=30,
        yolo_interval=0.5,
        system_interval=15,
        usb_interval=10,
        update_interval=300,
    )
    print("  \033[32m🛡️ Sentinel active\033[0m")

    print("  \033[90m🧠 Starting Thought Engine...\033[0m")
    thought_engine = ThoughtEngine(brain=brain, interval=config.thought_interval)
    thought_engine.start()
    print(f"  \033[32m🧠 Thought Engine active (every {config.thought_interval}s)\033[0m")

    if config.camera_feed_enabled:
        print("  \033[90m📹 Starting Camera Feed...\033[0m")
        camera_feed = CameraFeedWindow(width=280, height=210, refresh_ms=500)
        camera_feed.start()
        print("  \033[32m📹 Camera Feed active\033[0m")

    if config.dashboard_enabled:
        print(f"  \033[90m🌐 Starting Dashboard on port {config.dashboard_port}...\033[0m")
        start_dashboard_server(port=config.dashboard_port)
        print(f"  \033[32m🌐 Dashboard live at http://localhost:{config.dashboard_port}\033[0m")

    free_talk = None
    if config.free_talk_enabled:
        print("  \033[90m🗣️ Starting Free Talk...\033[0m")
        free_talk = FreeTalkController(
            speaker=speaker, min_interval=config.free_talk_min_interval,
        )
        free_talk.start()
        print(f"  \033[32m🗣️ Free Talk active (every {config.free_talk_min_interval}s+)\033[0m")

    print("  \033[90m🔧 Starting Self-Healer...\033[0m")
    start_self_healer(brain=brain, speaker=speaker)
    print("  \033[32m🔧 Self-Healer active\033[0m")

    # Startup routine
    brain.perform_startup_routine(speaker)
    time.sleep(0.5)

    idle_count = 0
    last_chat_ts = 0.0

    while True:
        try:
            # 1. Check for dashboard chat input first
            from core.event_bus import get_bus
            chat_state = get_bus().get_state("dashboard.chat_input")
            text = None
            
            if chat_state and chat_state.get("timestamp", 0) > last_chat_ts:
                msg = chat_state["message"]
                text = f"[DASHBOARD] {msg}"
                last_chat_ts = chat_state["timestamp"]
                print(f"\n  \033[90m💻 Dashboard:\033[0m \033[1m{msg}\033[0m")
            
            # 2. If no chat input, use microphone
            if not text:
                if free_talk:
                    free_talk.notify_user_speaking()

                text = listener.listen()

                if free_talk:
                    free_talk.notify_user_done()

            # Autonomous idle engagement
            if not text:
                idle_count += 1
                if idle_count >= 3:
                    idle_count = 0
                    print("\n  \033[90m⚙️ [Autonomous Protocol]\033[0m")
                    text = (
                        "[SYSTEM: 15s silence. Act autonomously — diagnostics, logs, "
                        "code, self-improve, narrate observations, or share a thought.]"
                    )
                else:
                    continue
            else:
                idle_count = 0
                if free_talk:
                    free_talk.pause()

            text_lower = text.lower().strip()

            # Skip noise
            if len(text_lower) < 3:
                continue

            # Enforce wake word ("hey max") on actual user speech
            if not text.startswith("[SYSTEM:") and not text.startswith("[DASHBOARD]"):
                import re
                # Clean punctuation to match "Hey, Max.", "Hey Max!", etc.
                text_clean = re.sub(r'[^\w\s]', '', text_lower)
                if "hey max" not in text_clean:
                    continue

            # Skip self-echo
            skip_phrases = [
                "maximus", "decimus", "meridius", "fully operational",
                "this machine is mine", "strength and honor",
            ]
            if any(phrase in text_lower for phrase in skip_phrases):
                continue

            # Exit commands
            if any(w in text_lower for w in ["goodbye max", "shutdown max", "exit max", "sleep max"]):
                speaker.speak_blocking("Strength and honor. Until we meet again.")
                break

            print(f"  \033[90m🎤 You:\033[0m \033[1m{text}\033[0m")
            print("  \033[90m🧠 Thinking...\033[0m", end="", flush=True)

            stream_and_speak(brain, speaker, text)

            speaker.wait_until_done()
            time.sleep(0.3)

            if free_talk:
                free_talk.resume()

        except KeyboardInterrupt:
            print("\n")
            thought_engine.stop()
            if free_talk:
                free_talk.stop()
            speaker.speak_blocking("Strength and honor. Farewell.")
            break


def run_text_mode(brain: Brain):
    """Text-only mode: no microphone or speaker."""
    print("\n\033[32m  Text mode active.\033[0m Type your commands.")
    print("  Type \033[1m'quit'\033[0m to exit, \033[1m'reset'\033[0m to clear memory.\n")

    while True:
        try:
            user_input = input("\033[36m  You ❯ \033[0m").strip()

            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "bye"):
                print("  \033[35m🤖 Max:\033[0m Strength and honor. Farewell.")
                break
            if user_input.lower() == "reset":
                brain.reset_memory()
                print("  \033[90m(Memory cleared)\033[0m")
                continue

            print("  \033[90m🧠 Thinking...\033[0m", end="", flush=True)

            full = ""
            print(f"\r  \033[35m🤖 Max:\033[0m ", end="", flush=True)
            for chunk in brain.think_stream(user_input):
                print(chunk, end="", flush=True)
                full += chunk
            print()

        except (KeyboardInterrupt, EOFError):
            print("\n  \033[35m🤖 Max:\033[0m Farewell.")
            break


# ── Entry Point ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Max — Maximus Decimus Meridius, Your AI Commander v3.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--always-listen", action="store_true", help="Continuous listening mode.")
    parser.add_argument("--text", action="store_true", help="Text-only mode.")
    parser.add_argument("--list-mics", action="store_true", help="List microphones and exit.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging.")
    parser.add_argument("--autonomous", action="store_true", help="Full autonomous mode.")
    args = parser.parse_args()

    if args.autonomous:
        args.always_listen = True

    setup_logging(verbose=args.verbose)
    logger = logging.getLogger("max.main")

    print(BANNER)

    # List mics
    if args.list_mics:
        print("  Available microphones:")
        try:
            for i, name in enumerate(Listener.list_microphones()):
                print(f"    [{i}] {name}")
        except Exception as e:
            print(f"    Error: {e}")
        return

    # Load config
    print("  \033[90mLoading configuration...\033[0m")
    config = load_config()

    # Initialize event bus
    bus = get_bus()
    logger.info("Event bus initialized (capacity: %d)", config.event_bus_capacity)

    # Discover skills
    print("  \033[90mDiscovering skills...\033[0m")
    skill_registry = SkillRegistry()
    skill_registry.discover()
    skills = skill_registry.list_skills()
    logger.info("Loaded %d skills", len(skills))

    # Initialize brain
    print("  \033[90mConnecting to LLM...\033[0m")
    brain = Brain(config, skill_registry)
    try:
        brain.initialize()
    except RuntimeError as e:
        print(f"\n  \033[31m✗ Brain init failed:\033[0m {e}")
        print("  \033[90mTip: Run --text mode while fixing LLM.\033[0m")
        if not args.text:
            return

    # Text mode
    if args.text:
        print_status(config, len(skills))
        run_text_mode(brain)
        return

    # Initialize speaker
    print("  \033[90mInitializing speaker...\033[0m")
    speaker = Speaker(config)
    speaker.initialize()

    # Initialize listener
    print("  \033[90mInitializing microphone...\033[0m")
    listener = Listener(config)
    try:
        listener.calibrate()
    except RuntimeError as e:
        print(f"\n  \033[31m✗ Mic error:\033[0m {e}")
        print("  \033[90mFalling back to text mode...\033[0m")
        print_status(config, len(skills))
        run_text_mode(brain)
        return

    print_status(config, len(skills))

    # Graceful shutdown
    def signal_handler(sig, frame):
        print("\n  \033[90mShutting down...\033[0m")
        speaker.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Startup greeting
    speaker.speak("Maximus Decimus Meridius, online and at full strength. What is your command?")

    try:
        if args.always_listen:
            run_always_listen(listener, speaker, brain, config)
        else:
            run_interactive(listener, speaker, brain, config)
    finally:
        speaker.shutdown()
        print("  \033[90mMax offline.\033[0m\n")


if __name__ == "__main__":
    main()
