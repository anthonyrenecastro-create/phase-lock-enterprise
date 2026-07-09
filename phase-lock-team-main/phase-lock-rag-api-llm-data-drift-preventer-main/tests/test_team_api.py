def _auth(user_id: str) -> dict[str, str]:
    return {"X-User-Id": user_id}


def test_team_org_workspace_and_member_flow(client):
    org_res = client.post("/v1/team/orgs", headers=_auth("owner-1"), json={"name": "Acme AI"})
    assert org_res.status_code == 200
    org = org_res.json()

    forbidden_workspace = client.post(
        f"/v1/team/orgs/{org['org_id']}/workspaces",
        headers=_auth("viewer-1"),
        json={"name": "production-rag"},
    )
    assert forbidden_workspace.status_code == 403

    add_admin = client.post(
        f"/v1/team/orgs/{org['org_id']}/members",
        headers=_auth("owner-1"),
        json={"user_id": "admin-1", "role": "admin"},
    )
    assert add_admin.status_code == 200

    workspace_res = client.post(
        f"/v1/team/orgs/{org['org_id']}/workspaces",
        headers=_auth("admin-1"),
        json={"name": "production-rag"},
    )
    assert workspace_res.status_code == 200

    members_res = client.get(f"/v1/team/orgs/{org['org_id']}/members", headers=_auth("admin-1"))
    assert members_res.status_code == 200
    members = members_res.json()
    member_ids = {m["user_id"] for m in members}
    assert member_ids.issuperset({"owner-1", "admin-1"})


def test_team_api_key_management_and_audit(client):
    org_res = client.post("/v1/team/orgs", headers=_auth("owner-2"), json={"name": "Beta Org"})
    assert org_res.status_code == 200
    org_id = org_res.json()["org_id"]

    workspace_res = client.post(
        f"/v1/team/orgs/{org_id}/workspaces",
        headers=_auth("owner-2"),
        json={"name": "staging"},
    )
    assert workspace_res.status_code == 200
    workspace_id = workspace_res.json()["workspace_id"]

    create_key = client.post(
        f"/v1/team/workspaces/{workspace_id}/api-keys",
        headers=_auth("owner-2"),
        json={"name": "ci-deploy"},
    )
    assert create_key.status_code == 200
    key_body = create_key.json()
    assert key_body["api_key"].startswith("plk_")
    key_id = key_body["key_id"]

    keys_before = client.get(f"/v1/team/workspaces/{workspace_id}/api-keys", headers=_auth("owner-2"))
    assert keys_before.status_code == 200
    assert len(keys_before.json()) == 1
    assert keys_before.json()[0]["revoked"] is False

    revoke_key = client.delete(
        f"/v1/team/workspaces/{workspace_id}/api-keys/{key_id}",
        headers=_auth("owner-2"),
    )
    assert revoke_key.status_code == 200
    assert revoke_key.json()["revoked"] is True

    audit = client.get(f"/v1/team/orgs/{org_id}/audit", headers=_auth("owner-2"))
    assert audit.status_code == 200
    actions = {event["action"] for event in audit.json()}
    assert actions.issuperset({"org.created", "workspace.created", "api_key.created", "api_key.revoked"})


def test_team_requires_user_header(client):
    missing_user = client.post("/v1/team/orgs", json={"name": "No User"})
    assert missing_user.status_code == 401
    assert "X-User-Id" in missing_user.json()["detail"]
