"""SQLite-backed configuration that is safe to expose to ADA's core."""

import json
import sqlite3
import threading
from pathlib import Path


class ConfigurationStore:
    """Store dynamic configuration and system prompts outside memory.db."""

    def __init__(self, db_path):
        self.path = Path(db_path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(str(self.path), timeout=15)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._lock, self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY, value TEXT NOT NULL, value_type TEXT NOT NULL DEFAULT 'json',
                    scope TEXT NOT NULL DEFAULT 'global', description TEXT DEFAULT '', updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS system_prompts (
                    text TEXT NOT NULL, priority INTEGER NOT NULL DEFAULT 100
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS model_catalog (
                    name TEXT PRIMARY KEY, roles TEXT NOT NULL, quality_tier TEXT DEFAULT 'medium',
                    min_ram_gb REAL DEFAULT 4, description TEXT DEFAULT '', auto_pull INTEGER DEFAULT 0,
                    priority INTEGER DEFAULT 100, enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS model_policies (
                    role TEXT PRIMARY KEY, preferred_model TEXT, fallback_models TEXT DEFAULT '[]',
                    max_tokens INTEGER, temperature REAL, enabled INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def system_prompt(self, fallback=""):
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT text FROM system_prompts ORDER BY priority ASC, rowid ASC LIMIT 1"
            ).fetchone()
        return str(row["text"]) if row else fallback

    def add_system_prompt(self, text, priority=100):
        text = str(text or "").strip()
        if not text:
            raise ValueError("El system prompt no puede estar vacío")
        with self._lock, self._connect() as conn:
            cursor = conn.execute("INSERT INTO system_prompts(text, priority) VALUES (?, ?)", (text, int(priority)))
            conn.commit()
            return cursor.lastrowid

    def ensure_system_prompt(self, text, priority=100):
        """Seed the default prompt once without overwriting user edits."""
        with self._lock, self._connect() as conn:
            exists = conn.execute("SELECT 1 FROM system_prompts LIMIT 1").fetchone()
            if exists:
                return False
            text = str(text or "").strip()
            if not text:
                return False
            conn.execute("INSERT INTO system_prompts(text, priority) VALUES (?, ?)", (text, int(priority)))
            conn.commit()
            return True

    def set_setting(self, key, value, value_type="json", scope="global", description=""):
        serialized = value if isinstance(value, str) and value_type == "text" else json.dumps(value, ensure_ascii=False)
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO settings(key,value,value_type,scope,description,updated_at) VALUES (?,?,?,?,?,CURRENT_TIMESTAMP) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value,value_type=excluded.value_type,scope=excluded.scope,description=excluded.description,updated_at=CURRENT_TIMESTAMP",
                (str(key), serialized, value_type, scope, description),
            )
            conn.commit()
