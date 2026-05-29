"""Cryptographic primitives for auth: argon2id, JWT, refresh tokens.

Every crypto operation in the codebase routes through this file. Concentrating
them makes security review trivial — there's one place to audit.

Three responsibilities:
  1. Password hashing / verification (argon2id).
  2. Access-token minting + decoding (JWT, HS256).
  3. Refresh-token generation + hashing (opaque random + SHA-256).
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerifyMismatchError

from app.core.config import Settings, get_settings

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
JWT_ISSUER: Final[str] = "devpulse"
JWT_AUDIENCE: Final[str] = "devpulse-api"
ACCESS_TOKEN_TYPE: Final[str] = "access"

# -----------------------------------------------------------------------------
# Password hashing (argon2id)
# -----------------------------------------------------------------------------
# Parameter choices: stronger than OWASP minimum, fast enough for a login
# request (~100ms on a modern laptop). Tune via benchmarking on production
# hardware before launch.
#   memory_cost (KiB)  - how much RAM each hash uses. 64 MiB = harder for GPUs.
#   time_cost          - iterations.
#   parallelism        - lanes (CPU cores used).
#   salt_len           - per-hash salt length (16 bytes is standard).
#   hash_len           - output length (32 bytes = 256 bits).
# -----------------------------------------------------------------------------
_password_hasher: Final[PasswordHasher] = PasswordHasher(
    memory_cost=64 * 1024,
    time_cost=3,
    parallelism=4,
    salt_len=16,
    hash_len=32,
)


def hash_password(password: str) -> str:
    """Hash a plaintext password with argon2id.

    Returns the encoded hash string ($argon2id$...) which includes the
    algorithm, parameters, salt, and hash — everything needed to verify later.
    """
    return _password_hasher.hash(password)


def verify_password(plaintext: str, stored_hash: str) -> bool:
    """Constant-time verification. Never raises on mismatch — returns False.

    `InvalidHash` (malformed stored hash) is also treated as a failed verify
    so we can't accidentally crash on a corrupt DB row during login.
    """
    try:
        _password_hasher.verify(stored_hash, plaintext)
        return True
    except (VerifyMismatchError, InvalidHash):
        return False


def password_needs_rehash(stored_hash: str) -> bool:
    """True when the hash was computed under weaker parameters than the
    current configuration. Call after a successful verify and re-hash if so.
    """
    return _password_hasher.check_needs_rehash(stored_hash)


# -----------------------------------------------------------------------------
# Access tokens (JWT)
# -----------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    """Decoded access-token claims, after signature + iss/aud verification."""

    sub: UUID  # user_id
    org_id: UUID | None  # active org (None until user picks one)
    role: str | None  # role in active org
    email: str
    jti: UUID
    iat: datetime
    exp: datetime


def mint_access_token(
    *,
    user_id: UUID,
    email: str,
    org_id: UUID | None,
    role: str | None,
    settings: Settings | None = None,
) -> tuple[str, datetime]:
    """Create a signed access token. Returns (token, expiry)."""
    settings = settings or get_settings()
    now = datetime.now(tz=UTC)
    exp = now + timedelta(seconds=settings.security.jwt_access_token_ttl_seconds)

    payload: dict[str, Any] = {
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "sub": str(user_id),
        "email": email,
        "org_id": str(org_id) if org_id else None,
        "role": role,
        "jti": str(uuid4()),
        "token_type": ACCESS_TOKEN_TYPE,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    token = jwt.encode(
        payload,
        settings.security.jwt_secret.get_secret_value(),
        algorithm=settings.security.jwt_algorithm,
    )
    return token, exp


class InvalidAccessTokenError(Exception):
    """Token is malformed, expired, wrong signature, wrong issuer/audience, or wrong type."""


def decode_access_token(token: str, *, settings: Settings | None = None) -> AccessTokenClaims:
    """Verify signature + claims and return the typed payload.

    Raises `InvalidAccessTokenError` for any failure. Callers should treat all
    failures the same — never leak why the token was rejected.
    """
    settings = settings or get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.security.jwt_secret.get_secret_value(),
            algorithms=[settings.security.jwt_algorithm],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
            options={"require": ["exp", "iat", "sub", "jti", "token_type"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidAccessTokenError(str(exc)) from exc

    if payload.get("token_type") != ACCESS_TOKEN_TYPE:
        raise InvalidAccessTokenError("unexpected token_type")

    try:
        return AccessTokenClaims(
            sub=UUID(payload["sub"]),
            org_id=UUID(payload["org_id"]) if payload.get("org_id") else None,
            role=payload.get("role"),
            email=payload["email"],
            jti=UUID(payload["jti"]),
            iat=datetime.fromtimestamp(payload["iat"], tz=UTC),
            exp=datetime.fromtimestamp(payload["exp"], tz=UTC),
        )
    except (KeyError, ValueError) as exc:
        raise InvalidAccessTokenError(f"malformed claim: {exc}") from exc


# -----------------------------------------------------------------------------
# Refresh tokens (opaque random + SHA-256 fingerprint)
# -----------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class NewRefreshToken:
    """A freshly minted refresh token. Plaintext is returned to the client
    exactly once; only `token_hash` is persisted server-side.
    """

    plaintext: str
    token_hash: str
    expires_at: datetime


def generate_refresh_token(*, settings: Settings | None = None) -> NewRefreshToken:
    """Generate a high-entropy refresh token + its storage fingerprint.

    `secrets.token_urlsafe(32)` yields ~43 chars of URL-safe random.
    `hash_refresh_token` produces a SHA-256 hex digest for DB lookup.
    """
    settings = settings or get_settings()
    plaintext = secrets.token_urlsafe(32)
    ttl = settings.security.jwt_refresh_token_ttl_seconds
    expires_at = datetime.now(tz=UTC) + timedelta(seconds=ttl)
    return NewRefreshToken(
        plaintext=plaintext,
        token_hash=hash_refresh_token(plaintext),
        expires_at=expires_at,
    )


def hash_refresh_token(plaintext: str) -> str:
    """Deterministic SHA-256 fingerprint for DB storage and lookup.

    Refresh tokens are already high-entropy random, so we don't need a slow
    KDF like argon2 — SHA-256 is fast and prevents replay if the DB leaks.
    """
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
