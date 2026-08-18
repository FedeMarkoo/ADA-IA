"""Conservative burst detection for photo batches.

Filename sequence numbers are only a candidate signal. A burst is accepted
when camera sequence metadata, capture time, or near-identical adjacent
frames provides supporting evidence.
"""
from datetime import datetime
import json
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from src.ada.capabilities.photography.analyze_photo import IMAGE_EXTENSIONS, _load_rgb

RAW_EXTENSIONS = {'.raw', '.cr2', '.nef', '.arw', '.dng', '.raf', '.orf'}
SEQUENCE_KEYS = ('SequenceNumber', 'SequenceFileNumber', 'ContinuousNumber', 'ShotOrder')
BURST_KEYS = ('ReleaseMode', 'DriveMode', 'BurstMode', 'ContinuousShooting', 'ShootingMode')


def _tag(row, name):
    """Read ExifTool tags with or without their group prefix."""
    if name in row:
        return row[name]
    suffix = ':' + name
    for key, value in row.items():
        if str(key).endswith(suffix):
            return value
    return None


def _number_value(value):
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _continuous(value):
    if value in (None, ''):
        return False
    text = str(value).lower()
    return text not in {'0', 'single', 'normal', 'one shot', 'mechanical'}


def _number(path):
    match = re.search(r'(\d{1,})$', path.stem)
    return int(match.group(1)) if match else None


def _parse_datetime(value):
    if not value:
        return None
    text = str(value).replace('T', ' ').split('+')[0].rstrip('Z')
    for fmt in ('%Y:%m:%d %H:%M:%S.%f', '%Y:%m:%d %H:%M:%S',
                '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _exiftool_metadata(files):
    """Read MakerNotes when ExifTool is installed; otherwise return no data."""
    executable = shutil.which('exiftool')
    if not executable or not files:
        return {}
    try:
        result = subprocess.run(
            [executable, '-j', '-n', '-a', '-G1', '-s', *[str(p) for p in files]],
            capture_output=True, text=True, timeout=90, check=True)
        rows = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError):
        return {}
    return {str(Path(row.get('SourceFile', ''))): row for row in rows}


def _raw_metadata(path):
    data = {}
    if path.suffix.lower() not in RAW_EXTENSIONS:
        return data
    try:
        import rawpy
        with rawpy.imread(str(path)) as raw:
            other = raw.other
            for key in ('timestamp', 'shot_order', 'iso_speed'):
                value = getattr(other, key, None)
                if value not in (None, ''):
                    data[key] = value
    except Exception:
        pass
    return data


def _visual_similarity(left, right):
    """Compare small grayscale previews; robust enough for adjacent frames."""
    try:
        images = []
        for path in (left, right):
            try:
                image = _load_rgb(path).convert('L')
            except Exception:
                # Keeps the detector testable with preview-like fixtures and
                # supports cameras whose embedded preview is readable by PIL.
                image = Image.open(path).convert('L')
            image.thumbnail((64, 64), Image.Resampling.BILINEAR)
            canvas = Image.new('L', (64, 64), 0)
            canvas.paste(image, ((64 - image.width) // 2, (64 - image.height) // 2))
            images.append(np.asarray(canvas, dtype=np.float32) / 255.0)
        difference = float(np.mean(np.abs(images[0] - images[1])))
        return max(0.0, 1.0 - difference)
    except Exception:
        return None


def detect_burst_groups(files):
    """Return groups with evidence and a short diagnostic summary."""
    files = sorted(Path(path) for path in files if Path(path).suffix.lower() in IMAGE_EXTENSIONS)
    maker = _exiftool_metadata(files)
    metadata = {}
    for path in files:
        row = maker.get(str(path), {})
        metadata[path] = {'maker': row, 'raw': _raw_metadata(path)}

    candidates = []
    numbered = [(path, _number(path)) for path in files]
    numbered = [(path, number) for path, number in numbered if number is not None]
    numbered.sort(key=lambda item: (str(item[0].parent), item[1]))
    for index, (left, left_number) in enumerate(numbered):
        for right, right_number in numbered[index + 1:]:
            if right.parent != left.parent or right_number - left_number > 4:
                break
            candidates.append((left, right))

    groups = []
    evidence = []
    for left, right in candidates:
        left_meta, right_meta = metadata[left], metadata[right]
        left_tags, right_tags = left_meta['maker'], right_meta['maker']
        sequence_signal = False
        for key in SEQUENCE_KEYS:
            left_value = _number_value(_tag(left_tags, key))
            right_value = _number_value(_tag(right_tags, key))
            if left_value is not None and right_value is not None and abs(right_value - left_value) == 1:
                sequence_signal = True
                break
        mode_signal = any(
            _continuous(_tag(left_tags, key)) and _continuous(_tag(right_tags, key))
            for key in BURST_KEYS
        )
        times = []
        for item in (left_meta['raw'], right_meta['raw']):
            times.append(_parse_datetime(item.get('timestamp')))
        time_signal = bool(times[0] and times[1] and abs((times[1] - times[0]).total_seconds()) <= 1.0)
        similarity = _visual_similarity(left, right)
        visual_signal = similarity is not None and similarity >= 0.985
        if sequence_signal or mode_signal or time_signal or visual_signal:
            groups.append({left, right})
            evidence.append({'files': [str(left), str(right)],
                             'signals': [name for name, value in (
                                 ('maker_sequence', sequence_signal), ('maker_mode', mode_signal),
                                 ('capture_time', time_signal), ('visual_similarity', visual_signal)) if value],
                             'similarity': round(similarity, 4) if similarity is not None else None})

    merged = []
    for group in groups:
        for existing in merged:
            if group & existing:
                existing.update(group)
                break
        else:
            merged.append(set(group))
    return merged, {'exiftool': bool(maker), 'candidate_pairs': len(candidates), 'evidence': evidence}
