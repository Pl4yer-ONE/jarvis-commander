"""
Jarvis Skills — Complete Hardware Control

Provides deep hardware control skills: display, audio devices, GPU, CPU governor,
storage mount/unmount, Bluetooth pairing, keyboard backlight, touchpad, fan control,
network scanning, and more.
"""

import logging
import os
import subprocess

from skills import skill

logger = logging.getLogger("jarvis.skills.hardware_control")


# ═══════════════════════════════════════════════════════════════
#  DISPLAY / MONITOR CONTROL
# ═══════════════════════════════════════════════════════════════

@skill(
    name="get_display_info",
    description="Gets detailed display/monitor information: resolution, refresh rate, connected monitors.",
    parameters={"type": "object", "properties": {}},
)
def get_display_info(**kwargs) -> str:
    try:
        result = subprocess.run(["xrandr", "--current"], capture_output=True, text=True, timeout=5)
        return f"Display Info:\n{result.stdout}"
    except FileNotFoundError:
        return "xrandr not found."
    except Exception as e:
        return f"Error: {e}"


@skill(
    name="set_display_resolution",
    description="Sets the display resolution. Example: '1920x1080', '2560x1440', '1366x768'.",
    parameters={
        "type": "object",
        "properties": {
            "resolution": {"type": "string", "description": "Resolution like '1920x1080'."},
            "output": {"type": "string", "description": "Monitor output name (e.g. 'eDP-1'). Default: auto-detect primary."},
        },
        "required": ["resolution"],
    },
)
def set_display_resolution(resolution: str, output: str = "", **kwargs) -> str:
    if not output:
        try:
            r = subprocess.run(["xrandr", "--current"], capture_output=True, text=True, timeout=5)
            for line in r.stdout.split("\n"):
                if " connected" in line:
                    output = line.split()[0]
                    break
        except Exception:
            return "Cannot detect display output."
    try:
        subprocess.run(["xrandr", "--output", output, "--mode", resolution], check=True, capture_output=True, timeout=5)
        return f"Set {output} to {resolution}."
    except subprocess.CalledProcessError as e:
        return f"Failed: {e.stderr}"
    except Exception as e:
        return f"Error: {e}"


@skill(
    name="set_display_rotation",
    description="Rotates the display. Direction: 'normal', 'left', 'right', 'inverted'.",
    parameters={
        "type": "object",
        "properties": {
            "direction": {"type": "string", "description": "'normal', 'left', 'right', or 'inverted'."},
            "output": {"type": "string", "description": "Monitor output name. Default: auto-detect."},
        },
        "required": ["direction"],
    },
)
def set_display_rotation(direction: str, output: str = "", **kwargs) -> str:
    if direction not in ("normal", "left", "right", "inverted"):
        return "Direction must be 'normal', 'left', 'right', or 'inverted'."
    if not output:
        try:
            r = subprocess.run(["xrandr", "--current"], capture_output=True, text=True, timeout=5)
            for line in r.stdout.split("\n"):
                if " connected" in line:
                    output = line.split()[0]
                    break
        except Exception:
            return "Cannot detect display."
    try:
        subprocess.run(["xrandr", "--output", output, "--rotate", direction], check=True, capture_output=True, timeout=5)
        return f"Rotated {output} to '{direction}'."
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════
#  AUDIO DEVICE MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@skill(
    name="list_audio_devices",
    description="Lists all audio input (microphones) and output (speakers/headphones) devices.",
    parameters={"type": "object", "properties": {}},
)
def list_audio_devices(**kwargs) -> str:
    parts = []
    try:
        r = subprocess.run(["pactl", "list", "sinks", "short"], capture_output=True, text=True, timeout=5)
        parts.append(f"Output Devices (Sinks):\n{r.stdout}")
    except Exception:
        parts.append("Cannot list output devices.")
    try:
        r = subprocess.run(["pactl", "list", "sources", "short"], capture_output=True, text=True, timeout=5)
        parts.append(f"Input Devices (Sources):\n{r.stdout}")
    except Exception:
        parts.append("Cannot list input devices.")
    return "\n".join(parts)


