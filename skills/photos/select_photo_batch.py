"""Batch orchestration built on the same single-photo multi-agent workflow."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from skills.photos.analyze_photo import IMAGE_EXTENSIONS


def run(args):
    root = Path(args.get('path') or args.get('folder') or '').expanduser()
    if not root.is_dir():
        return {'error': 'folder not found', 'path': str(root)}
    files = sorted(p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)
    if not files:
        return {'error': 'no images found', 'path': str(root)}
    # Import lazily so skill discovery remains independent from agent startup.
    from agents import MultiAgentCoordinator
    config = dict(args.get('config') or {})
    config.setdefault('agent_max_workers', int(args.get('workers', 2)))
    coordinator = MultiAgentCoordinator(config)
    records, failures, xmp_written = [], [], []

    def analyze(path):
        return coordinator.analyze_photo({
            'path': str(path),
            'folder': str(root),
            'vision': args.get('vision', True),
            'write_xmp': args.get('write_xmp', False),
        })

    with ThreadPoolExecutor(max_workers=max(1, int(args.get('workers', 2)))) as pool:
        futures = {pool.submit(analyze, path): path for path in files}
        for future in as_completed(futures):
            path = futures[future]
            try:
                result = future.result()
                records.append(result)
                if result.get('xmp'):
                    # The single-photo coordinator has already written this
                    # sidecar before returning; no end-of-batch flush exists.
                    xmp_written.append(result['xmp'])
            except Exception as exc:
                failures.append({'path': str(path), 'error': str(exc)})
    selected = [item for item in records if int((item.get('review') or {}).get('selection_rating', 0) or 0) >= 3]
    rejected = [item for item in records if item not in selected]
    return {
        'ok': not failures,
        'workflow': 'photo_batch_selection',
        'path': str(root),
        'scanned': len(files),
        'completed': len(records),
        'failed': failures,
        'selected_count': len(selected),
        'rejected_count': len(rejected),
        'selected': selected,
        'rejected': rejected,
        'xmp_written': xmp_written,
        'decision_mode': 'same_multi_agent_photo_review_per_file',
    }
