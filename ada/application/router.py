"""Intent router for natural-language requests.

The router is model-assisted, but never trusts an arbitrary model response as
an executable command. It validates the requested action and falls back to a
small deterministic classifier when no model is available.
"""

import json
import logging
import re
from datetime import date

logger = logging.getLogger("ada.router")

FOOD_ACTIONS = {
    "advise",
    "add",
    "list",
    "check",
    "remove",
    "save",
    "recipe_to_shopping",
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
}
FOOD_MUTATIONS = FOOD_ACTIONS - {"advise", "list", "inventory_list", "budget_list", "plan_list"}


def is_capability_discussion(text):
    """Return True when capability words are being discussed, not commanded.

    Natural requests such as "compará los riesgos de organizar archivos" used
    to be routed as an actual filesystem mutation just because they contained
    the infinitive "organizar".  Discussion markers take precedence over the
    capability keyword so the chat model can answer the question safely.
    """
    value = str(text or "").lower()
    capability_terms = re.search(
        r"\b(archivos?|carpetas?|directorios?|fotos?|im[aá]genes?|lightroom|agente\s+local|"
        r"permisos?|acceso|timeout|modo|mcp|m[eé]tricas?|calendar|calendario|gmail|telegram)\b",
        value,
    )
    discussion_markers = re.search(
        r"\b(ventajas?|desventajas?|riesgos?|pros?|contras?|enfoques?|alternativas?|"
        r"compar(?:á|a|ar|ame|emos)|explic(?:á|a|ar|ame)|qu[eé]\s+conviene|"
        r"recomendaci[oó]n|concepto|teor[ií]a|significa|funciona|general|"
        r"sin\s+(?:acceder|cambiar|ejecutar)|diferencia)\b",
        value,
    )
    return bool(capability_terms and discussion_markers)


