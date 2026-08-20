import tempfile
import unittest
from pathlib import Path

from ada.application.memory import MemoryLayers
from ada.infrastructure.credentials import CredentialStore
from ada.infrastructure.persistence.sqlite import Memory


class MemoryCredentialTests(unittest.TestCase):
    def test_memory_layers_and_task_retention(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = Memory(str(Path(directory) / "memory.db"))
            layers = MemoryLayers(memory)
            layers.remember("preferencias del usuario", "profile")
            self.assertTrue(memory.search_text("preferencias", kind="profile"))
            self.assertFalse(memory.search_text("preferencias", kind="episodic"))
            for index in range(3):
                memory.record_task({"n": index}, "result")
            self.assertEqual(memory.purge_tasks(1), 2)
            self.assertEqual(len(memory.recent_tasks(10)), 1)

    def test_memory_records_schema_version(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = Memory(str(Path(directory) / "memory.db"))
            self.assertEqual(memory.conn.execute("PRAGMA user_version").fetchone()[0], Memory.SCHEMA_VERSION)
            self.assertEqual(
                memory.conn.execute("SELECT version FROM schema_migrations ORDER BY version DESC").fetchone()[0], 2
            )

    def test_memory_backup_is_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Memory(str(Path(directory) / "memory.db"))
            source.add_text("dato de backup", kind="note")
            target = Path(directory) / "backups" / "memory-copy.db"
            source.backup_to(target)
            restored = Memory(str(target))
            self.assertTrue(restored.search_text("backup", kind="note"))

    def test_credentials_require_encryption_key(self):
        with tempfile.TemporaryDirectory() as directory:
            store = CredentialStore(Path(directory) / "credentials.enc")
            with self.assertRaises(RuntimeError):
                store.set("token", "secret")

    def test_credentials_round_trip_when_fernet_available(self):
        try:
            from cryptography.fernet import Fernet
        except ImportError:
            self.skipTest("cryptography no instalada")
        with tempfile.TemporaryDirectory() as directory:
            store = CredentialStore(Path(directory) / "credentials.enc", Fernet.generate_key())
            store.set("token", "secret")
            self.assertEqual(store.get("token"), "secret")
            self.assertEqual(store.path.stat().st_mode & 0o777, 0o600)

    def test_memory_encrypts_sensitive_rows_and_retrieves_them(self):
        try:
            from cryptography.fernet import Fernet
        except ImportError:
            self.skipTest("cryptography no instalada")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memory.db"
            memory = Memory(path, encrypted=True, encryption_key=Fernet.generate_key())
            memory.add_text("secreto de memoria", kind="profile")
            memory.add("/private/photo.jpg", meta={"camera": "secret"})
            memory.append_conversation([{"role": "user", "text": "conversación privada"}])
            raw = memory.conn.execute("SELECT content FROM memories").fetchone()[0]
            self.assertTrue(raw.startswith("ada:v1:"))
            image = memory.conn.execute("SELECT path, meta FROM images").fetchone()
            self.assertTrue(image["path"].startswith("ada:v1:"))
            self.assertTrue(image["meta"].startswith("ada:v1:"))
            self.assertTrue(memory.search_text("secreto", kind="profile"))
            self.assertEqual(memory.conversation()[0]["text"], "conversación privada")

    def test_credential_store_rejects_missing_key_even_for_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "credentials.enc"
            path.write_bytes(b"not plaintext")
            with self.assertRaises(RuntimeError):
                CredentialStore(path).get("token")


if __name__ == "__main__":
    unittest.main()
