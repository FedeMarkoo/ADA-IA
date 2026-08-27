import json
import sys
import tempfile
from pathlib import Path

from ada.infrastructure.runtime.triggers import TriggerManager


def test_trigger_catalog_exposes_future_entry_points_without_starting_them():
    with tempfile.TemporaryDirectory() as directory:
        manager = TriggerManager(
            {"telegram": {"enabled": False, "token": ""}},
            Path(__file__).resolve().parents[1],
            state_dir=directory,
            discover_existing=False,
        )
        summary = manager.summary()

    assert [item["id"] for item in summary["triggers"]] == [
        "telegram",
        "removable-device",
        "calendar",
        "cron",
        "webhook",
    ]
    assert summary["triggers"][1]["implementation"] == "ready"
    assert summary["triggers"][1]["controllable"] is False


def test_detached_trigger_is_adopted_by_a_new_manager_instance():
    project_root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as directory:
        marker = str(project_root / "telegram" / "bot.py")
        command = [sys.executable, "-c", "import time; time.sleep(60)", marker]
        config = {"telegram": {"enabled": False, "token": "test-token"}}
        config_path = Path(directory) / "config.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        first = TriggerManager(
            config,
            project_root,
            config_path=config_path,
            state_dir=directory,
            telegram_command=command,
            discover_existing=False,
        )
        second = TriggerManager(
            config,
            project_root,
            config_path=config_path,
            state_dir=directory,
            telegram_command=command,
            discover_existing=False,
        )
        try:
            started = first.start("telegram")
            assert started["ok"] is True
            assert started["running"] is True
            assert json.loads(config_path.read_text(encoding="utf-8"))["telegram"]["enabled"] is True

            adopted = second.telegram_status()
            assert adopted["running"] is True
            assert adopted["pid"] == started["pid"]
            assert adopted["survives_dashboard_restart"] is True
        finally:
            stopped = second.stop("telegram")
            assert stopped["ok"] is True
            assert stopped["running"] is False
            assert json.loads(config_path.read_text(encoding="utf-8"))["telegram"]["enabled"] is False


def test_telegram_timeout_follows_patient_agent_configuration():
    from telegram.bot import TelegramListener

    listener = TelegramListener(
        {
            "chat_timeout_seconds": 900,
            "telegram": {"enabled": False, "token": ""},
        }
    )
    assert listener.request_timeout == 900
