"""Small SQLite time-series store with bounded retention for ADA telemetry."""
import os, sqlite3, threading, time, resource

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
