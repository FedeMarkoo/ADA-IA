import os
import shutil
from pathlib import Path

KEYWORDS = {
    "wedding": "Weddings",
    "vacation": "Vacations",
    "vacaciones": "Vacations",
    "paris": "Vacations/Paris",
    "birthday": "Birthdays",
    "concert": "Concerts",
    "family": "Family",
    "reunion": "Family",
}


def run(args):
    """Organize photos in a directory into subfolders based on filename keywords.

    Args:
        args: dict with 'dir' key.
    Returns a dict with summary.
    """
    folder = args.get("dir")
    if not folder:
        return {"error": "no dir provided"}
    folder = os.path.expanduser(folder)
    if not os.path.isdir(folder):
        return {"error": "dir not found", "dir": folder}
    dry_run = bool(args.get("dry_run", False))
    if not dry_run and not args.get("confirm"):
        return {"error": "confirmation_required", "action": "organize_photos"}
    roots = [Path(os.path.expanduser(str(item))).resolve() for item in args.get("allowed_roots", []) if item]
    folder_path = Path(folder).resolve()
    if not roots:
        return {"error": "allowed_roots_required", "dir": str(folder_path)}
    if not any(folder_path == root or root in folder_path.parents for root in roots):
        return {"error": "path_outside_allowed_roots", "dir": str(folder_path)}
    organized = os.path.join(folder, "organized")
    if not dry_run:
        os.makedirs(organized, exist_ok=True)
    moved = []
    for fname in os.listdir(folder):
        if fname.lower().endswith((".jpg", ".jpeg", ".png")):
            src = os.path.join(folder, fname)
            key = None
            lname = fname.lower()
            for k, v in KEYWORDS.items():
                if k in lname:
                    key = v
                    break
            if key is None:
                key = "Unsorted"
            dest_dir = os.path.join(organized, key)
            if not dry_run:
                os.makedirs(dest_dir, exist_ok=True)
            dest = os.path.join(dest_dir, fname)
            if os.path.exists(dest):
                stem, ext = os.path.splitext(fname)
                dest = os.path.join(dest_dir, stem + "_ada" + ext)
            if not dry_run:
                shutil.move(src, dest)
            moved.append({"from": src, "to": dest})
    return {"ok": True, "dry_run": dry_run, "moved": moved, "count": len(moved)}
