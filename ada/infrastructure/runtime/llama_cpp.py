"""Lifecycle manager for the standalone llama.cpp HTTP server."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request


@dataclass
class LlamaCppStatus:
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


class LlamaCppRuntime:
    """Start and monitor llama-server without embedding inference in ADA."""

    def __init__(self, config=None):
        self.config = config or {}
        self._process = None
        self._lock = threading.RLock()
        self.reload(self.config)

    def reload(self, config=None):
        if config is not None:
            self.config = dict(config)
        runtime = self.config.get("local_runtime", {})
        self.provider = "llama_cpp"
        self.endpoint = os.environ.get(
            "ADA_LLAMA_CPP_URL",
            runtime.get("url", "http://127.0.0.1:8080"),
        ).rstrip("/")
        self.port = int(runtime.get("port", 8080))
        self.host = str(runtime.get("host", "127.0.0.1"))
        self.model_path = os.path.expanduser(str(runtime.get("model_path", "")))
        self.model_alias = str(runtime.get("model_alias", Path(self.model_path).stem or "ada-local"))
        self.mmproj_path = os.path.expanduser(str(runtime.get("mmproj_path", "")))
        self.auto_start = bool(runtime.get("auto_start", True))
        self.startup_timeout = float(runtime.get("startup_timeout", 30))
        configured_binary = runtime.get("binary") or os.environ.get("ADA_LLAMA_SERVER_BIN")
        self.binary = configured_binary or shutil.which("llama-server") or shutil.which("llama_server")

    def _healthy(self):
        try:
            with urllib.request.urlopen(self.endpoint + "/health", timeout=1.5) as response:
                return response.status == 200
        except (OSError, urllib.error.URLError):
            return False

    def status(self):
        if self._healthy():
            return LlamaCppStatus(self.provider, self.endpoint, True, self._process is not None, "ready")
        if not self.binary:
            reason = "llama_server_not_installed"
        elif not self.model_path:
            reason = "model_path_not_configured"
        elif not Path(self.model_path).is_file():
            reason = "model_file_not_found"
        else:
            reason = "not_running"
        return LlamaCppStatus(self.provider, self.endpoint, False, self._process is not None, reason)

    def start(self):
        with self._lock:
            if self._healthy():
                return self.status()
            if not self.binary:
                return self.status()
            if not self.model_path or not Path(self.model_path).is_file():
                return self.status()
            command = [
                self.binary,
                "-m", self.model_path,
                "--alias", self.model_alias,
                "--host", self.host,
                "--port", str(self.port),
                "--metrics",
                "--slots",
            ]
            ctx = self.config.get("llama_cpp_context") or self.config.get("ollama_num_ctx")
            if ctx:
                command.extend(["-c", str(int(ctx))])
            threads = self.config.get("llama_cpp_threads")
            if threads:
                command.extend(["-t", str(int(threads))])
            if self.mmproj_path and Path(self.mmproj_path).is_file():
                command.extend(["--mmproj", self.mmproj_path])
            try:
                self._process = subprocess.Popen(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            except OSError as exc:
                return LlamaCppStatus(self.provider, self.endpoint, False, False, f"start_failed: {exc}")
            deadline = time.monotonic() + self.startup_timeout
            while time.monotonic() < deadline:
                if self._healthy():
                    return self.status()
                if self._process.poll() is not None:
                    return LlamaCppStatus(self.provider, self.endpoint, False, False, "process_exited")
                time.sleep(0.25)
            return LlamaCppStatus(self.provider, self.endpoint, False, True, "startup_timeout")

    def stop(self):
        with self._lock:
            if self._process and self._process.poll() is None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait(timeout=5)
                self._process = None
            return LlamaCppStatus(self.provider, self.endpoint, self._healthy(), False, "stopped")

    def restart(self):
        self.stop()
        return self.start()

    def ensure_ready(self):
        with self._lock:
            status = self.status()
            if status.available or not self.auto_start:
                return status
            return self.start()

    def installed_models(self):
        return [self.model_alias] if self.model_path and Path(self.model_path).is_file() else []

    def ensure_models(self, models):
        installed = self.installed_models()
        selected = [model for model in models if model]
        missing = [] if selected and self.model_alias in selected else selected
        return {"ready": not missing, "installed": installed, "missing": missing, "pulled": [], "auto_pull": False}

    def pull_model(self, model):
        return False

