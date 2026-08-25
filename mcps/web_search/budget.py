"""Local, atomic usage budget for paid web-search providers."""

from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union


class SearchBudget:
    """Reserve provider requests without ever exceeding the local monthly cap."""

    def __init__(self, path: Optional[Union[str, Path]] = None, monthly_limit: Optional[int] = None):
        default_path = Path.home() / "Desktop" / "ADA_Data" / "web-search-usage.db"
        self.path = Path(path or os.environ.get("ADA_WEB_SEARCH_USAGE_PATH", default_path)).expanduser()
        self.monthly_limit = int(monthly_limit if monthly_limit is not None else os.environ.get("ADA_WEB_SEARCH_MONTHLY_LIMIT", "900"))
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path, timeout=15) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS usage (provider TEXT NOT NULL, month TEXT NOT NULL, requests INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(provider, month))")
            conn.commit()

    def reserve(self, provider: str, count: int = 1) -> bool:
        """Atomically reserve requests; return False when the cap is exhausted."""
        if count < 1 or self.monthly_limit < count:
            return False
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        with self._lock, sqlite3.connect(self.path, timeout=15) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT requests FROM usage WHERE provider=? AND month=?", (provider, month)).fetchone()
            used = int(row[0]) if row else 0
            if used + count > self.monthly_limit:
                conn.rollback()
                return False
            conn.execute(
                "INSERT INTO usage(provider, month, requests) VALUES (?, ?, ?) "
                "ON CONFLICT(provider, month) DO UPDATE SET requests=requests+excluded.requests",
                (provider, month, count),
            )
            conn.commit()
            return True
