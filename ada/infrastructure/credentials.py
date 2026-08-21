"""Local encrypted credential storage backed by an isolated SQLite vault.

Re-exports SecureVault and CredentialStore from shared utils.credentials module.
"""

from utils.credentials import (
    CredentialStore,
    SecureVault,
    _resolve_master_key,
)

__all__ = ["SecureVault", "CredentialStore", "_resolve_master_key"]
