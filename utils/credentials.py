"""Local encrypted credential storage backed by an isolated SQLite vault.

Shared utility module for ADA Core, MCPs, and Telegram Server.
Never stores plaintext credentials on disk, in config files, or in Git.
"""

import json
import logging
import os
from pathlib import Path
import sqlite3
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ada.vault")


def _resolve_master_key(explicit_key: Optional[str] = None) -> str:
    """Resolve or generate a master encryption key.

    Priority:
    1. Explicit key argument.
    2. Environment variable ADA_CREDENTIAL_KEY.
    3. OS Keyring (Secret Service API / Apple Keychain / Windows Credential Manager).
    4. Protected local machine file ~/.config/ada/vault.key with chmod 0600.
    """
    if explicit_key:
        return explicit_key

    env_key = os.environ.get("ADA_CREDENTIAL_KEY")
    if env_key:
        return env_key.strip()

    # 3. Try OS Keyring if available
    try:
        import keyring

        key = keyring.get_password("ADA_System", "master_vault_key")
        if key:
            return key.strip()
    except Exception:
        pass

    # 4. Protected local machine keyfile
    key_dir = Path(os.environ.get("ADA_CONFIG_DIR", "~/.config/ada")).expanduser()
    key_file = key_dir / "vault.key"
    if key_file.is_file():
        try:
            return key_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass

    # Auto-generate a strong Fernet key
    try:
        from cryptography.fernet import Fernet

        new_key = Fernet.generate_key().decode("utf-8")
        key_dir.mkdir(parents=True, exist_ok=True)
        key_file.write_text(new_key, encoding="utf-8")
        try:
            os.chmod(key_file, 0o600)
        except OSError:
            pass

        # Try to also register in OS Keyring
        try:
            import keyring

            keyring.set_password("ADA_System", "master_vault_key", new_key)
        except Exception:
            pass

        return new_key
    except ImportError:
        raise RuntimeError("Instalá el paquete 'cryptography' para utilizar la bóveda de credenciales cifradas.")


