"""Separate SQLite execution log used only when ADA debug mode is enabled."""
import json
import sqlite3
import threading
import time
from pathlib import Path


class DebugLog:
    def __init__(self, path):
        self.path = str(Path(path).expanduser())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.lock = threading.RLock()
        self.conn.execute("""CREATE TABLE IF NOT EXISTS execution_log (
            id INTEGER PRIMARY KEY, created_at REAL NOT NULL, level TEXT NOT NULL,
            event TEXT NOT NULL, session_id TEXT, payload TEXT NOT NULL)""")
        self.conn.execute("""CREATE TABLE IF NOT EXISTS debug_settings (
            key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at REAL NOT NULL)""")
        self.conn.commit()

    def enabled(self):
        with self.lock:
            row = self.conn.execute("SELECT value FROM debug_settings WHERE key='enabled'").fetchone()
        return bool(row and row[0] == "1")

    def set_enabled(self, enabled):
        value = "1" if enabled else "0"
        with self.lock:
            self.conn.execute(
                "INSERT INTO debug_settings(key,value,updated_at) VALUES('enabled',?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (value, time.time()),
            )
            self.conn.commit()

    def write(self, event, payload=None, level="DEBUG", session_id=None):
        with self.lock:
            self.conn.execute("INSERT INTO execution_log(created_at,level,event,session_id,payload) VALUES(?,?,?,?,?)",
                              (time.time(), level, event, session_id, json.dumps(payload or {}, ensure_ascii=False, default=str)))
            self.conn.commit()

    def close(self):
        with self.lock:
            self.conn.close()
