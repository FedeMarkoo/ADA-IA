import tempfile
import unittest
from pathlib import Path

from src.ada.application.memory import MemoryLayers
from src.ada.infrastructure.credentials import CredentialStore
from src.ada.infrastructure.persistence.sqlite import Memory


class MemoryCredentialTests(unittest.TestCase):
    def test_memory_layers_and_task_retention(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = Memory(str(Path(directory) / 'memory.db'))
            layers = MemoryLayers(memory)
            layers.remember('preferencias del usuario', 'profile')
            self.assertTrue(memory.search_text('preferencias'))
            for index in range(3):
                memory.record_task({'n': index}, 'result')
            self.assertEqual(memory.purge_tasks(1), 2)
            self.assertEqual(len(memory.recent_tasks(10)), 1)

    def test_credentials_require_encryption_key(self):
        with tempfile.TemporaryDirectory() as directory:
            store = CredentialStore(Path(directory) / 'credentials.enc')
            with self.assertRaises(RuntimeError):
                store.set('token', 'secret')

    def test_credentials_round_trip_when_fernet_available(self):
        try:
            from cryptography.fernet import Fernet
        except ImportError:
            self.skipTest('cryptography no instalada')
        with tempfile.TemporaryDirectory() as directory:
            store = CredentialStore(Path(directory) / 'credentials.enc', Fernet.generate_key())
            store.set('token', 'secret')
            self.assertEqual(store.get('token'), 'secret')

    def test_credential_store_rejects_missing_key_even_for_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'credentials.enc'
            path.write_bytes(b'not plaintext')
            with self.assertRaises(RuntimeError):
                CredentialStore(path).get('token')


if __name__ == '__main__':
    unittest.main()
