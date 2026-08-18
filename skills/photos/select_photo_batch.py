"""Scalable first-pass selection for large event folders.

This stage is local and deterministic. It scans every image, groups near-
identical adjacent frames, and returns a shortlist for the visual agent. It
does not move or delete files.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import re

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


def _write_xmp(path, status, rating, score, reason):
    """Create or update only ADA's fields while preserving an existing XMP."""
    sidecar = Path(path).with_suffix('.xmp')
    content = sidecar.read_text(encoding='utf-8', errors='ignore') if sidecar.is_file() else (
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
        ' <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
        '  <rdf:Description xmlns:xmp="http://ns.adobe.com/xap/1.0/" rdf:about=""/>\n'
        ' </rdf:RDF>\n</x:xmpmeta>\n'
    )
    attributes = {
        'xmp:Rating': str(rating if status == 'Seleccionada' else 0),
        'xmp:Label': status,
        'ada:Status': status,
        'ada:Score': f'{score:.2f}',
        'ada:Reason': reason,
    }
    if 'xmlns:ada=' not in content:
        content = content.replace('<rdf:Description',
                                  '<rdf:Description xmlns:ada="https://ada.local/ns/1.0/"', 1)
    if 'xmlns:xmp=' not in content:
        content = content.replace('<rdf:Description',
                                  '<rdf:Description xmlns:xmp="http://ns.adobe.com/xap/1.0/"', 1)
    for key, value in attributes.items():
        escaped = value.replace('&', '&amp;').replace('"', '&quot;')
        pattern = rf'{re.escape(key)}="[^"]*"'
        replacement = f'{key}="{escaped}"'
        if re.search(pattern, content):
            content = re.sub(pattern, replacement, content, count=1)
        else:
            content = content.replace('<rdf:Description ', f'<rdf:Description {replacement} ', 1)
    sidecar.write_text(content, encoding='utf-8')
    return str(sidecar)


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
    selected_paths = {item['path'] for item in selected}
    xmp_written = []
    if args.get('write_xmp'):
        # Write a sidecar for every scanned file, including duplicate frames,
        # so Lightroom can show the decision on every original.
        for item in records:
            score = float(item['technical'].get('overall_score', 0) or 0)
            selected_item = item['path'] in selected_paths
            rating = max(1, min(5, round(score / 2))) if selected_item else 0
            status = 'Seleccionada' if selected_item else 'Rechazada'
            reason = 'Incluida en la shortlist de ADA' if selected_item else 'Fuera de la shortlist preliminar'
            xmp_written.append(_write_xmp(item['path'], status, rating, score, reason))
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
        'xmp_written': xmp_written,
        'next_stage': 'Enviar selected a ContextPhotoAgent para validar momento, sujeto y cobertura del evento.',
    }
