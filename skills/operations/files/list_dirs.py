"""Read-only directory listing."""
import os
from pathlib import Path


def run(args):
    folder = Path(os.path.expanduser(args.get('dir', '')))
    if not folder.is_dir():
        return {'error': 'dir not found', 'dir': str(folder)}
    recursive = bool(args.get('recursive', False))
    dirs = sorted(p for p in (folder.rglob('*') if recursive else folder.iterdir()) if p.is_dir() and not p.name.startswith('.') and p.name not in {'.venv', 'node_modules'})
    return {'ok': True, 'dir': str(folder.resolve()), 'count': len(dirs), 'dirs': [str(p) for p in dirs]}
