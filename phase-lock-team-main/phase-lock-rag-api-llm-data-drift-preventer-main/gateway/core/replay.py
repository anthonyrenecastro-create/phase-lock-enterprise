from dataclasses import dataclass

from gateway.core.schemas import StabilizeRequest
from gateway.core.service import StabilizationService


@dataclass
class ReplayReport:
    total_requests: int
    incidents_prevented: int
    avg_drift_score: float


def replay_requests(service: StabilizationService, requests: list[StabilizeRequest]) -> ReplayReport:
    if not requests:
        return ReplayReport(total_requests=0, incidents_prevented=0, avg_drift_score=0.0)

    incidents_prevented = 0
    total_drift = 0.0

    for req in requests:
        out = service.stabilize(req)
        total_drift += out.drift_score
        if "fallback-model" in out.actions or "human-review" in out.actions:
            incidents_prevented += 1

    return ReplayReport(
        total_requests=len(requests),
        incidents_prevented=incidents_prevented,
        avg_drift_score=total_drift / len(requests),
    )
