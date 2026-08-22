from collections import defaultdict, deque
import threading
import time


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
            self._counters[self._key(name, tags)] += float(value)

    def observe(self, name, seconds, tags=None):
        with self._lock:
            self._timings[self._key(name, tags)].append(round(float(seconds), 6))

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
