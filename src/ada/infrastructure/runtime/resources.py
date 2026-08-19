"""Lightweight resource policy used before starting expensive local work."""
import os
import time

try:
    import psutil
except Exception:
    psutil = None


def cpu_budget(config=None):
    config = config or {}
    return max(10.0, min(100.0, float(config.get('cpu_limit_percent', 50))))


def recommended_threads(config=None):
    """Return a conservative Ollama thread count for the configured budget."""
    config = config or {}
    explicit = config.get('ollama_num_thread')
    if explicit:
        return max(1, int(explicit))
    cores = os.cpu_count() or 2
    return max(1, min(cores, int(cores * cpu_budget(config) / 100.0) or 1))


def wait_for_cpu_budget(config=None):
    """Pause new jobs when system load already exceeds the ADA budget.

    The load-average fallback is intentionally conservative and portable. It
    controls admission and concurrency; Ollama's thread option limits the
    actual inference workload.
    """
    config = config or {}
    limit = cpu_budget(config) / 100.0
    cores = max(1, os.cpu_count() or 1)
    max_wait = max(1.0, float(config.get('cpu_throttle_max_wait_seconds', 30.0)))
    started_waiting = time.monotonic()
    while True:
        if psutil is not None:
            load = psutil.cpu_percent(interval=0.1) / 100.0
        else:
            try:
                load = os.getloadavg()[0] / cores
            except (AttributeError, OSError):
                return
        if load < limit:
            return
        # Load average includes unrelated system work and can remain above the
        # threshold for minutes. Throttling must slow ADA down, not deadlock a
        # batch forever; after the grace period one admitted worker may run.
        if time.monotonic() - started_waiting >= max_wait:
            return
        time.sleep(float(config.get('cpu_throttle_seconds', 1.0)))


def hardware_profile():
    """Return a small, portable hardware profile for model selection."""
    cores = os.cpu_count() or 1
    ram_gb = 0.0
    if psutil is not None:
        ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 1)
    if ram_gb >= 32 and cores >= 8:
        tier = 'high'
    elif ram_gb >= 16 and cores >= 4:
        tier = 'mid'
    else:
        tier = 'low'
    return {'tier': tier, 'cpu_cores': cores, 'ram_gb': ram_gb}
