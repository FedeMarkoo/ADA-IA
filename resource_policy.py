"""Lightweight resource policy used before starting expensive local work."""
import os
import time


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
    return max(1, min(2, int(cores * cpu_budget(config) / 100.0)))


def wait_for_cpu_budget(config=None):
    """Pause new jobs when system load already exceeds the ADA budget.

    The load-average fallback is intentionally conservative and portable. It
    controls admission and concurrency; Ollama's thread option limits the
    actual inference workload.
    """
    config = config or {}
    limit = cpu_budget(config) / 100.0
    cores = max(1, os.cpu_count() or 1)
    while True:
        try:
            load = os.getloadavg()[0] / cores
        except (AttributeError, OSError):
            return
        if load < limit:
            return
        time.sleep(float(config.get('cpu_throttle_seconds', 1.0)))