@skill(
    name="set_audio_output",
    description="Switches the default audio output device (speaker/headphone). Use list_audio_devices first to get sink names.",
    parameters={
        "type": "object",
        "properties": {
            "sink_name": {"type": "string", "description": "Name or index of the audio sink to set as default."},
        },
        "required": ["sink_name"],
    },
)
def set_audio_output(sink_name: str, **kwargs) -> str:
    try:
        subprocess.run(["pactl", "set-default-sink", sink_name], check=True, capture_output=True, timeout=5)
        return f"Default audio output set to: {sink_name}"
    except Exception as e:
        return f"Error setting audio output: {e}"


@skill(
    name="set_audio_input",
    description="Switches the default audio input device (microphone). Use list_audio_devices first to get source names.",
    parameters={
        "type": "object",
        "properties": {
            "source_name": {"type": "string", "description": "Name or index of the audio source to set as default."},
        },
        "required": ["source_name"],
    },
)
def set_audio_input(source_name: str, **kwargs) -> str:
    try:
        subprocess.run(["pactl", "set-default-source", source_name], check=True, capture_output=True, timeout=5)
        return f"Default audio input set to: {source_name}"
    except Exception as e:
        return f"Error setting audio input: {e}"


@skill(
    name="toggle_mute",
    description="Mutes or unmutes the audio output or input. Target: 'output' (speakers) or 'input' (microphone).",
    parameters={
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "'output' for speakers, 'input' for microphone."},
            "mute": {"type": "boolean", "description": "True to mute, False to unmute. Default: toggle."},
        },
        "required": ["target"],
    },
)
def toggle_mute(target: str = "output", mute: bool = None, **kwargs) -> str:
    try:
        if target == "input":
            action = "1" if mute is True else ("0" if mute is False else "toggle")
            subprocess.run(["pactl", "set-source-mute", "@DEFAULT_SOURCE@", action], check=True, capture_output=True)
            return f"Microphone {'muted' if mute else 'unmuted' if mute is False else 'toggled'}."
        else:
            action = "1" if mute is True else ("0" if mute is False else "toggle")
            subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", action], check=True, capture_output=True)
            return f"Speakers {'muted' if mute else 'unmuted' if mute is False else 'toggled'}."
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════
#  GPU INFORMATION
# ═══════════════════════════════════════════════════════════════

