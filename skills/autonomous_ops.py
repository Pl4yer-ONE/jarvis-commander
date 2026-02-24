"""
Jarvis Skills — Autonomous Operations

Skills that enable Max to act autonomously:
- Self-reflection and performance analysis
- Full environmental scanning
- Activity narration based on camera/YOLO
- Proactive action suggestions
"""

import json
import logging
import subprocess
from datetime import datetime

from skills import skill

logger = logging.getLogger("jarvis.skills.autonomous")


# ── Self Reflection ──────────────────────────────────────────

@skill(
    name="self_reflect",
    description=(
        "Max analyzes his own performance, reviews recent actions and conversations, "
        "and proposes improvements to his skills or behaviour. Returns a self-analysis report."
    ),
    parameters={
        "type": "object",
        "properties": {},
    },
)
def self_reflect(**kwargs) -> str:
    """Gather performance data and return a self-analysis report."""
    report_parts = []

    # 1. Check recent thoughts
    try:
        from core.thought_engine import get_thoughts
        thoughts = get_thoughts(20)
        categories = {}
        for t in thoughts:
            cat = t.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1
        report_parts.append(
            f"Recent thought distribution ({len(thoughts)} thoughts): "
            + ", ".join(f"{k}={v}" for k, v in categories.items())
        )
    except Exception as e:
        report_parts.append(f"Thought analysis unavailable: {e}")

    # 2. Check skill registry
    try:
        from skills import SkillRegistry
        sr = SkillRegistry()
        sr.discover()
        skills = sr.list_skills()
        report_parts.append(f"Active skills: {len(skills)} ({', '.join(list(skills.keys())[:15])}...)")
    except Exception as e:
        report_parts.append(f"Skill check error: {e}")

    # 3. System resource check
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        report_parts.append(
            f"System load: CPU {cpu}%, RAM {mem.percent}% "
            f"({mem.used // (1024**3)}/{mem.total // (1024**3)} GB)"
        )
    except Exception:
        pass

    # 4. Ollama model check
    try:
        result = subprocess.run(
            ["curl", "-s", "http://localhost:11434/api/tags"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            models = json.loads(result.stdout).get("models", [])
            names = [m.get("name", "?") for m in models]
            report_parts.append(f"Available AI models: {', '.join(names)}")
    except Exception:
        pass

    # 5. Uptime
    try:
        result = subprocess.run(["uptime", "-p"], capture_output=True, text=True, timeout=5)
        report_parts.append(f"System uptime: {result.stdout.strip()}")
    except Exception:
        pass

    return "=== MAX SELF-REFLECTION REPORT ===\n" + "\n".join(f"• {p}" for p in report_parts)


# ── Environmental Scan ───────────────────────────────────────

@skill(
    name="environmental_scan",
    description=(
        "Performs a comprehensive environment sweep: camera capture, YOLO detection, "
        "system telemetry, network status, and USB devices. Returns a full situational report."
    ),
    parameters={
        "type": "object",
        "properties": {},
    },
)
def environmental_scan(**kwargs) -> str:
    """Full environment sweep combining all sensors."""
    parts = [f"=== ENVIRONMENTAL SCAN — {datetime.now().strftime('%H:%M:%S')} ==="]

    # Camera
    try:
        from skills.vision_ops import look_at_camera
        cam_result = look_at_camera()
        parts.append(f"📷 Camera: {cam_result}")
    except Exception as e:
        parts.append(f"📷 Camera: Error — {e}")

    # YOLO
    try:
        from core.sentinel import get_live_state
        state = get_live_state()
        yolo = state.get("yolo", {})
        dets = yolo.get("detections", [])
        if dets:
            objs = ", ".join(f"{d['object']}({d['confidence']:.0%})" for d in dets[:10])
            parts.append(f"🔍 YOLO: {len(dets)} objects — {objs}")
        else:
            parts.append("🔍 YOLO: No objects detected")
    except Exception as e:
        parts.append(f"🔍 YOLO: Error — {e}")

    # System
    try:
        import psutil
        import shutil
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = shutil.disk_usage("/")
        parts.append(
            f"⚙️ System: CPU {cpu}%, RAM {mem.percent}%, "
            f"Disk {disk.free // (1024**3)}GB free"
        )
    except Exception:
        pass

    # Network
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL", "dev", "wifi"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.strip().split("\n"):
            if line.startswith("yes:"):
                parts_line = line.split(":")
                parts.append(f"📶 WiFi: {parts_line[1]} (signal: {parts_line[2]}%)")
                break
    except Exception:
        pass

    # USB
    try:
        result = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=5)
        usb_count = len(result.stdout.strip().split("\n")) if result.stdout.strip() else 0
        parts.append(f"🔌 USB: {usb_count} devices connected")
    except Exception:
        pass

    return "\n".join(parts)


# ── Narrate Activity ─────────────────────────────────────────

@skill(
    name="narrate_activity",
    description=(
        "Describes what appears to be happening based on camera feed and YOLO detections. "
        "Max narrates the current scene as if commentating live."
    ),
    parameters={
        "type": "object",
        "properties": {},
    },
)
def narrate_activity(**kwargs) -> str:
    """Build a narrative from current sensor data."""
    observations = []

    try:
        from core.sentinel import get_live_state
        state = get_live_state()

        # YOLO
        yolo = state.get("yolo", {})
        dets = yolo.get("detections", [])
        if dets:
            objects = [d["object"] for d in dets]
            unique = list(set(objects))
            counts = {obj: objects.count(obj) for obj in unique}
            obj_desc = ", ".join(
                f"{count} {obj}{'s' if count > 1 else ''}"
                for obj, count in counts.items()
            )
            observations.append(f"I can see: {obj_desc}")

            # Detect people
            person_count = objects.count("person")
            if person_count == 1:
                observations.append("There is one person in view — likely the user.")
            elif person_count > 1:
                observations.append(f"There are {person_count} people visible.")

        # System activity
        sys_data = state.get("system", {}).get("data", {})
        cpu = sys_data.get("cpu", 0)
        if isinstance(cpu, (int, float)):
            if cpu > 70:
                observations.append(
                    f"The system is under heavy load at {cpu}% CPU — "
                    "something computationally intensive is running."
                )
            elif cpu < 10:
                observations.append("The system is largely idle.")

    except Exception as e:
        observations.append(f"Sensor data unavailable: {e}")

    if not observations:
        return "The environment is quiet. Nothing notable to report."

    return "Current scene: " + " ".join(observations)


# ── Suggest Action ───────────────────────────────────────────

@skill(
    name="suggest_action",
    description=(
        "Based on current system state and context, Max proactively suggests a helpful "
        "action the user might want to take. Returns a suggestion with reasoning."
    ),
    parameters={
        "type": "object",
        "properties": {},
    },
)
def suggest_action(**kwargs) -> str:
    """Analyze context and suggest a useful action."""
    suggestions = []

    try:
        import psutil
        import shutil

        # Battery
        try:
            bat = psutil.sensors_battery()
            if bat and bat.percent < 30 and not bat.power_plugged:
                suggestions.append(
                    f"⚡ Battery at {bat.percent}% and not charging. "
                    "Consider plugging in soon."
                )
        except Exception:
            pass

        # Disk space
        disk = shutil.disk_usage("/")
        free_pct = (disk.free / disk.total) * 100
        if free_pct < 15:
            suggestions.append(
                f"💾 Disk space is low ({free_pct:.1f}% free). "
                "Consider cleaning up old files or docker images."
            )

        # CPU
        cpu = psutil.cpu_percent(interval=1)
        if cpu > 85:
            top_procs = sorted(
                psutil.process_iter(['name', 'cpu_percent']),
                key=lambda p: p.info.get('cpu_percent', 0),
                reverse=True
            )[:3]
            procs_str = ", ".join(
                f"{p.info['name']}({p.info['cpu_percent']}%)" for p in top_procs
            )
            suggestions.append(
                f"🔥 High CPU usage ({cpu}%). Top processes: {procs_str}. "
                "Want me to investigate or kill something?"
            )

        # RAM
        mem = psutil.virtual_memory()
        if mem.percent > 85:
            suggestions.append(
                f"🧠 RAM usage is high ({mem.percent}%). "
                "Consider closing unused applications."
            )

    except Exception as e:
        return f"Could not analyze system for suggestions: {e}"

    if not suggestions:
        # Time-based suggestions
        hour = datetime.now().hour
        if hour >= 22 or hour < 5:
            suggestions.append(
                "🌙 It's late. Consider saving your work and taking a break."
            )
        elif hour >= 12 and hour <= 13:
            suggestions.append("🍴 It's around lunch time. Don't forget to eat.")

    if not suggestions:
        return "Everything looks good. No urgent suggestions at the moment."

    return "=== PROACTIVE SUGGESTIONS ===\n" + "\n".join(suggestions)


# ── Describe Camera View (Vision Model) ──────────────────────

@skill(
    name="describe_camera_view",
    description=(
        "Captures a camera frame and uses a vision/multimodal AI model to describe "
        "what Max sees in natural language. Provides rich scene understanding beyond "
        "simple object detection."
    ),
    parameters={
        "type": "object",
        "properties": {},
    },
)
def describe_camera_view(**kwargs) -> str:
    """Capture camera and describe using vision model."""
    # First capture
    try:
        import cv2
    except ImportError:
        return "Error: opencv-python not installed"

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return "Error: Cannot access webcam"

    ret, frame = cap.read()
    cap.release()

    if not ret:
        return "Error: Could not read camera frame"

    out_path = "/tmp/max_vision_describe.jpg"
    cv2.imwrite(out_path, frame)

    # Try to use vision model via Ollama
    try:
        import ollama
        import base64

        with open(out_path, "rb") as f:
            img_data = f.read()

        response = ollama.chat(
            model="llava:7b",
            messages=[{
                "role": "user",
                "content": "Describe what you see in this image in 2-3 sentences. Be specific about people, objects, and activities.",
                "images": [img_data],
            }],
        )
        description = response.get("message", {}).get("content", "")
        if description:
            return f"Vision Model Analysis:\n{description}"
    except Exception as e:
        logger.debug("Vision model (llava) unavailable: %s", e)

    # Fallback: just return YOLO data
    try:
        from core.sentinel import get_live_state
        state = get_live_state()
        dets = state.get("yolo", {}).get("detections", [])
        if dets:
            objs = ", ".join(f"{d['object']}" for d in dets[:8])
            return f"Camera captured. Vision model unavailable, but YOLO detects: {objs}"
    except Exception:
        pass

    return f"Camera captured and saved to {out_path}. No vision model available for description."


logger.info("Autonomous Operations skills loaded.")
