"""Lightroom catalog and workflow manager."""

import os
import shutil
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcps.photography.xmp import XmpManager


class LightroomManager:
    """Manages Lightroom catalogs, sidecar verification, and cleaning plans."""

    @classmethod
    def plan_cleanup(cls, root_dir: Path | str, dry_run: bool = True) -> Dict[str, Any]:
        root = Path(os.path.expanduser(str(root_dir))).resolve()
        if not root.exists():
            return {"error": "photo root not found", "root": str(root)}

        photos = []
        xmp_files = []
        for p in root.rglob("*"):
            if p.is_file():
                ext = p.suffix.lower()
                if ext in {".raw", ".cr2", ".cr3", ".nef", ".arw", ".dng", ".jpg", ".jpeg"}:
                    photos.append(p)
                elif ext == ".xmp":
                    xmp_files.append(p)

        orphan_xmps = [str(x) for x in xmp_files if not x.with_suffix("").exists() and not any(x.parent.glob(f"{x.stem}.*"))]

        return {
            "ok": True,
            "root": str(root),
            "total_photos": len(photos),
            "total_xmps": len(xmp_files),
            "orphan_xmps_count": len(orphan_xmps),
            "orphan_xmps": orphan_xmps[:20],
            "dry_run": dry_run,
            "actions_planned": f"Verificación completada: {len(photos)} fotos y {len(xmp_files)} XMP sidecars auditados.",
        }

    @classmethod
    def run(cls, args: Dict[str, Any]) -> Dict[str, Any]:
        action = str(args.get("action", "plan")).lower()
        root = Path(os.path.expanduser(args.get("root", "~/Desktop/Fotos"))).resolve()
        dry_run = action in {"plan", "simulate", "dry_run"}

        if not dry_run and not args.get("confirm"):
            return {
                "error": "confirmation_required",
                "action": action,
                "root": str(root),
                "message": "Use plan/simulate first and confirm before changing Fotos.",
            }

        return cls.plan_cleanup(root, dry_run=dry_run)


run = LightroomManager.run
