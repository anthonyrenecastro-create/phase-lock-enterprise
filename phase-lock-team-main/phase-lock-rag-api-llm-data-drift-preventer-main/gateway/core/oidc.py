from __future__ import annotations

import json
from secrets import token_urlsafe
from threading import Lock
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import HTTPException

from gateway.core.config import GatewaySettings
from gateway.core.egress import assert_url_allowed

_DISCOVERY_LOCK = Lock()
_DISCOVERY_CACHE: dict[str, dict[str, str]] = {}


def build_nonce() -> str:
    return token_urlsafe(24)


def _discovery_url(issuer: str) -> str:
    issuer = issuer.rstrip("/")
    return f"{issuer}/.well-known/openid-configuration"


def _assert_outbound_allowed(url: str, settings: GatewaySettings) -> None:
    assert_url_allowed(url, settings)


def _fetch_discovery(issuer: str, settings: GatewaySettings) -> dict[str, str]:
    with _DISCOVERY_LOCK:
        cached = _DISCOVERY_CACHE.get(issuer)
    if cached is not None:
        return cached

    url = _discovery_url(issuer)
    _assert_outbound_allowed(url, settings)
    req = Request(url, method="GET")
    try:
        with urlopen(req, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=502, detail="Unable to fetch OIDC discovery document")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="OIDC discovery document is invalid")

    out: dict[str, str] = {}
    auth_endpoint = payload.get("authorization_endpoint")
    token_endpoint = payload.get("token_endpoint")
    jwks_uri = payload.get("jwks_uri")
    if isinstance(auth_endpoint, str):
        out["authorization_endpoint"] = auth_endpoint
    if isinstance(token_endpoint, str):
        out["token_endpoint"] = token_endpoint
    if isinstance(jwks_uri, str):
        out["jwks_uri"] = jwks_uri

    with _DISCOVERY_LOCK:
        _DISCOVERY_CACHE[issuer] = out
    return out


def resolve_oidc_endpoints(settings: GatewaySettings) -> tuple[str, str, str | None]:
    authorization_url = settings.oidc_authorization_url
    token_url = settings.oidc_token_url
    jwks_url = settings.oidc_jwks_url

    if authorization_url and token_url:
        _assert_outbound_allowed(authorization_url, settings)
        _assert_outbound_allowed(token_url, settings)
        return authorization_url, token_url, jwks_url

    if settings.oidc_issuer is None:
        raise HTTPException(status_code=500, detail="OIDC issuer or explicit endpoint URLs are required")

    discovery = _fetch_discovery(settings.oidc_issuer, settings)
    authorization_url = authorization_url or discovery.get("authorization_endpoint")
    token_url = token_url or discovery.get("token_endpoint")
    jwks_url = jwks_url or discovery.get("jwks_uri")

    if not authorization_url or not token_url:
        raise HTTPException(status_code=500, detail="OIDC endpoints are missing from configuration/discovery")

    return authorization_url, token_url, jwks_url


def build_authorize_url(
    *,
    authorization_url: str,
    client_id: str,
    redirect_uri: str,
    scopes: tuple[str, ...],
    state: str,
    nonce: str,
) -> str:
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(scopes),
        "state": state,
        "nonce": nonce,
    }
    return f"{authorization_url}?{urlencode(params)}"


def exchange_authorization_code(
    *,
    token_url: str,
    client_id: str,
    client_secret: str | None,
    code: str,
    redirect_uri: str,
    settings: GatewaySettings,
) -> dict[str, object]:
    _assert_outbound_allowed(token_url, settings)
    body = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
    }
    if client_secret:
        body["client_secret"] = client_secret

    data = urlencode(body).encode("utf-8")
    req = Request(token_url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urlopen(req, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=502, detail="OIDC token exchange failed")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="OIDC token response is invalid")
    return payload
