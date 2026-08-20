"""Intent router for natural-language requests.

The router is model-assisted, but never trusts an arbitrary model response as
an executable command. It validates the requested action and falls back to a
small deterministic classifier when no model is available.
"""

import json
import logging
import re


logger = logging.getLogger("ada.router")


class IntentRouter:
    def __init__(self, model_manager, config=None, memory=None):
        self.model_manager = model_manager
        self.config = config or {}
        if memory is None:
            raise ValueError("IntentRouter requiere una instancia de memoria inyectada.")
        self.memory = memory

    def _allowed_actions(self):
        return {row["action"] for row in self.memory.router_actions()}

    def _actions_text(self):
        return ", ".join(f"{row['action']} ({row['description']})" for row in self.memory.router_actions())

    def _template(self, name, fallback):
        return self.memory.prompt_template(name, fallback)

    def _schema(self, name):
        return self.memory.json_schema(name)

    def route(self, text, history=""):
        fallback = self._fallback(text)
        provider = self.model_manager.choose(
            {
                "complexity": 4,
                "privacy": self.config.get("privacy_default", "normal"),
            }
        )
        if not provider:
            return fallback
        prompt = self._prompt(text, history)
        logger.debug("router request=%r history_chars=%d", text, len(history))
        try:
            raw = self.model_manager.call(
                provider,
                prompt,
                ollama_model=self.config.get("models", {}).get("router") or self.config.get("router_model"),
                temperature=0,
                max_tokens=600,
                timeout=self.config.get("router_timeout", 45),
                format=self._schema("router"),
            )
            logger.info("router raw=%s", str(raw)[:1000])
            normalized = self._normalize(self._decode(raw), fallback)
            if normalized.get("action") == "food" and normalized.get("food_action") in {"add", "check", "remove"}:
                verified = self._verify_food_mutation(provider, text, normalized)
                if not verified:
                    normalized = {
                        "action": "food",
                        "domain": "recipes",
                        "food_action": "advise",
                        "advisor": True,
                        "complexity": 4,
                        "confidence": normalized.get("confidence", 0.0),
                    }
            if normalized.get("action") in {"ask", "suggest"}:
                food = self._route_food(provider, text, history)
                if food:
                    return food
            logger.info(
                "router normalized action=%s food_action=%s confidence=%s",
                normalized.get("action"),
                normalized.get("food_action"),
                normalized.get("confidence"),
            )
            return normalized
        except Exception as exc:
            logger.warning("router failed: %s", exc)
            return fallback

    def _verify_food_mutation(self, provider, text, intent):
        template = self._template(
            "food_mutation_verifier", "Verificá la mutación y devolvé SOLO JSON. Intención: {intent}\nPedido: {text}"
        )
        prompt = template.replace("{intent}", str(intent)).replace("{text}", text)
        try:
            raw = self.model_manager.call(
                provider,
                prompt,
                temperature=0,
                max_tokens=180,
                timeout=self.config.get("router_timeout", 45),
                format=self._schema("food_verify"),
            )
            result = self._decode(raw)
            logger.info(
                "food mutation verification raw=%s allow=%s",
                str(raw)[:500],
                result.get("allow") if isinstance(result, dict) else None,
            )
            return isinstance(result, dict) and result.get("allow") is True
        except Exception as exc:
            logger.warning("food mutation verification failed: %s", exc)
            return False

    def _route_food(self, provider, text, history):
        """Second-pass semantic classifier for food requests.

        This is intentionally model-based: it catches natural requests such
        as "no sé qué cocinar" without maintaining a phrase dictionary.
        """
        template = self._template(
            "food_classifier", "Clasificá el pedido y devolvé SOLO JSON. Historial: {history}\nPedido: {text}"
        )
        prompt = (
            template.replace("{history}", history[-1200:])
            .replace("{text}", text)
            .replace("{food_actions}", "advise, add, list, check, remove, save, recipe_to_shopping")
        )
        try:
            raw = self.model_manager.call(
                provider,
                prompt,
                temperature=0,
                max_tokens=400,
                timeout=self.config.get("router_timeout", 45),
                format=self._schema("food"),
            )
            candidate = self._decode(raw)
            logger.info("food classifier raw=%s", str(raw)[:800])
            if not isinstance(candidate, dict):
                return None
            domain = str(candidate.get("domain", "")).lower()
            raw_action = str(candidate.get("action", "")).lower()
            is_food = (
                candidate.get("is_food") is True
                or raw_action.startswith("food")
                or domain in {"food", "comida", "comidas", "shopping", "compras", "recipes", "recetas"}
                or candidate.get("food_action")
                in {"advise", "add", "list", "check", "remove", "save", "recipe_to_shopping"}
            )
            if not is_food:
                return None
            result = dict(candidate)
            if raw_action.startswith("food/"):
                result["food_action"] = raw_action.split("/", 1)[1]
            result["food_action"] = (
                result.get("food_action")
                if result.get("food_action")
                in {"advise", "add", "list", "check", "remove", "save", "recipe_to_shopping"}
                else "advise"
            )
            if domain in {"compras", "shopping"}:
                result["domain"] = "shopping"
            elif domain in {"recetas", "recipes", "comida", "comidas", "food"}:
                result["domain"] = "recipes"
            result.update(
                {
                    "action": "food",
                    "advisor": result.get("food_action") == "advise",
                    "confidence": self._confidence(candidate.get("confidence")),
                    "complexity": 4,
                }
            )
            result.pop("needs_clarification", None)
            result.pop("clarifying_question", None)
            logger.info("food classifier normalized food_action=%s", result.get("food_action"))
            return result
        except Exception as exc:
            logger.warning("food classifier failed: %s", exc)
            return None

    def _prompt(self, text, history):
        template = self._template(
            "router",
            "Clasificá la solicitud y devolvé SOLO JSON. Acciones: {actions}. Historial: {history}\nPedido: {text}",
        )
        return (
            template.replace("{actions}", self._actions_text())
            .replace("{food_actions}", "advise, add, list, check, remove, save, recipe_to_shopping")
            .replace("{history}", history[-2500:])
            .replace("{text}", text)
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
        candidate = dict(candidate)
        action = str(candidate.get("action") or "").lower()
        if action.startswith("food/"):
            candidate["action"] = "food"
            candidate.setdefault("food_action", action.split("/", 1)[1])
            candidate["advisor"] = candidate.get("food_action") in {"advise", "ask", "suggest"}
            candidate.pop("needs_clarification", None)
            candidate.pop("clarifying_question", None)
            action = "food"
        if action not in self._allowed_actions():
            return fallback
        result = dict(fallback)
        result.update({key: value for key, value in candidate.items() if value is not None})
        result["action"] = action
        result["confidence"] = self._confidence(candidate.get("confidence"))
        steps = candidate.get("steps")
        if isinstance(steps, list):
            result["steps"] = [
                item for item in steps if isinstance(item, dict) and item.get("action") in self._allowed_actions()
            ]
        if candidate.get("needs_clarification"):
            result["needs_clarification"] = True
            result["clarifying_question"] = str(
                candidate.get("clarifying_question") or "Necesito un dato más para hacerlo."
            )
        return result

    @staticmethod
    def _confidence(value):
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    def _fallback(self, text):
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
            "food": (
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
        }
        if self.memory:
            scores = {row["action"]: tuple(row.get("keywords") or []) for row in self.memory.router_actions()}
        matches = {action: sum(1 for phrase in phrases if phrase in value) for action, phrases in scores.items()}
        action, score = max(matches.items(), key=lambda item: item[1])
        if score == 0:
            return {"action": "ask", "complexity": 3, "confidence": 0.0}
        if action == "food":
            return {
                "action": "food",
                "food_action": "advise",
                "advisor": True,
                "complexity": 4,
                "confidence": min(0.75, 0.35 + score * 0.15),
            }
        return {"action": action, "complexity": 5 if score == 1 else 6, "confidence": min(0.85, 0.35 + score * 0.15)}
