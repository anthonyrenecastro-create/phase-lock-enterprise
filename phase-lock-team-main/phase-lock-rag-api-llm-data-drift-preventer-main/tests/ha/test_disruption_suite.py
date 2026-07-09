from __future__ import annotations

import os
import pathlib
import subprocess

import pytest


def test_ha_disruption_suite_script_exists_and_is_executable():
    script = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "ha" / "run_disruption_suite.sh"
    assert script.exists()
    assert script.stat().st_mode & 0o111


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("RUN_HA_TESTS") != "1", reason="Set RUN_HA_TESTS=1 to run disruption suite")
def test_run_ha_disruption_suite():
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "ha" / "run_disruption_suite.sh"

    env = os.environ.copy()
    env.setdefault("NAMESPACE", "default")
    env.setdefault("GATEWAY_LABEL", "app=phase-lock-gateway")
    env.setdefault("GATEWAY_DEPLOYMENT", "phase-lock-gateway")

    completed = subprocess.run(
        [str(script)],
        cwd=str(repo_root),
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stdout + "\n" + completed.stderr
