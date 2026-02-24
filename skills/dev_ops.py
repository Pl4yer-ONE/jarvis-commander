"""
Max Skills — Development & Code Operations

Write, read, fix, and manage code. Git operations.
Enables Max to learn, adapt, and develop code autonomously.
"""

import os
import subprocess
import re

from skills import skill


# ── Code Writing & Editing ───────────────────────────────────

@skill(
    name="write_code",
    description=(
        "Creates or overwrites a file with the given code content. "
        "Use this to write scripts, config files, or any text file. "
        "Will create parent directories automatically."
    ),
    parameters={
        "type": "object",
        "properties": {
            "filepath": {
                "type": "string",
                "description": "Absolute or relative path to the file.",
            },
            "content": {
                "type": "string",
                "description": "The full content to write to the file.",
            },
        },
        "required": ["filepath", "content"],
    },
)
def write_code(filepath: str, content: str, **kwargs) -> str:
    try:
        filepath = os.path.expanduser(filepath)
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "w") as f:
            f.write(content)
        return f"Written {len(content)} chars to {filepath}"
    except Exception as e:
        return f"Error writing file: {e}"


@skill(
    name="edit_file",
    description=(
        "Replaces a specific string/block in a file with new content. "
        "Use for targeted edits without rewriting the whole file."
    ),
    parameters={
        "type": "object",
        "properties": {
            "filepath": {
                "type": "string",
                "description": "Path to the file to edit.",
            },
            "find": {
                "type": "string",
                "description": "The exact text to find and replace.",
            },
            "replace": {
                "type": "string",
                "description": "The replacement text.",
            },
        },
        "required": ["filepath", "find", "replace"],
    },
)
def edit_file(filepath: str, find: str, replace: str, **kwargs) -> str:
    try:
        filepath = os.path.expanduser(filepath)
        with open(filepath, "r") as f:
            content = f.read()

        if find not in content:
            return f"Target text not found in {filepath}."

        count = content.count(find)
        new_content = content.replace(find, replace)
        with open(filepath, "w") as f:
            f.write(new_content)
        return f"Replaced {count} occurrence(s) in {filepath}."
    except Exception as e:
        return f"Error editing file: {e}"


@skill(
    name="append_to_file",
    description="Appends text to the end of a file.",
    parameters={
        "type": "object",
        "properties": {
            "filepath": {
                "type": "string",
                "description": "Path to the file.",
            },
            "content": {
                "type": "string",
                "description": "Text to append.",
            },
        },
        "required": ["filepath", "content"],
    },
)
def append_to_file(filepath: str, content: str, **kwargs) -> str:
    try:
        filepath = os.path.expanduser(filepath)
        with open(filepath, "a") as f:
            f.write(content)
        return f"Appended {len(content)} chars to {filepath}."
    except Exception as e:
        return f"Error appending to file: {e}"


# ── Model Evolution ──────────────────────────────────────────

@skill(
    name="pull_ollama_model",
    description="Downloads a new AI model from the Ollama registry (e.g., 'llama3.2'). "
                "Takes several minutes. Will block until complete.",
    parameters={
        "type": "object",
        "properties": {
            "model_name": {
                "type": "string",
                "description": "Name of the Ollama model (e.g., 'phi3:mini', 'llama3').",
            },
        },
        "required": ["model_name"],
    },
)
def pull_ollama_model(model_name: str, **kwargs) -> str:
    try:
        res = subprocess.run(["ollama", "pull", model_name], check=True, text=True, capture_output=True)
        return f"Successfully downloaded model: {model_name}. You can now switch to it."
    except Exception as e:
        return f"Error downloading model {model_name}: {e}"


@skill(
    name="switch_active_model",
    description="Switches Max's active intelligence model by modifying config.py "
                "and restarting the background service immediately.",
    parameters={
        "type": "object",
        "properties": {
            "model_name": {
                "type": "string",
                "description": "Name of the downloaded Ollama model to switch to.",
            },
        },
        "required": ["model_name"],
    },
)
def switch_active_model(model_name: str, **kwargs) -> str:
    try:
        config_path = os.path.expanduser("~/.gemini/antigravity/scratch/jarvis/config.py")
        with open(config_path, "r") as f:
            content = f.read()
            
        # Regex replace the ollama_model line
        new_content = re.sub(
            r'ollama_model:\s*str\s*=\s*"[^"]+"', 
            f'ollama_model: str = "{model_name}"', 
            content
        )
        
        with open(config_path, "w") as f:
            f.write(new_content)
            
        # Restart the brain
        subprocess.Popen(["systemctl", "--user", "restart", "jarvis.service"])
        return f"Model switched to {model_name}. Core is restarting..."
    except Exception as e:
        return f"Error switching active model: {e}"


# ── Code Analysis ────────────────────────────────────────────

