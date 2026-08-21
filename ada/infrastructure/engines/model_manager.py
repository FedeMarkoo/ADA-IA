"""Model routing and provider adapters used by ADA.

The local provider is Ollama. Remote providers are optional and are only used
when configured and when the router decides that the task needs them.
"""

import json
import os
import re
import urllib.error
import urllib.request
import time
import threading

from ada.infrastructure.runtime.resources import recommended_threads
from ada.infrastructure.runtime.resources import hardware_profile
from ada.models.catalog import DEFAULT_MODEL_CATALOG

from ada.infrastructure.runtime.ollama import LocalModelRuntime, RuntimeStatus
from ada.infrastructure.observability import Metrics

try:
    from openai import OpenAI
except Exception:  # optional dependency
    OpenAI = None

try:
    from anthropic import Anthropic
except Exception:  # optional dependency
    Anthropic = None

try:
    from gpt4all import GPT4All
except Exception:  # optional dependency
    GPT4All = None


class ModelManager:
    AUTO_MODES = {"light", "hybrid", "turbo"}
    MODEL_ROLES = ("chat", "router", "reasoning", "coding", "tools", "vision")
    MODE_LABELS = {
        "manual": {
            "label": "Manual",
            "description": "Elegís exactamente qué modelo usa cada tarea.",
        },
        "light": {
            "label": "Liviano",
            "description": "Prioriza velocidad, poca RAM y baja temperatura del equipo.",
        },
        "hybrid": {
            "label": "Híbrido",
            "description": "Usa modelos rápidos para lo simple y especialistas para tareas exigentes.",
        },
        "turbo": {
            "label": "Turbo",
            "description": "Elige el modelo más potente que entra con un margen seguro de memoria.",
        },
    }

    def __init__(self, config=None):
        self.config = config or {}
        self.ollama_url = os.environ.get(
            "ADA_OLLAMA_URL", self.config.get("ollama_url", "http://127.0.0.1:11434")
        ).rstrip("/")
        self.openai_key = os.environ.get("OPENAI_API_KEY")
        self.anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        self.local_runtime = LocalModelRuntime(self.config)
        self.provider = self.config.get(
            "engine_provider",
            self.config.get("local_runtime", {}).get("provider", "ollama"),
        )
        self.models = self.config.get("models", {})
        self._gpt4all = None
        self.metrics = Metrics("models")
        self._model_stats = {}
        self._model_stats_lock = threading.RLock()
        self._installed_cache = (0.0, [])

    def reload(self, config=None):
        """Reload model policy at runtime without recreating the agent."""
        if config is not None:
            self.config = dict(config)
        self.ollama_url = os.environ.get(
            "ADA_OLLAMA_URL", self.config.get("ollama_url", "http://127.0.0.1:11434")
        ).rstrip("/")
        self.openai_key = os.environ.get("OPENAI_API_KEY")
        self.anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        self.provider = self.config.get(
            "engine_provider",
            self.config.get("local_runtime", {}).get("provider", "ollama"),
        )
        self.models = self.config.get("models", {})
        self.local_runtime.reload(self.config)
        self._gpt4all = None
        self._installed_cache = (0.0, [])

    def available(self):
        local_available = self._ollama_available() if self.provider == "ollama" else False
        return {
            # `local` is the stable ADA capability; `ollama` is the current
            # implementation so callers can remain backwards compatible.
            "local": local_available,
            "ollama": local_available,
            "openai": bool(OpenAI and self.openai_key),
            "anthropic": bool(Anthropic and self.anthropic_key),
            "gpt4all": self._gpt4all_available(),
        }

    def _model(self, role, legacy_key, default):
        policy = self.effective_policy()
        candidate = policy.get(role)
        if isinstance(candidate, dict):
            candidate = candidate.get("preferred") or (candidate.get("fallbacks") or [None])[0]
        if candidate:
            return candidate
        if role in policy:
            return ""
        return self.models.get(role) or self.config.get(legacy_key, default)

    @staticmethod
    def _parameter_billions(name):
        matches = re.findall(r"(?:^|[:_-])(\d+(?:\.\d+)?)b(?:$|[^a-z])", str(name).lower())
        return float(matches[-1]) if matches else 0.0

    def _catalog_profiles(self):
        """Merge built-in metadata with user catalog entries by model name."""
        merged = {item["name"]: dict(item) for item in DEFAULT_MODEL_CATALOG}
        configured = self.config.get("model_catalog") or []
        if isinstance(configured, dict):
            configured = [dict({"name": name}, **value) for name, value in configured.items()]
        for item in configured:
            if isinstance(item, dict) and item.get("name"):
                merged[item["name"]] = {**merged.get(item["name"], {}), **item}
        return merged

    def _profile_for_model(self, name):
        profile = dict(self._catalog_profiles().get(name, {}))
        params = self._parameter_billions(name)
        lowered = name.lower()
        if not profile:
            if "embed" in lowered:
                roles = ["embedding"]
            elif any(token in lowered for token in ("vision", "-vl", "vl:")):
                roles = ["vision"]
            elif any(token in lowered for token in ("coder", "code")):
                roles = ["coding", "tools", "chat"]
            elif any(token in lowered for token in ("r1", "reason")):
                roles = ["reasoning", "chat"]
            else:
                roles = ["chat"]
                if params and params <= 4:
                    roles.extend(["router", "fast"])
            profile = {
                "name": name,
                "roles": roles,
                "min_ram_gb": max(2.0, round(params * 0.75, 1)) if params else 4.0,
                "quality_tier": "huge" if params >= 24 else "large" if params >= 12 else "medium" if params >= 7 else "small",
                "description": "Modelo instalado detectado automáticamente.",
            }
        profile.setdefault("name", name)
        profile.setdefault("roles", ["chat"])
        profile.setdefault("min_ram_gb", max(2.0, round(params * 0.75, 1)) if params else 4.0)
        profile["parameters_b"] = params
        return profile

    def _installed_model_names(self, force=False):
        cached_at, names = self._installed_cache
        if not force and time.monotonic() - cached_at < 10:
            return list(names)
        names = self.local_runtime.installed_models()
        self._installed_cache = (time.monotonic(), list(names))
        return list(names)

    def installed_model_profiles(self, force=False):
        profile = hardware_profile()
        safe_ram = max(2.0, float(profile.get("ram_gb") or 0) - 2.0)
        result = []
        for name in self._installed_model_names(force=force):
            item = self._profile_for_model(name)
            item["installed"] = True
            item["hardware_fit"] = float(item.get("min_ram_gb", 0) or 0) <= safe_ram
            result.append(item)
        return sorted(result, key=lambda item: (float(item.get("min_ram_gb", 0)), item["name"]))

    @staticmethod
    def _mode_budget(mode, role, profile):
        total = max(4.0, float(profile.get("ram_gb") or 8))
        if role == "router":
            return min(6.0, total - 2.0)
        if mode == "light":
            return min(6.0, total * 0.45)
        if mode == "hybrid":
            return min(10.0, total * 0.70)
        return max(4.0, total - 2.0)

    @staticmethod
    def _role_power(item, role):
        params = float(item.get("parameters_b") or 0)
        roles = set(item.get("roles") or [])
        name = str(item.get("name") or "").lower()
        score = params
        if role == "chat":
            score += 3 if "general" in roles else 0
            score += 3 if "qwen2.5" in name else 0
            score -= 1 if name.startswith("qwen3:") else 0
            score -= 8 if "coder" in name else 0
            score -= 3 if "reasoning" in roles else 0
        elif role == "coding":
            score += 3 if "coder" in name or "coding" in roles else 0
        elif role == "reasoning":
            score += 3 if "reasoning" in roles or "r1" in name else 0
        elif role == "tools":
            score += 4 if "qwen" in name else 0
        return score

    def automatic_policy(self, mode, installed_profiles=None, profile=None):
        """Build a role policy from installed models and a hardware-safe budget."""
        if mode not in self.AUTO_MODES:
            raise ValueError("Modo automático inválido")
        installed = list(installed_profiles if installed_profiles is not None else self.installed_model_profiles())
        profile = profile or hardware_profile()
        policy = {}
        for role in self.MODEL_ROLES:
            budget = self._mode_budget(mode, role, profile)
            candidates = [
                item for item in installed
                if role in set(item.get("roles") or []) and float(item.get("min_ram_gb", 0) or 0) <= budget
            ]
            if role == "router" and not candidates:
                candidates = [
                    item for item in installed
                    if "chat" in set(item.get("roles") or [])
                    and float(item.get("parameters_b") or 0) <= 4
                    and float(item.get("min_ram_gb", 0) or 0) <= budget
                ]
            if mode == "light" or role == "router":
                ordered = sorted(
                    candidates,
                    key=lambda item: (float(item.get("min_ram_gb", 0)), float(item.get("parameters_b", 0)), item["name"]),
                )
            else:
                ordered = sorted(candidates, key=lambda item: (-self._role_power(item, role), item["name"]))
            preferred = ordered[0]["name"] if ordered else None
            fallbacks = [item["name"] for item in ordered[1:4]]
            policy[role] = {"preferred": preferred, "fallbacks": fallbacks}

        # In the light profile, an unavailable specialist deliberately falls
        # back to the smallest chat model instead of loading a much larger one.
        if mode == "light" and policy["chat"]["preferred"]:
            for role in ("reasoning", "coding", "tools"):
                if not policy[role]["preferred"]:
                    policy[role] = {"preferred": policy["chat"]["preferred"], "fallbacks": []}
        return policy

    def effective_policy(self):
        mode = str(self.config.get("model_selection_mode") or "manual").lower()
        if mode in self.AUTO_MODES:
            return self.automatic_policy(mode)
        return self.config.get("model_policy", {})

    @classmethod
    def runtime_settings_for_mode(cls, mode, profile=None):
        profile = profile or hardware_profile()
        cores = max(1, int(profile.get("cpu_cores") or 1))
        settings = {
            "light": {
                "cpu_limit_percent": 50, "ollama_num_thread": min(4, cores), "ollama_num_ctx": 4096,
                "ollama_keep_alive": "2m", "model_timeout": 25, "chat_timeout_seconds": 35, "chat_max_tokens": 384,
            },
            "hybrid": {
                "cpu_limit_percent": 75, "ollama_num_thread": min(6, cores), "ollama_num_ctx": 4096,
                "ollama_keep_alive": "10m", "model_timeout": 50, "chat_timeout_seconds": 65, "chat_max_tokens": 768,
            },
            "turbo": {
                "cpu_limit_percent": 100, "ollama_num_thread": cores, "ollama_num_ctx": 8192,
                "ollama_keep_alive": "30m", "model_timeout": 90, "chat_timeout_seconds": 110, "chat_max_tokens": 1200,
            },
        }
        return dict(settings.get(mode, {}))

    def selection_summary(self):
        mode = str(self.config.get("model_selection_mode") or "manual").lower()
        policy = self.effective_policy()
        installed = self.installed_model_profiles()
        hardware = hardware_profile()
        warnings = []
        installed_names = {item["name"] for item in installed}
        vision_model = policy.get("vision", {}).get("preferred")
        if not vision_model or vision_model not in installed_names:
            warnings.append("No hay un modelo de visión instalado; las fotos no podrán analizarse con IA visual.")
        for role, assignment in policy.items():
            preferred = assignment.get("preferred") if isinstance(assignment, dict) else assignment
            if preferred and preferred not in installed_names and role != "vision":
                warnings.append(f"El modelo asignado a {role} no está descargado: {preferred}.")
        return {
            "mode": mode,
            "automatic": mode in self.AUTO_MODES,
            "modes": self.MODE_LABELS,
            "policy": policy,
            "active": {role: (policy.get(role) or {}).get("preferred") for role in self.MODEL_ROLES},
            "installed": installed,
            "hardware": hardware,
            "runtime_settings": self.runtime_settings_for_mode(mode),
            "mode_previews": {
                candidate: self.automatic_policy(candidate, installed_profiles=installed, profile=hardware)
                for candidate in sorted(self.AUTO_MODES)
            },
            "runtime_presets": {
                candidate: self.runtime_settings_for_mode(candidate, hardware)
                for candidate in sorted(self.AUTO_MODES)
            },
            "warnings": warnings,
        }

    def model_catalog(self):
        """Return the declarative model catalog filtered by the current hardware."""
        profile = hardware_profile()
        catalog = self.config.get("model_catalog") or []
        if isinstance(catalog, dict):
            catalog = [dict({"name": name}, **value) for name, value in catalog.items()]
        result = []
        for item in catalog:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            minimum = item.get("min_ram_gb", 0)
            if profile["ram_gb"] and profile["ram_gb"] < float(minimum):
                continue
            minimum_vram = float(item.get("min_vram_gb", 0) or 0)
            if minimum_vram and profile["vram_gb"] < minimum_vram:
                continue
            minimum_disk = float(item.get("min_disk_free_gb", 0) or 0)
            if minimum_disk and profile["disk_free_gb"] < minimum_disk:
                continue
            result.append(dict(item, hardware_tier=profile["tier"]))
        return result

    def _model_candidates(self, task, role="chat"):
        task_name = task if isinstance(task, str) else (task.get("task") or task.get("type") or task.get("model_role"))
        policy = self.effective_policy()
        configured = policy.get(task_name) or policy.get(role)
        names = []
        if isinstance(configured, str):
            names = [configured]
        elif isinstance(configured, dict):
            names = [configured.get("preferred")] + list(configured.get("fallbacks") or [])
        if not names:
            names = [self._model(role, f"{role}_model", self.models.get(role, ""))]
        return [name for name in names if name]

    def select_model(self, task, role="chat"):
        """Select a hardware-compatible model name from the runtime policy."""
        names = self._model_candidates(task, role)
        names = self._adaptive_order(names)
        installed = set(self._installed_model_names()) if self.provider == "ollama" else set()
        for name in names:
            if name and (not installed or name in installed):
                return name
        return names[0] if names else ""

    @staticmethod
    def role_for_task(task):
        explicit = task.get("model_role")
        if explicit:
            return explicit
        prompt = str(task.get("prompt") or "").lower()
        if any(word in prompt for word in ("código", "codigo", "program", "python", "javascript", "refactor", "debug")):
            return "coding"
        if int(task.get("complexity", 3) or 3) >= 7:
            return "reasoning"
        return "chat"

    def _adaptive_order(self, names):
        """Rank models with observed performance while preserving cold-start order."""
        if not self.config.get("adaptive_models") or len(names) < 2:
            return names
        with self._model_stats_lock:
            stats = {name: dict(self._model_stats.get(name, {})) for name in names}
        measured = [item for item in stats.values() if item.get("calls")]
        if not measured:
            return names
        best_average = min(item["seconds"] / item["calls"] for item in measured)

        def score(index_name):
            index, name = index_name
            item = stats[name]
            calls = item.get("calls", 0)
            if not calls:
                # A cold candidate gets a small exploration allowance instead
                # of permanently losing to the first configured model.
                return best_average * 1.25, index
            error_rate = item.get("errors", 0) / calls
            return (item["seconds"] / calls) * (1.0 + error_rate * 3.0), index

        return [name for _, name in sorted(enumerate(names), key=score)]

    def _record_model_stat(self, model_tag, duration, error=False):
        with self._model_stats_lock:
            item = self._model_stats.setdefault(model_tag, {"calls": 0, "errors": 0, "seconds": 0.0})
            item["calls"] += 1
            item["seconds"] += duration
            if error:
                item["errors"] += 1

    def ensure_model(self, task, role="chat"):
        """Ensure the selected local model is installed or use an installed fallback."""
        selected = self.select_model(task, role)
        if self.provider != "ollama" or not selected:
            return selected
        status = self.local_runtime.ensure_models([selected])
        if status.get("ready"):
            return selected
        installed = set(status.get("installed", []))
        for candidate in self._model_candidates(task, role):
            if candidate in installed:
                return candidate
        return selected

    def model_recommendations(self):
        """Expose task policy, hardware filtering and provider telemetry together."""
        roles = set(self.MODEL_ROLES) | set(self.models) | set(self.effective_policy())
        return {
            "mode": str(self.config.get("model_selection_mode") or "manual").lower(),
            "adaptive": bool(self.config.get("adaptive_models", False)),
            "roles": {role: self.select_model(role, role=role) for role in sorted(roles)},
            "model_stats": self.model_stats(),
            "telemetry": self.metrics.snapshot(),
        }

    def model_stats(self):
        with self._model_stats_lock:
            return {name: dict(values) for name, values in self._model_stats.items()}

    def _gpt4all_available(self):
        if GPT4All is None:
            return False
        settings = self.config.get("gpt4all", {})
        return bool(settings.get("model_name") and settings.get("model_path"))

    def _ollama_available(self):
        return self.local_runtime.ensure_ready().available

    def runtime_status(self):
        """Expose runtime and installed-model state for the UI and diagnostics."""
        status = (
            self.local_runtime.ensure_ready()
            if self.provider == "ollama"
            else {
                "provider": self.provider,
                "endpoint": "configured locally",
                "available": self.available().get(self.provider, False),
                "managed": False,
                "reason": "ready" if self.available().get(self.provider, False) else "provider_unavailable",
            }
        )
        if self.provider == "ollama":
            status_available = status.available if isinstance(status, RuntimeStatus) else bool(status.get("available"))
            models = (
                self.local_runtime.ensure_models(
                    [
                        self._model("chat", "ollama_model", "llama3.2:3b"),
                        self._model("vision", "vision_model", "qwen2.5vl:3b"),
                        self._model("router", "router_model", "llama3.2:3b"),
                    ]
                )
                if status_available
                else {"ready": False, "installed": [], "missing": []}
            )
        else:
            models = {"ready": self.available().get(self.provider, False), "installed": [], "missing": []}
        status_payload = status.as_dict() if hasattr(status, "as_dict") else status
        return {"status": status_payload, "models": models}

    def choose(self, task):
        """Choose a provider using complexity, privacy and explicit preferences."""
        available = self.available()
        requested_value = task.get("model") or task.get("model_hint") or self.config.get("model_hint")
        requested = str(requested_value) if requested_value else None
        if requested == "local":
            requested = "ollama"
        elif requested == "chatgpt":
            requested = "openai"
        elif requested == "claude":
            requested = "anthropic"
        if requested in available and available[requested]:
            return requested

        complexity = max(1, min(10, int(task.get("complexity", 3))))
        privacy = task.get("privacy", self.config.get("privacy_default", "normal"))
        if self.provider in available and available[self.provider]:
            return self.provider
        if privacy == "high" and available.get(self.provider):
            return self.provider
        if complexity <= int(self.config.get("local_max_complexity", 5)) and available.get(self.provider):
            return self.provider
        priority = [
            {"local": "ollama", "chatgpt": "openai", "claude": "anthropic"}.get(item, item)
            for item in self.config.get("engine_priority", ["openai", "anthropic", "ollama"])
        ]
        if complexity >= 7:
            for provider in priority:
                if available.get(provider, False):
                    return provider
        for provider in priority:
            if available.get(provider, False):
                return provider
        return None

    def call(self, provider, prompt, **kwargs):
        started = time.monotonic()
        model_tag = kwargs.get("ollama_model") or kwargs.get(f"{provider}_model") or "default"
        tags = {"provider": provider, "model": model_tag}
        self.metrics.increment("provider.calls", tags=tags)
        failed = False
        try:
            if provider == "ollama":
                return self._call_ollama(prompt, **kwargs)
            if provider == "openai":
                return self._call_openai(prompt, **kwargs)
            if provider == "anthropic":
                return self._call_anthropic(prompt, **kwargs)
            if provider == "gpt4all":
                return self._call_gpt4all(prompt, **kwargs)
            raise RuntimeError("No hay un proveedor de modelos disponible: %s" % provider)
        except Exception:
            failed = True
            self.metrics.increment("provider.errors", tags=tags)
            raise
        finally:
            duration = time.monotonic() - started
            self._record_model_stat(model_tag, duration, error=failed)
            self.metrics.observe("provider.duration", duration, tags)

    def call_vision(self, provider, prompt, image_base64, **kwargs):
        if provider != "ollama":
            raise RuntimeError("El proveedor configurado no ofrece análisis visual compatible")
        return self._call_ollama_vision(prompt, image_base64, **kwargs)

    def _call_ollama(self, prompt, **kwargs):
        model = kwargs.get("ollama_model") or self._model("chat", "ollama_model", "llama3.2:3b")
        options = {
            "temperature": kwargs.get("temperature", float(self.config.get("ollama_temperature", 0.2))),
            "num_thread": kwargs.get("num_thread", recommended_threads(self.config)),
        }
        if "num_ctx" in kwargs:
            options["num_ctx"] = int(kwargs["num_ctx"])
        elif self.config.get("ollama_num_ctx"):
            options["num_ctx"] = int(self.config["ollama_num_ctx"])
        if kwargs.get("max_tokens"):
            options["num_predict"] = int(kwargs["max_tokens"])

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": options,
            "keep_alive": kwargs.get("keep_alive", self.config.get("ollama_keep_alive", "5m")),
        }
        # Ollama accepts a JSON schema here and constrains the model output.
        # This is stronger than asking for JSON in the natural-language prompt.
        if kwargs.get("format"):
            payload["format"] = kwargs["format"]
        request_body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.ollama_url + "/api/chat",
            data=request_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=kwargs.get("timeout", 180)) as response:
                data = json.loads(response.read().decode("utf-8"))
            return data.get("message", {}).get("content", "").strip()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError("Ollama devolvió un error: %s" % detail) from exc

    def _call_ollama_vision(self, prompt, image_base64, **kwargs):
        model = kwargs.get("ollama_model") or self._model("vision", "vision_model", "qwen2.5vl:3b")
        options = {
            "temperature": kwargs.get("temperature", float(self.config.get("ollama_temperature", 0.1))),
            "num_thread": kwargs.get("num_thread", recommended_threads(self.config)),
        }
        if "num_ctx" in kwargs:
            options["num_ctx"] = int(kwargs["num_ctx"])
        elif self.config.get("ollama_num_ctx"):
            options["num_ctx"] = int(self.config["ollama_num_ctx"])

        payload = json.dumps(
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt, "images": [image_base64]}],
                "stream": False,
                "format": "json",
                "options": options,
                "keep_alive": kwargs.get("keep_alive", self.config.get("ollama_keep_alive", "5m")),
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            self.ollama_url + "/api/chat", data=payload, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=kwargs.get("timeout", 180)) as response:
                data = json.loads(response.read().decode("utf-8"))
            return data.get("message", {}).get("content", "").strip()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError("Ollama devolvió un error visual: %s" % detail) from exc

    def _call_openai(self, prompt, **kwargs):
        client = OpenAI(api_key=self.openai_key)
        response = client.chat.completions.create(
            model=kwargs.get("openai_model", self.config.get("openai_model", "gpt-4o-mini")),
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", 0.2),
            max_tokens=kwargs.get("max_tokens", 1024),
        )
        return response.choices[0].message.content or ""

    def _call_anthropic(self, prompt, **kwargs):
        client = Anthropic(api_key=self.anthropic_key)
        response = client.messages.create(
            model=kwargs.get("anthropic_model", self.config.get("anthropic_model", "claude-3-5-sonnet-latest")),
            max_tokens=kwargs.get("max_tokens", 1024),
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(getattr(block, "text", "") for block in response.content)

    def _call_gpt4all(self, prompt, **kwargs):
        if GPT4All is None:
            raise RuntimeError("El proveedor configurado no está instalado")
        settings = self.config.get("gpt4all", {})
        if self._gpt4all is None:
            self._gpt4all = GPT4All(
                settings["model_name"],
                model_path=settings["model_path"],
                allow_download=False,
                device=settings.get("device", "cpu"),
            )
        with self._gpt4all.chat_session():
            return self._gpt4all.generate(
                prompt,
                max_tokens=kwargs.get("max_tokens", 1024),
                temp=kwargs.get("temperature", 0.2),
                n_threads=kwargs.get("num_thread", recommended_threads(self.config)),
            )
