"""Batch orchestration and photo culling pipeline."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import os
import re
from typing import Any, Dict, List, Optional

from mcps.photography.analyzer import PhotoAnalyzer, IMAGE_EXTENSIONS
from mcps.photography.burst import BurstDetector
from mcps.photography.xmp import XmpManager, write_photo_xmp, mark_xmp_label


def _feedback_label(path: Path | str) -> Optional[str]:
    name = Path(path).name.upper()
    if name.startswith("OK__"):
        return "selected"
    if name.startswith("RECH__"):
        return "rejected"
    return None


class BatchProcessor:
    """Orchestrates multi-photo evaluation, ranking, repair, and burst culling."""

    @classmethod
    def analyze_single(cls, path: Path, root: Path, folder_ctx: Dict[str, Any], config: Optional[Dict[str, Any]] = None, vision: bool = False, write_xmp: bool = False) -> Dict[str, Any]:
        """Worker for single photo analysis with review grading."""
        from ada.agents.coordinator import MultiAgentCoordinator
        res = MultiAgentCoordinator(config).analyze_photo({
            "path": str(path),
            "folder": str(root),
            "folder_context": folder_ctx,
            "vision": vision,
            "write_xmp": write_xmp,
        })
        return res

    @classmethod
    def demote_burst_duplicates(cls, burst_groups: List[List[Path]], records: List[Dict[str, Any]], write_xmp: bool = False, accept_threshold: float = 5.0) -> List[str]:
        duplicates = []
        stored_cache = {}

        def stored(path):
            key = str(path)
            if key not in stored_cache:
                sidecar = Path(path).with_suffix(".xmp")
                if not sidecar.is_file():
                    stored_cache[key] = {"status": "Rechazada", "score": 0.0, "rating": 0}
                else:
                    content = sidecar.read_text(encoding="utf-8", errors="ignore")
                    status = re.search(r'ada:Status="([^"]+)"', content)
                    score = re.search(r'ada:Score="([^"]+)"', content)
                    rating = re.search(r'xmp:Rating="([^"]+)"', content)
                    try:
                        rating_value = int(rating.group(1)) if rating else 0
                        numeric_score = float(score.group(1)) if score else float(rating_value) * 2
                    except (TypeError, ValueError):
                        rating_value = 0
                        numeric_score = 0.0
                    stored_cache[key] = {
                        "status": status.group(1) if status else "Rechazada",
                        "score": numeric_score,
                        "rating": rating_value,
                    }
            return stored_cache[key]

        for group in burst_groups:
            paths = {str(path) for path in group}
            candidates = [item for item in records if item.get("path") in paths]
            accepted = []
            for item in candidates:
                review = item.get("review") or {}
                if (
                    int(review.get("selection_rating", 0) or 0) >= 3
                    and float(review.get("selection_score", 0) or 0) >= accept_threshold
                ):
                    accepted.append((item, float(review.get("selection_score", 0) or 0)))
            if not accepted:
                accepted = [
                    (item, stored(item.get("path"))["score"])
                    for item in candidates
                    if (
                        stored(item.get("path"))["status"] == "Seleccionada"
                        and stored(item.get("path"))["score"] >= accept_threshold
                    )
                ]
            if len(accepted) <= 1:
                continue

            labeled = [item for item, _ in accepted if _feedback_label(item.get("path")) == "selected"]
            winner = max(
                (item for item, _ in accepted if not labeled or item in labeled),
                key=lambda item: float(
                    (item.get("review") or {}).get("selection_score", 0) or stored(item.get("path"))["score"]
                ),
            )

            if write_xmp and winner:
                wpath = winner.get("path")
                wscore = (winner.get("review") or {}).get("selection_score", 0) or stored(wpath)["score"]
                wrating = (winner.get("review") or {}).get("selection_rating", 0) or stored(wpath)["rating"] or 3
                write_photo_xmp(
                    wpath,
                    "Seleccionada",
                    wrating,
                    wscore,
                    "Ráfaga ganadora seleccionada por ADA",
                    label="Amarillo",
                )

            for item, _ in accepted:
                if item != winner:
                    p = item.get("path")
                    duplicates.append(p)
                    if write_xmp and p:
                        write_photo_xmp(
                            p,
                            "Rechazada",
                            0,
                            stored(p)["score"],
                            "Ráfaga descartada: mejor fotograma seleccionado",
                            label="Amarillo",
                        )

        return duplicates

    @classmethod
    def process_batch(cls, args: Dict[str, Any]) -> Dict[str, Any]:
        folder_str = str(args.get("path") or args.get("dir") or args.get("folder") or "")
        folder = Path(os.path.expanduser(folder_str)).resolve() if folder_str else Path.cwd()
        if not folder.is_dir():
            return {"error": "directory not found", "dir": str(folder)}

        repair_xmp = bool(args.get("repair_xmp", False))
        if repair_xmp:
            repaired_count = 0
            xmp_files = sorted(folder.glob("*.xmp"))
            for xmp in xmp_files:
                img_candidate = xmp.with_suffix(".jpg")
                if not img_candidate.exists():
                    img_candidate = xmp.with_suffix(".ARW")
                if not img_candidate.exists():
                    img_candidate = xmp.with_suffix("")
                XmpManager.repair_photo_xmp(img_candidate)
                repaired_count += 1

            files = sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS])
            burst_groups, _ = BurstDetector.detect_burst_groups(files)
            records = [{"path": str(f)} for f in files]
            duplicates = cls.demote_burst_duplicates(burst_groups, records, write_xmp=True) if args.get("mark_bursts") else []

            return {
                "ok": True,
                "repaired_count": repaired_count,
                "burst_duplicates_rejected": duplicates,
            }

        files = sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS])
        if not files:
            return {"ok": True, "scanned": 0, "completed": 0, "records": []}

        limit = args.get("limit")
        if limit:
            files = files[:int(limit)]

        vision = bool(args.get("vision", False))
        write_xmp = bool(args.get("write_xmp", False))
        folder_ctx = PhotoAnalyzer.folder_context(files[0], folder)

        records = []
        xmp_written = []
        for f in files:
            rec = cls.analyze_single(f, folder, folder_ctx, args.get("config"), vision=vision, write_xmp=write_xmp)
            records.append(rec)
            if write_xmp and rec.get("ok"):
                xmp_written.append(str(f.with_suffix(".xmp")))

        # Detect bursts
        burst_groups, _ = BurstDetector.detect_burst_groups(files)
        duplicates = cls.demote_burst_duplicates(burst_groups, records, write_xmp=write_xmp)
        burst_count = sum(len(g) for g in burst_groups)

        # Ensure all detected burst members get yellow label if write_xmp is true
        if write_xmp and burst_groups:
            for grp in burst_groups:
                for p in grp:
                    if str(p) not in duplicates:
                        sidecar = Path(p).with_suffix(".xmp")
                        if sidecar.is_file():
                            mark_xmp_label(p, "Amarillo")

        return {
            "ok": True,
            "dir": str(folder),
            "scanned": len(files),
            "completed": len(records),
            "xmp_written": xmp_written,
            "burst_count": burst_count,
            "burst_duplicates_demoted": len(duplicates),
            "burst_duplicates_rejected": duplicates,
            "records": records,
        }


run = BatchProcessor.process_batch
