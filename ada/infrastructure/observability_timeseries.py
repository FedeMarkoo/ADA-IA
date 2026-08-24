"""Small SQLite time-series store with bounded retention for ADA telemetry."""
import os, sqlite3, threading, time, resource


def metrics_scraper_status(path="~/Desktop/ADA_Data/metrics.db", freshness_seconds=5, now=None):
    """Report the external scraper state from its last valid persisted sample.

    The scraper is intentionally outside the web process, so a PID check alone
    is not enough: it may be alive but unable to reach ADA. Fresh samples are
    the operational signal that the dashboard actually needs.
    """
    current = time.time() if now is None else float(now)
    db_path = os.path.expanduser(path)
    base = {
        "source": "external_scraper",
        "path": db_path,
        "freshness_seconds": freshness_seconds,
        "last_sample_at": None,
        "age_seconds": None,
        "status": "stopped",
        "ok": False,
    }
    if not os.path.exists(db_path):
        return {**base, "message": "Todavía no existe la base de telemetría"}
    try:
        with sqlite3.connect(db_path) as db:
            row = db.execute(
                """
                SELECT MAX(ts), COUNT(*)
                FROM prometheus_samples
                WHERE name NOT LIKE '%_source_ai_testing%'
                  AND name NOT LIKE '%_source_diagnostic%'
                """
            ).fetchone()
    except sqlite3.Error as exc:
        return {**base, "status": "error", "message": f"No se pudo leer la telemetría: {exc}"}

    last_sample_at, sample_count = row or (None, 0)
    if last_sample_at is None:
        return {**base, "sample_count": int(sample_count or 0), "message": "El scraper todavía no guardó muestras válidas"}

    age_seconds = max(0, current - float(last_sample_at))
    active = age_seconds <= freshness_seconds
    return {
        **base,
        "last_sample_at": float(last_sample_at),
        "age_seconds": round(age_seconds, 1),
        "sample_count": int(sample_count or 0),
        "status": "active" if active else "stale",
        "ok": active,
        "message": "Scraper activo y entregando muestras" if active else f"La última muestra llegó hace {round(age_seconds, 1)} s",
    }

class TimeSeriesStore:
    def __init__(self, path="~/Desktop/ADA_Data/metrics.db", retention_days=7):
        self.path=os.path.expanduser(path); self.retention_days=retention_days; self.lock=threading.RLock()
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS samples (ts REAL NOT NULL, component TEXT NOT NULL, metric TEXT NOT NULL, value REAL NOT NULL, tags TEXT DEFAULT '')")
            db.execute("CREATE INDEX IF NOT EXISTS idx_samples_ts ON samples(ts)")
    def record(self, component, metric, value, tags=""):
        with self.lock, sqlite3.connect(self.path) as db: db.execute("INSERT INTO samples VALUES (?,?,?,?,?)", (time.time(), component, metric, float(value), tags))
    def prune(self):
        cutoff=time.time()-self.retention_days*86400
        with self.lock, sqlite3.connect(self.path) as db: db.execute("DELETE FROM samples WHERE ts<?",(cutoff,))
    def query(self, since=None, component=None):
        since=since or time.time()-3600; q="SELECT ts,component,metric,value,tags FROM samples WHERE ts>=?"; args=[since]
        if component: q+=" AND component=?"; args.append(component)
        q+=" ORDER BY ts ASC"
        with self.lock, sqlite3.connect(self.path) as db: return [dict(zip(("ts","component","metric","value","tags"),row)) for row in db.execute(q,args)]
    def sample_process(self):
        usage=resource.getrusage(resource.RUSAGE_SELF); self.record("ada","cpu_time_seconds",usage.ru_utime+usage.ru_stime); self.record("ada","rss_mb",usage.ru_maxrss/1024); self.prune()
