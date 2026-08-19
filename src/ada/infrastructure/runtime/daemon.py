"""Always-on autonomy worker built from the durable event bus and watchers."""

import logging
import time

from src.ada.application.agent import Agent
from src.ada.application.services.autonomy import AutonomyService
from src.ada.config import load_config
from src.ada.infrastructure.runtime.event_bus import EventBus
from src.ada.infrastructure.runtime.scheduler import Scheduler
from src.ada.infrastructure.runtime.watchers import FolderWatcher

logger = logging.getLogger("ada.daemon")


def run(config=None):
    config = config or load_config()
    agent = Agent(config)
    autonomy = AutonomyService(agent, config)
    bus = EventBus(agent.mem)

    def file_created(payload):
        logger.info("new_file path=%s", payload.get("path"))
        return autonomy.handle("filesystem.file_created", payload)

    scheduler = Scheduler(
        agent.mem, {"filesystem.file_created": file_created}, interval=config.get("scheduler_interval", 2)
    )
    watchers = [FolderWatcher(folder, bus) for folder in config.get("watch_folders", [])]
    while True:
        for watcher in watchers:
            watcher.scan()
        scheduler.run_once()
        time.sleep(max(0.1, float(config.get("watch_interval", 5))))
