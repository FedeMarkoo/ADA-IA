from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context, g
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.ada.application.agent import Agent
from src.ada.config import load_config
from src.ada.infrastructure.runtime.resources import hardware_profile
from src.ada.capabilities.files.filesystem import IMAGE_EXTENSIONS
from src.ada.interfaces.telegram import TelegramListener
import re
import secrets
import threading
from functools import wraps

PROJECT_ROOT = Path(__file__).resolve().parents[4]
app = Flask(__name__, static_folder=str(PROJECT_ROOT / "ui"))


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    app.logger.exception("Unhandled ADA request error")
    correlation_id = secrets.token_hex(8)
    app.logger.error("request_failed correlation_id=%s", correlation_id)
    return (
        jsonify(
            {
                "error": "internal_error",
                "message": "Error interno. Reintentá más tarde.",
                "correlation_id": correlation_id,
            }
        ),
        500,
    )


def _csrf_token():
    return request.cookies.get("ada_csrf") or secrets.token_urlsafe(32)


@app.before_request
def protect_mutating_requests():
    if request.method not in {"POST", "DELETE", "PUT", "PATCH"}:
        return None
    if request.host.split(":", 1)[0].lower() not in {"127.0.0.1", "localhost"}:
        return jsonify({"error": "invalid_host"}), 403
    origin = request.headers.get("Origin")
    if origin and not re.match(r"^https?://(127\.0\.0\.1|localhost)(:\d+)?$", origin, re.I):
        return jsonify({"error": "invalid_origin"}), 403
    if request.path.startswith("/api/"):
        if (request.content_type or "").split(";", 1)[0].lower() != "application/json":
            return jsonify({"error": "content_type_must_be_json"}), 415
        token = request.headers.get("X-ADA-Token")
        if not token or not secrets.compare_digest(token, request.cookies.get("ada_csrf", "")):
            return jsonify({"error": "csrf_token_required"}), 403
    return None


@app.after_request
def hide_provider_metadata(response):
    """Keep engine/provider details out of public conversation responses."""
    if request.path == "/api/chat" and response.is_json:
        payload = response.get_json(silent=True)
        if isinstance(payload, dict) and "model" in payload:
            payload.pop("model", None)
            response.set_data(json.dumps(payload, ensure_ascii=False))
            response.headers["Content-Type"] = "application/json; charset=utf-8"
    return response


cfg_path = PROJECT_ROOT / "config.json"
cfg = load_config(cfg_path, PROJECT_ROOT)

agent = Agent(cfg)


class PersistentConversation(list):
    """List-compatible history that survives UI and server restarts."""

    def __init__(self, memory, session="main"):
        self.memory = memory
        self.session = session
        super().__init__(memory.conversation(session=session, limit=1000))

    def extend(self, items):
        items = list(items)
        super().extend(items)
        self.memory.append_conversation(items, session=self.session)

    def clear(self):
        super().clear()
        self.memory.clear_conversation(session=self.session)


class WebSessionState:
    def __init__(self, memory, session_id):
        self.session_id = session_id
        self.conversation = PersistentConversation(memory, session=session_id)
        self.pending_action: Optional[Dict[str, Any]] = None
        self.lock = threading.RLock()


conversation = PersistentConversation(agent.mem)
pending_action: Optional[Dict[str, Any]] = None
session_states: Dict[str, WebSessionState] = {}
session_states_lock = threading.RLock()
chat_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ada-chat")


def _session_state():
    session_id = request.cookies.get("ada_session") or getattr(g, "ada_session_id", None)
    if not session_id:
        session_id = secrets.token_urlsafe(24)
        g.ada_session_id = session_id
    with session_states_lock:
        return session_states.setdefault(session_id, WebSessionState(agent.mem, session_id))


