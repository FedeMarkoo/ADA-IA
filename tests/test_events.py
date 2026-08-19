import tempfile
import unittest
from pathlib import Path

from ada.infrastructure.persistence.sqlite import Memory
from ada.infrastructure.runtime.event_bus import EventBus
from ada.infrastructure.runtime.scheduler import Scheduler
from ada.infrastructure.runtime.watchers import FolderWatcher


class EventTests(unittest.TestCase):
    def test_event_is_persisted_and_acknowledged(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = Memory(str(Path(directory) / "events.db"))
            bus = EventBus(memory)
            received = []
            bus.publish("test", {"value": 1})
            scheduler = Scheduler(memory, {"test": received.append})
            self.assertEqual(scheduler.run_once(), 1)
            self.assertEqual(received, [{"value": 1}])
            self.assertEqual(memory.claim_events(), [])

    def test_folder_watcher_emits_new_files(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = Memory(str(Path(directory) / "events.db"))
            bus = EventBus(memory)
            folder = Path(directory) / "photos"
            folder.mkdir()
            watcher = FolderWatcher(folder, bus)
            self.assertEqual(watcher.scan(), 0)
            (folder / "one.jpg").write_text("x")
            self.assertEqual(watcher.scan(), 1)
            self.assertEqual(next(bus.consume())["payload"]["path"], str((folder / "one.jpg").resolve()))

    def test_priority_deduplication_and_cancellation(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = Memory(str(Path(directory) / "events.db"))
            scheduler = Scheduler(memory, {"test": lambda payload: None})
            low = scheduler.schedule("test", {"name": "low"}, priority=1)
            high = scheduler.schedule("test", {"name": "high"}, priority=10)
            self.assertIsInstance(high, int)
            duplicate = scheduler.schedule("test", {"name": "ignored"}, dedupe_key="same")
            self.assertEqual(scheduler.schedule("test", {"name": "ignored"}, dedupe_key="same"), duplicate)
            self.assertTrue(scheduler.cancel(low))
            claimed = list(scheduler.bus.consume(limit=2))
            self.assertEqual([item["payload"]["name"] for item in claimed], ["high", "ignored"])


if __name__ == "__main__":
    unittest.main()
