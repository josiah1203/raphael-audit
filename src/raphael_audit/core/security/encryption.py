"""Fernet encryption at rest for persisted stores."""

from __future__ import annotations

import os
from pathlib import Path

from raphael_audit.core.compliance.audit_logging import AuditEvent, log_audit
from raphael_audit.core.paths import calliope_home

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # pragma: no cover
    Fernet = None  # type: ignore[misc, assignment]
    InvalidToken = Exception  # type: ignore[misc, assignment]


class EncryptionError(RuntimeError):
    """Raised when encryption is required but unavailable."""


class DataKeyManager:
    """Load or generate a Fernet key for at-rest encryption."""

    ENV_VAR = "CALLIOPE_DATA_KEY"
    DEFAULT_KEY_PATH = calliope_home() / "master.key"

    def __init__(self, key_path: Path | None = None, enabled: bool = False) -> None:
        self.enabled = enabled
        self.key_path = key_path or self.DEFAULT_KEY_PATH
        self._fernet: Fernet | None = None
        if enabled:
            self._fernet = Fernet(self._load_or_create_key())

    def _load_or_create_key(self) -> bytes:
        if Fernet is None:
            raise EncryptionError("cryptography package is required for encrypted_at_rest")

        log_audit(AuditEvent.ENCRYPTION_KEY_ACCESSED, resource=str(self.key_path))
        env_key = os.environ.get(self.ENV_VAR)
        if env_key is not None:
            normalized = env_key.strip()
            if not normalized:
                raise EncryptionError(f"{self.ENV_VAR} must not be empty")
            key_bytes = normalized.encode("utf-8")
            try:
                Fernet(key_bytes)
            except Exception as exc:
                raise EncryptionError(
                    f"Invalid {self.ENV_VAR}: expected url-safe base64 Fernet key"
                ) from exc
            return key_bytes
        if self.key_path.exists():
            # Issue #1: Check permissions (mode != 0o600)
            mode = self.key_path.stat().st_mode & 0o777
            if mode != 0o600:
                raise EncryptionError(
                    f"Unsafe permissions on encryption key {self.key_path}: {oct(mode)}. "
                    "Expected 0o600."
                )
            return self.key_path.read_bytes().strip()

        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        key = Fernet.generate_key()

        # Issue #1: Use umask 0o077 when writing key
        old_umask = os.umask(0o077)
        try:
            # We use os.open to ensure correct permissions during creation
            fd = os.open(self.key_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(key)
        finally:
            os.umask(old_umask)

        return key

    def encrypt(self, plaintext: str) -> str:
        if not self.enabled or self._fernet is None:
            return plaintext
        token = self._fernet.encrypt(plaintext.encode("utf-8"))
        return "enc:" + token.decode("ascii")

    def decrypt(self, stored: str) -> str:
        if not stored.startswith("enc:"):
            return stored
        if not self.enabled or self._fernet is None:
            raise EncryptionError("encrypted data present but encryption is disabled")
        try:
            return self._fernet.decrypt(stored[4:].encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise EncryptionError("failed to decrypt stored data") from exc
