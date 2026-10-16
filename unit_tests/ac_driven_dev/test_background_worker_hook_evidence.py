"""Hook diagnostics preserve bounded process evidence through outcome reconciliation."""

import json
from pathlib import Path

import pytest

from scripts.background_worker.execution_boundary import ExecutorError, run_process
from scripts.background_worker.git_hooks import GitHookSandbox, GitHookError
from .test_background_worker_hooks import hook_repo, requires_bubblewrap  # noqa: F401


@requires_bubblewrap
def test_failed_real_hook_retains_guard_output(request):
    # covers: ACD-1300g-1, ACD-1300g-2
    repo, workspace, install = request.getfixturevalue("hook_repo")
    install("printf 'Meaningful guard failure\\n' >&2; exit 7")
    with pytest.raises(GitHookError) as caught:
        with GitHookSandbox(repo, workspace).invocation(workspace) as overrides:
            run_process(["git", *overrides, "commit", "-m", "checked"], cwd=workspace, timeout=30)
    assert "Meaningful guard failure" in caught.value.evidence["stderr"]
    assert caught.value.evidence["returncode"] != 0
    assert caught.value.evidence["hook_outcomes"][0]["hook"] == "pre-commit"
    assert isinstance(caught.value.__cause__, ExecutorError)


def test_missing_hook_outcome_preserves_timeout_cause_bounded_redacted(tmp_path, monkeypatch):
    # covers: ACD-1300g-1, ACD-1300g-1-i
    sandbox = GitHookSandbox(tmp_path, tmp_path)
    monkeypatch.setattr(sandbox, "preflight", lambda cwd: [tmp_path / "pre-commit"])
    monkeypatch.setenv("PROBE_SECRET_TOKEN", "example-private-credential")
    cause = ExecutorError("Execution timed out; process tree terminated")
    cause.evidence = {"stdout": "x" * 20000 + "example-private-credential", "stderr": "guard still running", "argv": ["must not persist"]}
    with pytest.raises(GitHookError) as caught:
        with sandbox.invocation(tmp_path) as overrides:
            directory = Path(overrides[1].split("=", 1)[1])
            (directory / "outcomes.jsonl").write_text(json.dumps({"hook": "pre-commit", "started": True}) + "\n")
            raise cause
    evidence = caught.value.evidence
    assert "timed out" in evidence["cause"]
    assert "outcome missing" in evidence["hook_outcomes"][0]["reason"]
    assert "example-private-credential" not in json.dumps(evidence)
    assert len(evidence["stdout"]) <= 16000
    assert "argv" not in evidence
    assert caught.value.__cause__ is cause
