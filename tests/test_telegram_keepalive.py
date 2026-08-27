import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from ada.infrastructure.runtime.triggers import TriggerManager
from ada.interfaces.web.server import create_app
from ada.interfaces.web.state import (
    get_telegram_service_status,
    start_telegram_service,
    stop_telegram_service,
    restart_telegram_service,
)
from ada.interfaces.web.doctor import HealthDoctor


def test_telegram_watchdog_auto_recovers_when_process_dies():
    """Verify that TriggerManager watchdog/reconcile resurrects a crashed Telegram bot."""
    project_root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as directory:
        marker = str(project_root / "telegram" / "bot.py")
        command = [sys.executable, "-c", "import time; time.sleep(60)", marker]
        config = {"telegram": {"enabled": True, "token": "test-keepalive-token"}}
        config_path = Path(directory) / "config.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")

        manager = TriggerManager(
            config,
            project_root,
            config_path=config_path,
            state_dir=directory,
            telegram_command=command,
            discover_existing=False,
        )

        started = manager.start("telegram")
        assert started["ok"] is True
        assert started["running"] is True
        pid1 = started["pid"]

        # Simulate process crash / kill
        import psutil
        proc = psutil.Process(pid1)
        proc.terminate()
        proc.wait(timeout=2)

        # Status immediately shows recovering because desired_state is running
        status_after_crash = manager.telegram_status()
        assert status_after_crash["running"] is False
        assert status_after_crash["desired_state"] == "running"
        assert status_after_crash["status"] == "recovering"

        # Reconcile will automatically restart the process
        manager._last_start_attempt = 0.0  # bypass cooldown
        reconciled = manager.reconcile()
        assert reconciled["ok"] is True
        assert reconciled["running"] is True
        pid2 = reconciled["pid"]
        assert pid2 != pid1

        # Clean up
        manager.stop("telegram")


def test_telegram_stays_stopped_after_explicit_stop():
    """Verify that when the user explicitly stops Telegram, the watchdog does not resurrect it."""
    project_root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as directory:
        marker = str(project_root / "telegram" / "bot.py")
        command = [sys.executable, "-c", "import time; time.sleep(60)", marker]
        config = {"telegram": {"enabled": True, "token": "test-keepalive-token"}}
        config_path = Path(directory) / "config.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")

        manager = TriggerManager(
            config,
            project_root,
            config_path=config_path,
            state_dir=directory,
            telegram_command=command,
            discover_existing=False,
        )

        manager.start("telegram")
        stopped = manager.stop("telegram", persist=True)
        assert stopped["running"] is False
        assert stopped["desired_state"] == "stopped"

        # Calling reconcile should NOT start it
        after_reconcile = manager.reconcile()
        assert after_reconcile["running"] is False
        assert after_reconcile["desired_state"] == "stopped"


def test_state_telegram_helpers_integrate_with_gestor_runtime():
    """Verify state.py helpers correctly reflect and control TriggerManager state."""
    with tempfile.TemporaryDirectory() as directory:
        test_cfg = {
            "allowed_roots": ["/tmp"],
            "db_path": ":memory:",
            "trigger_state_dir": directory,
            "discover_external_triggers": False,
            "telegram": {"enabled": False, "token": ""},
        }
        app = create_app(test_cfg, config_path=Path(directory) / "config.json")
        with app.app_context():
            with patch("ada.interfaces.web.state.resolve_telegram_token", return_value="fake_token_1234567890"):
                status = get_telegram_service_status()
                assert status["configured"] is True
                assert status["token_masked"] == "fake_t...7890"
                assert status["running"] is False

                # Start mock
                with patch.object(app.extensions["ada_runtime"]["trigger_manager"], "start", return_value={"ok": True, "running": True, "pid": 9999}):
                    res = start_telegram_service()
                    assert res["ok"] is True

                # Stop mock
                with patch.object(app.extensions["ada_runtime"]["trigger_manager"], "stop", return_value={"ok": True, "running": False}):
                    res = stop_telegram_service()
                    assert res["ok"] is True


def test_doctor_telegram_auto_fix():
    """Verify HealthDoctor checks telegram and executes start/restart fixes."""
    doctor = HealthDoctor(agent=None, config={"telegram": {"enabled": True, "token": "test-token"}})
    with patch("ada.interfaces.web.state.get_telegram_service_status", return_value={"running": False, "token_set": True, "status": "stopped"}):
        item = doctor._check_telegram()
        assert item.status == "warning"
        assert item.can_auto_fix is True
        assert item.fix_action_id == "start_telegram"

    with patch("ada.interfaces.web.state.start_telegram_service", return_value={"ok": True}):
        res = doctor.fix_action("start_telegram")
        assert res["ok"] is True


def test_telegram_rest_endpoints_and_logs():
    """Verify Flask REST endpoints for telegram (/status, /start, /stop, /restart, /logs)."""
    with tempfile.TemporaryDirectory() as directory:
        test_cfg = {
            "allowed_roots": ["/tmp"],
            "db_path": ":memory:",
            "trigger_state_dir": directory,
            "discover_external_triggers": False,
            "telegram": {"enabled": False, "token": "dummy-token"},
        }
        app = create_app(test_cfg, config_path=Path(directory) / "config.json")
        client = app.test_client()

        # CSRF token
        client.get("/").close()
        csrf_token = client.get_cookie("ada_csrf").value
        headers = {"X-ADA-Token": csrf_token, "Content-Type": "application/json"}

        # Status
        res = client.get("/api/telegram/status")
        assert res.status_code == 200
        data = res.get_json()
        assert "running" in data
        assert data["survives_dashboard_restart"] is True

        # Start via API
        with patch.object(app.extensions["ada_runtime"]["trigger_manager"], "start", return_value={"ok": True, "running": True, "pid": 12345}):
            res = client.post("/api/telegram/start", headers=headers)
            assert res.status_code == 200
            assert res.get_json().get("ok") is True

        # Restart via API
        with patch.object(app.extensions["ada_runtime"]["trigger_manager"], "restart", return_value={"ok": True, "running": True, "pid": 12346}):
            res = client.post("/api/telegram/restart", headers=headers)
            assert res.status_code == 200
            assert res.get_json().get("ok") is True

        # Logs via API
        res = client.get("/api/telegram/logs")
        assert res.status_code == 200
        assert "logs" in res.get_json()

        # Stop via API
        with patch.object(app.extensions["ada_runtime"]["trigger_manager"], "stop", return_value={"ok": True, "running": False}):
            res = client.post("/api/telegram/stop", headers=headers)
            assert res.status_code == 200
            assert res.get_json().get("ok") is True


def test_watchdog_thread_lifecycle():
    """Verify that start_watchdog starts a daemon thread and multiple calls return the same thread."""
    project_root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as directory:
        manager = TriggerManager(
            {"telegram": {"enabled": False, "token": ""}},
            project_root,
            state_dir=directory,
            discover_existing=False,
        )
        t1 = manager.start_watchdog(interval=2.0)
        assert t1 is not None
        assert t1.is_alive()
        assert t1.daemon is True

        t2 = manager.start_watchdog(interval=2.0)
        assert t2 is t1

        # Stop watchdog
        manager._watchdog_stop.set()
        t1.join(timeout=1.0)
        assert not t1.is_alive()
