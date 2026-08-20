"""Knowledge loading and retrieval preparation for the application layer."""

import logging
import os
from pathlib import Path

logger = logging.getLogger("ada.knowledge")


class KnowledgeLoader:
    def __init__(self, memory):
        self.memory = memory

    def load_files(self, filenames):
        loaded = 0
        for filename in filenames or []:
            try:
                path = Path(os.path.expanduser(str(filename)))
                if not path.exists():
                    logger.warning("knowledge_file_missing file=%s", filename)
                    continue
                marker = f"[ADA knowledge: {path.name}]"
                if any(marker in item for item in self.memory.knowledge()):
                    continue
                self.memory.add_knowledge(marker, marker + "\n" + path.read_text(encoding="utf-8"), source=str(path))
                loaded += 1
            except (OSError, UnicodeError) as exc:
                logger.warning("knowledge_load_failed file=%s error=%s", filename, exc)
        return loaded
