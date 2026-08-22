"""Portable polling watcher that emits events for newly discovered files."""

import logging
from pathlib import Path

logger = logging.getLogger("ada.watchers")


class FolderWatcher:
    def __init__(self, folder, event_bus, topic="filesystem.file_created", recursive=True, max_seen=50000):
        self.folder = Path(folder).expanduser().resolve()
        self.event_bus = event_bus
        self.topic = topic
        self.recursive = recursive
        self.max_seen = int(max_seen)
        self._seen = set()
        self._initialized = False

    def scan(self):
        if not self.folder.is_dir():
            return 0
        current = set()
        try:
            iterator = self.folder.rglob("*") if self.recursive else self.folder.iterdir()
            for path in iterator:
                try:
                    if path.is_file() and not path.name.startswith("."):
                        current.add(str(path))
                        if len(current) >= self.max_seen:
                            break
                except (OSError, PermissionError):
                    continue
        except (OSError, PermissionError) as exc:
            logger.warning("folder_watcher_scan_error folder=%s error=%s", self.folder, exc)
            return 0

        fresh = current - self._seen if self._initialized else set()
        self._seen = current
        self._initialized = True
        for path in sorted(fresh):
            self.event_bus.publish(self.topic, {"path": path})
        return len(fresh)
