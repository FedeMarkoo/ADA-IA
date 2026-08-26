from datetime import datetime, timezone

from ada.infrastructure.runtime.calendar_digest import CalendarTelegramDigest, cron_due


class FakeMCP:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def execute_tool(self, name, parameters):
        self.calls.append((name, parameters))
        return self.result


def config(chat_id="12345"):
    return {
        "telegram": {"digest_chat_id": chat_id},
        "triggers": {"cron": {"calendar_weekly_digest": {"enabled": True}}},
    }


def test_digest_queries_real_calendar_before_sending_weekly_summary():
    mcp = FakeMCP(
        {
            "ok": True,
            "result": {
                "kind": "calendar#events",
                "items": [
                    {"summary": "Sesión", "start": {"dateTime": "2026-08-25T10:00:00-03:00"}, "calendar": "Trabajo"},
                ],
            },
        }
    )
    sent = []
    digest = CalendarTelegramDigest(mcp, lambda chat_id, text: sent.append((chat_id, text)), config())

    result = digest.run_once(datetime(2026, 8, 25, 7, 30, tzinfo=timezone.utc))

    assert result["ok"] is True
    assert mcp.calls[0][0] == "google_calendar.list_events"
    assert mcp.calls[0][1]["timeMin"].startswith("2026-08-25T00:00:00")
    assert mcp.calls[0][1]["timeMax"].startswith("2026-09-01T00:00:00")
    assert mcp.calls[0][1]["singleEvents"] is True
    assert len(sent) == 1
    assert sent[0][0] == "12345"
    assert "Sesión" in sent[0][1]
    assert "Trabajo" in sent[0][1]


def test_digest_does_not_send_when_calendar_mcp_fails():
    mcp = FakeMCP({"ok": False, "error": "calendar_auth_failed"})
    sent = []
    digest = CalendarTelegramDigest(mcp, lambda chat_id, text: sent.append((chat_id, text)), config())

    result = digest.run_once(datetime(2026, 8, 25, tzinfo=timezone.utc))

    assert result == {"ok": False, "error": "calendar_auth_failed", "mcp": mcp.result}
    assert sent == []


def test_digest_requires_explicit_telegram_destination():
    mcp = FakeMCP({"ok": True, "result": {"items": []}})
    sent = []
    digest = CalendarTelegramDigest(mcp, lambda chat_id, text: sent.append((chat_id, text)), config(chat_id=""))

    result = digest.run_once(datetime(2026, 8, 25, tzinfo=timezone.utc))

    assert result["ok"] is False
    assert result["error"] == "missing_telegram_digest_chat_id"
    assert mcp.calls == []
    assert sent == []


def test_cron_due_only_once_at_configured_daily_slot():
    now = datetime(2026, 8, 25, 8, 0, tzinfo=timezone.utc)
    assert cron_due(now, None, 8, 0) is True
    assert cron_due(now, "2026-08-25", 8, 0) is False
    assert cron_due(now.replace(minute=1), None, 8, 0) is True
    assert cron_due(now.replace(hour=7, minute=59), None, 8, 0) is False
