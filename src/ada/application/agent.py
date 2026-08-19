import json
import os
import re
from pathlib import Path

from src.ada.infrastructure.engines.model_manager import ModelManager
from src.ada.infrastructure.persistence.sqlite import Memory
from src.ada.capabilities.registry import load_capabilities
from src.ada.agents import MultiAgentCoordinator
from src.ada.application.router import IntentRouter


class Agent:
    """ADA's general-purpose agent: route, execute tools, report and remember."""

    def __init__(self, cfg=None):
        self.cfg = cfg or {}
        self.model_manager = ModelManager(self.cfg)
        db_path = self.cfg.get("db_path", str(Path(__file__).parent / "memory.db"))
        self.mem = Memory(db_path)
        self.skills = load_capabilities()
        self.coordinator = MultiAgentCoordinator(self.cfg)
        self.router = IntentRouter(self.model_manager, self.cfg)
        self._load_knowledge()
        self.history = []
        self.lang = self.cfg.get("lang", "auto")
        self.running = True

    def _load_knowledge(self):
        for filename in self.cfg.get('knowledge_files', []):
            try:
                path = Path(os.path.expanduser(filename))
                if not path.exists():
                    continue
                marker = f"[ADA knowledge: {path.name}]"
                if not any(marker in item for item in self.mem.knowledge()):
                    self.mem.add_knowledge(path.name, marker + "\n" + path.read_text(encoding='utf-8'), source=str(path))
            except Exception:
                continue

    def _system_prompt(self):
        language = "Responde en español." if self.lang.startswith("es") else ""
        return (
            "Eres ADA, un agente de IA neutral y práctico. Tu modo permanente es AGENTE, no chatbot: "
            "no preguntes al usuario si quiere chat o agente ni ofrezcas elegir entre esos modos. "
            "Interpretá la intención, proponé el siguiente paso concreto y usá las herramientas disponibles "
            "cuando la solicitud corresponda a una acción. No inventes ejecuciones ni resultados. "
            "Si no podés ejecutar una acción, explicá claramente qué falta. Sé breve y claro. " + language
        )

    def decide_and_run(self, task):
        task = dict(task)
        task.setdefault("complexity", self.estimate_complexity(task.get("prompt", "")))
        provider = self.model_manager.choose(task)
        self.history.append({"task": task, "chosen_model": provider})

        skill_name = task.get("type")
        if skill_name == 'analyze_photo':
            payload = dict(task.get('payload', {}))
            payload.setdefault('config', self.cfg)
            result = self.coordinator.run({'workflow': 'photo_review', **payload})
            self.mem.record_task(task, result, provider=provider or 'multi-agent', success=not bool(result.get('error')))
            return {"model": provider or "multi-agent", "result": result}
        if skill_name in self.skills:
            skill_args = dict(task.get("payload", {}))
            if task.get("confirm") is not None:
                skill_args["confirm"] = task.get("confirm")
            result = self.run_skill(skill_name, skill_args, confirm=task.get("confirm"))
            self.mem.record_task(task, result, provider=provider, success=not bool(result.get("error")) if isinstance(result, dict) else True)
            return {"model": provider or "tool", "result": result}

        if not provider:
            result = {"error": "No hay modelos disponibles. Instala/inicia Ollama o configura una API."}
            self.mem.record_task(task, result, success=False)
            return {"model": None, "result": result}

        prompt = self._system_prompt()
        knowledge = self.mem.knowledge(task.get("prompt", ""), limit=2)
        if knowledge:
            prompt += "\nReferencias confiables del proyecto; respetalas y no inventes reglas:\n" + "\n---\n".join(knowledge)
        procedures = self.mem.find_procedures(task.get("prompt", ""))
        if procedures:
            prompt += "\nProcedimientos aprendidos relevantes:\n" + "\n".join(
                f"- {p['name']}: {p['instructions']}" for p in procedures
            )
        prompt += "\nSolicitud del usuario:\n" + (task.get("prompt") or json.dumps(task, ensure_ascii=False))
        try:
            result = self.model_manager.call(provider, prompt, complexity=task["complexity"])
            self.mem.record_task(task, result, provider=provider, success=True)
            self.mem.add_text(
                f"Tarea: {task.get('prompt', task)}\nResultado: {result}",
                meta={"provider": provider}, kind="task_result"
            )
            return {"model": provider, "result": result}
        except Exception as exc:
            # A remote provider can be temporarily unavailable. Fall back to
            # the local model before returning an error to the user.
            if provider != "ollama" and self.model_manager.available().get("ollama"):
                try:
                    result = self.model_manager.call("ollama", prompt, complexity=task["complexity"])
                    self.mem.record_task(task, result, provider="ollama", success=True)
                    return {"model": "ollama (fallback)", "result": result}
                except Exception:
                    pass
            result = {"error": str(exc), "provider": provider}
            self.mem.record_task(task, result, provider=provider, success=False)
            return {"model": provider, "result": result}

    def run_skill(self, name, args, confirm=None):
        if name not in self.skills:
            return {"error": f"Skill no disponible: {name}"}
        if name == 'mcp' and 'servers' not in args:
            args = dict(args)
            args['servers'] = self.cfg.get('mcp_servers', {})
        if name == 'analyze_photo' and 'config' not in args:
            args = dict(args)
            args['config'] = self.cfg
        risky_filesystem = name == 'filesystem' and args.get('action') in {'move_files', 'copy_files', 'mkdir'}
        risky_lightroom = name == 'lightroom' and args.get('action') in {'organize', 'organizar', 'mover', 'limpiar', 'recuperar'}
        risky_mcp = name == 'mcp' and not args.get('list_tools')
        if (name in {"organize_photos", "run_script", "group_files"} or risky_filesystem or risky_lightroom or risky_mcp) and self.cfg.get("confirm_risky", True):
            if confirm is None:
                return {"error": "confirmation_required", "message": f"La skill '{name}' requiere confirmación."}
            if not confirm:
                return {"cancelled": True, "message": "Operación cancelada por el usuario."}
        try:
            result = self.skills[name](args)
            return result if isinstance(result, dict) else {"result": result}
        except Exception as exc:
            return {"error": str(exc), "skill": name}

    @staticmethod
    def estimate_complexity(text):
        value = text.lower()
        if any(word in value for word in ("analizá", "analiza", "analizar", "diseñá", "diseña", "investiga", "complejo", "script nuevo")):
            return 8
        if any(word in value for word in ("adaptá", "adapta", "modifica", "explica", "compará", "compara")):
            return 5
        if any(word in value for word in ("ejecuta", "corré", "corre", "lista", "mostrame", "reporte")):
            return 2
        return 3

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
        candidate_path = quoted_path.group(1) if quoted_path and ("/" in quoted_path.group(1) or quoted_path.group(1).startswith("~")) else (path_match.group(1) if path_match else None)
        # Quoted directories are valid workflow targets too. Without this,
        # photo-batch requests fell through to the slow general router.
        if quoted_path and candidate_path:
            quoted_candidate = Path(os.path.expanduser(candidate_path.strip()))
            if quoted_candidate.is_dir():
                candidate_path = str(quoted_candidate)
        path = os.path.expanduser(candidate_path.strip().rstrip(".,;:!?\"'")) if candidate_path else None
        if path and Path(path).suffix.lower() in {'.jpg', '.jpeg', '.png', '.webp', '.tif', '.tiff', '.nef', '.arw', '.cr2', '.dng', '.raf', '.orf'}:
            return {"action": "analyze_photo", "path": path, "photo_name": Path(path).name, "complexity": 5}
        batch_words = ('seleccionar fotos', 'seleccioná fotos', 'selecciona fotos',
                       'seleccioná las fotos', 'selecciona las fotos',
                       'selección de fotos', 'seleccion de fotos', 'curar fotos', 'culling')
        xmp_batch = path and 'xmp' in lowered and any(w in lowered for w in ('proces', 'actualiz', 'regener', 'analiz', 'marc', 'repar', 'correg', 'ráfag', 'rafag'))
        if (any(w in lowered for w in batch_words) or xmp_batch
                or ('shortlist' in lowered and ('fotos' in lowered or path))):
            target_match = (re.search(r'shortlist\s+(?:de|con|a)?\s*(\d{2,5})', lowered)
                            or re.search(r'\b(\d{2,5})\s*(?:fotos|imágenes|imagenes)\b', lowered))
            repair_xmp = any(w in lowered for w in ('repar', 'correg'))
            return {"action": "select_photo_batch", "path": path, "target": int(target_match.group(1)) if target_match else 300,
                    "write_xmp": any(w in lowered for w in ('xmp', 'lightroom', 'marcar', 'etiquetar')) and not repair_xmp,
                    "repair_xmp": repair_xmp,
                    "mark_bursts": any(w in lowered for w in ('ráfag', 'rafag')), "complexity": 6}
        if any(w in lowered for w in ('reporte de mis fotos', 'reporte de fotos', 'informe de mis fotos', 'informe de fotos')):
            return {'action': 'lightroom', 'lightroom_action': 'report', 'path': path, 'complexity': 3}
        if lowered.startswith("run:") or lowered.startswith(("ejecuta", "execute", "corré", "corre")):
            command = text.split(":", 1)[1].strip() if ":" in text else text.split(maxsplit=1)[1] if len(text.split()) > 1 else ""
            return {"action": "run", "command": command, "complexity": 2}
        if any(w in lowered for w in ("index", "indexar", "scan", "escanear")):
            return {"action": "index", "path": path, "complexity": 2}
        if (any(w in lowered for w in ("analizar foto", "analizá foto", "analizá la foto", "analiza foto", "analiza la foto", "analizar imagen", "analizar la imagen", "evaluar foto", "evaluar la foto", "criticar foto", "criticá la foto"))
                or re.search(r"\b(?:analizá|analiza|analizar|evaluá|evalua|evaluar|criticá|critica|criticar)\s+_?dsc\d+", lowered)):
            photo_name = None
            name_match = re.search(r"(?<!\w)_?dsc\d+(?:\.(?:nef|arw|cr2|dng|raf|orf|jpg|jpeg|png))?", text, re.I)
            if name_match and not path:
                photo_name = name_match.group(0)
            return {"action": "analyze_photo", "path": path, "photo_name": photo_name, "complexity": 5}
        if any(w in lowered for w in ("listar fotos", "lista de fotos", "listá mis fotos", "listar mis fotos", "liste mis fotos", "listes mis fotos", "fotos")) and any(w in lowered for w in ("listar", "lista", "liste", "listes", "mostrar", "mostrá", "ver", "encontrar")):
            return {"action": "list_photos", "path": path, "complexity": 2}
        if (re.search(r"list\w*.*carpet", lowered) or re.search(r"carpet.*list\w*", lowered) or any(w in lowered for w in ("listar directorios", "ver directorios"))):
            return {"action": "list_dirs", "path": path, "complexity": 2}
        if any(w in lowered for w in ("listar archivos", "lista los archivos", "listame los archivos")):
            return {"action": "list_files", "path": path, "complexity": 2}
        if any(w in lowered for w in ("poner todos los archivos", "pone todos los archivos", "mover todos los archivos", "movelas", "moverlas", "moverlos", "pasalas", "pasarlos", "agrupar los archivos", "acomodar los archivos", "ordenar los archivos", "una sola carpeta")):
            return {"action": "group_files", "path": path, "complexity": 4}
        if (any(w in lowered for w in ('lightroom', 'raw', 'xmp', 'rechazadas', 'colecciones', 'fotos rechazadas', 'base de datos', 'sqlite', 'estructura de carpetas', 'carpetas ordenadas'))
                or ('carpet' in lowered and any(w in lowered for w in ('orden', 'estructura', 'acomod')))
                or re.search(r'\bbd\b', lowered)
                or ('organizar' in lowered and ('fotos' in lowered or 'carpetas' in lowered))):
            if ('carpet' in lowered or 'estructura' in lowered) and any(w in lowered for w in ('orden', 'estructura', 'organiza', 'acomod')):
                return {'action': 'lightroom', 'lightroom_action': 'structure', 'path': path, 'complexity': 3}
            if any(w in lowered for w in ('estado', 'estadística', 'estadistica', 'base de datos', 'bd', 'base sqlite', 'resumen')):
                return {'action': 'lightroom', 'lightroom_action': 'status', 'path': path, 'complexity': 3}
            action = 'plan'
            if any(w in lowered for w in ('simul', 'plan')):
                action = 'plan'
            elif any(w in lowered for w in ('limpiar', 'borrar', 'eliminar')):
                action = 'limpiar'
            elif any(w in lowered for w in ('mover', 'organizar')):
                action = 'organize'
            return {'action': 'lightroom', 'lightroom_action': action, 'path': path, 'complexity': 6}
        if any(w in lowered for w in ("organiza", "organizar", "ordená", "ordenar")):
            return {"action": "organize", "path": path, "complexity": 4}
        if any(w in lowered for w in ("sugerí", "sugerir", "sugerencia", "recomendá")):
            return {"action": "suggest", "path": path, "complexity": 4}
        return {"action": "ask", "complexity": self.estimate_complexity(text)}

    def parse_prompt(self, text):
        """Parse explicit commands first and route open-ended requests intelligently."""
        parsed = self._parse_prompt_rules(text)
        if parsed.get("action") != "ask":
            return parsed
        return self.router.route(text, history=" ".join(item.get("text", "") for item in self.mem.conversation(limit=6)))

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
                print("/help | /history [n] | /skills | /models | /teach NOMBRE: instrucciones | /mem list | /lang es|en | /exit")
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
            if parsed["action"] in ("run", "organize") and parsed.get("path") is None and parsed["action"] == "organize":
                print("Necesito la ruta de la carpeta.")
                continue
            if parsed["action"] == "run":
                answer = input("¿Confirmás ejecutar ese comando? [s/N] ").lower().strip() in ("s", "si", "sí", "y", "yes")
                task = {"type": "run_script", "payload": {"command": parsed.get("command"), "timeout": self.cfg.get("script_timeout", 60)}, "complexity": 2, "confirm": answer}
            elif parsed["action"] == "organize":
                answer = input("Esto moverá archivos. ¿Confirmás? [s/N] ").lower().strip() in ("s", "si", "sí", "y", "yes")
                task = {"type": "organize_photos", "payload": {"dir": parsed["path"]}, "complexity": 4, "confirm": answer}
            elif parsed["action"] == "analyze_photo":
                if not parsed.get("path"):
                    print("Necesito la ruta de la imagen.")
                    continue
                task = {"type": "analyze_photo", "payload": {"path": parsed["path"]}, "complexity": 5}
            else:
                task = {"prompt": text, "complexity": parsed.get("complexity", 3), "use_memory": True}
            result = self.decide_and_run(task)
            print(f"[{result.get('model') or 'sin modelo'}] {json.dumps(result.get('result'), ensure_ascii=False, indent=2) if isinstance(result.get('result'), dict) else result.get('result')}")
