from collections import defaultdict, deque
import threading
import time

from ada.infrastructure.prometheus_metrics import (
    EVENTS,
    OPERATIONS,
    PIPELINE_STAGE_DURATION,
    PIPELINE_STAGE_LAST,
    measure_stage,
    record_stage_duration,
)


class Metrics:
    def __init__(self, namespace="ada"):
        self.namespace = namespace
        self._counters = defaultdict(float)
        self._timings = defaultdict(lambda: deque(maxlen=1000))
        self._lock = threading.RLock()

    @staticmethod
    def _key(name, tags=None):
        suffix = "".join(f".{key}={value}" for key, value in sorted((tags or {}).items()))
        return f"{name}{suffix}"

    def increment(self, name, value=1, tags=None):
        with self._lock:
            key = self._key(name, tags)
            self._counters[key] += float(value)
            EVENTS.labels(metric=f"{self.namespace}_{name}", tags=self._labels(tags)).inc(float(value))

    def observe(self, name, seconds, tags=None):
        with self._lock:
            value = round(float(seconds), 6)
            self._timings[self._key(name, tags)].append(value)
            OPERATIONS.labels(metric=f"{self.namespace}_{name}", tags=self._labels(tags)).observe(value)

    @staticmethod
    def _labels(tags=None):
        return ",".join(f"{key}={value}" for key, value in sorted((tags or {}).items())) or "none"

    def timer(self, name, tags=None):
        metrics = self
        started = time.monotonic()

        class Timer:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                metrics.observe(name, time.monotonic() - started, tags)

        return Timer()

    def snapshot(self):
        with self._lock:
            timings = {}
            for key, values in self._timings.items():
                timings[key] = {
                    "count": len(values),
                    "avg_seconds": round(sum(values) / len(values), 6) if values else 0.0,
                    "max_seconds": max(values) if values else 0.0,
                }
            return {"namespace": self.namespace, "counters": dict(self._counters), "timings": timings}
