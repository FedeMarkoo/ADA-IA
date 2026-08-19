"""Model routing and provider adapters used by ADA.

The local provider is Ollama. Remote providers are optional and are only used
when configured and when the router decides that the task needs them.
"""

import json
import os
import urllib.error
import urllib.request
import time

from ada.infrastructure.runtime.resources import recommended_threads
from ada.infrastructure.runtime.resources import hardware_profile

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

    def reload(self, config=None):
        """Reload model policy at runtime without recreating the agent."""
        if config is not None:
            self.config = dict(config)
        self.models = self.config.get("models", {})
        self.local_runtime.config = self.config

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
        policy = self.config.get("model_policy", {})
        candidate = policy.get(role)
        if isinstance(candidate, dict):
            candidate = candidate.get("preferred") or (candidate.get("fallbacks") or [None])[0]
        if candidate:
            return candidate
        return self.models.get(role) or self.config.get(legacy_key, default)

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

    def select_model(self, task, role="chat"):
        """Select a model name from policy/catalog without requiring code changes."""
        policy = self.config.get("model_policy", {})
        configured = policy.get(task) or policy.get(role)
        names = []
        if isinstance(configured, str):
            names = [configured]
        elif isinstance(configured, dict):
            names = [configured.get("preferred")] + list(configured.get("fallbacks") or [])
        available = {item["name"] for item in self.model_catalog()}
        for name in names:
            if name and (not available or name in available):
                return name
        return self._model(role, f"{role}_model", self.models.get(role, ""))

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
        self.metrics.increment("provider.calls", tags={"provider": provider})
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
            self.metrics.increment("provider.errors", tags={"provider": provider})
            raise
        finally:
            self.metrics.observe("provider.duration", time.monotonic() - started, {"provider": provider})

    def call_vision(self, provider, prompt, image_base64, **kwargs):
        if provider != "ollama":
            raise RuntimeError("El proveedor configurado no ofrece análisis visual compatible")
        return self._call_ollama_vision(prompt, image_base64, **kwargs)

    def _call_ollama(self, prompt, **kwargs):
        model = kwargs.get("ollama_model") or self._model("chat", "ollama_model", "llama3.2:3b")
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.2),
                "num_thread": kwargs.get("num_thread", recommended_threads(self.config)),
            },
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
        payload = json.dumps(
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt, "images": [image_base64]}],
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": kwargs.get("temperature", 0.1),
                    "num_thread": kwargs.get("num_thread", recommended_threads(self.config)),
                },
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
