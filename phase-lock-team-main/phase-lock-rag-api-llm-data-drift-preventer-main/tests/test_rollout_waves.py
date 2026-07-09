from __future__ import annotations

import json
import pathlib
import subprocess
import sys


def test_rollout_waves_validator_accepts_valid_plan():
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "release" / "validate_rollout_waves.py"
    plan = repo_root / "docs" / "release-rollout-waves.json"

    completed = subprocess.run(
        [sys.executable, str(script), str(plan)],
        cwd=str(repo_root),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + "\n" + completed.stderr


def test_rollout_waves_validator_rejects_non_monotonic_plan(tmp_path):
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "release" / "validate_rollout_waves.py"

    broken_plan = {
        "waves": [
            {
                "name": "canary",
                "maxTrafficPercent": 10,
                "soakMinutes": 10,
                "promotionCriteria": {
                    "errorRateThreshold": 0.01,
                    "maxP95LatencyMs": 300,
                    "minimumRequests": 100,
                },
            },
            {
                "name": "regional",
                "maxTrafficPercent": 8,
                "soakMinutes": 10,
                "promotionCriteria": {
                    "errorRateThreshold": 0.01,
                    "maxP95LatencyMs": 300,
                    "minimumRequests": 100,
                },
            },
            {
                "name": "global",
                "maxTrafficPercent": 100,
                "soakMinutes": 10,
                "promotionCriteria": {
                    "errorRateThreshold": 0.01,
                    "maxP95LatencyMs": 300,
                    "minimumRequests": 100,
                },
            },
        ]
    }

    plan_path = tmp_path / "broken.json"
    plan_path.write_text(json.dumps(broken_plan), encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(script), str(plan_path)],
        cwd=str(repo_root),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "strictly increasing" in (completed.stdout + completed.stderr)
