"""
Jarvis Skills — Total Omnicompetence Control

These skills grant Max absolute, zero-blind-spot control over the Linux system.
Includes process annihilation, deep firmware/kernel insight, firewall mastery,
and audio/video stream hijacking.
"""

import logging
import os
import subprocess
import shutil

from skills import skill

logger = logging.getLogger("jarvis.skills.omni_control")

# ═══════════════════════════════════════════════════════════════
#  USER & PROCESS ANNIHILATION
# ═══════════════════════════════════════════════════════════════

@skill(
    name="nuke_process",
    description="Forcefully terminates a process by PID or name using SIGKILL (-9). Faster and more brutal than standard close.",
    parameters={
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "PID (number) or exact process name.",
            }
        },
        "required": ["target"],
    },
)
def nuke_process(target: str, **kwargs) -> str:
    try:
        if target.isdigit():
            subprocess.run(["sudo", "kill", "-9", target], check=True, capture_output=True, timeout=5)
            return f"Process with PID {target} annihilated."
        else:
            subprocess.run(["sudo", "killall", "-9", target], check=True, capture_output=True, timeout=5)
            return f"All processes named '{target}' annihilated."
    except subprocess.CalledProcessError as e:
        return f"Failed to nuke process: {e.stderr.decode('utf-8', errors='replace').strip()}"
    except Exception as e:
        return f"Error: {e}"


@skill(
    name="kill_tty_session",
    description="Forcefully terminates all processes associated with a specific TTY or PTS session.",
    parameters={
        "type": "object",
        "properties": {
            "tty_name": {
                "type": "string",
                "description": "Name of the TTY (e.g. 'tty3', 'pts/0').",
            }
        },
        "required": ["tty_name"],
    },
)
def kill_tty_session(tty_name: str, **kwargs) -> str:
    try:
        subprocess.run(["sudo", "pkill", "-9", "-t", tty_name], check=True, capture_output=True, timeout=5)
        return f"All processes on {tty_name} forcefully terminated."
    except subprocess.CalledProcessError as e:
        return f"Failed to kill TTY session: No processes matched or insufficient permissions."
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════
#  FIRMWARE & KERNEL INSIGHT
# ═══════════════════════════════════════════════════════════════

@skill(
    name="read_kernel_logs",
    description="Reads the latest system kernel logs (dmesg) or critical journalctl errors to diagnose hardware or driver faults.",
    parameters={
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "description": "'dmesg' for kernel ring buffer, 'journal' for systemd critical errors. Default: 'dmesg'.",
            },
            "lines": {
                "type": "integer",
                "description": "Number of recent lines to retrieve. Default: 30.",
            }
        },
    },
)
def read_kernel_logs(source: str = "dmesg", lines: int = 30, **kwargs) -> str:
    try:
        if source == "journal":
            r = subprocess.run(["sudo", "journalctl", "-p", "3", "-b", "-n", str(lines)], 
                              capture_output=True, text=True, timeout=10)
        else:
            r = subprocess.run(["sudo", "dmesg", "-T"], capture_output=True, text=True, timeout=10)
            logs = r.stdout.strip().split('\n')[-lines:]
            r.stdout = '\n'.join(logs)
            
        return r.stdout.strip() if r.stdout.strip() else f"No recent logs found for {source}."
    except Exception as e:
        return f"Error reading logs: {e}"


@skill(
    name="list_kernel_modules",
    description="Lists loaded kernel modules (drivers) using lsmod.",
    parameters={"type": "object", "properties": {}},
)
def list_kernel_modules(**kwargs) -> str:
    try:
        r = subprocess.run(["lsmod"], capture_output=True, text=True, timeout=5)
        return f"Loaded Kernel Modules (first 40):\n" + "\n".join(r.stdout.split('\n')[:40])
    except Exception as e:
        return f"Error reading kernel modules: {e}"


# ═══════════════════════════════════════════════════════════════
#  FIREWALL & PORT MASTERY
# ═══════════════════════════════════════════════════════════════

@skill(
    name="manage_firewall",
    description="Manipulates the Uncomplicated Firewall (UFW) to block or allow network traffic.",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "'status', 'enable', 'disable', 'allow', 'deny'.",
            },
            "port": {
                "type": "string",
                "description": "Port number and optional protocol (e.g. '80', '22/tcp'). Required for 'allow'/'deny'.",
            }
        },
        "required": ["action"],
    },
)
def manage_firewall(action: str, port: str = "", **kwargs) -> str:
    if shutil.which("ufw") is None:
        return "UFW (Uncomplicated Firewall) is not installed on this system."
        
    action = action.lower()
    try:
        if action in ["status", "enable", "disable"]:
            cmd = ["sudo", "ufw", action]
        elif action in ["allow", "deny"]:
            if not port:
                return f"Port must be specified for action '{action}'."
            cmd = ["sudo", "ufw", action, port]
        else:
            return f"Invalid action: {action}"
            
        r = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=10)
        return r.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"Firewall command failed: {e.stderr.strip()}"
    except Exception as e:
        return f"Error managing firewall: {e}"


@skill(
    name="list_active_connections",
    description="Lists all active network connections and listening ports using ss/netstat.",
    parameters={"type": "object", "properties": {}},
)
def list_active_connections(**kwargs) -> str:
    try:
        r = subprocess.run(["ss", "-tunlp"], capture_output=True, text=True, timeout=10)
        # We need sudo to see process names for all ports, but we'll try without first.
        # If running as root or if it's user-owned, it'll show.
        if r.returncode == 0:
            lines = r.stdout.strip().split('\n')
            if len(lines) > 30:
               return "Active Connections (Listening):\n" + "\n".join(lines[:30]) + f"\n... ({len(lines)-30} more omitted)"
            return "Active Connections (Listening):\n" + "\n".join(lines)
        return "Failed to list connections."
    except Exception as e:
        return f"Error reading connections: {e}"


# ═══════════════════════════════════════════════════════════════
#  AUDIO/VIDEO STREAM HIJACKING
# ═══════════════════════════════════════════════════════════════

@skill(
    name="audio_stream_hijack",
    description="Intercepts or controls active PulseAudio/Pipewire streams at a low level.",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "'list_streams' (view active streams), 'kill_stream' (terminate a stream).",
            },
            "sink_input_id": {
                "type": "string",
                "description": "ID of the stream to kill (from list_streams). Required for 'kill_stream'.",
            }
        },
        "required": ["action"],
    },
)
def audio_stream_hijack(action: str, sink_input_id: str = "", **kwargs) -> str:
    try:
        if action == "list_streams":
            r = subprocess.run(["pactl", "list", "sink-inputs", "short"], capture_output=True, text=True, timeout=5)
            if r.stdout.strip():
                return f"Active Audio Streams:\n{r.stdout.strip()}"
            return "No active audio streams playing right now."
        elif action == "kill_stream":
            if not sink_input_id:
                return "sink_input_id required to kill a stream."
            subprocess.run(["pactl", "kill-sink-input", sink_input_id], check=True, capture_output=True, timeout=5)
            return f"Successfully killed audio stream ID {sink_input_id}."
        else:
            return f"Invalid action: {action}"
    except subprocess.CalledProcessError as e:
       return f"PulseAudio command failed: {e.stderr.decode('utf-8', errors='replace').strip()}"
    except Exception as e:
        return f"Error manipulating audio streams: {e}"

logger.info("Omnicompetence Control skills loaded.")
