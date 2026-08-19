"""Move files into one named directory, with collision protection."""

import os
import shutil
from pathlib import Path


def run(args):
    source = Path(os.path.expanduser(args.get("source", ""))).resolve()
    name = str(args.get("name", "")).strip()
    if not source.is_dir():
        return {"error": "source not found", "source": str(source)}
    roots = [Path(os.path.expanduser(str(item))).resolve() for item in args.get("allowed_roots", []) if item]
    if roots and not any(source == root or root in source.parents for root in roots):
        return {"error": "path_outside_allowed_roots", "source": str(source)}
    if not name or Path(name).name != name or name in {".", ".."}:
        return {"error": "invalid destination name"}
    destination = (source.parent / name).resolve()
    if destination == source or source in destination.parents:
        return {"error": "destination cannot be inside source", "destination": str(destination)}
    files = [p for p in source.iterdir() if p.is_file() and not p.name.startswith(".")]
    destination.mkdir(parents=True, exist_ok=True)
    moved = []
    for item in files:
        target = destination / item.name
        if target.exists():
            stem, suffix = item.stem, item.suffix
            index = 1
            while target.exists():
                target = destination / f"{stem}_ada_{index}{suffix}"
                index += 1
        shutil.move(str(item), str(target))
        moved.append({"from": str(item), "to": str(target)})
    return {"ok": True, "source": str(source), "destination": str(destination), "count": len(moved), "moved": moved}