@skill(
    name="read_code",
    description="Reads a source file and returns its content with line numbers.",
    parameters={
        "type": "object",
        "properties": {
            "filepath": {
                "type": "string",
                "description": "Path to the source file to read.",
            },
            "start_line": {
                "type": "integer",
                "description": "Starting line number (1-based). Default: 1.",
            },
            "end_line": {
                "type": "integer",
                "description": "Ending line number. Default: all lines.",
            },
        },
        "required": ["filepath"],
    },
)
def read_code(filepath: str, start_line: int = 1, end_line: int = 0, **kwargs) -> str:
    try:
        filepath = os.path.expanduser(filepath)
        with open(filepath, "r") as f:
            lines = f.readlines()

        total = len(lines)
        start = max(1, start_line) - 1
        end = end_line if end_line > 0 else total

        selected = lines[start:end]
        if len(selected) > 200:
            selected = selected[:200]
            selected.append(f"\n... (truncated, showing 200 of {total} lines)\n")

        numbered = [f"{i + start + 1:4d} | {line}" for i, line in enumerate(selected)]
        return f"File: {filepath} ({total} lines)\n" + "".join(numbered)
    except Exception as e:
        return f"Error reading file: {e}"


@skill(
    name="grep_code",
    description="Searches for a pattern in files. Like grep -rn. Returns matching lines with filenames and line numbers.",
    parameters={
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Text or regex pattern to search for.",
            },
            "path": {
                "type": "string",
                "description": "File or directory to search in. Default: current directory.",
            },
            "file_type": {
                "type": "string",
                "description": "File extension filter, e.g. 'py', 'js', 'txt'. Optional.",
            },
        },
        "required": ["pattern"],
    },
)
def grep_code(pattern: str, path: str = ".", file_type: str = "", **kwargs) -> str:
    try:
        path = os.path.expanduser(path)
        cmd = ["grep", "-rn", "--color=never"]
        if file_type:
            cmd.extend(["--include", f"*.{file_type}"])
        cmd.extend([pattern, path])

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=15,
        )
        output = result.stdout.strip()
        lines = output.split("\n")
        if len(lines) > 50:
            return "\n".join(lines[:50]) + f"\n... ({len(lines)} total matches, showing 50)"
        return output if output else f"No matches for '{pattern}' in {path}."
    except Exception as e:
        return f"Error searching: {e}"


# ── Code Execution & Testing ────────────────────────────────

@skill(
    name="run_python",
    description="Executes a Python script or code snippet and returns the output.",
    parameters={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute directly (inline mode).",
            },
            "filepath": {
                "type": "string",
                "description": "Path to a Python file to run (alternative to inline code).",
            },
            "timeout": {
                "type": "integer",
                "description": "Maximum runtime in seconds. Default: 30.",
            },
        },
    },
)
def run_python(code: str = "", filepath: str = "", timeout: int = 30, **kwargs) -> str:
    try:
        if filepath:
            filepath = os.path.expanduser(filepath)
            cmd = ["python3", filepath]
        elif code:
            cmd = ["python3", "-c", code]
        else:
            return "Provide either 'code' or 'filepath'."

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
        output = result.stdout + result.stderr
        if len(output) > 5000:
            output = output[:5000] + "\n... (truncated)"
        if result.returncode != 0:
            return f"Exit code {result.returncode}:\n{output}"
        return output if output.strip() else "Script executed successfully (no output)."
    except subprocess.TimeoutExpired:
        return f"Timed out after {timeout}s."
    except Exception as e:
        return f"Error running Python: {e}"


@skill(
    name="run_tests",
    description="Runs tests using pytest or unittest in a directory.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to test file or directory. Default: current directory.",
            },
            "framework": {
                "type": "string",
                "description": "'pytest' or 'unittest'. Default: 'pytest'.",
            },
        },
    },
)
def run_tests(path: str = ".", framework: str = "pytest", **kwargs) -> str:
    try:
        path = os.path.expanduser(path)
        if framework == "pytest":
            cmd = ["python3", "-m", "pytest", "-v", "--tb=short", path]
        else:
            cmd = ["python3", "-m", "unittest", "discover", "-s", path, "-v"]

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
        )
        output = result.stdout + result.stderr
        if len(output) > 5000:
            output = output[:5000] + "\n... (truncated)"
        return output if output.strip() else "No tests found."
    except subprocess.TimeoutExpired:
        return "Tests timed out after 120s."
    except Exception as e:
        return f"Error running tests: {e}"


# ── Git Operations ───────────────────────────────────────────

@skill(
    name="git_status",
    description="Shows git status of a repository.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the git repository. Default: current directory.",
            },
        },
    },
)
def git_status(path: str = ".", **kwargs) -> str:
    try:
        result = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=os.path.expanduser(path),
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip() or "Clean working tree."
    except Exception as e:
        return f"Error: {e}"


