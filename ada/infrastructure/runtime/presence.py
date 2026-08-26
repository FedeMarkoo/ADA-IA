"""Privacy-preserving presence state used by autonomous rules.

Presence is an explicit signal from a phone, webhook, geofence or Wi-Fi
detector. Tailscale can transport/authenticate that signal but is not itself a
location sensor.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional


class PresenceStore:
    def __init__(self, path: Optional[str] = None):
        default = Path.home() / "Desktop" / "ADA_Data" / "runtime" / "presence.json"
        self.path = Path(path or os.environ.get("ADA_PRESENCE_PATH", default)).expanduser()

    def set(
        self, location: str, active: bool = True, ttl_seconds: int = 7200, source: str = "unknown"
    ) -> Dict[str, Any]:
        now = time.time()
        payload = {
            "location": str(location).strip().lower(),
            "active": bool(active),
            "source": str(source),
            "updated_at": now,
            "expires_at": now + max(1, int(ttl_seconds)) if active else now,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix="presence-", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, ensure_ascii=False)
            os.replace(temporary_name, self.path)
        finally:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
        return payload

    def get(self, location: Optional[str] = None) -> Dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {"active": False, "reason": "missing"}
        if location and str(payload.get("location", "")).lower() != str(location).lower():
            return {"active": False, "reason": "different_location", "payload": payload}
        if not payload.get("active") or float(payload.get("expires_at", 0)) <= time.time():
            return {"active": False, "reason": "expired", "payload": payload}
        return {"active": True, **payload}
