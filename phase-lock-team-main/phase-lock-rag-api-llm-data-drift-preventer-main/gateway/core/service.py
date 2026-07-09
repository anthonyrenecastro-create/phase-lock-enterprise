from typing import Any
from dataclasses import dataclass
from threading import Lock

from phase_lock_core import DriftEngine

from gateway.core.config import GatewaySettings, load_settings
from gateway.core.policy import decide_actions
from gateway.core.schemas import StabilizeRequest, StabilizeResponse
from gateway.core.state_backend import StateBackend, get_state_backend


@dataclass
class TenantRuntime:
    engine: DriftEngine


class StabilizationService:
    def __init__(self) -> None:
        self.settings: GatewaySettings = load_settings()
        self.state_backend: StateBackend = get_state_backend(self.settings)
        self._lock = Lock()
        self._tenants: dict[str, TenantRuntime] = {}

    def _spike_key(self, tenant_id: str) -> str:
        return f"tenant:{tenant_id}:spike_streak"

    def _tenant_runtime(self, tenant_id: str) -> TenantRuntime:
        if not self.settings.tenant_runtime_cache_enabled:
            return TenantRuntime(engine=DriftEngine(nx=18, ny=18, n_fields=10, seed=self.settings.default_seed))

        with self._lock:
            runtime = self._tenants.get(tenant_id)
            if runtime is None:
                runtime = TenantRuntime(
                    engine=DriftEngine(nx=18, ny=18, n_fields=10, seed=self.settings.default_seed),
                )
                self._tenants[tenant_id] = runtime
            return runtime

    def _bounded_metric_window(self, req: StabilizeRequest) -> list[float]:
        window = req.metric_window
        if len(window) > self.settings.max_metric_window:
            raise ValueError(
                f"metric_window exceeds MAX_METRIC_WINDOW={self.settings.max_metric_window}"
            )

        requested_steps = int(req.metadata.get("step_cap", len(window)))
        requested_steps = max(24, requested_steps)
        budget_steps = int(req.metadata.get("compute_budget_steps", requested_steps))
        capped_steps = min(requested_steps, budget_steps, self.settings.max_compute_steps)

        if capped_steps < 24:
            raise ValueError("compute budget must allow at least 24 steps")

        if len(window) <= capped_steps:
            return list(window)

        # Uniform downsample to honor cost controls while keeping bounded behavior.
        span = len(window) - 1
        out: list[float] = []
        for i in range(capped_steps):
            idx = round(i * span / (capped_steps - 1))
            out.append(float(window[idx]))
        return out

    def stabilize(self, req: StabilizeRequest) -> StabilizeResponse:
        runtime = self._tenant_runtime(req.tenant_id)
        metric_window = self._bounded_metric_window(req)

        out: dict[str, Any] = runtime.engine.stabilize(
            metric_window=metric_window,
            embedding=req.embedding,
        )

        drift_score = float(out["drift_score"])
        spike_key = self._spike_key(req.tenant_id)
        if drift_score >= self.settings.drift_spike_threshold:
            spike_streak = self.state_backend.incr_int(spike_key, delta=1, ttl_seconds=3600)
        else:
            # Reset streak eagerly when score recovers.
            spike_streak = 0
            self.state_backend.set_int(spike_key, spike_streak, ttl_seconds=3600)

        breaker_open = spike_streak >= self.settings.breaker_trip_count
        risk, actions = decide_actions(
            drift_score=drift_score,
            breaker_open=breaker_open,
            settings=self.settings,
        )

        return StabilizeResponse(
            request_id=req.request_id,
            stabilized_vector=[float(x) for x in out["stabilized_vector"]],
            drift_score=drift_score,
            risk_level=risk,
            actions=actions,
            diagnostics={
                "euler_chi": float(out.get("euler_chi", 0.0)),
                "genus": float(out.get("genus", 0.0)),
                "beta0": float(out.get("beta0", 0.0)),
                "beta1": float(out.get("beta1", 0.0)),
                "energy_level": float(out.get("energy_level", 0.0)),
                "stress_level": float(out.get("stress_level", 0.0)),
                "drift_ema": float(out.get("drift_ema", drift_score)),
                "drift_trend": float(out.get("drift_trend", 0.0)),
                "topology_volatility": float(out.get("topology_volatility", 0.0)),
                "surgery_rate": float(out.get("surgery_rate", 0.0)),
                "surgery_total": float(out.get("surgery_total", 0.0)),
                "breaker_open": 1.0 if breaker_open else 0.0,
                "spike_streak": float(spike_streak),
                "effective_window": float(len(metric_window)),
            },
        )
