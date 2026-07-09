def _base_payload(**overrides):
    payload = {
        "tenant_id": "acme",
        "request_id": "req-001",
        "text": "example input",
        "embedding": [0.05, -0.02, 0.01],
        "metric_window": [0.1] * 24,
        "metadata": {},
    }
    payload.update(overrides)
    return payload


def test_stabilize_returns_contract_shape(client):
    res = client.post("/v1/stabilize", json=_base_payload())
    assert res.status_code == 200

    data = res.json()
    assert data["request_id"] == "req-001"
    assert isinstance(data["stabilized_vector"], list)
    assert len(data["stabilized_vector"]) == 24
    assert 0.0 <= data["drift_score"] <= 1.0
    assert data["risk_level"] in {"green", "yellow", "red"}
    assert isinstance(data["actions"], list)
    assert set(data["diagnostics"]).issuperset(
        {"euler_chi", "genus", "beta0", "beta1", "breaker_open", "spike_streak", "effective_window"}
    )


def test_stabilize_requires_text_or_embedding(client):
    payload = _base_payload(text=None, embedding=None)
    res = client.post("/v1/stabilize", json=payload)
    assert res.status_code == 400
    assert "Provide at least one" in res.json()["detail"]


def test_feedback_and_telemetry_collect_slos(client):
    # Trigger one successful stabilize request.
    stabilize_res = client.post("/v1/stabilize", json=_base_payload())
    assert stabilize_res.status_code == 200

    # Send correction signal to drive false-positive counters.
    feedback_payload = {
        "tenant_id": "acme",
        "request_id": "req-001",
        "corrected": True,
        "correction_score": 0.9,
        "observed_risk_level": "green",
        "metadata": {},
    }
    feedback_res = client.post("/v1/feedback", json=feedback_payload)
    assert feedback_res.status_code == 200
    assert feedback_res.json()["status"] == "accepted"

    telemetry_json = client.get("/v1/telemetry")
    assert telemetry_json.status_code == 200
    body = telemetry_json.json()
    assert body["status"] == "ok"
    metrics = body["metrics"]
    assert metrics["requests_total"] >= 1
    assert metrics["stabilize_success_total"] >= 1
    assert metrics["feedback_total"] >= 1
    assert metrics["false_positive_total"] >= 1
    assert metrics["p95_latency_ms"] >= 0.0

    telemetry_prom = client.get("/v1/telemetry?format=prometheus")
    assert telemetry_prom.status_code == 200
    assert "gateway_requests_total" in telemetry_prom.text
    assert "gateway_stabilize_latency_p95_ms" in telemetry_prom.text


def test_api_key_enforced_when_configured(client, monkeypatch):
    monkeypatch.setenv("GATEWAY_API_KEY", "top-secret")

    unauthorized = client.post("/v1/feedback", json={
        "tenant_id": "acme",
        "request_id": "req-auth",
        "corrected": False,
        "correction_score": 0.2,
        "metadata": {},
    })
    assert unauthorized.status_code == 401

    authorized = client.post(
        "/v1/feedback",
        headers={"X-API-Key": "top-secret"},
        json={
            "tenant_id": "acme",
            "request_id": "req-auth",
            "corrected": False,
            "correction_score": 0.2,
            "metadata": {},
        },
    )
    assert authorized.status_code == 200


def test_health_includes_state_backend_status(client):
    res = client.get("/v1/health")
    assert res.status_code == 200
    payload = res.json()
    assert "state_backend" in payload
    assert payload["state_backend"]["backend"] in {"memory", "redis"}
