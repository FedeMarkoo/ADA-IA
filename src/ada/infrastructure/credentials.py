"""Local encrypted credential storage; never falls back to plaintext."""

import json
import os
from pathlib import Path
import tempfile
import threading


class CredentialStore:
    def __init__(self, path=None, key=None):
        self.path = Path(path or os.environ.get("ADA_CREDENTIALS_PATH", "~/.config/ada/credentials.enc")).expanduser()
        self.key = key or os.environ.get("ADA_CREDENTIAL_KEY")
        self._lock = threading.RLock()

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
        with self._lock:
            return self._read().get(name, default)

    def set(self, name, value):
        with self._lock:
            data = self._read()
            data[str(name)] = value
            self._write(data)

    def delete(self, name):
        with self._lock:
            data = self._read()
            data.pop(str(name), None)
            self._write(data)

    def _write(self, data):
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
