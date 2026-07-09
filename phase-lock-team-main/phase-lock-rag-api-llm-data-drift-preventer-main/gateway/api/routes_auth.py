from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse

from gateway.core.auth import (
    AuthContext,
    create_oidc_login_state,
    create_oidc_session_token,
    log_auth_event,
    parse_oidc_login_state,
    parse_oidc_session_token,
    revoke_oidc_session_token,
    rotate_oidc_session_token,
    require_auth_context,
    verify_oidc_token,
)
from gateway.core.config import load_settings
from gateway.core.oidc import build_authorize_url, build_nonce, exchange_authorization_code, resolve_oidc_endpoints

router = APIRouter(prefix="/v1/auth", tags=["auth"])


def _ensure_oidc_enabled() -> None:
    settings = load_settings()
    if settings.auth_mode != "oidc":
        raise HTTPException(status_code=400, detail="OIDC flow is available only when AUTH_MODE=oidc")


def _callback_url(request: Request) -> str:
    settings = load_settings()
    if settings.oidc_redirect_uri:
        return settings.oidc_redirect_uri
    return str(request.url_for("oidc_callback"))


def _safe_return_to(value: str) -> str:
    if not value.startswith("/"):
        return "/"
    if value.startswith("//"):
        return "/"
    return value


@router.get("/oidc/login")
def oidc_login(
    request: Request,
    return_to: str = Query(default="/", description="Path to redirect after successful callback"),
) -> RedirectResponse:
    _ensure_oidc_enabled()
    settings = load_settings()

    if not settings.oidc_client_id:
        raise HTTPException(status_code=500, detail="OIDC_CLIENT_ID is required for OIDC login")

    authorization_url, _, _ = resolve_oidc_endpoints(settings)
    redirect_uri = _callback_url(request)

    nonce = build_nonce()
    state = create_oidc_login_state(nonce=nonce, return_to=_safe_return_to(return_to))

    location = build_authorize_url(
        authorization_url=authorization_url,
        client_id=settings.oidc_client_id,
        redirect_uri=redirect_uri,
        scopes=settings.oidc_scopes,
        state=state,
        nonce=nonce,
    )
    return RedirectResponse(url=location, status_code=302)


@router.get("/oidc/callback", name="oidc_callback")
def oidc_callback(
    request: Request,
    code: str = Query(..., min_length=1),
    state: str = Query(..., min_length=1),
) -> RedirectResponse:
    _ensure_oidc_enabled()
    settings = load_settings()

    if not settings.oidc_client_id:
        raise HTTPException(status_code=500, detail="OIDC_CLIENT_ID is required for OIDC callback")

    state_data = parse_oidc_login_state(state)
    _, token_url, discovered_jwks_url = resolve_oidc_endpoints(settings)
    redirect_uri = _callback_url(request)

    token_payload = exchange_authorization_code(
        token_url=token_url,
        client_id=settings.oidc_client_id,
        client_secret=settings.oidc_client_secret,
        code=code,
        redirect_uri=redirect_uri,
        settings=settings,
    )

    id_token = token_payload.get("id_token")
    if not isinstance(id_token, str) or not id_token.strip():
        raise HTTPException(status_code=502, detail="OIDC token response missing id_token")

    ctx = verify_oidc_token(
        id_token,
        expected_nonce=state_data["nonce"],
        jwks_url_override=discovered_jwks_url,
    )
    session_token = create_oidc_session_token(ctx)

    return_to = _safe_return_to(state_data["return_to"])
    response = RedirectResponse(url=return_to, status_code=302)
    existing = request.cookies.get(settings.oidc_cookie_name)
    if existing:
        revoke_oidc_session_token(existing)
    response.set_cookie(
        key=settings.oidc_cookie_name,
        value=session_token,
        max_age=settings.oidc_session_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.oidc_cookie_secure,
        path="/",
    )
    log_auth_event(
        event="oidc.login",
        user_id=ctx.user_id,
        details={"groups": list(ctx.groups)},
    )
    return response


@router.get("/session")
def session(ctx: AuthContext = Depends(require_auth_context)) -> dict[str, object]:
    return {
        "authenticated": True,
        "user_id": ctx.user_id,
        "groups": list(ctx.groups),
        "auth_type": ctx.auth_type,
    }


@router.post("/logout")
def logout(request: Request) -> JSONResponse:
    settings = load_settings()
    existing = request.cookies.get(settings.oidc_cookie_name)
    user_id: str | None = None
    if existing:
        try:
            user_id = parse_oidc_session_token(existing).user_id
        except HTTPException:
            user_id = None
        revoke_oidc_session_token(existing)
    response = JSONResponse({"status": "ok", "message": "logged out"})
    response.delete_cookie(key=settings.oidc_cookie_name, path="/")
    log_auth_event(event="oidc.logout", user_id=user_id, details={"had_session": bool(existing)})
    return response


@router.post("/session/refresh")
def refresh_session(request: Request) -> JSONResponse:
    _ensure_oidc_enabled()
    settings = load_settings()
    existing = request.cookies.get(settings.oidc_cookie_name)
    if not existing:
        raise HTTPException(status_code=401, detail="Missing OIDC session cookie")

    ctx, refreshed = rotate_oidc_session_token(existing)
    revoke_oidc_session_token(existing)
    response = JSONResponse({"status": "ok", "user_id": ctx.user_id})
    response.set_cookie(
        key=settings.oidc_cookie_name,
        value=refreshed,
        max_age=settings.oidc_session_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.oidc_cookie_secure,
        path="/",
    )
    log_auth_event(event="oidc.refresh", user_id=ctx.user_id)
    return response
