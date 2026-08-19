"""Batch orchestration built on the same single-photo multi-agent workflow."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import re

from src.ada.capabilities.photography.analyze_photo import IMAGE_EXTENSIONS
from src.ada.capabilities.photography.burst_detection import detect_burst_groups
from src.ada.capabilities.photography.xmp import mark_xmp_label, repair_photo_xmp, write_photo_xmp
from src.ada.infrastructure.runtime.resources import wait_for_cpu_budget


def _burst_groups(files):
    """Compatibility wrapper returning only groups."""
    return detect_burst_groups(files)[0]


def _stored_review(path):
    sidecar = Path(path).with_suffix('.xmp')
    if not sidecar.is_file():
        return {'status': 'Rechazada', 'score': 0.0}
    content = sidecar.read_text(encoding='utf-8', errors='ignore')
    status = re.search(r'ada:Status="([^"]+)"', content)
    score = re.search(r'ada:Score="([^"]+)"', content)
    rating = re.search(r'xmp:Rating="([^"]+)"', content)
    try:
        numeric_score = float(score.group(1)) if score else float(rating.group(1) or 0) * 2
    except (TypeError, ValueError):
        numeric_score = 0.0
    return {
        'status': status.group(1) if status else 'Rechazada',
        'score': numeric_score,
    }


def _feedback_label(path):
    name = Path(path).name.upper()
    if name.startswith('OK__'):
        return 'selected'
    if name.startswith('RECH__'):
        return 'rejected'
    return None


def _demote_burst_duplicates(burst_groups, records, write_xmp=False):
    duplicates = []
    for group in burst_groups:
        paths = {str(path) for path in group}
        candidates = [item for item in records if item.get('path') in paths]
        accepted = []
        for item in candidates:
            review = item.get('review') or {}
            if int(review.get('selection_rating', 0) or 0) >= 3:
                accepted.append((item, float(review.get('selection_score', 0) or 0)))
        if not accepted:
            accepted = [
                (item, _stored_review(item.get('path'))['score'])
                for item in candidates
                if _stored_review(item.get('path'))['status'] == 'Seleccionada'
            ]
        if len(accepted) <= 1:
            continue
        labeled = [item for item, _ in accepted if _feedback_label(item.get('path')) == 'selected']
        winner = max(
            (item for item, _ in accepted if not labeled or item in labeled),
            key=lambda item: float((item.get('review') or {}).get('selection_score', 0) or _stored_review(item.get('path'))['score']),
        )
        for item, score in accepted:
            if item is winner:
                continue
            review = item.setdefault('review', {})
            review['selection_rating'] = 2
            review['selection_label'] = 'dudosa'
            review['recommendation'] = 'revisar; duplicado de ráfaga con otra toma mejor'
            review.setdefault('issues', []).append('duplicado de ráfaga; se conserva otra toma mejor')
            duplicates.append(item.get('path'))
            if write_xmp:
                write_photo_xmp(item['path'], 'Rechazada', 0, score,
                                'Duplicado de ráfaga; se conserva otra toma mejor', label='Amarillo')
    return duplicates


def run(args):
    root = Path(args.get('path') or args.get('folder') or '').expanduser()
    if not root.is_dir():
        return {'error': 'folder not found', 'path': str(root)}
    if args.get('repair_xmp') or args.get('mark_bursts'):
        sidecars = sorted(root.rglob('*.xmp'))
        repaired = [repair_photo_xmp(path) for path in sidecars] if args.get('repair_xmp') else []
        raw_files = [path for path in root.rglob('*') if path.is_file() and path.suffix.lower() in {'.raw', '.cr2', '.nef', '.arw', '.dng', '.raf', '.orf'}]
        burst_groups, burst_detection = detect_burst_groups(raw_files)
        burst_paths = {str(path) for group in burst_groups for path in group}
        burst_duplicates = _demote_burst_duplicates(
            burst_groups,
            [{'path': str(path), 'review': {
                'selection_rating': 3 if _stored_review(path)['status'] == 'Seleccionada' else 0,
                'selection_score': _stored_review(path)['score'],
            }} for path in raw_files],
            write_xmp=True,
        )
        burst_xmp = [mark_xmp_label(path, 'Amarillo') for path in raw_files if str(path) in burst_paths]
        return {'ok': True, 'workflow': 'photo_xmp_repair', 'path': str(root),
                'repaired_count': len(repaired), 'burst_count': len(burst_paths),
                'burst_duplicates_rejected': burst_duplicates,
                'burst_detection': burst_detection,
                'burst_xmp_written': burst_xmp, 'xmp_written': repaired + burst_xmp}
    files = sorted(p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)
    if not files:
        return {'error': 'no images found', 'path': str(root)}
    # Import lazily so skill discovery remains independent from agent startup.
    from src.ada.agents import MultiAgentCoordinator
    config = dict(args.get('config') or {})
    # A batch must yield between files without waiting indefinitely for a
    # noisy system load average. The worker/thread limit still enforces the
    # configured CPU policy; this only bounds admission latency.
    config.setdefault('cpu_throttle_max_wait_seconds', 2.0)
    config.setdefault('agent_max_workers', int(args.get('workers', config.get('photo_workers', 1))))
    coordinator = MultiAgentCoordinator(config)
    records, failures, xmp_written = [], [], []

    def analyze(path):
        wait_for_cpu_budget(config)
        return coordinator.analyze_photo({
            'path': str(path),
            'folder': str(root),
            'vision': args.get('vision', True),
            'write_xmp': args.get('write_xmp', False),
        })

    max_workers = max(1, int(args.get('workers', config.get('photo_workers', 1))))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
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
    burst_groups, burst_detection = detect_burst_groups(files)
    burst_paths = {str(path) for group in burst_groups for path in group}
    burst_duplicates = _demote_burst_duplicates(burst_groups, records, write_xmp=args.get('write_xmp', False))
    selected = [item for item in records if int((item.get('review') or {}).get('selection_rating', 0) or 0) >= 3]
    rejected = [item for item in records if item not in selected]
    burst_xmp = []
    if args.get('write_xmp'):
        burst_xmp = [mark_xmp_label(path, 'Amarillo') for path in files if str(path) in burst_paths]
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
        'burst_count': len(burst_paths),
        'burst_duplicates_rejected': burst_duplicates,
        'burst_detection': burst_detection,
        'burst_xmp_written': burst_xmp,
        'decision_mode': 'same_multi_agent_photo_review_per_file',
    }
