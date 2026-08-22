import json
import logging
from pathlib import Path
import signal
import threading
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

    stop_event = threading.Event()

    def handle_signal(signum, frame):
        logger.info("daemon_shutdown_signal received=%s", signum)
        stop_event.set()

    try:
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
    except (ValueError, AttributeError):
        # Signals can only be set from the main thread
        pass

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

    logger.info("ada_daemon_started watch_folders=%d", len(watchers))
    while not stop_event.is_set():
        for watcher in watchers:
            try:
                watcher.scan()
            except Exception as exc:
                logger.warning("watcher_scan_failed folder=%s error=%s", getattr(watcher, "folder", "?"), exc)
        try:
            scheduler.run_once()
        except Exception as exc:
            logger.warning("scheduler_cycle_failed error=%s", exc)

        if next_backup is not None and time.monotonic() >= next_backup:
            backup_path = config.get("backup_path") or str(agent.mem.db_path) + ".backup"
            try:
                agent.mem.backup_to(backup_path)
                logger.info("memory_backup_created path=%s", backup_path)
            except Exception:
                logger.exception("memory_backup_failed path=%s", backup_path)
            next_backup = time.monotonic() + backup_interval

        # Write daemon health heartbeat
        health_path = config.get("daemon_health_path")
        if not health_path and agent.mem and getattr(agent.mem, "db_path", None):
            health_path = str(Path(agent.mem.db_path).parent / "daemon-health.json")
        if health_path:
            try:
                Path(health_path).parent.mkdir(parents=True, exist_ok=True)
                tmp_health = Path(health_path).with_suffix(".tmp")
                tmp_health.write_text(
                    json.dumps({
                        "status": "running",
                        "updated_at": time.time(),
                        "watchers": len(watchers),
                    }),
                    encoding="utf-8"
                )
                tmp_health.replace(health_path)
            except Exception:
                pass

        stop_event.wait(max(0.1, float(config.get("watch_interval", 5))))

    logger.info("ada_daemon_stopped")
