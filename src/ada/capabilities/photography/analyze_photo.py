"""Fast technical and contextual analysis of a photograph.

Technical metrics are calculated locally with Pillow and NumPy. Semantic
analysis is optional and uses a vision-language model through Ollama when it
is available. The local metrics remain useful when no vision model is loaded.
"""

import base64
import io
import json
import math
import os
import re
from pathlib import Path

import numpy as np
from PIL import ExifTags, Image, ImageOps


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic", ".tif", ".tiff", ".raw", ".cr2", ".nef", ".arw"}


def _clamp(value, low=0.0, high=10.0):
    return round(max(low, min(high, float(value))), 2)


def _score_from_log(value, low=5.0, high=1200.0):
    value = max(0.0, float(value))
    if value <= low:
        return _clamp(value / max(low, 1.0) * 4.0)
    return _clamp(4.0 + 6.0 * (math.log1p(value) - math.log1p(low)) / (math.log1p(high) - math.log1p(low)))


def _metadata(image):
    exif = {}
    try:
        raw = image.getexif()
        for key, value in raw.items():
            name = ExifTags.TAGS.get(key, str(key))
            if name in {
                "DateTime",
                "DateTimeOriginal",
                "Make",
                "Model",
                "LensModel",
                "FNumber",
                "ExposureTime",
                "ISOSpeedRatings",
                "FocalLength",
            }:
                exif[name] = str(value)
    except Exception:
        pass
    return exif


def _capture_metadata(path, image, raw_metadata=None):
    """Collect capture data from EXIF, RAW headers and an adjacent XMP sidecar."""
    metadata = _metadata(image)
    raw_path = Path(path)
    if raw_metadata is not None:
        metadata.update(raw_metadata)
    elif raw_path.suffix.lower() in {".raw", ".cr2", ".nef", ".arw", ".dng", ".raf", ".orf"}:
        try:
            import rawpy

            with rawpy.imread(str(raw_path)) as raw:
                other = raw.other
                if getattr(other, "iso_speed", None):
                    metadata.setdefault("ISO", str(round(float(other.iso_speed))))
                if getattr(other, "shutter_speed", None):
                    metadata.setdefault("ExposureTime", str(other.shutter_speed))
                if getattr(other, "aperture", None):
                    metadata.setdefault("FNumber", str(other.aperture))
                lens = getattr(raw, "lens", None)
                if lens and getattr(lens, "model", None):
                    metadata.setdefault("LensModel", str(lens.model))
        except Exception:
            pass
    sidecar = raw_path.with_suffix(".xmp")
    if sidecar.is_file():
        try:
            content = sidecar.read_text(encoding="utf-8", errors="ignore")
            for key, output in {
                "tiff:Make": "Make",
                "tiff:Model": "Model",
                "exif:RecommendedExposureIndex": "ISO",
                "exif:ExposureTime": "ExposureTime",
                "exif:FNumber": "FNumber",
                "exif:FocalLength": "FocalLength",
                "aux:Lens": "LensModel",
            }.items():
                match = re.search(rf'{re.escape(key)}="([^"]+)"', content)
                if match:
                    metadata[output] = match.group(1)
        except OSError:
            pass
    return metadata


def _noise_score(metadata):
    """Estimate high-ISO risk using conservative, explainable camera priors."""
    try:
        iso = float(str(metadata.get("ISO", "")).replace(",", "."))
    except (TypeError, ValueError):
        return 8.0, None, "sin ISO disponible"
    if iso <= 800:
        score = 9.5
    elif iso <= 1600:
        score = 8.5
    elif iso <= 3200:
        score = 7.2
    elif iso <= 6400:
        score = 5.8
    elif iso <= 12800:
        score = 4.3
    else:
        score = 3.2
    make = str(metadata.get("Make", "")).lower()
    model = str(metadata.get("Model", "")).lower()
    # Initial priors, intentionally modest: the user's own accepted/rejected
    # photos should eventually calibrate these values per camera body.
    if "sony" in make or "ilce" in model or "alpha" in model:
        score += 0.5
    elif "nikon" in make or model.startswith("d"):
        score -= 0.2
    score = _clamp(score)
    label = "bajo" if score >= 8 else "moderado" if score >= 6 else "alto"
    return score, round(iso), f"riesgo de ruido {label} para ISO {round(iso)}"


def _load_rgb(path):
    """Load a normal image or develop a camera RAW into an RGB preview."""
    if path.suffix.lower() in {".raw", ".cr2", ".nef", ".arw", ".dng", ".raf", ".orf"}:
        try:
            import rawpy
        except ImportError as exc:
            raise RuntimeError("rawpy is required for RAW files") from exc
        with rawpy.imread(str(path)) as raw:
            rendered = raw.postprocess(use_camera_wb=True, no_auto_bright=True, output_bps=8)
        return Image.fromarray(rendered, mode="RGB")
    return Image.open(path).convert("RGB")


def _load_raw_once(path):
    import rawpy

    metadata = {}
    with rawpy.imread(str(path)) as raw:
        other = raw.other
        if getattr(other, "iso_speed", None):
            metadata["ISO"] = str(round(float(other.iso_speed)))
        if getattr(other, "shutter_speed", None):
            metadata["ExposureTime"] = str(other.shutter_speed)
        if getattr(other, "aperture", None):
            metadata["FNumber"] = str(other.aperture)
        lens = getattr(raw, "lens", None)
        if lens and getattr(lens, "model", None):
            metadata["LensModel"] = str(lens.model)
        rendered = raw.postprocess(use_camera_wb=True, no_auto_bright=True, output_bps=8)
    return Image.fromarray(rendered, mode="RGB"), metadata


