"""Small dependency-free HTTP application for ADA prompt test management."""
import json
import os
import sqlite3
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DB = os.environ.get("DB_PATH", "/data/test-manager.sqlite")
ADA_URL = os.environ.get("ADA_URL", "http://ada:8080").rstrip("/")
STATIC = Path(__file__).parent / "static"


def db():
    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.executescript("""
      CREATE TABLE IF NOT EXISTS categories(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
      CREATE TABLE IF NOT EXISTS prompts(
        id INTEGER PRIMARY KEY, category_id INTEGER NOT NULL REFERENCES categories(id),
        name TEXT NOT NULL, prompt TEXT NOT NULL, expected_tools TEXT NOT NULL DEFAULT '[]',
        expected_memories TEXT NOT NULL DEFAULT '[]', expected_context TEXT NOT NULL DEFAULT '[]',
        expected_rag INTEGER NOT NULL DEFAULT 0
      );
      CREATE TABLE IF NOT EXISTS executions(
        id INTEGER PRIMARY KEY, prompt_id INTEGER NOT NULL REFERENCES prompts(id), created_at TEXT NOT NULL,
        ada_message_id TEXT, status TEXT NOT NULL, response TEXT, model TEXT, input_tokens INTEGER,
        output_tokens INTEGER, token_usage TEXT NOT NULL DEFAULT '[]', context_selection TEXT,
        executed_tools TEXT NOT NULL DEFAULT '[]', evaluation TEXT
      );
    """)
    if connection.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0:
        category = connection.execute("INSERT INTO categories(name) VALUES (?) RETURNING id", ("Smoke tests",)).fetchone()[0]
        connection.executemany(
            "INSERT INTO prompts(category_id,name,prompt,expected_tools) VALUES (?,?,?,?)",
            [(category, "Arquitectura hexagonal", "Explicá en tres puntos qué es una arquitectura hexagonal y cómo se separan dominio, aplicación e infraestructura.", "[]"),
             (category, "Formatos de imagen", "Compará JPG, PNG y RAW para conservar fotografías. Indicá una ventaja y una desventaja de cada formato.", "[]"),
             (category, "Comida simple", "Tengo arroz, huevos y tomate. Dame dos ideas fáciles para comer ahora.", "[]")])
        connection.commit()
    return connection


def dumps(value):
    return json.dumps(value if value is not None else [], ensure_ascii=False)


def row_prompt(row):
    item = dict(row)
    for key in ("expected_tools", "expected_memories", "expected_context"):
        item[key] = json.loads(item[key])
    item["expected_rag"] = bool(item["expected_rag"])
    return item


