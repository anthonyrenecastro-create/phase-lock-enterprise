from fastapi.testclient import TestClient

from gateway.operator_webhook import app


def _admission_request(obj):
    return {
        "apiVersion": "admission.k8s.io/v1",
        "kind": "AdmissionReview",
        "request": {
            "uid": "uid-1",
            "object": obj,
        },
    }


def test_validating_webhook_accepts_valid_resource():
    client = TestClient(app)
    payload = _admission_request({"spec": {"image": "ghcr.io/acme/phase-lock:latest", "replicas": 2}})
    res = client.post("/validate-platform-phaselock-io-v1alpha1-phaselockgateway", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["response"]["allowed"] is True


def test_validating_webhook_rejects_invalid_resource():
    client = TestClient(app)
    payload = _admission_request({"spec": {"replicas": 0}})
    res = client.post("/validate-platform-phaselock-io-v1alpha1-phaselockgateway", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["response"]["allowed"] is False


def test_conversion_webhook_converts_api_version():
    client = TestClient(app)
    payload = {
        "apiVersion": "apiextensions.k8s.io/v1",
        "kind": "ConversionReview",
        "request": {
            "uid": "uid-2",
            "desiredAPIVersion": "platform.phaselock.io/v1alpha1",
            "objects": [
                {
                    "apiVersion": "platform.phaselock.io/v1alpha1",
                    "kind": "PhaseLockGateway",
                    "metadata": {"name": "plg"},
                    "spec": {"image": "ghcr.io/acme/phase-lock:latest"},
                }
            ],
        },
    }
    res = client.post("/convert-platform-phaselock-io", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["response"]["result"]["status"] == "Success"
    assert body["response"]["convertedObjects"][0]["apiVersion"] == "platform.phaselock.io/v1alpha1"
