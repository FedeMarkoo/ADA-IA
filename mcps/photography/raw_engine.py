"""Camera RAW image decoding and metadata extraction engine."""

from pathlib import Path
from typing import Dict, Tuple
from PIL import Image

RAW_EXTENSIONS = {".raw", ".cr2", ".cr3", ".nef", ".arw", ".dng", ".raf", ".orf", ".rw2"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic", ".tif", ".tiff"} | RAW_EXTENSIONS


class RawEngine:
    """Handles Camera RAW file loading, development, and EXIF/MakerNotes extraction."""

    @staticmethod
    def is_raw(path: Path) -> bool:
        return path.suffix.lower() in RAW_EXTENSIONS

    @classmethod
    def load_rgb(cls, path: Path) -> Image.Image:
        """Load a standard image or develop a camera RAW into an RGB PIL Image."""
        if cls.is_raw(path):
            try:
                import rawpy
            except ImportError as exc:
                raise RuntimeError("rawpy is required for RAW files") from exc
            with rawpy.imread(str(path)) as raw:
                rendered = raw.postprocess(use_camera_wb=True, no_auto_bright=True, output_bps=8)
            return Image.fromarray(rendered, mode="RGB")
        return Image.open(path).convert("RGB")

    @classmethod
    def load_raw_once(cls, path: Path) -> Tuple[Image.Image, Dict[str, str]]:
        """Develop RAW and extract metadata in a single read pass for performance."""
        try:
            import rawpy
        except ImportError as exc:
            raise RuntimeError("rawpy is required for RAW files") from exc

        metadata: Dict[str, str] = {}
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
