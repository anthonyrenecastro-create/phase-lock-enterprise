import os
from dataclasses import dataclass


@dataclass(frozen=True)
class GatewaySettings:
    deterministic_mode: bool
    default_seed: int
    drift_spike_threshold: float
    breaker_trip_count: int
    max_metric_window: int
    max_compute_steps: int
    auth_mode: str
    api_key: str | None
    oidc_issuer: str | None
    oidc_audience: str | None
    oidc_jwks_url: str | None
    oidc_authorization_url: str | None
    oidc_token_url: str | None
    oidc_client_id: str | None
    oidc_client_secret: str | None
    oidc_redirect_uri: str | None
    oidc_scopes: tuple[str, ...]
    oidc_session_secret: str | None
    oidc_session_ttl_seconds: int
    oidc_session_max_lifetime_seconds: int
    oidc_cookie_name: str
    oidc_cookie_secure: bool
    auth_audit_log_path: str | None
    auth_audit_log_max_bytes: int
    auth_audit_log_backup_count: int
    oidc_required_groups: tuple[str, ...]
    oidc_group_role_map: tuple[tuple[str, str], ...]
    policy_mode: str
    opa_url: str | None
    policy_bundle_path: str | None
    policy_default_decision: str
    policy_decision_log_path: str | None
    policy_decision_log_max_bytes: int
    policy_decision_log_backup_count: int
    state_backend: str
    state_redis_urls: tuple[str, ...]
    tenant_runtime_cache_enabled: bool
    airgap_allowed_hosts: tuple[str, ...]
    airgapped_mode: bool
    allow_outbound_network: bool
    ha_mode_enabled: bool


def _env_bool(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _env_csv(name: str) -> tuple[str, ...]:
    raw = os.getenv(name, "")
    if not raw:
        return tuple()
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _env_scopes(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    values = _env_csv(name)
    return values if values else default


def _env_group_role_map(name: str) -> tuple[tuple[str, str], ...]:
    allowed_roles = {"viewer", "analyst", "admin", "owner"}
    raw = os.getenv(name, "")
    if not raw:
        return tuple()

    out: list[tuple[str, str]] = []
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if ":" not in pair:
            continue
        group, role = pair.split(":", 1)
        group = group.strip()
        role = role.strip().lower()
        if not group or role not in allowed_roles:
            continue
        out.append((group, role))
    return tuple(out)


def _normalize_mode(value: str, default: str, allowed: set[str]) -> str:
    normalized = value.strip().lower()
    if normalized in allowed:
        return normalized
    return default


def _normalize_backend(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"memory", "redis"}:
        return normalized
    return "memory"


def _empty_as_none(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def load_settings() -> GatewaySettings:
    api_key = _empty_as_none(os.getenv("GATEWAY_API_KEY"))
    auth_mode = _normalize_mode(
        os.getenv("AUTH_MODE", "api_key"),
        default="api_key",
        allowed={"api_key", "oidc"},
    )
    policy_mode = _normalize_mode(
        os.getenv("POLICY_MODE", "builtin"),
        default="builtin",
        allowed={"builtin", "opa"},
    )
    policy_default_decision = _normalize_mode(
        os.getenv("POLICY_DEFAULT_DECISION", "deny"),
        default="deny",
        allowed={"deny", "allow"},
    )
    state_backend = _normalize_backend(os.getenv("STATE_BACKEND", "memory"))

    return GatewaySettings(
        deterministic_mode=_env_bool("DETERMINISTIC_MODE", "true"),
        default_seed=int(os.getenv("DRIFT_ENGINE_SEED", "7")),
        drift_spike_threshold=float(os.getenv("DRIFT_SPIKE_THRESHOLD", "0.80")),
        breaker_trip_count=int(os.getenv("DRIFT_BREAKER_TRIP_COUNT", "3")),
        max_metric_window=int(os.getenv("MAX_METRIC_WINDOW", "4096")),
        max_compute_steps=int(os.getenv("MAX_COMPUTE_STEPS", "50000")),
        auth_mode=auth_mode,
        api_key=api_key,
        oidc_issuer=_empty_as_none(os.getenv("OIDC_ISSUER")),
        oidc_audience=_empty_as_none(os.getenv("OIDC_AUDIENCE")),
        oidc_jwks_url=_empty_as_none(os.getenv("OIDC_JWKS_URL")),
        oidc_authorization_url=_empty_as_none(os.getenv("OIDC_AUTHORIZATION_URL")),
        oidc_token_url=_empty_as_none(os.getenv("OIDC_TOKEN_URL")),
        oidc_client_id=_empty_as_none(os.getenv("OIDC_CLIENT_ID")),
        oidc_client_secret=_empty_as_none(os.getenv("OIDC_CLIENT_SECRET")),
        oidc_redirect_uri=_empty_as_none(os.getenv("OIDC_REDIRECT_URI")),
        oidc_scopes=_env_scopes("OIDC_SCOPES", ("openid", "profile", "email", "groups")),
        oidc_session_secret=_empty_as_none(os.getenv("OIDC_SESSION_SECRET")),
        oidc_session_ttl_seconds=max(60, int(os.getenv("OIDC_SESSION_TTL_SECONDS", "3600"))),
        oidc_session_max_lifetime_seconds=max(
            300,
            int(os.getenv("OIDC_SESSION_MAX_LIFETIME_SECONDS", "86400")),
        ),
        oidc_cookie_name=os.getenv("OIDC_COOKIE_NAME", "phase_lock_session").strip() or "phase_lock_session",
        oidc_cookie_secure=_env_bool("OIDC_COOKIE_SECURE", "true"),
        auth_audit_log_path=_empty_as_none(os.getenv("AUTH_AUDIT_LOG_PATH")),
        auth_audit_log_max_bytes=max(0, int(os.getenv("AUTH_AUDIT_LOG_MAX_BYTES", "10485760"))),
        auth_audit_log_backup_count=max(0, int(os.getenv("AUTH_AUDIT_LOG_BACKUP_COUNT", "5"))),
        oidc_required_groups=_env_csv("OIDC_REQUIRED_GROUPS"),
        oidc_group_role_map=_env_group_role_map("OIDC_GROUP_ROLE_MAP"),
        policy_mode=policy_mode,
        opa_url=_empty_as_none(os.getenv("OPA_URL")),
        policy_bundle_path=_empty_as_none(os.getenv("POLICY_BUNDLE_PATH")),
        policy_default_decision=policy_default_decision,
        policy_decision_log_path=_empty_as_none(os.getenv("POLICY_DECISION_LOG_PATH")),
        policy_decision_log_max_bytes=max(0, int(os.getenv("POLICY_DECISION_LOG_MAX_BYTES", "10485760"))),
        policy_decision_log_backup_count=max(0, int(os.getenv("POLICY_DECISION_LOG_BACKUP_COUNT", "5"))),
        state_backend=state_backend,
        state_redis_urls=_env_csv("STATE_REDIS_URLS"),
        tenant_runtime_cache_enabled=_env_bool("TENANT_RUNTIME_CACHE_ENABLED", "false"),
        airgap_allowed_hosts=_env_csv("AIRGAP_ALLOWED_HOSTS"),
        airgapped_mode=_env_bool("AIRGAPPED_MODE", "false"),
        allow_outbound_network=_env_bool("ALLOW_OUTBOUND_NETWORK", "true"),
        ha_mode_enabled=_env_bool("HA_MODE_ENABLED", "false"),
    )
