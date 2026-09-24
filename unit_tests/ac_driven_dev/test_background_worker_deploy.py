"""Installed consumer smoke checks for ACD-1300b-1."""

import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture
def outside_package():
    # This repository redirects pytest's ordinary tmp_path below the checkout.
    # An explicit sibling directory prevents accidental imports from hiding a missing dependency.
    # Keep fixture repositories outside the app's watched workspace: automatic
    # Git discovery/fetch can otherwise race assertions or hold Windows directories open.
    temporary_root = Path.home() / "AppData/Local/Temp" if os.name == "nt" else None
    with tempfile.TemporaryDirectory(prefix="worker-deploy-", dir=temporary_root) as directory:
        path = Path(directory).resolve()
        assert not path.is_relative_to(ROOT.resolve())
        yield path


# covers: ACD-1300b-1
def test_deployed_cli_runs_without_package_checkout(outside_package, monkeypatch):
    tmp_path = outside_package
    import build_phases
    from build_phases_background_worker import background_worker_sources, build_background_worker

    # Freeze only declared package sources, since other implementation agents
    # may edit the live source while the installed CLI smoke is running.
    snapshot = tmp_path / "package-snapshot"
    for source in background_worker_sources(ROOT):
        destination = snapshot / source.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    monkeypatch.setattr(build_phases, "PACKAGE_ROOT", snapshot)
    install = tmp_path / "consumer" / ".leafcutter"
    count = build_background_worker(install, {}, False, True)
    assert count > 5
    repo = tmp_path / "consumer"
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    cli = install / "scripts/background_worker_cli.py"
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["PATH"] = str(Path(shutil.which("git")).parent)
    assert not repo.resolve().is_relative_to(ROOT.resolve())
    result = subprocess.run(
        [sys.executable, str(cli), "--repo", str(repo), "status"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["settings"]["enabled"] is False
    config = repo / "worker-config.json"
    config.write_text(
        json.dumps(
            {
                "implementation": {
                    "executor": "codex-cli",
                    "provider": "ollama",
                    "model": "qwen3.5:9b-q4_K_M",
                    "endpoint": "http://127.0.0.1:11434",
                },
                "reviewer": {"executor": "codex-sdk", "model": "configured-review-model"},
                "checks": [[sys.executable, "-c", "print('checked')"]],
            }
        ),
        encoding="utf-8",
    )
    for command in [
        ["configure", "--config", str(config)],
        ["on", "--no-start"],
        ["run", "--once"],
        ["off"],
    ]:
        invoked = subprocess.run(
            [sys.executable, str(cli), "--repo", str(repo), *command],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        assert invoked.returncode == 0, (command, invoked.stdout, invoked.stderr)
        if command[0] == "run":
            assert json.loads(invoked.stdout)["state"] == "waiting"
    assert (install / "scripts/ac_store/ac_parent_id.py").read_bytes() == (
        ROOT / "scripts/ac_store/ac_parent_id.py"
    ).read_bytes()
    assert (install / "scripts/ac_store/__init__.py").is_file()
    assert (install / "scripts/background_worker/requirements.txt").exists()
    assert (install / "scripts/background_worker/reviewer_sdk/package.json").exists()
    assert not (install / "scripts/background_worker/reviewer_sdk/node_modules").exists()
    assert build_background_worker(install, {}, False, True) == 0


# covers: ACD-1300b-1
def test_worker_sources_registered_in_both_build_guard_inventories():
    import build
    from build_phases_background_worker import manifest_background_worker

    expected = manifest_background_worker(ROOT)
    assert "scripts/background_worker/reviewer_sdk/bridge.mjs" in expected
    assert "scripts/background_worker/reviewer_sdk/package.json" in expected
    assert "scripts/background_worker/requirements.txt" in expected
    assert "scripts/background_worker/planning.py" in expected
    assert "scripts/ac_store/ac_parent_id.py" in expected
    assert "scripts/ac_store/__init__.py" in expected
    assert expected <= build._get_source_deployable_scripts(ROOT)
    assert expected <= build._get_source_paths_for_guard(ROOT)
    assert not any("node_modules" in path or "__pycache__" in path for path in expected)


# covers: ACD-1300b-1-i
def test_worker_missing_canonical_helper_is_reported_before_partial_deploy(tmp_path, monkeypatch):
    import build_phases
    from build_phases_background_worker import build_background_worker

    package = tmp_path / "package"
    (package / "scripts/background_worker").mkdir(parents=True)
    (package / "scripts/background_worker_cli.py").write_text("pass\n")
    errors = []
    monkeypatch.setattr(build_phases, "PACKAGE_ROOT", package)
    monkeypatch.setattr(build_phases, "record_deploy_failure", lambda *args: errors.append(args))
    target = tmp_path / "install"
    assert build_background_worker(target, {}, False, True) == 0
    assert any("ac_parent_id.py" in str(error) for error in errors)
    assert not target.exists()
