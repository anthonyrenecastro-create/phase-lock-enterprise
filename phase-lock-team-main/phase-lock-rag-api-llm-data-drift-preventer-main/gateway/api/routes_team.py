from fastapi import APIRouter, Depends, HTTPException

from gateway.core.auth import AuthContext, require_auth_context
from gateway.core.config import load_settings
from gateway.core.team import ROLE_RANK
from gateway.core.team import team_store
from gateway.core.team_schemas import (
    AddMemberRequest,
    ApiKeyResponse,
    AuditEventResponse,
    CreateApiKeyRequest,
    CreateApiKeyResponse,
    CreateOrgRequest,
    CreateWorkspaceRequest,
    MemberResponse,
    OrgResponse,
    TeamActivityResponse,
    WorkspaceAnalyticsResponse,
    WorkspaceResponse,
)

router = APIRouter(prefix="/v1/team", tags=["team-edition"])


def _require_actor_user_id(ctx: AuthContext) -> str:
    if not ctx.user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-Id header")
    return ctx.user_id


def _group_mapped_role(groups: tuple[str, ...]) -> str | None:
    settings = load_settings()
    mapped_roles = [role for group, role in settings.oidc_group_role_map if group in set(groups)]
    if not mapped_roles:
        return None
    return max(mapped_roles, key=lambda role: ROLE_RANK[role])


def _effective_role(org_id: str, ctx: AuthContext) -> str | None:
    user_id = _require_actor_user_id(ctx)
    direct_role = team_store.role_for(org_id=org_id, user_id=user_id)
    mapped_role = _group_mapped_role(ctx.groups)
    if direct_role is None:
        return mapped_role
    if mapped_role is None:
        return direct_role
    return max((direct_role, mapped_role), key=lambda role: ROLE_RANK[role])


