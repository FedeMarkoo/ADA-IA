"""General filesystem tool used by ADA workflows.

Read operations are safe by default. Mutating operations require the agent to
pass confirm=True and return an auditable report.
"""
import os
import shutil
from pathlib import Path


IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.heic', '.tif', '.tiff', '.raw', '.cr2', '.nef', '.arw'}
SKIP_PARTS = {'.venv', 'node_modules', '.git', '__pycache__'}


def _path(value):
    return Path(os.path.expanduser(str(value or ''))).resolve()


def _files(root, recursive=True):
    paths = root.rglob('*') if recursive else root.iterdir()
    return [p for p in paths if p.is_file() and not p.name.startswith('.') and not any(part in SKIP_PARTS for part in p.parts)]


def run(args):
    action = str(args.get('action', 'list_files')).lower()
    root = _path(args.get('dir') or args.get('source'))
    recursive = bool(args.get('recursive', True))
    if action in {'list_files', 'list_dirs', 'search'} and not root.is_dir():
        return {'error': 'dir not found', 'dir': str(root)}

    if action == 'list_files':
        extensions = {str(x).lower() if str(x).startswith('.') else '.' + str(x).lower() for x in args.get('extensions', [])}
        items = _files(root, recursive)
        if extensions:
            items = [p for p in items if p.suffix.lower() in extensions]
        return {'ok': True, 'action': action, 'dir': str(root), 'count': len(items), 'files': [str(p) for p in sorted(items)]}

    if action == 'list_dirs':
        paths = root.rglob('*') if recursive else root.iterdir()
        items = sorted(p for p in paths if p.is_dir() and not p.name.startswith('.') and not any(part in SKIP_PARTS for part in p.parts))
        return {'ok': True, 'action': action, 'dir': str(root), 'count': len(items), 'dirs': [str(p) for p in items]}

    if action == 'search':
        query = str(args.get('query', '')).lower()
        items = [p for p in _files(root, recursive) if query in p.name.lower()]
        return {'ok': True, 'action': action, 'dir': str(root), 'query': query, 'count': len(items), 'files': [str(p) for p in sorted(items)]}

    if action in {'move_files', 'copy_files'}:
        if not args.get('confirm'):
            return {'error': 'confirmation_required', 'action': action, 'source': str(root), 'name': args.get('name')}
        if not root.is_dir():
            return {'error': 'source not found', 'source': str(root)}
        name = str(args.get('name', '')).strip()
        if not name or Path(name).name != name or name in {'.', '..'}:
            return {'error': 'invalid destination name'}
        destination = (root.parent / name).resolve()
        if destination == root or root in destination.parents:
            return {'error': 'destination cannot be inside source'}
        destination.mkdir(parents=True, exist_ok=True)
        # Flatten files from nested folders into the destination. This makes
        # “mover todas las fotos” behave as users expect for organized trees.
        items = _files(root, recursive=True)
        changed = []
        for item in items:
            target = destination / item.name
            index = 1
            while target.exists():
                target = destination / f'{item.stem}_ada_{index}{item.suffix}'
                index += 1
            target.parent.mkdir(parents=True, exist_ok=True)
            operation = shutil.move if action == 'move_files' else shutil.copy2
            operation(str(item), str(target))
            changed.append({'from': str(item), 'to': str(target)})
        return {'ok': True, 'action': action, 'source': str(root), 'destination': str(destination), 'count': len(changed), 'changed': changed}

    if action == 'mkdir':
        if not args.get('confirm'):
            return {'error': 'confirmation_required', 'action': action}
        target = _path(args.get('path'))
        target.mkdir(parents=True, exist_ok=True)
        return {'ok': True, 'action': action, 'created': str(target)}

    return {'error': 'unsupported filesystem action', 'action': action}
