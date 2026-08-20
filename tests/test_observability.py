import unittest

from ada.infrastructure.observability import Metrics


class ObservabilityTests(unittest.TestCase):
    def test_metrics_snapshot_is_json_ready(self):
        metrics = Metrics("test")
        metrics.increment("calls", tags={"tool": "demo"})
        with metrics.timer("duration", tags={"tool": "demo"}):
            pass
        snapshot = metrics.snapshot()
        self.assertEqual(snapshot["namespace"], "test")
        self.assertEqual(snapshot["counters"]["calls.tool=demo"], 1.0)
        self.assertEqual(snapshot["timings"]["duration.tool=demo"]["count"], 1)


if __name__ == "__main__":
    unittest.main()
