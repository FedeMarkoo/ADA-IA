"""Filesystem operations and validation handlers."""

import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional


class FilesystemHandlers:
    """Safe filesystem operations restricted to allowed roots."""

    def __init__(self, allowed_dirs: Optional[List[str]] = None):
        # None means standalone CLI default; [] is an explicit deny-all policy.
        configured = [os.getcwd()] if allowed_dirs is None else allowed_dirs
        self.allowed = [Path(d).resolve() for d in configured if d]

    def check_path(self, path_str: str) -> Path:
        p = Path(path_str).resolve()
        for root in self.allowed:
            try:
                p.relative_to(root)
                return p
            except ValueError:
                continue
        raise PermissionError(f"Ruta '{path_str}' no permitida fuera de las carpetas autorizadas: {self.allowed}")

    @staticmethod
    def photo_counts(paths):
        """Return the event-photo format breakdown used by all filesystem clients."""
        return {
            "xml": sum(1 for p in paths if Path(p).suffix.casefold() == ".xml"),
            "raw": sum(
                1
                for p in paths
                if Path(p).suffix.casefold() in {".raw", ".nef", ".arw", ".cr2", ".dng", ".raf", ".orf"}
            ),
            "jpg": sum(1 for p in paths if Path(p).suffix.casefold() in {".jpg", ".jpeg"}),
        }

    @staticmethod
    def photo_summary(counts):
        """Translate technical counts into the user-facing event-photo summary."""
        accepted = max(counts.get("raw", 0), counts.get("xml", 0), counts.get("jpg", 0))
        if counts.get("jpg", 0) > 0:
            return f"{accepted} fotos aceptadas y exportadas"
        return f"{accepted} fotos aceptadas sin exportar"

    def list_files(self, args: Dict[str, Any]) -> Dict[str, Any]:
        target = self.check_path(args.get("path", "."))
        if not target.exists():
            return {"error": f"Ruta no existe: {target}"}
        if not target.is_dir():
            return {"error": f"La ruta no es un directorio: {target}"}

        recursive = bool(args.get("recursive", False))
        children = target.rglob("*") if recursive else target.iterdir()
        items = []
        for child in sorted(children):
            items.append(
                {
                    "name": str(child.relative_to(target)) if recursive else child.name,
                    "is_dir": child.is_dir(),
                    "size_bytes": child.stat().st_size if child.is_file() else None,
                }
            )
        return {
            "path": str(target),
            "recursive": recursive,
            "total_items": len(items),
            "items": items,
            "photo_counts": self.photo_counts(
                [child for child in target.rglob("*") if child.is_file()]
                if recursive
                else [child for child in target.iterdir() if child.is_file()]
            ),
        }

    def read_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        target = self.check_path(args.get("path", ""))
        if not target.is_file():
            return {"error": f"Archivo no encontrado: {target}"}
        content = target.read_text(encoding="utf-8", errors="replace")
        return {"path": str(target), "content": content, "size_bytes": len(content)}

    def write_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        target = self.check_path(args.get("path", ""))
        content = args.get("content", "")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {"path": str(target), "bytes_written": len(content), "ok": True}

    def move_files(self, args: Dict[str, Any]) -> Dict[str, Any]:
        src = self.check_path(args.get("source", ""))
        dest = self.check_path(args.get("destination", ""))
        if not src.exists():
            return {"error": f"Origen no encontrado: {src}"}
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        return {"source": str(src), "destination": str(dest), "ok": True}
