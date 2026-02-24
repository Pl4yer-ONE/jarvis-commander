"""
Max — Sentinel Module (Always-On Background Monitoring)

Continuous background threads that give Max persistent awareness:
  - Camera Loop: Captures frames for dashboard and YOLO
  - YOLO Loop: Object detection on camera feed
  - System Telemetry: Live hardware monitoring
  - USB Watcher: Detects new devices
  - Self-Update: Periodic health checks

All data is published to the event bus for real-time consumption.
"""

import json
import logging
import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("max.sentinel")

DATA_DIR = Path(__file__).parent.parent / "data"
CAPTURE_DIR = DATA_DIR / "captures"
STATE_FILE = DATA_DIR / "sentinel_state.json"


def _save_state_file(state: dict):
    """Persist state to disk for external consumers."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2, default=str)
    except Exception:
        pass


def _crash_recovery(func, name, *args):
    """Wrapper that auto-restarts a loop on crash."""
    while True:
        try:
            func(*args)
        except Exception as e:
            logger.error("⚠️ %s crashed: %s — restarting in 10s", name, e)
            time.sleep(10)


def _publish_sync(topic: str, data: dict):
    """Publish to event bus from a sync context. Best-effort, never blocks."""
    try:
        import asyncio
        from core.event_bus import get_bus
        bus = get_bus()
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(bus.publish(topic, data))
        except RuntimeError:
            # No running loop — update state directly
            import asyncio
            asyncio.run(bus.publish(topic, data))
    except Exception:
        pass


# ── Camera Loop ──────────────────────────────────────────────

def _camera_loop(interval: int = 30):
    """Continuous camera capture at ~2 FPS."""
    logger.info("📷 Camera thread started (continuous ~2 FPS)")
    os.makedirs(CAPTURE_DIR, exist_ok=True)

    FRAME_INTERVAL = 0.5
    CLEANUP_EVERY = max(interval, 30)
    last_cleanup = time.time()

    while True:
        try:
            os.environ["OPENCV_LOG_LEVEL"] = "SILENT"
            import cv2
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                _publish_sync("sentinel.camera", {"status": "error", "error": "Cannot open webcam"})
                time.sleep(10)
                continue

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, 5)

            logger.info("📷 Camera opened — streaming")
            frame_count = 0

            while True:
                ret, frame = cap.read()
                if not ret:
                    logger.warning("📷 Frame read failed — reconnecting")
                    break

                latest_temp = str(CAPTURE_DIR / "cam_temp.jpg")
                latest = str(CAPTURE_DIR / "cam_latest.jpg")
                cv2.imwrite(latest_temp, frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                os.replace(latest_temp, latest)
                frame_count += 1

                _publish_sync("sentinel.camera", {
                    "status": "active",
                    "last_capture": datetime.now().isoformat(),
                    "path": latest,
                    "fps": round(1.0 / FRAME_INTERVAL, 1),
                    "frames": frame_count,
                    "error": None,
                })

                # Save timestamped snapshot periodically
                if frame_count % int(CLEANUP_EVERY / FRAME_INTERVAL) == 0:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    cv2.imwrite(str(CAPTURE_DIR / f"cam_{ts}.jpg"), frame)

                # Periodic cleanup (keep last 20 snapshots)
                now = time.time()
                if now - last_cleanup > CLEANUP_EVERY:
                    captures = sorted(CAPTURE_DIR.glob("cam_2*.jpg"))
                    for old in captures[:-20]:
                        try:
                            old.unlink()
                        except Exception:
                            pass
                    last_cleanup = now

                time.sleep(FRAME_INTERVAL)

            cap.release()
            time.sleep(2)

        except ImportError:
            _publish_sync("sentinel.camera", {"status": "error", "error": "opencv-python not installed"})
            return
        except Exception as e:
            logger.warning("Camera error: %s", e)
            _publish_sync("sentinel.camera", {"status": "error", "error": str(e)})
            time.sleep(interval)


# ── YOLO Detection Loop ─────────────────────────────────────

_prev_detection_set: set = set()


def _yolo_loop(interval: float = 0.5):
    """YOLO object detection on the camera feed."""
    global _prev_detection_set
    logger.info("🔍 YOLO thread started (every %.1fs)", interval)

    model = None

    while True:
        try:
            import cv2
            from ultralytics import YOLO

            if model is None:
                model_path = str(Path(__file__).parent.parent / "yolov8n.pt")
                model = YOLO(model_path)

            latest = CAPTURE_DIR / "cam_latest.jpg"
            if not latest.exists():
                time.sleep(1)
                continue

            frame = cv2.imread(str(latest))
            if frame is None:
                time.sleep(1)
                continue

            results = model(frame, verbose=False)
            detections = []
            for r in results:
                for box in r.boxes:
                    conf = float(box.conf[0])
                    if conf > 0.3:
                        x1, y1, x2, y2 = box.xyxy[0]
                        cls = int(box.cls[0])
                        detections.append({
                            "object": model.names[cls],
                            "confidence": round(conf, 2),
                            "bbox": [int(x1), int(y1), int(x2), int(y2)],
                            "center": [int((x1 + x2) / 2), int((y1 + y2) / 2)],
                        })

            # Scene-change detection
            current_set = set(d["object"] for d in detections)
            scene_changed = False
            if _prev_detection_set:
                changes = current_set.symmetric_difference(_prev_detection_set)
                scene_changed = len(changes) / max(len(current_set | _prev_detection_set), 1) > 0.3
                if scene_changed:
                    logger.info("🔍 Scene change! Δ: %s", changes)
            _prev_detection_set = current_set

            _publish_sync("sentinel.yolo", {
                "status": "active",
                "last_scan": datetime.now().isoformat(),
                "detections": detections,
                "scene_changed": scene_changed,
                "error": None,
            })

        except ImportError as e:
            _publish_sync("sentinel.yolo", {"status": "error", "error": f"Missing: {e}"})
            return
        except Exception as e:
            logger.warning("YOLO error: %s", e)

        time.sleep(interval)


# ── System Telemetry ─────────────────────────────────────────

def _system_loop(interval: int = 15):
    """System telemetry collection."""
    logger.info("⚙️ System telemetry thread started (every %ds)", interval)

    while True:
        try:
            import psutil
            import shutil

            cpu = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory()
            disk = shutil.disk_usage("/")

            # Temperature
            temp = "N/A"
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    for entries in temps.values():
                        if entries:
                            temp = f"{entries[0].current:.0f}°C"
                            break
            except Exception:
                try:
                    r = subprocess.run(["sensors"], capture_output=True, text=True, timeout=5)
                    for line in r.stdout.split("\n"):
                        if any(k in line for k in ("Core 0", "Tctl", "temp1")):
                            temp = line.split(":")[1].strip().split()[0] if ":" in line else "N/A"
                            break
                except Exception:
                    pass

            # Battery
            battery = "N/A"
            try:
                bat = psutil.sensors_battery()
                if bat:
                    battery = f"{bat.percent:.0f}%{'⚡' if bat.power_plugged else '🔋'}"
            except Exception:
                pass

            data = {
                "cpu": round(cpu, 1),
                "ram": round(mem.percent, 1),
                "ram_used_gb": round(mem.used / (1024 ** 3), 1),
                "ram_total_gb": round(mem.total / (1024 ** 3), 1),
                "disk_free": f"{disk.free / (1024 ** 3):.1f}GB",
                "temp": temp,
                "battery": battery,
                "timestamp": datetime.now().isoformat(),
            }

            _publish_sync("sentinel.system", {
                "status": "active",
                "last_check": datetime.now().isoformat(),
                "data": data,
                "error": None,
            })

        except Exception as e:
            logger.warning("Telemetry error: %s", e)

        time.sleep(interval)


# ── USB Watcher ──────────────────────────────────────────────

def _usb_loop(interval: int = 10):
    """Monitor USB ports for new devices."""
    logger.info("🔌 USB watcher started (every %ds)", interval)
    prev_devices: set = set()

    while True:
        try:
            result = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=5)
            current = set(result.stdout.strip().split("\n")) if result.stdout.strip() else set()

            new_devices = current - prev_devices
            removed = prev_devices - current

            new_device = None
            if prev_devices and new_devices:
                new_device = list(new_devices)[0]
                logger.info("🔌 NEW USB: %s", new_device)
            elif prev_devices and removed:
                logger.info("🔌 USB removed: %s", list(removed)[0])

            prev_devices = current

            _publish_sync("sentinel.usb", {
                "status": "active",
                "last_check": datetime.now().isoformat(),
                "devices": list(current),
                "new_device": new_device,
                "error": None,
            })

        except Exception as e:
            logger.warning("USB watcher error: %s", e)

        time.sleep(interval)


# ── Self-Update Cycle ────────────────────────────────────────

def _self_update_loop(interval: int = 300):
    """Periodic health checks."""
    logger.info("🧬 Self-update thread started (every %ds)", interval)

    while True:
        try:
            actions = []

            # Check skills
            try:
                from skills import SkillRegistry
                sr = SkillRegistry()
                sr.discover()
                actions.append(f"Skills OK: {len(sr.list_skills())} loaded")
            except Exception as e:
                actions.append(f"Skills ERROR: {e}")

            # Check Ollama
            try:
                result = subprocess.run(
                    ["curl", "-s", "http://localhost:11434/api/tags"],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0:
                    models = json.loads(result.stdout).get("models", [])
                    names = [m.get("name", "?") for m in models]
                    actions.append(f"Ollama OK: {', '.join(names)}")
                else:
                    actions.append("Ollama: connection issue")
            except Exception as e:
                actions.append(f"Ollama check failed: {e}")

            # Disk space
            try:
                import shutil
                disk = shutil.disk_usage("/")
                free_pct = (disk.free / disk.total) * 100
                status = f"⚠️ LOW DISK: {free_pct:.1f}%" if free_pct < 10 else f"Disk OK: {free_pct:.1f}%"
                actions.append(status)
            except Exception:
                pass

            _publish_sync("sentinel.self_update", {
                "status": "active",
                "last_run": datetime.now().isoformat(),
                "actions": actions,
                "error": None,
            })

        except Exception as e:
            logger.warning("Self-update error: %s", e)

        time.sleep(interval)


# ── Thought State Sync ───────────────────────────────────────

def _thought_sync_loop(interval: int = 5):
    """Sync thought engine state into event bus for dashboard."""
    logger.info("💭 Thought sync thread started")
    while True:
        try:
            from core.thought_engine import get_thoughts, get_latest_thought
            thoughts = get_thoughts(10)
            latest = get_latest_thought()
            _publish_sync("sentinel.thoughts", {
                "status": "active" if thoughts else "idle",
                "count": len(thoughts),
                "latest": latest.get("content", "") if latest else None,
                "recent": [
                    {
                        "content": t["content"][:120],
                        "category": t["category"],
                        "timestamp": t["timestamp"],
                        "speak_score": t["speak_score"],
                    }
                    for t in thoughts[-8:]
                ],
            })
        except ImportError:
            pass
        except Exception as e:
            logger.debug("Thought sync error: %s", e)
        time.sleep(interval)


# ── State File Sync (for dashboard fallback) ─────────────────

def _state_file_sync_loop(interval: int = 3):
    """Periodically write combined state to JSON file for dashboard."""
    logger.info("📁 State file sync started")
    while True:
        try:
            from core.event_bus import get_bus
            bus = get_bus()
            state = bus.get_all_state()
            # Flatten the sentinel.* prefixed keys
            flat = {}
            for key, val in state.items():
                if key.startswith("sentinel."):
                    flat[key.replace("sentinel.", "")] = val
                else:
                    flat[key] = val
            _save_state_file(flat)
        except Exception:
            pass
        time.sleep(interval)


# ── Public API ───────────────────────────────────────────────

def get_live_state() -> dict:
    """Get a snapshot of all sentinel data from event bus."""
    try:
        from core.event_bus import get_bus
        bus = get_bus()
        state = bus.get_all_state()
        return {
            k.replace("sentinel.", ""): v
            for k, v in state.items()
            if k.startswith("sentinel.")
        }
    except Exception:
        return {}


def get_live_context() -> str:
    """Formatted string of live sensor data for the LLM system prompt."""
    state = get_live_state()
    parts = []

    cam = state.get("camera", {})
    if cam.get("status") == "active":
        parts.append(f"📷 Camera: LIVE (last: {cam.get('last_capture', 'N/A')})")

    yolo = state.get("yolo", {})
    if yolo.get("detections"):
        det = ", ".join(f"{d['object']}@({d['center'][0]},{d['center'][1]})" for d in yolo["detections"][:10])
        parts.append(f"🔍 YOLO: {len(yolo['detections'])} objects: {det}")

    sys_data = state.get("system", {}).get("data", {})
    if sys_data:
        parts.append(
            f"⚙️ System: CPU {sys_data.get('cpu', '?')}%, RAM {sys_data.get('ram', '?')}%, "
            f"Disk {sys_data.get('disk_free', '?')} free"
        )

    usb = state.get("usb", {})
    if usb.get("new_device"):
        parts.append(f"🔌 NEW USB: {usb['new_device']}")

    return "\n".join(parts)


def start_sentinel(
    camera_interval: int = 30,
    yolo_interval: float = 0.5,
    system_interval: int = 15,
    usb_interval: int = 10,
    update_interval: int = 300,
):
    """Start all background monitoring threads with crash recovery."""
    threads = [
        ("sentinel-camera", _camera_loop, (camera_interval,)),
        ("sentinel-yolo", _yolo_loop, (yolo_interval,)),
        ("sentinel-system", _system_loop, (system_interval,)),
        ("sentinel-usb", _usb_loop, (usb_interval,)),
        ("sentinel-update", _self_update_loop, (update_interval,)),
        ("sentinel-thoughts", _thought_sync_loop, (5,)),
        ("sentinel-state-file", _state_file_sync_loop, (3,)),
    ]

    for name, target, args in threads:
        t = threading.Thread(
            target=_crash_recovery, args=(target, name, *args),
            daemon=True, name=name,
        )
        t.start()
        logger.info("Started %s (with crash recovery)", name)

    logger.info("🛡️ All Sentinel threads active.")
