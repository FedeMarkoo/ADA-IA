"""Independent SQLite stores for tools and operational telemetry."""

import json
import sqlite3
import threading
from pathlib import Path


class ToolStore:
    def __init__(self, db_path):
        self.path = Path(db_path).expanduser(); self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock(); self._init()

    def _connect(self):
        conn = sqlite3.connect(str(self.path), timeout=15); conn.row_factory = sqlite3.Row; return conn

    def _init(self):
        with self._connect() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS router_catalog (action TEXT PRIMARY KEY, description TEXT NOT NULL, keywords TEXT, enabled INTEGER NOT NULL DEFAULT 1, meta TEXT);
            CREATE TABLE IF NOT EXISTS prompt_templates (name TEXT PRIMARY KEY, body TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, meta TEXT);
            CREATE TABLE IF NOT EXISTS json_schemas (name TEXT PRIMARY KEY, body TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, meta TEXT);
            """); c.commit()

    def seed_from(self, source):
        """Seed generic defaults without making memories.db a dependency."""
        with self._lock, source._lock, self._connect() as c:
            for table, columns in (("router_catalog", "action,description,keywords,enabled,meta"), ("prompt_templates", "name,body,enabled,updated_at,meta"), ("json_schemas", "name,body,enabled,updated_at,meta")):
                try: rows = source.conn.execute(f"SELECT {columns} FROM {table}").fetchall()
                except sqlite3.OperationalError: continue
                placeholders = ",".join("?" for _ in columns.split(","))
                c.executemany(f"INSERT OR IGNORE INTO {table}({columns}) VALUES ({placeholders})", [tuple(row) for row in rows])
            c.commit()

    def router_actions(self):
        with self._connect() as c: return [dict(row) for row in c.execute("SELECT action,description,keywords FROM router_catalog WHERE enabled=1 ORDER BY action")]

    def prompt_template(self, name, fallback=""):
        with self._connect() as c:
            row = c.execute("SELECT body FROM prompt_templates WHERE name=? AND enabled=1", (name,)).fetchone()
        return row["body"] if row else fallback

    def json_schema(self, name, fallback=None):
        with self._connect() as c: row = c.execute("SELECT body FROM json_schemas WHERE name=? AND enabled=1", (name,)).fetchone()
        if not row: return fallback
        try: return json.loads(row["body"])
        except (TypeError, ValueError): return fallback


class OperationsStore:
    def __init__(self, db_path):
        self.path = Path(db_path).expanduser(); self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock(); self._init()

    def _connect(self):
        conn = sqlite3.connect(str(self.path), timeout=15); conn.row_factory = sqlite3.Row; return conn

    def _init(self):
        with self._connect() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP, task TEXT NOT NULL, result TEXT, provider TEXT, success INTEGER);
            CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP, action TEXT NOT NULL, actor TEXT NOT NULL DEFAULT 'ada', request TEXT, result TEXT, success INTEGER NOT NULL DEFAULT 1, correlation_id TEXT);
            CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP, topic TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0, available_at TEXT DEFAULT CURRENT_TIMESTAMP, last_error TEXT, priority INTEGER NOT NULL DEFAULT 0, cancelled INTEGER NOT NULL DEFAULT 0, dedupe_key TEXT, locked_at TEXT, lock_owner TEXT);
            """); c.commit()

    def record_task(self, task, result, provider=None, success=True):
        with self._lock, self._connect() as c:
            c.execute("INSERT INTO tasks(task,result,provider,success) VALUES (?,?,?,?)", (json.dumps(task, ensure_ascii=False, default=str), json.dumps(result, ensure_ascii=False, default=str), provider, int(bool(success)))); c.commit()

    def migrate_from(self, source):
        """Compatibility helper, intentionally unused by the clean runtime."""
        with self._lock, source._lock, self._connect() as c:
            if c.execute("SELECT 1 FROM tasks LIMIT 1").fetchone() or c.execute("SELECT 1 FROM audit_log LIMIT 1").fetchone():
                return
            for table, columns in (("tasks", "created_at,task,result,provider,success"), ("audit_log", "created_at,action,actor,request,result,success,correlation_id"), ("events", "created_at,topic,payload,status,attempts,available_at,last_error,priority,cancelled,dedupe_key,locked_at,lock_owner")):
                try: rows = source.conn.execute(f"SELECT {columns} FROM {table}").fetchall()
                except sqlite3.OperationalError: continue
                placeholders = ",".join("?" for _ in columns.split(","))
                c.executemany(f"INSERT INTO {table}({columns}) VALUES ({placeholders})", [tuple(row) for row in rows])
            c.commit()

    def record_audit(self, action, request=None, result=None, success=True, actor="ada", correlation_id=None):
        with self._lock, self._connect() as c:
            c.execute("INSERT INTO audit_log(action,actor,request,result,success,correlation_id) VALUES (?,?,?,?,?,?)", (str(action), actor, json.dumps(request, ensure_ascii=False, default=str) if request is not None else None, json.dumps(result, ensure_ascii=False, default=str) if result is not None else None, int(bool(success)), correlation_id)); c.commit()

    def recent_tasks(self, limit=10):
        with self._connect() as c: rows = c.execute("SELECT * FROM tasks ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
        result=[]
        for row in rows:
            item=dict(row)
            for key in ("task", "result"):
                try: item[key]=json.loads(item[key])
                except (TypeError, ValueError): pass
            result.append(item)
        return result

    def recent_audit(self, limit=50):
        with self._connect() as c: rows = c.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
        result=[]
        for row in rows:
            item=dict(row)
            for key in ("request", "result"):
                try: item[key]=json.loads(item[key]) if item[key] is not None else None
                except (TypeError, ValueError): pass
            result.append(item)
        return result

    def stats(self):
        with self._connect() as c:
            return {
                "task_count": c.execute("SELECT COUNT(*) FROM tasks").fetchone()[0],
                "audit_count": c.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0],
                "event_count": c.execute("SELECT COUNT(*) FROM events").fetchone()[0],
                "db_path": str(self.path),
            }

    def publish_event(self, topic, payload, priority=0, dedupe_key=None, delay_seconds=0):
        with self._lock, self._connect() as c:
            if dedupe_key and c.execute("SELECT id FROM events WHERE dedupe_key=? AND status IN ('pending','processing') AND cancelled=0", (str(dedupe_key),)).fetchone():
                return c.execute("SELECT id FROM events WHERE dedupe_key=? ORDER BY id DESC LIMIT 1", (str(dedupe_key),)).fetchone()[0]
            cur = c.execute("INSERT INTO events(topic,payload,priority,dedupe_key,available_at) VALUES (?,?,?,?,datetime('now',?))", (str(topic), json.dumps(payload, ensure_ascii=False, default=str), int(priority), dedupe_key, f"+{max(0,int(delay_seconds))} seconds")); c.commit(); return cur.lastrowid

    def claim_events(self, limit=10, lease_seconds=300, owner=None):
        with self._lock, self._connect() as c:
            rows=c.execute("SELECT * FROM events WHERE status='pending' AND cancelled=0 AND available_at<=CURRENT_TIMESTAMP ORDER BY priority DESC,id LIMIT ?", (int(limit),)).fetchall()
            for row in rows: c.execute("UPDATE events SET status='processing',attempts=attempts+1,locked_at=CURRENT_TIMESTAMP,lock_owner=? WHERE id=?", (owner,row["id"]))
            c.commit(); return [dict(row) for row in rows]

    def finish_event(self, event_id, success=True, error=None, retry_seconds=0):
        status = "done" if success else ("pending" if retry_seconds else "failed")
        with self._lock, self._connect() as c:
            c.execute("UPDATE events SET status=?,last_error=?,available_at=CASE WHEN ? THEN datetime('now', ?) ELSE available_at END,locked_at=NULL,lock_owner=NULL WHERE id=?", (status, str(error or "") if not success else None, int(bool(retry_seconds and not success)), f"+{int(retry_seconds)} seconds", int(event_id))); c.commit()

    def cancel_event(self, event_id):
        with self._lock, self._connect() as c:
            cur=c.execute("UPDATE events SET cancelled=1,status='cancelled',locked_at=NULL,lock_owner=NULL WHERE id=? AND status IN ('pending','processing')", (int(event_id),)); c.commit(); return cur.rowcount > 0
