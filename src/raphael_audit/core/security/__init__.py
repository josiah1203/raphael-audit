"""Shared security primitives for Calliope."""

from raphael_audit.core.security.encryption import DataKeyManager, EncryptionError
from raphael_audit.core.security.jwt_config import (
    KNOWN_DEV_SECRETS,
    SecurityConfigurationError,
    resolve_jwt_secret,
)
from raphael_audit.core.security.passwords import (
    HibpClient,
    LiveHibpClient,
    StubHibpClient,
    hash_password,
    is_legacy_sha256_hash,
    validate_password_strength,
    verify_password,
    verify_password_legacy_sha256,
    verify_password_with_migration,
)

__all__ = [
    "DataKeyManager",
    "EncryptionError",
    "HibpClient",
    "KNOWN_DEV_SECRETS",
    "LiveHibpClient",
    "SecurityConfigurationError",
    "StubHibpClient",
    "hash_password",
    "is_legacy_sha256_hash",
    "resolve_jwt_secret",
    "validate_password_strength",
    "verify_password",
    "verify_password_legacy_sha256",
    "verify_password_with_migration",
]
