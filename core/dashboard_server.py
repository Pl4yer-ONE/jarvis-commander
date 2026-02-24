"""
Max — Web Dashboard Server

FastAPI + WebSocket server that serves the live dashboard and streams
real-time data (sentinel state, camera frames, YOLO, thoughts, chat).

Reads state from the event bus (with file-based fallback).
Endpoints:
  GET /              → Dashboard HTML
  GET /api/health    → Health check
  GET /api/state     → Full state snapshot
  WS  /ws/state      → Real-time state stream (1s)
  WS  /ws/camera     → Live camera frames as base64 JPEG
"""

import asyncio
import base64
import json
import logging
import os
import socket
import threading
import time
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger("max.dashboard")

JARVIS_DIR = Path(__file__).parent.parent
DATA_DIR = JARVIS_DIR / "data"
DASHBOARD_DIR = JARVIS_DIR / "dashboard"
SENTINEL_STATE = DATA_DIR / "sentinel_state.json"
CHAT_LOG = DATA_DIR / "chat_log.txt"
CAM_PATH = DATA_DIR / "captures" / "cam_latest.jpg"


def _get_state() -> dict:
    """Get state from event bus, falling back to disk file."""
    try:
        from core.event_bus import get_bus
        bus = get_bus()
        state = bus.get_all_state()
        flat = {}
        for key, val in state.items():
            if key.startswith("sentinel."):
                flat[key.replace("sentinel.", "")] = val
            else:
                flat[key] = val
        if flat:
            return flat
    except Exception:
        pass

    # Fallback: read from disk
    try:
        if SENTINEL_STATE.exists():
            with open(SENTINEL_STATE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _read_recent_chat(count: int = 30) -> list[dict]:
    """Read recent chat messages from the log file."""
    messages = []
    try:
        if CHAT_LOG.exists():
            with open(CHAT_LOG) as f:
                lines = f.readlines()
            for line in lines[-count:]:
                line = line.strip()
                if not line:
                    continue
                try:
                    parts = line.split("] ", 1)
                    if len(parts) == 2:
                        ts = parts[0].lstrip("[")
                        msg_parts = parts[1].split(": ", 1)
                        if len(msg_parts) == 2:
                            messages.append({
                                "timestamp": ts,
                                "source": msg_parts[0].strip(),
                                "message": msg_parts[1].strip(),
                            })
                except Exception:
                    pass
    except Exception:
        pass
    return messages


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(title="MAXIMUS COMMAND CENTER", version="3.0")

    # CORS for local dev
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Serve static dashboard files
    if DASHBOARD_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(DASHBOARD_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def serve_dashboard():
        index = DASHBOARD_DIR / "index.html"
        if index.exists():
            return FileResponse(str(index), media_type="text/html")
        return HTMLResponse("<h1>Dashboard not found</h1>", status_code=404)

    @app.get("/api/health")
    async def health():
        return {
            "status": "online",
            "name": "MAXIMUS DECIMUS MERIDIUS",
            "timestamp": datetime.now().isoformat(),
            "uptime": time.monotonic(),
        }

    @app.get("/api/state")
    async def state():
        return _get_state()

    @app.get("/api/chat")
    async def chat():
        return {"messages": _read_recent_chat(50)}

    @app.websocket("/ws/state")
    async def ws_state(websocket: WebSocket):
        await websocket.accept()
        logger.info("Dashboard client connected (state)")
        try:
            while True:
                state = _get_state()
                state["chat"] = _read_recent_chat(30)
                state["timestamp"] = datetime.now().isoformat()
                await websocket.send_json(state)
                await asyncio.sleep(1.0)
        except WebSocketDisconnect:
            logger.info("Dashboard client disconnected (state)")
        except Exception as e:
            logger.debug("State WS error: %s", e)

    @app.websocket("/ws/camera")
    async def ws_camera(websocket: WebSocket):
        await websocket.accept()
        logger.info("Dashboard client connected (camera)")
        last_mtime = 0.0
        try:
            while True:
                try:
                    cam = str(CAM_PATH)
                    if os.path.exists(cam):
                        mtime = os.path.getmtime(cam)
                        if mtime != last_mtime:
                            with open(cam, "rb") as f:
                                img_data = f.read()
                            b64 = base64.b64encode(img_data).decode("utf-8")
                            await websocket.send_json({
                                "frame": b64,
                                "timestamp": datetime.now().isoformat(),
                            })
                            last_mtime = mtime
                except Exception as e:
                    logger.debug("Camera frame error: %s", e)
                await asyncio.sleep(0.5)
        except WebSocketDisconnect:
            logger.info("Dashboard client disconnected (camera)")
        except Exception as e:
            logger.debug("Camera WS error: %s", e)

    return app


def start_dashboard_server(port: int = 7777):
    """Start the dashboard server in a background thread."""
    import uvicorn

    # Check if port is available
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("0.0.0.0", port))
        sock.close()
    except OSError as e:
        logger.warning("Port %d in use (%s) — dashboard may already be running", port, e)
        return None

    app = create_app()

    def _run():
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning", access_log=False)

    thread = threading.Thread(target=_run, daemon=True, name="dashboard-server")
    thread.start()
    logger.info("🌐 Dashboard at http://localhost:%d", port)
    return thread
