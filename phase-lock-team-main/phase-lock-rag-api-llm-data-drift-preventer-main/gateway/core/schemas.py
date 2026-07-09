from typing import Any, Literal

from pydantic import BaseModel, Field, conlist

RiskLevel = Literal["green", "yellow", "red"]
ActionType = Literal["pass", "clamp", "retry", "fallback-model", "human-review"]


class StabilizeRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128)
    request_id: str = Field(..., min_length=1, max_length=128)
    workspace_id: str | None = Field(default=None, min_length=1, max_length=128)
    text: str | None = None
    embedding: list[float] | None = None
    metric_window: conlist(float, min_length=24, max_length=4096)
    metadata: dict[str, Any] = Field(default_factory=dict, max_length=128)


class StabilizeResponse(BaseModel):
    request_id: str
    stabilized_vector: conlist(float, min_length=24, max_length=24)
    drift_score: float
    risk_level: RiskLevel
    actions: list[ActionType]
    diagnostics: dict[str, float]


class FeedbackRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128)
    request_id: str = Field(..., min_length=1, max_length=128)
    workspace_id: str | None = Field(default=None, min_length=1, max_length=128)
    corrected: bool
    correction_score: float = Field(..., ge=0.0, le=1.0)
    observed_risk_level: RiskLevel | None = None
    metadata: dict[str, Any] = Field(default_factory=dict, max_length=128)
