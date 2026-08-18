"""Model routing and provider adapters used by ADA.

The local provider is Ollama. Remote providers are optional and are only used
when configured and when the router decides that the task needs them.
"""
import json
import os
import urllib.error
import urllib.request

from runtime import LocalModelRuntime

try:
    from openai import OpenAI
except Exception:  # optional dependency
    OpenAI = None

try:
    from anthropic import Anthropic
except Exception:  # optional dependency
    Anthropic = None


class ModelManager:
    def __init__(self, config=None):
        self.config = config or {}
        self.ollama_url = os.environ.get(
            "ADA_OLLAMA_URL", self.config.get("ollama_url", "http://127.0.0.1:11434")
        ).rstrip("/")
        self.openai_key = os.environ.get("OPENAI_API_KEY")
        self.anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        self.local_runtime = LocalModelRuntime(self.config)

    def available(self):
        local_available = self._ollama_available()
        return {
            # `local` is the stable ADA capability; `ollama` is the current
            # implementation so callers can remain backwards compatible.
            "local": local_available,
            "ollama": local_available,
            "openai": bool(OpenAI and self.openai_key),
            "anthropic": bool(Anthropic and self.anthropic_key),
        }

    def _ollama_available(self):
        return self.local_runtime.ensure_ready().available

    def runtime_status(self):
        """Expose runtime and installed-model state for the UI and diagnostics."""
        status = self.local_runtime.ensure_ready()
        models = self.local_runtime.ensure_models([
            self.config.get("ollama_model", "llama3.2:3b"),
            self.config.get("vision_model", "qwen2.5vl:3b"),
        ]) if status.available else {"ready": False, "installed": [], "missing": []}
        return {"status": status.as_dict(), "models": models}

    def choose(self, task):
        """Choose a provider using complexity, privacy and explicit preferences."""
        available = self.available()
        requested = task.get("model") or task.get("model_hint") or self.config.get("model_hint")
        requested = {"local": "ollama", "ollama": "ollama", "chatgpt": "openai", "claude": "anthropic"}.get(requested, requested)
        if requested in available and available[requested]:
            return requested

        complexity = max(1, min(10, int(task.get("complexity", 3))))
        privacy = task.get("privacy", self.config.get("privacy_default", "normal"))
        if privacy == "high" and available["ollama"]:
            return "ollama"
        if complexity <= int(self.config.get("local_max_complexity", 5)) and available["ollama"]:
            return "ollama"
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
        raise RuntimeError("No hay un proveedor de modelos disponible: %s" % provider)

    def call_vision(self, provider, prompt, image_base64, **kwargs):
        if provider != "ollama":
            raise RuntimeError("El análisis visual local está configurado para Ollama")
        return self._call_ollama_vision(prompt, image_base64, **kwargs)

    def _call_ollama(self, prompt, **kwargs):
        model = kwargs.get("ollama_model") or self.config.get("ollama_model", "llama3.2:3b")
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": kwargs.get("temperature", 0.2)},
        }).encode("utf-8")
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
        model = kwargs.get("ollama_model") or self.config.get("vision_model", "qwen2.5vl:3b")
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt, "images": [image_base64]}],
            "stream": False,
            "format": "json",
            "options": {"temperature": kwargs.get("temperature", 0.1)},
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
