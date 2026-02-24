"""
Max — Autonomous Thought Engine

A continuous background thread that gives Max an inner monologue.
Observes environment, forms thoughts, plans actions, and decides
independently whether to speak, act, or stay silent.

Publishes thoughts to the event bus for dashboard and free-talk.
"""

import logging
import random
import threading
import time
from datetime import datetime

logger = logging.getLogger("max.thought_engine")

# ── Shared Thought State ─────────────────────────────────────

_THOUGHT_LOCK = threading.Lock()
_THOUGHTS: list[dict] = []
_MAX_THOUGHTS = 100

THOUGHT_CATEGORIES = {
    "observation": 0.7,
    "analysis": 0.4,
    "opinion": 0.8,
    "plan": 0.5,
    "curiosity": 0.9,
    "environmental": 0.6,
    "reflection": 0.3,
    "alert": 1.0,
}


def get_thoughts(count: int = 20) -> list[dict]:
    """Get the most recent thoughts."""
    with _THOUGHT_LOCK:
        return list(_THOUGHTS[-count:])


def get_latest_thought() -> dict | None:
    """Get the most recent thought."""
    with _THOUGHT_LOCK:
        return _THOUGHTS[-1] if _THOUGHTS else None


def get_speakable_thoughts(since_seconds: int = 60) -> list[dict]:
    """Get thoughts worth speaking aloud from the last N seconds."""
    cutoff = datetime.now().timestamp() - since_seconds
    with _THOUGHT_LOCK:
        return [
            t for t in _THOUGHTS
            if t.get("timestamp_epoch", 0) > cutoff
            and t.get("speak_score", 0) > 0.5
            and not t.get("spoken", False)
        ]


def mark_thought_spoken(thought_id: str):
    """Mark a thought as already spoken."""
    with _THOUGHT_LOCK:
        for t in _THOUGHTS:
            if t.get("id") == thought_id:
                t["spoken"] = True
                break


def _add_thought(content: str, category: str = "observation", speak_score: float = 0.5):
    """Add a thought to the shared state."""
    thought = {
        "id": f"t_{datetime.now().strftime('%H%M%S')}_{random.randint(100, 999)}",
        "content": content,
        "category": category,
        "speak_score": min(speak_score, 1.0),
        "timestamp": datetime.now().isoformat(),
        "timestamp_epoch": datetime.now().timestamp(),
        "spoken": False,
    }
    with _THOUGHT_LOCK:
        _THOUGHTS.append(thought)
        while len(_THOUGHTS) > _MAX_THOUGHTS:
            _THOUGHTS.pop(0)
    logger.debug("💭 [%s] %s", category, content[:80])
    return thought


