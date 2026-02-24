import logging
import subprocess
from skills import skill

logger = logging.getLogger("jarvis.skills.power_management")


@skill(
    name="suspend_system",
    description="Puts the Pop!_OS machine to sleep (Suspend to RAM). Note: This will disconnect you temporarily until woken up.",
    parameters={"type": "object", "properties": {}},
)
def suspend_system(**kwargs) -> str:
    try:
        subprocess.run(["systemctl", "suspend"], check=True, text=True, capture_output=True)
        return "System suspend initiated."
    except Exception as e:
        return f"Error suspending system: {e}"


@skill(
    name="reboot_system",
    description="Reboots the Pop!_OS machine. Note: You will be offline for a few moments while the system restarts.",
    parameters={"type": "object", "properties": {}},
)
def reboot_system(**kwargs) -> str:
    try:
        subprocess.run(["systemctl", "reboot"], check=True, text=True, capture_output=True)
        return "System reboot initiated."
    except Exception as e:
        return f"Error rebooting system: {e}"


@skill(
    name="set_power_profile",
    description="Sets the system76-power profile. Options are typically: 'Battery Life', 'Balanced', 'Performance'.",
    parameters={
        "type": "object",
        "properties": {
            "profile_name": {
                "type": "string",
                "description": "Profile name: 'Battery Life', 'Balanced', or 'Performance'.",
            }
        },
        "required": ["profile_name"],
    },
)
def set_power_profile(profile_name: str, **kwargs) -> str:
    try:
        profile_map = {
            "battery life": "battery",
            "balanced": "balanced",
            "performance": "performance"
        }
        internal_name = profile_map.get(profile_name.lower())
        
        if not internal_name:
            return f"Error: Unknown profile '{profile_name}'. Use 'Battery Life', 'Balanced', or 'Performance'."

        subprocess.run(["system76-power", "profile", internal_name], check=True, text=True, capture_output=True)
        return f"Successfully set power profile to: {profile_name.title()}"
    except FileNotFoundError:
        return "Error: system76-power not found. This might not be a System76/Pop!_OS machine, or you lack permissions."
    except Exception as e:
        return f"Error setting power profile: {e}"

logger.info("Power Management skills loaded.")
