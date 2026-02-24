"""
Jarvis Skills — File Operations

Provides skills for searching, reading, creating, and managing files.
"""

import os
import subprocess
from pathlib import Path

from skills import skill


# ── Search Files ─────────────────────────────────────────────

@skill(
    name="search_files",
    description="Searches for files by name or pattern in a directory. Uses the 'find' command.",
    parameters={
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Filename or glob pattern to search for (e.g. '*.pdf', 'report').",
            },
            "directory": {
                "type": "string",
                "description": "Directory to search in. Default: home directory.",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results. Default: 20.",
            },
        },
        "required": ["pattern"],
    },
)
def search_files(
    pattern: str, directory: str = "", max_results: int = 20, **kwargs
) -> str:
    directory = directory.strip() or os.path.expanduser("~")

    if not os.path.isdir(directory):
        return f"Directory not found: {directory}"

    try:
        # Use find with -iname for case-insensitive matching
        name_pattern = pattern if "*" in pattern else f"*{pattern}*"
        result = subprocess.run(
            [
                "find", directory,
                "-maxdepth", "5",
                "-iname", name_pattern,
                "-not", "-path", "*/.*",
                "-type", "f",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        files = [f for f in result.stdout.strip().split("\n") if f][:max_results]

        if not files:
            return f"No files matching '{pattern}' found in {directory}."

        return f"Found {len(files)} file(s):\n" + "\n".join(f"  • {f}" for f in files)
    except subprocess.TimeoutExpired:
        return "Search timed out. Try a more specific directory."
    except Exception as e:
        return f"Search failed: {e}"


# ── Read File ────────────────────────────────────────────────

@skill(
    name="read_file",
    description="Reads and returns the contents of a text file. Limited to first 500 lines for safety.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the file to read.",
            },
            "max_lines": {
                "type": "integer",
                "description": "Maximum number of lines to read. Default: 100.",
            },
        },
        "required": ["path"],
    },
)
def read_file(path: str, max_lines: int = 100, **kwargs) -> str:
    path = os.path.expanduser(path.strip())

    if not os.path.exists(path):
        return f"File not found: {path}"

    if not os.path.isfile(path):
        return f"Not a file: {path}"

    # Safety check: limit file size
    size = os.path.getsize(path)
    if size > 5 * 1024 * 1024:  # 5 MB
        return f"File too large ({size / (1024*1024):.1f} MB). Maximum is 5 MB."

    max_lines = min(max_lines, 500)

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = []
            for i, line in enumerate(f):
                if i >= max_lines:
                    lines.append(f"\n... (truncated at {max_lines} lines, file has more)")
                    break
                lines.append(line.rstrip())

        return "\n".join(lines)
    except PermissionError:
        return f"Permission denied: {path}"
    except Exception as e:
        return f"Error reading file: {e}"


# ── Create File ──────────────────────────────────────────────

@skill(
    name="create_file",
    description="Creates a new file with the specified content. Will not overwrite existing files unless force=true.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path for the new file.",
            },
            "content": {
                "type": "string",
                "description": "Text content to write to the file.",
            },
            "force": {
                "type": "boolean",
                "description": "If true, overwrite existing file. Default: false.",
            },
        },
        "required": ["path", "content"],
    },
)
def create_file(path: str, content: str, force: bool = False, **kwargs) -> str:
    path = os.path.expanduser(path.strip())

    if os.path.exists(path) and not force:
        return (
            f"File already exists: {path}. "
            "Use force=true to overwrite."
        )

    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"File created: {path} ({len(content)} characters)"
    except PermissionError:
        return f"Permission denied: cannot write to {path}"
    except Exception as e:
        return f"Error creating file: {e}"


# ── List Directory ───────────────────────────────────────────

@skill(
    name="list_directory",
    description="Lists files and subdirectories in a directory, with sizes.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory path to list. Default: home directory.",
            },
            "show_hidden": {
                "type": "boolean",
                "description": "Show hidden files (starting with '.'). Default: false.",
            },
        },
    },
)
def list_directory(path: str = "", show_hidden: bool = False, **kwargs) -> str:
    path = os.path.expanduser(path.strip()) if path.strip() else os.path.expanduser("~")

    if not os.path.isdir(path):
        return f"Not a directory: {path}"

    try:
        entries = sorted(os.listdir(path))
        if not show_hidden:
            entries = [e for e in entries if not e.startswith(".")]

        lines = [f"Contents of {path}:"]
        for entry in entries[:50]:  # Limit to 50 entries
            full_path = os.path.join(path, entry)
            if os.path.isdir(full_path):
                lines.append(f"  📁 {entry}/")
            else:
                try:
                    size = os.path.getsize(full_path)
                    if size >= 1024 * 1024:
                        size_str = f"{size / (1024 * 1024):.1f} MB"
                    elif size >= 1024:
                        size_str = f"{size / 1024:.1f} KB"
                    else:
                        size_str = f"{size} B"
                    lines.append(f"  📄 {entry} ({size_str})")
                except OSError:
                    lines.append(f"  📄 {entry}")

        if len(entries) > 50:
            lines.append(f"  ... and {len(entries) - 50} more entries")

        return "\n".join(lines)
    except PermissionError:
        return f"Permission denied: {path}"
    except Exception as e:
        return f"Error listing directory: {e}"


# ── Get File Info ────────────────────────────────────────────

@skill(
    name="get_file_info",
    description="Returns detailed information about a file: size, permissions, modification time, type.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the file.",
            }
        },
        "required": ["path"],
    },
)
def get_file_info(path: str, **kwargs) -> str:
    import datetime
    import stat

    path = os.path.expanduser(path.strip())

    if not os.path.exists(path):
        return f"Path not found: {path}"

    try:
        st = os.stat(path)
        file_type = "directory" if os.path.isdir(path) else "file"
        size = st.st_size
        modified = datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        permissions = stat.filemode(st.st_mode)

        if size >= 1024 * 1024 * 1024:
            size_str = f"{size / (1024**3):.2f} GB"
        elif size >= 1024 * 1024:
            size_str = f"{size / (1024**2):.2f} MB"
        elif size >= 1024:
            size_str = f"{size / 1024:.2f} KB"
        else:
            size_str = f"{size} bytes"

        return (
            f"Path: {path}\n"
            f"Type: {file_type}\n"
            f"Size: {size_str}\n"
            f"Modified: {modified}\n"
            f"Permissions: {permissions}"
        )
    except Exception as e:
        return f"Error getting file info: {e}"
