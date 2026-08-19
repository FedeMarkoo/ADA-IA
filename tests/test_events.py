import tempfile
import unittest
from pathlib import Path

from src.ada.infrastructure.persistence.sqlite import Memory
from src.ada.infrastructure.runtime.event_bus import EventBus
from src.ada.infrastructure.runtime.scheduler import Scheduler
from src.ada.infrastructure.runtime.watchers import FolderWatcher


class EventTests(unittest.TestCase):
    def test_event_is_persisted_and_acknowledged(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = Memory(str(Path(directory) / 'events.db'))
            bus = EventBus(memory)
            received = []
            bus.publish('test', {'value': 1})
            scheduler = Scheduler(memory, {'test': received.append})
            self.assertEqual(scheduler.run_once(), 1)
            self.assertEqual(received, [{'value': 1}])
            self.assertEqual(memory.claim_events(), [])

    def test_folder_watcher_emits_new_files(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = Memory(str(Path(directory) / 'events.db'))
            bus = EventBus(memory)
            folder = Path(directory) / 'photos'
            folder.mkdir()
            watcher = FolderWatcher(folder, bus)
            self.assertEqual(watcher.scan(), 0)
            (folder / 'one.jpg').write_text('x')
            self.assertEqual(watcher.scan(), 1)
            self.assertEqual(next(bus.consume())['payload']['path'], str((folder / 'one.jpg').resolve()))


if __name__ == '__main__':
    unittest.main()
