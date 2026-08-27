import json
import logging
import os
import re
import secrets
import time
from pathlib import Path

from ada.infrastructure.engines.model_manager import ModelManager
from ada.infrastructure.persistence.sqlite import Memory
from ada.capabilities.registry import capability_catalog, load_capabilities
from ada.agents.coordinator import MultiAgentCoordinator
from ada.application.router import IntentRouter, is_capability_discussion
from ada.domain.policy import PolicyEngine, PolicyViolation
from ada.application.planner import Planner
from ada.domain.tasks import Action
from ada.infrastructure.observability import Metrics
from ada.application.services.complexity import ComplexityEstimator
from ada.application.services.knowledge import KnowledgeLoader
from ada.application.services.prompts import PromptBuilder

logger = logging.getLogger("ada.agent")


class Agent:
    """ADA's general-purpose agent: route, execute tools, report and remember."""

    def __init__(self, cfg=None, mcp_manager=None):
        self.cfg = cfg or {}
        self.metrics = Metrics("agent")
        self.model_manager = ModelManager(self.cfg)
        db_path = self.cfg.get("db_path", str(Path.home() / "Desktop" / "ADA_Data" / "memory.db"))
        self.mem = Memory(
            db_path,
            encrypted=bool(self.cfg.get("memory_encryption", False)),
            encryption_key=os.environ.get("ADA_MEMORY_KEY"),
        )
        self.capabilities_enabled = bool(self.cfg.get("capabilities_enabled", True))
        self.skills = load_capabilities()
        self.coordinator = MultiAgentCoordinator(self.cfg)
        self.router = IntentRouter(self.model_manager, self.cfg, memory=self.mem, mcp_manager=mcp_manager)
        self.policy = PolicyEngine(self.cfg)
        self.planner = Planner(self.skills, self.policy)
        self.knowledge_loader = KnowledgeLoader(self.mem)
        self.mcp_manager = mcp_manager
        self.prompt_builder = PromptBuilder(self.mem, mcp_manager=mcp_manager)
        self._load_knowledge()
        self.history = []
        self.lang = self.cfg.get("lang", "auto")
        self.running = True

    @staticmethod
    def _safe_error(message, exc):
        error_id = secrets.token_hex(8)
        logger.exception("agent_operation_failed error_id=%s", error_id)
        return {"error": message, "error_id": error_id}

    @staticmethod
    def _memory_tool_request(result):
        """Decode the single bounded memory-as-a-tool request, if present."""
        try:
            candidate = result if isinstance(result, dict) else json.loads(str(result).strip())
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        call = candidate.get("tool_call") if isinstance(candidate, dict) else None
        if not isinstance(call, dict) or call.get("name") != "memory.search":
            return None
        arguments = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
        query = str(arguments.get("query") or "").strip()
        if not query:
            return None
        try:
            limit = int(arguments.get("limit", 3) or 3)
        except (TypeError, ValueError):
            limit = 3
        return {"query": query, "limit": min(3, max(1, limit))}

    def _complete_with_memory_tool(self, provider, prompt, result, call_options):
        """Execute at most one explicit memory lookup, then resume generation."""
        request = self._memory_tool_request(result)
        if not request or not self.mcp_manager or not self.cfg.get("memory_as_tool", True):
            return result
        lookup = self.mcp_manager.execute_tool(
            "memory.search", {**request, "_request": request["query"]}, self
        )
        continuation = (
            str(prompt)
            + "\n\nResultado de memory.search (usalo como fuente, no inventes otros recuerdos):\n"
            + json.dumps(lookup, ensure_ascii=False)
            + "\nRespondé ahora al usuario sin volver a pedir otra herramienta."
        )
        return self.model_manager.call(provider, continuation, **call_options)

    def plan_request(self, text):
        """Turn a routed request into a validated, non-executing plan."""
        parsed = self.parse_prompt(text)
        action_name = parsed.get("action")
        if action_name in {None, "ask", "suggest"}:
            return self.planner.from_actions([], explanation="Conversación o sugerencia sin mutación.")
        payload = {key: value for key, value in parsed.items() if key not in {"action", "complexity"}}
        return self.planner.from_actions(
            [Action(action_name, payload)], explanation=f"Acción seleccionada: {action_name}"
        )

    def capability_catalog(self):
        return capability_catalog() if self.capabilities_enabled else {}

    def _load_knowledge(self):
        return self.knowledge_loader.load_files(self.cfg.get("knowledge_files", []))

    def _system_prompt(self):
        return self.prompt_builder.system(self.lang)

    def decide_and_run(self, task):
        task = dict(task)
        if task.get("task_type") and not task.get("model_role"):
            task["model_role"] = task["task_type"]
        if task.get("model_hint") in {"chat", "reasoning", "coding", "vision", "tools", "router"}:
            task.setdefault("model_role", task["model_hint"])
        task.setdefault("complexity", self.estimate_complexity(task.get("prompt", "")))
        provider = self.model_manager.choose(task)
        self.history.append({"task": task, "chosen_model": provider})

        skill_name = task.get("type")
        if skill_name == "mcp_call":
            if not self.mcp_manager:
                result = {"error": "No hay un administrador MCP disponible."}
            else:
                tool = str((task.get("payload") or {}).get("tool") or "")
                parameters = dict((task.get("payload") or {}).get("parameters") or {})
                parameters.setdefault("_request", task.get("prompt", ""))
                if task.get("confirm"):
                    parameters["_confirmed"] = True
                result = self.mcp_manager.execute_tool(tool, parameters, self)
            self.mem.record_task(task, result, provider="mcp", success=not bool(result.get("error")))
            return {"model": "mcp", "result": result}
        if skill_name and not self.capabilities_enabled:
            # No in-process action is allowed in the default architecture.
            # Integrations and local tools must be selected as MCP calls.
            result = {
                "error": "action_requires_mcp",
                "action": skill_name,
                "message": "Esta acción debe ejecutarse mediante una herramienta MCP activa.",
            }
            self.mem.record_task(task, result, provider="mcp", success=False)
            return {"model": "mcp", "result": result}
        if skill_name == "food":
            payload = dict(task.get("payload", {}))
            payload.setdefault("config", self.cfg)
            payload.setdefault("db_path", self.mem.db_path)
            payload["action"] = payload.pop("food_action", payload.get("action", "list"))
            if payload.get("action") in {"advise", "ask", "suggest"} or payload.get("advisor"):
                inventory = self.run_skill(
                    "food",
                    {
                        "db_path": self.mem.db_path,
                        "domain": "inventory",
                        "action": "list",
                        "config": self.cfg,
                    },
                )
                request = str(task.get("prompt") or "")
                has_specific_ingredients = self._food_request_has_specific_ingredients(request)
                if not inventory.get("items") and not has_specific_ingredients:
                    reply = (
                        "Todavía no tengo ingredientes cargados en tu alacena. "
                        "Decime qué tenés —aunque sea tres cosas— y te propongo una comida rápida sin comprar nada."
                    )
                elif has_specific_ingredients:
                    # A concrete ingredient list is enough for a useful local
                    # answer. Avoid holding the chat open while a culinary
                    # model starts up or times out.
                    reply = self._fallback_food_advice(request)
                else:
                    reply = self.advise_food(request) or self._fallback_food_advice(request)
                result = {"ok": True, "action": "advise", "reply": reply}
                self.mem.record_task(task, result, provider="food-advisor", success=True)
                return {"model": "food-advisor", "result": result}
            result = self.run_skill("food", payload)
            self.mem.record_task(task, result, provider="food", success=not bool(result.get("error")))
            return {"model": "food", "result": result}
        if skill_name == "analyze_photo":
            payload = dict(task.get("payload", {}))
            payload.setdefault("config", self.cfg)
            result = self.coordinator.run({"workflow": "photo_review", **payload})
            self.mem.record_task(
                task, result, provider=provider or "multi-agent", success=not bool(result.get("error"))
            )
            return {"model": provider or "multi-agent", "result": result}
        if skill_name in self.skills:
            skill_args = dict(task.get("payload", {}))
            if task.get("confirm") is not None:
                skill_args["confirm"] = task.get("confirm")
            result = self.run_skill(skill_name, skill_args, confirm=task.get("confirm"))
            self.mem.record_audit(
                skill_name,
                request=task,
                result=result,
                success=not bool(result.get("error")) if isinstance(result, dict) else True,
            )
            self.mem.record_task(
                task,
                result,
                provider=provider,
                success=not bool(result.get("error")) if isinstance(result, dict) else True,
            )
            return {"model": provider or "tool", "result": result}

        if not provider:
            result = {"error": "No hay modelos disponibles. Configura llama.cpp, Ollama o una API remota."}
            self.mem.record_task(task, result, success=False)
            return {"model": None, "result": result}

        prompt = self.prompt_builder.task(task, self.lang)
        model_role = self.model_manager.role_for_task(task)
        model_name = self.model_manager.ensure_model(task, role=model_role)
        role_token_limits = self.cfg.get("model_role_max_tokens", {})
        call_options = {
            "timeout": self.cfg.get("model_timeout", 300),
            "max_tokens": role_token_limits.get(model_role, self.cfg.get("chat_max_tokens", 768)),
        }
        if provider == "ollama" and model_name:
            call_options["ollama_model"] = model_name
        elif provider == "llama_cpp" and model_name:
            call_options["llama_cpp_model"] = model_name
        try:
            result = self.model_manager.call(
                provider,
                prompt,
                complexity=task["complexity"],
                token_usage=getattr(prompt, "token_usage", None),
                **call_options,
            )
            result = self._complete_with_memory_tool(provider, prompt, result, call_options)
            self.mem.record_task(task, result, provider=provider, success=True)
            self.mem.add_text(
                f"Tarea: {task.get('prompt', task)}\nResultado: {result}",
                meta={"provider": provider},
                kind="task_result",
            )
            return {"model": provider, "result": result}
        except Exception as exc:
            self.mem.record_audit(skill_name or "agent", request=task, result={"error": str(exc)}, success=False)
            # A remote provider can be temporarily unavailable. Fall back to
            # the local model before returning an error to the user.
            local_provider = (
                self.model_manager.provider
                if self.model_manager.provider in {"ollama", "llama_cpp", "local"}
                else "ollama"
            )
            if provider not in {"ollama", "llama_cpp", "local"} and self.model_manager.available().get(local_provider):
                try:
                    result = self.model_manager.call(
                        local_provider,
                        prompt,
                        complexity=task["complexity"],
                        **(
                            {"ollama_model": model_name}
                            if local_provider == "ollama"
                            else {"llama_cpp_model": model_name}
                        ),
                        timeout=self.cfg.get("model_timeout", 300),
                    )
                    self.mem.record_task(task, result, provider=local_provider, success=True)
                    return {"model": f"{local_provider} (fallback)", "result": result}
                except Exception as fallback_exc:
                    logger.warning("provider_fallback_failed provider=ollama error=%s", fallback_exc)
                    pass
            result = self._safe_error("El proveedor no pudo completar la solicitud.", exc)
            result["provider"] = provider
            self.mem.record_task(task, result, provider=provider, success=False)
            return {"model": provider, "result": result}

    @staticmethod
    def _food_request_has_specific_ingredients(request):
        lowered = str(request or "").lower()
        match = re.search(r"\btengo\s+(.+?)(?:[.!?]|$)", lowered)
        if not match:
            return False
        value = match.group(1).strip()
        generic = {"lo que", "todo lo que", "cosas", "algo", "comida", "hambre", "ganas"}
        return bool(value and not any(value.startswith(prefix) for prefix in generic))

    @staticmethod
    def _fallback_food_advice(request):
        """Return a concise answer when the culinary model is unavailable."""
        lowered = str(request or "").lower()
        match = re.search(r"\btengo\s+(.+?)(?:[.!?]|$)", lowered)
        raw = match.group(1) if match else ""
        ingredients = [
            item.strip(" ,")
            for item in re.split(r",|\s+y\s+", raw)
            if item.strip(" ,") and len(item.strip(" ,").split()) <= 4
        ]
        normalized = " ".join(ingredients)
        allergy_note = " Si sos alérgico a los frutos secos, evitá cualquier fruto seco y revisá etiquetas y contaminación cruzada."
        if "arroz" in normalized and ("huevo" in normalized or "huevos" in normalized):
            tomato = " y tomate" if "tomate" in normalized else ""
            response = (
                f"Hacé un arroz salteado con huevo{tomato}: calentá el arroz, sumá el tomate picado "
                "y terminá con el huevo revuelto en la misma sartén. Como segunda opción, mezclá todo "
                "y hacé una tortilla dorada de ambos lados."
            )
            return response + (allergy_note if re.search(r"al[eé]rg", lowered) and "fruto" in lowered else "")
        if ingredients:
            shown = ", ".join(ingredients[:4])
            response = (
                f"Con {shown}, haría un salteado rápido: cociná primero lo más firme y agregá el resto al final. "
                "Como alternativa, unilo con huevo o una base de arroz/pasta si tenés para hacer una tortilla o bowl."
            )
            return response + (allergy_note if re.search(r"al[eé]rg", lowered) and "fruto" in lowered else "")
        return "Decime qué ingredientes tenés y te propongo una comida concreta y una alternativa rápida."

    def advise_food(self, request):
        """Use the configured model as a culinary advisor with profile context."""
        provider = self.model_manager.choose({"complexity": 4, "privacy": "normal"})
        if not provider:
            return None
        profile = self.mem.knowledge("comidas recetas gustos freezer", limit=2)
        recipes = self.skills.get("food", lambda _: {"recipes": []})(
            {
                "db_path": self.mem.db_path,
                "domain": "recipes",
                "action": "list",
                "config": self.cfg,
            }
        ).get("recipes", [])
        inventory = self.skills.get("food", lambda _: {"items": []})(
            {
                "db_path": self.mem.db_path,
                "domain": "inventory",
                "action": "list",
                "config": self.cfg,
            }
        ).get("items", [])
        inventory_text = ", ".join(
            f"{item.get('item')} ({item.get('quantity', 0)} {item.get('unit') or ''})".strip()
            for item in inventory[:50]
        )
        context = "\n".join(profile)
        if inventory_text:
            context = f"{context}\nINVENTARIO ACTUAL: {inventory_text}".strip()
        catalog = "\n".join(f"- {item.get('name')}" for item in recipes[:30] if item.get("name"))
        recent = self.mem.conversation(limit=12)
        # Previous assistant answers can contain hallucinated steps or menus;
        # only user turns are reliable conversational constraints.
        conversation = "\n".join(f"usuario: {item['text']}" for item in recent if item["role"] == "user")
        template = self.mem.prompt_template("food_advisor")
        prompt = (
            template.replace("{profile}", context)
            .replace("{catalog}", catalog)
            .replace("{conversation}", conversation)
            .replace("{request}", request)
        )
        logger.debug(
            "food advisor request=%r profile_chars=%d catalog_items=%d history_items=%d",
            request,
            len(context),
            len(recipes),
            len(recent),
        )
        try:
            result = self.model_manager.call(
                provider,
                prompt,
                complexity=4,
                temperature=0.25,
                max_tokens=900,
                timeout=self.cfg.get("food_advisor_timeout")
                or min(
                    180,
                    max(5, int(self.cfg.get("chat_timeout_seconds", 900)) - 5),
                ),
                format=self.mem.json_schema("food_reply"),
            )
            decoded = result
            if isinstance(result, str):
                try:
                    decoded = json.loads(result)
                except (TypeError, ValueError):
                    decoded = None
            reply = decoded.get("reply") if isinstance(decoded, dict) else None
            reply = reply or (result if isinstance(result, str) else "")
            logger.info("food advisor provider=%s response_chars=%d", provider, len(str(reply)))
            return reply
        except Exception as exc:
            logger.warning("food advisor failed: %s", exc)
            return None

    def run_skill(self, name, args, confirm=None):
        if not self.capabilities_enabled:
            return {
                "error": "capabilities_disabled",
                "message": "Las capabilities están deshabilitadas; usá una herramienta MCP activa.",
            }
        if name not in self.skills:
            return {"error": f"Skill no disponible: {name}"}
        if name == "mcp" and "servers" not in args:
            args = dict(args)
            args["servers"] = self.cfg.get("mcp_servers", {})
        if name == "analyze_photo" and "config" not in args:
            args = dict(args)
            args["config"] = self.cfg
        if name == "food" and "config" not in args:
            args = dict(args)
            args["config"] = self.cfg
        if name in {"gmail_read", "gmail_send", "gmail_draft", "instagram_publish"} and "config" not in args:
            args = dict(args)
            args["config"] = self.cfg
        if name == "filesystem" and "allowed_roots" not in args:
            configured = self.cfg.get("allowed_roots") or []
            args["allowed_roots"] = configured + [self.cfg.get("photo_root", ""), os.path.expanduser("~/Desktop")]
            args["allowed_roots"] = [item for item in args["allowed_roots"] if item]
        if name == "run_script" and "allowed_commands" not in args:
            args["allowed_commands"] = self.cfg.get("allowed_commands", [])
        if name == "group_files" and "allowed_roots" not in args:
            args["allowed_roots"] = self.cfg.get("allowed_roots") or [os.path.expanduser("~/Desktop")]
        try:
            self.metrics.increment("capability.calls", tags={"name": name})
            started = time.monotonic()
            self.policy.authorize(name, args, confirmed=bool(confirm))
            result = self.skills[name](args)
            self.metrics.observe("capability.duration", time.monotonic() - started, {"name": name})
            if isinstance(result, dict) and result.get("error"):
                self.metrics.increment("capability.errors", tags={"name": name})
            if isinstance(result, dict) and result.get("changed"):
                self.mem.record_audit("operation", request={"skill": name, "args": args}, result=result)
            return result if isinstance(result, dict) else {"result": result}
        except PolicyViolation as exc:
            self.metrics.increment("capability.policy_denials", tags={"name": name})
            if str(exc) == "confirmation_required" and confirm is None:
                return {"error": "confirmation_required", "message": f"La skill '{name}' requiere confirmación."}
            if str(exc) == "confirmation_required" and not confirm:
                return {"cancelled": True, "message": "Operación cancelada por el usuario."}
            return {"error": str(exc), "skill": name}
        except Exception as exc:
            self.metrics.increment("capability.errors", tags={"name": name})
            return {**self._safe_error("La capability no pudo completar la operación.", exc), "skill": name}

    @staticmethod
    def estimate_complexity(text):
        return ComplexityEstimator.estimate(text)

    def teach(self, name, instructions):
        self.mem.add_procedure(name, instructions, meta={"source": "user"})
        return {"saved": True, "name": name}

    def _parse_prompt_rules(self, text):
        lowered = text.lower()
        quoted_path = re.search(r'["“]([^"”]+)["”]', text)
        path_match = re.search(
            r"(?<!\S)(/(?:[^\s]+?\.(?:jpg|jpeg|png|webp|tif|tiff|nef|arw|cr2|dng|raf|orf))|~/(?:[^\s]+?\.(?:jpg|jpeg|png|webp|tif|tiff|nef|arw|cr2|dng|raf|orf))|\./(?:[^\s]+?\.(?:jpg|jpeg|png|webp|tif|tiff|nef|arw|cr2|dng|raf|orf)))(?=\s|$|[.,;:!?])",
            text,
            re.I,
        )
        candidate_path = (
            quoted_path.group(1)
            if quoted_path and ("/" in quoted_path.group(1) or quoted_path.group(1).startswith("~"))
            else (path_match.group(1) if path_match else None)
        )
        # Quoted directories are valid workflow targets too. Without this,
        # photo-batch requests fell through to the slow general router.
        if quoted_path and candidate_path:
            quoted_candidate = Path(os.path.expanduser(candidate_path.strip()))
            if quoted_candidate.is_dir():
                candidate_path = str(quoted_candidate)
        path = os.path.expanduser(candidate_path.strip().rstrip(".,;:!?\"'")) if candidate_path else None
        if not path and is_capability_discussion(text):
            return {"action": "ask", "complexity": self.estimate_complexity(text), "confidence": 0.98}
        if path and Path(path).suffix.lower() in {
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
            ".tif",
            ".tiff",
            ".nef",
            ".arw",
            ".cr2",
            ".dng",
            ".raf",
            ".orf",
        }:
            return {"action": "analyze_photo", "path": path, "photo_name": Path(path).name, "complexity": 5}
        batch_words = (
            "seleccionar fotos",
            "seleccioná fotos",
            "selecciona fotos",
            "seleccioná las fotos",
            "selecciona las fotos",
            "selección de fotos",
            "seleccion de fotos",
            "curar fotos",
            "culling",
        )
        xmp_batch = (
            path
            and "xmp" in lowered
            and any(
                w in lowered
                for w in ("proces", "actualiz", "regener", "analiz", "marc", "repar", "correg", "ráfag", "rafag")
            )
        )
        if (
            any(w in lowered for w in batch_words)
            or xmp_batch
            or ("shortlist" in lowered and ("fotos" in lowered or path))
        ):
            target_match = re.search(r"shortlist\s+(?:de|con|a)?\s*(\d{2,5})", lowered) or re.search(
                r"\b(\d{2,5})\s*(?:fotos|imágenes|imagenes)\b", lowered
            )
            repair_xmp = any(w in lowered for w in ("repar", "correg"))
            return {
                "action": "select_photo_batch",
                "path": path,
                "target": int(target_match.group(1)) if target_match else 300,
                "write_xmp": any(w in lowered for w in ("xmp", "lightroom", "marcar", "etiquetar")) and not repair_xmp,
                "repair_xmp": repair_xmp,
                "mark_bursts": any(w in lowered for w in ("ráfag", "rafag")),
                "complexity": 6,
            }
        if any(
            w in lowered
            for w in ("reporte de mis fotos", "reporte de fotos", "informe de mis fotos", "informe de fotos")
        ):
            return {"action": "lightroom", "lightroom_action": "report", "path": path, "complexity": 3}
        if lowered.startswith("run:") or lowered.startswith(("ejecuta", "execute", "corré", "corre")):
            command = (
                text.split(":", 1)[1].strip()
                if ":" in text
                else text.split(maxsplit=1)[1] if len(text.split()) > 1 else ""
            )
            return {"action": "run", "command": command, "complexity": 2}
        if any(w in lowered for w in ("index", "indexar", "scan", "escanear")):
            return {"action": "index", "path": path, "complexity": 2}
        if any(w in lowered for w in ("inventario", "stock", "despensa")):
            action = "inventory_list"
            if any(w in lowered for w in ("agreg", "sumá", "suma", "cargá", "anotá")):
                action = "inventory_add"
            elif any(w in lowered for w in ("usá", "usa", "consum", "gast")):
                action = "inventory_use"
            return {"action": "food", "domain": "inventory", "food_action": action, "complexity": 3}
        if any(w in lowered for w in ("presupuesto de comida", "presupuesto semanal", "presupuesto mensual")):
            action = (
                "budget_list"
                if any(w in lowered for w in ("cuánto", "cuanto", "ver", "mostrá", "lista"))
                else "budget_set"
            )
            return {"action": "food", "domain": "budget", "food_action": action, "complexity": 3}
        if any(
            w in lowered for w in ("plan semanal", "planificá las comidas", "planifica las comidas", "plan de comidas")
        ):
            action = "plan_list" if any(w in lowered for w in ("ver", "mostrá", "lista")) else "plan_set"
            return {"action": "food", "domain": "planning", "food_action": action, "complexity": 3}
        if any(
            w in lowered
            for w in (
                "analizar foto",
                "analizá foto",
                "analizá la foto",
                "analiza foto",
                "analiza la foto",
                "analizar imagen",
                "analizar la imagen",
                "evaluar foto",
                "evaluar la foto",
                "criticar foto",
                "criticá la foto",
            )
        ) or re.search(
            r"\b(?:analizá|analiza|analizar|evaluá|evalua|evaluar|criticá|critica|criticar)\s+_?dsc\d+", lowered
        ):
            photo_name = None
            name_match = re.search(r"(?<!\w)_?dsc\d+(?:\.(?:nef|arw|cr2|dng|raf|orf|jpg|jpeg|png))?", text, re.I)
            if name_match and not path:
                photo_name = name_match.group(0)
            return {"action": "analyze_photo", "path": path, "photo_name": photo_name, "complexity": 5}
        if any(
            w in lowered
            for w in (
                "listar fotos",
                "lista de fotos",
                "listá mis fotos",
                "listar mis fotos",
                "liste mis fotos",
                "listes mis fotos",
                "fotos",
            )
        ) and any(
            w in lowered for w in ("listar", "lista", "liste", "listes", "mostrar", "mostrá", "ver", "encontrar")
        ):
            return {"action": "list_photos", "path": path, "complexity": 2}
        if (
            re.search(r"list\w*.*carpet", lowered)
            or re.search(r"carpet.*list\w*", lowered)
            or any(w in lowered for w in ("listar directorios", "ver directorios"))
        ):
            return {"action": "list_dirs", "path": path, "complexity": 2}
        if any(w in lowered for w in ("listar archivos", "lista los archivos", "listame los archivos")):
            return {"action": "list_files", "path": path, "complexity": 2}
        if any(
            w in lowered
            for w in (
                "poner todos los archivos",
                "pone todos los archivos",
                "mover todos los archivos",
                "movelas",
                "moverlas",
                "moverlos",
                "pasalas",
                "pasarlos",
                "agrupar los archivos",
                "acomodar los archivos",
                "ordenar los archivos",
                "una sola carpeta",
            )
        ):
            return {"action": "group_files", "path": path, "complexity": 4}
        if (
            any(
                w in lowered
                for w in (
                    "lightroom",
                    "raw",
                    "xmp",
                    "rechazadas",
                    "colecciones",
                    "fotos rechazadas",
                    "base de datos",
                    "sqlite",
                    "estructura de carpetas",
                    "carpetas ordenadas",
                )
            )
            or ("carpet" in lowered and any(w in lowered for w in ("orden", "estructura", "acomod")))
            or re.search(r"\bbd\b", lowered)
            or ("organizar" in lowered and ("fotos" in lowered or "carpetas" in lowered))
        ):
            if ("carpet" in lowered or "estructura" in lowered) and any(
                w in lowered for w in ("orden", "estructura", "organiza", "acomod")
            ):
                return {"action": "lightroom", "lightroom_action": "structure", "path": path, "complexity": 3}
            if any(
                w in lowered
                for w in ("estado", "estadística", "estadistica", "base de datos", "bd", "base sqlite", "resumen")
            ):
                return {"action": "lightroom", "lightroom_action": "status", "path": path, "complexity": 3}
            action = "plan"
            if any(w in lowered for w in ("simul", "plan")):
                action = "plan"
            elif any(w in lowered for w in ("limpiar", "borrar", "eliminar")):
                action = "limpiar"
            elif any(w in lowered for w in ("mover", "organizar")):
                action = "organize"
            return {"action": "lightroom", "lightroom_action": action, "path": path, "complexity": 6}
        if any(w in lowered for w in ("organiza", "organizar", "ordená", "ordenar")):
            return {"action": "organize", "path": path, "complexity": 4}
        if any(w in lowered for w in ("sugerí", "sugerir", "sugerencia", "recomendá")):
            return {"action": "suggest", "path": path, "complexity": 4}
        return {"action": "ask", "complexity": self.estimate_complexity(text)}

    def parse_prompt(self, text, history=None):
        """Parse explicit commands first and route open-ended requests intelligently."""
        parsed = self._parse_prompt_rules(text)
        if parsed.get("action") != "ask":
            return parsed
        if history is None:
            history = " ".join(item.get("text", "") for item in self.mem.conversation(limit=6))
        return self.router.route(text, history=history[-3500:])

    def interactive_loop(self):
        print('ADA activa. Escribí "exit" para salir. Usá /help para ayuda.')
        while self.running:
            try:
                text = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nSaliendo.")
                break
            if not text:
                continue
            if text.lower() in ("exit", "quit", "/exit"):
                break
            if text.lower() in ("hola", "hi", "hello", "buenas", "hey"):
                print("Hola, ¿en qué puedo ayudarte?")
                continue
            if text.startswith("/help"):
                print(
                    "/help | /history [n] | /skills | /models | /teach NOMBRE: instrucciones | /mem list | /lang es|en | /exit"
                )
                continue
            if text.startswith("/models"):
                print(json.dumps(self.model_manager.available(), indent=2, ensure_ascii=False))
                continue
            if text.startswith("/lang "):
                self.lang = text.split(None, 1)[1].strip()
                print("Idioma:", self.lang)
                continue
            if text.startswith("/skills"):
                print("Skills:", ", ".join(sorted(self.skills)) or "(ninguna)")
                continue
            if text.startswith("/history"):
                limit = int(text.split()[1]) if len(text.split()) > 1 else 10
                for item in self.mem.recent_tasks(limit):
                    print(item["task"], "→", item["result"][:300])
                continue
            if text.startswith("/mem list"):
                for item in self.mem.list_procedures():
                    print(f"- {item['name']}: {item['instructions']}")
                continue
            if text.startswith("/teach "):
                body = text[7:]
                if ":" not in body:
                    print("Uso: /teach nombre: instrucciones")
                else:
                    name, instructions = body.split(":", 1)
                    print(self.teach(name, instructions))
                continue

            parsed = self.parse_prompt(text)
            if parsed["action"] == "organize" and parsed.get("path") is None:
                print("Necesito la ruta de la carpeta.")
                continue
            if parsed["action"] == "run":
                answer = input("¿Confirmás ejecutar ese comando? [s/N] ").lower().strip() in (
                    "s",
                    "si",
                    "sí",
                    "y",
                    "yes",
                )
                task = {
                    "type": "run_script",
                    "payload": {"command": parsed.get("command"), "timeout": self.cfg.get("script_timeout", 60)},
                    "complexity": 2,
                    "confirm": answer,
                }
            elif parsed["action"] == "organize":
                answer = input("Esto moverá archivos. ¿Confirmás? [s/N] ").lower().strip() in (
                    "s",
                    "si",
                    "sí",
                    "y",
                    "yes",
                )
                task = {
                    "type": "organize_photos",
                    "payload": {"dir": parsed["path"]},
                    "complexity": 4,
                    "confirm": answer,
                }
            elif parsed["action"] == "analyze_photo":
                if not parsed.get("path"):
                    print("Necesito la ruta de la imagen.")
                    continue
                task = {"type": "analyze_photo", "payload": {"path": parsed["path"]}, "complexity": 5}
            else:
                task = {"prompt": text, "complexity": parsed.get("complexity", 3), "use_memory": True}
            result = self.decide_and_run(task)
            print(
                f"[{result.get('model') or 'sin modelo'}] {json.dumps(result.get('result'), ensure_ascii=False, indent=2) if isinstance(result.get('result'), dict) else result.get('result')}"
            )
