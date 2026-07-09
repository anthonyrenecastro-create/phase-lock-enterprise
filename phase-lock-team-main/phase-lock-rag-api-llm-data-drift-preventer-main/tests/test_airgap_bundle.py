from __future__ import annotations

import pathlib
import subprocess


def test_airgap_bundle_script_exists_and_is_executable():
    root = pathlib.Path(__file__).resolve().parents[1]
    build_script = root / "scripts" / "airgap" / "build_offline_bundle.sh"
    verify_script = root / "scripts" / "airgap" / "verify_offline_bundle.sh"
    assert build_script.exists()
    assert verify_script.exists()
    assert build_script.stat().st_mode & 0o111
    assert verify_script.stat().st_mode & 0o111


def test_airgap_bundle_build_and_verify_pipeline(tmp_path):
    root = pathlib.Path(__file__).resolve().parents[1]
    build_script = root / "scripts" / "airgap" / "build_offline_bundle.sh"
    verify_script = root / "scripts" / "airgap" / "verify_offline_bundle.sh"

    out_dir = tmp_path / "bundle"
    env = {
        "OUT_DIR": str(out_dir),
        "IMAGE": "ghcr.io/example/phase-lock:test",
        "PATH": "/usr/local/bin:/usr/bin:/bin",
    }

    build = subprocess.run(
        [str(build_script)],
        cwd=str(root),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert build.returncode == 0, build.stdout + "\n" + build.stderr

    verify = subprocess.run(
        [str(verify_script), str(out_dir)],
        cwd=str(root),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert verify.returncode == 0, verify.stdout + "\n" + verify.stderr
