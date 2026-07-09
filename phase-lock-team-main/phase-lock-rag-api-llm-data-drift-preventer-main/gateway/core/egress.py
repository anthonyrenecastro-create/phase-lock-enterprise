from __future__ import annotations

from urllib.parse import urlparse

from fastapi import HTTPException

from gateway.core.config import GatewaySettings


def is_local_host(host: str | None) -> bool:
    if host is None:
        return False
    return host in {"localhost", "127.0.0.1", "::1"}


def is_url_allowed(url: str, settings: GatewaySettings) -> bool:
    if not settings.airgapped_mode or settings.allow_outbound_network:
        return True

    host = urlparse(url).hostname
    if is_local_host(host):
        return True
    return host in set(settings.airgap_allowed_hosts)


def assert_url_allowed(url: str, settings: GatewaySettings) -> None:
    if is_url_allowed(url, settings):
        return
    raise HTTPException(status_code=503, detail="Outbound network disabled in air-gapped mode")
