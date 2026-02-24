"""
Jarvis Skills — Application Control

Provides skills for launching, closing, and managing applications.
"""

import shutil
import subprocess

import psutil

from skills import skill


# ── Open Application ─────────────────────────────────────────

@skill(
    name="open_application",
    description=(
        "Launches a desktop application by name. Common names: "
        "firefox, chrome, code, nautilus, terminal, calculator, text-editor, "
        "spotify, vlc, gimp, libreoffice, settings, files."
    ),
    parameters={
        "type": "object",
        "properties": {
            "app_name": {
                "type": "string",
                "description": "Name of the application to launch (e.g. 'firefox', 'code', 'nautilus').",
            }
        },
        "required": ["app_name"],
    },
)
def open_application(app_name: str, **kwargs) -> str:
    app_name = app_name.strip().lower()

    # Map common friendly names to actual executables
    app_map = {
        "browser": "firefox",
        "web browser": "firefox",
        "firefox": "firefox",
        "chrome": "google-chrome",
        "chromium": "chromium-browser",
        "code": "code",
        "vscode": "code",
        "visual studio code": "code",
        "terminal": "gnome-terminal",
        "files": "nautilus",
        "file manager": "nautilus",
        "nautilus": "nautilus",
        "calculator": "gnome-calculator",
        "calc": "gnome-calculator",
        "text editor": "gedit",
        "editor": "gedit",
        "gedit": "gedit",
        "settings": "gnome-control-center",
        "system settings": "gnome-control-center",
        "spotify": "spotify",
        "vlc": "vlc",
        "gimp": "gimp",
        "libreoffice": "libreoffice",
        "writer": "libreoffice --writer",
        "calc": "libreoffice --calc",
        "impress": "libreoffice --impress",
        "disk usage": "baobab",
        "system monitor": "gnome-system-monitor",
        "screenshot": "gnome-screenshot",
    }

    executable = app_map.get(app_name, app_name)

    # Check if executable exists
    exe_parts = executable.split()
    if not shutil.which(exe_parts[0]):
        return (
            f"Application '{app_name}' (executable: {exe_parts[0]}) not found. "
            f"It may not be installed."
        )

    try:
        subprocess.Popen(
            exe_parts,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return f"Launched {app_name}."
    except Exception as e:
        return f"Failed to launch {app_name}: {e}"


# ── Close Application ───────────────────────────────────────

@skill(
    name="close_application",
    description="Closes a running application by name. Sends a graceful termination signal first.",
    parameters={
        "type": "object",
        "properties": {
            "app_name": {
                "type": "string",
                "description": "Name of the application to close.",
            },
            "force": {
                "type": "boolean",
                "description": "If true, force-kill the application. Default: false.",
            },
        },
        "required": ["app_name"],
    },
)
def close_application(app_name: str, force: bool = False, **kwargs) -> str:
    app_name = app_name.strip().lower()
    killed = 0

    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if app_name in proc.info["name"].lower():
                if force:
                    proc.kill()
                else:
                    proc.terminate()
                killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if killed > 0:
        action = "force-killed" if force else "terminated"
        return f"Successfully {action} {killed} process(es) matching '{app_name}'."
    else:
        return f"No running process found matching '{app_name}'."


# ── Open Browser with URL ───────────────────────────────────

@skill(
    name="open_browser",
    description="Opens Firefox (or default browser) with an optional URL.",
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL to open. If omitted, opens a new tab.",
            }
        },
    },
)
def open_browser(url: str = "", **kwargs) -> str:
    cmd = ["xdg-open" if url else "firefox"]
    if url:
        cmd.append(url)

    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return f"Opened browser{' to ' + url if url else ''}."
    except Exception as e:
        return f"Failed to open browser: {e}"


# ── Open File Manager ───────────────────────────────────────

