"""Portable polling watcher that emits events for newly discovered files."""

from pathlib import Path


class FolderWatcher:
    def __init__(self, folder, event_bus, topic="filesystem.file_created", recursive=True):
        self.folder = Path(folder).expanduser().resolve()
        self.event_bus = event_bus
        self.topic = topic
        self.recursive = recursive
        self._seen = set()
        self._initialized = False

    def scan(self):
        if not self.folder.is_dir():
            return 0
        paths = self.folder.rglob("*") if self.recursive else self.folder.iterdir()
        current = {str(path) for path in paths if path.is_file() and not path.name.startswith(".")}
        fresh = current - self._seen if self._initialized else set()
        self._seen = current
        self._initialized = True
        for path in sorted(fresh):
            self.event_bus.publish(self.topic, {"path": path})
        return len(fresh)
