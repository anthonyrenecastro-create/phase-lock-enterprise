from fastapi import FastAPI

from gateway.api.routes_auth import router as auth_router
from gateway.api.routes_team import router as team_router
from gateway.api.routes_stabilize import router as stabilize_router
from gateway.core.config import load_settings
from gateway.core.state_backend import get_state_backend

app = FastAPI(title="Phase-Lock Drift Prevention Gateway", version="0.1.0")
app.include_router(stabilize_router)
app.include_router(team_router)
app.include_router(auth_router)
settings = load_settings()
state_backend = get_state_backend(settings)


@app.get("/v1/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "deterministic_mode": settings.deterministic_mode,
        "engine_seed": settings.default_seed,
        "auth_mode": settings.auth_mode,
        "policy_mode": settings.policy_mode,
        "ha_mode_enabled": settings.ha_mode_enabled,
        "airgapped_mode": settings.airgapped_mode,
        "state_backend": state_backend.health(),
    }
