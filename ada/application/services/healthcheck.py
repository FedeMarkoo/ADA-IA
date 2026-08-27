"""Functional ADA healthchecks, backed by the same SQLite memory database."""

import json
import re
import sqlite3
import threading
import urllib.request

FUNCTIONAL_CATEGORY_LABELS = {
    "commands": "Sistema",
    "chat": "Conversación",
    "reasoning": "Razonamiento",
    "food": "Alimentación",
    "photography": "Fotos y archivos",
    "filesystem": "Fotos y archivos",
    "mcp_google_drive": "Fotos y archivos",
    "web": "Internet",
    "finance": "Operaciones monetarias",
    "calendar": "Calendario",
    "mcp_google_calendar": "Calendario",
    "gmail": "Correo",
    "mcp_gmail": "Correo",
    "agent": "Capacidades de ADA",
    "diagnostics": "Diagnóstico",
    "architecture": "Arquitectura",
    "metrics": "Observabilidad",
    "safety": "Seguridad",
}

MCP_REQUIRED_CATEGORIES = {
    "web",
    "finance",
    "calendar",
    "mcp_google_calendar",
    "gmail",
    "mcp_gmail",
    "filesystem",
    "photography",
    "mcp_google_drive",
}


def requires_mcp(item):
    """Return whether a healthcheck result must be grounded in a tool call."""
    return str(item.get("category") or "").lower() in MCP_REQUIRED_CATEGORIES


def functional_category(category):
    """Translate internal source categories into user-facing capabilities."""
    return FUNCTIONAL_CATEGORY_LABELS.get(category, str(category or "Otros").replace("_", " ").title())


def _case(category, case_id, name, capability, prompt, must_match, tags=None):
    """Small declaration helper: adding a case is one data-only entry."""
    return {
        "id": case_id,
        "category": category,
        "name": name,
        "capability": capability,
        "tags": tags or [capability, "readonly"],
        "prompt": prompt,
        "must_match": must_match,
    }


