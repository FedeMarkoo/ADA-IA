"""Local model runtime lifecycle managed by ADA.

ADA treats Ollama as an implementation detail of its local engine.  This
module starts it when needed, waits for readiness, and never stops a process
that ADA did not start itself.
"""

from dataclasses import dataclass
import json
import os
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request


@dataclass
class RuntimeStatus:
    provider: str
    endpoint: str
    available: bool
    managed: bool = False
    reason: str = ""

    def as_dict(self):
        return {
            "provider": self.provider,
            "endpoint": self.endpoint,
            "available": self.available,
            "managed": self.managed,
            "reason": self.reason,
        }


class LocalModelRuntime:
    """Own the lifecycle of ADA's local inference service."""

    def __init__(self, config=None):
        self.config = config or {}
        self._process = None
        self._lock = threading.Lock()
        self.reload(self.config)

    def reload(self, config=None):
        """Refresh runtime settings without touching a process already owned by ADA."""
        if config is not None:
            self.config = dict(config)
        runtime = self.config.get("local_runtime", {})
        self.provider = runtime.get("provider", "ollama")
        self.endpoint = os.environ.get(
            "ADA_OLLAMA_URL",
            runtime.get("url", self.config.get("ollama_url", "http://127.0.0.1:11434")),
        ).rstrip("/")
        self.auto_start = bool(runtime.get("auto_start", True))
        self.startup_timeout = float(runtime.get("startup_timeout", 12))
        configured_binary = runtime.get("binary") or os.environ.get("ADA_OLLAMA_BIN")
        self.binary = configured_binary or shutil.which("ollama")

    def _healthy(self):
        try:
            with urllib.request.urlopen(self.endpoint + "/api/tags", timeout=1.5) as response:
                return response.status == 200
        except (OSError, urllib.error.URLError):
            return False

    def status(self):
        if self._healthy():
            return RuntimeStatus(self.provider, self.endpoint, True, self._process is not None, "ready")
        reason = "not_running" if self.binary else "ollama_not_installed"
        return RuntimeStatus(self.provider, self.endpoint, False, self._process is not None, reason)

    def start(self):
        """Explicitly start Ollama service."""
        with self._lock:
            if self._healthy():
                return RuntimeStatus(self.provider, self.endpoint, True, self._process is not None, "already_running")
            if not self.binary:
                return RuntimeStatus(self.provider, self.endpoint, False, False, "ollama_not_installed")
            try:
                env = os.environ.copy()
                host = self.endpoint.removeprefix("http://").removeprefix("https://")
                env.setdefault("OLLAMA_HOST", host)
                self._process = subprocess.Popen(
                    [self.binary, "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=env,
                    start_new_session=True,
                )
            except OSError as exc:
                return RuntimeStatus(self.provider, self.endpoint, False, False, f"start_failed: {exc}")

            deadline = time.monotonic() + self.startup_timeout
            while time.monotonic() < deadline:
                if self._healthy():
                    return RuntimeStatus(self.provider, self.endpoint, True, True, "started_by_ada")
                if self._process.poll() is not None:
                    return RuntimeStatus(self.provider, self.endpoint, False, False, "process_exited")
                time.sleep(0.25)
            return RuntimeStatus(self.provider, self.endpoint, False, True, "startup_timeout")

    def stop(self):
        """Explicitly stop the Ollama service."""
        with self._lock:
            if self._process and self._process.poll() is None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait(timeout=3)
                self._process = None
            else:
                try:
                    subprocess.run(["pkill", "-f", "ollama serve"], capture_output=True, timeout=3)
                except Exception:
                    pass
            time.sleep(0.5)
            healthy = self._healthy()
            return RuntimeStatus(self.provider, self.endpoint, healthy, False, "stopped" if not healthy else "still_running")

    def restart(self):
        """Explicitly restart the Ollama service."""
        self.stop()
        time.sleep(0.5)
        return self.start()

    def ensure_ready(self):
        """Return status, starting the local runtime if configured to do so."""
        with self._lock:
            status = self.status()
            if status.available or not self.auto_start:
                return status
            return self.start()

    def installed_models(self):
        if not self.ensure_ready().available:
            return []
        try:
            with urllib.request.urlopen(self.endpoint + "/api/tags", timeout=2) as response:
                data = json.loads(response.read().decode("utf-8"))
            return [item.get("name") for item in data.get("models", []) if item.get("name")]
        except (OSError, ValueError, urllib.error.URLError):
            return []

    def ensure_models(self, models):
        """Report model readiness; optional pulling is explicit to avoid surprise downloads."""
        installed = set(self.installed_models())
        missing = [model for model in models if model and model not in installed]
        pulled = []
        if missing and bool(self.config.get("local_runtime", {}).get("auto_pull", False)):
            for model in missing:
                if self.pull_model(model):
                    pulled.append(model)
            installed.update(pulled)
            missing = [model for model in missing if model not in pulled]
        return {
            "ready": not missing,
            "installed": sorted(installed),
            "missing": missing,
            "pulled": pulled,
            "auto_pull": bool(self.config.get("local_runtime", {}).get("auto_pull", False)),
        }

    def pull_model(self, model):
        try:
            payload = json.dumps({"name": model, "stream": False}).encode("utf-8")
            request = urllib.request.Request(
                self.endpoint + "/api/pull", data=payload, headers={"Content-Type": "application/json"}, method="POST"
            )
            with urllib.request.urlopen(
                request, timeout=float(self.config.get("model_pull_timeout", 1800))
            ) as response:
                return response.status == 200
        except (OSError, ValueError, urllib.error.URLError):
            return False
