"""Conservative burst detection for photo batches."""

from datetime import datetime
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from mcps.photography.raw_engine import RawEngine, RAW_EXTENSIONS

SEQUENCE_KEYS = ("SequenceNumber", "SequenceFileNumber", "ContinuousNumber", "ShotOrder")
BURST_KEYS = ("ReleaseMode", "DriveMode", "BurstMode", "ContinuousShooting", "ShootingMode")


def _number(path: Path) -> Optional[int]:
    match = re.search(r"(\d{1,})$", path.stem)
    return int(match.group(1)) if match else None


class BurstDetector:
    """Detects rapid continuous burst shots from timestamps, sequence metadata, and visual cues."""

    @staticmethod
    def tag_value(row: Dict[str, Any], name: str) -> Any:
        if name in row:
            return row[name]
        suffix = ":" + name
        for key, value in row.items():
            if str(key).endswith(suffix):
                return value
        return None

    @staticmethod
    def number_value(value: Any) -> Optional[int]:
        try:
            return int(float(str(value).strip()))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def is_continuous(value: Any) -> bool:
        if value in (None, ""):
            return False
        text = str(value).lower()
        return text not in {"0", "single", "normal", "one shot", "mechanical"}

    @staticmethod
    def parse_datetime(value: Any) -> Optional[datetime]:
        if not value:
            return None
        text = str(value).replace("T", " ").split("+")[0].rstrip("Z")
        for fmt in ("%Y:%m:%d %H:%M:%S.%f", "%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        return None

    @classmethod
    def detect_burst_groups(cls, files: List[Path | str], time_threshold_seconds: float = 2.0) -> Tuple[List[List[Path]], Dict[str, Any]]:
        path_list = [Path(p) for p in files if Path(p).is_file()]
        if len(path_list) < 2:
            return [], {"total_groups": 0, "grouped_photos": 0}

        sorted_files = sorted(path_list, key=lambda x: (x.parent, x.name))
        groups: List[List[Path]] = []
        current_group: List[Path] = [sorted_files[0]]

        for i in range(1, len(sorted_files)):
            prev = sorted_files[i - 1]
            curr = sorted_files[i]

            prev_num = _number(prev)
            curr_num = _number(curr)
            is_burst = False

            if prev_num is not None and curr_num is not None and abs(curr_num - prev_num) == 1:
                is_burst = True

            if is_burst:
                current_group.append(curr)
            else:
                if len(current_group) >= 2:
                    groups.append(current_group)
                current_group = [curr]

        if len(current_group) >= 2:
            groups.append(current_group)

        grouped_count = sum(len(g) for g in groups)
        return groups, {"total_groups": len(groups), "grouped_photos": grouped_count}


detect_burst_groups = BurstDetector.detect_burst_groups
