import json

from gateway.core.config import load_settings
from gateway.core.policy import decide_actions


def test_opa_mode_uses_local_policy_bundle(tmp_path, monkeypatch):
    bundle = tmp_path / "policy-bundle.json"
    bundle.write_text(
        json.dumps(
            {
                "actions": {
                    "green": ["pass"],
                    "yellow": ["retry"],
                    "red": ["human-review", "fallback-model"],
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("POLICY_MODE", "opa")
    monkeypatch.setenv("POLICY_BUNDLE_PATH", str(bundle))

    settings = load_settings()
    risk, actions = decide_actions(drift_score=0.30, breaker_open=False, settings=settings)

    assert risk == "yellow"
    assert actions == ["retry"]


def test_opa_mode_falls_back_when_bundle_missing(monkeypatch):
    monkeypatch.setenv("POLICY_MODE", "opa")
    monkeypatch.setenv("POLICY_BUNDLE_PATH", "/tmp/does-not-exist.json")

    settings = load_settings()
    risk, actions = decide_actions(drift_score=0.30, breaker_open=False, settings=settings)

    assert risk == "red"
    assert actions == ["fallback-model", "human-review"]


def test_opa_mode_default_allow_when_configured(monkeypatch):
    monkeypatch.setenv("POLICY_MODE", "opa")
    monkeypatch.setenv("POLICY_BUNDLE_PATH", "/tmp/does-not-exist.json")
    monkeypatch.setenv("POLICY_DEFAULT_DECISION", "allow")

    settings = load_settings()
    risk, actions = decide_actions(drift_score=0.30, breaker_open=False, settings=settings)

    assert risk == "yellow"
    assert actions == ["clamp", "retry"]


def test_policy_decision_logging_writes_jsonl(tmp_path, monkeypatch):
    log_file = tmp_path / "decisions" / "policy.jsonl"
    monkeypatch.setenv("POLICY_MODE", "builtin")
    monkeypatch.setenv("POLICY_DECISION_LOG_PATH", str(log_file))

    settings = load_settings()
    risk, actions = decide_actions(drift_score=0.10, breaker_open=False, settings=settings)

    assert risk == "green"
    assert actions == ["pass"]
    assert log_file.exists()

    line = log_file.read_text(encoding="utf-8").strip()
    parsed = json.loads(line)
    assert parsed["source"] == "builtin"
    assert parsed["risk"] == "green"


def test_policy_decision_log_rotates_when_size_limit_reached(tmp_path, monkeypatch):
    log_file = tmp_path / "decisions" / "policy.jsonl"
    monkeypatch.setenv("POLICY_MODE", "builtin")
    monkeypatch.setenv("POLICY_DECISION_LOG_PATH", str(log_file))
    monkeypatch.setenv("POLICY_DECISION_LOG_MAX_BYTES", "1")
    monkeypatch.setenv("POLICY_DECISION_LOG_BACKUP_COUNT", "2")

    settings = load_settings()
    decide_actions(drift_score=0.10, breaker_open=False, settings=settings)
    decide_actions(drift_score=0.30, breaker_open=False, settings=settings)

    assert log_file.exists()
    rotated = log_file.with_name(log_file.name + ".1")
    assert rotated.exists()


def test_policy_decision_log_rotation_without_backups_removes_old_file(tmp_path, monkeypatch):
    log_file = tmp_path / "decisions" / "policy.jsonl"
    monkeypatch.setenv("POLICY_MODE", "builtin")
    monkeypatch.setenv("POLICY_DECISION_LOG_PATH", str(log_file))
    monkeypatch.setenv("POLICY_DECISION_LOG_MAX_BYTES", "1")
    monkeypatch.setenv("POLICY_DECISION_LOG_BACKUP_COUNT", "0")

    settings = load_settings()
    decide_actions(drift_score=0.10, breaker_open=False, settings=settings)
    decide_actions(drift_score=0.40, breaker_open=False, settings=settings)

    assert log_file.exists()
    assert not log_file.with_name(log_file.name + ".1").exists()


def test_opa_blocked_egress_falls_back_to_default_deny(monkeypatch):
    monkeypatch.setenv("POLICY_MODE", "opa")
    monkeypatch.setenv("OPA_URL", "https://opa.example.com/v1/data/phaselock/decision")
    monkeypatch.setenv("AIRGAPPED_MODE", "true")
    monkeypatch.setenv("ALLOW_OUTBOUND_NETWORK", "false")
    monkeypatch.delenv("AIRGAP_ALLOWED_HOSTS", raising=False)

    settings = load_settings()
    risk, actions = decide_actions(drift_score=0.1, breaker_open=False, settings=settings)

    assert risk == "red"
    assert actions == ["fallback-model", "human-review"]
