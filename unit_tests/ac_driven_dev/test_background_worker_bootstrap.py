"""Fresh-worktree deployment closure and actual package guard execution."""

from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from scripts.background_worker.bootstrap import provision_runtime
from scripts.background_worker.execution_boundary import ExecutorError, run_process, permission_overrides
from scripts.background_worker.git_ops import GitOps


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=True).stdout.strip()


@pytest.fixture
def deployed_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "--initial-branch=main")
    git(repo, "config", "user.name", "Worker test")
    git(repo, "config", "user.email", "worker@example.invalid")
    (repo / ".gitignore").write_text(".leafcutter/\n.pre-commit-config.yaml\n")
    (repo / "README.md").write_text("# Fixture\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "seed")
    for path in ("scripts", "config", "skills/security-scanner/scripts"):
        (repo / ".leafcutter" / path).mkdir(parents=True, exist_ok=True)
    (repo / ".leafcutter/scripts/commit_guardian").mkdir()
    (repo / ".leafcutter/scripts/commit_guardian/check_secrets.py").write_text("print('checked')\n")
    (repo / ".leafcutter/pre-commit-config.yaml").write_text(
        "repos:\n- repo: local\n  hooks:\n  - id: fixture\n    name: fixture\n"
        "    entry: python .leafcutter/scripts/commit_guardian/check_secrets.py\n    language: system\n")
    return repo


def workspace(repo):
    path = repo.parent / "owned"
    git(repo, "worktree", "add", "-b", "codex/test", str(path))
    return path


def test_bootstrap_copies_ignored_runtime_only_and_idempotently(deployed_repo):
    # covers: ACD-1300b-4, ACD-1300g-1
    repo = deployed_repo
    (repo / ".env").write_text("private")
    (repo / ".leafcutter/scripts/auth.json").write_text("private")
    (repo / ".leafcutter/config/user-credentials.json").write_text("private")
    (repo / ".leafcutter/scripts/custom-secret.py").write_text("private")
    (repo / ".leafcutter/background-worker").mkdir()
    (repo / ".leafcutter/background-worker/state.sqlite").write_text("private-state")
    owned = workspace(repo)
    assert provision_runtime(repo, owned, run_process)
    assert provision_runtime(repo, owned, run_process)
    assert (owned / ".leafcutter/scripts/commit_guardian/check_secrets.py").is_file()
    assert not (owned / ".env").exists()
    assert not (owned / ".leafcutter/scripts/auth.json").exists()
    assert not (owned / ".leafcutter/config/user-credentials.json").exists()
    assert not (owned / ".leafcutter/scripts/custom-secret.py").exists()
    assert not (owned / ".leafcutter/background-worker").exists()
    assert not git(owned, "status", "--porcelain")
    (owned / ".leafcutter/scripts/commit_guardian/check_secrets.py").write_text("altered")
    with pytest.raises(ExecutorError, match="differs"):
        provision_runtime(repo, owned, run_process)


def test_bootstrap_rejects_unignored_runtime_and_missing_entrypoint(deployed_repo):
    # covers: ACD-1300g-1-i
    owned = workspace(deployed_repo)
    (owned / ".gitignore").write_text(".pre-commit-config.yaml\n")
    with pytest.raises(ExecutorError):
        provision_runtime(deployed_repo, owned, run_process)
    (owned / ".gitignore").write_text(".leafcutter/\n.pre-commit-config.yaml\n")
    (deployed_repo / ".leafcutter/scripts/commit_guardian/check_secrets.py").unlink()
    with pytest.raises(ExecutorError, match="entrypoint"):
        provision_runtime(deployed_repo, owned, run_process)


def test_model_runtime_permissions_are_readonly(tmp_path):
    # covers: ACD-1300b-1
    import tomllib
    from scripts.background_worker.bootstrap import PROTECTED_PATHS

    for relative in PROTECTED_PATHS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".yaml":
            path.touch()
        else:
            path.mkdir(exist_ok=True)
    config = tomllib.loads("\n".join(permission_overrides(workspace=tmp_path)))
    grants = config["permissions"]["leafcutter-worker"]["filesystem"][":workspace_roots"]
    assert all(grants[path] == "read" for path in PROTECTED_PATHS)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink test")
def test_bootstrap_rejects_source_config_link_before_reading(deployed_repo):
    # covers: ACD-1300b-1-i
    config = deployed_repo / ".leafcutter/pre-commit-config.yaml"
    config.unlink()
    config.symlink_to(deployed_repo.parent / "unreadable-missing-source")
    with pytest.raises(ExecutorError, match="symlinks"):
        provision_runtime(deployed_repo, workspace(deployed_repo), run_process)


@pytest.mark.skipif(not sys.platform.startswith("linux") or not shutil.which("bwrap"),
                    reason="Real package guards require Linux hook boundary")
@pytest.mark.parametrize("bad", [False, True])
def test_fresh_worktree_runs_real_deployed_secret_guard(deployed_repo, bad):
    # covers: ACD-1300g-1, ACD-1300g-2
    source = Path(__file__).resolve().parents[2] / ".leafcutter"
    repo = deployed_repo
    shutil.copytree(source / "scripts/commit_guardian", repo / ".leafcutter/scripts/commit_guardian",
                    dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(source / "skills/security-scanner/scripts", repo / ".leafcutter/skills/security-scanner/scripts",
                    dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
    (repo / ".leafcutter/pre-commit-config.yaml").write_text(
        "repos:\n- repo: local\n  hooks:\n  - id: check-secrets\n    name: Real secrets guard\n"
        "    entry: python .leafcutter/scripts/commit_guardian/run_hook.py .leafcutter/scripts/commit_guardian/check_secrets.py\n"
        "    language: system\n    pass_filenames: false\n    always_run: true\n")
    hook = repo / ".git/hooks/pre-commit"
    hook.write_text("#!/usr/bin/env bash\nexec '" + sys.executable + "' -m pre_commit hook-impl "
                    "--config=.pre-commit-config.yaml --hook-type=pre-commit --hook-dir=\"$(dirname \"$0\")\" -- \"$@\"\n")
    hook.chmod(0o700)
    ops = GitOps(repo, {"target_ref": "main"})
    run = {"id": "fixture", "payload": {}}
    prepared = ops.prepare(run)
    run.update(workspace=prepared["workspace"])
    run["payload"].update(prepared)
    owned = Path(run["workspace"])
    (owned / "new.txt").write_text(("-----BEGIN " + "RSA PRIVATE KEY-----\n") if bad else "safe fixture\n")
    if bad:
        with pytest.raises(ExecutorError):
            ops.commit(run, "DEM-100a-1")
        assert ops.head(owned) == prepared["base_sha"]
    else:
        assert ops.commit(run, "DEM-100a-1") != prepared["base_sha"]


@pytest.mark.skipif(not sys.platform.startswith("linux") or not shutil.which("bwrap"),
                    reason="Real runtime immutability requires Linux")
def test_real_hook_cannot_rewrite_provisioned_runtime(deployed_repo):
    # covers: ACD-1300b-1-i
    repo = deployed_repo
    ops = GitOps(repo, {"target_ref": "main"})
    run = {"id": "immutable", "payload": {}}
    prepared = ops.prepare(run)
    run.update(workspace=prepared["workspace"])
    run["payload"].update(prepared)
    owned = Path(run["workspace"])
    hook = repo / ".git/hooks/pre-commit"
    hook.write_text("#!/bin/sh\nprintf replaced > .leafcutter/scripts/commit_guardian/check_secrets.py\n")
    hook.chmod(0o700)
    (owned / "README.md").write_text("changed\n")
    with pytest.raises(ExecutorError):
        ops.commit(run, "DEM-100a-1")
    assert (owned / ".leafcutter/scripts/commit_guardian/check_secrets.py").read_text() == "print('checked')\n"
    assert ops.head(owned) == prepared["base_sha"]
