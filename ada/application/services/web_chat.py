"""Use-case service for the HTTP chat channel.

The web adapter is intentionally limited to request validation and JSON
serialization. Session state is supplied by the adapter, while routing,
confirmation and capability execution live here with the other application services.
"""

import logging
import os
import re
from pathlib import Path
from typing import Optional

from ada.application.services.responses import text_from_result
from ada.interfaces.i18n import tr

logger = logging.getLogger("ada.web_chat")

# Colloquial path aliases -> real paths.
_PATH_ALIASES = {
    "escritorio": "~/Desktop",
    "desktop": "~/Desktop",
    "documentos": "~/Documents",
    "documents": "~/Documents",
    "descargas": "~/Downloads",
    "downloads": "~/Downloads",
    "imagenes": "~/Pictures",
    "imágenes": "~/Pictures",
    "fotos": "~/Pictures",
    "pictures": "~/Pictures",
    "musica": "~/Music",
    "música": "~/Music",
    "videos": "~/Videos",
    "inicio": "~",
    "home": "~",
    "raiz": "/",
    "raíz": "/",
}


def _resolve_path_alias(text: str) -> Optional[str]:
    """Return a real path for a known colloquial alias or explicit path."""
    clean = text.strip().lower().rstrip(".")
    if clean in _PATH_ALIASES:
        return os.path.expanduser(_PATH_ALIASES[clean])
    for alias, real in _PATH_ALIASES.items():
        if re.search(r"\b" + re.escape(alias) + r"\b", clean):
            return os.path.expanduser(real)
    if re.match(r"^[~/]", text.strip()):
        return os.path.expanduser(text.strip())
    return None


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
        self._memory = getattr(agent, "mem", None)

    @staticmethod
    def _alias_key(text):
        return re.sub(r"\s+", " ", re.sub(r"[^\wáéíóúüñ ]", " ", text.lower())).strip()

    def _dynamic_path(self, text):
        """Resolve remembered or unique folder names below ADA's configured base."""
        key = self._alias_key(text)
        if not key:
            return None
        if self._memory:
            remembered = self._memory.get_folder_alias(key)
            if remembered and Path(remembered["path"]).is_dir():
                return remembered["path"]
        base = Path(os.path.expanduser(str(self.config.get("base_dir") or "~/GoogleDrive")))
        if not base.is_dir():
            return None
        stopwords = {"las", "los", "la", "el", "de", "del", "en", "fotos", "foto", "archivos", "carpeta", "carpetas"}
        terms = [term for term in re.findall(r"[\wáéíóúüñ]+", key) if term not in stopwords and len(term) > 1]
        if not terms:
            return None
        matches = []
        try:
            for folder in base.rglob("*"):
                if folder.is_dir() and all(term in folder.name.lower() for term in terms):
                    matches.append(folder)
                    if len(matches) > 1:
                        return None
        except OSError:
            return None
        if len(matches) == 1:
            resolved = str(matches[0].resolve())
            if self._memory:
                self._memory.save_folder_alias(key, resolved)
            return resolved
        return None

    def _resolve_path(self, text):
        clean = self._alias_key(text)
        # A phrase such as “las fotos de Sofía” must be searched dynamically;
        # the generic word “fotos” must not short-circuit it to ~/Pictures.
        if clean in _PATH_ALIASES or re.match(r"^[~/]", text.strip()):
            return _resolve_path_alias(text)
        generic = {"las", "los", "la", "el", "de", "del", "en", "que", "qué", "hay", "listar", "listame", "lista", "mostrame", "mostrar", "ver", "fotos", "foto", "archivos", "archivo", "carpeta", "carpetas", *(_PATH_ALIASES.keys())}
        meaningful = [term for term in re.findall(r"[\wáéíóúüñ]+", clean) if term not in generic and len(term) > 1]
        if not meaningful or not re.search(r"\b(de|del|en|fotos?|carpetas?)\b", clean):
            return _resolve_path_alias(text)
        # A named-folder phrase must never fall back to the generic
        # "fotos -> ~/Pictures" alias: that sends the request to the wrong
        # filesystem root when the user's photos live in Google Drive.
        return self._dynamic_path(text)

    @staticmethod
    def _remember(state, user_text, reply):
        state.conversation.extend([{"role": "user", "text": user_text}, {"role": "assistant", "text": reply}])

    def _payload(self, parsed, action, text):
        payload = {key: value for key, value in parsed.items() if key not in {"action", "complexity"}}
        if action == "run_script":
            payload.setdefault("timeout", 60)
        if action == "filesystem":
            filesystem_action = parsed.get("action")
            lowered = text.lower()
            # Natural-language folder questions are unambiguous even when the
            # model/router classified them as a generic file listing.
            if re.search(r"\b(carpetas?|directorios?)\b", lowered) and re.search(
                r"\b(qué|que|hay|listar|lista|listame|listá|mostrar|mostrá|ver|cu[aá]les)\b", lowered
            ):
                filesystem_action = "list_dirs"
            if filesystem_action in {"list_dirs", "list_files"}:
                payload["action"] = filesystem_action
                payload.setdefault("recursive", True)
            elif filesystem_action == "list_photos":
                payload.update({"action": "list_files", "extensions": [".jpg", ".jpeg", ".png", ".webp"]})
            elif filesystem_action == "group_files":
                payload.update({"action": "move_files", "name": parsed.get("name") or "Agrupadas"})
            if not (payload.get("path") or payload.get("dir")):
                resolved = self._resolve_path(text)
                if resolved:
                    payload["dir"] = resolved
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
        if len(text.split()) <= 3 and re.fullmatch(
            r"(?:hola|hi|hello|buenas|buenos días|buenos dias|hey)", text, re.I
        ):
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

        # If the bot previously asked for a path, allow the next message to supply it.
        pending_path_action = getattr(state, "pending_path_action", None)
        if pending_path_action:
            resolved = self._resolve_path(text)
            if resolved:
                task = dict(pending_path_action)
                state.pending_path_action = None
                payload = dict(task.get("payload") or {})
                payload["dir"] = resolved
                payload.setdefault("path", resolved)
                task["payload"] = payload
                task["prompt"] = text
                result = self.agent.decide_and_run(task)
                output = result.get("result", result)
                if isinstance(output, dict) and output.get("error") == "confirmation_required":
                    state.pending_action = task
                    reply = tr("confirmation_required", lang)
                else:
                    reply = text_from_result(output)
                self._remember(state, text, reply)
                return {"reply": reply, "model": result.get("model", "tool"), "result": output}, 200
            state.pending_path_action = None

        parsed = self.agent.parse_prompt(text)
        # Folder/file questions with a known path must not fall through to the
        # generic chat model (which can ask for the path again).
        lowered = text.lower()
        if self._resolve_path(text) and re.search(r"\b(archivos?|ficheros?|documentos?|fotos?)\b", lowered):
            parsed = dict(parsed or {})
            parsed["action"] = "list_files"
            parsed.setdefault("complexity", 1)
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
            state.pending_path_action = {
                "type": action,
                "payload": payload,
                "prompt": text,
                "complexity": parsed.get("complexity", 3),
            }
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
