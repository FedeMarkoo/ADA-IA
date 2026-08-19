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
        self.db_path = ':memory:' if str(db_path) == ':memory:' else str(Path(db_path).expanduser().resolve())
        if self.db_path != ':memory:':
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._lock = threading.RLock()
        self.conn.row_factory = sqlite3.Row
        self._fts_available = False
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.execute('PRAGMA synchronous=NORMAL')
        self._ensure_tables()

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
                last_error TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_memories_kind_id ON memories(kind, id DESC);
            CREATE INDEX IF NOT EXISTS idx_conversation_session_id ON conversation_messages(session, id DESC);
            CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(id DESC);
        """)
        columns = {row[1] for row in self.conn.execute('PRAGMA table_info(router_catalog)').fetchall()}
        if 'keywords' not in columns:
            self.conn.execute('ALTER TABLE router_catalog ADD COLUMN keywords TEXT')
        self.conn.commit()
        try:
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

    def _seed_dynamic_ai_defaults(self):
        actions = {
            'analyze_photo': ('Analizar una foto', ('foto','imagen','raw','jpg','nef','arw','enfoque','exposición','iso')),
            'select_photo_batch': ('Seleccionar un lote de fotos', ('selección','seleccionar','descartes','ráfaga','rafaga','lote','xmp')),
            'lightroom': ('Consultar o preparar acciones de Lightroom', ('lightroom','colección','sqlite','biblioteca','rechazadas')),
            'list_photos': ('Listar fotos', ('listar fotos','mostrame fotos','ver fotos')),
            'list_files': ('Listar archivos', ('listar archivos','lista los archivos','listame los archivos','documentos')),
            'list_dirs': ('Listar carpetas', ('carpetas','directorios','estructura')),
            'group_files': ('Agrupar archivos', ('agrupar','mover archivos','juntar archivos')),
            'organize': ('Organizar archivos', ('organizar','ordenar archivos','ordenar los archivos')),
            'suggest': ('Sugerir una acción general', ('sugerir','recomendar')),
            'run': ('Ejecutar un script', ('ejecutar','correr comando','script')),
            'food': ('Compras, recetas, cocina y planificación de comidas', ('comida','comidas','receta','recetas','cocinar','compras','supermercado','ingredientes','comer')),
            'gmail_read': ('Leer metadatos de Gmail', ('gmail','correo','mail','email','bandeja')),
            'gmail_send': ('Enviar un correo de Gmail', ('enviar correo','mandar mail','gmail enviar')),
            'instagram_publish': ('Publicar una imagen en Instagram', ('instagram','publicar foto','postear')),
            'ask': ('Conversación general', ()),
        }
        self.conn.executemany(
            'INSERT OR IGNORE INTO router_catalog(action,description,keywords) VALUES (?,?,?)',
            [(action, description, json.dumps(keywords, ensure_ascii=False)) for action, (description, keywords) in actions.items()]
        )
        templates = {
            'router': ('Sos el router de ADA. Devolvé SOLO JSON válido. Elegí una action del catálogo: {actions}. '
                       'Para comida usá domain=shopping|recipes y food_action={food_actions}. '
                       'Si el pedido trata de cocinar, comer, recetas, gustos o supermercado, elegí food. '
                       'No ejecutes acciones. Historial: {history}\nPedido: {text}'),
            'food_classifier': ('Clasificá semánticamente el pedido. Devolvé SOLO JSON válido. '
                                'Si trata de comida, cocina, recetas o compras, is_food=true y food_action={food_actions}. '
                                'Una duda como qué cocinar usa advise. Si no es comida, is_food=false. '
                                'Historial: {history}\nPedido: {text}'),
            'food_mutation_verifier': ('Verificá si el usuario pidió modificar explícitamente la lista de compras. '
                                       'allow=true para agregar, comprar, marcar o quitar un producto concreto; '
                                       'allow=false para recomendaciones o recetas. Devolvé SOLO JSON. '
                                       'Intención: {intent}\nPedido: {text}'),
            'food_advisor': ('Sos el asesor culinario personal. Respondé en español rioplatense. Usá el perfil y catálogo. '
                             'Priorizá comidas simples, rendidoras, reutilizables y aptas para freezer; evitá lentejas, '
                             'supremas y repetir pizza. Interpretá restricciones del hilo. Elegí una recomendación y como '
                             'máximo una alternativa. No hagas cuestionarios, no muestres razonamiento ni pasos internos. '
                             'Devolvé SOLO JSON con el campo reply. PERFIL:\n{profile}\nCATÁLOGO:\n{catalog}\n'
                             'HILO DE USUARIO:\n{conversation}\nPEDIDO:\n{request}')
        }
        self.conn.executemany('INSERT OR IGNORE INTO prompt_templates(name,body) VALUES (?,?)', templates.items())
        schemas = {
            'router': {
                'type': 'object', 'properties': {
                    'action': {'type': 'string', 'enum': ['analyze_photo','select_photo_batch','lightroom','list_photos','list_files','list_dirs','group_files','organize','suggest','run','food','gmail_read','gmail_send','instagram_publish','ask']},
                    'domain': {'type': 'string', 'enum': ['shopping','recipes']},
                    'food_action': {'type': 'string', 'enum': ['add','list','check','remove','save','suggest','recipe_to_shopping','advise']},
                    'item': {'type': 'string'}, 'quantity': {'type': 'string'}, 'unit': {'type': 'string'},
                    'name': {'type': 'string'}, 'ingredients': {'type': 'string'}, 'available': {'type': 'string'},
                    'confidence': {'type': 'number'}, 'reason': {'type': 'string'},
                    'needs_clarification': {'type': 'boolean'}, 'clarifying_question': {'type': 'string'},
                }, 'required': ['action'], 'additionalProperties': False,
            },
            'food': {
                'type': 'object', 'properties': {
                    'is_food': {'type': 'boolean'}, 'domain': {'type': 'string', 'enum': ['shopping','recipes']},
                    'food_action': {'type': 'string', 'enum': ['add','list','check','remove','save','recipe_to_shopping','advise']},
                    'item': {'type': 'string'}, 'quantity': {'type': 'string'}, 'unit': {'type': 'string'},
                    'name': {'type': 'string'}, 'ingredients': {'type': 'string'}, 'confidence': {'type': 'number'},
                }, 'required': ['is_food'], 'additionalProperties': False,
            },
            'food_verify': {'type': 'object', 'properties': {'allow': {'type': 'boolean'}, 'reason': {'type': 'string'}}, 'required': ['allow'], 'additionalProperties': False},
            'food_reply': {'type': 'object', 'properties': {'reply': {'type': 'string'}}, 'required': ['reply'], 'additionalProperties': False},
        }
        self.conn.executemany('INSERT OR IGNORE INTO json_schemas(name,body) VALUES (?,?)', [(name, json.dumps(body, ensure_ascii=False)) for name, body in schemas.items()])
        self.conn.commit()

    def router_actions(self):
        rows = [dict(row) for row in self.conn.execute(
            'SELECT action,description,keywords FROM router_catalog WHERE enabled=1 ORDER BY action'
        ).fetchall()]
        for row in rows:
            try:
                row['keywords'] = json.loads(row.get('keywords') or '[]')
            except (TypeError, ValueError):
                row['keywords'] = []
        return rows

    def prompt_template(self, name, fallback=''):
        row = self.conn.execute('SELECT body FROM prompt_templates WHERE name=? AND enabled=1', (name,)).fetchone()
        return row['body'] if row else fallback

    def upsert_prompt_template(self, name, body, meta=None):
        with self._lock:
            self.conn.execute(
                'INSERT INTO prompt_templates(name,body,meta) VALUES (?,?,?) '
                'ON CONFLICT(name) DO UPDATE SET body=excluded.body,meta=excluded.meta,updated_at=CURRENT_TIMESTAMP',
                (name, body, json.dumps(meta or {}, ensure_ascii=False)),
            )
            self.conn.commit()

    def json_schema(self, name, fallback=None):
        row = self.conn.execute('SELECT body FROM json_schemas WHERE name=? AND enabled=1', (name,)).fetchone()
        if not row:
            return fallback
        try:
            return json.loads(row['body'])
        except (TypeError, ValueError):
            return fallback

    def upsert_json_schema(self, name, schema, meta=None):
        with self._lock:
            self.conn.execute(
                'INSERT INTO json_schemas(name,body,meta) VALUES (?,?,?) '
                'ON CONFLICT(name) DO UPDATE SET body=excluded.body,meta=excluded.meta,updated_at=CURRENT_TIMESTAMP',
                (name, json.dumps(schema, ensure_ascii=False), json.dumps(meta or {}, ensure_ascii=False)),
            )
            self.conn.commit()

    def add(self, path, vector=None, meta=None):
        with self._lock:
            self.conn.execute("INSERT OR REPLACE INTO images(path, meta) VALUES (?, ?)",
                              (str(path), json.dumps(meta or {}, ensure_ascii=False)))
            self.conn.commit()

    def add_text(self, text, vector=None, meta=None, kind="note"):
        with self._lock:
            self.conn.execute("INSERT INTO memories(content, kind, meta) VALUES (?, ?, ?)",
                              (str(text), kind, json.dumps(meta or {}, ensure_ascii=False)))
            self.conn.commit()

    def add_knowledge(self, name, content, source=None):
        """Persist a trusted reference document for retrieval by the agent."""
        with self._lock:
            self.conn.execute("INSERT INTO memories(content, kind, meta) VALUES (?, ?, ?)",
                              (str(content), "knowledge", json.dumps({'name': name, 'source': source}, ensure_ascii=False)))
            self.conn.commit()

    def knowledge(self, query=None, limit=3):
        if query and self._fts_available:
            terms = [t for t in re.findall(r"[\wáéíóúñü]+", query.lower()) if len(t) > 2]
            if terms:
                match = ' OR '.join('"' + term.replace('"', '') + '"' for term in terms)
                rows = self.conn.execute(
                    "SELECT m.content FROM memory_search s JOIN memories m ON m.id=s.rowid "
                    "WHERE memory_search MATCH ? AND m.kind='knowledge' ORDER BY bm25(memory_search) LIMIT ?",
                    (match, limit),
                ).fetchall()
                return [row['content'] for row in rows]
        rows = self.conn.execute(
            "SELECT content, meta FROM memories WHERE kind='knowledge' ORDER BY id DESC LIMIT 10000"
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
        if self._fts_available and terms:
            match = ' OR '.join('"' + term.replace('"', '') + '"' for term in terms)
            rows = self.conn.execute(
                "SELECT m.content FROM memory_search s JOIN memories m ON m.id=s.rowid "
                "WHERE memory_search MATCH ? ORDER BY bm25(memory_search) LIMIT ?",
                (match, k),
            ).fetchall()
            return [row['content'] for row in rows]
        rows = self.conn.execute("SELECT content FROM memories ORDER BY id DESC LIMIT 10000").fetchall()
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
        with self._lock:
            self.conn.execute("INSERT INTO tasks(task, result, provider, success) VALUES (?, ?, ?, ?)",
                              (json.dumps(task, ensure_ascii=False), str(result), provider, int(bool(success))))
            self.conn.commit()

    def record_audit(self, action, request=None, result=None, success=True, actor='ada', correlation_id=None):
        with self._lock:
            self.conn.execute(
                'INSERT INTO audit_log(action, actor, request, result, success, correlation_id) VALUES (?, ?, ?, ?, ?, ?)',
                (str(action), actor, json.dumps(request, ensure_ascii=False, default=str) if request is not None else None,
                 json.dumps(result, ensure_ascii=False, default=str) if result is not None else None,
                 int(bool(success)), correlation_id),
            )
            self.conn.commit()

    def recent_audit(self, limit=50):
        with self._lock:
            return [dict(row) for row in self.conn.execute(
                'SELECT * FROM audit_log ORDER BY id DESC LIMIT ?', (limit,)
            ).fetchall()]

    def publish_event(self, topic, payload):
        with self._lock:
            cursor = self.conn.execute(
                'INSERT INTO events(topic, payload) VALUES (?, ?)',
                (str(topic), json.dumps(payload, ensure_ascii=False, default=str)),
            )
            self.conn.commit()
            return cursor.lastrowid

    def claim_events(self, limit=10):
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM events WHERE status='pending' AND available_at <= CURRENT_TIMESTAMP ORDER BY id LIMIT ?",
                (limit,),
            ).fetchall()
            for row in rows:
                self.conn.execute("UPDATE events SET status='processing', attempts=attempts+1 WHERE id=?", (row['id'],))
            self.conn.commit()
            return [dict(row) for row in rows]

    def finish_event(self, event_id, success=True, error=None, retry_seconds=0):
        with self._lock:
            if success:
                self.conn.execute("UPDATE events SET status='done', last_error=NULL WHERE id=?", (event_id,))
            elif retry_seconds:
                self.conn.execute(
                    "UPDATE events SET status='pending', available_at=datetime('now', ?), last_error=? WHERE id=?",
                    (f'+{int(retry_seconds)} seconds', str(error or ''), event_id),
                )
            else:
                self.conn.execute("UPDATE events SET status='failed', last_error=? WHERE id=?", (str(error or ''), event_id))
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