class IntentRouter:
    def __init__(self, model_manager, config=None, memory=None, mcp_manager=None):
        self.model_manager = model_manager
        self.config = config or {}
        if memory is None:
            raise ValueError("IntentRouter requiere una instancia de memoria inyectada.")
        self.memory = memory
        self.mcp_manager = mcp_manager

    def _allowed_actions(self):
        return {row["action"] for row in self.memory.router_actions()}

    def _actions_text(self):
        actions = [f"{row['action']} ({row['description']})" for row in self.memory.router_actions()]
        if self.mcp_manager:
            actions.append("mcp_call (ejecutar una herramienta MCP de solo lectura seleccionada del inventario)")
        return ", ".join(actions)

    def _tools_text(self, category=None):
        if not self.mcp_manager:
            return "(sin MCPs disponibles)"
        try:
            tools = [
                tool for tool in self.mcp_manager.list_tools()
                if tool.get("enabled") and not tool.get("requires_confirmation")
                and (not category or tool.get("category") == category or tool.get("server") == category)
            ]
            return "\n".join(
                f"- {tool.get('name')} [{tool.get('category') or tool.get('server')}] — {tool.get('description') or 'sin descripción'}"
                for tool in tools
            ) or "(sin herramientas MCP activas)"
        except Exception:
            return "(inventario MCP no disponible)"

    def _template(self, name, fallback):
        return self.memory.prompt_template(name, fallback)

    def _schema(self, name):
        schema = self.memory.json_schema(name)
        if name == "router" and isinstance(schema, dict):
            schema = json.loads(json.dumps(schema))
            action = schema.setdefault("properties", {}).setdefault("action", {})
            values = action.setdefault("enum", [])
            if self.mcp_manager and "mcp_call" not in values:
                values.append("mcp_call")
            schema["properties"].update({
                "tool": {"type": "string"},
                "parameters": {"type": "object", "additionalProperties": True},
            })
        return schema

    @staticmethod
    def _mcp_schema():
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["mcp_call"]},
                "tool": {"type": "string"},
                "parameters": {"type": "object", "additionalProperties": True},
            },
            "required": ["action", "tool", "parameters"],
            "additionalProperties": False,
        }

    def route(self, text, history=""):
        if is_capability_discussion(text):
            return {"action": "ask", "complexity": 4, "confidence": 0.98}
        fallback = self._fallback(text)
        # A plain conversational question with no capability keyword does not
        # need a model call just to be classified as chat. This removes an
        # entire cold start from the most common path.
        contextual_reference = bool(history and re.search(
            r"\b(eso|esto|esa|ese|ah[ií]|adentro|anterior|antes|lo\s+que|me\s+refiero|resumen|listar)\b|^(?:y|tamb[ié]n)\b",
            text.lower(),
        ))
        external_hint = bool(self.mcp_manager and re.search(
            r"\b(calendar|calendario|evento|gmail|correo|mails?|drive|internet|fuente|d[oó]lar|"
            r"busc[aá]|investig[aá]|verific[aá]|confirm[aá]|actual|hoy|últim[oa]|noticia|precio|"
            r"no\s+(?:sé|se)|duda|qué\s+pas[oó]|qui[eé]n\s+es)\b", text.lower()
        ))
        if fallback.get("action") == "ask" and fallback.get("confidence") == 0.0 and not contextual_reference and not external_hint:
            return fallback
        provider = self.model_manager.choose(
            {
                "complexity": 4,
                "privacy": self.config.get("privacy_default", "normal"),
            }
        )
        if not provider:
            if external_hint and self.mcp_manager:
                return {
                    "action": "ask",
                    "routing_error": "mcp_router_unavailable",
                    "complexity": 4,
                    "confidence": 0.0,
                }
            return fallback
        prompt = self._mcp_prompt(text) if external_hint else self._prompt(text, history)
        logger.debug("router request=%r history_chars=%d", text, len(history))
        try:
            raw = self.model_manager.call(
                provider,
                prompt,
                ollama_model=self.model_manager.select_model("router", role="router"),
                temperature=0,
                max_tokens=180 if external_hint else 180,
                timeout=max(self.config.get("router_timeout", 30), 60) if external_hint else self.config.get("router_timeout", 30),
                format=self._mcp_schema() if external_hint else self._schema("router"),
            )
            logger.info("router raw=%s", str(raw)[:1000])
            normalized = self._normalize(self._decode(raw), fallback)
            if external_hint and normalized.get("action") != "mcp_call":
                return {
                    "action": "ask",
                    "routing_error": "external_request_not_grounded",
                    "complexity": 4,
                    "confidence": 0.0,
                }
            if normalized.get("action") == "food" and normalized.get("food_action") in FOOD_MUTATIONS:
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
                food_clues = (
                    "comida", "comidas", "receta", "recetas", "cocinar", "cocina", "compras",
                    "supermercado", "ingredientes", "comer", "cena", "almuerzo", "desayuno",
                    "heladera", "alacena", "despensa", "plato", "menú", "menu", "vianda"
                )
                if any(clue in text.lower() for clue in food_clues):
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
            if external_hint and self.mcp_manager:
                return {
                    "action": "ask",
                    "routing_error": "mcp_router_failed",
                    "complexity": 4,
                    "confidence": 0.0,
                }
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
                timeout=self.config.get("router_timeout", 30),
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
            .replace("{food_actions}", ", ".join(sorted(FOOD_ACTIONS)))
        )
        try:
            raw = self.model_manager.call(
                provider,
                prompt,
                temperature=0,
                max_tokens=400,
                timeout=self.config.get("router_timeout", 30),
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
                or domain
                in {
                    "food",
                    "comida",
                    "comidas",
                    "shopping",
                    "compras",
                    "recipes",
                    "recetas",
                    "inventory",
                    "budget",
                    "planning",
                }
                or candidate.get("food_action") in FOOD_ACTIONS
            )
            if not is_food:
                return None
            result = dict(candidate)
            if raw_action.startswith("food/"):
                result["food_action"] = raw_action.split("/", 1)[1]
            result["food_action"] = result.get("food_action") if result.get("food_action") in FOOD_ACTIONS else "advise"
            if domain in {"compras", "shopping"}:
                result["domain"] = "shopping"
            elif domain in {"recetas", "recipes", "comida", "comidas", "food"}:
                result["domain"] = "recipes"
            elif domain in {"inventory", "inventario", "stock", "despensa"}:
                result["domain"] = "inventory"
            elif domain in {"budget", "presupuesto"}:
                result["domain"] = "budget"
            elif domain in {"planning", "plan", "meal_plan", "comidas_semanales"}:
                result["domain"] = "planning"
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
            .replace("{food_actions}", ", ".join(sorted(FOOD_ACTIONS)))
            .replace("{history}", history[-2500:])
            .replace("{text}", text)
            + "\nHerramientas MCP activas:\n" + self._tools_text()
            + "\nSi corresponde a una consulta externa, elegí mcp_call con esta forma exacta: "
            + '{"action":"mcp_call","tool":"nombre.del.inventario","parameters":{}}. '
            + "No uses method, params ni nombres inventados; no inventes resultados."
        )

    def _mcp_prompt(self, text):
        """Keep external tool selection focused on the live MCP catalog."""
        category = "web_search" if re.search(r"\b(internet|web|noticia|fuente|enlace)\b", text, re.I) else None
        catalog = self._tools_text(category) or self._tools_text()
        return (
            "Debés elegir una herramienta MCP del inventario para responder el pedido; no respondas con texto, no pidas aclaraciones y no uses una acción local. "
            "Devolvé SOLO JSON con esta forma exacta: "
            '{"action":"mcp_call","tool":"nombre.del.inventario","parameters":{}}. '
            "Usá únicamente un nombre listado y parámetros necesarios para el pedido. "
            "No inventes datos ni uses method o params.\n"
            "Si se piden próximos eventos sin un eventId, elegí una herramienta de listado o búsqueda; "
            "no uses una herramienta de detalle que requiera un ID.\n"
            f"Fecha actual: {date.today().isoformat()}. Para eventos próximos no uses fechas pasadas.\n"
            "Inventario MCP activo:\n" + catalog + "\nPedido: " + text
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
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            # Ollama can truncate a structured response at the token limit.
            # Recover only the explicit MCP action/tool pair; parameters stay
            # empty and are validated by the live catalog before execution.
            action = re.search(r'"action"\s*:\s*"(mcp_call)"', text)
            tool = re.search(r'"tool"\s*:\s*"([A-Za-z0-9_.-]+)"', text)
            if action and tool:
                return {"action": action.group(1), "tool": tool.group(1), "parameters": {}}
            return {}

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
        if action == "mcp_call":
            tool = str(candidate.get("tool") or "")
            if not tool or not self.mcp_manager:
                return fallback
            known = {item.get("name"): item for item in self.mcp_manager.list_tools()}
            definition = known.get(tool)
            if not definition or not definition.get("enabled") or definition.get("requires_confirmation"):
                return fallback
            result = dict(fallback)
            result.update({"action": "mcp_call", "tool": tool, "parameters": candidate.get("parameters") or {}, "confidence": self._confidence(candidate.get("confidence"))})
            return result
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
        if re.search(r"\b(que|qué)\s+(podes|puedes|haces|sabes hacer|funciones tenes|funciones tienes)\b", value) or \
           re.search(r"\b(quien|quién)\s+(sos|eres)\b", value) or \
           value.strip() in {"ayuda", "help", "hola"}:
            return {"action": "ask", "complexity": 3, "confidence": 0.95}
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
