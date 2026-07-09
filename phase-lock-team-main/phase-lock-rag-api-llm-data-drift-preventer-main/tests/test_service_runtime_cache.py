import importlib
import pathlib
import sys
import types

from gateway.core.schemas import StabilizeRequest

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
                "genus": 0.0,
                "beta0": 1.0,
                "beta1": 0.0,
            }

    module.DriftEngine = DriftEngine
    sys.modules["phase_lock_core"] = module


def test_service_does_not_cache_tenant_runtime_when_disabled(monkeypatch):
    monkeypatch.setenv("TENANT_RUNTIME_CACHE_ENABLED", "false")
    _install_fake_phase_lock_core()

    if "gateway.core.service" in sys.modules:
        importlib.reload(sys.modules["gateway.core.service"])
    else:
        importlib.import_module("gateway.core.service")

    service_mod = sys.modules["gateway.core.service"]
    service = service_mod.StabilizationService()

    req = StabilizeRequest(
        tenant_id="acme",
        request_id="req-service-1",
        metric_window=[0.1] * 24,
        metadata={},
    )
    out = service.stabilize(req)

    assert out.risk_level == "green"
    assert service._tenants == {}


def test_service_caches_tenant_runtime_when_enabled(monkeypatch):
    monkeypatch.setenv("TENANT_RUNTIME_CACHE_ENABLED", "true")
    _install_fake_phase_lock_core()

    if "gateway.core.service" in sys.modules:
        importlib.reload(sys.modules["gateway.core.service"])
    else:
        importlib.import_module("gateway.core.service")

    service_mod = sys.modules["gateway.core.service"]
    service = service_mod.StabilizationService()

    req = StabilizeRequest(
        tenant_id="acme",
        request_id="req-service-2",
        metric_window=[0.1] * 24,
        metadata={},
    )
    _ = service.stabilize(req)

    assert "acme" in service._tenants