@skill(
    name="open_file_manager",
    description="Opens the file manager (Nautilus/Files) at the specified path.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory path to open. Default: home directory.",
            }
        },
    },
)
def open_file_manager(path: str = "", **kwargs) -> str:
    import os

    path = path.strip() or os.path.expanduser("~")

    if not os.path.exists(path):
        return f"Path does not exist: {path}"

    try:
        subprocess.Popen(
            ["xdg-open", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return f"Opened file manager at {path}."
    except Exception as e:
        return f"Failed to open file manager: {e}"


# ── Take Screenshot ──────────────────────────────────────────

@skill(
    name="take_screenshot",
    description="Takes a screenshot of the screen and saves it to the specified path.",
    parameters={
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "Filename for the screenshot. Default: screenshot_<timestamp>.png",
            },
            "area": {
                "type": "string",
                "description": "'full' for fullscreen, 'window' for active window, 'select' for selection. Default: 'full'.",
            },
        },
    },
)
def take_screenshot(filename: str = "", area: str = "full", **kwargs) -> str:
    import datetime
    import os

    if not filename:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"

    # Ensure it's saved in home directory by default
    if not os.path.isabs(filename):
        filename = os.path.join(os.path.expanduser("~"), "Pictures", filename)

    os.makedirs(os.path.dirname(filename), exist_ok=True)

    # Try gnome-screenshot first, then import (ImageMagick)
    flag_map = {"full": "", "window": "-w", "select": "-a"}
    flag = flag_map.get(area, "")

    cmd = ["gnome-screenshot", "-f", filename]
    if flag:
        cmd.insert(1, flag)

    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=10)
        return f"Screenshot saved to {filename}."
    except FileNotFoundError:
        # Fallback to import (ImageMagick)
        try:
            import_cmd = ["import"]
            if area == "full":
                import_cmd.extend(["-window", "root"])
            import_cmd.append(filename)
            subprocess.run(import_cmd, check=True, capture_output=True, timeout=10)
            return f"Screenshot saved to {filename} (via ImageMagick)."
        except FileNotFoundError:
            return "Neither gnome-screenshot nor ImageMagick 'import' found. Install one."
    except subprocess.TimeoutExpired:
        return "Screenshot timed out (may require user interaction for area selection)."
    except subprocess.CalledProcessError as e:
        return f"Screenshot failed: {e}"


# ── Lock Screen ──────────────────────────────────────────────

@skill(
    name="lock_screen",
    description="Locks the screen immediately.",
    parameters={"type": "object", "properties": {}},
)
def lock_screen(**kwargs) -> str:
    try:
        subprocess.run(
            ["loginctl", "lock-session"],
            check=True, capture_output=True,
        )
        return "Screen locked."
    except Exception as e:
        return f"Could not lock screen: {e}"


# ── List Windows ────────────────────────────────────────────

@skill(
    name="list_windows",
    description="Lists all open windows with their IDs, titles, and positions.",
    parameters={"type": "object", "properties": {}},
)
def list_windows(**kwargs) -> str:
    try:
        r = subprocess.run(["wmctrl", "-l", "-G"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            return f"Open Windows:\n{r.stdout}"
        # Fallback to xdotool
        r = subprocess.run(["xdotool", "search", "--onlyvisible", "--name", ""],
                          capture_output=True, text=True, timeout=5)
        if r.stdout.strip():
            window_ids = r.stdout.strip().split("\n")
            lines = []
            for wid in window_ids[:20]:
                try:
                    name = subprocess.run(["xdotool", "getwindowname", wid],
                                         capture_output=True, text=True, timeout=2).stdout.strip()
                    if name:
                        lines.append(f"  {wid}: {name}")
                except Exception:
                    pass
            return f"Open Windows ({len(lines)}):\n" + "\n".join(lines) if lines else "No windows found."
        return "No visible windows."
    except FileNotFoundError:
        return "Neither wmctrl nor xdotool found."
    except Exception as e:
        return f"Error: {e}"


# ── Focus Window ────────────────────────────────────────────

@skill(
    name="focus_window",
    description="Focuses (brings to front) a window by name or window ID.",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Window title or partial match to search for."},
            "window_id": {"type": "string", "description": "Window ID (from list_windows). Takes priority over name."},
        },
    },
)
def focus_window(name: str = "", window_id: str = "", **kwargs) -> str:
    try:
        if window_id:
            subprocess.run(["xdotool", "windowactivate", window_id],
                          check=True, capture_output=True, timeout=5)
            return f"Focused window {window_id}."
        elif name:
            r = subprocess.run(["xdotool", "search", "--name", name],
                              capture_output=True, text=True, timeout=5)
            if r.stdout.strip():
                wid = r.stdout.strip().split("\n")[0]
                subprocess.run(["xdotool", "windowactivate", wid],
                              check=True, capture_output=True, timeout=5)
                return f"Focused window '{name}' (ID: {wid})."
            return f"No window matching '{name}' found."
        return "Specify either 'name' or 'window_id'."
    except FileNotFoundError:
        return "xdotool not found."
    except Exception as e:
        return f"Error: {e}"
