"""Password hashing, strength validation, and legacy SHA256 migration."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from typing import Protocol

_LEGACY_SHA256_HEX = re.compile(r"^[0-9a-fA-F]{64}$")


class HibpClient(Protocol):
    def is_pwned(self, password: str) -> bool: ...


class StubHibpClient:
    """Testable HIBP stub — flags known weak passwords."""

    PWNED = {"password123", "password1234567", "qwerty123", "letmein"}

    def is_pwned(self, password: str) -> bool:
        return password.lower() in self.PWNED


class LiveHibpClient:
    """Check password against Have I Been Pwned k-anonymity API."""

    def is_pwned(self, password: str) -> bool:
        import httpx

        sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
        prefix, suffix = sha1[:5], sha1[5:]
        try:
            resp = httpx.get(
                f"https://api.pwnedpasswords.com/range/{prefix}",
                timeout=5.0,
            )
            resp.raise_for_status()
            return any(line.startswith(suffix) for line in resp.text.splitlines())
        except Exception:
            return False


def hash_password(password: str, *, iterations: int = 600_000) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    )
    return f"pbkdf2_sha256${iterations}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    parts = stored.split("$")
    if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
        return False
    iterations = int(parts[1])
    salt, expected = parts[2], parts[3]
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    )
    return secrets.compare_digest(digest.hex(), expected)


def validate_password_strength(password: str, hibp: HibpClient | None = None) -> str | None:
    if hibp and hibp.is_pwned(password):
        return "password_pwned"
    if len(password) < 12:
        return "password_too_short"
    return None


def is_legacy_sha256_hash(stored: str) -> bool:
    """Return True when ``stored`` looks like a bare SHA256 hex digest (no ``$``)."""
    return "$" not in stored and bool(_LEGACY_SHA256_HEX.fullmatch(stored))


def verify_password_legacy_sha256(password: str, stored: str) -> bool:
    digest = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(digest, stored)


def verify_password_with_migration(password: str, stored: str) -> tuple[bool, str | None]:
    """Verify password; return ``(ok, upgraded_hash)`` when legacy SHA256 should be re-hashed."""
    if is_legacy_sha256_hash(stored):
        if verify_password_legacy_sha256(password, stored):
            return True, hash_password(password)
        return False, None
    if verify_password(password, stored):
        return True, None
    return False, None