# Data catalog. Categories may contain any number of prompts; no API/UI code is
# needed to add another case here (custom cases can also be added through POST).
HEALTHCHECK_PROMPTS = [
    _case(
        "web",
        "web_search",
        "Búsqueda en internet",
        "web",
        "Buscá en internet una noticia actual sobre inteligencia artificial. Resumí el hallazgo en dos frases e incluí al menos una fuente o enlace.",
        [r"(http|fuente|enlace|sitio)", r"(inteligencia artificial|IA)"],
    ),
    _case(
        "web",
        "web_search_fact",
        "Verificación de una búsqueda",
        "web",
        "Buscá dos fuentes actuales y confiables sobre el precio o la evolución reciente del dólar en Argentina. Compará las fechas y aclarame si hay diferencias.",
        [r"(fuente|enlace|sitio)", r"(dólar|dolar)", r"(fecha|diferencia|compar)"],
    ),
    _case(
        "photography",
        "event_photos_report",
        "Reporte de fotos de eventos",
        "photography",
        "Prepará un reporte de las fotos del evento más reciente que encuentres en mi Drive. Indicá evento, cantidad de fotos, aceptadas/rechazadas y si están exportadas. Si no podés acceder, explicá el motivo.",
        [r"(foto|evento|Drive)", r"(exportad|no puedo|no encontr|acced)"],
    ),
    _case(
        "photography",
        "event_photos_quality",
        "Estado de exportación de un evento",
        "photography",
        "Revisá el evento de fotos Sofia en Google Drive y decime si tiene originales, seleccionadas y exportadas. Resumí faltantes sin modificar archivos.",
        [r"(Sofia|evento|Drive)", r"(original|seleccion|exportad|no encontr|acced)"],
    ),
    _case(
        "finance",
        "financial_operations",
        "Reporte de operaciones monetarias",
        "finance",
        "Dame un reporte actualizado y prudente sobre oportunidades de comprar o vender acciones, cripto o dólares. Compará alternativas, riesgos, horizonte y datos que faltan. No ejecutes ninguna operación ni presentes esto como asesoramiento financiero personalizado.",
        [r"(compr|vend|mant|alternativ)", r"(riesgo|volatilidad)", r"(no ejecut|no es asesoramiento|financier)"],
    ),
    _case(
        "finance",
        "financial_sources",
        "Fuentes para una decisión financiera",
        "finance",
        "Buscá información actual sobre una acción, una criptomoneda y el dólar que yo podría evaluar. Para cada uno indicá fuente, fecha, volatilidad y qué debería verificar antes de decidir. No compres ni vendas nada.",
        [r"(acción|cripto|dólar|dolar)", r"(fuente|fecha)", r"(riesgo|volatilidad|verificar)"],
    ),
    _case(
        "calendar",
        "next_calendar_event",
        "Próximo evento del calendario",
        "calendar",
        "Decime cuál es mi próximo evento en Google Calendar. Mostrá título, fecha, hora y calendario. Solo lectura; si no hay eventos o falta conexión, decilo claramente.",
        [r"(próxim|evento|calendar)", r"(fecha|hora|no hay|no encontr|conexi)"],
    ),
    _case(
        "calendar",
        "calendar_week",
        "Agenda de los próximos días",
        "calendar",
        "Dame un resumen de mis eventos de Google Calendar durante los próximos siete días, ordenados por fecha y hora. No crees ni modifiques eventos.",
        [r"(evento|calendar)", r"(fecha|hora|semana|días|no hay)"],
    ),
    _case(
        "gmail",
        "mail_report",
        "Reporte de mails",
        "gmail",
        "Hacé un reporte de mis mails recientes: cantidad relevante, asuntos, remitentes y fechas. No respondas, envíes ni modifiques correos; si no hay acceso, explicalo.",
        [r"(mail|correo|mails?)", r"(asunto|remitente|fecha|no hay|acceso)"],
    ),
    _case(
        "gmail",
        "last_email",
        "Último correo",
        "gmail",
        "Decime cuál es mi último correo recibido: asunto, remitente, fecha y un resumen breve. Solo lectura; no abras enlaces ni realices acciones.",
        [r"(correo|mail)", r"(asunto|remitente|fecha|no encontr|acceso)"],
    ),
    _case(
        "gmail",
        "gmail_unread",
        "Correos no leídos",
        "gmail",
        "¿Cuántos correos no leídos tengo y cuáles son los tres asuntos más importantes? Solo consultá Gmail, no marques nada como leído.",
        [r"(correo|mail|Gmail)", r"(no le[ií]d|asunto|no hay|acceso)"],
    ),
    _case(
        "agent",
        "capabilities_summary",
        "Resumen de capacidades",
        "agent",
        "Explicame qué puede hacer ADA hoy. Organizá la respuesta por herramientas o categorías y distinguí entre consultar, recomendar y ejecutar.",
        [r"(puede|capacidad|herramienta)", r"(consult|recomend|ejecut)", r"(web|calendar|Gmail|foto)"],
    ),
    _case(
        "agent",
        "agent_readonly_boundary",
        "Límites de solo lectura",
        "agent",
        "Explicá qué tareas puede consultar ADA y cuáles requieren confirmación o no debe ejecutar automáticamente. No realices ninguna acción.",
        [r"(consult|leer|solo lectura)", r"(confirm|permiso|no debe|no ejecut)"],
    ),
    _case(
        "chat",
        "greeting",
        "Saludo inicial",
        "chat",
        "Hola ADA, respondeme en una frase breve y amable.",
        [r"(hola|buenas|qu[eé])"],
    ),
    _case(
        "food",
        "food_advice",
        "Recomendación de comida",
        "food",
        "Tengo arroz, huevos y tomate. Dame dos ideas fáciles para comer ahora.",
        [r"(arroz|huevo|tomate)"],
    ),
    _case(
        "reasoning",
        "summarize_explanation",
        "Concepto de copia de seguridad",
        "reasoning",
        "Explicá qué es una copia de seguridad en dos frases y diferenciá sincronización de respaldo.",
        [r"(sincronizaci[oó]n|sincronizar)", r"(respaldo|copia)"],
    ),
    _case(
        "reasoning",
        "compare_options",
        "Comparación de formatos de imagen",
        "reasoning",
        "Compará usar JPG, PNG y RAW para conservar fotografías. Indicá una ventaja y una desventaja de cada formato.",
        [r"JPG", r"PNG", r"RAW"],
    ),
    _case(
        "reasoning",
        "model_mode_explanation",
        "Modos de ejecución de modelos",
        "reasoning",
        "Explicá la diferencia entre modo liviano, híbrido y turbo de un agente local.",
        [r"liviano", r"h[ií]brido", r"turbo"],
    ),
    _case(
        "diagnostics",
        "telegram_diagnosis",
        "Diagnóstico de Telegram",
        "diagnostics",
        "Telegram dejó de responder. ¿Qué comprobaciones de diagnóstico harías antes de reiniciar nada?",
        [r"(instancia|token|getUpdates|logs|proceso)"],
    ),
    _case(
        "architecture",
        "mcp_explanation",
        "Ventajas del protocolo MCP",
        "architecture",
        "¿Qué ventaja tiene que la lógica de herramientas viva en un MCP y no en ADA?",
        [r"(MCP|herramienta)", r"(reutil|consist|separ|modular)"],
    ),
    _case(
        "safety",
        "safe_refusal",
        "Explicación segura de permisos",
        "safety",
        "Necesito una explicación general de cómo funcionan los permisos de una carpeta, sin acceder ni cambiar ningún archivo.",
        [r"(permiso|acceso)", r"(leer|escribir|ejecutar)"],
    ),
]


