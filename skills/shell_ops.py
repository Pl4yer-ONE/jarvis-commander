"""
Jarvis Skills — Shell Operations

Provides skills for running terminal commands and installing packages.
Includes safety checks to prevent destructive commands.
"""

import logging
import os
import subprocess

from skills import skill

logger = logging.getLogger("jarvis.skills.shell")

# ── Dangerous command patterns ───────────────────────────────
# These require explicit confirmation (handled at the brain level)

DANGEROUS_PATTERNS = [
    "rm -rf /",
    "rm -rf /*",
    "rm -rf ~",
    "rm -rf $HOME",
    "dd if=",
    "mkfs",
    ":(){",
    "fork bomb",
    "> /dev/sda",
    "chmod -R 777 /",
    "chown -R",
    "shutdown",
    "reboot",
    "poweroff",
    "halt",
    "init 0",
    "init 6",
    "mv /* ",
    "wget | sh",
    "curl | sh",
    "wget | bash",
    "curl | bash",
]

WARNING_PATTERNS = [
    "rm -rf",
    "rm -r",
    "sudo rm",
    "chmod",
    "chown",
    "sudo ",
    "systemctl stop",
    "systemctl disable",
    "kill -9",
    "killall",
    "pkill",
]


def _assess_command_risk(command: str) -> tuple[str, str]:
    """
    Assess the risk level of a command.
    Returns: (risk_level, reason)
        risk_level: 'blocked', 'dangerous', 'warning', 'safe'
    """
    # Import config to check unsafe mode
    try:
        from config import load_config
        config = load_config()
        if config.unsafe_mode:
            # In unsafe mode, only log warnings — never block
            cmd_lower = command.lower().strip()
            for pattern in DANGEROUS_PATTERNS:
                if pattern in cmd_lower:
                    logger.warning("⚠️  Running dangerous command (UNSAFE_MODE): %s", command)
                    return "safe", ""
            return "safe", ""
    except Exception:
        pass

    cmd_lower = command.lower().strip()

    for pattern in DANGEROUS_PATTERNS:
        if pattern in cmd_lower:
            return "blocked", f"Blocked: contains dangerous pattern '{pattern}'"

    for pattern in WARNING_PATTERNS:
        if pattern in cmd_lower:
            return "warning", f"Warning: contains potentially destructive pattern '{pattern}'"

    return "safe", ""


# ── Run Command ──────────────────────────────────────────────

@skill(
    name="run_command",
    description=(
        "Runs a shell command and returns its output. "
        "Use for system administration, package management, debugging, etc. "
        "Dangerous commands (rm -rf /, dd, mkfs, etc.) are blocked for safety. "
        "Commands run with the current user's permissions (not root unless sudo is used)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute.",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds. Default: 30.",
            },
            "working_directory": {
                "type": "string",
                "description": "Working directory for the command. Default: home directory.",
            },
        },
        "required": ["command"],
    },
)
def run_command(
    command: str, timeout: int = 30, working_directory: str = "", **kwargs
) -> str:
    command = command.strip()

    if not command:
        return "No command provided."

    # Safety check
    risk, reason = _assess_command_risk(command)

    if risk == "blocked":
        return (
            f"🛑 BLOCKED: This command is too dangerous to execute.\n"
            f"Reason: {reason}\n"
            f"If you really need to run this, do it manually in a terminal."
        )

    if risk == "warning":
        logger.warning("⚠️  Executing potentially risky command: %s (%s)", command, reason)

    # Resolve working directory
    cwd = working_directory.strip() or os.path.expanduser("~")
    if not os.path.isdir(cwd):
        cwd = os.path.expanduser("~")

    timeout = min(max(timeout, 5), 120)  # Clamp between 5 and 120 seconds

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env={**os.environ, "PAGER": "cat", "GIT_PAGER": "cat"},
        )

        output_parts = []

        if result.stdout.strip():
            stdout = result.stdout.strip()
            # Truncate very long output
            if len(stdout) > 3000:
                stdout = stdout[:3000] + f"\n... (truncated, {len(result.stdout)} total characters)"
            output_parts.append(stdout)

        if result.stderr.strip():
            stderr = result.stderr.strip()
            if len(stderr) > 1000:
                stderr = stderr[:1000] + "\n... (stderr truncated)"
            output_parts.append(f"[stderr] {stderr}")

        if result.returncode != 0:
            output_parts.append(f"[exit code: {result.returncode}]")

        return "\n".join(output_parts) if output_parts else "(no output)"

    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout} seconds."
    except Exception as e:
        return f"Command execution failed: {e}"


# ── Install Package ──────────────────────────────────────────

@skill(
    name="install_package",
    description="Installs a system package via apt or a Python package via pip.",
    parameters={
        "type": "object",
        "properties": {
            "package_name": {
                "type": "string",
                "description": "Name of the package to install.",
            },
            "package_manager": {
                "type": "string",
                "description": "'apt' for system packages, 'pip' for Python packages. Default: 'pip'.",
            },
        },
        "required": ["package_name"],
    },
)
def install_package(
    package_name: str, package_manager: str = "pip", **kwargs
) -> str:
    package_name = package_name.strip()

    if not package_name:
        return "No package name provided."

    # Basic sanitization
    if ";" in package_name or "&&" in package_name or "|" in package_name:
        return "Invalid package name. No shell metacharacters allowed."

    if package_manager == "apt":
        cmd = f"sudo apt install -y {package_name}"
    elif package_manager == "pip":
        cmd = f"pip install {package_name}"
    else:
        return f"Unknown package manager: {package_manager}. Use 'apt' or 'pip'."

    logger.info("Installing package: %s (via %s)", package_name, package_manager)

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode == 0:
            return f"Successfully installed {package_name} via {package_manager}."
        else:
            error = result.stderr.strip()[-500:] if result.stderr else "Unknown error"
            return f"Installation failed: {error}"

    except subprocess.TimeoutExpired:
        return f"Installation of {package_name} timed out after 120 seconds."
    except Exception as e:
        return f"Installation failed: {e}"
