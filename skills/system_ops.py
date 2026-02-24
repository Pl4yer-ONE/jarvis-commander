"""
Jarvis Skills — System Operations

Provides skills for querying and controlling system state:
time, CPU, memory, disk, battery, volume, brightness as well as 
raw hardware diagnostic tools.
"""

import datetime
import os
import platform
import shutil
import subprocess

import psutil

from skills import skill


# ── Time ─────────────────────────────────────────────────────

@skill(
    name="get_time",
    description="Returns the current date, time, and day of the week.",
)
def get_time(**kwargs) -> str:
    now = datetime.datetime.now()
    return now.strftime("It is %A, %B %d, %Y at %I:%M %p")


# ── System Info ──────────────────────────────────────────────

@skill(
    name="get_system_info",
    description="Returns CPU usage, RAM usage, disk usage, and system uptime.",
)
def get_system_info(**kwargs) -> str:
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_freq = psutil.cpu_freq()
    mem = psutil.virtual_memory()
    disk = shutil.disk_usage("/")
    uptime_seconds = (
        datetime.datetime.now() - datetime.datetime.fromtimestamp(psutil.boot_time())
    ).total_seconds()

    hours, remainder = divmod(int(uptime_seconds), 3600)
    minutes, _ = divmod(remainder, 60)

    return (
        f"CPU: {cpu_percent}% usage ({cpu_freq.current:.0f} MHz)\n"
        f"RAM: {mem.percent}% used ({mem.used / (1024**3):.1f} GB / {mem.total / (1024**3):.1f} GB)\n"
        f"Disk: {disk.used / (1024**3):.1f} GB used / {disk.total / (1024**3):.1f} GB total "
        f"({disk.free / (1024**3):.1f} GB free)\n"
        f"Uptime: {hours}h {minutes}m\n"
        f"OS: {platform.platform()}"
    )


# ── Battery ──────────────────────────────────────────────────

@skill(
    name="get_battery",
    description="Returns the current battery percentage and charging status.",
)
def get_battery(**kwargs) -> str:
    battery = psutil.sensors_battery()
    if battery is None:
        return "No battery detected (desktop system or battery not accessible)."

    status = "charging" if battery.power_plugged else "discharging"
    time_left = ""
    if battery.secsleft > 0 and not battery.power_plugged:
        hours, remainder = divmod(battery.secsleft, 3600)
        minutes, _ = divmod(remainder, 60)
        time_left = f", approximately {int(hours)}h {int(minutes)}m remaining"

    return f"Battery: {battery.percent:.0f}% ({status}{time_left})"


# ── Volume Control ───────────────────────────────────────────

@skill(
    name="set_volume",
    description="Sets the system audio volume to a percentage (0-100). Use 'mute' or 'unmute' as special values.",
    parameters={
        "type": "object",
        "properties": {
            "level": {
                "type": "string",
                "description": "Volume level: a number 0-100, 'mute', or 'unmute'."
            }
        },
        "required": ["level"]
    }
)
def set_volume(level: str = "50", **kwargs) -> str:
    level = level.strip().lower()

    if level == "mute":
        subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"], check=True)
        return "Audio muted."
    elif level == "unmute":
        subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"], check=True)
        return "Audio unmuted."
    else:
        try:
            vol = max(0, min(100, int(level)))
        except ValueError:
            return f"Invalid volume level: '{level}'. Use a number 0-100, 'mute', or 'unmute'."

        subprocess.run(
            ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{vol}%"],
            check=True,
        )
        return f"Volume set to {vol}%."


# ── Brightness Control ──────────────────────────────────────

@skill(
    name="set_brightness",
    description="Sets the screen brightness to a percentage (1-100).",
    parameters={
        "type": "object",
        "properties": {
            "level": {
                "type": "integer",
                "description": "Brightness level from 1 to 100."
            }
        },
        "required": ["level"]
    }
)
def set_brightness(level: int = 50, **kwargs) -> str:
    level = max(1, min(100, int(level)))

    try:
        result = subprocess.run(
            ["xrandr", "--listmonitors"],
            capture_output=True, text=True, check=True,
        )
        lines = result.stdout.strip().split("\n")
        if len(lines) > 1:
            monitor = lines[1].split()[-1]
            brightness = level / 100.0
            subprocess.run(
                ["xrandr", "--output", monitor, "--brightness", str(brightness)],
                check=True,
            )
            return f"Brightness set to {level}% (via xrandr)."
    except (subprocess.CalledProcessError, FileNotFoundError, IndexError):
        pass

    try:
        subprocess.run(
            ["brightnessctl", "set", f"{level}%"],
            check=True, capture_output=True,
        )
        return f"Brightness set to {level}% (via brightnessctl)."
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    return (
        f"Could not set brightness to {level}%. "
        "Try installing brightnessctl: sudo apt install brightnessctl"
    )


