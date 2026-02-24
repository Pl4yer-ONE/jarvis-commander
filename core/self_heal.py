"""
Max — Self-Healing Module

Monitors Max's health, detects errors, and uses the Brain (LLM) to
reason about and fix problems autonomously.

Capabilities:
  - Detect crashed threads/services and restart them
  - Read error logs and use LLM to diagnose + fix
  - Auto-install missing dependencies
  - Fix broken configs
  - Report unresolvable issues via speech
"""

import json
import logging
import os
import re
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("max.self_heal")

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
HEAL_LOG = DATA_DIR / "self_heal_log.json"

ERROR_PATTERNS = [
    (r"ModuleNotFoundError: No module named '(\w+)'", "missing_module"),
    (r"ImportError: (.+)", "import_error"),
    (r"ConnectionRefusedError", "connection_error"),
    (r"FileNotFoundError: .+?'(.+?)'", "missing_file"),
    (r"PermissionError", "permission_error"),
    (r"OSError: \[Errno 98\] .+ address already in use", "port_conflict"),
    (r"CUDA out of memory", "memory_error"),
    (r"ollama.*connection refused", "ollama_down"),
]


class SelfHealer:
    """Autonomous self-healing system for Max."""

    def __init__(self, brain=None, speaker=None):
        self.brain = brain
        self.speaker = speaker
        self._running = False
        self._thread = None
        self._error_history: list[dict] = []
        self._fixes_applied: list[dict] = []
        self._check_interval = 30
        self._cooldown: dict[str, float] = {}  # err_key -> last_attempt_time

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._heal_loop, daemon=True, name="self-healer",
        )
        self._thread.start()
        logger.info("🔧 Self-Healer started")

    def stop(self):
        self._running = False

    def _heal_loop(self):
        while self._running:
            try:
                problems = self._detect_problems()
                for problem in problems:
                    err_key = f"{problem['type']}:{problem.get('error', '')[:60]}"

                    # Cooldown: don't spam-fix the same error
                    last_attempt = self._cooldown.get(err_key, 0)
                    if time.time() - last_attempt < 300:  # 5min cooldown
                        continue
                    self._cooldown[err_key] = time.time()

                    try:
                        self._attempt_fix(problem)
                    except Exception as e:
                        logger.error("Fix attempt failed for %s: %s", problem["type"], e)
            except Exception as e:
                logger.error("Self-heal loop error: %s", e)

            time.sleep(self._check_interval)

    def _detect_problems(self) -> list[dict]:
        problems = []
        problems.extend(self._check_sentinel())
        problems.extend(self._check_logs())
        problems.extend(self._check_ollama())
        return problems

    def _check_sentinel(self) -> list[dict]:
        """Check sentinel state from event bus for errors."""
        problems = []
        try:
            from core.event_bus import get_bus
            bus = get_bus()
            for topic in ("sentinel.camera", "sentinel.yolo", "sentinel.system"):
                state = bus.get_state(topic)
                if state and state.get("error"):
                    err = state["error"]
                    if "Restarting after crash" not in str(err):
                        problems.append({
                            "type": "sentinel_error",
                            "module": topic.split(".")[-1],
                            "error": str(err),
                            "severity": "medium",
                        })
        except Exception:
            pass
        return problems

    def _check_logs(self) -> list[dict]:
        problems = []
        try:
            log_file = Path("/tmp/max_autonomous.log")
            if log_file.exists():
                with open(log_file) as f:
                    lines = f.readlines()[-50:]
                for line in lines:
                    for pattern, err_type in ERROR_PATTERNS:
                        match = re.search(pattern, line, re.IGNORECASE)
                        if match:
                            err_key = f"{err_type}:{match.group(0)[:60]}"
                            if err_key not in [e.get("key") for e in self._error_history[-20:]]:
                                problem = {
                                    "type": err_type,
                                    "error": match.group(0),
                                    "detail": match.groups(),
                                    "key": err_key,
                                    "severity": "high" if err_type in ("ollama_down", "missing_module") else "medium",
                                }
                                problems.append(problem)
                                self._error_history.append(problem)
        except Exception:
            pass
        return problems

    def _check_ollama(self) -> list[dict]:
        problems = []
        try:
            import requests
            r = requests.get("http://localhost:11434/api/tags", timeout=3)
            if r.status_code != 200:
                problems.append({
                    "type": "ollama_down",
                    "error": f"Ollama returned {r.status_code}",
                    "severity": "critical",
                })
        except Exception:
            problems.append({
                "type": "ollama_down",
                "error": "Cannot connect to Ollama",
                "severity": "critical",
            })
        return problems

    def _attempt_fix(self, problem: dict):
        ptype = problem["type"]
        logger.info("🔧 Healing: %s — %s", ptype, problem.get("error", "")[:80])

        fixed = False
        if ptype == "missing_module":
            fixed = self._fix_missing_module(problem)
        elif ptype == "ollama_down":
            fixed = self._fix_ollama()
        elif ptype == "port_conflict":
            fixed = self._fix_port_conflict()
        elif ptype == "connection_error":
            fixed = self._fix_connection()
        elif ptype == "sentinel_error":
            logger.info("  Sentinel crash recovery handles: %s", problem.get("module"))
            fixed = True
        else:
            fixed = self._fix_with_brain(problem)

        status = "auto-fixed" if fixed else "unfixed"
        self._log_fix(problem, status)
        if fixed:
            logger.info("  ✅ Fixed: %s", ptype)
        else:
            self._notify_user(problem)

    def _fix_missing_module(self, problem: dict) -> bool:
        detail = problem.get("detail", ())
        if detail:
            module = detail[0] if isinstance(detail, tuple) else str(detail)
            try:
                venv_pip = str(PROJECT_ROOT / "venv" / "bin" / "pip")
                result = subprocess.run(
                    [venv_pip, "install", module],
                    capture_output=True, text=True, timeout=120,
                )
                return result.returncode == 0
            except Exception as e:
                logger.error("Module install error: %s", e)
        return False

    def _fix_ollama(self) -> bool:
        try:
            subprocess.run(["pkill", "-f", "ollama serve"], timeout=5, capture_output=True)
            time.sleep(2)
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            time.sleep(5)
            import requests
            return requests.get("http://localhost:11434/api/tags", timeout=5).status_code == 200
        except Exception as e:
            logger.error("Ollama restart failed: %s", e)
            return False

    def _fix_port_conflict(self) -> bool:
        try:
            subprocess.run(["fuser", "-k", "7777/tcp"], capture_output=True, timeout=5)
            time.sleep(1)
            return True
        except Exception:
            return False

    def _fix_connection(self) -> bool:
        try:
            subprocess.run(
                ["nmcli", "connection", "up", "Providence_Faculty"],
                capture_output=True, timeout=30,
            )
            time.sleep(3)
            return True
        except Exception:
            return False

    def _fix_with_brain(self, problem: dict) -> bool:
        if not self.brain:
            return False
        try:
            prompt = (
                f"[SELF-HEALING] Critical error detected:\n"
                f"Type: {problem['type']}\nError: {problem.get('error', 'unknown')}\n"
                f"Detail: {problem.get('detail', '')}\n\n"
                f"Use your tools to locate the issue, read the code, and apply a fix. "
                f"State 'FIX_APPLIED' if fixed, 'CANNOT_FIX' if impossible."
            )
            response = self.brain.think(prompt)
            return "FIX_APPLIED" in response
        except Exception as e:
            logger.debug("Brain-fix error: %s", e)
        return False

    def _notify_user(self, problem: dict):
        if self.speaker and problem.get("severity") in ("critical", "high"):
            msg = f"Problem detected: {problem['type']}: {problem.get('error', '')[:100]}"
            try:
                self.speaker.speak(msg)
            except Exception:
                pass

    def _log_fix(self, problem: dict, status: str):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": problem["type"],
            "error": problem.get("error", ""),
            "status": status,
        }
        self._fixes_applied.append(entry)
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            log = []
            if HEAL_LOG.exists():
                with open(HEAL_LOG) as f:
                    log = json.load(f)
            log.append(entry)
            log = log[-200:]
            with open(HEAL_LOG, "w") as f:
                json.dump(log, f, indent=2)
        except Exception:
            pass


def start_self_healer(brain=None, speaker=None):
    """Start the self-healer in a background thread."""
    healer = SelfHealer(brain=brain, speaker=speaker)
    healer.start()
    return healer
