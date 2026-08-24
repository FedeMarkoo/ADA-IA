import sqlite3
import tempfile
import time
from pathlib import Path

from ada.infrastructure.observability_timeseries import metrics_scraper_status


def test_metrics_scraper_status_requires_a_recent_valid_sample():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "metrics.db"

        stopped = metrics_scraper_status(str(path), now=100)
        assert stopped["status"] == "stopped"
        assert stopped["ok"] is False

        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE prometheus_samples (ts REAL, name TEXT, labels TEXT, value REAL)")
            db.execute("INSERT INTO prometheus_samples VALUES (96, 'ada_up', '', 1)")
            db.execute("INSERT INTO prometheus_samples VALUES (99, 'messages_received_source_ai_testing', '', 99)")

        active = metrics_scraper_status(str(path), freshness_seconds=5, now=100)
        assert active["status"] == "active"
        assert active["last_sample_at"] == 96
        assert active["ok"] is True

        stale = metrics_scraper_status(str(path), freshness_seconds=5, now=103)
        assert stale["status"] == "stale"
        assert stale["ok"] is False