def technical_analysis(path):
    """Return deterministic image-quality measurements in a compact report."""
    image_path = Path(path)
    is_raw = image_path.suffix.lower() in {".raw", ".cr2", ".nef", ".arw", ".dng", ".raf", ".orf"}
    raw_metadata = {}
    if is_raw:
        image, raw_metadata = _load_raw_once(image_path)
    else:
        image = _load_rgb(image_path)
    image = ImageOps.exif_transpose(image)
    exif = _capture_metadata(path, image, raw_metadata)
    image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    array = np.asarray(image, dtype=np.float32) / 255.0
    gray = 0.299 * array[:, :, 0] + 0.587 * array[:, :, 1] + 0.114 * array[:, :, 2]
    center = gray[1:-1, 1:-1]
    laplacian = gray[:-2, 1:-1] + gray[2:, 1:-1] + gray[1:-1, :-2] + gray[1:-1, 2:] - 4 * center
    focus_raw = float(np.var(laplacian)) * 10000.0
    mean = float(np.mean(gray))
    shadow_clip = float(np.mean(gray <= 0.02) * 100.0)
    highlight_clip = float(np.mean(gray >= 0.98) * 100.0)
    # A dark event image is not automatically a failed image: faces may be
    # recoverable from RAW and a dark background can be intentional. Keep
    # clipping as a warning, but avoid turning moderate underexposure into a
    # near-zero score (the previous formula did exactly that).
    exposure_score = 10.0 - abs(mean - 0.46) * 8.0 - min(shadow_clip * 0.12, 2.0) - min(highlight_clip * 0.12, 2.0)
    raw_recovery_bonus = 0.0
    if is_raw and mean < 0.4 and highlight_clip < 2.0:
        raw_recovery_bonus = 0.75
        exposure_score += raw_recovery_bonus
    contrast = float(np.percentile(gray, 90) - np.percentile(gray, 10))
    contrast_score = _clamp(contrast * 14.0)
    focus_score = _score_from_log(focus_raw)
    exposure_score = _clamp(exposure_score)
    composition_score = _clamp(4.0 + contrast_score * 0.35 + (1.0 if 0.18 < mean < 0.82 else 0.0))
    noise_score, iso, noise_note = _noise_score(exif)
    overall = _clamp(focus_score * 0.35 + exposure_score * 0.3 + composition_score * 0.25 + noise_score * 0.1)
    return {
        "width": image.width,
        "height": image.height,
        "orientation": (
            "landscape" if image.width > image.height else "portrait" if image.height > image.width else "square"
        ),
        "focus": {"score": focus_score, "measure": round(focus_raw, 3), "note": "higher is sharper"},
        "exposure": {
            "score": exposure_score,
            "mean_luminance": round(mean, 4),
            "shadow_clip_percent": round(shadow_clip, 3),
            "highlight_clip_percent": round(highlight_clip, 3),
            "raw_recovery_bonus": raw_recovery_bonus,
            "note": (
                "subexposición potencialmente recuperable desde RAW"
                if raw_recovery_bonus
                else "evaluación del render disponible"
            ),
        },
        "noise": {"score": noise_score, "iso": iso, "note": noise_note},
        "contrast": {"score": contrast_score, "range": round(contrast, 4)},
        "composition": {
            "score": composition_score,
            "note": "technical proxy; semantic composition requires a vision model",
        },
        "overall_score": overall,
        "exif": exif,
    }


def _folder_context(path, folder):
    folder = Path(folder) if folder else Path(path).parent
    if not folder.is_dir():
        return {"folder": str(folder), "siblings": []}
    siblings = [p.name for p in sorted(folder.iterdir()) if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS]
    return {"folder": str(folder), "siblings": siblings[:30], "count": len(siblings)}


def _extract_json(text):
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


def vision_analysis(path, folder_context, config=None):
    """Ask the configured local VLM for semantic and photographer feedback."""
    config = config or {}
    from src.ada.infrastructure.engines.model_manager import ModelManager

    manager = ModelManager(config)
    provider = config.get("vision_provider", config.get("engine_provider", "ollama"))
    if not manager.available().get(provider):
        return {"available": False, "reason": "vision_provider_unavailable"}
    prompt = (
        "Analiza esta fotografía como un fotógrafo profesional. Devuelve SOLO JSON válido, "
        "sin markdown, con estas claves: subject, context (lista), style, photographer_feedback, "
        "artistic_score (0 a 10), session_match {matches_folder, confidence, reason}. "
        "Usa una confianza conservadora: no inventes identidad, lugar ni evento. "
        f"La carpeta se llama {folder_context['folder']!r} y contiene {folder_context.get('count', 0)} fotos. "
        f"Algunos archivos vecinos son: {folder_context.get('siblings', [])}. "
        "Evalúa si el contenido parece pertenecer a esa misma sesión."
    )
    # Vision models generally do not accept camera RAW containers directly.
    # Render the RAW with rawpy/Pillow and send a temporary in-memory JPEG.
    preview = _load_rgb(Path(path))
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
    parsed = _extract_json(result)
    parsed["available"] = True
    return parsed


def run(args):
    path = Path(os.path.expanduser(str(args.get("path") or args.get("file") or ""))).resolve()
    if not path.is_file():
        return {"error": "image not found", "path": str(path)}
    try:
        technical = technical_analysis(path)
    except Exception as exc:
        return {"error": f"could not analyze image: {exc}", "path": str(path)}
    result = {"ok": True, "path": str(path), "technical": technical}
    context = args.get("folder_context") or _folder_context(path, args.get("folder"))
    result["session_context"] = context
    if args.get("vision", True):
        try:
            result["semantic"] = vision_analysis(str(path), context, args.get("config"))
        except Exception as exc:
            result["semantic"] = {"available": False, "reason": str(exc)}
    return result
