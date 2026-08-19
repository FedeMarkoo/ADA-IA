"""Local encrypted credential storage; never falls back to plaintext."""

import json
import os
from pathlib import Path


class CredentialStore:
    def __init__(self, path=None, key=None):
        self.path = Path(path or os.environ.get("ADA_CREDENTIALS_PATH", "~/.config/ada/credentials.enc")).expanduser()
        self.key = key or os.environ.get("ADA_CREDENTIAL_KEY")

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
        return self._read().get(name, default)

    def set(self, name, value):
        data = self._read()
        data[str(name)] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(self._fernet().encrypt(json.dumps(data, ensure_ascii=False).encode("utf-8")))
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def delete(self, name):
        data = self._read()
        data.pop(str(name), None)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(self._fernet().encrypt(json.dumps(data, ensure_ascii=False).encode("utf-8")))
