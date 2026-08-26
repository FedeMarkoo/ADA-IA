import tempfile
import unittest
import threading
from pathlib import Path

from ada.application.memory import MemoryLayers
from ada.infrastructure.credentials import CredentialStore, SecureVault
from ada.infrastructure.persistence.sqlite import Memory
import sqlite3


class MemoryCredentialTests(unittest.TestCase):
    def test_file_backed_memory_uses_connection_per_thread(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = Memory(str(Path(directory) / "memory.db"))
            connections = []
            worker = threading.Thread(target=lambda: connections.append(memory.conn))
            worker.start()
            worker.join()
            self.assertEqual(len(connections), 1)
            self.assertIsNot(memory.conn, connections[0])
            memory.close()

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

    def test_utils_credentials_reexport_and_compatibility(self):
        from utils.credentials import SecureVault as UtilsVault, CredentialStore as UtilsStore
        from ada.infrastructure.credentials import SecureVault as AdaVault, CredentialStore as AdaStore

        self.assertIs(UtilsVault, AdaVault)
        self.assertIs(UtilsStore, AdaStore)

    def test_secure_vault_isolated_sqlite_round_trip(self):
        try:
            from cryptography.fernet import Fernet
        except ImportError:
            self.skipTest("cryptography no instalada")
        with tempfile.TemporaryDirectory() as directory:
            vault_file = Path(directory) / "vault.db"
            key = Fernet.generate_key().decode("utf-8")
            vault = SecureVault(vault_file, master_key=key)

            # Store string and json secrets
            vault.set("telegram_bot_token", "12345:SecretBotToken", meta={"service": "telegram"})
            vault.set("gmail_oauth", {"access_token": "ya29.xyz", "refresh_token": "1//abc"})

            # Verify retrieval
            self.assertEqual(vault.get("telegram_bot_token"), "12345:SecretBotToken")
            self.assertEqual(vault.get("gmail_oauth")["access_token"], "ya29.xyz")
            self.assertTrue(vault.has("telegram_bot_token"))
            self.assertFalse(vault.has("non_existent"))

            # Verify raw SQLite data is encrypted
            with sqlite3.connect(str(vault_file)) as conn:
                raw_row = conn.execute("SELECT ciphertext FROM secrets WHERE name = 'telegram_bot_token'").fetchone()
                self.assertIsNotNone(raw_row)
                self.assertNotIn(b"SecretBotToken", raw_row[0])

            # Verify list_keys
            keys = vault.list_keys()
            self.assertEqual(len(keys), 2)
            self.assertEqual(keys[0]["name"], "gmail_oauth")
            self.assertEqual(keys[1]["name"], "telegram_bot_token")

            # Verify delete
            self.assertTrue(vault.delete("gmail_oauth"))
            self.assertIsNone(vault.get("gmail_oauth"))
            self.assertEqual(len(vault.list_keys()), 1)

            # Verify file mode
            self.assertEqual(vault_file.stat().st_mode & 0o777, 0o600)

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
