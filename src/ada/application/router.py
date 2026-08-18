"""Intent router for natural-language requests.

The router is model-assisted, but never trusts an arbitrary model response as
an executable command. It validates the requested action and falls back to a
small deterministic classifier when no model is available.
"""

import json
import re


ALLOWED_ACTIONS = {
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
    "ask",
}


class IntentRouter:
    def __init__(self, model_manager, config=None):
        self.model_manager = model_manager
        self.config = config or {}

    def route(self, text, history=""):
        fallback = self._fallback(text)
        provider = self.model_manager.choose({
            "complexity": 4,
            "privacy": self.config.get("privacy_default", "normal"),
        })
        if not provider:
            return fallback
        prompt = self._prompt(text, history)
        try:
            raw = self.model_manager.call(
                provider,
                prompt,
                ollama_model=self.config.get("router_model", self.config.get("ollama_model")),
                temperature=0,
                max_tokens=600,
                timeout=self.config.get("router_timeout", 45),
            )
            return self._normalize(self._decode(raw), fallback)
        except Exception:
            return fallback

    @staticmethod
    def _prompt(text, history):
        return (
            "Sos el router de ADA. Clasificá la solicitud y devolvé SOLO JSON válido. "
            "No ejecutes acciones ni inventes rutas. Elegí una acción de esta lista: "
            + ", ".join(sorted(ALLOWED_ACTIONS))
            + ". Si hay varios pedidos, incluí steps con acciones en orden. "
            "Si falta un dato imprescindible, usá needs_clarification=true y una pregunta breve.\n\n"
            f"Historial reciente:\n{history[-2500:]}\n\nSolicitud:\n{text}\n\n"
            'Formato: {"action":"...","confidence":0.0,"reason":"...",'
            '"steps":[{"action":"...","reason":"..."}],'
            '"needs_clarification":false,"clarifying_question":""}'
        )

    @staticmethod
    def _decode(raw):
        if isinstance(raw, dict):
            return raw
        text = str(raw).strip()
        fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.I | re.S)
        if fenced:
            text = fenced.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.S)
            return json.loads(match.group(0)) if match else {}

    def _normalize(self, candidate, fallback):
        if not isinstance(candidate, dict):
            return fallback
        action = candidate.get("action")
        if action not in ALLOWED_ACTIONS:
            return fallback
        result = dict(fallback)
        result.update({key: value for key, value in candidate.items() if value is not None})
        result["action"] = action
        result["confidence"] = self._confidence(candidate.get("confidence"))
        steps = candidate.get("steps")
        if isinstance(steps, list):
            result["steps"] = [
                item for item in steps
                if isinstance(item, dict) and item.get("action") in ALLOWED_ACTIONS
            ]
        if candidate.get("needs_clarification"):
            result["needs_clarification"] = True
            result["clarifying_question"] = str(candidate.get("clarifying_question") or "Necesito un dato más para hacerlo.")
        return result

    @staticmethod
    def _confidence(value):
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _fallback(text):
        value = text.lower()
        scores = {
            "analyze_photo": ("foto", "imagen", "raw", "jpg", "nef", "arw", "enfoque", "exposición", "iso"),
            "select_photo_batch": ("selección", "seleccionar", "descartes", "ráfaga", "rafaga", "lote", "xmp"),
            "lightroom": ("lightroom", "colección", "sqlite", "biblioteca", "rechazadas"),
            "list_photos": ("listar fotos", "mostrame fotos", "ver fotos"),
            "list_files": ("listar archivos", "lista los archivos", "listame los archivos", "documentos"),
            "list_dirs": ("carpetas", "directorios", "estructura"),
            "group_files": ("agrupar", "mover archivos", "juntar archivos"),
            "organize": ("organizar", "ordenar archivos", "ordenar los archivos"),
            "suggest": ("sugerir", "recomendar"),
            "run": ("ejecutar", "correr comando", "script"),
        }
        matches = {
            action: sum(1 for phrase in phrases if phrase in value)
            for action, phrases in scores.items()
        }
        action, score = max(matches.items(), key=lambda item: item[1])
        if score == 0:
            return {"action": "ask", "complexity": 3, "confidence": 0.0}
        return {"action": action, "complexity": 5 if score == 1 else 6, "confidence": min(0.85, 0.35 + score * 0.15)}
