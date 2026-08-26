import json
import logging
from pathlib import Path
import signal
import threading
import time
from datetime import datetime

from ada.application.agent import Agent
from ada.application.services.autonomy import AutonomyService
from ada.config import load_config
from ada.infrastructure.runtime.event_bus import EventBus
from ada.infrastructure.runtime.scheduler import Scheduler
from ada.infrastructure.runtime.watchers import FolderWatcher
from ada.infrastructure.runtime.calendar_digest import CalendarTelegramDigest, cron_due
from ada.application.services.transport_alert import TransportTelegramAlert
from ada.mcps.manager import MCPManager
from telegram.bot import TelegramListener
from ada.infrastructure.update import UpdateManager

logger = logging.getLogger("ada.daemon")


def run(config=None):
    config = config or load_config()
    mcp_manager = MCPManager(config)
    agent = Agent(config, mcp_manager=mcp_manager)
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
    update_manager = UpdateManager(config) if (config.get("update") or {}).get("enabled") else None
    if update_manager is not None:
        # If this process was started by the commit autorestart, finish the
        # existing Telegram message instead of sending a second notification.
        update_manager.finalize_restart_notification(success=True)
    update_interval = max(300.0, float((config.get("update") or {}).get("check_interval_seconds", 3600)))
    next_update_check = time.monotonic() if update_manager else None
    cron_config = (config.get("triggers") or {}).get("cron") or {}
    digest_config = cron_config.get("calendar_weekly_digest") or {}
    digest = None
    last_digest_date = None
    transport_alert = None
    last_transport_date = None
    status_config = cron_config.get("sarmiento_status") or {}
    if cron_config.get("enabled") and (digest_config.get("enabled") or status_config.get("enabled")):
        telegram = TelegramListener(config)
        if digest_config.get("enabled"):
            digest = CalendarTelegramDigest(mcp_manager, telegram.send_message, config)
        if status_config.get("enabled"):
            transport_alert = TransportTelegramAlert(agent, telegram.send_message, config)

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

        if update_manager is not None and time.monotonic() >= next_update_check:
            try:
                update_result = update_manager.run_once()
                logger.info("update_check status=%s local=%s remote=%s", update_result.get("status"), update_result.get("local_sha"), update_result.get("remote_sha"))
            except Exception:
                logger.exception("update_check_failed")
            next_update_check = time.monotonic() + update_interval

        if digest is not None:
            now = datetime.now().astimezone()
            try:
                hour = int(digest_config.get("hour", 8))
                minute = int(digest_config.get("minute", 0))
            except (TypeError, ValueError):
                hour, minute = 8, 0
            if cron_due(now, last_digest_date, hour, minute):
                result = digest.run_once(now)
                last_digest_date = now.date().isoformat()
                if result.get("ok"):
                    logger.info("calendar_weekly_digest_sent chat_id=%s events=%s", result.get("chat_id"), result.get("event_count"))
                else:
                    logger.error("calendar_weekly_digest_failed error=%s", result.get("error"))

        if transport_alert is not None:
            now = datetime.now().astimezone()
            status_config = cron_config.get("sarmiento_status") or {}
            try:
                hour = int(status_config.get("hour", 13))
                minute = int(status_config.get("minute", 0))
            except (TypeError, ValueError):
                hour, minute = 13, 0
            if cron_due(now, last_transport_date, hour, minute):
                result = transport_alert.run_once(now)
                if result.get("status") != "presence_inactive":
                    last_transport_date = now.date().isoformat()
                if result.get("ok"):
                    logger.info("sarmiento_status_processed status=%s", result.get("status"))
                else:
                    logger.error("sarmiento_status_failed error=%s", result.get("error"))

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
