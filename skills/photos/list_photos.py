"""Read-only photo listing skill."""
import os
from pathlib import Path

EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.heic', '.tif', '.tiff', '.raw', '.cr2', '.nef', '.arw'}


def run(args):
    folder = os.path.expanduser(args.get('dir', ''))
    if not folder:
        return {'error': 'no dir provided'}
    root = Path(folder)
    if not root.is_dir():
        return {'error': 'dir not found', 'dir': str(root)}
    photos = sorted(str(path) for path in root.rglob('*') if path.is_file() and path.suffix.lower() in EXTENSIONS)
    return {'ok': True, 'dir': str(root.resolve()), 'count': len(photos), 'photos': photos}