@skill(
    name="git_commit",
    description="Stages all changes and commits with the given message.",
    parameters={
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Commit message.",
            },
            "path": {
                "type": "string",
                "description": "Path to the git repo. Default: current directory.",
            },
        },
        "required": ["message"],
    },
)
def git_commit(message: str, path: str = ".", **kwargs) -> str:
    try:
        cwd = os.path.expanduser(path)
        subprocess.run(["git", "add", "-A"], cwd=cwd, check=True, capture_output=True, timeout=10)
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=cwd, capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip() or result.stderr.strip()
    except Exception as e:
        return f"Error: {e}"


@skill(
    name="git_diff",
    description="Shows the current uncommitted changes (diff).",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the git repo. Default: current directory.",
            },
        },
    },
)
def git_diff(path: str = ".", **kwargs) -> str:
    try:
        result = subprocess.run(
            ["git", "diff", "--stat"],
            cwd=os.path.expanduser(path),
            capture_output=True, text=True, timeout=10,
        )
        output = result.stdout.strip()
        if not output:
            return "No uncommitted changes."
        return output
    except Exception as e:
        return f"Error: {e}"


@skill(
    name="git_log",
    description="Shows recent git commits.",
    parameters={
        "type": "object",
        "properties": {
            "count": {
                "type": "integer",
                "description": "Number of commits to show. Default: 10.",
            },
            "path": {
                "type": "string",
                "description": "Path to the git repo. Default: current directory.",
            },
        },
    },
)
def git_log(count: int = 10, path: str = ".", **kwargs) -> str:
    try:
        result = subprocess.run(
            ["git", "log", f"-{count}", "--oneline", "--graph"],
            cwd=os.path.expanduser(path),
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip() or "No commits yet."
    except Exception as e:
        return f"Error: {e}"


# ── Self-Improvement ─────────────────────────────────────────

@skill(
    name="add_skill",
    description=(
        "Creates a new skill file for Max. Provide the skill module name and full Python code. "
        "Max can use this to teach himself new abilities at runtime."
    ),
    parameters={
        "type": "object",
        "properties": {
            "module_name": {
                "type": "string",
                "description": "Name for the new skill module (e.g. 'web_scraping').",
            },
            "code": {
                "type": "string",
                "description": "Full Python code for the skill module, including imports and @skill decorators.",
            },
        },
        "required": ["module_name", "code"],
    },
)
def add_skill(module_name: str, code: str, **kwargs) -> str:
    try:
        skills_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)))
        filepath = os.path.join(skills_dir, f"{module_name}.py")

        if os.path.exists(filepath):
            return f"Skill module '{module_name}' already exists. Use edit_file to modify it."

        with open(filepath, "w") as f:
            f.write(code)

        return (
            f"New skill module created: {filepath}\n"
            f"Restart Max to load the new skills, or use run_command to do it."
        )
    except Exception as e:
        return f"Error creating skill: {e}"


@skill(
    name="learn_from_error",
    description=(
        "Analyzes an error message or traceback and suggests or applies a fix. "
        "Provide the error output and optionally the file path."
    ),
    parameters={
        "type": "object",
        "properties": {
            "error": {
                "type": "string",
                "description": "The error message or full traceback.",
            },
            "filepath": {
                "type": "string",
                "description": "Path to the file that caused the error (optional).",
            },
        },
        "required": ["error"],
    },
)
def learn_from_error(error: str, filepath: str = "", **kwargs) -> str:
    info = [f"Error analysis:\n{error}\n"]

    # Extract file and line from traceback
    import re
    matches = re.findall(r'File "([^"]+)", line (\d+)', error)
    if matches:
        for fpath, line_no in matches[-3:]:  # Last 3 frames
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r") as f:
                        lines = f.readlines()
                    ln = int(line_no)
                    start = max(0, ln - 3)
                    end = min(len(lines), ln + 3)
                    context = "".join(
                        f"{'→' if i+1 == ln else ' '} {i+1:4d} | {lines[i]}"
                        for i in range(start, end)
                    )
                    info.append(f"\nContext from {fpath}:\n{context}")
                except Exception:
                    pass

    if filepath and os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                content = f.read()
            info.append(f"\nFull file ({filepath}): {len(content)} chars, {content.count(chr(10))+1} lines")
        except Exception:
            pass

    return "\n".join(info)

@skill(
    name="upgrade_max_core",
    description=(
        "Restarts the Jarvis/Max background systemd service. "
        "Call this ONLY after you have successfully used `write_code` or `edit_file` "
        "to upgrade your own core Python files or add new skills, so the changes take effect. "
        "WARNING: This will immediately kill your current process and restart you."
    ),
    parameters={
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Short explanation of why you are restarting.",
            }
        },
        "required": ["reason"],
    }
)
def upgrade_max_core(reason: str, **kwargs) -> str:
    try:
        # We run the restart in the background slightly delayed so we can return the response first
        import subprocess
        subprocess.Popen(
            "sleep 2 && systemctl --user restart jarvis.service",
            shell=True,
            start_new_session=True
        )
        return f"Initiating core upgrade/restart sequence in 2 seconds. Reason: {reason}"
    except Exception as e:
        return f"Failed to initiate upgrade sequence: {e}"