class HealthcheckStore:
    """Stores definitions and executions in the agent's existing SQLite DB."""

    def __init__(self, memory):
        # Keep healthcheck traffic on its own connection. The agent can spend
        # minutes inside a model/tool call; sharing its SQLite connection made
        # read-only catalog requests block and the UI rendered as empty.
        if str(getattr(memory, "db_path", ":memory:")) == ":memory:":
            self.conn = memory.conn
            self._lock = getattr(memory, "_lock", threading.RLock())
        else:
            with getattr(memory, "_lock", threading.RLock()):
                if not hasattr(memory, "_healthcheck_conn"):
                    healthcheck_conn = sqlite3.connect(str(memory.db_path), check_same_thread=False, timeout=30)
                    healthcheck_conn.row_factory = sqlite3.Row
                    healthcheck_conn.execute("PRAGMA busy_timeout=30000")
                    memory._healthcheck_conn = healthcheck_conn
                    memory._healthcheck_lock = threading.RLock()
            self.conn = memory._healthcheck_conn
            self._lock = memory._healthcheck_lock
        # Serialize catalog migrations/seeding on the dedicated healthcheck connection.
        self._lock.acquire()
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS healthcheck_prompts (
                id TEXT PRIMARY KEY, category TEXT NOT NULL DEFAULT 'general', name TEXT NOT NULL,
                capability TEXT NOT NULL, tags TEXT NOT NULL DEFAULT '[]', prompt TEXT NOT NULL,
                criteria TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS healthcheck_runs (
                id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, prompt_id TEXT NOT NULL,
                response TEXT, evaluation TEXT NOT NULL, elapsed_seconds REAL NOT NULL,
                request TEXT, status TEXT NOT NULL DEFAULT 'failed', status_code INTEGER,
                model TEXT, mcps TEXT NOT NULL DEFAULT '[]', trace TEXT NOT NULL DEFAULT '[]',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS healthcheck_batches (
                run_id TEXT PRIMARY KEY, total INTEGER NOT NULL, completed INTEGER NOT NULL DEFAULT 0,
                passed INTEGER NOT NULL DEFAULT 0, failed INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending', current_prompt_id TEXT,
                started_at TEXT DEFAULT CURRENT_TIMESTAMP, finished_at TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        run_columns = {row[1] for row in self.conn.execute("PRAGMA table_info(healthcheck_runs)")}
        additions = {
            "request": "TEXT",
            "status": "TEXT NOT NULL DEFAULT 'failed'",
            "status_code": "INTEGER",
            "model": "TEXT",
            "mcps": "TEXT NOT NULL DEFAULT '[]'",
            "trace": "TEXT NOT NULL DEFAULT '[]'",
        }
        for name, definition in additions.items():
            if name not in run_columns:
                self.conn.execute(f"ALTER TABLE healthcheck_runs ADD COLUMN {name} {definition}")
        columns = {row[1] for row in self.conn.execute("PRAGMA table_info(healthcheck_prompts)")}
        for name, definition in (
            ("category", "TEXT NOT NULL DEFAULT 'general'"),
            ("tags", "TEXT NOT NULL DEFAULT '[]'"),
        ):
            if name not in columns:
                self.conn.execute(f"ALTER TABLE healthcheck_prompts ADD COLUMN {name} {definition}")
        for item in HEALTHCHECK_PROMPTS:
            self.conn.execute(
                "INSERT OR IGNORE INTO healthcheck_prompts(id,category,name,capability,tags,prompt,criteria) VALUES (?,?,?,?,?,?,?)",
                (
                    item["id"],
                    item["category"],
                    item["name"],
                    item["capability"],
                    json.dumps(item["tags"]),
                    item["prompt"],
                    json.dumps(item["must_match"]),
                ),
            )
            self.conn.execute(
                "UPDATE healthcheck_prompts SET category=?, capability=?, tags=?, prompt=?, criteria=?, name=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (
                    item["category"],
                    item["capability"],
                    json.dumps(item["tags"]),
                    item["prompt"],
                    json.dumps(item["must_match"]),
                    item["name"],
                    item["id"],
                ),
            )
        self.conn.commit()
        self._lock.release()

    def prompts(self):
        rows = self.conn.execute(
            "SELECT id,category,name,capability,tags,prompt,criteria FROM healthcheck_prompts WHERE enabled=1 ORDER BY category,rowid"
        ).fetchall()
        return [
            {
                "id": r[0],
                "category": r[1],
                "functional_category": functional_category(r[1]),
                "name": r[2],
                "capability": r[3],
                "tags": json.loads(r[4] or "[]"),
                "prompt": r[5],
                "must_match": json.loads(r[6] or "[]"),
            }
            for r in rows
        ]

    def add_prompt(self, item):
        required = (item.get("id"), item.get("category"), item.get("name"), item.get("capability"), item.get("prompt"))
        if not all(str(value or "").strip() for value in required) or not item.get("must_match"):
            raise ValueError("id, category, name, capability, prompt y must_match son obligatorios")
        self.conn.execute(
            "INSERT INTO healthcheck_prompts(id,category,name,capability,tags,prompt,criteria) VALUES (?,?,?,?,?,?,?)",
            (
                item["id"].strip(),
                item["category"].strip(),
                item["name"].strip(),
                item["capability"].strip(),
                json.dumps(item.get("tags") or [item["capability"], "readonly"]),
                item["prompt"].strip(),
                json.dumps(item["must_match"]),
            ),
        )
        self.conn.commit()

    def save_run(
        self,
        run_id,
        prompt_id,
        response,
        evaluation,
        elapsed,
        request=None,
        status=None,
        status_code=None,
        model=None,
        mcps=None,
        trace=None,
    ):
        final_status = status or ("passed" if evaluation.get("passed") else "failed")
        self.conn.execute(
            "INSERT INTO healthcheck_runs(run_id,prompt_id,response,evaluation,elapsed_seconds,request,status,status_code,model,mcps,trace) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                run_id,
                prompt_id,
                response,
                json.dumps(evaluation, ensure_ascii=False),
                elapsed,
                request,
                final_status,
                status_code,
                model,
                json.dumps(mcps or [], ensure_ascii=False),
                json.dumps(trace or [], ensure_ascii=False),
            ),
        )
        self.conn.commit()

    def begin_batch(self, run_id, prompt_ids):
        self.conn.execute(
            "INSERT OR REPLACE INTO healthcheck_batches(run_id,total,status,current_prompt_id,updated_at) VALUES (?,?, 'pending', NULL, CURRENT_TIMESTAMP)",
            (run_id, len(prompt_ids)),
        )
        self.conn.commit()

    def mark_batch_running(self, run_id, prompt_id):
        self.conn.execute(
            "UPDATE healthcheck_batches SET status='running', current_prompt_id=?, updated_at=CURRENT_TIMESTAMP WHERE run_id=?",
            (prompt_id, run_id),
        )
        self.conn.commit()

    def mark_batch_item(self, run_id, passed):
        self.conn.execute(
            "UPDATE healthcheck_batches SET completed=completed+1, passed=passed+?, failed=failed+?, current_prompt_id=NULL, updated_at=CURRENT_TIMESTAMP WHERE run_id=? AND status='running'",
            (1 if passed else 0, 0 if passed else 1, run_id),
        )
        self.conn.commit()

    def finish_batch(self, run_id):
        self.conn.execute(
            "UPDATE healthcheck_batches SET status='completed', finished_at=CURRENT_TIMESTAMP, current_prompt_id=NULL, updated_at=CURRENT_TIMESTAMP WHERE run_id=? AND status='running'",
            (run_id,),
        )
        self.conn.commit()

    def interrupt_batch(self, run_id):
        """Stop presenting a stalled or user-cancelled batch as active."""
        self.conn.execute(
            "UPDATE healthcheck_batches SET status='interrupted', finished_at=CURRENT_TIMESTAMP, current_prompt_id=NULL, updated_at=CURRENT_TIMESTAMP WHERE run_id=? AND status IN ('pending','running')",
            (run_id,),
        )
        self.conn.commit()
        return self.conn.total_changes

    def recover_orphaned_batches(self, active_run_ids=()):
        """Mark runs from a previous/dead worker as interrupted.

        The worker registry is process-local. Therefore a pending/running row
        that is not present in it cannot still be executing after a server
        restart, and must not remain indefinitely in the active queue.
        """
        active_run_ids = tuple(active_run_ids)
        params = list(active_run_ids)
        where = "status IN ('pending','running')"
        if active_run_ids:
            placeholders = ",".join("?" for _ in active_run_ids)
            where += f" AND run_id NOT IN ({placeholders})"
        self.conn.execute(
            f"UPDATE healthcheck_batches SET status='interrupted', finished_at=CURRENT_TIMESTAMP, current_prompt_id=NULL, updated_at=CURRENT_TIMESTAMP WHERE {where}",
            params,
        )
        self.conn.commit()
        return self.conn.total_changes

    def active_batches(self):
        rows = self.conn.execute(
            "SELECT run_id,total,completed,passed,failed,status,current_prompt_id,started_at,finished_at,updated_at FROM healthcheck_batches WHERE status IN ('pending','running') ORDER BY started_at DESC"
        ).fetchall()
        return [self._batch_row(row) for row in rows]

    def recent_batches(self, limit=10):
        rows = self.conn.execute(
            "SELECT run_id,total,completed,passed,failed,status,current_prompt_id,started_at,finished_at,updated_at FROM healthcheck_batches ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._batch_row(row) for row in rows]

    def batch(self, run_id):
        row = self.conn.execute(
            "SELECT run_id,total,completed,passed,failed,status,current_prompt_id,started_at,finished_at,updated_at FROM healthcheck_batches WHERE run_id=?",
            (run_id,),
        ).fetchone()
        return self._batch_row(row) if row else None

    @staticmethod
    def _batch_row(row):
        return {
            "run_id": row[0],
            "total": row[1],
            "completed": row[2],
            "passed": row[3],
            "failed": row[4],
            "status": row[5],
            "current_prompt_id": row[6],
            "started_at": row[7],
            "finished_at": row[8],
            "updated_at": row[9],
            "percent": round(row[2] / max(1, row[1]) * 100, 1),
        }

    def history(self, limit=30):
        rows = self.conn.execute(
            "SELECT run_id,prompt_id,response,evaluation,elapsed_seconds,request,status,status_code,model,mcps,trace,created_at FROM healthcheck_runs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {
                "run_id": r[0],
                "prompt_id": r[1],
                "response": r[2],
                "evaluation": json.loads(r[3]),
                "elapsed_seconds": r[4],
                "request": r[5],
                "status": r[6],
                "status_code": r[7],
                "model": r[8],
                "mcps": json.loads(r[9] or "[]"),
                "trace": json.loads(r[10] or "[]"),
                "created_at": r[11],
            }
            for r in rows
        ]

    def latest_results(self):
        rows = self.conn.execute(
            "SELECT h.run_id,h.prompt_id,h.response,h.evaluation,h.elapsed_seconds,h.status,h.status_code,h.model,h.mcps,h.trace,h.created_at "
            "FROM healthcheck_runs h WHERE h.id=(SELECT MAX(id) FROM healthcheck_runs latest WHERE latest.prompt_id=h.prompt_id) "
            "ORDER BY h.prompt_id"
        ).fetchall()
        results = []
        for r in rows:
            evaluation = json.loads(r[3])
            results.append(
                {
                    "run_id": r[0],
                    "prompt_id": r[1],
                    "response": r[2],
                    "elapsed_seconds": r[4],
                    "status": r[5],
                    "status_code": r[6],
                    "model": r[7],
                    "mcps": json.loads(r[8] or "[]"),
                    "trace": json.loads(r[9] or "[]"),
                    "created_at": r[10],
                    **evaluation,
                }
            )
        return results


def evaluate(item, reply, elapsed, error=None):
    reply = str(reply or "")
    missing = [pattern for pattern in item.get("must_match", []) if not re.search(pattern, reply, re.I)]
    passed = not error and bool(reply) and not missing
    return {
        "passed": passed,
        "missing": missing,
        "reply_chars": len(reply),
        "elapsed_seconds": round(elapsed, 3),
        "error": error,
    }


FAILURE_MARKERS = re.compile(
    r"\b(no pude|no puedo|no tengo acceso|sin acceso|no est[aá] conectado|no encontr[eé]|no fue posible|error de conexi[oó]n|permiso denegado)\b",
    re.I,
)


def llm_judge(item, reply, endpoint="http://127.0.0.1:11434", model="llama3.2:3b", mcp_evidence=None):
    """Use an independent model to judge task completion, not keyword presence."""
    if not reply or (FAILURE_MARKERS.search(str(reply)) and not mcp_evidence):
        return {
            "passed": False,
            "score": 0.0,
            "issues": ["La respuesta indica que ADA no pudo completar o acceder a la tarea."],
            "rationale": "Falla explícita detectada antes de consultar al juez.",
            "source": "guard",
        }
    category = str(item.get("category") or "").lower()
    conceptual = category in {"chat", "reasoning", "architecture", "metrics", "safety", "diagnostics", "agent"}
    evidence_rule = (
        "Como este caso es conceptual y no solicita ejecutar acciones, evaluá la calidad y completitud de la explicación; "
        "no exijas evidencia de MCP."
        if conceptual
        else "Debe aportar el resultado solicitado o evidencia concreta de haber consultado la herramienta. "
        "Si explica cómo hacerlo, pide datos, dice que no tiene acceso o responde con una limitación, es FAIL."
    )
    trace_evidence = ""
    if mcp_evidence:
        trace_evidence = (
            " La traza de ejecución confirma que la herramienta MCP indicada fue ejecutada con éxito; "
            "no exijas que la respuesta textual vuelva a describir esa ejecución. Evidencia: "
            + json.dumps(mcp_evidence, ensure_ascii=False)
        )
    judge_prompt = (
        "Sos un evaluador estricto de pruebas funcionales de un agente. Evaluá si la respuesta realmente cumplió el pedido. "
        "No alcanza con que repita palabras del pedido: " + evidence_rule + trace_evidence + " "
        "Devolvé SOLO JSON válido con estas claves: passed (boolean), score (número 0 a 1), issues (lista de strings) y rationale (string).\n\n"
        f"CASO: {item.get('name')}\nPEDIDO: {item.get('prompt')}\nCRITERIOS AUXILIARES: {item.get('must_match', [])}\nRESPUESTA DE ADA: {reply}"
    )
    payload = json.dumps(
        {"model": model, "prompt": judge_prompt, "stream": False, "format": "json", "options": {"temperature": 0}}
    ).encode()
    req = urllib.request.Request(
        f"{endpoint.rstrip('/')}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            raw = json.loads(response.read().decode()).get("response", "{}")
        result = json.loads(raw) if isinstance(raw, str) else raw
        score = max(0.0, min(1.0, float(result.get("score", 0))))
        passed = bool(result.get("passed")) and score >= 0.75
        return {
            "passed": passed,
            "score": round(score, 3),
            "issues": result.get("issues") or [],
            "rationale": str(result.get("rationale") or ""),
            "source": "llm",
            "model": model,
        }
    except Exception as exc:
        return {
            "passed": False,
            "score": 0.0,
            "issues": ["No se pudo ejecutar la IA evaluadora."],
            "rationale": str(exc),
            "source": "unavailable",
            "error": str(exc),
        }
