"""Persistent, dependency-light memory for ADA.

Vector indexes are optional for image use cases; conversational memory uses a
SQLite lexical search so it survives restarts and does not depend on embedding
dimensions or heavyweight model downloads.
"""
import json
import os
import re
import sqlite3
import threading
from pathlib import Path


class Memory:
    def __init__(self, db_path):
        self.db_path = str(Path(db_path).expanduser().resolve())
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._lock = threading.RLock()
        self.conn.row_factory = sqlite3.Row
        self._ensure_tables()

    def _ensure_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, meta TEXT
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                task TEXT NOT NULL, result TEXT, provider TEXT, success INTEGER
            );
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                content TEXT NOT NULL, kind TEXT DEFAULT 'note', meta TEXT
            );
            CREATE TABLE IF NOT EXISTS procedures (
                id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL,
                instructions TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP, meta TEXT
            );
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id INTEGER PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                session TEXT NOT NULL DEFAULT 'main', role TEXT NOT NULL,
                text TEXT NOT NULL, model TEXT
            );
        """)
        self.conn.commit()

    def add(self, path, vector=None, meta=None):
        self.conn.execute(
            "INSERT OR REPLACE INTO images(path, meta) VALUES (?, ?)",
            (str(path), json.dumps(meta or {}, ensure_ascii=False)),
        )
        self.conn.commit()

    def add_text(self, text, vector=None, meta=None, kind="note"):
        self.conn.execute(
            "INSERT INTO memories(content, kind, meta) VALUES (?, ?, ?)",
            (str(text), kind, json.dumps(meta or {}, ensure_ascii=False)),
        )
        self.conn.commit()

    def add_knowledge(self, name, content, source=None):
        """Persist a trusted reference document for retrieval by the agent."""
        self.conn.execute(
            "INSERT INTO memories(content, kind, meta) VALUES (?, ?, ?)",
            (str(content), "knowledge", json.dumps({'name': name, 'source': source}, ensure_ascii=False)),
        )
        self.conn.commit()

    def knowledge(self, query=None, limit=3):
        rows = self.conn.execute(
            "SELECT content, meta FROM memories WHERE kind='knowledge' ORDER BY id DESC"
        ).fetchall()
        if not query:
            return [row['content'] for row in rows[:limit]]
        terms = [t for t in re.findall(r"[\wáéíóúñü]+", query.lower()) if len(t) > 2]
        scored = []
        for row in rows:
            score = sum(row['content'].lower().count(term) for term in terms)
            scored.append((score, row['content']))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [content for score, content in scored[:limit] if score]

    def search_text(self, vector_or_query, k=5):
        query = vector_or_query if isinstance(vector_or_query, str) else ""
        if not query:
            return []
        terms = [t for t in re.findall(r"[\wáéíóúñü]+", query.lower()) if len(t) > 2]
        rows = self.conn.execute("SELECT content FROM memories ORDER BY id DESC").fetchall()
        scored = []
        for row in rows:
            content = row["content"]
            low = content.lower()
            score = sum(low.count(term) for term in terms)
            if score:
                scored.append((score, content))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [content for _, content in scored[:k]]

    def add_procedure(self, name, instructions, meta=None):
        self.conn.execute(
            """INSERT INTO procedures(name, instructions, meta) VALUES (?, ?, ?)
               ON CONFLICT(name) DO UPDATE SET instructions=excluded.instructions,
               updated_at=CURRENT_TIMESTAMP, meta=excluded.meta""",
            (name.strip(), instructions.strip(), json.dumps(meta or {}, ensure_ascii=False)),
        )
        self.conn.commit()

    def list_procedures(self):
        return [dict(row) for row in self.conn.execute(
            "SELECT name, instructions, updated_at FROM procedures ORDER BY name"
        ).fetchall()]

    def find_procedures(self, query, k=5):
        terms = [t for t in re.findall(r"[\wáéíóúñü]+", query.lower()) if len(t) > 2]
        scored = []
        for item in self.list_procedures():
            text = (item["name"] + " " + item["instructions"]).lower()
            score = sum(text.count(term) for term in terms)
            if score:
                scored.append((score, item))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [item for _, item in scored[:k]]

    def record_task(self, task, result, provider=None, success=True):
        self.conn.execute(
            "INSERT INTO tasks(task, result, provider, success) VALUES (?, ?, ?, ?)",
            (json.dumps(task, ensure_ascii=False), str(result), provider, int(bool(success))),
        )
        self.conn.commit()

    def recent_tasks(self, limit=10):
        return [dict(row) for row in self.conn.execute(
            "SELECT * FROM tasks ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()]

    def append_conversation(self, messages, session="main"):
        rows = [(session, item.get("role", "assistant"), str(item.get("text", "")), item.get("model"))
                for item in messages if item.get("text") is not None]
        if not rows:
            return
        with self._lock:
            self.conn.executemany(
                "INSERT INTO conversation_messages(session, role, text, model) VALUES (?, ?, ?, ?)",
                rows,
            )
            self.conn.commit()

    def conversation(self, session="main", limit=1000):
        rows = self.conn.execute(
            "SELECT id, created_at, role, text, model FROM conversation_messages "
            "WHERE session=? ORDER BY id DESC LIMIT ?", (session, limit)
        ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def clear_conversation(self, session="main"):
        with self._lock:
            self.conn.execute("DELETE FROM conversation_messages WHERE session=?", (session,))
            self.conn.commit()
