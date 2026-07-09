from __future__ import annotations

import json
import pathlib
import subprocess


def test_governance_script_generates_summary_in_dry_run(tmp_path):
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "release_governance_checks.sh"

    env = {
        "PATH": str(pathlib.Path("/usr/bin")) + ":" + str(pathlib.Path("/bin")) + ":" + str(pathlib.Path("/usr/local/bin")),
        "DRY_RUN": "1",
        "REPORT_DIR": str(tmp_path / "report"),
    }

    completed = subprocess.run(
        [str(script)],
        cwd=str(repo_root),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + "\n" + completed.stderr

    summary_file = tmp_path / "report" / "summary.json"
    assert summary_file.exists()
    payload = json.loads(summary_file.read_text(encoding="utf-8"))
    assert payload["checks"]["tests"] == "passed"
    assert payload["checks"]["helm_template"] == "passed"
    assert payload["checks"]["airgap_bundle"] == "passed"
    assert payload["checks"]["airgap_verify"] == "passed"
    assert payload["checks"]["plan_guard"] == "passed"
    assert payload["checks"]["rollout_waves"] == "passed"
