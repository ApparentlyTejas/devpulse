"""Integration tests for auth endpoints.

Each test gets a fresh DB session (SAVEPOINT rollback) and a real HTTP client.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

BASE = "/api/v1/auth"


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------


async def test_register_creates_user_and_returns_tokens(client: AsyncClient) -> None:
    resp = await client.post(
        f"{BASE}/register",
        json={"email": "alice@example.com", "password": "securepass1"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"  # noqa: S105


async def test_register_duplicate_email_returns_409(client: AsyncClient) -> None:
    payload = {"email": "bob@example.com", "password": "password123"}
    await client.post(f"{BASE}/register", json=payload)
    resp = await client.post(f"{BASE}/register", json=payload)
    assert resp.status_code == 409


async def test_register_normalizes_email_case(client: AsyncClient) -> None:
    await client.post(
        f"{BASE}/register", json={"email": "Carol@example.com", "password": "pw123456"}
    )
    resp = await client.post(
        f"{BASE}/register", json={"email": "carol@example.com", "password": "pw123456"}
    )
    assert resp.status_code == 409


async def test_register_short_password_returns_422(client: AsyncClient) -> None:
    resp = await client.post(
        f"{BASE}/register",
        json={"email": "dave@example.com", "password": "short"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


async def test_login_valid_credentials(client: AsyncClient) -> None:
    email, password = "eve@example.com", "goodpassword"
    await client.post(f"{BASE}/register", json={"email": email, "password": password})

    resp = await client.post(f"{BASE}/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_login_wrong_password_returns_401(client: AsyncClient) -> None:
    email = "frank@example.com"
    await client.post(f"{BASE}/register", json={"email": email, "password": "correctpass"})

    resp = await client.post(f"{BASE}/login", json={"email": email, "password": "wrongpass"})
    assert resp.status_code == 401


async def test_login_unknown_email_returns_401(client: AsyncClient) -> None:
    resp = await client.post(
        f"{BASE}/login",
        json={"email": "nobody@example.com", "password": "password123"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------


async def test_refresh_rotates_token(client: AsyncClient) -> None:
    reg = await client.post(
        f"{BASE}/register",
        json={"email": "grace@example.com", "password": "password99"},
    )
    original_rt = reg.json()["refresh_token"]

    resp = await client.post(f"{BASE}/refresh", json={"refresh_token": original_rt})
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["refresh_token"] != original_rt


async def test_refresh_used_token_returns_401(client: AsyncClient) -> None:
    reg = await client.post(
        f"{BASE}/register",
        json={"email": "henry@example.com", "password": "password99"},
    )
    rt = reg.json()["refresh_token"]

    await client.post(f"{BASE}/refresh", json={"refresh_token": rt})
    resp = await client.post(f"{BASE}/refresh", json={"refresh_token": rt})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


async def test_logout_succeeds(client: AsyncClient) -> None:
    reg = await client.post(
        f"{BASE}/register",
        json={"email": "iris@example.com", "password": "password99"},
    )
    rt = reg.json()["refresh_token"]

    resp = await client.post(f"{BASE}/logout", json={"refresh_token": rt})
    assert resp.status_code == 204


async def test_logout_then_refresh_fails(client: AsyncClient) -> None:
    reg = await client.post(
        f"{BASE}/register",
        json={"email": "jake@example.com", "password": "password99"},
    )
    rt = reg.json()["refresh_token"]

    await client.post(f"{BASE}/logout", json={"refresh_token": rt})
    resp = await client.post(f"{BASE}/refresh", json={"refresh_token": rt})
    assert resp.status_code == 401


async def test_logout_unknown_token_is_idempotent(client: AsyncClient) -> None:
    resp = await client.post(f"{BASE}/logout", json={"refresh_token": "nonexistent-token"})
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# /me
# ---------------------------------------------------------------------------


async def test_me_returns_current_user(client: AsyncClient) -> None:
    reg = await client.post(
        f"{BASE}/register",
        json={"email": "kate@example.com", "password": "password99", "full_name": "Kate"},
    )
    access_token = reg.json()["access_token"]

    resp = await client.get(f"{BASE}/me", headers={"Authorization": f"Bearer {access_token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "kate@example.com"
    assert body["full_name"] == "Kate"
    assert body["is_active"] is True


async def test_me_without_token_returns_403(client: AsyncClient) -> None:
    resp = await client.get(f"{BASE}/me")
    assert resp.status_code in {401, 403}


async def test_me_invalid_token_returns_401(client: AsyncClient) -> None:
    resp = await client.get(f"{BASE}/me", headers={"Authorization": "Bearer invalidtoken"})
    assert resp.status_code == 401
