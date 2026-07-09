import json
import os
from threading import Lock
from typing import Literal
from urllib.request import Request, urlopen
from uuid import uuid4

from gateway.core.config import GatewaySettings
from gateway.core.egress import assert_url_allowed

RiskLevel = Literal["green", "yellow", "red"]
ActionType = Literal["pass", "clamp", "retry", "fallback-model", "human-review"]


_BUNDLE_LOCK = Lock()
_BUNDLE_CACHE: dict[str, object] = {
    "path": None,
    "mtime": None,
    "data": None,
}
_DECISION_LOG_LOCK = Lock()


def _rotate_decision_log(path: str, max_bytes: int, backup_count: int) -> None:
    if max_bytes <= 0:
        return
    if not os.path.exists(path):
        return
    try:
        current_size = os.path.getsize(path)
    except OSError:
        return
    if current_size < max_bytes:
        return

    if backup_count > 0:
        for i in range(backup_count - 1, 0, -1):
            src = f"{path}.{i}"
            dst = f"{path}.{i + 1}"
            if os.path.exists(src):
                try:
                    os.replace(src, dst)
                except OSError:
                    pass
        try:
            os.replace(path, f"{path}.1")
        except OSError:
            return
    else:
        try:
            os.remove(path)
        except OSError:
            return


def classify_risk(drift_score: float) -> RiskLevel:
    if drift_score < 0.20:
        return "green"
    if drift_score < 0.45:
        return "yellow"
    return "red"


def actions_for_risk(risk: RiskLevel) -> list[ActionType]:
    if risk == "green":
        return ["pass"]
    if risk == "yellow":
        return ["clamp", "retry"]
    return ["fallback-model", "human-review"]


def enforce_circuit_breaker(actions: list[ActionType], breaker_open: bool) -> list[ActionType]:
    if not breaker_open:
        return actions

    escalated: list[ActionType] = list(actions)
    if "fallback-model" not in escalated:
        escalated.append("fallback-model")
    if "human-review" not in escalated:
        escalated.append("human-review")
    return escalated


def _load_policy_bundle(path: str) -> dict[str, object] | None:
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None

    with _BUNDLE_LOCK:
        if _BUNDLE_CACHE["path"] == path and _BUNDLE_CACHE["mtime"] == mtime:
            cached = _BUNDLE_CACHE["data"]
            if isinstance(cached, dict):
                return cached
            return None

        try:
            with open(path, "r", encoding="utf-8") as handle:
                parsed = json.load(handle)
        except (OSError, json.JSONDecodeError):
            parsed = None

        _BUNDLE_CACHE["path"] = path
        _BUNDLE_CACHE["mtime"] = mtime
        _BUNDLE_CACHE["data"] = parsed
        if isinstance(parsed, dict):
            return parsed
        return None


def _actions_from_bundle(path: str | None, risk: RiskLevel) -> list[ActionType] | None:
    if not path:
        return None
    bundle = _load_policy_bundle(path)
    if bundle is None:
        return None

    actions_block = bundle.get("actions")
    if not isinstance(actions_block, dict):
        return None
    risk_actions = actions_block.get(risk)
    if not isinstance(risk_actions, list):
        return None

    allowed: set[str] = {"pass", "clamp", "retry", "fallback-model", "human-review"}
    out: list[ActionType] = []
    for action in risk_actions:
        if isinstance(action, str) and action in allowed:
            out.append(action)
    return out or None


def _actions_from_opa_endpoint(
    *,
    opa_url: str | None,
    drift_score: float,
    risk: RiskLevel,
    breaker_open: bool,
    settings: GatewaySettings,
) -> list[ActionType] | None:
    if not opa_url:
        return None

    try:
        assert_url_allowed(opa_url, settings)
    except Exception:
        return None
    payload = {
        "input": {
            "drift_score": drift_score,
            "risk": risk,
            "breaker_open": breaker_open,
        }
    }

    req = Request(
        opa_url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(req, timeout=2.5) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None

    result = body.get("result") if isinstance(body, dict) else None
    if isinstance(result, dict):
        raw_actions = result.get("actions")
    else:
        raw_actions = result

    if not isinstance(raw_actions, list):
        return None

    allowed: set[str] = {"pass", "clamp", "retry", "fallback-model", "human-review"}
    out: list[ActionType] = []
    for action in raw_actions:
        if isinstance(action, str) and action in allowed:
            out.append(action)
    return out or None


def _default_decision(settings: GatewaySettings, risk: RiskLevel) -> tuple[RiskLevel, list[ActionType], str]:
    if settings.policy_default_decision == "allow":
        return risk, actions_for_risk(risk), "default_allow"
    return "red", ["fallback-model", "human-review"], "default_deny"


def _log_policy_decision(
    *,
    settings: GatewaySettings,
    decision_source: str,
    drift_score: float,
    risk: RiskLevel,
    actions: list[ActionType],
    breaker_open: bool,
) -> None:
    path = settings.policy_decision_log_path
    if not path:
        return

    record = {
        "decision_id": f"dec_{uuid4().hex}",
        "source": decision_source,
        "drift_score": drift_score,
        "risk": risk,
        "actions": actions,
        "breaker_open": breaker_open,
    }
    line = json.dumps(record, separators=(",", ":")) + "\n"
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with _DECISION_LOG_LOCK:
        _rotate_decision_log(
            path,
            settings.policy_decision_log_max_bytes,
            settings.policy_decision_log_backup_count,
        )
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(line)


def decide_actions(
    *,
    drift_score: float,
    breaker_open: bool,
    settings: GatewaySettings,
) -> tuple[RiskLevel, list[ActionType]]:
    risk = classify_risk(drift_score)

    if settings.policy_mode == "opa":
        actions = _actions_from_bundle(settings.policy_bundle_path, risk)
        source = "bundle"
        if actions is None:
            actions = _actions_from_opa_endpoint(
                opa_url=settings.opa_url,
                drift_score=drift_score,
                risk=risk,
                breaker_open=breaker_open,
                settings=settings,
            )
            source = "opa_api" if actions is not None else "default"
        if actions is None:
            risk, actions, source = _default_decision(settings, risk)
        actions = enforce_circuit_breaker(actions, breaker_open)
        _log_policy_decision(
            settings=settings,
            decision_source=source,
            drift_score=drift_score,
            risk=risk,
            actions=actions,
            breaker_open=breaker_open,
        )
        return risk, actions

    if settings.policy_mode == "builtin":
        actions = actions_for_risk(risk)
        actions = enforce_circuit_breaker(actions, breaker_open)
        _log_policy_decision(
            settings=settings,
            decision_source="builtin",
            drift_score=drift_score,
            risk=risk,
            actions=actions,
            breaker_open=breaker_open,
        )
        return risk, actions

    actions = actions_for_risk(risk)
    actions = enforce_circuit_breaker(actions, breaker_open)
    _log_policy_decision(
        settings=settings,
        decision_source="fallback",
        drift_score=drift_score,
        risk=risk,
        actions=actions,
        breaker_open=breaker_open,
    )
    return risk, actions