def serialize_state(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        state = _session_state()
        global conversation, pending_action
        with state.lock:
            previous_conversation = conversation
            previous_pending_action = pending_action
            conversation = state.conversation
            pending_action = state.pending_action
            try:
                return function(*args, **kwargs)
            finally:
                state.pending_action = pending_action
                conversation = previous_conversation
                pending_action = previous_pending_action

    return wrapped


def _context_prompt(text):
    recent = conversation[-30:]
    if not recent:
        return text
    history = "\n".join(f"{item['role']}: {item['text']}" for item in recent)
    return "Conversación reciente:\n" + history + "\n\nMensaje actual del usuario:\n" + text


@app.after_request
def set_session_cookie(response):
    session_id = getattr(g, "ada_session_id", None)
    if session_id and not request.cookies.get("ada_session"):
        response.set_cookie("ada_session", session_id, samesite="Strict", secure=False, httponly=True)
    return response


def _desktop_path():
    return str(Path.home() / "Desktop")


def _mentions_desktop(text):
    return bool(re.search(r"(?<![/\\\w])(?:escritorio|desktop)(?![/\\\w])", text.lower()))


def _resolve_folder(text, previous):
    if _mentions_desktop(text):
        return _desktop_path()
    return None


def _last_known_folder(previous):
    """Resolve the most specific folder ADA mentioned in the conversation."""
    return _resolve_folder("", previous)


def _resolve_photo_reference(text, previous, parsed):
    """Resolve a camera filename without ever falling back to another photo."""
    path = parsed.get("path")
    if path and Path(path).is_file():
        return {"path": path}
    name = parsed.get("photo_name")
    if not name:
        match = re.search(r"(?<!\w)_?dsc\d+(?:\.(?:nef|arw|cr2|dng|raf|orf|jpg|jpeg|png))?", text, re.I)
        name = match.group(0) if match else None
    if not name:
        return {"path": path}
    stem = Path(name).stem.lower()
    extensions = {".nef", ".arw", ".cr2", ".dng", ".raf", ".orf", ".jpg", ".jpeg", ".png"}
    roots = []
    # Reuse the folder of a previously explicit image path in this conversation.
    for match in re.finditer(r"(/[^\n\"]+?\.(?:nef|arw|cr2|dng|raf|orf|jpg|jpeg|png))", previous, re.I):
        candidate = Path(match.group(1).rstrip(".,;:!?"))
        if candidate.is_file():
            roots.append(candidate.parent)
    roots.extend([Path(cfg.get("photo_root", ""))] if cfg.get("photo_root") else [])
    candidates = []
    seen = set()
    for root in roots:
        if not root.is_dir():
            continue
        try:
            for candidate in root.rglob("*"):
                if (
                    candidate.is_file()
                    and candidate.suffix.lower() in extensions
                    and candidate.stem.lower() == stem
                    and str(candidate) not in seen
                ):
                    seen.add(str(candidate))
                    candidates.append(candidate)
        except OSError:
            continue
    # RAW wins over a rendered JPG, and files in Originales win over exports.
    unique: List[Path] = []
    for candidate in candidates:
        if any(candidate.samefile(existing) for existing in unique):
            continue
        unique.append(candidate)
    raw_candidates = [
        item for item in unique if item.suffix.lower() in {".nef", ".arw", ".cr2", ".dng", ".raf", ".orf"}
    ]
    raw_candidates.sort(key=lambda item: ("originales" not in str(item).lower(), str(item)))
    if len(raw_candidates) == 1:
        return {"path": str(raw_candidates[0])}
    if len(unique) == 1:
        return {"path": str(unique[0])}
    if unique:
        unique.sort(
            key=lambda item: (
                item.suffix.lower() not in {".nef", ".arw", ".cr2", ".dng", ".raf", ".orf"},
                "originales" not in str(item).lower(),
                str(item),
            )
        )
        return {"ambiguous": [str(item) for item in unique], "photo_name": name}
    return {"not_found": name}


def _last_photo_path(previous):
    paths = []
    for match in re.finditer(r"(/[^\n\"]+?\.(?:nef|arw|cr2|dng|raf|orf|jpg|jpeg|png))", previous, re.I):
        candidate = Path(match.group(1).rstrip(".,;:!?"))
        if candidate.is_file():
            paths.append(candidate)
    return paths[-1] if paths else None


def _resolve_contextual_photo(text, previous):
    """Resolve short follow-ups such as 'otra' using the active photo session."""
    lowered = text.strip().lower()
    if not re.search(r"\b(otra|otro|siguiente|seguí|sigue|continuá|continua)\b", lowered):
        return None
    last = _last_photo_path(previous)
    if not last or not last.parent.is_dir():
        return None
    extensions = {".nef", ".arw", ".cr2", ".dng", ".raf", ".orf"}
    reviewed = {item.lower() for item in re.findall(r"(/[^\n\"]+?\.(?:nef|arw|cr2|dng|raf|orf))", previous, re.I)}
    candidates = [
        item
        for item in sorted(last.parent.iterdir())
        if item.is_file() and item.suffix.lower() in extensions and str(item).lower() not in reviewed
    ]
    following = [item for item in candidates if item.name.lower() > last.name.lower()]
    return (following or candidates)[0] if (following or candidates) else None


def _reply(text, model="ADA · agente"):
    conversation.extend([{"role": "user", "text": text}, {"role": "assistant", "text": text}])
    return jsonify({"reply": text, "model": model})


def _photo_reply(result):
    """Turn the internal multi-agent contract into a readable photographer report."""
    technical = result.get("technical") or {}
    semantic = result.get("semantic") or {}
    review = result.get("review") or {}
    focus = technical.get("focus", {})
    exposure = technical.get("exposure", {})
    composition = technical.get("composition", {})
    noise = technical.get("noise", {})
    match = semantic.get("session_match") or {}
    selection_rating = review.get("selection_rating", "—")
    selection_score = review.get("selection_score", "—")
    selection_label = review.get("selection_label", "—")
    lines = [
        "# Análisis fotográfico",
        "",
        f"**Archivo:** `{result.get('path', 'sin identificar')}`",
        "",
        f"## Selección: {selection_rating}/5 · {selection_label} · {review.get('recommendation', 'revisar')}",
        "",
        f"**Puntaje de selección:** {selection_score}/10  ·  **Puntaje técnico:** {technical.get('overall_score', '—')}/10",
        "",
        "| Área | Puntuación | Lectura |",
        "|---|---:|---|",
        f"| Enfoque | {focus.get('score', '—')}/10 | {'Nitidez limitada; revisar foco o trepidación' if focus.get('score', 0) < 5 else 'Nitidez aceptable'} |",
        f"| Exposición | {exposure.get('score', '—')}/10 | {'Algo baja, pero potencialmente recuperable desde RAW' if exposure.get('raw_recovery_bonus') else ('Subexpuesta o con sombras densas' if exposure.get('score', 0) < 5 else 'Equilibrada')} |",
        f"| Composición técnica | {composition.get('score', '—')}/10 | {composition.get('note', 'Evaluación técnica')} |",
        f"| Ruido / ISO | {noise.get('score', '—')}/10 | {noise.get('note', 'Sin datos de ISO')} |",
        "",
    ]
    if semantic.get("subject"):
        lines += ["## Lectura de la escena", "", f"**Sujeto y contexto:** {semantic['subject']}", ""]
    if semantic.get("style"):
        lines += [f"**Estilo:** {semantic['style']}", ""]
    if semantic.get("photographer_feedback"):
        lines += ["## Devolución como fotógrafo", "", semantic["photographer_feedback"], ""]
    if match:
        confidence = match.get("confidence")
        if isinstance(confidence, (int, float)):
            confidence_text = f"{round(float(confidence) * 100 if confidence <= 1 else float(confidence))}%"
        else:
            confidence_text = str(confidence or "—")
        lines += [f"**Coincidencia con la sesión:** {confidence_text}", str(match.get("reason", "")), ""]
    if review.get("strengths"):
        lines += ["**Puntos fuertes**", ""] + [f"- {item}" for item in review["strengths"]] + [""]
    if review.get("issues"):
        lines += ["**A revisar**", ""] + [f"- {item}" for item in review["issues"]] + [""]
    lines += ["_Analizado por ADA con el workflow multiagente._"]
    return "\n".join(lines)


@app.route("/")
def index():
    response = send_from_directory(str(PROJECT_ROOT / "ui"), "index.html")
    response.set_cookie("ada_csrf", _csrf_token(), samesite="Strict", secure=False)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


@app.route("/api/status")
def status():
    """Return active engines, local runtime health, and agent registry."""
    return jsonify(
        {
            "engines": agent.model_manager.available(),
            "runtime": agent.model_manager.runtime_status(),
            "agents": list(agent.coordinator.available_agents()),
            "hardware": hardware_profile(),
            "models": agent.model_manager.model_catalog(),
        }
    )


@app.route("/api/audit")
def audit_api():
    limit = min(200, max(1, request.args.get("limit", default=50, type=int)))
    entries = agent.mem.recent_audit(limit)
    return jsonify({"entries": entries, "count": len(entries)})


@app.route("/api/warmup", methods=["POST"])
def warmup():
    return jsonify({"runtime": agent.model_manager.runtime_status(), "ok": True})


@app.route("/api/conversation", methods=["GET", "DELETE"])
def conversation_api():
    state = _session_state()
    with state.lock:
        if request.method == "DELETE":
            state.conversation.clear()
            state.pending_action = None
            return jsonify({"ok": True, "messages": []})
        return jsonify({"messages": list(state.conversation), "count": len(state.conversation)})


@app.route("/api/chat", methods=["POST"])
@serialize_state
def chat():
    global pending_action
    data = request.get_json() or {}
    text = data.get("message", "")
    lang = data.get("lang")
    if lang:
        agent.lang = lang
    if not text:
        return jsonify({"error": "empty message"}), 400
    # simple heuristic: short greetings get a canned reply (avoid calling LLM)
    if (
        isinstance(text, str)
        and len(text.strip().split()) <= 3
        and re.match(r"^(hola|hi|hello|buenas|buenos d[ií]as|hey)$", text.strip(), flags=re.I)
    ):
        canned = (
            "Hola, ¿en qué puedo ayudarte?"
            if lang and lang.startswith("es")
            else ("Hello, how can I help you?" if lang and lang.startswith("en") else "Hola, ¿en qué puedo ayudarte?")
        )
        conversation.extend([{"role": "user", "text": text}, {"role": "assistant", "text": canned}])
        return jsonify({"reply": canned, "model": "ADA · respuesta rápida"})

    lowered = text.strip().lower()
    if lowered in {"que podes hacer?", "qué podés hacer?", "que puedes hacer?", "qué puedes hacer?"}:
        reply = (
            "Soy ADA, un agente local. Puedo consultar la base de fotos, mostrar cómo están organizadas, "
            "analizar RAW/XMP, preparar planes y ordenar fotos; también puedo listar, buscar y mover archivos, "
            "ejecutar scripts con confirmación y aprender procedimientos que me enseñes. "
            "Cuando una operación modifica archivos, primero te muestro el plan y pido confirmación."
        )
        conversation.extend([{"role": "user", "text": text}, {"role": "assistant", "text": reply}])
        return jsonify({"reply": reply, "model": "ADA · agente"})
    if any(phrase in lowered for phrase in ("sos agente", "quiero que lo hagas vos", "la idea es que lo hagas vos")):
        reply = (
            "Sí. Estoy configurada para trabajar como agente: consulto la información disponible, uso las skills "
            "y ejecuto las tareas dentro de ADA. Para acciones que mueven, borran o modifican archivos, te muestro "
            "primero un plan y solicito confirmación antes de ejecutarlas."
        )
        conversation.extend([{"role": "user", "text": text}, {"role": "assistant", "text": reply}])
        return jsonify({"reply": reply, "model": "ADA · agente"})

    parsed: Dict[str, Any] = agent.parse_prompt(text)
    if parsed.get("action") in {"food", "ask"}:
        app.logger.info(
            "ADA intent action=%s food_action=%s confidence=%s",
            parsed.get("action"),
            parsed.get("food_action"),
            parsed.get("confidence"),
        )
    if parsed.get("action") == "food":
        if parsed.get("needs_clarification"):
            reply = parsed.get("clarifying_question", "Necesito un dato más para ayudarte.")
            conversation.extend([{"role": "user", "text": text}, {"role": "assistant", "text": reply}])
            return jsonify({"reply": reply, "model": "food-router"})
        if parsed.get("advisor") or parsed.get("food_action") in {"suggest", "advise"}:
            advice = agent.advise_food(text)
            if advice:
                conversation.extend([{"role": "user", "text": text}, {"role": "assistant", "text": str(advice)}])
                return jsonify({"reply": str(advice), "model": "food-advisor"})
            # Ollama may be unavailable or time out. Use the local recipe
            # catalog as a useful fallback; never query the shopping domain
            # for recipe suggestions.
            fallback_result = agent.decide_and_run(
                {
                    "type": "food",
                    "payload": {
                        "domain": "recipes",
                        "food_action": "list",
                        "config": cfg,
                    },
                    "complexity": 2,
                }
            )
            recipes = (fallback_result.get("result") or {}).get("recipes", [])
            reply = "No pude consultar al asesor ahora. De tu recetario, probaría con:\n" + (
                "\n".join(f"- {item['name']}" for item in recipes[:3]) if recipes else "No hay recetas cargadas."
            )
            conversation.extend([{"role": "user", "text": text}, {"role": "assistant", "text": reply}])
            return jsonify({"reply": reply, "model": "food-catalog-fallback"})
        payload = {key: value for key, value in parsed.items() if key not in {"action", "complexity"}}
        result = agent.decide_and_run({"type": "food", "payload": payload, "complexity": parsed.get("complexity", 2)})
        out = result.get("result", {})
        food_action = parsed.get("food_action")
        if out.get("error") == "item_not_found":
            reply = f"No encontré “{out.get('item', '')}” en la lista."
        elif out.get("error") == "recipe_not_found":
            reply = f"No encontré esa receta: {parsed.get('name', '')}."
        elif parsed.get("domain") == "shopping" and food_action == "list":
            items = out.get("items", [])
            reply = "🛒 Lista de compras:\n" + (
                "\n".join(f"- {i.get('quantity') + ' ' if i.get('quantity') else ''}{i['item']}" for i in items)
                if items
                else "Está vacía."
            )
        elif parsed.get("domain") == "shopping" and food_action == "add":
            reply = f"Agregué {parsed.get('item')} a la lista de compras."
        elif food_action == "check":
            reply = f"Marqué {parsed.get('item')} como comprado."
        elif food_action == "remove":
            reply = f"Saqué {parsed.get('item')} de la lista."
        elif food_action == "recipe_to_shopping":
            reply = f"Agregué {out.get('added', 0)} ingredientes de {out.get('name', parsed.get('name'))} a la lista."
        elif food_action == "save":
            reply = f"Guardé la receta “{out.get('name', parsed.get('name'))}” con {len(out.get('ingredients', []))} ingredientes."
        elif food_action in {"suggest", "list"}:
            recipes = out.get("recipes", [])
            reply = ("🍲 Recetas sugeridas:\n" if food_action == "suggest" else "📖 Recetas guardadas:\n") + (
                "\n".join(f"- {r['name']}" for r in recipes[:5]) if recipes else "Todavía no tengo recetas guardadas."
            )
        else:
            reply = json.dumps(out, ensure_ascii=False, indent=2)
        conversation.extend([{"role": "user", "text": text}, {"role": "assistant", "text": reply}])
        return jsonify({"reply": reply, "model": result.get("model", "food")})
    previous_text = " ".join(item["text"] for item in conversation[-4:])
    previous = previous_text.lower()
    contextual_photo = _resolve_contextual_photo(text, previous_text)
    if contextual_photo and parsed.get("action") in {"ask", "suggest"}:
        parsed = {
            "action": "analyze_photo",
            "path": str(contextual_photo),
            "photo_name": contextual_photo.name,
            "complexity": 5,
        }
    if pending_action and pending_action.get("type") == "photo_choice":
        extension = text.strip().lower().lstrip(".")
        candidates = pending_action.get("candidates", [])
        selected = [item for item in candidates if Path(item).suffix.lower().lstrip(".") == extension]
        if len(selected) == 1:
            parsed = {
                "action": "analyze_photo",
                "path": selected[0],
                "photo_name": Path(selected[0]).name,
                "complexity": 5,
            }
            pending_action = None
        elif len(selected) > 1:
            reply = (
                "Hay varias versiones ."
                + extension
                + " para ese archivo:\n\n"
                + "\n".join(f"- {item}" for item in selected)
                + "\n\nIndicame la ruta exacta."
            )
            conversation.extend([{"role": "user", "text": text}, {"role": "assistant", "text": reply}])
            return jsonify({"reply": reply, "model": "ADA · agente"})
    affirmative = text.strip().lower() in {"si", "sí", "s", "dale", "hacelo", "hazlo", "confirmo", "confirmar"}
    if pending_action and affirmative:
        action = pending_action
        pending_action = None
        result = agent.decide_and_run({**action, "confirm": True})
        out = result.get("result", {})
        reply = json.dumps(out, ensure_ascii=False, indent=2) if isinstance(out, dict) else str(out)
        conversation.extend([{"role": "user", "text": text}, {"role": "assistant", "text": reply}])
        return jsonify({"reply": reply, "model": result.get("model", "tool")})
    if parsed.get("action") == "lightroom":
        lr_action = parsed.get("lightroom_action", "plan")
        root = parsed.get("path") or cfg.get("photo_root") or os.path.expanduser("~/Desktop/Fotos")
        if lr_action in {"status", "structure", "report"}:
            result = agent.decide_and_run(
                {
                    "type": "sqlite",
                    "payload": {"action": lr_action, "db": cfg.get("lightroom_db")},
                    "complexity": 2,
                }
            )
            out = result.get("result", {})
            if isinstance(out, dict) and out.get("action") == "status" and out.get("ok"):
                s = out["summary"]
                reply = (
                    f"Estado de la biblioteca (SQLite):\n\n"
                    f"- Carpetas: {s['carpetas']}\n- Fotos RAW registradas: {s['total']}\n"
                    f"- Buenas: {s['buenas']}\n- Rechazadas: {s['rechazadas']}\n"
                    f"- Eliminadas: {s['eliminadas']}\n- Movidas: {s['movidas']}\n\n"
                    "Estados:\n"
                    + "\n".join(f"- {item['estado']}: {item['cantidad']}" for item in out["estados"])
                    + "\n\nFormatos:\n"
                    + "\n".join(f"- {item['formato']}: {item['colecciones']} colecciones" for item in out["formatos"])
                )
            elif isinstance(out, dict) and out.get("action") == "structure" and out.get("ok"):
                groups: Dict[str, List[Dict[str, Any]]] = {}
                for item in out["collections"]:
                    groups.setdefault(item["formato"] or "Sin formato", []).append(item)
                lines = [f"Estructura registrada en SQLite ({out['count']} colecciones):"]
                for formato, items in groups.items():
                    lines.append(f"\n{formato} ({len(items)}):")
                    for item in items:
                        date = f"{item['fecha']} - " if item["fecha"] else ""
                        context = f"{item['contexto']}/" if item["contexto"] else ""
                        lines.append(f"- {context}{date}{item['contenido']}\n  {item['ruta']}")
                reply = "\n".join(lines)
            elif isinstance(out, dict) and out.get("action") == "report" and out.get("ok"):
                s = out["summary"]
                lines = [
                    "Reporte real de la biblioteca (SQLite):",
                    f"- Carpetas: {s['carpetas']}",
                    f"- RAW registrados: {s['total']}",
                    f"- Buenas: {s['buenas']}",
                    f"- Rechazadas: {s['rechazadas']}",
                    f"- Eliminadas: {s['eliminadas']}",
                    f"- Movidas: {s['movidas']}",
                    "",
                    f"- JPG registrados: {s.get('jpg', 0)} ({s.get('jpg_asociados', 0)} asociados)",
                    f"- Videos: {s.get('videos', 0)} · Editables: {s.get('editables', 0)} · Otros: {s.get('otros', 0)}",
                    "",
                    "Resumen por formato:",
                ]
                for item in out["formatos"]:
                    label = (
                        f"{item['colecciones']} colecciones"
                        if item["colecciones"]
                        else f"{item['carpetas']} carpeta sin colección"
                    )
                    lines.append(
                        f"- {item['formato']}: {label}, "
                        f"{item['total']} RAW, {item.get('jpg', 0)} JPG "
                        f"({item['buenas']} buenas, {item['rechazadas']} rechazadas)"
                    )
                lines.append("\nDetalle completo por carpeta:")
                for item in out["collections"]:
                    date = f"{item['fecha']} - " if item["fecha"] else ""
                    context = f"{item['contexto']}/" if item["contexto"] else ""
                    lines.append(
                        f"- [{item['formato']}] {context}{date}{item['contenido']}: "
                        f"{item['total']} RAW ({item['buenas']} buenas, {item['rechazadas']} rechazadas)\n  {item['ruta']}"
                    )
                reply = "\n".join(lines)
            else:
                reply = json.dumps(out, ensure_ascii=False, indent=2)
            conversation.extend([{"role": "user", "text": text}, {"role": "assistant", "text": reply}])
            return jsonify({"reply": reply, "model": result.get("model", "tool: sqlite")})
        payload = {
            "action": lr_action,
            "root": root,
            "script": cfg.get("lightroom_script"),
            "db": cfg.get("lightroom_db"),
        }
        if lr_action in {"organize", "organizar", "mover", "limpiar", "recuperar"}:
            pending_action = {"type": "lightroom", "payload": payload, "complexity": 7}
            reply = f"Preparé una operación Lightroom sobre {root}. Primero conviene revisar el plan simulado. ¿Querés que lo ejecute después de confirmar?"
            conversation.extend([{"role": "user", "text": text}, {"role": "assistant", "text": reply}])
            return jsonify({"reply": reply, "model": "ADA · agente"})
        result = agent.decide_and_run({"type": "lightroom", "payload": payload, "complexity": 6})
        out = result.get("result", {})
        if isinstance(out, dict) and out.get("action") == "status" and out.get("ok"):
            s = out["summary"]
            reply = (
                f"Estado de la biblioteca:\n\n"
                f"- Carpetas: {s['carpetas']}\n- Fotos RAW registradas: {s['total']}\n"
                f"- Buenas: {s['buenas']}\n- Rechazadas: {s['rechazadas']}\n"
                f"- Eliminadas: {s['eliminadas']}\n- Movidas: {s['movidas']}\n\n"
                "Estados:\n"
                + "\n".join(f"- {item['estado']}: {item['cantidad']}" for item in out["estados"])
                + "\n\nFormatos:\n"
                + "\n".join(f"- {item['formato']}: {item['colecciones']} colecciones" for item in out["formatos"])
            )
        elif isinstance(out, dict) and out.get("action") == "structure" and out.get("ok"):
            groups = {}
            for item in out["collections"]:
                groups.setdefault(item["formato"] or "Sin formato", []).append(item)
            lines = [f"Estructura registrada en la base ({out['count']} colecciones):"]
            for formato, items in groups.items():
                lines.append(f"\n{formato} ({len(items)}):")
                for item in items:
                    date = f"{item['fecha']} - " if item["fecha"] else ""
                    context = f"{item['contexto']}/" if item["contexto"] else ""
                    lines.append(f"- {context}{date}{item['contenido']}\n  {item['ruta']}")
            reply = "\n".join(lines)
        else:
            reply = out.get("stdout", "") if isinstance(out, dict) else str(out)
        if isinstance(out, dict) and out.get("stderr"):
            reply += "\n\nErrores/avisos:\n" + out["stderr"]
        conversation.extend([{"role": "user", "text": text}, {"role": "assistant", "text": reply}])
        return jsonify(
            {"reply": reply or json.dumps(out, ensure_ascii=False, indent=2), "model": result.get("model", "tool")}
        )
    if (
        pending_action
        and pending_action.get("type") == "filesystem"
        and pending_action.get("payload", {}).get("action") in {"list_dirs", "list_files"}
        and (_mentions_desktop(text) or "test" in text.lower())
    ):
        parsed = {"action": pending_action["payload"]["action"], "complexity": 2}
        pending_action = None
    if _mentions_desktop(text) and "fotos" in previous:
        parsed = {"action": "list_photos", "complexity": 2}
    elif (
        _mentions_desktop(text)
        and ("carpet" in previous or "directori" in previous)
        and any(w in previous for w in ("list", "mostrar", "ver"))
    ):
        parsed = {"action": "list_dirs", "complexity": 2}
    if parsed.get("action") == "analyze_photo":
        resolved = _resolve_photo_reference(text, previous_text, parsed)
        if resolved.get("ambiguous"):
            pending_action = {
                "type": "photo_choice",
                "photo_name": resolved["photo_name"],
                "candidates": resolved["ambiguous"],
            }
            reply = (
                "Encontré varias versiones de "
                + resolved["photo_name"]
                + ":\n\n"
                + "\n".join(f"- {item}" for item in resolved["ambiguous"])
                + "\n\nIndicame cuál querés analizar."
            )
            conversation.extend([{"role": "user", "text": text}, {"role": "assistant", "text": reply}])
            return jsonify({"reply": reply, "model": "ADA · agente"})
        if resolved.get("not_found"):
            reply = f"No encontré una foto llamada {resolved['not_found']} en la carpeta de la sesión. No analicé ninguna otra foto."
            conversation.extend([{"role": "user", "text": text}, {"role": "assistant", "text": reply}])
            return jsonify({"reply": reply, "model": "ADA · agente"})
        path = resolved.get("path")
        if not path:
            reply = "Necesito la ruta de la imagen. Por ejemplo: “analizá la foto /ruta/imagen.jpg”."
            conversation.extend([{"role": "user", "text": text}, {"role": "assistant", "text": reply}])
            return jsonify({"reply": reply, "model": "ADA · agente"})
        result = agent.decide_and_run({"type": "analyze_photo", "payload": {"path": path}, "complexity": 5})
        out = result.get("result", {})
        reply = _photo_reply(out)
        conversation.extend([{"role": "user", "text": text}, {"role": "assistant", "text": reply}])
        return jsonify({"reply": reply, "model": result.get("model", "tool: analyze_photo")})
    if parsed.get("action") in {"list_dirs", "list_files"}:
        folder = parsed.get("path") or _resolve_folder(text, previous)
        if not folder:
            reply = "¿En qué carpeta querés buscar? Podés decirme “las de test” o “el escritorio”."
            pending_action = {"type": "filesystem", "payload": {"action": parsed["action"]}, "complexity": 2}
            conversation.extend([{"role": "user", "text": text}, {"role": "assistant", "text": reply}])
            return jsonify({"reply": reply, "model": "ADA · agente"})
        result = agent.decide_and_run(
            {
                "type": "filesystem",
                "payload": {"action": parsed["action"], "dir": folder, "recursive": True},
                "complexity": 2,
            }
        )
        out = result.get("result", {})
        key = "dirs" if parsed["action"] == "list_dirs" else "files"
        reply = (
            (f"Encontré {out.get('count', 0)} elementos en {out.get('dir', folder)}.\n\n" + "\n".join(out.get(key, [])))
            if isinstance(out, dict) and out.get("ok")
            else json.dumps(out, ensure_ascii=False, indent=2)
        )
        conversation.extend([{"role": "user", "text": text}, {"role": "assistant", "text": reply}])
        return jsonify({"reply": reply, "model": result.get("model", "tool")})
    group_words = (
        "nombre",
        "llamala",
        "llamalo",
        "agrup",
        "carpeta nueva",
        "movelas",
        "moverlas",
        "mover todos",
        "todas las fotos",
        "la segunda",
    )
    if parsed.get("action") == "group_files" or (pending_action and any(w in text.lower() for w in group_words)):
        source = (pending_action or {}).get("payload", {}).get("source") if pending_action else None
        source = source or _last_known_folder(previous) or _resolve_folder(text, previous)
        if not source:
            reply = "¿De qué carpeta querés agrupar los archivos?"
        else:
            match = re.search(r"(?:nombre|llam(?:ar|ala|alo)?)\s+(?:a\s+)?[\"“]?([\w.-]+)", text, re.I)
            name = match.group(1) if match else None
            if not name and any(w in text.lower() for w in ("agrupad", "grouped")):
                name = "grouped" if "grouped" in text.lower() else "Agrupadas"
            if not name and "la segunda" in text.lower():
                name = "Agrupadas"
            if pending_action and name:
                pending_action["payload"]["name"] = name
            if not name and pending_action:
                name = pending_action["payload"].get("name")
            if not name:
                pending_action = {
                    "type": "filesystem",
                    "payload": {"action": "move_files", "source": source},
                    "complexity": 4,
                }
                reply = f"Voy a agrupar los archivos de {source}. ¿Qué nombre querés ponerle a la carpeta nueva?"
            else:
                pending_action = {
                    "type": "filesystem",
                    "payload": {"action": "move_files", "source": source, "name": name},
                    "complexity": 4,
                }
                reply = f"Voy a mover los archivos de {source} a {source.rsplit('/', 1)[0]}/{name}. ¿Confirmás?"
        conversation.extend([{"role": "user", "text": text}, {"role": "assistant", "text": reply}])
        return jsonify({"reply": reply, "model": "ADA · agente"})
    if parsed.get("action") == "select_photo_batch":
        folder = parsed.get("path") or _last_known_folder(previous_text) or _resolve_folder(text, previous_text)
        if not folder:
            reply = "¿En qué carpeta querés hacer la selección? Indicame la ruta del evento."
            model = "ADA · agente"
        else:
            result = agent.decide_and_run(
                {
                    "type": "select_photo_batch",
                    "payload": {
                        "path": folder,
                        "write_xmp": parsed.get("write_xmp", False),
                        "repair_xmp": parsed.get("repair_xmp", False),
                        "mark_bursts": parsed.get("mark_bursts", False),
                        "batch_accept_threshold": cfg.get("batch_accept_threshold", 5.6),
                        # Large batches stay deterministic and fast. Vision remains
                        # enabled for individual reviews and can be explicitly opted
                        # into for a smaller batch through the internal action.
                        "vision": bool(parsed.get("vision", False)),
                    },
                    "complexity": 6,
                }
            )
            out = result.get("result", {})
            model = result.get("model", "tool: select_photo_batch")
            if out.get("ok") and out.get("workflow") == "photo_xmp_repair":
                reply = (
                    f"Actualicé {len(out.get('xmp_written', []))} XMP sin volver a analizar las fotos. "
                    f"Ráfagas marcadas en amarillo: {out.get('burst_count', 0)} archivos."
                )
            elif out.get("ok"):
                reply = (
                    f"Selección preliminar terminada sobre {out['scanned']} fotos.\n\n"
                    f"- Seleccionadas: {out.get('selected_count', 0)}\n"
                    f"- Rechazadas: {out.get('rejected_count', 0)}\n"
                    f"- XMP escritos: {len(out.get('xmp_written', []))}\n\n"
                    "Cada foto fue evaluada con el mismo workflow multiagente que un análisis individual."
                )
            else:
                reply = json.dumps(out, ensure_ascii=False, indent=2)
        conversation.extend([{"role": "user", "text": text}, {"role": "assistant", "text": reply}])
        return jsonify({"reply": reply, "model": model})
    if parsed.get("action") == "list_photos":
        folder = parsed.get("path")
        if not folder and (_mentions_desktop(text) or ("fotos" in previous and "carpeta" in previous)):
            folder = _desktop_path()
        if not folder:
            reply = "¿En qué carpeta querés que liste las fotos? Podés decirme, por ejemplo, “escritorio”."
            conversation.extend([{"role": "user", "text": text}, {"role": "assistant", "text": reply}])
            return jsonify({"reply": reply, "model": "ADA · agente"})
        result = agent.decide_and_run(
            {
                "type": "filesystem",
                "payload": {"action": "list_files", "dir": folder, "extensions": list(IMAGE_EXTENSIONS)},
                "complexity": 2,
            }
        )
        out = result.get("result", {})
        if isinstance(out, dict) and out.get("ok"):
            photos = out.get("files", out.get("photos", []))
            reply = f"Encontré {out['count']} fotos en {out['dir']}.\n\n" + (
                "\n".join(photos) if photos else "No encontré imágenes."
            )
        else:
            reply = json.dumps(out, ensure_ascii=False, indent=2)
        conversation.extend([{"role": "user", "text": text}, {"role": "assistant", "text": reply}])
        return jsonify({"reply": reply, "model": result.get("model", "tool")})

    # by default avoid injecting RAG context for UI chat messages unless caller requests it
    task = {
        "type": None,
        "prompt": _context_prompt(text),
        "complexity": agent.estimate_complexity(text),
        "use_memory": True,
        "mode": "agent",
    }
    res = agent.decide_and_run(task)
    response_model: Optional[str] = (
        res.get("model") if isinstance(res, dict) and isinstance(res.get("model"), str) else None
    )
    # Normalize output
    out = res.get("result") if isinstance(res, dict) else res
    if isinstance(out, dict):
        # try to get text in common fields
        out_text = out.get("text") or out.get("result") or str(out)
    else:
        out_text = str(out)

    # sanitize output: remove persona statements (age/gender) and trim auto-inserted language blocks
    # remove explicit age/gender roleplay lines
    out_text = re.sub(r"I(?:'m| am) a \d{1,3}[- ]?year[- ]?old [a-zA-Z]+[\.,]?", "", out_text, flags=re.I)
    out_text = re.sub(r"My name is [A-Za-z ]{1,30}\.?", "", out_text)
    # remove common auto-questions and assistant self-introductions
    out_text = re.sub(r"What is your name\??", "", out_text, flags=re.I)
    out_text = re.sub(r"What is your purpose\??", "", out_text, flags=re.I)
    out_text = re.sub(r"ADA:.*?", "", out_text, flags=re.I)
    out_text = re.sub(r"user prompt:.*", "", out_text, flags=re.I | re.S)
    # remove leading 'English:' / 'Spanish:' blocks if lang specified
    if lang == "es":
        # keep Spanish block after 'Spanish:' or 'Spanish' marker
        m = re.search(r"Spanish:\s*(.*?)$", out_text, flags=re.I | re.S)
        if m:
            out_text = m.group(1).strip()
        else:
            # remove any English: ... Spanish: markers and keep whole text
            out_text = re.sub(r"English:.*?Spanish:\s*", "", out_text, flags=re.I | re.S)
    elif lang == "en":
        m = re.search(r"English:\s*(.*?)($|Spanish:)", out_text, flags=re.I | re.S)
        if m:
            out_text = m.group(1).strip()
        else:
            out_text = re.sub(r"Spanish:.*?English:\s*", "", out_text, flags=re.I | re.S)
    # strip repeated whitespace and odd characters
    out_text = out_text.strip()

    # detect roleplay/storytelling outputs and retry with stricter instruction
    roleplay_patterns = [
        r"Your Character",
        r"The Environment",
        r"What do you want to do",
        r"I'll describe",
        r"you are a skilled",
        r"adventurer",
        r"text-based adventure",
    ]
    try:
        if any(re.search(pat, out_text, flags=re.I) for pat in roleplay_patterns):
            # retry once with a stronger non-roleplay instruction
            retry_task = {
                "type": None,
                "prompt": f"Respuesta breve en {lang if lang!='auto' else 'español'} al mensaje: {text}. No roleplay. Contesta sólo un saludo y pregunta cómo puedo ayudar.",
                "complexity": 1,
                "use_memory": False,
            }
            retry_res = agent.decide_and_run(retry_task)
            response_model = (
                retry_res.get("model")
                if isinstance(retry_res, dict) and isinstance(retry_res.get("model"), str)
                else response_model
            )
            out = retry_res.get("result") if isinstance(retry_res, dict) else retry_res
            out_text = out if isinstance(out, str) else str(out)
            out_text = re.sub(r"I(?:'m| am) a \d{1,3}[- ]?year[- ]?old [a-zA-Z]+[\.,]?", "", out_text, flags=re.I)
            out_text = re.sub(r"My name is [A-Za-z ]{1,30}\.?", "", out_text)
            out_text = out_text.strip()
    except Exception:
        pass
    conversation.extend([{"role": "user", "text": text}, {"role": "assistant", "text": out_text}])
    return jsonify({"reply": out_text, "model": response_model or "sin modelo"})


def _sse(event, payload):
    """Encode one chat progress event for the web client."""
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _run_chat_in_worker(data, session_id):
    """Run the existing JSON chat action in an isolated request context."""
    with app.test_request_context(
        "/api/chat", method="POST", json=data, headers={"Cookie": f"ada_session={session_id}"}
    ):
        response = chat()
        return response.get_json(silent=True) or {}


@app.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    """Answer through SSE so the UI can show ADA's progress incrementally.

    The existing JSON endpoint remains available for Telegram and integrations.
    This endpoint deliberately reuses the same chat action, so web and Telegram
    cannot drift into different agent behavior.
    """
    data = request.get_json() or {}
    text = data.get("message", "")
    if not text:
        return jsonify({"error": "empty message"}), 400
    state = _session_state()

    @stream_with_context
    def events():
        received = "Recibí tu pedido. Estoy entendiendo qué tarea corresponde."
        state.conversation.extend([{"role": "assistant", "text": received, "kind": "status"}])
        yield _sse("status", {"text": received})

        processing = (
            "Estoy procesando la información y preparando la respuesta. Las tareas largas continúan en segundo plano."
        )
        state.conversation.extend([{"role": "assistant", "text": processing, "kind": "status"}])
        yield _sse("status", {"text": processing})
        future = chat_executor.submit(_run_chat_in_worker, data, state.session_id)
        try:
            last_update = time.monotonic()
            while not future.done():
                if time.monotonic() - last_update >= 5:
                    update = "La tarea sigue en ejecución. ADA continúa trabajando y guardará los resultados progresivamente."
                    state.conversation.extend([{"role": "assistant", "text": update, "kind": "status"}])
                    yield _sse("status", {"text": update})
                    last_update = time.monotonic()
                time.sleep(0.25)
            payload = future.result()
            if payload.get("error"):
                yield _sse("error", {"text": payload.get("message") or payload["error"]})
            else:
                yield _sse("reply", {"text": payload.get("reply", "(sin respuesta)")})
        except Exception as error:
            app.logger.exception("Streaming chat failed")
            failure = f"La tarea terminó con un error: {error}"
            state.conversation.extend([{"role": "assistant", "text": failure, "kind": "error"}])
            yield _sse("error", {"text": failure})
        yield _sse("done", {"ok": True})

    response_stream = events()  # type: ignore[call-arg]
    return Response(
        response_stream,
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def main():
    port = int(os.environ.get("ADA_UI_PORT", "5005"))
    telegram = TelegramListener(cfg, base_url=f"http://127.0.0.1:{port}")
    telegram.start()
    app.run(host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
