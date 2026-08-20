"""Semantic Vision-Language Model analysis for photography."""

import base64
import io
import json
from pathlib import Path
from typing import Any, Dict, Optional
from PIL import Image

from mcps.photography.raw_engine import RawEngine


class VisionAnalyzer:
    """Invokes local VLM (e.g. Qwen2.5-VL) for artistic review and subject classification."""

    @staticmethod
    def extract_json(text: str) -> Dict[str, Any]:
        try:
            return json.loads(text)
        except Exception:
            start, end = text.find("{"), text.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except Exception:
                    pass
        return {"raw": text}

    @classmethod
    def analyze(cls, path: Path | str, folder_context: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        config = config or {}
        try:
            from ada.infrastructure.engines.model_manager import ModelManager
            manager = ModelManager(config)
            provider = config.get("vision_provider", config.get("engine_provider", "ollama"))
            if not manager.available().get(provider):
                return {"available": False, "reason": "vision_provider_unavailable"}

            prompt = (
                "Analiza esta fotografía como un fotógrafo profesional. Devuelve SOLO JSON válido, "
                "sin markdown, con estas claves: subject, context (lista), style, photographer_feedback, "
                "artistic_score (0 a 10), session_match {matches_folder, confidence, reason}. "
                "Usa una confianza conservadora: no inventes identidad, lugar ni evento. "
                f"La carpeta se llama {folder_context.get('folder')!r} y contiene {folder_context.get('count', 0)} fotos. "
                "Evalúa si el contenido parece pertenecer a esa misma sesión."
            )

            preview = RawEngine.load_rgb(Path(path))
            preview.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            preview.save(buffer, format="JPEG", quality=90)
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")

            result = manager.call_vision(
                provider,
                prompt,
                image_base64=encoded,
                ollama_model=(config.get("models", {}).get("vision") or config.get("vision_model", "qwen2.5vl:3b")),
            )
            parsed = cls.extract_json(result)
            parsed["available"] = True
            return parsed
        except Exception as exc:
            return {"available": False, "reason": str(exc)}