@skill(
    name="get_gpu_info",
    description="Gets GPU/graphics card information including driver, memory, and utilization.",
    parameters={"type": "object", "properties": {}},
)
def get_gpu_info(**kwargs) -> str:
    parts = []
    # Try lspci for GPU identification
    try:
        r = subprocess.run(["lspci"], capture_output=True, text=True, timeout=5)
        gpus = [line for line in r.stdout.split("\n") if "VGA" in line or "3D" in line or "Display" in line]
        if gpus:
            parts.append("GPU Hardware:\n" + "\n".join(f"  {g}" for g in gpus))
    except Exception:
        pass

    # Try nvidia-smi for NVIDIA GPUs
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,memory.used,utilization.gpu,temperature.gpu",
                           "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            parts.append(f"NVIDIA GPU:\n  {r.stdout.strip()}")
    except FileNotFoundError:
        pass

    # Try intel_gpu_top info
    try:
        r = subprocess.run(["sudo", "intel_gpu_frequency", "-g"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            parts.append(f"Intel GPU Frequency:\n  {r.stdout.strip()}")
    except FileNotFoundError:
        pass

    # Try glxinfo for OpenGL
    try:
        r = subprocess.run(["glxinfo", "-B"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            parts.append(f"OpenGL Info:\n{r.stdout}")
    except FileNotFoundError:
        pass

    return "\n".join(parts) if parts else "No GPU information available."


# ═══════════════════════════════════════════════════════════════
#  CPU GOVERNOR / FREQUENCY CONTROL
# ═══════════════════════════════════════════════════════════════

@skill(
    name="get_cpu_governor",
    description="Gets the current CPU frequency governor and available governors.",
    parameters={"type": "object", "properties": {}},
)
def get_cpu_governor(**kwargs) -> str:
    parts = []
    try:
        r = subprocess.run(["cat", "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"],
                          capture_output=True, text=True, timeout=3)
        parts.append(f"Current Governor: {r.stdout.strip()}")
    except Exception:
        pass
    try:
        r = subprocess.run(["cat", "/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors"],
                          capture_output=True, text=True, timeout=3)
        parts.append(f"Available: {r.stdout.strip()}")
    except Exception:
        pass
    try:
        r = subprocess.run(["cat", "/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"],
                          capture_output=True, text=True, timeout=3)
        freq = int(r.stdout.strip()) / 1000
        parts.append(f"Current Frequency: {freq:.0f} MHz")
    except Exception:
        pass
    try:
        r = subprocess.run(["cat", "/sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq"],
                          capture_output=True, text=True, timeout=3)
        r2 = subprocess.run(["cat", "/sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq"],
                           capture_output=True, text=True, timeout=3)
        min_f = int(r.stdout.strip()) / 1000
        max_f = int(r2.stdout.strip()) / 1000
        parts.append(f"Range: {min_f:.0f} MHz — {max_f:.0f} MHz")
    except Exception:
        pass
    return "\n".join(parts) if parts else "Cannot read CPU governor info."


@skill(
    name="set_cpu_governor",
    description="Sets the CPU frequency governor. Common options: 'performance', 'powersave', 'schedutil', 'ondemand'.",
    parameters={
        "type": "object",
        "properties": {
            "governor": {"type": "string", "description": "Governor name: 'performance', 'powersave', 'schedutil', 'ondemand'."},
        },
        "required": ["governor"],
    },
)
def set_cpu_governor(governor: str, **kwargs) -> str:
    try:
        # Count CPUs
        cpu_count = os.cpu_count() or 1
        for i in range(cpu_count):
            subprocess.run(
                ["sudo", "bash", "-c", f"echo {governor} > /sys/devices/system/cpu/cpu{i}/cpufreq/scaling_governor"],
                check=True, capture_output=True, timeout=5
            )
        return f"CPU governor set to '{governor}' on all {cpu_count} cores."
    except subprocess.CalledProcessError as e:
        return f"Failed to set governor: {e.stderr}"
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════
#  STORAGE MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@skill(
    name="mount_device",
    description="Mounts a storage device (USB drive, partition) to a specified mount point.",
    parameters={
        "type": "object",
        "properties": {
            "device": {"type": "string", "description": "Device path like '/dev/sdb1'."},
            "mount_point": {"type": "string", "description": "Where to mount, e.g. '/mnt/usb'. Default: auto."},
        },
        "required": ["device"],
    },
)
def mount_device(device: str, mount_point: str = "", **kwargs) -> str:
    if not mount_point:
        mount_point = f"/mnt/{os.path.basename(device)}"
    try:
        os.makedirs(mount_point, exist_ok=True)
        subprocess.run(["sudo", "mount", device, mount_point], check=True, capture_output=True, timeout=10)
        return f"Mounted {device} at {mount_point}."
    except subprocess.CalledProcessError as e:
        return f"Mount failed: {e.stderr}"
    except Exception as e:
        return f"Error: {e}"


@skill(
    name="unmount_device",
    description="Unmounts a storage device or mount point.",
    parameters={
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "Device path or mount point to unmount."},
        },
        "required": ["target"],
    },
)
def unmount_device(target: str, **kwargs) -> str:
    try:
        subprocess.run(["sudo", "umount", target], check=True, capture_output=True, timeout=10)
        return f"Unmounted {target}."
    except subprocess.CalledProcessError as e:
        return f"Unmount failed: {e.stderr}"
    except Exception as e:
        return f"Error: {e}"


@skill(
    name="get_storage_info",
    description="Gets detailed storage information: all mounted filesystems, usage, and types.",
    parameters={"type": "object", "properties": {}},
)
def get_storage_info(**kwargs) -> str:
    try:
        r = subprocess.run(["df", "-hT"], capture_output=True, text=True, timeout=5)
        return f"Filesystems:\n{r.stdout}"
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════
#  BLUETOOTH DEVICE MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@skill(
    name="bluetooth_scan",
    description="Scans for nearby Bluetooth devices.",
    parameters={"type": "object", "properties": {}},
)
def bluetooth_scan(**kwargs) -> str:
    try:
        subprocess.run(["bluetoothctl", "power", "on"], capture_output=True, text=True, timeout=5)
        r = subprocess.run(["bluetoothctl", "--timeout", "8", "scan", "on"],
                          capture_output=True, text=True, timeout=12)
        devices = subprocess.run(["bluetoothctl", "devices"], capture_output=True, text=True, timeout=5)
        return f"Bluetooth Devices Found:\n{devices.stdout}" if devices.stdout.strip() else "No Bluetooth devices found nearby."
    except Exception as e:
        return f"Bluetooth scan error: {e}"


