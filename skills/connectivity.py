import logging
import subprocess
from skills import skill

logger = logging.getLogger("jarvis.skills.connectivity")


@skill(
    name="toggle_wifi",
    description="Turn the Wi-Fi radio on or off globally.",
    parameters={
        "type": "object",
        "properties": {
            "state": {
                "type": "string",
                "description": "Desired state: 'on' or 'off'.",
            }
        },
        "required": ["state"],
    },
)
def toggle_wifi(state: str, **kwargs) -> str:
    """Takes 'on' or 'off' as state."""
    state = state.lower()
    if state not in ["on", "off"]:
        return "Error: state must be 'on' or 'off'"
    try:
        subprocess.run(["nmcli", "radio", "wifi", state], check=True, text=True, capture_output=True)
        return f"Wi-Fi successfully turned {state}."
    except Exception as e:
        return f"Error toggling Wi-Fi: {e}"


@skill(
    name="toggle_bluetooth",
    description="Turn the Bluetooth radio on or off globally.",
    parameters={
        "type": "object",
        "properties": {
            "state": {
                "type": "string",
                "description": "Desired state: 'on' or 'off'.",
            }
        },
        "required": ["state"],
    },
)
def toggle_bluetooth(state: str, **kwargs) -> str:
    """Takes 'on' or 'off' as state."""
    state = state.lower()
    if state not in ["on", "off"]:
        return "Error: state must be 'on' or 'off'"
    try:
        rfkill_state = "unblock" if state == "on" else "block"
        subprocess.run(["rfkill", rfkill_state, "bluetooth"], check=True, text=True, capture_output=True)
        
        if state == "on":
            # additionally try to ensure bluetoothctl powers on the default controller
            subprocess.run(["bluetoothctl", "power", "on"], check=False, text=True, capture_output=True)
            
        return f"Bluetooth successfully turned {state}."
    except Exception as e:
        return f"Error toggling Bluetooth: {e}"

logger.info("Connectivity skills loaded.")
