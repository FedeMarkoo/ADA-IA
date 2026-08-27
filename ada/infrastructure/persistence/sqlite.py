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
import unicodedata
from pathlib import Path


class Memory:
    SCHEMA_VERSION = 2

    def __init__(self, db_path, encrypted=False, encryption_key=None):
        self.db_path = ":memory:" if str(db_path) == ":memory:" else str(Path(db_path).expanduser().resolve())
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._thread_local = threading.local()
        self._connections = []
        self._connections_lock = threading.Lock()
        self._primary_conn = self._new_connection()
        self._lock = threading.RLock()
        self._fts_available = False
        self._encrypted = bool(encrypted)
        self._fernet = None
        if self._encrypted:
            key = encryption_key or os.environ.get("ADA_MEMORY_KEY")
            if not key:
                raise RuntimeError("Definí ADA_MEMORY_KEY para habilitar el cifrado de memory.db.")
            try:
                from cryptography.fernet import Fernet

                self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
            except ImportError as exc:
                raise RuntimeError("Instalá la extra credentials para cifrar memory.db.") from exc
            except (TypeError, ValueError) as exc:
                raise RuntimeError("ADA_MEMORY_KEY no es una clave Fernet válida.") from exc
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self._ensure_tables()

    def _new_connection(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        with self._connections_lock:
            self._connections.append(conn)
        return conn

    @property
    def conn(self):
        """Return one connection per worker thread for file-backed databases."""
        if self.db_path == ":memory:":
            return self._primary_conn
        conn = getattr(self._thread_local, "conn", None)
        if conn is None:
            conn = self._new_connection()
            self._thread_local.conn = conn
        return conn

    def _seal(self, value):
        text = str(value)
        if not self._encrypted:
            return text
        if text.startswith("ada:v1:"):
            return text
        assert self._fernet is not None
        return "ada:v1:" + self._fernet.encrypt(text.encode("utf-8")).decode("ascii")

    def _open(self, value):
        text = "" if value is None else str(value)
        if not text.startswith("ada:v1:"):
            return text
        if not self._fernet:
            raise RuntimeError("La base contiene datos cifrados; inicializá Memory con ADA_MEMORY_KEY.")
        return self._fernet.decrypt(text[7:].encode("ascii")).decode("utf-8")

    @staticmethod
    def _json(value):
        return json.dumps(value, ensure_ascii=False, default=str)

    def _migrate_sensitive_rows(self):
        if not self._encrypted:
            return
        ALLOWED_COLUMNS = {
            "images": {"path", "meta"},
            "memories": {"summary", "content", "meta"},
            "tasks": {"task", "result"},
            "procedures": {"instructions", "meta"},
            "conversation_messages": {"text"},
            "audit_log": {"request", "result"},
        }
        for table, cols in ALLOWED_COLUMNS.items():
            for column in cols:
                for row in self.conn.execute(f"SELECT id, {column} FROM {table}").fetchall():
                    value = row[column]
                    if value is not None and not str(value).startswith("ada:v1:"):
                        self.conn.execute(f"UPDATE {table} SET {column}=? WHERE id=?", (self._seal(value), row["id"]))
        self.conn.commit()

    def _ensure_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY, applied_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, meta TEXT
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                task TEXT NOT NULL, result TEXT, provider TEXT, success INTEGER
            );
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                summary TEXT NOT NULL DEFAULT '', content TEXT NOT NULL, kind TEXT DEFAULT 'note', meta TEXT
            );
            CREATE TABLE IF NOT EXISTS procedures (
                id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL,
                instructions TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP, meta TEXT
            );
            CREATE TABLE IF NOT EXISTS folder_aliases (
                alias TEXT PRIMARY KEY, path TEXT NOT NULL, confidence REAL NOT NULL DEFAULT 1.0,
                use_count INTEGER NOT NULL DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS folder_contexts (
                session TEXT PRIMARY KEY, path TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS folder_index (
                path TEXT PRIMARY KEY, name TEXT NOT NULL, normalized_name TEXT NOT NULL,
                parent_path TEXT NOT NULL, last_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                use_count INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id INTEGER PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                session TEXT NOT NULL DEFAULT 'main', role TEXT NOT NULL,
                text TEXT NOT NULL, model TEXT
            );
            CREATE TABLE IF NOT EXISTS conversation_summaries (
                session TEXT PRIMARY KEY, summary TEXT NOT NULL DEFAULT '',
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS router_catalog (
                action TEXT PRIMARY KEY, description TEXT NOT NULL,
                keywords TEXT, enabled INTEGER NOT NULL DEFAULT 1, meta TEXT
            );
            CREATE TABLE IF NOT EXISTS prompt_templates (
                name TEXT PRIMARY KEY, body TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1, updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                meta TEXT
            );
            CREATE TABLE IF NOT EXISTS json_schemas (
                name TEXT PRIMARY KEY, body TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1, updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                meta TEXT
            );
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                action TEXT NOT NULL, actor TEXT NOT NULL DEFAULT 'ada',
                request TEXT, result TEXT, success INTEGER NOT NULL DEFAULT 1,
                correlation_id TEXT
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                topic TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0, available_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_error TEXT, priority INTEGER NOT NULL DEFAULT 0,
                cancelled INTEGER NOT NULL DEFAULT 0, dedupe_key TEXT,
                locked_at TEXT, lock_owner TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_memories_kind_id ON memories(kind, id DESC);
            CREATE INDEX IF NOT EXISTS idx_conversation_session_id ON conversation_messages(session, id DESC);
            CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(id DESC);
            CREATE INDEX IF NOT EXISTS idx_folder_index_name ON folder_index(normalized_name);
            CREATE INDEX IF NOT EXISTS idx_folder_index_parent ON folder_index(parent_path);
        """)
        columns = {row[1] for row in self.conn.execute("PRAGMA table_info(router_catalog)").fetchall()}
        if "keywords" not in columns:
            self.conn.execute("ALTER TABLE router_catalog ADD COLUMN keywords TEXT")
        memory_columns = {row[1] for row in self.conn.execute("PRAGMA table_info(memories)").fetchall()}
        if "summary" not in memory_columns:
            # Existing installations only had the detailed content field.
            # Keep it intact and derive a selector summary below.
            self.conn.execute("ALTER TABLE memories ADD COLUMN summary TEXT NOT NULL DEFAULT ''")
            for row in self.conn.execute("SELECT id, content FROM memories WHERE summary='' OR summary IS NULL").fetchall():
                self.conn.execute(
                    "UPDATE memories SET summary=? WHERE id=?",
                    (self._memory_summary(self._open(row["content"])), row["id"]),
                )
        self._apply_migrations()
        self._migrate_sensitive_rows()
        self.conn.commit()
        try:
            if self._encrypted:
                raise sqlite3.OperationalError("FTS no puede indexar contenido cifrado")
            self.conn.executescript("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_search USING fts5(
                    content, kind, content='memories', content_rowid='id'
                );
                CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                    INSERT INTO memory_search(rowid, content, kind) VALUES (new.id, new.content, new.kind);
                END;
                CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                    INSERT INTO memory_search(memory_search, rowid, content, kind) VALUES ('delete', old.id, old.content, old.kind);
                END;
                CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                    INSERT INTO memory_search(memory_search, rowid, content, kind) VALUES ('delete', old.id, old.content, old.kind);
                    INSERT INTO memory_search(rowid, content, kind) VALUES (new.id, new.content, new.kind);
                END;
                INSERT INTO memory_search(memory_search) VALUES ('rebuild');
            """)
            self._fts_available = True
        except sqlite3.OperationalError:
            # Some minimal Python builds omit SQLite FTS5; lexical fallback remains available.
            self._fts_available = False
        self._seed_dynamic_ai_defaults()

    def _apply_migrations(self):
        """Record schema changes explicitly so future upgrades stay ordered."""
        version = int(self.conn.execute("PRAGMA user_version").fetchone()[0])
        if version < 1:
            self.conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(version) VALUES (?)",
                (self.SCHEMA_VERSION,),
            )
            self.conn.execute("PRAGMA user_version = 1")
            self.conn.commit()
            version = 1
        if version < 2:
            columns = {row[1] for row in self.conn.execute("PRAGMA table_info(events)").fetchall()}
            additions = {
                "priority": "INTEGER NOT NULL DEFAULT 0",
                "cancelled": "INTEGER NOT NULL DEFAULT 0",
                "dedupe_key": "TEXT",
                "locked_at": "TEXT",
                "lock_owner": "TEXT",
            }
            for name, definition in additions.items():
                if name not in columns:
                    self.conn.execute(f"ALTER TABLE events ADD COLUMN {name} {definition}")
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_ready ON events(status, cancelled, priority DESC, id)"
            )
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_events_dedupe ON events(dedupe_key)")
            self.conn.execute("INSERT OR IGNORE INTO schema_migrations(version) VALUES (2)")
            self.conn.execute("PRAGMA user_version = 2")
            self.conn.commit()

    def _seed_dynamic_ai_defaults(self):
        aliases = {
            "analyze_photo": (
                "Analizar una foto",
                ("foto", "imagen", "raw", "jpg", "nef", "arw", "enfoque", "exposición", "iso"),
            ),
            "select_photo_batch": (
                "Seleccionar un lote de fotos",
                ("selección", "seleccionar", "descartes", "ráfaga", "rafaga", "lote", "xmp"),
            ),
            "lightroom": (
                "Consultar o preparar acciones de Lightroom",
                ("lightroom", "colección", "sqlite", "biblioteca", "rechazadas"),
            ),
            "list_photos": ("Listar fotos", ("listar fotos", "mostrame fotos", "ver fotos")),
            "list_files": (
                "Listar archivos",
                ("listar archivos", "lista los archivos", "listame los archivos", "documentos"),
            ),
            "list_dirs": ("Listar carpetas", ("carpetas", "directorios", "estructura")),
            "group_files": ("Agrupar archivos", ("agrupar", "mover archivos", "juntar archivos")),
            "organize": ("Organizar archivos", ("organizar", "ordenar archivos", "ordenar los archivos")),
            "suggest": ("Sugerir una acción general", ("sugerir", "recomendar")),
            "run": ("Ejecutar un script", ("ejecutar", "correr comando", "script")),
            "food": (
                "Compras, recetas, cocina y planificación de comidas",
                (
                    "comida",
                    "comidas",
                    "receta",
                    "recetas",
                    "cocinar",
                    "compras",
                    "supermercado",
                    "ingredientes",
                    "comer",
                ),
            ),
            "gmail_read": ("Leer metadatos de Gmail", ("gmail", "correo", "mail", "email", "bandeja")),
            "gmail_send": ("Enviar un correo de Gmail", ("enviar correo", "mandar mail", "gmail enviar")),
            "gmail_draft": ("Crear un borrador de Gmail", ("borrador de correo", "draft gmail", "preparar mail")),
            "instagram_publish": ("Publicar una imagen en Instagram", ("instagram", "publicar foto", "postear")),
            "ask": ("Conversación general", ()),
        }
        from ada.capabilities.registry import capability_specs

        generated = {name: (spec.description, ()) for name, spec in capability_specs().items()}
        actions = dict(aliases)
        actions.update({name: value for name, value in generated.items() if name not in actions})
        self.conn.executemany(
            "INSERT INTO router_catalog(action,description,keywords) VALUES (?,?,?) "
            "ON CONFLICT(action) DO UPDATE SET description=excluded.description, keywords=excluded.keywords",
            [
                (action, description, json.dumps(keywords, ensure_ascii=False))
                for action, (description, keywords) in actions.items()
            ],
        )
        templates = {
            "agent_system": (
                "Eres ADA, un agente de IA neutral y práctico. Tu modo permanente es AGENTE, no chatbot: "
                "no preguntes al usuario si quiere chat o agente ni ofrezcas elegir entre esos modos. "
                "Interpretá la intención, proponé el siguiente paso concreto y usá las herramientas disponibles "
                "cuando la solicitud corresponda a una acción. No inventes ejecuciones ni resultados. "
                "Si no podés ejecutar una acción, explicá claramente qué falta. En consultas conceptuales "
                "autocontenidas, respondé directamente usando supuestos razonables y no pidas datos técnicos "
                "que no sean indispensables. Respetá las alternativas pedidas y cerrá con una recomendación. "
                "Sé breve y claro. {language}"
            ),
            "router": (
                "Sos el router de ADA. Devolvé SOLO JSON válido. Elegí una action del catálogo: {actions}. "
                "Para comida usá domain=shopping|recipes|inventory|budget|planning y food_action={food_actions}. "
                "Si el pedido trata de cocinar, comer, recetas, gustos o supermercado, elegí food. "
                "No ejecutes acciones. Historial: {history}\nPedido: {text}"
            ),
            "food_classifier": (
                "Clasificá semánticamente el pedido. Devolvé SOLO JSON válido. "
                "Si trata de comida, cocina, recetas, compras, inventario o planificación, is_food=true y food_action={food_actions}. "
                "Una duda como qué cocinar usa advise. Si no es comida, is_food=false. "
                "Historial: {history}\nPedido: {text}"
            ),
            "food_mutation_verifier": (
                "Verificá si el usuario pidió modificar explícitamente la lista de compras. "
                "allow=true para agregar, comprar, marcar o quitar un producto concreto; "
                "allow=false para recomendaciones o recetas. Devolvé SOLO JSON. "
                "Intención: {intent}\nPedido: {text}"
            ),
            "food_advisor": (
                "Sos el asesor culinario personal. Respondé en español rioplatense. Usá el perfil y catálogo. "
                "Priorizá comidas simples, rendidoras, reutilizables y aptas para freezer; evitá lentejas, "
                "supremas y repetir pizza. Interpretá restricciones del hilo. Elegí una recomendación y como "
                "máximo una alternativa. No hagas cuestionarios, no muestres razonamiento ni pasos internos. "
                "Devolvé SOLO JSON con el campo reply. PERFIL:\n{profile}\nCATÁLOGO:\n{catalog}\n"
                "HILO DE USUARIO:\n{conversation}\nPEDIDO:\n{request}"
            ),
        }
        self.conn.executemany("INSERT OR IGNORE INTO prompt_templates(name,body) VALUES (?,?)", templates.items())
        schemas = {
            "router": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "analyze_photo",
                            "select_photo_batch",
                            "lightroom",
                            "list_photos",
                            "list_files",
                            "list_dirs",
                            "group_files",
                            "organize",
                            "suggest",
                            "run",
                            "food",
                            "gmail_read",
                            "gmail_send",
                            "gmail_draft",
                            "instagram_publish",
                            "ask",
                        ],
                    },
                    "domain": {"type": "string", "enum": ["shopping", "recipes", "inventory", "budget", "planning"]},
                    "food_action": {
                        "type": "string",
                        "enum": [
                            "add",
                            "list",
                            "check",
                            "remove",
                            "save",
                            "suggest",
                            "recipe_to_shopping",
                            "advise",
                            "inventory_add",
                            "inventory_list",
                            "inventory_use",
                            "inventory_remove",
                            "budget_set",
                            "budget_spend",
                            "budget_list",
                            "plan_set",
                            "plan_list",
                            "plan_remove",
                        ],
                    },
                    "item": {"type": "string"},
                    "quantity": {"type": "string"},
                    "unit": {"type": "string"},
                    "name": {"type": "string"},
                    "ingredients": {"type": "string"},
                    "available": {"type": "string"},
                    "confidence": {"type": "number"},
                    "reason": {"type": "string"},
                    "needs_clarification": {"type": "boolean"},
                    "clarifying_question": {"type": "string"},
                },
                "required": ["action"],
                "additionalProperties": False,
            },
            "food": {
                "type": "object",
                "properties": {
                    "is_food": {"type": "boolean"},
                    "domain": {"type": "string", "enum": ["shopping", "recipes", "inventory", "budget", "planning"]},
                    "food_action": {
                        "type": "string",
                        "enum": [
                            "add",
                            "list",
                            "check",
                            "remove",
                            "save",
                            "recipe_to_shopping",
                            "advise",
                            "inventory_add",
                            "inventory_list",
                            "inventory_use",
                            "inventory_remove",
                            "budget_set",
                            "budget_spend",
                            "budget_list",
                            "plan_set",
                            "plan_list",
                            "plan_remove",
                        ],
                    },
                    "item": {"type": "string"},
                    "quantity": {"type": "string"},
                    "unit": {"type": "string"},
                    "name": {"type": "string"},
                    "ingredients": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["is_food"],
                "additionalProperties": False,
            },
            "food_verify": {
                "type": "object",
                "properties": {"allow": {"type": "boolean"}, "reason": {"type": "string"}},
                "required": ["allow"],
                "additionalProperties": False,
            },
            "food_reply": {
                "type": "object",
                "properties": {"reply": {"type": "string"}},
                "required": ["reply"],
                "additionalProperties": False,
            },
        }
        self.conn.executemany(
            "INSERT OR IGNORE INTO json_schemas(name,body) VALUES (?,?)",
            [(name, json.dumps(body, ensure_ascii=False)) for name, body in schemas.items()],
        )
        self.conn.commit()

    def router_actions(self):
        rows = [
            dict(row)
            for row in self.conn.execute(
                "SELECT action,description,keywords FROM router_catalog WHERE enabled=1 ORDER BY action"
            ).fetchall()
        ]
        for row in rows:
            try:
                row["keywords"] = json.loads(row.get("keywords") or "[]")
            except (TypeError, ValueError):
                row["keywords"] = []
        return rows

    def prompt_template(self, name, fallback=""):
        row = self.conn.execute("SELECT body FROM prompt_templates WHERE name=? AND enabled=1", (name,)).fetchone()
        return row["body"] if row else fallback

    def upsert_prompt_template(self, name, body, meta=None):
        with self._lock:
            self.conn.execute(
                "INSERT INTO prompt_templates(name,body,meta) VALUES (?,?,?) "
                "ON CONFLICT(name) DO UPDATE SET body=excluded.body,meta=excluded.meta,updated_at=CURRENT_TIMESTAMP",
                (name, body, json.dumps(meta or {}, ensure_ascii=False)),
            )
            self.conn.commit()

    def json_schema(self, name, fallback=None):
        row = self.conn.execute("SELECT body FROM json_schemas WHERE name=? AND enabled=1", (name,)).fetchone()
        if not row:
            return fallback
        try:
            return json.loads(row["body"])
        except (TypeError, ValueError):
            return fallback

    def upsert_json_schema(self, name, schema, meta=None):
        with self._lock:
            self.conn.execute(
                "INSERT INTO json_schemas(name,body,meta) VALUES (?,?,?) "
                "ON CONFLICT(name) DO UPDATE SET body=excluded.body,meta=excluded.meta,updated_at=CURRENT_TIMESTAMP",
                (name, json.dumps(schema, ensure_ascii=False), json.dumps(meta or {}, ensure_ascii=False)),
            )
            self.conn.commit()

    def add(self, path, vector=None, meta=None):
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO images(path, meta) VALUES (?, ?)",
                (self._seal(path), self._seal(json.dumps(meta or {}, ensure_ascii=False))),
            )
            self.conn.commit()

    def add_text(self, text, vector=None, meta=None, kind="note"):
        with self._lock:
            self.conn.execute(
                "INSERT INTO memories(summary, content, kind, meta) VALUES (?, ?, ?, ?)",
                (self._seal(self._memory_summary(text)), self._seal(text), kind, self._seal(self._json(meta or {}))),
            )
            self.conn.commit()

    def stats(self):
        """Return compact memory counters for the manager and diagnostics."""
        with self._lock:
            counts = {}
            for table, key in (
                ("memories", "memory_count"),
                ("conversation_messages", "conversation_count"),
                ("tasks", "task_count"),
                ("audit_log", "audit_count"),
            ):
                try:
                    counts[key] = int(self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                except sqlite3.OperationalError:
                    # Operational tables live in operations.db in the clean
                    # runtime; keep this API useful for memory-only stores.
                    counts[key] = 0
        counts["db_path"] = self.db_path
        return counts

    def drop_auxiliary_tables(self):
        """Keep memories.db limited to memory and conversation data."""
        with self._lock:
            for table in ("router_catalog", "prompt_templates", "json_schemas", "tasks", "audit_log", "events"):
                self.conn.execute(f"DROP TABLE IF EXISTS {table}")
            self.conn.commit()

    @staticmethod
    def _memory_summary(content, max_chars=180):
        """Build a compact selector text when callers do not provide one."""
        text = re.sub(r"\s+", " ", str(content or "")).strip()
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 1].rsplit(" ", 1)[0] + "…"

    def add_memory_record(self, content, kind="note", meta=None, summary=None):
        content = str(content or "").strip()
        summary = self._memory_summary(summary if summary is not None else content)
        if not content:
            raise ValueError("content no puede estar vacío")
        if not summary:
            raise ValueError("summary no puede estar vacío")
        with self._lock:
            cursor = self.conn.execute(
                "INSERT INTO memories(summary, content, kind, meta) VALUES (?, ?, ?, ?)",
                (self._seal(summary), self._seal(content), kind, self._seal(self._json(meta or {}))),
            )
            self.conn.commit()
            return cursor.lastrowid

    def search_memory_records(self, query, limit=10, kind=None):
        terms = [term for term in re.findall(r"[\wáéíóúñü]+", str(query or "").lower()) if len(term) > 2]
        limit = min(max(int(limit), 1), 50)
        with self._lock:
            rows = self.conn.execute(
                "SELECT id, created_at, summary, content, kind, meta FROM memories "
                "WHERE (? IS NULL OR kind=?) ORDER BY id DESC LIMIT 500",
                (kind, kind),
            ).fetchall()
        result = []
        for row in rows:
            content = self._open(row["content"])
            summary = self._open(row["summary"] or "")
            searchable = f"{summary} {content}".lower()
            if terms and not all(term in searchable for term in terms):
                continue
            try:
                meta = json.loads(self._open(row["meta"] or "{}"))
            except (TypeError, ValueError):
                meta = {}
            result.append(
                {
                    "id": row["id"],
                    "created_at": row["created_at"],
                    "content": content,
                    "summary": summary,
                    "kind": row["kind"],
                    "meta": meta,
                }
            )
            if len(result) >= limit:
                break
        return result

    def retrieve_memory_candidates(self, query, limit=20, session=None):
        """Return bounded, scored memory candidates for router reranking."""
        terms = [term for term in re.findall(r"[\wáéíóúñü]+", str(query or "").lower()) if len(term) > 2]
        limit = min(max(int(limit), 1), 30)
        with self._lock:
            rows = self.conn.execute(
                "SELECT id, created_at, summary, content, kind, meta FROM memories ORDER BY id DESC LIMIT 500"
            ).fetchall()
        candidates = []
        for row in rows:
            content = self._open(row["content"])
            summary = self._open(row["summary"] or "")
            lowered = f"{summary} {content}".lower()
            overlap = sum(lowered.count(term) for term in terms)
            if terms and not overlap:
                continue
            try:
                meta = json.loads(self._open(row["meta"] or "{}"))
            except (TypeError, ValueError):
                meta = {}
            if session and meta.get("session") not in {None, session}:
                continue
            layer_boost = {"knowledge": 0.25, "profile": 0.2, "semantic": 0.1}.get(row["kind"], 0.0)
            score = min(1.0, overlap / max(1, len(terms)) * 0.7 + layer_boost)
            candidates.append(
                {
                    "id": row["id"],
                    "kind": row["kind"],
                    "summary": summary,
                    "score": round(score, 4),
                    "source": "memory",
                    "created_at": row["created_at"],
                }
            )
        candidates.sort(key=lambda item: (item["score"], item["id"]), reverse=True)
        return candidates[:limit]

    def memory_records_by_ids(self, memory_ids, limit=3):
        """Resolve only selected memory ids for the current request."""
        ids = []
        for value in memory_ids or []:
            try:
                value = int(value)
            except (TypeError, ValueError):
                continue
            if value not in ids:
                ids.append(value)
        ids = ids[: max(1, min(int(limit), 10))]
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        with self._lock:
            rows = self.conn.execute(
                f"SELECT id, summary, content, kind FROM memories WHERE id IN ({placeholders})", ids
            ).fetchall()
        by_id = {row["id"]: row for row in rows}
        return [
            {
                "id": memory_id,
                "summary": self._open(by_id[memory_id]["summary"] or ""),
                "content": self._open(by_id[memory_id]["content"]),
                "kind": by_id[memory_id]["kind"],
            }
            for memory_id in ids
            if memory_id in by_id
        ]

    def update_memory_record(self, memory_id, content=None, kind=None, meta=None, summary=None):
        fields, values = [], []
        if content is not None:
            fields.append("content=?")
            values.append(self._seal(str(content)))
            if summary is None:
                summary = self._memory_summary(content)
        if summary is not None:
            fields.append("summary=?")
            values.append(self._seal(self._memory_summary(summary)))
        if kind is not None:
            fields.append("kind=?")
            values.append(str(kind))
        if meta is not None:
            fields.append("meta=?")
            values.append(self._seal(self._json(meta)))
        if not fields:
            return False
        with self._lock:
            values.append(int(memory_id))
            cursor = self.conn.execute(f"UPDATE memories SET {', '.join(fields)} WHERE id=?", values)
            self.conn.commit()
            return cursor.rowcount > 0

    def delete_memory_record(self, memory_id):
        with self._lock:
            cursor = self.conn.execute("DELETE FROM memories WHERE id=?", (int(memory_id),))
            self.conn.commit()
            return cursor.rowcount > 0

    def add_knowledge(self, name, content, source=None):
        """Persist a trusted reference document for retrieval by the agent."""
        with self._lock:
            self.conn.execute(
                "INSERT INTO memories(summary, content, kind, meta) VALUES (?, ?, ?, ?)",
                (self._seal(self._memory_summary(content)), self._seal(content), "knowledge", self._seal(self._json({"name": name, "source": source}))),
            )
            self.conn.commit()

    def knowledge(self, query=None, limit=3):
        with self._lock:
            return self._knowledge_locked(query, limit)

    def _knowledge_locked(self, query=None, limit=3):
        if query and self._fts_available:
            terms = [t for t in re.findall(r"[\wáéíóúñü]+", query.lower()) if len(t) > 2]
            if terms:
                match = " OR ".join('"' + term.replace('"', "") + '"' for term in terms)
                rows = self.conn.execute(
                    "SELECT m.content FROM memory_search s JOIN memories m ON m.id=s.rowid "
                    "WHERE memory_search MATCH ? AND m.kind='knowledge' ORDER BY bm25(memory_search) LIMIT ?",
                    (match, limit),
                ).fetchall()
                return [self._open(row["content"]) for row in rows]
        rows = self.conn.execute(
            "SELECT content, meta FROM memories WHERE kind='knowledge' ORDER BY id DESC LIMIT 500"
        ).fetchall()
        if not query:
            return [self._open(row["content"]) for row in rows[:limit]]
        terms = [t for t in re.findall(r"[\wáéíóúñü]+", query.lower()) if len(t) > 2]
        scored = []
        for row in rows:
            content = self._open(row["content"])
            score = sum(content.lower().count(term) for term in terms)
            scored.append((score, content))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [content for score, content in scored[:limit] if score]

    def search_text(self, vector_or_query, k=5, kind=None):
        with self._lock:
            return self._search_text_locked(vector_or_query, k, kind)

    def _search_text_locked(self, vector_or_query, k=5, kind=None):
        query = vector_or_query if isinstance(vector_or_query, str) else ""
        if not query:
            return []
        terms = [t for t in re.findall(r"[\wáéíóúñü]+", query.lower()) if len(t) > 2]
        if self._fts_available and terms:
            match = " OR ".join('"' + term.replace('"', "") + '"' for term in terms)
            if kind:
                rows = self.conn.execute(
                    "SELECT m.content FROM memory_search s JOIN memories m ON m.id=s.rowid "
                    "WHERE memory_search MATCH ? AND m.kind=? ORDER BY bm25(memory_search) LIMIT ?",
                    (match, kind, k),
                ).fetchall()
            else:
                rows = self.conn.execute(
                    "SELECT m.content FROM memory_search s JOIN memories m ON m.id=s.rowid "
                    "WHERE memory_search MATCH ? ORDER BY bm25(memory_search) LIMIT ?",
                    (match, k),
                ).fetchall()
            return [self._open(row["content"]) for row in rows]
        if kind:
            rows = self.conn.execute(
                "SELECT content FROM memories WHERE kind=? ORDER BY id DESC LIMIT 500", (kind,)
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT content FROM memories ORDER BY id DESC LIMIT 500").fetchall()
        scored = []
        for row in rows:
            content = self._open(row["content"])
            low = content.lower()
            score = sum(low.count(term) for term in terms)
            if score:
                scored.append((score, content))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [content for _, content in scored[:k]]

    def list_recent_sessions(self, limit=20):
        """Return distinct session names ordered by recent activity."""
        with self._lock:
            rows = self.conn.execute(
                "SELECT session FROM conversation_messages GROUP BY session ORDER BY MAX(id) DESC LIMIT ?",
                (max(1, int(limit)),),
            ).fetchall()
        return [row[0] for row in rows if row[0]]

    def prune_by_kind_and_age(self, kinds=("note", "task_result"), days=30):
        """Prune transient memories older than the given days."""
        with self._lock:
            placeholders = ",".join("?" for _ in kinds)
            cursor = self.conn.execute(
                f"DELETE FROM memories WHERE kind IN ({placeholders}) AND created_at < datetime('now', ?)",
                (*kinds, f"-{max(1, int(days))} days"),
            )
            self.conn.commit()
            return cursor.rowcount

    def add_procedure(self, name, instructions, meta=None):
        with self._lock:
            self.conn.execute(
                """INSERT INTO procedures(name, instructions, meta) VALUES (?, ?, ?)
                   ON CONFLICT(name) DO UPDATE SET instructions=excluded.instructions,
                   updated_at=CURRENT_TIMESTAMP, meta=excluded.meta""",
                (name.strip(), self._seal(instructions.strip()), self._seal(self._json(meta or {}))),
            )
            self.conn.commit()

    def list_procedures(self):
        result = []
        for row in self.conn.execute("SELECT name, instructions, updated_at FROM procedures ORDER BY name").fetchall():
            item = dict(row)
            item["instructions"] = self._open(item["instructions"])
            result.append(item)
        return result

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
        with self._lock:
            self.conn.execute(
                "INSERT INTO tasks(task, result, provider, success) VALUES (?, ?, ?, ?)",
                (self._seal(self._json(task)), self._seal(result), provider, int(bool(success))),
            )
            self.conn.commit()

    def record_audit(self, action, request=None, result=None, success=True, actor="ada", correlation_id=None):
        with self._lock:
            self.conn.execute(
                "INSERT INTO audit_log(action, actor, request, result, success, correlation_id) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    str(action),
                    actor,
                    self._seal(self._json(request)) if request is not None else None,
                    self._seal(self._json(result)) if result is not None else None,
                    int(bool(success)),
                    correlation_id,
                ),
            )
            self.conn.commit()

    def recent_audit(self, limit=50):
        with self._lock:
            result = []
            for row in self.conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall():
                item = dict(row)
                if item.get("request") is not None:
                    item["request"] = self._open(item["request"])
                if item.get("result") is not None:
                    item["result"] = self._open(item["result"])
                result.append(item)
            return result

    def publish_event(self, topic, payload, priority=0, dedupe_key=None, delay_seconds=0):
        with self._lock:
            if dedupe_key:
                existing = self.conn.execute(
                    "SELECT id FROM events WHERE dedupe_key=? AND status IN ('pending', 'processing') AND cancelled=0 "
                    "ORDER BY id DESC LIMIT 1",
                    (str(dedupe_key),),
                ).fetchone()
                if existing:
                    return existing["id"]
            cursor = self.conn.execute(
                "INSERT INTO events(topic, payload, priority, dedupe_key, available_at) "
                "VALUES (?, ?, ?, ?, datetime('now', ?))",
                (
                    str(topic),
                    json.dumps(payload, ensure_ascii=False, default=str),
                    int(priority),
                    str(dedupe_key) if dedupe_key else None,
                    f"+{max(0, int(delay_seconds))} seconds",
                ),
            )
            self.conn.commit()
            return cursor.lastrowid

    def claim_events(self, limit=10, lease_seconds=300, owner=None):
        with self._lock:
            self.conn.execute(
                "UPDATE events SET status='pending', locked_at=NULL, lock_owner=NULL "
                "WHERE status='processing' AND (locked_at IS NULL OR locked_at < datetime('now', ?))",
                (f"-{max(1, int(lease_seconds))} seconds",),
            )
            rows = self.conn.execute(
                "SELECT * FROM events WHERE status='pending' AND cancelled=0 AND available_at <= CURRENT_TIMESTAMP "
                "ORDER BY priority DESC, id LIMIT ?",
                (limit,),
            ).fetchall()
            for row in rows:
                self.conn.execute(
                    "UPDATE events SET status='processing', attempts=attempts+1, locked_at=CURRENT_TIMESTAMP, "
                    "lock_owner=? WHERE id=?",
                    (owner, row["id"]),
                )
            self.conn.commit()
            return [dict(row) for row in rows]

    def finish_event(self, event_id, success=True, error=None, retry_seconds=0):
        with self._lock:
            if success:
                self.conn.execute(
                    "UPDATE events SET status='done', last_error=NULL, locked_at=NULL, lock_owner=NULL WHERE id=?",
                    (event_id,),
                )
            elif retry_seconds:
                self.conn.execute(
                    "UPDATE events SET status='pending', available_at=datetime('now', ?), last_error=?, "
                    "locked_at=NULL, lock_owner=NULL WHERE id=?",
                    (f"+{int(retry_seconds)} seconds", str(error or ""), event_id),
                )
            else:
                self.conn.execute(
                    "UPDATE events SET status='failed', last_error=?, locked_at=NULL, lock_owner=NULL WHERE id=?",
                    (str(error or ""), event_id),
                )
            self.conn.commit()

    def cancel_event(self, event_id):
        with self._lock:
            cursor = self.conn.execute(
                "UPDATE events SET cancelled=1, status='cancelled', locked_at=NULL, lock_owner=NULL "
                "WHERE id=? AND status IN ('pending', 'processing')",
                (event_id,),
            )
            self.conn.commit()
            return cursor.rowcount > 0

    def recent_tasks(self, limit=10):
        result = []
        with self._lock:
            rows = self.conn.execute("SELECT * FROM tasks ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        for row in rows:
            item = dict(row)
            item["task"] = self._open(item["task"])
            item["result"] = self._open(item["result"])
            result.append(item)
        return result

    def purge_tasks(self, keep=1000):
        with self._lock:
            cursor = self.conn.execute(
                "DELETE FROM tasks WHERE id NOT IN (SELECT id FROM tasks ORDER BY id DESC LIMIT ?)",
                (max(0, int(keep)),),
            )
            self.conn.commit()
            return cursor.rowcount

    def backup_to(self, path):
        """Create a consistent SQLite backup without copying a live WAL file."""
        target = Path(path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            destination = sqlite3.connect(str(target))
            try:
                self.conn.backup(destination)
            finally:
                destination.close()
        return str(target)

    def append_conversation(self, messages, session="main"):
        rows = [
            (session, item.get("role", "assistant"), self._seal(item.get("text", "")), item.get("model"))
            for item in messages
            if item.get("text") is not None
        ]
        if not rows:
            return
        with self._lock:
            self.conn.executemany(
                "INSERT INTO conversation_messages(session, role, text, model) VALUES (?, ?, ?, ?)",
                rows,
            )
            self.conn.commit()

    def conversation(self, session="main", limit=1000):
        with self._lock:
            rows = self.conn.execute(
                "SELECT id, created_at, role, text, model FROM conversation_messages "
                "WHERE session=? ORDER BY id DESC LIMIT ?",
                (session, limit),
            ).fetchall()
        result = []
        for row in reversed(rows):
            item = dict(row)
            item["text"] = self._open(item["text"])
            result.append(item)
        return result

    def get_conversation_summary(self, session="main"):
        with self._lock:
            row = self.conn.execute("SELECT summary FROM conversation_summaries WHERE session=?", (session,)).fetchone()
        return self._open(row[0]) if row else ""

    def save_conversation_summary(self, session, summary):
        with self._lock:
            self.conn.execute(
                "INSERT INTO conversation_summaries(session, summary, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) "
                "ON CONFLICT(session) DO UPDATE SET summary=excluded.summary, updated_at=CURRENT_TIMESTAMP",
                (session, self._seal(summary or "")),
            )
            self.conn.commit()

    def compact_conversation(self, session, summary, keep_messages=40):
        """Persist a bounded summary and remove only the older message rows."""
        keep_messages = max(1, int(keep_messages))
        with self._lock:
            rows = self.conn.execute(
                "SELECT id FROM conversation_messages WHERE session=? ORDER BY id DESC LIMIT ?",
                (session, keep_messages),
            ).fetchall()
            if not rows:
                return 0
            oldest_kept_id = rows[-1][0]
            cursor = self.conn.execute(
                "DELETE FROM conversation_messages WHERE session=? AND id<?",
                (session, oldest_kept_id),
            )
            self.conn.execute(
                "INSERT INTO conversation_summaries(session, summary, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) "
                "ON CONFLICT(session) DO UPDATE SET summary=excluded.summary, updated_at=CURRENT_TIMESTAMP",
                (session, self._seal(summary or "")),
            )
            self.conn.commit()
            return cursor.rowcount

    def clear_conversation(self, session="main"):
        with self._lock:
            self.conn.execute("DELETE FROM conversation_messages WHERE session=?", (session,))
            self.conn.commit()

    def get_folder_alias(self, alias):
        row = self.conn.execute(
            "SELECT alias, path, confidence, use_count FROM folder_aliases WHERE alias=?", (alias,)
        ).fetchone()
        return dict(row) if row else None

    def save_folder_alias(self, alias, path, confidence=1.0):
        with self._lock:
            self.conn.execute(
                """INSERT INTO folder_aliases(alias, path, confidence, use_count)
                   VALUES (?, ?, ?, 1)
                   ON CONFLICT(alias) DO UPDATE SET path=excluded.path,
                   confidence=excluded.confidence, use_count=folder_aliases.use_count+1,
                   updated_at=CURRENT_TIMESTAMP""",
                (alias, path, float(confidence)),
            )
            self.conn.commit()

    def get_folder_context(self, session):
        row = self.conn.execute("SELECT path FROM folder_contexts WHERE session=?", (session,)).fetchone()
        return row["path"] if row else None

    def save_folder_context(self, session, path):
        with self._lock:
            self.conn.execute(
                """INSERT INTO folder_contexts(session, path) VALUES (?, ?)
                   ON CONFLICT(session) DO UPDATE SET path=excluded.path, updated_at=CURRENT_TIMESTAMP""",
                (session, path),
            )
            self.conn.commit()

    def clear_folder_context(self, session):
        with self._lock:
            self.conn.execute("DELETE FROM folder_contexts WHERE session=?", (session,))
            self.conn.commit()

    @staticmethod
    def _normalize_folder_name(value):
        value = unicodedata.normalize("NFKD", str(value).casefold())
        value = "".join(char for char in value if not unicodedata.combining(char))
        return re.sub(r"\s+", " ", re.sub(r"[^\w ]", " ", value)).strip()

    def index_folders(self, parent_path, paths):
        rows = []
        for value in paths:
            path = Path(value).expanduser().absolute()
            rows.append(
                (
                    str(path),
                    path.name,
                    self._normalize_folder_name(path.name),
                    str(Path(parent_path).expanduser().absolute()),
                )
            )
        if not rows:
            return 0
        with self._lock:
            self.conn.executemany(
                """INSERT INTO folder_index(path,name,normalized_name,parent_path) VALUES(?,?,?,?)
                   ON CONFLICT(path) DO UPDATE SET name=excluded.name,
                   normalized_name=excluded.normalized_name, parent_path=excluded.parent_path,
                   last_seen=CURRENT_TIMESTAMP""",
                rows,
            )
            self.conn.commit()
        return len(rows)

    def search_folders(self, terms, limit=20):
        normalized = [self._normalize_folder_name(term) for term in terms if self._normalize_folder_name(term)]
        if not normalized:
            return []
        where = " AND ".join("normalized_name LIKE ?" for _ in normalized)
        params = [f"%{term}%" for term in normalized] + [max(1, int(limit))]
        rows = self.conn.execute(
            f"SELECT path,name,parent_path,last_seen,use_count FROM folder_index WHERE {where} "
            "ORDER BY use_count DESC, last_seen DESC LIMIT ?",
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def close(self):
        with self._lock:
            with self._connections_lock:
                connections = list(self._connections)
                self._connections.clear()
            for conn in connections:
                try:
                    conn.close()
                except sqlite3.Error:
                    pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
