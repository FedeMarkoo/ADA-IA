"""Always-on autonomy worker built from the durable event bus and watchers."""

import logging
import time

from ada.application.agent import Agent
from ada.application.services.autonomy import AutonomyService
from ada.config import load_config
from ada.infrastructure.runtime.event_bus import EventBus
from ada.infrastructure.runtime.scheduler import Scheduler
from ada.infrastructure.runtime.watchers import FolderWatcher

logger = logging.getLogger("ada.daemon")


def run(config=None):
    config = config or load_config()
    agent = Agent(config)
    autonomy = AutonomyService(agent, config)
    bus = EventBus(agent.mem)

    def handle_event(topic, payload):
        if topic == "filesystem.file_created":
            logger.info("new_file path=%s", payload.get("path"))
        return autonomy.handle(topic, payload)

    topics = set((config.get("event_rules") or {})) | {"filesystem.file_created"}
    handlers = {topic: (lambda payload, topic=topic: handle_event(topic, payload)) for topic in topics}
    scheduler = Scheduler(agent.mem, handlers, interval=config.get("scheduler_interval", 2))
    watchers = [FolderWatcher(folder, bus) for folder in config.get("watch_folders", [])]
    backup_interval = max(0.0, float(config.get("backup_interval_seconds", 0)))
    next_backup = time.monotonic() + backup_interval if backup_interval else None
    while True:
        for watcher in watchers:
            watcher.scan()
        scheduler.run_once()
        if next_backup is not None and time.monotonic() >= next_backup:
            backup_path = config.get("backup_path") or str(agent.mem.db_path) + ".backup"
            try:
                agent.mem.backup_to(backup_path)
                logger.info("memory_backup_created path=%s", backup_path)
            except Exception:
                logger.exception("memory_backup_failed path=%s", backup_path)
            next_backup = time.monotonic() + backup_interval
        time.sleep(max(0.1, float(config.get("watch_interval", 5))))
