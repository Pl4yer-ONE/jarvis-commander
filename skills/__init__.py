"""
Max — Skill Registry

Provides a decorator-based system for registering "skills" (tools) that the
LLM can invoke. Skills are auto-discovered from all modules in this package.
Supports both sync and async skill functions.
"""

import importlib
import inspect
import logging
import pkgutil
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("max.skills")

# ── Global Skill Store ───────────────────────────────────────

_SKILLS: dict[str, dict[str, Any]] = {}


def skill(
    name: str,
    description: str,
    parameters: dict | None = None,
):
    """
    Decorator to register a function as a Max skill.

    Usage:
        @skill(
            name="get_time",
            description="Returns the current date and time.",
            parameters={"type": "object", "properties": {}},
        )
        def get_time(**kwargs) -> str:
            ...
    """
    def decorator(func: Callable) -> Callable:
        # Validate parameters schema at registration time
        params = parameters or {"type": "object", "properties": {}}
        if "type" not in params:
            params["type"] = "object"
        if "properties" not in params:
            params["properties"] = {}

        _SKILLS[name] = {
            "function": func,
            "description": description,
            "parameters": params,
            "is_async": inspect.iscoroutinefunction(func),
        }
        logger.debug("Registered skill: %s%s", name, " (async)" if inspect.iscoroutinefunction(func) else "")
        return func

    return decorator


class SkillRegistry:
    """Manages skill discovery, listing, and execution."""

    def __init__(self):
        self._discovered = False

    def discover(self):
        """Auto-import all modules in the skills package to trigger @skill decorators."""
        if self._discovered:
            return

        package_dir = Path(__file__).parent
        for _, module_name, _ in pkgutil.iter_modules([str(package_dir)]):
            if module_name.startswith("_"):
                continue
            try:
                importlib.import_module(f"skills.{module_name}")
                logger.info("  Loaded: skills.%s", module_name)
            except Exception as e:
                logger.warning("  Failed: skills.%s: %s", module_name, e)

        self._discovered = True
        logger.info("Skill discovery complete: %d skills registered.", len(_SKILLS))

    def list_skills(self) -> dict[str, dict[str, Any]]:
        """Return all registered skills with metadata."""
        self.discover()
        return {
            name: {
                "description": info["description"],
                "parameters": info["parameters"],
            }
            for name, info in _SKILLS.items()
        }

    def execute(self, name: str, arguments: dict[str, Any] = None) -> str:
        """
        Execute a registered skill by name.
        Returns string result. Raises KeyError if skill doesn't exist.
        """
        self.discover()

        if name not in _SKILLS:
            available = list(_SKILLS.keys())
            raise KeyError(
                f"Unknown skill: '{name}'. Available: {available[:10]}{'...' if len(available) > 10 else ''}"
            )

        func = _SKILLS[name]["function"]
        arguments = arguments or {}

        try:
            if _SKILLS[name]["is_async"]:
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    # We're in an async context — create a task
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        result = loop.run_in_executor(pool, lambda: asyncio.run(func(**arguments)))
                except RuntimeError:
                    result = asyncio.run(func(**arguments))
            else:
                result = func(**arguments)
            return str(result) if result is not None else "Done."
        except Exception as e:
            logger.error("Skill '%s' failed: %s", name, e)
            raise

    def get_tool_definitions(self) -> list[dict]:
        """Get tool definitions formatted for LLM consumption."""
        self.discover()
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": info["description"],
                    "parameters": info["parameters"],
                },
            }
            for name, info in _SKILLS.items()
        ]


# Module-level singleton
registry = SkillRegistry()
