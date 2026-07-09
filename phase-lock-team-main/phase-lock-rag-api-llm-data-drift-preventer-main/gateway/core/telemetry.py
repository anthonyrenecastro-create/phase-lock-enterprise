from dataclasses import asdict, dataclass
from threading import Lock
from time import perf_counter


@dataclass
class TelemetrySnapshot:
    requests_total: int
    stabilize_success_total: int
    stabilize_error_total: int
    drift_incidents_prevented: int
    feedback_total: int
    false_positive_total: int
    p95_latency_ms: float


@dataclass
class _MutableCounters:
    requests_total: int = 0
    stabilize_success_total: int = 0
    stabilize_error_total: int = 0
    drift_incidents_prevented: int = 0
    feedback_total: int = 0
    false_positive_total: int = 0
    latencies_ms: list[float] | None = None

    def __post_init__(self) -> None:
        if self.latencies_ms is None:
            self.latencies_ms = []

    def snapshot(self) -> TelemetrySnapshot:
        latencies = sorted(self.latencies_ms or [])
        if not latencies:
            p95 = 0.0
        else:
            index = max(0, min(len(latencies) - 1, int(0.95 * (len(latencies) - 1))))
            p95 = float(latencies[index])

        return TelemetrySnapshot(
            requests_total=self.requests_total,
            stabilize_success_total=self.stabilize_success_total,
            stabilize_error_total=self.stabilize_error_total,
            drift_incidents_prevented=self.drift_incidents_prevented,
            feedback_total=self.feedback_total,
            false_positive_total=self.false_positive_total,
            p95_latency_ms=p95,
        )


class TelemetryStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._global = _MutableCounters()
        self._workspace_scoped: dict[tuple[str, str], _MutableCounters] = {}

    def start_timer(self) -> float:
        return perf_counter()

    def _bucket(self, org_id: str | None, workspace_id: str | None) -> _MutableCounters | None:
        if org_id is None or workspace_id is None:
            return None
        key = (org_id, workspace_id)
        scoped = self._workspace_scoped.get(key)
        if scoped is None:
            scoped = _MutableCounters()
            self._workspace_scoped[key] = scoped
        return scoped

    def observe_stabilize(
        self,
        started_at: float,
        success: bool,
        prevented_incident: bool,
        org_id: str | None = None,
        workspace_id: str | None = None,
    ) -> None:
        elapsed_ms = (perf_counter() - started_at) * 1000.0
        with self._lock:
            for counters in [self._global, self._bucket(org_id, workspace_id)]:
                if counters is None:
                    continue
                counters.requests_total += 1
                if success:
                    counters.stabilize_success_total += 1
                else:
                    counters.stabilize_error_total += 1
                if prevented_incident:
                    counters.drift_incidents_prevented += 1
                counters.latencies_ms.append(elapsed_ms)
                if len(counters.latencies_ms) > 5000:
                    counters.latencies_ms = counters.latencies_ms[-5000:]

    def observe_feedback(
        self,
        corrected: bool,
        risk_level: str | None,
        org_id: str | None = None,
        workspace_id: str | None = None,
    ) -> None:
        with self._lock:
            for counters in [self._global, self._bucket(org_id, workspace_id)]:
                if counters is None:
                    continue
                counters.feedback_total += 1
                if corrected and risk_level == "green":
                    counters.false_positive_total += 1

    def snapshot(self, org_id: str | None = None, workspace_id: str | None = None) -> TelemetrySnapshot:
        with self._lock:
            if org_id is None or workspace_id is None:
                return self._global.snapshot()
            counters = self._workspace_scoped.get((org_id, workspace_id), _MutableCounters())
            return counters.snapshot()

    def as_json(self, org_id: str | None = None, workspace_id: str | None = None) -> dict[str, float | int]:
        return asdict(self.snapshot(org_id=org_id, workspace_id=workspace_id))

    def reset(self) -> None:
        with self._lock:
            self._global = _MutableCounters()
            self._workspace_scoped = {}

    def as_prometheus(self, org_id: str | None = None, workspace_id: str | None = None) -> str:
        s = self.snapshot(org_id=org_id, workspace_id=workspace_id)
        labels = ""
        if org_id is not None and workspace_id is not None:
            labels = f'{{org_id="{org_id}",workspace_id="{workspace_id}"}}'

        lines = [
            "# TYPE gateway_requests_total counter",
            f"gateway_requests_total{labels} {s.requests_total}",
            "# TYPE gateway_stabilize_success_total counter",
            f"gateway_stabilize_success_total{labels} {s.stabilize_success_total}",
            "# TYPE gateway_stabilize_error_total counter",
            f"gateway_stabilize_error_total{labels} {s.stabilize_error_total}",
            "# TYPE gateway_drift_incidents_prevented_total counter",
            f"gateway_drift_incidents_prevented_total{labels} {s.drift_incidents_prevented}",
            "# TYPE gateway_feedback_total counter",
            f"gateway_feedback_total{labels} {s.feedback_total}",
            "# TYPE gateway_false_positive_total counter",
            f"gateway_false_positive_total{labels} {s.false_positive_total}",
            "# TYPE gateway_stabilize_latency_p95_ms gauge",
            f"gateway_stabilize_latency_p95_ms{labels} {s.p95_latency_ms:.3f}",
        ]
        return "\n".join(lines) + "\n"


telemetry_store = TelemetryStore()