@skill(
    name="bluetooth_pair",
    description="Pairs with a Bluetooth device by MAC address.",
    parameters={
        "type": "object",
        "properties": {
            "mac_address": {"type": "string", "description": "MAC address like 'AA:BB:CC:DD:EE:FF'."},
        },
        "required": ["mac_address"],
    },
)
def bluetooth_pair(mac_address: str, **kwargs) -> str:
    try:
        subprocess.run(["bluetoothctl", "power", "on"], capture_output=True, timeout=3)
        r = subprocess.run(["bluetoothctl", "pair", mac_address], capture_output=True, text=True, timeout=15)
        return f"Pair result: {r.stdout}\n{r.stderr}"
    except Exception as e:
        return f"Pairing error: {e}"


@skill(
    name="bluetooth_connect",
    description="Connects to a paired Bluetooth device by MAC address.",
    parameters={
        "type": "object",
        "properties": {
            "mac_address": {"type": "string", "description": "MAC address like 'AA:BB:CC:DD:EE:FF'."},
        },
        "required": ["mac_address"],
    },
)
def bluetooth_connect(mac_address: str, **kwargs) -> str:
    try:
        r = subprocess.run(["bluetoothctl", "connect", mac_address], capture_output=True, text=True, timeout=10)
        return f"Connect result: {r.stdout}\n{r.stderr}"
    except Exception as e:
        return f"Connect error: {e}"


@skill(
    name="bluetooth_disconnect",
    description="Disconnects a connected Bluetooth device by MAC address.",
    parameters={
        "type": "object",
        "properties": {
            "mac_address": {"type": "string", "description": "MAC address to disconnect."},
        },
        "required": ["mac_address"],
    },
)
def bluetooth_disconnect(mac_address: str, **kwargs) -> str:
    try:
        r = subprocess.run(["bluetoothctl", "disconnect", mac_address], capture_output=True, text=True, timeout=10)
        return f"Disconnect result: {r.stdout}"
    except Exception as e:
        return f"Disconnect error: {e}"


@skill(
    name="list_paired_bluetooth",
    description="Lists all paired Bluetooth devices.",
    parameters={"type": "object", "properties": {}},
)
def list_paired_bluetooth(**kwargs) -> str:
    try:
        r = subprocess.run(["bluetoothctl", "devices", "Paired"], capture_output=True, text=True, timeout=5)
        return f"Paired Devices:\n{r.stdout}" if r.stdout.strip() else "No paired devices."
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════
#  KEYBOARD BACKLIGHT
# ═══════════════════════════════════════════════════════════════

@skill(
    name="set_keyboard_backlight",
    description="Sets the keyboard backlight brightness. Level: 0 (off) to max (usually 2 or 3).",
    parameters={
        "type": "object",
        "properties": {
            "level": {"type": "integer", "description": "Brightness level: 0 (off) to max. Typically 0-2 or 0-3."},
        },
        "required": ["level"],
    },
)
def set_keyboard_backlight(level: int, **kwargs) -> str:
    # Try multiple methods
    paths = [
        "/sys/class/leds/tpacpi::kbd_backlight/brightness",
        "/sys/class/leds/asus::kbd_backlight/brightness",
        "/sys/class/leds/smc::kbd_backlight/brightness",
    ]
    # Also try finding any kbd_backlight
    import glob
    paths.extend(glob.glob("/sys/class/leds/*kbd_backlight/brightness"))

    for path in paths:
        if os.path.exists(path):
            try:
                subprocess.run(["sudo", "bash", "-c", f"echo {level} > {path}"],
                              check=True, capture_output=True, timeout=3)
                return f"Keyboard backlight set to {level}."
            except Exception:
                continue
    # Try brightnessctl
    try:
        subprocess.run(["brightnessctl", "--device=*kbd_backlight", "set", str(level)],
                      check=True, capture_output=True, timeout=5)
        return f"Keyboard backlight set to {level}."
    except Exception:
        pass
    return "No keyboard backlight device found."


# ═══════════════════════════════════════════════════════════════
#  TOUCHPAD CONTROL
# ═══════════════════════════════════════════════════════════════