class SecureVault:
    """Isolated, encrypted SQLite credentials vault."""

    def __init__(self, db_path: Optional[Path | str] = None, master_key: Optional[str] = None):
        default_path = os.environ.get("ADA_VAULT_PATH")
        if not default_path:
            p1 = Path("~/Desktop/ADA_Data/vault.db").expanduser()
            p2 = Path("~/Desktop/ADA_Data/credentials.db").expanduser()
            default_path = p1 if p1.is_file() else p2
        self.path = Path(db_path or default_path).expanduser()
        self._explicit_key = master_key
        self._lock = threading.RLock()
        self._init_db()

    def _get_fernet(self):
        key = _resolve_master_key(self._explicit_key)
        if not key:
            raise RuntimeError("No se pudo obtener la clave maestra para la bóveda de credenciales.")
        try:
            from cryptography.fernet import Fernet
        except ImportError as exc:
            raise RuntimeError("Instalá cryptography para usar la bóveda de credenciales cifradas.") from exc
        try:
            return Fernet(key.encode() if isinstance(key, str) else key)
        except (ValueError, TypeError) as exc:
            raise RuntimeError("La clave maestra no es una clave Fernet válida.") from exc

    def _init_db(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with sqlite3.connect(str(self.path), timeout=15) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS secrets (
                        name TEXT PRIMARY KEY,
                        ciphertext BLOB NOT NULL,
                        meta TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    """)
                conn.commit()
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass

    def get(self, name: str, default: Any = None) -> Any:
        """Decrypt and retrieve a credential value by name."""
        with self._lock:
            try:
                with sqlite3.connect(str(self.path), timeout=15) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT ciphertext FROM secrets WHERE name = ?", (str(name),))
                    row = cursor.fetchone()
                    if not row:
                        return default
                    fernet = self._get_fernet()
                    raw = fernet.decrypt(row[0])
                    decoded = raw.decode("utf-8")
                    try:
                        return json.loads(decoded)
                    except json.JSONDecodeError:
                        return decoded
            except Exception as exc:
                logger.warning("Error decrypting secret %s: %s", name, exc)
                return default

    def set(self, name: str, value: Any, meta: Optional[Dict[str, Any]] = None) -> None:
        """Encrypt and persist a credential value."""
        with self._lock:
            fernet = self._get_fernet()
            if isinstance(value, (dict, list, bool, int, float)):
                payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
            else:
                payload = str(value).encode("utf-8")

            ciphertext = fernet.encrypt(payload)
            meta_json = json.dumps(meta or {}, ensure_ascii=False) if meta else None

            with sqlite3.connect(str(self.path), timeout=15) as conn:
                conn.execute(
                    """
                    INSERT INTO secrets (name, ciphertext, meta, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(name) DO UPDATE SET
                        ciphertext = excluded.ciphertext,
                        meta = excluded.meta,
                        updated_at = CURRENT_TIMESTAMP;
                    """,
                    (str(name), ciphertext, meta_json),
                )
                conn.commit()
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass

    def delete(self, name: str) -> bool:
        """Delete a secret from the vault."""
        with self._lock:
            with sqlite3.connect(str(self.path), timeout=15) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM secrets WHERE name = ?", (str(name),))
                conn.commit()
                return cursor.rowcount > 0

    def has(self, name: str) -> bool:
        """Check whether a credential exists in the vault."""
        with self._lock:
            with sqlite3.connect(str(self.path), timeout=15) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM secrets WHERE name = ?", (str(name),))
                return cursor.fetchone() is not None

    def list_keys(self) -> List[Dict[str, Any]]:
        """List all secret entries without revealing their plaintext values."""
        with self._lock:
            with sqlite3.connect(str(self.path), timeout=15) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT name, meta, created_at, updated_at FROM secrets ORDER BY name ASC")
                results = []
                for row in cursor.fetchall():
                    meta = {}
                    if row["meta"]:
                        try:
                            meta = json.loads(row["meta"])
                        except Exception:
                            pass
                    results.append(
                        {
                            "name": row["name"],
                            "meta": meta,
                            "created_at": row["created_at"],
                            "updated_at": row["updated_at"],
                            "is_set": True,
                        }
                    )
                return results


class CredentialStore:
    """Backwards-compatible wrapper delegating to SecureVault or isolated file."""

    def __init__(self, path=None, key=None):
        self.key = key or os.environ.get("ADA_CREDENTIAL_KEY")
        if path:
            self.path = Path(path).expanduser()
            if self.path.suffix in {".db", ".sqlite"}:
                self._vault = SecureVault(self.path, self.key)
                self._legacy = False
            else:
                self._legacy = True
                self._lock = threading.RLock()
        else:
            self._vault = SecureVault(master_key=self.key)
            self._legacy = False
            self.path = self._vault.path

    def _fernet(self):
        if not self.key:
            raise RuntimeError("Definí ADA_CREDENTIAL_KEY para usar el almacén de credenciales.")
        try:
            from cryptography.fernet import Fernet
        except ImportError as exc:
            raise RuntimeError("Instalá la extra credentials para usar credenciales cifradas.") from exc
        try:
            return Fernet(self.key.encode() if isinstance(self.key, str) else self.key)
        except (ValueError, TypeError) as exc:
            raise RuntimeError("ADA_CREDENTIAL_KEY no es una clave Fernet válida.") from exc

    def _read(self):
        if not self.path.exists():
            return {}
        raw = self._fernet().decrypt(self.path.read_bytes())
        return json.loads(raw.decode("utf-8"))

    def get(self, name, default=None):
        if not self._legacy:
            return self._vault.get(name, default)
        if not self.key:
            raise RuntimeError("Definí ADA_CREDENTIAL_KEY para usar el almacén de credenciales.")
        with self._lock:
            return self._read().get(name, default)

    def set(self, name, value):
        if not self._legacy:
            return self._vault.set(name, value)
        if not self.key:
            raise RuntimeError("Definí ADA_CREDENTIAL_KEY para usar el almacén de credenciales.")
        with self._lock:
            data = self._read()
            data[str(name)] = value
            self._write(data)

    def delete(self, name):
        if not self._legacy:
            return self._vault.delete(name)
        if not self.key:
            raise RuntimeError("Definí ADA_CREDENTIAL_KEY para usar el almacén de credenciales.")
        with self._lock:
            data = self._read()
            data.pop(str(name), None)
            self._write(data)

    def _write(self, data):
        import tempfile

        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._fernet().encrypt(json.dumps(data, ensure_ascii=False).encode("utf-8"))
        descriptor, temporary = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=str(self.path.parent))
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
