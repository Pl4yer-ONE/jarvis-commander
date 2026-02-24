import logging
import subprocess
from skills import skill

logger = logging.getLogger("jarvis.skills.desktop_control")


@skill(
    name="type_keys",
    description="Simulate typing on the keyboard or triggering hotkeys using xdotool. Format for shortcuts: 'ctrl+c', 'alt+Tab', 'super+d'. Format for literal typing: Make sure NOT to use combined keys. If typing a sentence, just use the 'type_text' skill instead.",
    parameters={
        "type": "object",
        "properties": {
            "keys": {
                "type": "string",
                "description": "The key combination to trigger (e.g. 'ctrl+c', 'alt+Tab', 'super+d', 'Return').",
            }
        },
        "required": ["keys"],
    },
)
def type_keys(keys: str, **kwargs) -> str:
    try:
        subprocess.run(["xdotool", "key", keys], check=True, text=True, capture_output=True)
        return f"Successfully triggered key sequence: {keys}"
    except Exception as e:
        return f"Error executing keys '{keys}': {e}"
        

@skill(
    name="type_text",
    description="Simulate literally typing a string of text on the keyboard using xdotool.",
    parameters={
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The text string to type out on the keyboard.",
            }
        },
        "required": ["text"],
    },
)
def type_text(text: str, **kwargs) -> str:
    try:
        subprocess.run(["xdotool", "type", text], check=True, text=True, capture_output=True)
        return f"Successfully typed text: {text}"
    except Exception as e:
        return f"Error typing text: {e}"


@skill(
    name="move_mouse",
    description="Move the mouse cursor to a specific absolute X, Y screen coordinate using xdotool.",
    parameters={
        "type": "object",
        "properties": {
            "x": {
                "type": "integer",
                "description": "The X (horizontal) screen coordinate to move to.",
            },
            "y": {
                "type": "integer",
                "description": "The Y (vertical) screen coordinate to move to.",
            },
        },
        "required": ["x", "y"],
    },
)
def move_mouse(x: int, y: int, **kwargs) -> str:
    try:
        subprocess.run(["xdotool", "mousemove", str(x), str(y)], check=True, text=True, capture_output=True)
        return f"Moved mouse to ({x}, {y})"
    except Exception as e:
        return f"Error moving mouse: {e}"


@skill(
    name="click_mouse",
    description="Click the mouse at its current location using xdotool. button: 1 for left click, 2 for middle click, 3 for right click.",
    parameters={
        "type": "object",
        "properties": {
            "button": {
                "type": "integer",
                "description": "Mouse button: 1=left, 2=middle, 3=right. Default: 1.",
            }
        },
    },
)
def click_mouse(button: int = 1, **kwargs) -> str:
    try:
        subprocess.run(["xdotool", "click", str(button)], check=True, text=True, capture_output=True)
        click_map = {1: "left", 2: "middle", 3: "right"}
        return f"Executed {click_map.get(button, button)} click."
    except Exception as e:
        return f"Error clicking mouse: {e}"


@skill(
    name="send_notification",
    description="Send a visual GUI desktop notification (Toast) to the user using notify-send.",
    parameters={
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "The notification title/summary.",
            },
            "body": {
                "type": "string",
                "description": "Optional notification body text.",
            },
        },
        "required": ["summary"],
    },
)
def send_notification(summary: str, body: str = "", **kwargs) -> str:
    try:
        cmd = ["notify-send", summary]
        if body:
            cmd.append(body)
        subprocess.run(cmd, check=True, text=True, capture_output=True)
        return f"Sent notification: '{summary}'"
    except Exception as e:
        return f"Error sending notification: {e}"

logger.info("Desktop Control skills loaded.")
