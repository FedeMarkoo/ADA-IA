"""Scalable first-pass selection for large event folders.

This stage is local and deterministic. It scans every image, groups near-
identical adjacent frames, and returns a shortlist for the visual agent. It
does not move or delete files.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
from PIL import ImageOps

from skills.photos.analyze_photo import IMAGE_EXTENSIONS, _load_rgb, technical_analysis


def _signature(path):
    image = ImageOps.exif_transpose(_load_rgb(path)).convert('L')
    image.thumbnail((32, 32))
    image = image.resize((16, 16))
    values = np.asarray(image, dtype=np.float32)
    return (values >= float(values.mean())).reshape(-1)


def _hamming(left, right):
    return int(np.count_nonzero(left != right))


def _analyze(path):
    result = technical_analysis(path)
    result['_signature'] = _signature(path)
    return result


def run(args):
    root = Path(args.get('path') or args.get('folder') or '').expanduser()
    if not root.is_dir():
        return {'error': 'folder not found', 'path': str(root)}
    files = sorted(p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)
    if not files:
        return {'error': 'no images found', 'path': str(root)}
    workers = max(1, int(args.get('workers', 4)))
    records, failures = [], []
    with ThreadPoolExecutor(max_workers=min(workers, len(files))) as pool:
        futures = {pool.submit(_analyze, path): path for path in files}
        for future in as_completed(futures):
            path = futures[future]
            try:
                records.append({'path': str(path), 'technical': future.result()})
            except Exception as exc:
                failures.append({'path': str(path), 'error': str(exc)})
    records.sort(key=lambda item: item['path'])

    groups = []
    for record in records:
        signature = record['technical'].pop('_signature')
        record['signature'] = signature
        if groups and _hamming(signature, groups[-1][-1]['signature']) <= int(args.get('duplicate_distance', 10)):
            groups[-1].append(record)
        else:
            groups.append([record])
    representatives, duplicates = [], []
    for group in groups:
        best = max(group, key=lambda item: item['technical'].get('overall_score', 0))
        best['duplicate_count'] = len(group)
        representatives.append(best)
        duplicates.extend(item['path'] for item in group if item is not best)
    target = max(1, int(args.get('target', 300)))
    representatives.sort(key=lambda item: item['technical'].get('overall_score', 0), reverse=True)
    selected = representatives[:target]
    for item in selected:
        item.pop('signature', None)
    return {
        'ok': True,
        'workflow': 'photo_batch_selection',
        'path': str(root),
        'scanned': len(files),
        'failed': failures,
        'burst_groups': len(groups),
        'duplicate_candidates': len(duplicates),
        'representatives': len(representatives),
        'target': target,
        'selected': selected,
        'next_stage': 'Enviar selected a ContextPhotoAgent para validar momento, sujeto y cobertura del evento.',
    }
