"""Daily Google Calendar digest delivery through Telegram."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional


class CalendarTelegramDigest:
    """Build and deliver a read-only seven-day Calendar summary."""

    def __init__(
        self, mcp_manager, telegram_sender: Callable[[str, str], Any], config: Optional[Dict[str, Any]] = None
    ):
        self.mcp_manager = mcp_manager
        self.telegram_sender = telegram_sender
        self.config = config or {}

    def chat_id(self) -> str:
        cron = (self.config.get("triggers") or {}).get("cron") or {}
        job = cron.get("calendar_weekly_digest") or {}
        telegram = self.config.get("telegram") or {}
        configured = job.get("chat_id") or telegram.get("digest_chat_id")
        configured = configured or os.environ.get("TELEGRAM_DIGEST_CHAT_ID", "")
        if not configured:
            allowed = telegram.get("allowed_chat_ids") or []
            if isinstance(allowed, (list, tuple)) and len(allowed) == 1:
                configured = allowed[0]
        return str(configured or "").strip()

    @staticmethod
    def _window(now: Optional[datetime] = None):
        current = now or datetime.now().astimezone()
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        start = current.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, start + timedelta(days=7)

    @staticmethod
    def _payload(result: Dict[str, Any]) -> Dict[str, Any]:
        if result.get("ok") is False:
            return {"error": result.get("error", "calendar_mcp_failed")}
        payload = result.get("result") if result.get("ok") is True else result
        return payload if isinstance(payload, dict) else {"error": "invalid_calendar_result"}

    @staticmethod
    def _event_line(event: Dict[str, Any]) -> str:
        title = event.get("summary") or event.get("title") or "(sin título)"
        start = event.get("start") or {}
        if isinstance(start, dict):
            when = start.get("dateTime") or start.get("date") or "fecha no informada"
        else:
            when = str(start or "fecha no informada")
        calendar = event.get("calendar") or event.get("calendarName")
        suffix = f" — {calendar}" if calendar else ""
        return f"• {title} — {when}{suffix}"

    def _message(self, events, start: datetime, end: datetime) -> str:
        heading = f"Eventos de los próximos 7 días ({start.date()} a {(end - timedelta(days=1)).date()}):"
        if not events:
            return heading + "\nNo hay eventos agendados en ese período."
        return heading + "\n" + "\n".join(self._event_line(event) for event in events[:50])

    def run_once(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        chat_id = self.chat_id()
        if not chat_id:
            return {"ok": False, "error": "missing_telegram_digest_chat_id"}
        if not self.mcp_manager:
            return {"ok": False, "error": "missing_calendar_mcp"}

        start, end = self._window(now)
        parameters = {
            "timeMin": start.isoformat(),
            "timeMax": end.isoformat(),
            "singleEvents": True,
            "orderBy": "startTime",
            "maxResults": 50,
        }
        result = self.mcp_manager.execute_tool("google_calendar.list_events", parameters)
        payload = self._payload(result)
        if payload.get("error"):
            return {"ok": False, "error": payload["error"], "mcp": result}
        events = payload.get("items") or payload.get("events") or []
        if not isinstance(events, list):
            return {"ok": False, "error": "invalid_calendar_events_payload", "mcp": result}

        message = self._message(events, start, end)
        try:
            self.telegram_sender(chat_id, message)
        except Exception as exc:
            return {"ok": False, "error": "telegram_send_failed", "detail": str(exc), "mcp": result}
        return {
            "ok": True,
            "chat_id": chat_id,
            "event_count": len(events),
            "message": message,
            "window": {"timeMin": start.isoformat(), "timeMax": end.isoformat()},
            "mcp": result,
        }


def cron_due(now: datetime, last_run_date: Optional[str], hour: int = 8, minute: int = 0) -> bool:
    """Return true once the configured daily wall-clock slot is reached."""
    # The caller supplies the wall-clock timezone used by the schedule. Do
    # not silently convert an aware test/configuration time to the host zone.
    current = now
    slot_reached = (current.hour, current.minute) >= (hour, minute)
    return slot_reached and last_run_date != current.date().isoformat()