@skill(
    name="toggle_touchpad",
    description="Enables or disables the laptop touchpad.",
    parameters={
        "type": "object",
        "properties": {
            "state": {"type": "string", "description": "'on' to enable, 'off' to disable."},
        },
        "required": ["state"],
    },
)
def toggle_touchpad(state: str, **kwargs) -> str:
    try:
        # Find touchpad device ID
        r = subprocess.run(["xinput", "list"], capture_output=True, text=True, timeout=5)
        touchpad_id = None
        for line in r.stdout.split("\n"):
            if "touchpad" in line.lower() or "trackpad" in line.lower():
                parts = line.split("id=")
                if len(parts) > 1:
                    touchpad_id = parts[1].split()[0]
                    break
        if not touchpad_id:
            return "No touchpad device found."

        enable = "1" if state.lower() == "on" else "0"
        subprocess.run(["xinput", "set-prop", touchpad_id, "Device Enabled", enable],
                      check=True, capture_output=True, timeout=5)
        return f"Touchpad {'enabled' if state == 'on' else 'disabled'}."
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════
#  NETWORK ADVANCED
# ═══════════════════════════════════════════════════════════════

@skill(
    name="scan_wifi_networks",
    description="Scans and lists available Wi-Fi networks with signal strength.",
    parameters={"type": "object", "properties": {}},
)
def scan_wifi_networks(**kwargs) -> str:
    try:
        subprocess.run(["sudo", "nmcli", "device", "wifi", "rescan"], capture_output=True, timeout=10)
        r = subprocess.run(["nmcli", "-f", "SSID,SIGNAL,SECURITY,FREQ", "device", "wifi", "list"],
                          capture_output=True, text=True, timeout=10)
        return f"Wi-Fi Networks:\n{r.stdout}"
    except Exception as e:
        return f"Error scanning: {e}"


@skill(
    name="connect_wifi",
    description="Connects to a specific Wi-Fi network by SSID and password.",
    parameters={
        "type": "object",
        "properties": {
            "ssid": {"type": "string", "description": "Wi-Fi network name (SSID)."},
            "password": {"type": "string", "description": "Wi-Fi password. Omit for open networks."},
        },
        "required": ["ssid"],
    },
)
def connect_wifi(ssid: str, password: str = "", **kwargs) -> str:
    try:
        cmd = ["sudo", "nmcli", "device", "wifi", "connect", ssid]
        if password:
            cmd.extend(["password", password])
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return r.stdout if r.returncode == 0 else f"Failed: {r.stderr}"
    except Exception as e:
        return f"Error: {e}"


@skill(
    name="get_network_speed",
    description="Tests internet download/upload speed.",
    parameters={"type": "object", "properties": {}},
)
def get_network_speed(**kwargs) -> str:
    try:
        # Quick ping test first
        r = subprocess.run(["ping", "-c", "3", "8.8.8.8"],
                          capture_output=True, text=True, timeout=10)
        ping_line = [l for l in r.stdout.split("\n") if "avg" in l]
        ping_info = ping_line[0] if ping_line else "Ping test failed"

        # Basic speed test via curl
        r = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{speed_download}", "https://speed.cloudflare.com/__down?bytes=10000000"],
            capture_output=True, text=True, timeout=30
        )
        speed_bps = float(r.stdout)
        speed_mbps = (speed_bps * 8) / 1_000_000

        return f"Ping: {ping_info}\nDownload: {speed_mbps:.1f} Mbps"
    except Exception as e:
        return f"Speed test error: {e}"


