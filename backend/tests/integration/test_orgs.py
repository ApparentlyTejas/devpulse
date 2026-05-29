"""Integration tests for organizations endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

BASE_AUTH = "/api/v1/auth"
BASE_ORGS = "/api/v1/organizations"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _register(client: AsyncClient, email: str, password: str = "password99") -> dict:  # noqa: S107
    resp = await client.post(f"{BASE_AUTH}/register", json={"email": email, "password": password})
    assert resp.status_code == 201
    return resp.json()


async def _auth_headers(client: AsyncClient, email: str, password: str = "password99") -> dict:  # noqa: S107
    tokens = await _register(client, email, password)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


# ---------------------------------------------------------------------------
# Create org
# ---------------------------------------------------------------------------


async def test_create_org(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "owner@example.com")
    resp = await client.post(
        BASE_ORGS,
        json={"name": "Acme Corp", "slug": "acme"},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["slug"] == "acme"
    assert body["name"] == "Acme Corp"


async def test_create_org_duplicate_slug_returns_409(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "owner2@example.com")
    await client.post(BASE_ORGS, json={"name": "First", "slug": "dup-slug"}, headers=headers)
    resp = await client.post(
        BASE_ORGS, json={"name": "Second", "slug": "dup-slug"}, headers=headers
    )
    assert resp.status_code == 409


async def test_create_org_invalid_slug_returns_422(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "owner3@example.com")
    resp = await client.post(BASE_ORGS, json={"name": "Bad", "slug": "Has Spaces"}, headers=headers)
    assert resp.status_code == 422


async def test_create_org_unauthenticated_returns_403(client: AsyncClient) -> None:
    resp = await client.post(BASE_ORGS, json={"name": "X", "slug": "x-org"})
    assert resp.status_code in {401, 403}


# ---------------------------------------------------------------------------
# List orgs
# ---------------------------------------------------------------------------


async def test_list_orgs_returns_own_orgs(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "lister@example.com")
    await client.post(BASE_ORGS, json={"name": "Org A", "slug": "org-a-lister"}, headers=headers)
    await client.post(BASE_ORGS, json={"name": "Org B", "slug": "org-b-lister"}, headers=headers)

    resp = await client.get(BASE_ORGS, headers=headers)
    assert resp.status_code == 200
    slugs = {o["slug"] for o in resp.json()}
    assert {"org-a-lister", "org-b-lister"} <= slugs


async def test_list_orgs_does_not_return_other_users_orgs(client: AsyncClient) -> None:
    owner_headers = await _auth_headers(client, "org-owner@example.com")
    await client.post(
        BASE_ORGS, json={"name": "Private", "slug": "private-org"}, headers=owner_headers
    )

    other_headers = await _auth_headers(client, "other-user@example.com")
    resp = await client.get(BASE_ORGS, headers=other_headers)
    assert resp.status_code == 200
    slugs = {o["slug"] for o in resp.json()}
    assert "private-org" not in slugs


# ---------------------------------------------------------------------------
# Get / Update / Delete org
# ---------------------------------------------------------------------------


async def test_get_org(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "getter@example.com")
    created = (
        await client.post(
            BASE_ORGS, json={"name": "Getter Org", "slug": "getter-org"}, headers=headers
        )
    ).json()

    resp = await client.get(f"{BASE_ORGS}/{created['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["slug"] == "getter-org"


async def test_get_org_nonmember_returns_404(client: AsyncClient) -> None:
    owner_h = await _auth_headers(client, "og-owner@example.com")
    org = (
        await client.post(BASE_ORGS, json={"name": "Secret", "slug": "secret-org"}, headers=owner_h)
    ).json()

    stranger_h = await _auth_headers(client, "stranger@example.com")
    resp = await client.get(f"{BASE_ORGS}/{org['id']}", headers=stranger_h)
    assert resp.status_code == 404


async def test_update_org_name(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "updater@example.com")
    org = (
        await client.post(
            BASE_ORGS, json={"name": "Old Name", "slug": "update-me"}, headers=headers
        )
    ).json()

    resp = await client.patch(
        f"{BASE_ORGS}/{org['id']}", json={"name": "New Name"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


async def test_delete_org(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "deleter@example.com")
    org = (
        await client.post(
            BASE_ORGS, json={"name": "To Delete", "slug": "delete-me"}, headers=headers
        )
    ).json()

    resp = await client.delete(f"{BASE_ORGS}/{org['id']}", headers=headers)
    assert resp.status_code == 204

    resp2 = await client.get(f"{BASE_ORGS}/{org['id']}", headers=headers)
    assert resp2.status_code == 404


async def test_update_org_as_member_returns_403(client: AsyncClient) -> None:
    owner_h = await _auth_headers(client, "org-owner2@example.com")
    member_tokens = await _register(client, "plain-member@example.com")
    member_h = {"Authorization": f"Bearer {member_tokens['access_token']}"}

    org = (
        await client.post(
            BASE_ORGS, json={"name": "Protected", "slug": "protected-org"}, headers=owner_h
        )
    ).json()

    # Add member
    # We need the member's user_id — get it from /me
    me = (await client.get(f"{BASE_AUTH}/me", headers=member_h)).json()
    await client.post(
        f"{BASE_ORGS}/{org['id']}/members",
        json={"user_id": me["id"], "role": "member"},
        headers=owner_h,
    )

    resp = await client.patch(f"{BASE_ORGS}/{org['id']}", json={"name": "Hacked"}, headers=member_h)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Membership management
# ---------------------------------------------------------------------------


async def test_list_members_includes_owner(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "member-owner@example.com")
    org = (
        await client.post(
            BASE_ORGS, json={"name": "Members Org", "slug": "members-org"}, headers=headers
        )
    ).json()

    resp = await client.get(f"{BASE_ORGS}/{org['id']}/members", headers=headers)
    assert resp.status_code == 200
    members = resp.json()
    assert len(members) == 1
    assert members[0]["role"] == "owner"


async def test_add_member(client: AsyncClient) -> None:
    owner_h = await _auth_headers(client, "adder-owner@example.com")
    new_member_tokens = await _register(client, "new-member@example.com")
    new_member_h = {"Authorization": f"Bearer {new_member_tokens['access_token']}"}

    org = (
        await client.post(
            BASE_ORGS, json={"name": "Add Test Org", "slug": "add-test-org"}, headers=owner_h
        )
    ).json()
    new_member_me = (await client.get(f"{BASE_AUTH}/me", headers=new_member_h)).json()

    resp = await client.post(
        f"{BASE_ORGS}/{org['id']}/members",
        json={"user_id": new_member_me["id"], "role": "member"},
        headers=owner_h,
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "member"
    assert resp.json()["user"]["email"] == "new-member@example.com"


async def test_add_duplicate_member_returns_409(client: AsyncClient) -> None:
    owner_h = await _auth_headers(client, "dup-owner@example.com")
    dup_member_tokens = await _register(client, "dup-member@example.com")
    dup_member_h = {"Authorization": f"Bearer {dup_member_tokens['access_token']}"}

    org = (
        await client.post(
            BASE_ORGS, json={"name": "Dup Org", "slug": "dup-member-org"}, headers=owner_h
        )
    ).json()
    me = (await client.get(f"{BASE_AUTH}/me", headers=dup_member_h)).json()

    await client.post(
        f"{BASE_ORGS}/{org['id']}/members",
        json={"user_id": me["id"], "role": "member"},
        headers=owner_h,
    )
    resp = await client.post(
        f"{BASE_ORGS}/{org['id']}/members",
        json={"user_id": me["id"], "role": "member"},
        headers=owner_h,
    )
    assert resp.status_code == 409


async def test_remove_last_owner_returns_422(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "lonely-owner@example.com")
    me = (await client.get(f"{BASE_AUTH}/me", headers=headers)).json()
    org = (
        await client.post(
            BASE_ORGS, json={"name": "Lonely Org", "slug": "lonely-org"}, headers=headers
        )
    ).json()

    resp = await client.delete(f"{BASE_ORGS}/{org['id']}/members/{me['id']}", headers=headers)
    assert resp.status_code == 422


async def test_update_member_role(client: AsyncClient) -> None:
    owner_h = await _auth_headers(client, "role-owner@example.com")
    target_tokens = await _register(client, "role-target@example.com")
    target_h = {"Authorization": f"Bearer {target_tokens['access_token']}"}

    org = (
        await client.post(BASE_ORGS, json={"name": "Role Org", "slug": "role-org"}, headers=owner_h)
    ).json()
    target_me = (await client.get(f"{BASE_AUTH}/me", headers=target_h)).json()

    await client.post(
        f"{BASE_ORGS}/{org['id']}/members",
        json={"user_id": target_me["id"], "role": "member"},
        headers=owner_h,
    )

    resp = await client.patch(
        f"{BASE_ORGS}/{org['id']}/members/{target_me['id']}",
        json={"role": "admin"},
        headers=owner_h,
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"
