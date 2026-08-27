"""Memory estimates for local model loading and context budgets."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, Optional

GB = 1024**3


def _bytes(value: float) -> int:
    return max(0, int(round(float(value))))


def _parameter_billions(value: Any) -> float:
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*[bB]", str(value or ""))
    return float(match.group(1)) if match else 0.0


class ModelMemoryEstimator:
    """Estimate model memory without loading or running the model."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    def estimate(
        self,
        model: str,
        num_ctx: int,
        max_tokens: int = 0,
        batch: int = 1,
        metadata: Optional[Dict[str, Any]] = None,
        hardware: Optional[Dict[str, Any]] = None,
        running: Optional[Iterable[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        num_ctx = max(512, min(131072, int(num_ctx)))
        max_tokens = max(0, min(32768, int(max_tokens)))
        batch = max(1, min(16, int(batch)))
        metadata = metadata or {}
        hardware = hardware or {}
        running = list(running or [])
        details = metadata.get("details") or {}
        parameters_b = _parameter_billions(details.get("parameter_size") or metadata.get("parameter_size") or model)
        observed = next((item for item in running if item.get("name") == model), None)
        observed_bytes = _bytes((observed or {}).get("size_vram") or (observed or {}).get("size") or 0)
        disk_bytes = _bytes(metadata.get("size") or 0)
        quantization = str(details.get("quantization_level") or "").upper()
        bytes_per_parameter = self._bytes_per_parameter(quantization)
        weights_bytes = observed_bytes or disk_bytes or _bytes(parameters_b * 1_000_000_000 * bytes_per_parameter)
        source = "observed_ollama" if observed_bytes else "disk_size" if disk_bytes else "parameter_heuristic"
        confidence = "high" if observed_bytes else "medium" if disk_bytes else "low"

        # A conservative architecture-agnostic approximation when Ollama does
        # not expose KV dimensions in the model metadata.
        kv_bytes = _bytes(max(0.125, parameters_b * 0.03) * num_ctx * 1024 * batch)
        output_bytes = _bytes(max(0.0625, parameters_b * 0.015) * max_tokens * 1024 * batch)
        overhead_bytes = _bytes(max(0.35 * GB, weights_bytes * 0.08))
        total_bytes = weights_bytes + kv_bytes + output_bytes + overhead_bytes

        ram_available = _bytes(float(hardware.get("ram_available_gb") or 0) * GB)
        vram_available = _bytes(float(hardware.get("vram_available_gb") or hardware.get("vram_gb") or 0) * GB)
        available_bytes = vram_available or ram_available
        margin_bytes = max(_bytes(float(hardware.get("ram_gb") or 0) * GB * 0.15), GB)
        status = "unknown"
        if available_bytes:
            usable = max(0, available_bytes - margin_bytes)
            status = "safe" if total_bytes <= usable * 0.7 else "tight" if total_bytes <= usable else "exceeds"

        return {
            "model": model,
            "context": {"num_ctx": num_ctx, "max_tokens": max_tokens, "batch": batch},
            "estimate": {
                "weights_bytes": weights_bytes,
                "kv_cache_bytes": kv_bytes,
                "output_buffer_bytes": output_bytes,
                "runtime_overhead_bytes": overhead_bytes,
                "total_bytes": total_bytes,
                "source": source,
                "confidence": confidence,
            },
            "available": {
                "ram_available_bytes": ram_available,
                "vram_available_bytes": vram_available,
                "operating_margin_bytes": margin_bytes,
                "usable_bytes": max(0, available_bytes - margin_bytes) if available_bytes else 0,
            },
            "status": status,
            "warnings": (
                []
                if source == "observed_ollama"
                else ["Estimación aproximada; cargá el modelo para calibrar el consumo real."]
            ),
        }

    @staticmethod
    def _bytes_per_parameter(quantization: str) -> float:
        if "Q2" in quantization:
            return 0.35
        if "Q3" in quantization:
            return 0.45
        if "Q4" in quantization:
            return 0.6
        if "Q5" in quantization:
            return 0.7
        if "Q6" in quantization:
            return 0.8
        if "Q8" in quantization:
            return 1.05
        if "F16" in quantization or "BF16" in quantization:
            return 2.1
        return 1.0
