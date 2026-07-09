import importlib
import pathlib
import sys
import types

import pytest
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
            clean = [float(x) for x in metric_window]
            avg_abs = sum(abs(x) for x in clean) / max(1, len(clean))
            drift_score = max(0.0, min(1.0, avg_abs))

            anchor = 0.0 if not clean else clean[-1]
            stabilized_vector = [max(-1.0, min(1.0, anchor)) for _ in range(24)]

            euler_chi = max(-2.0, min(2.0, 2.0 - (2.0 * drift_score)))
            genus = max(0.0, min(2.0, (2.0 - euler_chi) / 2.0))

            return {
                "stabilized_vector": stabilized_vector,
                "drift_score": drift_score,
                "euler_chi": euler_chi,
                "genus": genus,
                "beta0": 1.0,
                "beta1": round(3.0 * drift_score),
            }

    module.DriftEngine = DriftEngine
    sys.modules["phase_lock_core"] = module


@pytest.fixture
def app_modules(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GATEWAY_API_KEY", raising=False)
    monkeypatch.setenv("TEAM_STORE_BACKEND", "memory")
    _install_fake_phase_lock_core()

    # Reload modules to ensure service singletons use the fake Rust extension.
    for name in [
        "gateway.core.team",
        "gateway.core.team_schemas",
        "gateway.core.service",
        "gateway.api.routes_team",
        "gateway.api.routes_stabilize",
        "gateway.main",
    ]:
        if name in sys.modules:
            importlib.reload(sys.modules[name])
        else:
            importlib.import_module(name)

    main = sys.modules["gateway.main"]
    routes = sys.modules["gateway.api.routes_stabilize"]
    telemetry = importlib.import_module("gateway.core.telemetry")
    telemetry.telemetry_store.reset()
    team = importlib.import_module("gateway.core.team")
    team.team_store.reset()
    return main, routes, telemetry


@pytest.fixture
def client(app_modules):
    main, _, _ = app_modules
    return TestClient(main.app)
