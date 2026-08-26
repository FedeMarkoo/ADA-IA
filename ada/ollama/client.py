"""Ollama dedicated client and API adapter for ADA."""

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Generator, List, Optional


@dataclass
class OllamaModelDetails:
    format: str = ""
    family: str = ""
    parameter_size: str = ""
    quantization_level: str = ""


@dataclass
class OllamaModelInfo:
    name: str
    size: int = 0
    size_formatted: str = ""
    digest: str = ""
    modified_at: str = ""
    details: Optional[OllamaModelDetails] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "size": self.size,
            "size_formatted": self.size_formatted or _format_bytes(self.size),
            "digest": self.digest,
            "modified_at": self.modified_at,
            "details": (
                {
                    "format": self.details.format if self.details else "",
                    "family": self.details.family if self.details else "",
                    "parameter_size": self.details.parameter_size if self.details else "",
                    "quantization_level": self.details.quantization_level if self.details else "",
                }
                if self.details
                else {}
            ),
        }


@dataclass
class RunningModelInfo:
    name: str
    size: int = 0
    size_vram: int = 0
    size_vram_formatted: str = ""
    expires_at: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "size": self.size,
            "size_vram": self.size_vram,
            "size_vram_formatted": self.size_vram_formatted or _format_bytes(self.size_vram),
            "expires_at": self.expires_at,
        }


def _format_bytes(size_bytes: int) -> str:
    if not size_bytes or size_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    val = float(size_bytes)
    while val >= 1024 and i < len(units) - 1:
        val /= 1024
        i += 1
    return f"{val:.2f} {units[i]}"


class OllamaClient:
    """High-level client for interacting with the local or remote Ollama instance."""

    def __init__(self, endpoint: Optional[str] = None, timeout: float = 30.0):
        self.endpoint = (endpoint or os.environ.get("ADA_OLLAMA_URL", "http://127.0.0.1:11434")).rstrip("/")
        self.timeout = timeout

    def health(self) -> Dict[str, Any]:
        """Check if Ollama server is reachable."""
        start = time.monotonic()
        try:
            req = urllib.request.Request(f"{self.endpoint}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                latency_ms = round((time.monotonic() - start) * 1000, 2)
                return {
                    "online": resp.status == 200,
                    "status": "healthy" if resp.status == 200 else "degraded",
                    "available": resp.status == 200,
                    "endpoint": self.endpoint,
                    "latency_ms": latency_ms,
                    "status_code": resp.status,
                }
        except Exception as err:
            return {
                "online": False,
                "status": "offline",
                "available": False,
                "endpoint": self.endpoint,
                "error": str(err),
                "latency_ms": None,
            }

    def list_models(self) -> List[Dict[str, Any]]:
        """List all downloaded/installed Ollama models with their metadata."""
        try:
            req = urllib.request.Request(f"{self.endpoint}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            models = []
            for item in data.get("models", []):
                details_raw = item.get("details", {})
                details = OllamaModelDetails(
                    format=details_raw.get("format", ""),
                    family=details_raw.get("family", ""),
                    parameter_size=details_raw.get("parameter_size", ""),
                    quantization_level=details_raw.get("quantization_level", ""),
                )
                info = OllamaModelInfo(
                    name=item.get("name", ""),
                    size=item.get("size", 0),
                    size_formatted=_format_bytes(item.get("size", 0)),
                    digest=item.get("digest", "")[:12],
                    modified_at=item.get("modified_at", ""),
                    details=details,
                )
                models.append(info.as_dict())
            return models
        except Exception:
            return []

    def running_models(self) -> List[Dict[str, Any]]:
        """List models currently loaded in memory/VRAM (Ollama /api/ps)."""
        try:
            req = urllib.request.Request(f"{self.endpoint}/api/ps", method="GET")
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            running = []
            for item in data.get("models", []):
                info = RunningModelInfo(
                    name=item.get("name", ""),
                    size=item.get("size", 0),
                    size_vram=item.get("size_vram", 0),
                    size_vram_formatted=_format_bytes(item.get("size_vram", 0)),
                    expires_at=item.get("expires_at", ""),
                )
                running.append(info.as_dict())
            return running
        except Exception:
            return []

    def stream_pull(self, model_name: str) -> Generator[Dict[str, Any], None, None]:
        """Pull an Ollama model streaming the download/unpacking progress."""
        payload = json.dumps({"name": model_name, "stream": True}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.endpoint}/api/pull",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=3600.0) as resp:
                for line in resp:
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line.decode("utf-8"))
                        status = chunk.get("status", "")
                        completed = chunk.get("completed", 0)
                        total = chunk.get("total", 0)
                        percent = round((completed / total) * 100, 1) if total > 0 else 0
                        yield {
                            "status": status,
                            "completed": completed,
                            "total": total,
                            "percent": percent,
                            "completed_formatted": _format_bytes(completed),
                            "total_formatted": _format_bytes(total),
                            "done": status == "success",
                        }
                    except ValueError:
                        continue
        except Exception as err:
            yield {"error": str(err), "done": True, "percent": 0}

    def pull_sync(self, model_name: str, timeout: float = 1800.0) -> bool:
        """Pull a model synchronously."""
        payload = json.dumps({"name": model_name, "stream": False}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.endpoint}/api/pull",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status == 200
        except Exception:
            return False

    def delete_model(self, model_name: str) -> bool:
        """Delete an installed model from local storage."""
        payload = json.dumps({"name": model_name}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.endpoint}/api/delete",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="DELETE",
        )
        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def unload_model(self, model_name: str) -> bool:
        """Unload a model from VRAM by sending keep_alive=0."""
        payload = json.dumps({"model": model_name, "keep_alive": 0}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.endpoint}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def load_model(self, model_name: str, keep_alive: Optional[str] = None) -> bool:
        """Preload a model into memory/VRAM without generating text."""
        body = {"model": model_name}
        if keep_alive:
            body["keep_alive"] = keep_alive
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{self.endpoint}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def show_model(self, model_name: str) -> Dict[str, Any]:
        """Get model parameters, system template and modelfile."""
        payload = json.dumps({"name": model_name}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.endpoint}/api/show",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as err:
            return {"error": str(err)}
