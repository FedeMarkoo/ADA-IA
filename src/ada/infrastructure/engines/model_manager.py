"""Model routing and provider adapters used by ADA.

The local provider is Ollama. Remote providers are optional and are only used
when configured and when the router decides that the task needs them.
"""
import json
import os
import urllib.error
import urllib.request

from src.ada.infrastructure.runtime.resources import recommended_threads

from src.ada.infrastructure.runtime.ollama import LocalModelRuntime

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
        return self.models.get(role) or self.config.get(legacy_key, default)

    def _gpt4all_available(self):
        if GPT4All is None:
            return False
        settings = self.config.get("gpt4all", {})
        return bool(settings.get("model_name") and settings.get("model_path"))

    def _ollama_available(self):
        return self.local_runtime.ensure_ready().available

    def runtime_status(self):
        """Expose runtime and installed-model state for the UI and diagnostics."""
        status = self.local_runtime.ensure_ready() if self.provider == "ollama" else {
            "provider": self.provider,
            "endpoint": "configured locally",
            "available": self.available().get(self.provider, False),
            "managed": False,
            "reason": "ready" if self.available().get(self.provider, False) else "provider_unavailable",
        }
        if self.provider == "ollama":
            models = self.local_runtime.ensure_models([
                self._model("chat", "ollama_model", "llama3.2:3b"),
                self._model("vision", "vision_model", "qwen2.5vl:3b"),
                self._model("router", "router_model", "llama3.2:3b"),
            ]) if status.available else {"ready": False, "installed": [], "missing": []}
        else:
            models = {"ready": self.available().get(self.provider, False), "installed": [], "missing": []}
        return {"status": status.as_dict() if hasattr(status, "as_dict") else status, "models": models}

    def choose(self, task):
        """Choose a provider using complexity, privacy and explicit preferences."""
        available = self.available()
        requested = task.get("model") or task.get("model_hint") or self.config.get("model_hint")
        requested = {"local": "ollama", "ollama": "ollama", "chatgpt": "openai", "claude": "anthropic"}.get(requested, requested)
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
        if provider == "ollama":
            return self._call_ollama(prompt, **kwargs)
        if provider == "openai":
            return self._call_openai(prompt, **kwargs)
        if provider == "anthropic":
            return self._call_anthropic(prompt, **kwargs)
        if provider == "gpt4all":
            return self._call_gpt4all(prompt, **kwargs)
        raise RuntimeError("No hay un proveedor de modelos disponible: %s" % provider)

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
        }
        # Ollama accepts a JSON schema here and constrains the model output.
        # This is stronger than asking for JSON in the natural-language prompt.
        if kwargs.get('format'):
            payload['format'] = kwargs['format']
        payload = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.ollama_url + "/api/chat", data=payload,
            headers={"Content-Type": "application/json"}, method="POST"
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
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt, "images": [image_base64]}],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": kwargs.get("temperature", 0.1),
                "num_thread": kwargs.get("num_thread", recommended_threads(self.config)),
            },
        }).encode("utf-8")
        request = urllib.request.Request(self.ollama_url + "/api/chat", data=payload,
                                         headers={"Content-Type": "application/json"}, method="POST")
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