def request_json(url, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.loads(response.read())


def run_ada(prompt):
    accepted = request_json(ADA_URL + "/api/v1/chat", {"message": prompt, "conversationId": "test-manager"})
    message_id = accepted["messageId"]
    for _ in range(180):
        status = request_json(ADA_URL + "/api/v1/chat/" + message_id + "/status")
        state = status.get("state", status.get("status"))
        if state in ("completed", "failed"):
            if state == "failed":
                raise RuntimeError(status.get("detail") or "ADA execution failed")
            return request_json(ADA_URL + "/api/v1/chat/" + message_id)
        time.sleep(1)
    raise TimeoutError("ADA execution timed out")


def evaluate(test, result):
    selected = (result.get("contextSelection") or {})
    actual_tools = result.get("executedTools", [])
    checks = {
        "response_present": bool(result.get("content", "").strip()),
        "expected_tools_executed": set(test["expected_tools"]).issubset(set(actual_tools)),
        "expected_memories_selected": set(test["expected_memories"]).issubset(set(selected.get("memories", []))),
        "expected_context_selected": set(test["expected_context"]).issubset(set(selected.get("mcps", []) + selected.get("tools", []))),
        "rag_available": not test["expected_rag"],
    }
    prompt = ("Evaluá esta ejecución de un asistente. Devolvé únicamente JSON válido con fields "
              "score (0 a 10), verdict (pass|review|fail), answer_quality, findings (array) y rationale. "
              "Considerá si responde exactamente lo pedido, si inventa datos y si respeta criterios.\n"
              + json.dumps({"test": test, "result": result, "checks": checks}, ensure_ascii=False))
    try:
        ai = run_ada(prompt)
        parsed = json.loads(ai.get("content", "{}"))
    except Exception as error:
        parsed = {"score": None, "verdict": "review", "answer_quality": "unavailable", "findings": [str(error)], "rationale": "No se pudo ejecutar el evaluador IA."}
    parsed["checks"] = checks
    parsed["token_usage"] = result.get("tokenUsage", [])
    return parsed


class Handler(BaseHTTPRequestHandler):
    def send_json(self, value, status=200):
        body = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def read_json(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))

    def do_GET(self):
        if self.path == "/health": return self.send_json({"status": "ok"})
        if self.path == "/" or self.path == "/index.html":
            body = (STATIC / "index.html").read_bytes(); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        connection = db()
        if self.path == "/api/categories": return self.send_json([dict(x) for x in connection.execute("SELECT * FROM categories ORDER BY name")])
        if self.path.startswith("/api/categories/"):
            category_id = self.path.rsplit("/", 1)[1]
            return self.send_json([row_prompt(x) for x in connection.execute("SELECT * FROM prompts WHERE category_id=? ORDER BY name", (category_id,))])
        if self.path.startswith("/api/prompts/") and self.path.endswith("/executions"):
            prompt_id = self.path.split("/")[3]
            rows = connection.execute("SELECT * FROM executions WHERE prompt_id=? ORDER BY id DESC", (prompt_id,))
            return self.send_json([dict(x) | {"token_usage": json.loads(x["token_usage"]), "context_selection": json.loads(x["context_selection"] or "null"), "executed_tools": json.loads(x["executed_tools"]), "evaluation": json.loads(x["evaluation"] or "null")} for x in rows])
        self.send_json({"error": "not_found"}, 404)

    def do_POST(self):
        connection = db(); path = self.path; payload = self.read_json()
        if path == "/api/categories":
            try:
                cur = connection.execute("INSERT INTO categories(name) VALUES (?)", (payload["name"],)); connection.commit(); return self.send_json({"id": cur.lastrowid, "name": payload["name"]}, 201)
            except sqlite3.IntegrityError as error:
                connection.rollback(); return self.send_json({"error": str(error)}, 409)
        if path == "/api/prompts":
            try:
                cur = connection.execute("INSERT INTO prompts(category_id,name,prompt,expected_tools,expected_memories,expected_context,expected_rag) VALUES (?,?,?,?,?,?,?)", (payload["category_id"], payload["name"], payload["prompt"], dumps(payload.get("expected_tools")), dumps(payload.get("expected_memories")), dumps(payload.get("expected_context")), int(payload.get("expected_rag", False)))); connection.commit(); return self.send_json({"id": cur.lastrowid}, 201)
            except sqlite3.IntegrityError as error:
                connection.rollback(); return self.send_json({"error": str(error)}, 400)
        if path.startswith("/api/prompts/") and path.endswith("/run"):
            prompt_id = path.split("/")[3]; test = row_prompt(connection.execute("SELECT * FROM prompts WHERE id=?", (prompt_id,)).fetchone())
            try:
                result = run_ada(test["prompt"]); evaluation = evaluate(test, result)
                cur = connection.execute("INSERT INTO executions(prompt_id,created_at,ada_message_id,status,response,model,input_tokens,output_tokens,token_usage,context_selection,executed_tools,evaluation) VALUES (?,datetime('now'),?,?,?,?,?,?,?,?,?,?)", (prompt_id, result.get("messageId"), "completed", result.get("content"), result.get("model"), result.get("inputTokens"), result.get("outputTokens"), dumps(result.get("tokenUsage")), json.dumps(result.get("contextSelection"), ensure_ascii=False), dumps(result.get("executedTools")), json.dumps(evaluation, ensure_ascii=False)))
                connection.commit(); return self.send_json({"id": cur.lastrowid, "result": result, "evaluation": evaluation}, 201)
            except Exception as error:
                evaluation = json.dumps({"score": 0, "verdict": "fail", "answer_quality": "execution_error", "findings": [str(error)], "rationale": "La ejecución no terminó correctamente."}, ensure_ascii=False)
                connection.execute("INSERT INTO executions(prompt_id,created_at,status,response,token_usage,executed_tools,evaluation) VALUES (?,datetime('now'),?,?,?,?,?)", (prompt_id, "failed", str(error), "[]", "[]", evaluation))
                connection.commit()
                return self.send_json({"error": str(error)}, 502)
        self.send_json({"error": "not_found"}, 404)

    def log_message(self, *_): pass


if __name__ == "__main__":
    db().close(); ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", 8088))), Handler).serve_forever()