# ── Network Info ─────────────────────────────────────────────

@skill(
    name="get_network_info",
    description="Returns current network connection status, IP addresses, and Wi-Fi SSID.",
)
def get_network_info(**kwargs) -> str:
    info_parts = []
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()

    for iface, addr_list in addrs.items():
        if iface == "lo":
            continue
        is_up = stats.get(iface, None)
        if is_up and is_up.isup:
            for addr in addr_list:
                if addr.family.name == "AF_INET":
                    info_parts.append(f"{iface}: {addr.address}")

    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"],
            capture_output=True, text=True, check=True,
        )
        for line in result.stdout.strip().split("\n"):
            if line.startswith("yes:"):
                ssid = line.split(":", 1)[1]
                info_parts.append(f"Wi-Fi: {ssid}")
                break
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    return "\n".join(info_parts) if info_parts else "No active network connections found."


# ── Process List ─────────────────────────────────────────────

@skill(
    name="list_running_processes",
    description="Lists the top active processes by CPU or memory usage.",
    parameters={
        "type": "object",
        "properties": {
            "sort_by": {"type": "string", "description": "'cpu' or 'memory'"},
            "count": {"type": "integer"}
        }
    }
)
def list_running_processes(sort_by: str = "cpu", count: int = 10, **kwargs) -> str:
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            info = p.info
            procs.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    key = "cpu_percent" if sort_by.lower() == "cpu" else "memory_percent"
    procs.sort(key=lambda x: x.get(key, 0) or 0, reverse=True)

    lines = [f"Top {count} processes by {sort_by}:"]
    for p in procs[:count]:
        lines.append(
            f"  PID {p['pid']:>6} | {p['name']:<25} | "
            f"CPU: {p.get('cpu_percent', 0):>5.1f}% | "
            f"MEM: {p.get('memory_percent', 0):>5.1f}%"
        )

    return "\n".join(lines)


# ── Hardware Diagnostics ─────────────────────────────────────

@skill(
    name="get_hardware_info",
    description="Returns detailed physical hardware information (CPU architecture, RAM, motherboard, disks).",
)
def get_hardware_info(**kwargs) -> str:
    try:
        result = subprocess.run(["sudo", "lshw", "-short"], capture_output=True, text=True, check=True)
        return f"Hardware Profile:\n{result.stdout}"
    except Exception as e:
        return f"Failed to retrieve hardware profile: {e}"

@skill(
    name="get_usb_devices",
    description="Lists all physical USB devices currently connected to the machine.",
)
def get_usb_devices(**kwargs) -> str:
    try:
        result = subprocess.run(["lsusb"], capture_output=True, text=True, check=True)
        return f"USB Devices:\n{result.stdout}"
    except Exception as e:
        return f"Failed to list USB devices: {e}"

@skill(
    name="get_cpu_thermals",
    description="Returns raw physical sensory data for CPU/GPU core temperatures and fan speeds.",
)
def get_cpu_thermals(**kwargs) -> str:
    try:
        result = subprocess.run(["sensors"], capture_output=True, text=True, check=True)
        return f"Thermal Sensors:\n{result.stdout}"
    except FileNotFoundError:
        return "The 'sensors' command is not installed. You should run: sudo apt install lm-sensors"
    except Exception as e:
        return f"Failed to read thermal sensors: {e}"

@skill(
    name="get_disk_partitions",
    description="Lists all physical drive block devices, SSDs, NVMes, and storage partitions.",
)
def get_disk_partitions(**kwargs) -> str:
    try:
        result = subprocess.run(["lsblk", "-o", "NAME,SIZE,TYPE,MOUNTPOINT"], capture_output=True, text=True, check=True)
        return f"Block Devices:\n{result.stdout}"
    except Exception as e:
        return f"Failed to list block devices: {e}"
