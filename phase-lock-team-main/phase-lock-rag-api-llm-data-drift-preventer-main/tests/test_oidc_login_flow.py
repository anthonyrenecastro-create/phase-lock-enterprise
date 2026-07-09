import importlib
import pathlib
import sys
import types
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_fake_phase_lock_core() -> None:
    module = types.ModuleType("phase_lock_core")

    class DriftEngine:
        def __init__(self, nx: int, ny: int, n_fields: int, seed: int) -> None:
            self.nx = nx
            self.ny = ny
            self.n_fields = n_fields
            self.seed = seed

        def stabilize(self, metric_window: list[float], embedding: list[float] | None = None) -> dict[str, object]:
            return {
                "stabilized_vector": [0.0] * 24,
                "drift_score": 0.1,
                "euler_chi": 1.0,
                "genus": 0.5,
                "beta0": 1.0,
                "beta1": 0.0,
            }

    module.DriftEngine = DriftEngine
    sys.modules["phase_lock_core"] = module


def _build_client(monkeypatch) -> TestClient:
    monkeypatch.delenv("GATEWAY_API_KEY", raising=False)
    monkeypatch.setenv("TEAM_STORE_BACKEND", "memory")
    monkeypatch.setenv("AUTH_MODE", "oidc")
    monkeypatch.setenv("OIDC_ISSUER", "https://issuer.example.com")
    monkeypatch.setenv("OIDC_AUDIENCE", "phase-lock")
    monkeypatch.setenv("OIDC_JWKS_URL", "https://issuer.example.com/jwks")
    monkeypatch.setenv("OIDC_AUTHORIZATION_URL", "https://issuer.example.com/authorize")
    monkeypatch.setenv("OIDC_TOKEN_URL", "https://issuer.example.com/token")
    monkeypatch.setenv("OIDC_CLIENT_ID", "phase-lock-client")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "phase-lock-secret")
    monkeypatch.setenv("OIDC_SESSION_SECRET", "unit-test-session-secret")
    monkeypatch.setenv("OIDC_SESSION_MAX_LIFETIME_SECONDS", "7200")
    monkeypatch.setenv("OIDC_COOKIE_SECURE", "false")

    _install_fake_phase_lock_core()

    for name in [
        "gateway.core.team",
        "gateway.core.team_schemas",
        "gateway.core.service",
        "gateway.api.routes_auth",
        "gateway.api.routes_team",
        "gateway.api.routes_stabilize",
        "gateway.main",
    ]:
        if name in sys.modules:
            importlib.reload(sys.modules[name])
        else:
            importlib.import_module(name)

    main = sys.modules["gateway.main"]
    telemetry = importlib.import_module("gateway.core.telemetry")
    telemetry.telemetry_store.reset()
    team = importlib.import_module("gateway.core.team")
    team.team_store.reset()
    return TestClient(main.app)


def test_oidc_login_redirect_and_callback_session(monkeypatch):
    client = _build_client(monkeypatch)
    routes_auth = importlib.import_module("gateway.api.routes_auth")
    auth_mod = importlib.import_module("gateway.core.auth")

    login = client.get("/v1/auth/oidc/login?return_to=/dashboard", follow_redirects=False)
    assert login.status_code == 302

    location = login.headers["location"]
    parsed = urlparse(location)
    assert parsed.scheme == "https"
    assert parsed.netloc == "issuer.example.com"
    params = parse_qs(parsed.query)
    assert params["client_id"][0] == "phase-lock-client"
    assert params["response_type"][0] == "code"
    state = params["state"][0]

    monkeypatch.setattr(
        routes_auth,
        "exchange_authorization_code",
        lambda **_: {"id_token": "fake-id-token"},
    )
    monkeypatch.setattr(
        routes_auth,
        "verify_oidc_token",
        lambda *_args, **_kwargs: auth_mod.AuthContext(
            user_id="oidc-user-1",
            groups=("phase-lock-users",),
            auth_type="oidc",
        ),
    )

    callback = client.get(f"/v1/auth/oidc/callback?code=auth-code-1&state={state}", follow_redirects=False)
    assert callback.status_code == 302
    assert callback.headers["location"] == "/dashboard"
    assert "phase_lock_session=" in callback.headers["set-cookie"]

    session = client.get("/v1/auth/session")
    assert session.status_code == 200
    body = session.json()
    assert body["authenticated"] is True
    assert body["user_id"] == "oidc-user-1"
    assert body["auth_type"] == "oidc"

    refresh = client.post("/v1/auth/session/refresh")
    assert refresh.status_code == 200
    assert refresh.json()["status"] == "ok"
    assert "phase_lock_session=" in refresh.headers["set-cookie"]

    logout = client.post("/v1/auth/logout")
    assert logout.status_code == 200
    assert logout.json()["status"] == "ok"


def test_oidc_callback_rejects_replayed_state(monkeypatch):
    client = _build_client(monkeypatch)
    routes_auth = importlib.import_module("gateway.api.routes_auth")
    auth_mod = importlib.import_module("gateway.core.auth")

    login = client.get("/v1/auth/oidc/login", follow_redirects=False)
    assert login.status_code == 302
    state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]

    monkeypatch.setattr(routes_auth, "exchange_authorization_code", lambda **_: {"id_token": "fake-id-token"})
    monkeypatch.setattr(
        routes_auth,
        "verify_oidc_token",
        lambda *_args, **_kwargs: auth_mod.AuthContext(user_id="oidc-user-1", groups=("phase-lock-users",), auth_type="oidc"),
    )

    first = client.get(f"/v1/auth/oidc/callback?code=auth-code-1&state={state}", follow_redirects=False)
    assert first.status_code == 302

    replay = client.get(f"/v1/auth/oidc/callback?code=auth-code-1&state={state}", follow_redirects=False)
    assert replay.status_code == 401
    assert "already used" in replay.json()["detail"]


def test_oidc_auth_audit_log_records_login_refresh_logout(monkeypatch, tmp_path):
    log_path = tmp_path / "audit" / "auth.jsonl"
    monkeypatch.setenv("AUTH_AUDIT_LOG_PATH", str(log_path))
    client = _build_client(monkeypatch)
    routes_auth = importlib.import_module("gateway.api.routes_auth")
    auth_mod = importlib.import_module("gateway.core.auth")

    login = client.get("/v1/auth/oidc/login", follow_redirects=False)
    state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
    monkeypatch.setattr(routes_auth, "exchange_authorization_code", lambda **_: {"id_token": "fake-id-token"})
    monkeypatch.setattr(
        routes_auth,
        "verify_oidc_token",
        lambda *_args, **_kwargs: auth_mod.AuthContext(user_id="oidc-user-2", groups=("phase-lock-users",), auth_type="oidc"),
    )

    callback = client.get(f"/v1/auth/oidc/callback?code=auth-code-2&state={state}", follow_redirects=False)
    assert callback.status_code == 302
    assert client.post("/v1/auth/session/refresh").status_code == 200
    assert client.post("/v1/auth/logout").status_code == 200

    lines = [line.strip() for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) >= 3
    events = [line for line in lines if "oidc." in line]
    assert any("oidc.login" in line for line in events)
    assert any("oidc.refresh" in line for line in events)
    assert any("oidc.logout" in line for line in events)
