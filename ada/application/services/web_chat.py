"""Use-case service for the HTTP chat channel.

The web adapter is intentionally limited to request validation and JSON
serialization. Session state is supplied by the adapter, while routing,
confirmation and capability execution live here with the other application
services.
"""

import logging
import re

from ada.application.services.responses import text_from_result
from ada.interfaces.i18n import tr

logger = logging.getLogger("ada.web_chat")


class WebChatService:
    _AFFIRMATIVE = {"si", "sí", "s", "dale", "hacelo", "hazlo", "confirmo", "confirmar"}
    _ACTION_MAP = {
        "run": "run_script",
        "organize": "organize_photos",
        "group_files": "filesystem",
        "list_dirs": "filesystem",
        "list_files": "filesystem",
        "list_photos": "filesystem",
        "lightroom": "sqlite",
    }

    def __init__(self, agent, config=None):
        self.agent = agent
        self.config = config or getattr(agent, "cfg", {})

    @staticmethod
    def _remember(state, user_text, reply):
        state.conversation.extend([{"role": "user", "text": user_text}, {"role": "assistant", "text": reply}])

    def _payload(self, parsed, action, text):
        payload = {key: value for key, value in parsed.items() if key not in {"action", "complexity"}}
        if action == "run_script":
            payload.setdefault("timeout", 60)
        if action == "filesystem":
            filesystem_action = parsed.get("action")
            if filesystem_action in {"list_dirs", "list_files"}:
                payload["action"] = filesystem_action
                payload.setdefault("recursive", True)
            elif filesystem_action == "list_photos":
                payload.update({"action": "list_files", "extensions": [".jpg", ".jpeg", ".png", ".webp"]})
            elif filesystem_action == "group_files":
                payload.update({"action": "move_files", "name": parsed.get("name") or "Agrupadas"})
        if action == "sqlite":
            payload["action"] = parsed.get("lightroom_action", "status")
            payload.setdefault("db", self.config.get("lightroom_db"))
        return payload

    @staticmethod
    def _needs_path(action, payload):
        return action in {"analyze_photo", "organize_photos", "filesystem", "select_photo_batch"} and not (
            payload.get("path") or payload.get("dir") or payload.get("source")
        )

    def _task(self, parsed, text):
        routed = parsed.get("action")
        action = self._ACTION_MAP.get(routed, routed)
        payload = self._payload(parsed, action, text)
        if action == "organize_photos":
            payload.setdefault("dir", parsed.get("path"))
        if action == "analyze_photo":
            payload.setdefault("path", parsed.get("path"))
        return action, payload

    def handle(self, text, state, lang=None):
        text = str(text or "").strip()
        if not text:
            return {"error": "empty_message", "message": tr("empty_message", lang)}, 400
        if lang:
            self.agent.lang = lang
        if len(text.split()) <= 3 and re.fullmatch(r"(?:hola|hi|hello|buenas|buenos días|buenos dias|hey)", text, re.I):
            reply = tr("greeting", lang)
            self._remember(state, text, reply)
            return {"reply": reply, "model": "ADA · respuesta rápida"}, 200

        if re.search(r"\b(que|qué)\s+(podes|puedes|haces|sabes hacer|funciones tenes|funciones tienes)\b", text, re.I) or \
           re.search(r"\b(en que|en qué)\s+(me podes|me puedes|ayudas|me ayudas)\b", text, re.I) or \
           re.search(r"\b(quien|quién)\s+(sos|eres)\b", text, re.I):
            reply = (
                "Soy **ADA**, tu asistente y compañero local de inteligencia artificial.\n\n"
                "Puedo ayudarte con varias tareas:\n"
                "- 📸 **Fotos y Selección**: Analizar calidad de imágenes RAW/JPG, detectar fotos borrosas o mal expuestas y organizar lotes.\n"
                "- 🗂️ **Gestión de Archivos**: Listar, ordenar, mover o respaldar archivos en tus carpetas autorizadas de forma segura.\n"
                "- 🌐 **Búsqueda Web**: Buscar información actualizada en internet en tiempo real.\n"
                "- 🍳 **Comidas y Recetas**: Armar listas de compras, sugerir recetas con lo que tenés y organizar menús.\n"
                "- 🧠 **Razonamiento y Chat**: Responder preguntas, resumir textos, programar y resolver problemas paso a paso.\n"
                "- 🔌 **Herramientas MCP**: Ejecutar herramientas locales mediante el protocolo MCP.\n\n"
                "¿Qué te gustaría hacer hoy?"
            )
            self._remember(state, text, reply)
            return {"reply": reply, "model": "ADA · asistente"}, 200

        if state.pending_action and text.lower() in {"no", "n", "cancelar", "cancela", "cancel"}:
            state.pending_action = None
            reply = tr("cancelled", lang)
            self._remember(state, text, reply)
            return {"reply": reply, "model": "ADA · agente"}, 200
        if state.pending_action and text.lower() in self._AFFIRMATIVE:
            pending = dict(state.pending_action)
            state.pending_action = None
            pending["confirm"] = True
            result = self.agent.decide_and_run(pending)
            reply = text_from_result(result.get("result", result))
            self._remember(state, text, reply)
            return {"reply": reply, "model": result.get("model", "tool")}, 200

        parsed = self.agent.parse_prompt(text)
        action_name = parsed.get("action")
        if action_name in {None, "ask", "suggest"}:
            complexity = parsed.get("complexity")
            if complexity is None:
                complexity = self.agent.estimate_complexity(text)
            result = self.agent.decide_and_run(
                {
                    "type": None,
                    "prompt": text,
                    "complexity": complexity,
                    "use_memory": True,
                    "mode": "agent",
                }
            )
            reply = text_from_result(result.get("result", result))
            self._remember(state, text, reply)
            return {"reply": reply, "model": result.get("model") or "sin modelo"}, 200

        action, payload = self._task(parsed, text)
        if self._needs_path(action, payload):
            reply = tr("path_required", lang)
            self._remember(state, text, reply)
            return {"reply": reply, "model": "ADA · agente"}, 200
        task = {
            "type": action,
            "payload": payload,
            "prompt": text,
            "complexity": parsed.get("complexity", 3),
        }
        result = self.agent.decide_and_run(task)
        output = result.get("result", result)
        if isinstance(output, dict) and output.get("error") == "confirmation_required":
            state.pending_action = task
            reply = tr("confirmation_required", lang)
        else:
            reply = text_from_result(output)
        self._remember(state, text, reply)
        return {"reply": reply, "model": result.get("model", "tool"), "result": output}, 200