# ═══════════════════════════════════════════════════════════════
#  SERVICE MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@skill(
    name="manage_service",
    description="Start, stop, restart, or check status of a systemd service.",
    parameters={
        "type": "object",
        "properties": {
            "service_name": {"type": "string", "description": "Service name (e.g. 'bluetooth', 'cups', 'ssh')."},
            "action": {"type": "string", "description": "'start', 'stop', 'restart', 'status', 'enable', 'disable'."},
        },
        "required": ["service_name", "action"],
    },
)
def manage_service(service_name: str, action: str, **kwargs) -> str:
    valid = ("start", "stop", "restart", "status", "enable", "disable")
    if action not in valid:
        return f"Invalid action. Use: {', '.join(valid)}"
    try:
        r = subprocess.run(["sudo", "systemctl", action, service_name],
                          capture_output=True, text=True, timeout=15)
        output = r.stdout or r.stderr
        return f"Service {service_name} {action}: {output.strip()}" if output.strip() else f"Service {service_name}: {action} OK."
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════
#  SWAP & RAM MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@skill(
    name="manage_swap",
    description="View, clear, or resize swap space.",
    parameters={
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "'info' to view, 'clear' to flush swap (frees cached data), 'off' to disable, 'on' to re-enable."},
        },
        "required": ["action"],
    },
)
def manage_swap(action: str, **kwargs) -> str:
    if action == "info":
        try:
            r = subprocess.run(["swapon", "--show"], capture_output=True, text=True, timeout=5)
            free = subprocess.run(["free", "-h"], capture_output=True, text=True, timeout=5)
            return f"Swap Devices:\n{r.stdout}\n{free.stdout}"
        except Exception as e:
            return f"Error: {e}"
    elif action == "clear":
        try:
            subprocess.run(["sudo", "swapoff", "-a"], check=True, capture_output=True, timeout=30)
            subprocess.run(["sudo", "swapon", "-a"], check=True, capture_output=True, timeout=10)
            return "Swap cleared and re-enabled."
        except Exception as e:
            return f"Error clearing swap: {e}"
    elif action == "off":
        try:
            subprocess.run(["sudo", "swapoff", "-a"], check=True, capture_output=True, timeout=30)
            return "All swap disabled."
        except Exception as e:
            return f"Error: {e}"
    elif action == "on":
        try:
            subprocess.run(["sudo", "swapon", "-a"], check=True, capture_output=True, timeout=10)
            return "Swap re-enabled."
        except Exception as e:
            return f"Error: {e}"
    return f"Unknown action: {action}. Use 'info', 'clear', 'off', or 'on'."


@skill(
    name="drop_caches",
    description="Drops the Linux page cache, dentries, and inodes to free up RAM. Use with caution.",
    parameters={"type": "object", "properties": {}},
)
def drop_caches(**kwargs) -> str:
    try:
        subprocess.run(["sudo", "bash", "-c", "sync; echo 3 > /proc/sys/vm/drop_caches"],
                      check=True, capture_output=True, timeout=10)
        import psutil
        mem = psutil.virtual_memory()
        return f"Caches dropped. RAM now: {mem.percent}% used ({mem.available / (1024**3):.1f} GB free)"
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════
#  FAN CONTROL
# ═══════════════════════════════════════════════════════════════

@skill(
    name="get_fan_speed",
    description="Reads current fan RPM from sensors.",
    parameters={"type": "object", "properties": {}},
)
def get_fan_speed(**kwargs) -> str:
    try:
        r = subprocess.run(["sensors"], capture_output=True, text=True, timeout=5)
        fan_lines = [l for l in r.stdout.split("\n") if "fan" in l.lower() or "RPM" in l]
        if fan_lines:
            return "Fan Status:\n" + "\n".join(f"  {l.strip()}" for l in fan_lines)
        return "No fan speed data found in sensors output."
    except FileNotFoundError:
        return "lm-sensors not installed."
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════════
#  CLIPBOARD
# ═══════════════════════════════════════════════════════════════

@skill(
    name="get_clipboard",
    description="Gets the current clipboard content.",
    parameters={"type": "object", "properties": {}},
)
def get_clipboard(**kwargs) -> str:
    try:
        r = subprocess.run(["xclip", "-selection", "clipboard", "-o"],
                          capture_output=True, text=True, timeout=5)
        content = r.stdout[:2000]  # Limit
        return f"Clipboard content:\n{content}" if content else "Clipboard is empty."
    except FileNotFoundError:
        return "xclip not installed. Install with: sudo apt install xclip"
    except Exception as e:
        return f"Error: {e}"


@skill(
    name="set_clipboard",
    description="Copies text to the system clipboard.",
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to copy to clipboard."},
        },
        "required": ["text"],
    },
)
def set_clipboard(text: str, **kwargs) -> str:
    try:
        p = subprocess.Popen(["xclip", "-selection", "clipboard"],
                            stdin=subprocess.PIPE)
        p.communicate(text.encode(), timeout=5)
        return f"Copied {len(text)} characters to clipboard."
    except FileNotFoundError:
        return "xclip not installed."
    except Exception as e:
        return f"Error: {e}"


logger.info("Hardware Control skills loaded.")
