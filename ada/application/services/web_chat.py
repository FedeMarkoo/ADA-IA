"""Use-case service for the HTTP chat channel.

The web adapter is intentionally limited to request validation and JSON
serialization. Session state is supplied by the adapter, while routing,
confirmation and capability execution live here with the other application services.
"""

import logging
import os
import re
import platform
import shutil
from pathlib import Path
from typing import Optional

from ada.application.services.responses import text_from_result
from ada.interfaces.i18n import tr
from ada.application.services.folder_resolver import FolderResolver

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

    def __init__(self, agent, config=None, mcp_manager=None):
        self.agent = agent
        self.config = config or getattr(agent, "cfg", {})
        self._memory = getattr(agent, "mem", None)
        self.folder_resolver = FolderResolver(self.config, self._memory)
        self.mcp_manager = mcp_manager or getattr(agent, "mcp_manager", None)

    def _capability_summary(self):
        """Build a user-facing capability list from the live MCP registry."""
        if not self.mcp_manager:
            return "No tengo un inventario MCP disponible en este momento."
        servers = self.mcp_manager.list_servers()
        tools = self.mcp_manager.list_tools()
        active = {s["name"] for s in servers if s.get("status") == "active"}
        grouped = {}
        for tool in tools:
            if tool.get("enabled") and tool.get("server") in active:
                grouped.setdefault(tool.get("server"), []).append(tool)
        lines = ["Soy ADA, un agente local. Estas son mis herramientas activas ahora:"]
        for server, server_tools in sorted(grouped.items()):
            lines.append(f"\n**{server}**")
            for tool in sorted(server_tools, key=lambda item: item.get("name", "")):
                confirmation = " (requiere confirmación)" if tool.get("requires_confirmation") else ""
                lines.append(f"- `{tool.get('name')}`: {tool.get('description', 'sin descripción')}{confirmation}")
        if not grouped:
            lines.append("\nNo hay herramientas MCP activas.")
        return "\n".join(lines)

    @staticmethod
    def _emit(progress, phase, **details):
        if progress:
            progress(phase, details)

    @staticmethod
    def _filesystem_intent(text):
        """Classify safe read-only filesystem questions without an LLM."""
        lowered = text.lower()
        location_words = (
            r"\b(ruta|ubicaci[oó]n|d[oó]nde\s+(?:est[aá]|est[aá]n|tengo|guard[eé])|"
            r"en\s+qu[eé]\s+carpeta|busc[aá]?(?:me)?\s+(?:la\s+)?carpeta|"
            r"no\s+me\s+acuerdo\s+(?:de\s+)?(?:la\s+)?carpeta)\b"
        )
        if re.search(location_words, lowered) and re.search(
            r"\b(carpetas?|directorios?|archivos?|documentos?|fotos?|im[aá]genes?)\b", lowered
        ):
            return "resolve_path"
        read_words = r"(?:qu[eé]|cu[aá]l(?:es)?|cu[aá]nt[oa]s?|cantidad|hay|tiene|tienen|listar|lista|listame|listá|mostrar|mostrá|ver|adentro|dentro|contenido)"
        if re.search(r"\b(carpetas?|directorios?)\b", lowered) and re.search(rf"\b{read_words}\b", lowered):
            return "list_dirs"
        if re.search(r"\b(archivos?|ficheros?|documentos?|fotos?|im[aá]genes?)\b", lowered) and re.search(
            rf"\b{read_words}\b|\bruta\b", lowered
        ):
            return "list_files"
        return None

    @staticmethod
    def _food_advice_intent(text):
        """Catch read-only cooking advice before the slower model router.

        These phrases are intentionally about recommendations, never about
        mutating shopping/inventory data.  Mutation requests continue through
        the validated router and policy layer.
        """
        lowered = text.lower()
        advice_patterns = (
            r"\b(?:qu[eé]|q)\s+(?:me\s+)?(?:puedo|podr[ií]a)\s+(?:cocinar|comer)\b",
            r"\b(?:tirame|tir[aá]me|dame|recomendame|recomend[aá]me|sugerime|suger[ií]me)\b.*\b(?:ideas?|recetas?|comer|cocinar|platos?)\b",
            r"\b(?:ideas?|recetas?)\b.*\b(?:con|para)\b.*\b(?:tengo|hay)\b",
            r"\b(?:cocinar|comer)\b.*\b(?:con\s+lo\s+que|sin\s+comprar)\b",
        )
        return any(re.search(pattern, lowered) for pattern in advice_patterns)

    def _remember_context(self, state, path):
        if not path:
            return
        state.current_path = str(path)
        if self._memory and getattr(state, "session_id", None) and hasattr(self._memory, "save_folder_context"):
            self._memory.save_folder_context(state.session_id, str(path))

    @staticmethod
    def _alias_key(text):
        return re.sub(r"\s+", " ", re.sub(r"[^\wáéíóúüñ ]", " ", text.lower())).strip()

    def _dynamic_path(self, text):
        """Resolve a named folder through the bounded resolver."""
        result = self.folder_resolver.resolve(text)
        return result.get("path") if result.get("status") == "resolved" else None

    def _resolve_path(self, text):
        clean = self._alias_key(text)
        if clean in {"fotos", "foto", "imagenes", "imágenes", "pictures", "photos"}:
            resolved = self.folder_resolver.resolve_label("Fotos", context_path=str(self.folder_resolver._base()))
            if resolved.get("status") == "resolved":
                return resolved["path"]
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

    @staticmethod
    def _conversation_context(state, limit=8):
        """Return only this web session's recent turns, clearly attributed."""
        items = list(getattr(state, "conversation", []) or [])[-limit:]
        lines = []
        for item in items:
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            speaker = "Usuario" if item.get("role") == "user" else "ADA"
            lines.append(f"{speaker}: {text}")
        return "\n".join(lines)[-3500:]

    @staticmethod
    def _filesystem_followup(text, context_path):
        """Recognize short references to the folder already active in this session."""
        if not context_path:
            return None
        lowered = re.sub(r"\s+", " ", str(text).lower().strip(" .!?"))
        if re.search(r"\b(resumen|resumime|resumir|panorama)\b", lowered) and re.search(
            r"\b(lo que|contenido|carpeta|tiene|hay|eso|esto)\b", lowered
        ):
            return {"action": "list_dirs", "use_context": True, "summarize": True}
        if re.fullmatch(r"(?:y\s+)?(?:listar|lista|listame|listá|mostrar|mostrame|mostrá|ver|contenido)", lowered):
            return {"action": "list_dirs", "use_context": True, "summarize": False}
        match = re.match(r"^(?:y\s+)?(?:que|qué)\s+(?:tiene|hay(?:\s+en)?)\s+(.+)$", lowered)
        if match:
            subject = match.group(1).strip()
            referential = subject in {"ahi", "ahí", "adentro", "dentro", "eso", "esto", "esa", "esa carpeta"}
            return {"action": "list_dirs", "use_context": referential, "summarize": False}
        return None

    @staticmethod
    def _folder_overview(result):
        """Create a grounded overview from directory names without inventing file contents."""
        paths = [Path(value) for value in (result.get("dirs") or [])]
        names = [path.name for path in paths]
        location = Path(result.get("dir") or ".").name or str(result.get("dir") or "la carpeta")
        groups = (
            ("fotos y cámara", ("dcim", "camera", "panorama")),
            ("ediciones y collages", ("edit", "collage", "photocollage")),
            ("mensajería", ("whatsapp", "telegram")),
            ("descargas", ("download", "descarga")),
            ("transferencias por Bluetooth", ("bluetooth",)),
        )
        used = set()
        summaries = []
        for label, markers in groups:
            matches = [name for name in names if any(marker in name.casefold() for marker in markers)]
            if matches:
                used.update(matches)
                summaries.append(f"• {label}: {', '.join(matches)}")
        remaining = [name for name in names if name not in used]
        if remaining:
            summaries.append(f"• otras carpetas: {', '.join(remaining)}")
        count = result.get("count", len(names))
        if not names:
            return f"{location} no tiene subcarpetas visibles. No revisé todavía si contiene archivos sueltos."
        return (
            f"En {location} hay {count} carpetas principales. Por sus nombres, el contenido está organizado así:\n\n"
            + "\n".join(summaries)
            + "\n\nEs un resumen de la estructura; no abrí cada subcarpeta ni inferí archivos que no haya comprobado."
        )

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
                # Never recurse implicitly.  This is especially important for
                # Google Drive mounts (GVFS): a recursive walk can block while
                # the mount is paging remote entries and makes a simple root
                # question look like a dead request.  Recursive traversal must
                # be an explicit user/router decision.
                payload.setdefault("recursive", False)
                if re.search(r"\b(subcarpetas?|adentro|dentro|recursiv[oa])\b", lowered):
                    payload["recursive"] = True
            elif filesystem_action == "list_photos":
                payload.update({"action": "list_files", "extensions": [".jpg", ".jpeg", ".png", ".webp", ".xml", ".nef", ".arw", ".cr2", ".dng", ".raf", ".orf"]})
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

    def handle(self, text, state, lang=None, progress=None):
        text = str(text or "").strip()
        if not text:
            return {"error": "empty_message", "message": tr("empty_message", lang)}, 400
        self._emit(progress, "received", message=text)
        if lang:
            self.agent.lang = lang

        # Telegram's version command must never go through the LLM router.
        if re.fullmatch(r"/(?:v|version|versi[oó]n)", text, re.I):
            reply = "ADA versión 0.1.0"
            self._remember(state, text, reply)
            return {"reply": reply, "model": "ADA · sistema"}, 200
        if re.fullmatch(r"/i", text, re.I):
            reply = self._system_info()
            self._remember(state, text, reply)
            return {"reply": reply, "model": "ADA · sistema"}, 200
        if len(text.split()) <= 3 and re.fullmatch(
            r"(?:hola|hi|hello|buenas|buenos días|buenos dias|hey)", text, re.I
        ):
            reply = tr("greeting", lang)
            self._remember(state, text, reply)
            return {"reply": reply, "model": "ADA · respuesta rápida"}, 200

        if re.search(r"\b(que|qué)\s+(podes|puedes|haces|sabes hacer|funciones tenes|funciones tienes|herramientas tenes|MCPs? tenes|capacidades tenes)\b", text, re.I) or \
           re.search(r"\b(en que|en qué)\s+(me podes|me puedes|ayudas|me ayudas)\b", text, re.I) or \
           re.search(r"\b(quien|quién)\s+(sos|eres)\b", text, re.I):
            reply = self._capability_summary()
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

        context_path = getattr(state, "current_path", None)
        lowered = text.lower()
        # Short negative feedback refers to the active task; do not discard
        # the conversation and ask an unrelated emotional-support question.
        if context_path and re.fullmatch(r"(?:p[eé]simo|mal[ií]simo|horrible|no sirve)", lowered.strip(" .!?")):
            reply = (
                "Tenés razón: la respuesta anterior no resolvió la tarea. "
                "Tengo activa la carpeta " + str(context_path) + ". "
                "Puedo reintentar la búsqueda o contar las fotos directamente."
            )
            self._remember(state, text, reply)
            return {"reply": reply, "model": "ADA · contexto de tarea"}, 200
        contextual_followup = self._filesystem_followup(text, context_path)
        local_action = self._filesystem_intent(text) or (
            contextual_followup.get("action") if contextual_followup else None
        )
        summarize_folder = bool(contextual_followup and contextual_followup.get("summarize"))
        conversation_context = self._conversation_context(state)
        cached_result = getattr(state, "last_result", None)
        if (
            summarize_folder
            and isinstance(cached_result, dict)
            and cached_result.get("action") == "list_dirs"
            and str(cached_result.get("dir")) == str(context_path)
        ):
            reply = self._folder_overview(cached_result)
            self._emit(progress, "route_local", action="summarize_cached_directory", reason="session_result")
            self._remember(state, text, reply)
            return {"reply": reply, "model": "ADA · contexto de carpeta", "result": cached_result}, 200
        folder = {"status": "none", "candidates": []}
        existence_question = False

        if self._food_advice_intent(text):
            self._emit(progress, "route_rule", action="food/advise", reason="read_only_food_advice")
            parsed = {
                "action": "food",
                "domain": "recipes",
                "food_action": "advise",
                "advisor": True,
                "complexity": 4,
                "confidence": 1.0,
            }
        elif local_action:
            self._emit(progress, "route_local", action=local_action, reason="read_only_filesystem_question")
            self._emit(progress, "folder_resolver_started", context_path=context_path)
            existence_question = bool(re.search(r"\bhay\s+(?:una?\s+)?carpeta\b", lowered))
            content_of_photos = bool(
                re.search(r"\b(adentro|dentro|contenido)\b", lowered) and re.search(r"\bfotos?\b", lowered)
            )
            if contextual_followup and contextual_followup.get("use_context"):
                folder = {"status": "resolved", "path": context_path, "source": "session_context", "confidence": 1.0}
            elif existence_question and context_path:
                folder = {"status": "resolved", "path": context_path, "source": "session_context", "confidence": 1.0}
            elif content_of_photos:
                folder = self.folder_resolver.resolve_label("Fotos", context_path=context_path)
            else:
                folder = self.folder_resolver.resolve(text, context_path=context_path)
            self._emit(progress, "folder_resolver_finished", **folder)
            parsed = {"action": local_action, "complexity": 1}
        else:
            self._emit(progress, "router_model_started")
            try:
                parsed = self.agent.parse_prompt(text, history=conversation_context)
            except TypeError as exc:
                if "unexpected keyword argument 'history'" not in str(exc):
                    raise
                parsed = self.agent.parse_prompt(text)
            self._emit(progress, "router_model_finished", action=parsed.get("action"), confidence=parsed.get("confidence"))

        if folder["status"] == "ambiguous" and re.search(r"\b(fotos?|archivos?|carpetas?|documentos?|ruta)\b", lowered):
            choices = "\n".join(f"{i + 1}. {path}" for i, path in enumerate(folder["candidates"]))
            reply = f"Encontré varias carpetas posibles:\n{choices}\nDecime cuál querés usar."
            self._remember(state, text, reply)
            return {"reply": reply, "model": "ADA · resolver de carpetas", "folder_candidates": folder["candidates"]}, 200
        if local_action == "resolve_path" and folder["status"] == "resolved":
            self._remember_context(state, folder["path"])
            reply = f"La ruta es {folder['path']}."
            self._remember(state, text, reply)
            return {"reply": reply, "model": "ADA · resolver de carpetas", "path": folder["path"], "resolver": folder}, 200
        if folder["status"] == "resolved" and local_action:
            parsed = dict(parsed or {})
            parsed["action"] = local_action
            parsed["path"] = folder["path"]
            parsed["dir"] = folder["path"]
            if local_action == "list_files" and re.search(r"\b(fotos?|im[aá]genes?)\b", lowered):
                parsed["extensions"] = [".jpg", ".jpeg", ".png", ".webp", ".xml", ".nef", ".arw", ".cr2", ".dng", ".raf", ".orf"]
        elif local_action and folder["status"] == "none" and folder.get("reason") != "no_folder_terms":
            if folder.get("reason") == "stale_index":
                reply = (
                    "Esa carpeta estaba registrada en ADA, pero ya no está disponible en el disco o en "
                    "Google Drive local. Revisá que Drive esté sincronizado y volvé a intentar."
                )
            else:
                reply = "No pude ubicar esa carpeta dentro de Google Drive. Decime el nombre exacto o desde qué carpeta querés buscar."
            self._remember(state, text, reply)
            return {"reply": reply, "model": "ADA · resolver de carpetas", "resolver": folder}, 200
        # Folder/file questions with a known path must not fall through to the
        # generic chat model (which can ask for the path again).
        static_path = _resolve_path_alias(text) if not local_action and folder["status"] != "resolved" else folder.get("path")
        if static_path and re.search(r"\b(archivos?|ficheros?|documentos?|fotos?)\b", lowered):
            parsed = dict(parsed or {})
            parsed["action"] = "list_files"
            parsed.setdefault("path", static_path)
            parsed.setdefault("dir", static_path)
            parsed.setdefault("complexity", 1)
        action_name = parsed.get("action")
        if action_name in {None, "ask", "suggest"}:
            complexity = parsed.get("complexity")
            if complexity is None:
                complexity = self.agent.estimate_complexity(text)
            model_task = {
                "type": None,
                "prompt": text,
                "complexity": complexity,
                "use_memory": True,
                "mode": "agent",
                "conversation_context": conversation_context,
            }
            manager = getattr(self.agent, "model_manager", None)
            model_role = manager.role_for_task(model_task) if manager and hasattr(manager, "role_for_task") else "chat"
            model_name = manager.select_model(model_role, role=model_role) if manager and hasattr(manager, "select_model") else None
            self._emit(progress, "model_started", model=model_name, role=model_role)
            result = self.agent.decide_and_run(model_task)
            self._emit(progress, "model_finished", model=model_name, role=model_role)
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
        self._emit(progress, "capability_started", capability=action, payload=payload)
        result = self.agent.decide_and_run(task)
        output = result.get("result", result)
        self._emit(
            progress,
            "capability_finished",
            capability=action,
            ok=not bool(output.get("error")) if isinstance(output, dict) else True,
            error=output.get("error") if isinstance(output, dict) else None,
        )
        if isinstance(output, dict) and output.get("error") == "confirmation_required":
            state.pending_action = task
            reply = tr("confirmation_required", lang)
        else:
            if (
                isinstance(output, dict)
                and output.get("action") == "list_dirs"
                and existence_question
                and re.search(r"\bcarpetas?\b", lowered)
                and re.search(r"\bfotos?\b", lowered)
            ):
                photos = next(
                    (path for path in output.get("dirs", []) if Path(path).name.casefold() == "fotos"),
                    None,
                )
                reply = f"Sí, hay una carpeta Fotos en {photos}." if photos else f"No encontré una carpeta Fotos en {output.get('dir')}."
            elif (
                isinstance(output, dict)
                and output.get("action") == "list_files"
                and re.search(r"\b(cu[aá]nt[oa]s?|cantidad|total)\b", lowered)
            ):
                counts = output.get("photo_counts")
                if counts and re.search(r"\b(fotos?|im[aá]genes?|evento|originales?)\b", lowered):
                    accepted = max(counts.get("raw", 0), counts.get("xml", 0), counts.get("jpg", 0))
                    if counts.get("jpg", 0) > 0:
                        reply = f"Encontré {accepted} fotos aceptadas y exportadas en {output.get('dir')}."
                    else:
                        reply = f"Encontré {accepted} fotos aceptadas sin exportar en {output.get('dir')}."
                else:
                    noun = "fotos" if re.search(r"\b(fotos?|im[aá]genes?)\b", lowered) else "archivos"
                    count = output.get("count", len(output.get("files") or []))
                    reply = f"Hay {count} {noun} en {output.get('dir')}."
            elif summarize_folder and isinstance(output, dict) and output.get("action") == "list_dirs":
                reply = self._folder_overview(output)
            else:
                reply = text_from_result(output)
        if isinstance(output, dict) and not output.get("error") and output.get("dir"):
            state.last_result = output
            self._remember_context(state, output["dir"])
            if output.get("action") == "list_dirs" and self._memory and hasattr(self._memory, "index_folders"):
                indexed = self._memory.index_folders(output["dir"], output.get("dirs") or [])
                self._emit(progress, "folder_index_updated", parent=output["dir"], indexed=indexed)
        self._remember(state, text, reply)
        return {"reply": reply, "model": result.get("model", "tool"), "result": output}, 200

    @staticmethod
    def _system_info():
        """Compact, non-invasive machine summary for the /i command."""
        try:
            import psutil
            memory = psutil.virtual_memory()
            cpu = psutil.cpu_percent(interval=0.15)
            battery = psutil.sensors_battery()
            battery_text = "No disponible"
            if battery:
                state = "cargando" if battery.power_plugged else "batería"
                battery_text = f"{battery.percent:.0f}% ({state})"
            memory_text = f"{memory.percent:.0f}% usado de {memory.total / (1024**3):.1f} GB"
        except Exception:
            memory_text = "No disponible"
            cpu = "No disponible"
            battery_text = "No disponible"
        disk = shutil.disk_usage(os.path.expanduser("~"))
        return (
            "Información del equipo\n\n"
            f"• Equipo: {platform.node() or 'No disponible'}\n"
            f"• Sistema: {platform.system()} {platform.release()}\n"
            f"• CPU: {cpu}% de uso ({os.cpu_count() or '?'} núcleos)\n"
            f"• Memoria: {memory_text}\n"
            f"• Batería: {battery_text}\n"
            f"• Disco disponible: {disk.free / (1024**3):.1f} GB"
        )
