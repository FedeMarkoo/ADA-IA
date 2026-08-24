#!/usr/bin/env python3
"""External ADA metrics scraper.

Polls ADA's Prometheus exposition endpoint and stores samples in SQLite. It is
deliberately a separate process so telemetry cannot block or crash ADA.
"""
import argparse, os, sqlite3, time, urllib.request, json
try:
    import psutil
except ImportError:
    psutil = None

DB=os.path.expanduser("~/Desktop/ADA_Data/metrics.db")

def scrape(url):
    with urllib.request.urlopen(url, timeout=10) as response:
        return response.read().decode("utf-8", "replace")

def store(db, text, retention_days=7):
    now=time.time(); db.execute("CREATE TABLE IF NOT EXISTS prometheus_samples (ts REAL, name TEXT, labels TEXT, value REAL)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_prom_samples_ts ON prometheus_samples(ts)")
    for line in text.splitlines():
        if not line or line.startswith("#") or " " not in line: continue
        key, raw=line.rsplit(" ",1)
        try: value=float(raw)
        except ValueError: continue
        if "{" in key: name, labels=key.split("{",1); labels=labels.rstrip("}")
        else: name, labels=key, ""
        # ADA exposes generic Prometheus families with the real metric name
        # in the `name` label. Preserve the metric family when promoting it:
        # timing count and timing average must never collapse into one series.
        if 'name="' in labels:
            promoted = labels.split('name="', 1)[1].split('"', 1)[0]
            if promoted:
                if name == "ada_agent_counter":
                    name = promoted
                elif name == "ada_agent_timing_count":
                    name = f"{promoted}_count"
                elif name == "ada_agent_timing_avg_seconds":
                    name = f"{promoted}_avg_seconds"
        # Test and diagnostic traffic is useful for CI, but must not pollute
        # the operational dashboard or its persisted telemetry window.
        if "_source_ai_testing" in name or "_source_diagnostic" in name:
            continue
        db.execute("INSERT INTO prometheus_samples VALUES (?,?,?,?)", (now,name,labels,value))
    db.execute("DELETE FROM prometheus_samples WHERE ts < ?", (now-retention_days*86400,)); db.commit()

def process_samples(db):
    if not psutil: return
    now=time.time(); rows=[]
    for proc in psutil.process_iter(["pid","cmdline","memory_info"]):
        try:
            cmd=" ".join(proc.info.get("cmdline") or [])
            if "ada.interfaces.web.server" in cmd: component="ada"
            elif "telegram/bot.py" in cmd: component="telegram"
            elif "ollama" in cmd or "llama-server" in cmd: component="ollama"
            else: continue
            cpu=proc.cpu_percent(interval=None); rss=(proc.info.get("memory_info").rss or 0)/1024/1024
            rows += [(now, f"{component}_process_cpu_percent", 'component="%s"'%component, cpu), (now, f"{component}_process_rss_mb", 'component="%s"'%component, rss)]
        except Exception: pass
    db.executemany("INSERT INTO prometheus_samples VALUES (?,?,?,?)", rows); db.commit()

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--url",default="http://127.0.0.1:5005/metrics"); parser.add_argument("--interval",type=float,default=1); parser.add_argument("--db",default=DB); args=parser.parse_args()
    os.makedirs(os.path.dirname(os.path.expanduser(args.db)),exist_ok=True)
    with sqlite3.connect(os.path.expanduser(args.db)) as db:
        while True:
            try: store(db,scrape(args.url)); process_samples(db)
            except Exception as exc: print(f"metrics scraper: {exc}",flush=True)
            time.sleep(max(1,args.interval))
if __name__ == "__main__": main()