def _require_org_role(org_id: str, ctx: AuthContext, minimum_role: str) -> str:
    org = team_store.get_org(org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    role = _effective_role(org_id=org_id, ctx=ctx)
    if role is None or ROLE_RANK[role] < ROLE_RANK[minimum_role]:
        raise HTTPException(status_code=403, detail="Insufficient role for organization")
    return _require_actor_user_id(ctx)


def _workspace_with_access(workspace_id: str, ctx: AuthContext, minimum_role: str):
    workspace = team_store.get_workspace(workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    role = _effective_role(workspace.org_id, ctx)
    if role is None or ROLE_RANK[role] < ROLE_RANK[minimum_role]:
        raise HTTPException(status_code=403, detail="Insufficient role for workspace")
    return workspace


@router.post("/orgs", response_model=OrgResponse)
def create_org(
    req: CreateOrgRequest,
    ctx: AuthContext = Depends(require_auth_context),
) -> OrgResponse:
    user_id = _require_actor_user_id(ctx)
    org = team_store.create_org(name=req.name, created_by=user_id)
    return OrgResponse(**org.__dict__)


@router.post("/orgs/{org_id}/members", response_model=MemberResponse)
def upsert_member(
    org_id: str,
    req: AddMemberRequest,
    ctx: AuthContext = Depends(require_auth_context),
) -> MemberResponse:
    user_id = _require_org_role(org_id=org_id, ctx=ctx, minimum_role="admin")
    member = team_store.add_member(org_id=org_id, actor_user_id=user_id, user_id=req.user_id, role=req.role)
    return MemberResponse(**member.__dict__)


@router.get("/orgs/{org_id}/members", response_model=list[MemberResponse])
def list_members(
    org_id: str,
    ctx: AuthContext = Depends(require_auth_context),
) -> list[MemberResponse]:
    _require_org_role(org_id=org_id, ctx=ctx, minimum_role="viewer")
    members = team_store.list_members(org_id)
    return [MemberResponse(**m.__dict__) for m in members]


@router.post("/orgs/{org_id}/workspaces", response_model=WorkspaceResponse)
def create_workspace(
    org_id: str,
    req: CreateWorkspaceRequest,
    ctx: AuthContext = Depends(require_auth_context),
) -> WorkspaceResponse:
    user_id = _require_org_role(org_id=org_id, ctx=ctx, minimum_role="admin")
    workspace = team_store.create_workspace(org_id=org_id, actor_user_id=user_id, name=req.name)
    return WorkspaceResponse(**workspace.__dict__)


@router.post("/workspaces/{workspace_id}/api-keys", response_model=CreateApiKeyResponse)
def create_api_key(
    workspace_id: str,
    req: CreateApiKeyRequest,
    ctx: AuthContext = Depends(require_auth_context),
) -> CreateApiKeyResponse:
    user_id = _require_actor_user_id(ctx)
    workspace = _workspace_with_access(workspace_id=workspace_id, ctx=ctx, minimum_role="admin")
    record, raw_key = team_store.create_api_key(workspace_id=workspace.workspace_id, actor_user_id=user_id, name=req.name)
    return CreateApiKeyResponse(api_key=raw_key, **record.__dict__)


@router.get("/workspaces/{workspace_id}/api-keys", response_model=list[ApiKeyResponse])
def list_api_keys(
    workspace_id: str,
    ctx: AuthContext = Depends(require_auth_context),
) -> list[ApiKeyResponse]:
    _workspace_with_access(workspace_id=workspace_id, ctx=ctx, minimum_role="admin")
    keys = team_store.list_api_keys(workspace_id=workspace_id)
    return [ApiKeyResponse(**k.__dict__) for k in keys]


@router.delete("/workspaces/{workspace_id}/api-keys/{key_id}", response_model=ApiKeyResponse)
def revoke_api_key(
    workspace_id: str,
    key_id: str,
    ctx: AuthContext = Depends(require_auth_context),
) -> ApiKeyResponse:
    user_id = _require_actor_user_id(ctx)
    _workspace_with_access(workspace_id=workspace_id, ctx=ctx, minimum_role="admin")
    try:
        key = team_store.revoke_api_key(workspace_id=workspace_id, key_id=key_id, actor_user_id=user_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return ApiKeyResponse(**key.__dict__)


@router.get("/orgs/{org_id}/audit", response_model=list[AuditEventResponse])
def list_audit_events(
    org_id: str,
    workspace_id: str | None = None,
    ctx: AuthContext = Depends(require_auth_context),
) -> list[AuditEventResponse]:
    _require_org_role(org_id=org_id, ctx=ctx, minimum_role="viewer")
    events = team_store.list_audit_events(org_id=org_id, workspace_id=workspace_id)
    return [AuditEventResponse(**event.__dict__) for event in events]


@router.get("/workspaces/{workspace_id}/analytics", response_model=WorkspaceAnalyticsResponse)
def workspace_analytics(
    workspace_id: str,
    window_hours: int = 24,
    ctx: AuthContext = Depends(require_auth_context),
) -> WorkspaceAnalyticsResponse:
    _workspace_with_access(workspace_id=workspace_id, ctx=ctx, minimum_role="analyst")
    if window_hours < 1 or window_hours > 168:
        raise HTTPException(status_code=400, detail="window_hours must be between 1 and 168")
    out = team_store.workspace_analytics(workspace_id=workspace_id, window_hours=window_hours)
    return WorkspaceAnalyticsResponse(**out)


@router.get("/orgs/{org_id}/analytics/team-activity", response_model=list[TeamActivityResponse])
def org_team_activity(
    org_id: str,
    window_hours: int = 24,
    limit: int = 100,
    ctx: AuthContext = Depends(require_auth_context),
) -> list[TeamActivityResponse]:
    _require_org_role(org_id=org_id, ctx=ctx, minimum_role="analyst")
    if window_hours < 1 or window_hours > 168:
        raise HTTPException(status_code=400, detail="window_hours must be between 1 and 168")
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")
    rows = team_store.org_team_activity(org_id=org_id, window_hours=window_hours, limit=limit)
    return [TeamActivityResponse(**row.__dict__) for row in rows]