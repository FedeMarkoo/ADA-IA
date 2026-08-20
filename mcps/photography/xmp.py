"""Lightroom-compatible XMP sidecar generator and metadata manager."""

import re
from pathlib import Path
from typing import Optional


class XmpManager:
    """Manages Lightroom XMP sidecars, ratings, color labels, and pick flags."""

    @staticmethod
    def write_photo_xmp(path: Path | str, status: str, rating: int, score: float, reason: str, label: Optional[str] = None) -> str:
        """Create or update ADA fields while preserving all existing XMP metadata."""
        sidecar = Path(path).with_suffix(".xmp")
        content = (
            sidecar.read_text(encoding="utf-8", errors="ignore")
            if sidecar.is_file()
            else (
                '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
                ' <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
                '  <rdf:Description xmlns:xmp="http://ns.adobe.com/xap/1.0/" rdf:about=""/>\n'
                " </rdf:RDF>\n</x:xmpmeta>\n"
            )
        )
        if "<rdf:Description" not in content:
            raise ValueError("XMP has no rdf:Description element")
        if "xmlns:ada=" not in content:
            content = content.replace("<rdf:Description", '<rdf:Description xmlns:ada="https://ada.local/ns/1.0/"', 1)
        if "xmlns:xmp=" not in content:
            content = content.replace("<rdf:Description", '<rdf:Description xmlns:xmp="http://ns.adobe.com/xap/1.0/"', 1)
        if "xmlns:xmpDM=" not in content:
            content = content.replace(
                "<rdf:Description", '<rdf:Description xmlns:xmpDM="http://ns.adobe.com/xmp/1.0/DynamicMedia/"', 1
            )
        values = {
            "xmp:Rating": str(int(rating if status == "Seleccionada" else 0)),
            "xmp:Label": label or status,
            "xmpDM:good": "True" if status == "Seleccionada" else "False",
            "ada:Status": status,
            "ada:Score": f"{float(score):.2f}",
            "ada:Reason": reason,
        }
        for key, value in values.items():
            escaped = str(value).replace("&", "&amp;").replace('"', "&quot;")
            pattern = rf'{re.escape(key)}="[^"]*"'
            replacement = f'{key}="{escaped}"'
            if re.search(pattern, content):
                content = re.sub(pattern, replacement, content, count=1)
            else:
                content = content.replace("<rdf:Description ", f"<rdf:Description {replacement} ", 1)
        sidecar.write_text(content, encoding="utf-8")
        return str(sidecar)

    @classmethod
    def repair_photo_xmp(cls, path: Path | str) -> str:
        """Repair Lightroom's pick/reject flag without re-running full analysis."""
        sidecar = Path(path).with_suffix(".xmp")
        content = sidecar.read_text(encoding="utf-8", errors="ignore")
        status_match = re.search(r'ada:Status="([^"]+)"', content)
        score_match = re.search(r'ada:Score="([^"]+)"', content)
        rating_match = re.search(r'xmp:Rating="([^"]+)"', content)
        status = (
            status_match.group(1)
            if status_match
            else ("Seleccionada" if rating_match and rating_match.group(1) != "0" else "Rechazada")
        )
        score = float(score_match.group(1)) if score_match else 0.0
        rating = int(rating_match.group(1)) if rating_match else 0
        label_match = re.search(r'xmp:Label="([^"]+)"', content)
        label = label_match.group(1) if label_match and label_match.group(1).lower() in {"amarillo", "yellow"} else None
        return cls.write_photo_xmp(path, status, rating, score, "Flag Lightroom reparado por ADA", label=label)

    @classmethod
    def mark_xmp_label(cls, path: Path | str, label: str) -> str:
        """Mark a burst photo with a specific label while preserving review values."""
        sidecar = Path(path).with_suffix(".xmp")
        if not sidecar.is_file():
            return cls.write_photo_xmp(
                path,
                "Rechazada",
                0,
                0.0,
                "Ráfaga detectada por ADA; análisis individual no disponible",
                label=label,
            )
        content = sidecar.read_text(encoding="utf-8", errors="ignore")
        status_match = re.search(r'ada:Status="([^"]+)"', content)
        score_match = re.search(r'ada:Score="([^"]+)"', content)
        rating_match = re.search(r'xmp:Rating="([^"]+)"', content)
        status = status_match.group(1) if status_match else "Rechazada"
        score = float(score_match.group(1)) if score_match else 0.0
        rating = int(rating_match.group(1)) if rating_match else 0
        return cls.write_photo_xmp(path, status, rating, score, "Ráfaga detectada por ADA", label=label)


# Convenience function aliases
write_photo_xmp = XmpManager.write_photo_xmp
repair_photo_xmp = XmpManager.repair_photo_xmp
mark_xmp_label = XmpManager.mark_xmp_label
