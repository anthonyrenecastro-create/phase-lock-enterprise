from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import PlainTextResponse

from gateway.core.auth import require_api_key
from gateway.core.schemas import FeedbackRequest, StabilizeRequest, StabilizeResponse
from gateway.core.service import StabilizationService
from gateway.core.team import team_store
from gateway.core.telemetry import telemetry_store

router = APIRouter(prefix="/v1", tags=["stabilization"])
service = StabilizationService()


def _resolve_workspace_id(request_workspace_id: str | None, header_workspace_id: str | None) -> str | None:
    if request_workspace_id and header_workspace_id and request_workspace_id != header_workspace_id:
        raise HTTPException(status_code=400, detail="workspace_id mismatch between body and header")
    return request_workspace_id or header_workspace_id


def _actor_user_id(x_user_id: str | None) -> str:
    if x_user_id is None or not x_user_id.strip():
        return "system"
    return x_user_id.strip()


@router.post("/stabilize", response_model=StabilizeResponse)
def stabilize(
    req: StabilizeRequest,
    _: None = Depends(require_api_key),
    x_workspace_id: str | None = Header(default=None),
    x_workspace_key_id: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> StabilizeResponse:
    started_at = telemetry_store.start_timer()
    workspace_id = _resolve_workspace_id(req.workspace_id, x_workspace_id)

    workspace = None
    if workspace_id is not None:
        workspace = team_store.get_workspace(workspace_id)
        if workspace is None:
            telemetry_store.observe_stabilize(started_at=started_at, success=False, prevented_incident=False)
            raise HTTPException(status_code=404, detail="Workspace not found")

    if x_workspace_key_id is not None:
        if workspace is None:
            telemetry_store.observe_stabilize(started_at=started_at, success=False, prevented_incident=False)
            raise HTTPException(status_code=400, detail="X-Workspace-Key-Id requires workspace attribution")

        key = team_store.get_api_key(x_workspace_key_id)
        if key is None or key.workspace_id != workspace.workspace_id:
            telemetry_store.observe_stabilize(started_at=started_at, success=False, prevented_incident=False)
            raise HTTPException(status_code=403, detail="Invalid workspace API key id")
        if key.revoked:
            telemetry_store.observe_stabilize(started_at=started_at, success=False, prevented_incident=False)
            raise HTTPException(status_code=403, detail="Workspace API key is revoked")

    if req.text is None and req.embedding is None:
        telemetry_store.observe_stabilize(
            started_at=started_at,
            success=False,
            prevented_incident=False,
            org_id=None if workspace is None else workspace.org_id,
            workspace_id=None if workspace is None else workspace.workspace_id,
        )
        raise HTTPException(status_code=400, detail="Provide at least one of: text, embedding")

    try:
        out = service.stabilize(req)
        prevented = "fallback-model" in out.actions or "human-review" in out.actions
        telemetry_store.observe_stabilize(
            started_at=started_at,
            success=True,
            prevented_incident=prevented,
            org_id=None if workspace is None else workspace.org_id,
            workspace_id=None if workspace is None else workspace.workspace_id,
        )
        if workspace is not None:
            team_store.record_runtime_event(
                workspace_id=workspace.workspace_id,
                actor_user_id=_actor_user_id(x_user_id),
                action="stabilize.request",
                request_id=req.request_id,
                drift_score=out.drift_score,
                prevented_incident=prevented,
                api_key_id=x_workspace_key_id,
            )
        return out
    except ValueError as e:
        telemetry_store.observe_stabilize(
            started_at=started_at,
            success=False,
            prevented_incident=False,
            org_id=None if workspace is None else workspace.org_id,
            workspace_id=None if workspace is None else workspace.workspace_id,
        )
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        telemetry_store.observe_stabilize(
            started_at=started_at,
            success=False,
            prevented_incident=False,
            org_id=None if workspace is None else workspace.org_id,
            workspace_id=None if workspace is None else workspace.workspace_id,
        )
        raise HTTPException(status_code=500, detail="Internal stabilization error")


@router.post("/feedback")
def feedback(
    req: FeedbackRequest,
    _: None = Depends(require_api_key),
    x_workspace_id: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> dict[str, str]:
    workspace_id = _resolve_workspace_id(req.workspace_id, x_workspace_id)
    workspace = None
    if workspace_id is not None:
        workspace = team_store.get_workspace(workspace_id)
        if workspace is None:
            raise HTTPException(status_code=404, detail="Workspace not found")

    telemetry_store.observe_feedback(
        corrected=req.corrected,
        risk_level=req.observed_risk_level,
        org_id=None if workspace is None else workspace.org_id,
        workspace_id=None if workspace is None else workspace.workspace_id,
    )
    if workspace is not None:
        team_store.record_runtime_event(
            workspace_id=workspace.workspace_id,
            actor_user_id=_actor_user_id(x_user_id),
            action="feedback.received",
            request_id=req.request_id,
            corrected=req.corrected,
            risk_level=req.observed_risk_level,
        )
    return {"status": "accepted", "request_id": req.request_id}


@router.get("/telemetry", response_model=None)
def telemetry(
    format: str = "json",
    workspace_id: str | None = None,
    _: None = Depends(require_api_key),
) -> object:
    org_id = None
    if workspace_id is not None:
        workspace = team_store.get_workspace(workspace_id)
        if workspace is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
        org_id = workspace.org_id

    if format == "prometheus":
        return PlainTextResponse(
            telemetry_store.as_prometheus(org_id=org_id, workspace_id=workspace_id),
            media_type="text/plain; version=0.0.4",
        )

    return {
        "status": "ok",
        "metrics": telemetry_store.as_json(org_id=org_id, workspace_id=workspace_id),
    }
