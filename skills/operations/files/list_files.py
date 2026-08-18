"""Read-only file listing."""
import os
from pathlib import Path


def run(args):
    folder = Path(os.path.expanduser(args.get('dir', '')))
    if not folder.is_dir():
        return {'error': 'dir not found', 'dir': str(folder)}
    recursive = bool(args.get('recursive', False))
    files = sorted(p for p in (folder.rglob('*') if recursive else folder.iterdir()) if p.is_file() and not p.name.startswith('.') and '.venv' not in p.parts and 'node_modules' not in p.parts)
    return {'ok': True, 'dir': str(folder.resolve()), 'count': len(files), 'files': [str(p) for p in files]}
