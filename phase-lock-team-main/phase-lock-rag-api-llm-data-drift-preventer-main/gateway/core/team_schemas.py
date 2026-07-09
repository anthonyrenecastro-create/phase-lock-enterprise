from typing import Literal

from pydantic import BaseModel, Field


Role = Literal["viewer", "analyst", "admin", "owner"]


class CreateOrgRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=128)


class OrgResponse(BaseModel):
    org_id: str
    name: str
    created_by: str
    created_at: str


class AddMemberRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128)
    role: Role


class MemberResponse(BaseModel):
    org_id: str
    user_id: str
    role: Role
    created_at: str


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=128)


class WorkspaceResponse(BaseModel):
    workspace_id: str
    org_id: str
    name: str
    created_by: str
    created_at: str


class CreateApiKeyRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=128)


class ApiKeyResponse(BaseModel):
    key_id: str
    workspace_id: str
    name: str
    key_prefix: str
    created_by: str
    created_at: str
    revoked: bool


class CreateApiKeyResponse(ApiKeyResponse):
    api_key: str


class AuditEventResponse(BaseModel):
    event_id: str
    org_id: str
    workspace_id: str | None
    actor_user_id: str
    action: str
    resource_type: str
    resource_id: str
    at: str
    request_id: str | None = None
    drift_score: float | None = None
    prevented_incident: bool | None = None
    api_key_id: str | None = None
    corrected: bool | None = None
    risk_level: str | None = None


class DriftTrendPointResponse(BaseModel):
    bucket: str
    avg_drift_score: float
    request_count: int


class IncidentPreventionResponse(BaseModel):
    total: int
    rate: float


class ApiKeyUsageResponse(BaseModel):
    key_id: str
    name: str
    revoked: bool
    use_count: int
    last_used_at: str | None = None


class TeamActivityResponse(BaseModel):
    actor_user_id: str
    action: str
    resource_type: str
    resource_id: str
    at: str


class WorkspaceAnalyticsResponse(BaseModel):
    workspace_id: str
    org_id: str
    window_hours: int
    drift_trend: list[DriftTrendPointResponse]
    incident_preventions: IncidentPreventionResponse
    key_usage: list[ApiKeyUsageResponse]
    team_activity: list[TeamActivityResponse]
    feedback_total: int