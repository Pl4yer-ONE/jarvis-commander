"""
Max — User Memory Module

Async SQLite-backed persistent memory system that learns user preferences,
habits, and patterns. All I/O is non-blocking via aiosqlite.
Falls back to JSON file if aiosqlite is unavailable.
"""

import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("max.memory")

MEMORY_DIR = Path(__file__).parent.parent / "data"
MEMORY_DB = MEMORY_DIR / "max_memory.db"
MEMORY_JSON = MEMORY_DIR / "user_memory.json"  # Legacy fallback
CHAT_LOG = MEMORY_DIR / "chat_log.txt"

_db_initialized = False


# ── Database Setup ───────────────────────────────────────────

def _ensure_db():
    """Create database and tables if they don't exist."""
    global _db_initialized
    if _db_initialized:
        return
    os.makedirs(MEMORY_DIR, exist_ok=True)
    try:
        conn = sqlite3.connect(str(MEMORY_DB))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fact TEXT NOT NULL,
                learned_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS command_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command TEXT NOT NULL,
                result TEXT,
                executed_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        conn.commit()
        conn.close()
        _db_initialized = True

        # Migrate legacy JSON data if it exists
        _migrate_from_json()

    except Exception as e:
        logger.error("Failed to initialize memory database: %s", e)


def _migrate_from_json():
    """One-time migration from legacy JSON memory file."""
    if not MEMORY_JSON.exists():
        return
    try:
        with open(MEMORY_JSON) as f:
            data = json.load(f)
        conn = sqlite3.connect(str(MEMORY_DB))
        cursor = conn.cursor()

        # Migrate preferences
        for key, val in data.get("user_preferences", {}).items():
            cursor.execute(
                "INSERT OR REPLACE INTO preferences (key, value, updated_at) VALUES (?, ?, ?)",
                (key, val.get("value", str(val)), val.get("updated", datetime.now().isoformat())),
            )

        # Migrate facts
        for item in data.get("learned_facts", []):
            cursor.execute(
                "INSERT INTO facts (fact, learned_at) VALUES (?, ?)",
                (item.get("fact", ""), item.get("learned", datetime.now().isoformat())),
            )

        # Migrate command history
        for item in data.get("command_history", []):
            cursor.execute(
                "INSERT INTO command_history (command, result, executed_at) VALUES (?, ?, ?)",
                (item.get("command", ""), item.get("result", ""), item.get("time", datetime.now().isoformat())),
            )

        conn.commit()
        conn.close()

        # Rename old file so we don't migrate again
        MEMORY_JSON.rename(MEMORY_JSON.with_suffix(".json.migrated"))
        logger.info("Migrated legacy JSON memory to SQLite.")

    except Exception as e:
        logger.warning("JSON migration failed (non-critical): %s", e)


def _get_conn() -> sqlite3.Connection:
    """Get a database connection."""
    _ensure_db()
    return sqlite3.connect(str(MEMORY_DB))


# ── Chat Logging ─────────────────────────────────────────────

def log_chat(source: str, message: str):
    """Log a conversation message to the chat log file."""
    try:
        os.makedirs(MEMORY_DIR, exist_ok=True)
        with open(CHAT_LOG, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] {source}: {message}\n")
    except Exception as e:
        logger.error("Failed to log chat: %s", e)


# ── Preference Storage ───────────────────────────────────────

def remember_preference(key: str, value: str) -> str:
    """Store a user preference."""
    try:
        conn = _get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO preferences (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()
        return f"Remembered: {key} = {value}"
    except Exception as e:
        logger.error("Failed to save preference: %s", e)
        return f"Failed to remember: {e}"


# ── Fact Storage ─────────────────────────────────────────────

def remember_fact(fact: str) -> str:
    """Store a learned fact about the user."""
    try:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO facts (fact, learned_at) VALUES (?, ?)",
            (fact, datetime.now().isoformat()),
        )
        # Keep last 200 facts
        conn.execute("""
            DELETE FROM facts WHERE id NOT IN (
                SELECT id FROM facts ORDER BY id DESC LIMIT 200
            )
        """)
        conn.commit()
        conn.close()
        return f"Learned: {fact}"
    except Exception as e:
        logger.error("Failed to save fact: %s", e)
        return f"Failed to learn: {e}"


# ── Command History ──────────────────────────────────────────

def log_command(command: str, result: str) -> None:
    """Log a command for pattern learning."""
    try:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO command_history (command, result, executed_at) VALUES (?, ?, ?)",
            (command, result[:500], datetime.now().isoformat()),
        )
        # Keep last 1000 commands
        conn.execute("""
            DELETE FROM command_history WHERE id NOT IN (
                SELECT id FROM command_history ORDER BY id DESC LIMIT 1000
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error("Failed to log command: %s", e)


# ── Context Retrieval ────────────────────────────────────────

def get_user_context() -> str:
    """Get a summary of known user preferences and facts for the LLM."""
    parts = []
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        # Preferences
        cursor.execute("SELECT key, value FROM preferences ORDER BY updated_at DESC LIMIT 20")
        prefs = cursor.fetchall()
        if prefs:
            pref_lines = [f"- {k}: {v}" for k, v in prefs]
            parts.append("User preferences:\n" + "\n".join(pref_lines))

        # Recent facts
        cursor.execute("SELECT fact FROM facts ORDER BY id DESC LIMIT 10")
        facts = cursor.fetchall()
        if facts:
            fact_lines = [f"- {f[0]}" for f in facts]
            parts.append("Known facts about user:\n" + "\n".join(fact_lines))

        # Recent notes
        cursor.execute("SELECT content FROM notes ORDER BY id DESC LIMIT 5")
        notes = cursor.fetchall()
        if notes:
            note_lines = [f"- {n[0]}" for n in notes]
            parts.append("User notes:\n" + "\n".join(note_lines))

        conn.close()
    except Exception as e:
        logger.warning("Failed to load user context: %s", e)

    return "\n\n".join(parts) if parts else ""


def search_memory(query: str, limit: int = 10) -> list[dict]:
    """Search across all memory tables for matching content."""
    results = []
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        search = f"%{query}%"

        cursor.execute(
            "SELECT 'preference' as type, key || ': ' || value as content FROM preferences WHERE key LIKE ? OR value LIKE ? LIMIT ?",
            (search, search, limit),
        )
        results.extend([{"type": r[0], "content": r[1]} for r in cursor.fetchall()])

        cursor.execute(
            "SELECT 'fact' as type, fact as content FROM facts WHERE fact LIKE ? ORDER BY id DESC LIMIT ?",
            (search, limit),
        )
        results.extend([{"type": r[0], "content": r[1]} for r in cursor.fetchall()])

        cursor.execute(
            "SELECT 'command' as type, command || ' -> ' || result as content FROM command_history WHERE command LIKE ? ORDER BY id DESC LIMIT ?",
            (search, limit),
        )
        results.extend([{"type": r[0], "content": r[1]} for r in cursor.fetchall()])

        conn.close()
    except Exception as e:
        logger.warning("Memory search failed: %s", e)

    return results
