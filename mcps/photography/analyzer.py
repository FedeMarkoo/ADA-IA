"""Fast technical and contextual analysis of a photograph."""

import math
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
from PIL import ExifTags, Image, ImageOps

from mcps.photography.raw_engine import RawEngine, IMAGE_EXTENSIONS


def clamp(value: float, low: float = 0.0, high: float = 10.0) -> float:
    return round(max(low, min(high, float(value))), 2)


def score_from_log(value: float, low: float = 5.0, high: float = 1200.0) -> float:
    val = max(0.0, float(value))
    if val <= low:
        return clamp(val / max(low, 1.0) * 4.0)
    return clamp(4.0 + 6.0 * (math.log1p(val) - math.log1p(low)) / (math.log1p(high) - math.log1p(low)))


class PhotoAnalyzer:
    """Computes deterministic image-quality metrics and reads EXIF/XMP context."""

    @staticmethod
    def extract_exif(image: Image.Image) -> Dict[str, str]:
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

    @classmethod
    def capture_metadata(
        cls, path: Path | str, image: Image.Image, raw_metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """Collect capture data from EXIF, RAW headers, and adjacent XMP sidecar."""
        metadata = cls.extract_exif(image)
        raw_path = Path(path)
        if raw_metadata is not None:
            metadata.update(raw_metadata)
        elif RawEngine.is_raw(raw_path):
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

    @staticmethod
    def noise_score(metadata: Dict[str, Any]) -> Tuple[float, Optional[int], str]:
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
        if "sony" in make or "ilce" in model or "alpha" in model:
            score += 0.5
        elif "nikon" in make or model.startswith("d"):
            score -= 0.2

        score = clamp(score)
        label = "bajo" if score >= 8 else "moderado" if score >= 6 else "alto"
        return score, round(iso), f"riesgo de ruido {label} para ISO {round(iso)}"

    @classmethod
    def technical_analysis(cls, path: Path | str) -> Dict[str, Any]:
        """Return deterministic image-quality measurements in a compact report."""
        image_path = Path(path)
        is_raw = RawEngine.is_raw(image_path)
        raw_metadata: Dict[str, str] = {}

        if is_raw:
            image, raw_metadata = RawEngine.load_raw_once(image_path)
        else:
            image = RawEngine.load_rgb(image_path)

        image = ImageOps.exif_transpose(image)
        exif = cls.capture_metadata(image_path, image, raw_metadata)
        image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        array = np.asarray(image, dtype=np.float32) / 255.0
        gray = 0.299 * array[:, :, 0] + 0.587 * array[:, :, 1] + 0.114 * array[:, :, 2]
        center = gray[1:-1, 1:-1]
        laplacian = gray[:-2, 1:-1] + gray[2:, 1:-1] + gray[1:-1, :-2] + gray[1:-1, 2:] - 4 * center
        focus_raw = float(np.var(laplacian)) * 10000.0
        mean = float(np.mean(gray))
        shadow_clip = float(np.mean(gray <= 0.02) * 100.0)
        highlight_clip = float(np.mean(gray >= 0.98) * 100.0)

        exposure_score = 10.0 - abs(mean - 0.46) * 8.0 - min(shadow_clip * 0.12, 2.0) - min(highlight_clip * 0.12, 2.0)
        raw_recovery_bonus = 0.0
        if is_raw and mean < 0.4 and highlight_clip < 2.0:
            raw_recovery_bonus = 0.75
            exposure_score += raw_recovery_bonus

        contrast = float(np.percentile(gray, 90) - np.percentile(gray, 10))
        contrast_score = clamp(contrast * 14.0)
        focus_score = score_from_log(focus_raw)
        exposure_score = clamp(exposure_score)
        composition_score = clamp(4.0 + contrast_score * 0.35 + (1.0 if 0.18 < mean < 0.82 else 0.0))
        noise_sc, iso_val, noise_note = cls.noise_score(exif)
        overall = clamp(focus_score * 0.35 + exposure_score * 0.3 + composition_score * 0.25 + noise_sc * 0.1)

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
            "noise": {"score": noise_sc, "iso": iso_val, "note": noise_note},
            "contrast": {"score": contrast_score, "range": round(contrast, 4)},
            "composition": {
                "score": composition_score,
                "note": "technical proxy; semantic composition requires a vision model",
            },
            "overall_score": overall,
            "exif": exif,
        }

    @classmethod
    def folder_context(cls, path: Path | str, folder: Optional[Path | str] = None) -> Dict[str, Any]:
        fld = Path(folder) if folder else Path(path).parent
        if not fld.is_dir():
            return {"folder": str(fld), "siblings": []}
        siblings = [p.name for p in sorted(fld.iterdir()) if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS]
        return {"folder": str(fld), "siblings": siblings[:30], "count": len(siblings)}

    @classmethod
    def analyze(cls, args: Dict[str, Any]) -> Dict[str, Any]:
        path_str = str(args.get("path") or args.get("file") or "")
        path = Path(os.path.expanduser(path_str)).resolve()
        if not path.is_file():
            return {"error": "image not found", "path": str(path)}
        try:
            technical = cls.technical_analysis(path)
        except Exception as exc:
            return {"error": f"could not analyze image: {exc}", "path": str(path)}

        result = {"ok": True, "path": str(path), "technical": technical}
        context = args.get("folder_context") or cls.folder_context(path, args.get("folder"))
        result["session_context"] = context

        if args.get("vision", False):
            from mcps.photography.vision import VisionAnalyzer

            try:
                result["semantic"] = VisionAnalyzer.analyze(str(path), context, args.get("config"))
            except Exception as exc:
                result["semantic"] = {"available": False, "reason": str(exc)}
        return result


# Convenience functions for backward compatibility
_noise_score = PhotoAnalyzer.noise_score
_capture_metadata = PhotoAnalyzer.capture_metadata
technical_analysis = PhotoAnalyzer.technical_analysis
_folder_context = PhotoAnalyzer.folder_context
run = PhotoAnalyzer.analyze
