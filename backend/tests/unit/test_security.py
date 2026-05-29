"""Unit tests for app/modules/auth/security.py.

All tests are pure-Python — no DB or network required.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from freezegun import freeze_time

from app.modules.auth.security import (
    InvalidAccessTokenError,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    mint_access_token,
    password_needs_rehash,
    verify_password,
)

USER_ID = uuid4()
EMAIL = "test@example.com"


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def test_hash_and_verify_roundtrip() -> None:
    hashed = hash_password("hunter2")
    assert verify_password("hunter2", hashed)


def test_wrong_password_returns_false() -> None:
    hashed = hash_password("correct")
    assert not verify_password("wrong", hashed)


def test_needs_rehash_false_for_fresh_hash() -> None:
    hashed = hash_password("password123")
    assert not password_needs_rehash(hashed)


# ---------------------------------------------------------------------------
# JWT access tokens
# ---------------------------------------------------------------------------


def test_mint_and_decode_roundtrip() -> None:
    token, exp = mint_access_token(
        user_id=USER_ID,
        email=EMAIL,
        org_id=None,
        role=None,
    )
    claims = decode_access_token(token)

    assert claims.sub == USER_ID
    assert claims.email == EMAIL
    assert claims.org_id is None
    assert claims.role is None
    assert isinstance(claims.jti, UUID)
    # JWT exp is stored as an integer timestamp, so microseconds are truncated.
    assert claims.exp == exp.replace(microsecond=0)


def test_decode_with_org_and_role() -> None:
    org_id = uuid4()
    token, _ = mint_access_token(
        user_id=USER_ID,
        email=EMAIL,
        org_id=org_id,
        role="owner",
    )
    claims = decode_access_token(token)
    assert claims.org_id == org_id
    assert claims.role == "owner"


def test_tampered_token_raises() -> None:
    token, _ = mint_access_token(user_id=USER_ID, email=EMAIL, org_id=None, role=None)
    bad_token = token[:-4] + "XXXX"
    with pytest.raises(InvalidAccessTokenError):
        decode_access_token(bad_token)


def test_expired_token_raises() -> None:
    with freeze_time("2000-01-01"):
        token, _ = mint_access_token(user_id=USER_ID, email=EMAIL, org_id=None, role=None)

    # Now time has moved forward — token is expired
    with pytest.raises(InvalidAccessTokenError, match="Signature has expired|expired"):
        decode_access_token(token)


def test_claims_dataclass_is_frozen() -> None:
    token, _ = mint_access_token(user_id=USER_ID, email=EMAIL, org_id=None, role=None)
    claims = decode_access_token(token)
    with pytest.raises((AttributeError, TypeError)):
        claims.email = "other@example.com"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Refresh tokens
# ---------------------------------------------------------------------------


def test_refresh_token_hash_is_deterministic() -> None:
    rt = generate_refresh_token()
    assert hash_refresh_token(rt.plaintext) == rt.token_hash


def test_refresh_token_plaintext_differs_from_hash() -> None:
    rt = generate_refresh_token()
    assert rt.plaintext != rt.token_hash


def test_refresh_token_has_future_expiry() -> None:
    rt = generate_refresh_token()
    assert rt.expires_at > datetime.now(tz=UTC)


def test_refresh_token_expiry_is_30_days_by_default() -> None:
    before = datetime.now(tz=UTC)
    rt = generate_refresh_token()
    after = datetime.now(tz=UTC)

    expected_min = before + timedelta(days=29)
    expected_max = after + timedelta(days=31)
    assert expected_min < rt.expires_at < expected_max
