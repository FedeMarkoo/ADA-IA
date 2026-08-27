"""Memory estimates for local model loading and context budgets."""

from __future__ import annotations

import re
import json
import os
from pathlib import Path
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
        configured_path = self.config.get("model_memory_calibration_path") or os.environ.get(
            "ADA_MODEL_MEMORY_CALIBRATION"
        )
        if not configured_path:
            configured_path = str(Path.home() / "Desktop" / "ADA_Data" / "model_memory_calibration.json")
        self.calibration_path = Path(configured_path).expanduser() if configured_path else None
        self.calibrations = self._load_calibrations()

    def _load_calibrations(self):
        if not self.calibration_path or not self.calibration_path.exists():
            return {}
        try:
            value = json.loads(self.calibration_path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save_calibrations(self):
        if not self.calibration_path:
            return
        self.calibration_path.parent.mkdir(parents=True, exist_ok=True)
        self.calibration_path.write_text(json.dumps(self.calibrations, indent=2), encoding="utf-8")

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
        calibration = self.calibrations.get(model) or {}
        calibration_factor = float(calibration.get("factor", 1.0))
        total_bytes = _bytes((weights_bytes + kv_bytes + output_bytes + overhead_bytes) * calibration_factor)

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
                "calibration_factor": calibration_factor,
                "calibration_samples": int(calibration.get("samples", 0)),
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

    def calibrate(self, model: str, predicted_bytes: int, observed_bytes: int) -> Dict[str, Any]:
        """Persist a bounded correction factor from an observed Ollama load."""
        predicted_bytes = max(1, int(predicted_bytes))
        observed_bytes = max(1, int(observed_bytes))
        raw_factor = max(0.5, min(2.0, observed_bytes / predicted_bytes))
        previous = self.calibrations.get(model) or {}
        samples = int(previous.get("samples", 0))
        old_factor = float(previous.get("factor", raw_factor))
        factor = (old_factor * samples + raw_factor) / (samples + 1)
        self.calibrations[model] = {"factor": round(factor, 6), "samples": samples + 1}
        self._save_calibrations()
        return {"model": model, "factor": factor, "samples": samples + 1, "observed_bytes": observed_bytes}

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
