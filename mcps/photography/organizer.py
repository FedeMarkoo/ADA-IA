"""Organize photos into categorized folders by keywords and metadata."""

import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_KEYWORDS = {
    "wedding": "Weddings",
    "casamiento": "Weddings",
    "boda": "Weddings",
    "vacation": "Vacations",
    "vacaciones": "Vacations",
    "paris": "Vacations/Paris",
    "birthday": "Birthdays",
    "cumple": "Birthdays",
    "concert": "Concerts",
    "recital": "Concerts",
    "family": "Family",
    "familia": "Family",
    "reunion": "Family",
}


class PhotoOrganizer:
    """Organizes photos in a directory into structured subfolders."""

    @classmethod
    def organize(cls, args: Dict[str, Any]) -> Dict[str, Any]:
        folder_str = args.get("dir") or args.get("path")
        if not folder_str:
            return {"error": "no dir provided"}

        folder = Path(os.path.expanduser(folder_str)).resolve()
        if not folder.is_dir():
            return {"error": "dir not found", "dir": str(folder)}

        dry_run = bool(args.get("dry_run", False))
        if not dry_run and not args.get("confirm"):
            return {"error": "confirmation_required", "action": "organize_photos"}

        roots = [Path(os.path.expanduser(str(item))).resolve() for item in args.get("allowed_roots", []) if item]
        if not roots:
            return {"error": "allowed_roots_required", "dir": str(folder)}

        if not any(folder == root or root in folder.parents for root in roots):
            return {"error": "path_outside_allowed_roots", "dir": str(folder)}

        organized_dir = folder / "organized"
        if not dry_run:
            organized_dir.mkdir(parents=True, exist_ok=True)

        keywords = dict(DEFAULT_KEYWORDS)
        if isinstance(args.get("keywords"), dict):
            keywords.update(args["keywords"])

        moved: List[Dict[str, str]] = []
        for child in sorted(folder.iterdir()):
            if not child.is_file():
                continue
            if child.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".raw", ".cr2", ".nef", ".arw", ".dng"}:
                continue

            target_cat = "Unsorted"
            lname = child.name.lower()
            for kw, category in keywords.items():
                if kw in lname:
                    target_cat = category
                    break

            dest_folder = organized_dir / target_cat
            if not dry_run:
                dest_folder.mkdir(parents=True, exist_ok=True)

            dest_path = dest_folder / child.name
            if dest_path.exists():
                dest_path = dest_folder / f"{child.stem}_ada{child.suffix}"

            if not dry_run:
                shutil.move(str(child), str(dest_path))
                xmp_sidecar = child.with_suffix(".xmp")
                if xmp_sidecar.is_file():
                    shutil.move(str(xmp_sidecar), str(dest_path.with_suffix(".xmp")))

            moved.append({"from": str(child), "to": str(dest_path), "category": target_cat})

        return {
            "ok": True,
            "dry_run": dry_run,
            "total_moved": len(moved),
            "moved": moved,
        }


run = PhotoOrganizer.organize
