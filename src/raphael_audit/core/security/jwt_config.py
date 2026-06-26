"""JWT secret resolution and production safety checks."""

from __future__ import annotations

import os

KNOWN_DEV_SECRETS = frozenset(
    {
        "dev-secret",
        "hb-labs-dev-secret",
        "dev-secret-with-32-byte-minimum-length!!",
    }
)


class SecurityConfigurationError(RuntimeError):
    """Raised when security configuration is invalid for the deployment environment."""


def _is_known_dev_secret(secret: str) -> bool:
    if secret in KNOWN_DEV_SECRETS:
        return True
    return secret.startswith("test-secret-")


def _deployment_env() -> str:
    return (
        os.environ.get("CALLIOPE_ENV") or os.environ.get("HBLABS_ENV") or "development"
    ).lower()


def resolve_jwt_secret(
    *,
    env_var: str = "CALLIOPE_JWT_SECRET",
    min_bytes: int = 32,
    config_value: str | None = None,
    dev_default: str | None = None,
) -> str:
    """Resolve JWT signing secret from environment, config, or an explicit dev default.

    In ``production`` or ``staging`` (via ``CALLIOPE_ENV`` / ``HBLABS_ENV``), missing,
    too-short, or known development secrets raise :class:`SecurityConfigurationError`.
    """
    secret = os.environ.get(env_var) or config_value
    env = _deployment_env()
    is_prod_like = env in ("production", "staging")

    if secret is None:
        if not is_prod_like and dev_default is not None:
            return dev_default
        raise SecurityConfigurationError(
            f"JWT secret missing; set {env_var} or provide config_value"
        )

    if len(secret.encode("utf-8")) < min_bytes:
        raise SecurityConfigurationError(
            f"JWT secret must be at least {min_bytes} bytes"
        )

    if is_prod_like:
        if _is_known_dev_secret(secret):
            raise SecurityConfigurationError(
                f"JWT secret must not use a known development default in {env}"
            )

    return secret