class ThoughtEngine:
    """Continuous background thinking loop for Max."""

    def __init__(self, brain=None, interval: int = 20):
        self.brain = brain
        self.interval = interval
        self._running = False
        self._thread: threading.Thread | None = None
        self._cycle_count = 0
        self._last_context_hash = ""

    def start(self):
        """Start the thought engine."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._think_loop, daemon=True, name="thought-engine",
        )
        self._thread.start()
        logger.info("🧠 Thought Engine started (every %ds)", self.interval)

    def stop(self):
        """Stop the thought engine."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("🧠 Thought Engine stopped.")

    def _think_loop(self):
        """Main thinking loop."""
        time.sleep(5)  # Wait for boot
        while self._running:
            try:
                self._cycle_count += 1
                self._run_thought_cycle()
            except Exception as e:
                logger.error("Thought engine error: %s", e)
                _add_thought(f"Internal error: {e}", category="alert", speak_score=0.2)
            time.sleep(self.interval)

    def _run_thought_cycle(self):
        """Execute one cycle of autonomous thinking."""
        context = self._gather_context()

        if not self.brain:
            return

        # Deduplication — skip if context hasn't changed meaningfully
        ctx_hash = str(hash(str(context.get("sentinel", {}).get("yolo", {}).get("detections", []))))
        if ctx_hash == self._last_context_hash and self._cycle_count % 3 != 0:
            logger.debug("Context unchanged — skipping thought cycle")
            return
        self._last_context_hash = ctx_hash

        self._deep_think(context)

    def _gather_context(self) -> dict:
        """Gather all available context."""
        context = {
            "cycle": self._cycle_count,
            "time": datetime.now().strftime("%H:%M:%S"),
        }

        # Get state from event bus
        try:
            from core.event_bus import get_bus
            bus = get_bus()
            sentinel_state = {}
            for topic in ("sentinel.camera", "sentinel.yolo", "sentinel.system", "sentinel.usb"):
                state = bus.get_state(topic)
                if state:
                    sentinel_state[topic.split(".")[-1]] = state
            context["sentinel"] = sentinel_state
        except Exception:
            pass

        # Recent conversation
        if self.brain and hasattr(self.brain, "conversation_history"):
            context["recent_conversation"] = self.brain.conversation_history[-5:]

        # Recent thoughts (avoid repetition)
        recent = get_thoughts(5)
        context["recent_thoughts"] = [t["content"] for t in recent]

        return context

    def _deep_think(self, context: dict):
        """Use the LLM to generate a deep thought."""
        if not self.brain:
            return

        parts = [
            f"Current time: {context.get('time', '?')}",
            f"Thought cycle #{context.get('cycle', 0)}",
        ]

        sentinel = context.get("sentinel", {})

        # YOLO detections
        yolo = sentinel.get("yolo", {})
        detections = yolo.get("detections", [])
        if detections:
            objs = ", ".join(f"{d['object']}({d['confidence']:.0%})" for d in detections[:8])
            parts.append(f"Camera sees: {objs}")

        # System info
        sys_data = sentinel.get("system", {}).get("data", {})
        if sys_data:
            parts.append(
                f"System: CPU {sys_data.get('cpu', '?')}%, "
                f"RAM {sys_data.get('ram', '?')}%, "
                f"Battery {sys_data.get('battery', '?')}"
            )

        # Recent conversation
        recent_conv = context.get("recent_conversation", [])
        if recent_conv:
            msgs = [f"{m['role']}: {m['content'][:100]}" for m in recent_conv[-3:]]
            parts.append("Recent dialogue:\n" + "\n".join(msgs))

        # Avoid repeats
        recent = context.get("recent_thoughts", [])
        if recent:
            parts.append(f"DO NOT REPEAT: {'; '.join(recent[-3:])}")

        context_str = "\n".join(parts)
        prompt = (
            "[AUTONOMOUS THOUGHT CYCLE]\n"
            "You are Max, thinking freely. Based on context, produce ONE thought.\n"
            "Be raw, genuine, opinionated, curious, or analytical.\n"
            "Category: observation, analysis, opinion, plan, curiosity, environmental, reflection, alert\n"
            "Format:\nCATEGORY: <category>\nSPEAK_SCORE: <0.0-1.0>\nTHOUGHT: <1-2 sentences>\n\n"
            f"Context:\n{context_str}"
        )

        try:
            messages = [
                {"role": "system", "content": self.brain.config.system_prompt},
                {"role": "user", "content": prompt},
            ]
            response = self.brain._chat(messages, tools=[])
            content = response.get("content", "")

            category = "observation"
            speak_score = 0.5
            thought_text = content.strip()

            for line in content.split("\n"):
                line = line.strip()
                if line.upper().startswith("CATEGORY:"):
                    cat = line.split(":", 1)[1].strip().lower()
                    if cat in THOUGHT_CATEGORIES:
                        category = cat
                elif line.upper().startswith("SPEAK_SCORE:"):
                    try:
                        speak_score = float(line.split(":", 1)[1].strip())
                    except ValueError:
                        pass
                elif line.upper().startswith("THOUGHT:"):
                    thought_text = line.split(":", 1)[1].strip()

            if thought_text and len(thought_text) > 5:
                _add_thought(thought_text, category=category, speak_score=speak_score)

        except Exception as e:
            logger.warning("Deep think failed: %s", e)
