def _auth(user_id: str) -> dict[str, str]:
    return {"X-User-Id": user_id}


def _stabilize_payload(workspace_id: str, request_id: str, metric: float = 0.7) -> dict[str, object]:
    return {
        "tenant_id": "acme",
        "workspace_id": workspace_id,
        "request_id": request_id,
        "text": "summarize incident trend",
        "embedding": [0.01, -0.02, 0.03],
        "metric_window": [metric] * 24,
        "metadata": {},
    }


def _feedback_payload(workspace_id: str, request_id: str) -> dict[str, object]:
    return {
        "tenant_id": "acme",
        "workspace_id": workspace_id,
        "request_id": request_id,
        "corrected": True,
        "correction_score": 0.91,
        "observed_risk_level": "green",
        "metadata": {},
    }


def test_workspace_scoped_runtime_attribution_and_analytics(client):
    org_res = client.post("/v1/team/orgs", headers=_auth("owner-analytics"), json={"name": "Gamma Org"})
    assert org_res.status_code == 200
    org_id = org_res.json()["org_id"]

    ws_res = client.post(
        f"/v1/team/orgs/{org_id}/workspaces",
        headers=_auth("owner-analytics"),
        json={"name": "prod-workspace"},
    )
    assert ws_res.status_code == 200
    workspace_id = ws_res.json()["workspace_id"]

    key_res = client.post(
        f"/v1/team/workspaces/{workspace_id}/api-keys",
        headers=_auth("owner-analytics"),
        json={"name": "service-key"},
    )
    assert key_res.status_code == 200
    key_id = key_res.json()["key_id"]

    stabilize_res = client.post(
        "/v1/stabilize",
        headers={
            "X-User-Id": "owner-analytics",
            "X-Workspace-Id": workspace_id,
            "X-Workspace-Key-Id": key_id,
        },
        json=_stabilize_payload(workspace_id, "req-ana-1", metric=0.9),
    )
    assert stabilize_res.status_code == 200

    feedback_res = client.post(
        "/v1/feedback",
        headers={"X-User-Id": "owner-analytics", "X-Workspace-Id": workspace_id},
        json=_feedback_payload(workspace_id, "req-ana-1"),
    )
    assert feedback_res.status_code == 200

    scoped_telemetry = client.get(f"/v1/telemetry?workspace_id={workspace_id}")
    assert scoped_telemetry.status_code == 200
    metrics = scoped_telemetry.json()["metrics"]
    assert metrics["requests_total"] >= 1
    assert metrics["feedback_total"] >= 1

    analytics_res = client.get(
        f"/v1/team/workspaces/{workspace_id}/analytics?window_hours=24",
        headers=_auth("owner-analytics"),
    )
    assert analytics_res.status_code == 200
    analytics = analytics_res.json()
    assert analytics["workspace_id"] == workspace_id
    assert analytics["incident_preventions"]["total"] >= 0
    assert len(analytics["drift_trend"]) >= 1
    assert len(analytics["key_usage"]) == 1
    assert analytics["key_usage"][0]["use_count"] >= 1
    assert len(analytics["team_activity"]) >= 2

    org_activity = client.get(
        f"/v1/team/orgs/{org_id}/analytics/team-activity?window_hours=24&limit=20",
        headers=_auth("owner-analytics"),
    )
    assert org_activity.status_code == 200
    assert len(org_activity.json()) >= 2


def test_stabilize_rejects_mismatched_workspace_attribution(client):
    org_res = client.post("/v1/team/orgs", headers=_auth("owner-mismatch"), json={"name": "Mismatch Org"})
    assert org_res.status_code == 200
    org_id = org_res.json()["org_id"]

    ws1_res = client.post(
        f"/v1/team/orgs/{org_id}/workspaces",
        headers=_auth("owner-mismatch"),
        json={"name": "ws-1"},
    )
    assert ws1_res.status_code == 200
    ws1 = ws1_res.json()["workspace_id"]

    ws2_res = client.post(
        f"/v1/team/orgs/{org_id}/workspaces",
        headers=_auth("owner-mismatch"),
        json={"name": "ws-2"},
    )
    assert ws2_res.status_code == 200
    ws2 = ws2_res.json()["workspace_id"]

    bad = client.post(
        "/v1/stabilize",
        headers={"X-Workspace-Id": ws1},
        json=_stabilize_payload(ws2, "req-mismatch-1", metric=0.3),
    )
    assert bad.status_code == 400
    assert "mismatch" in bad.json()["detail"]
