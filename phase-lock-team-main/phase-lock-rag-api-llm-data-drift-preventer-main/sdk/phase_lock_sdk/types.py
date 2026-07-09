from typing import Any, Literal, TypedDict


RiskLevel = Literal["green", "yellow", "red"]
ActionType = Literal["pass", "clamp", "retry", "fallback-model", "human-review"]


class StabilizeResponse(TypedDict):
    request_id: str
    stabilized_vector: list[float]
    drift_score: float
    risk_level: RiskLevel
    actions: list[ActionType]
    diagnostics: dict[str, float]


class FeedbackResponse(TypedDict):
    status: str
    request_id: str


class TelemetryResponse(TypedDict):
    status: str
    metrics: dict[str, Any]
