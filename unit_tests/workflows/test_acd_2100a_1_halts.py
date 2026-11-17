"""
MODULE: test_acd_2100a_1_halts
GOAL: The halt paths of plan-feature.js's repo-anchored maker-path fallback
    (`resolveRepoAnchoredMakerPath`, ACD-2100a-1): when no workspace is handed
    in, the run finds the workspace maker's in-repository location with two
    plain probes. Whenever that location cannot be named with certainty the run
    must END (status error, through workspaceFailure) quoting what it received,
    and must never dispatch the maker (`worktree.py ensure`).

    Four halts are covered:
      1. no repository resolves (no repo here, no child repo);
      2. the probe reply is a decline;
      3. the probe reply is prose, not a result;
      4. several child repositories are found -- the maker's AMBIGUOUS_REPO;
         the run must not pick one (it used to take the alphabetically first).

HARNESS: the real-execution harness of test_acd_2100a_1.py (every shell-runner
    dispatch is ACTUALLY executed with a controlled cwd against a real
    temporary filesystem); the decline and prose cases answer the probe label
    with a canned reply instead.

TICKET: 18_TICKET-20261020-epic-ci-green.md (review findings M-1, M-3)
AC: ACD-2100a-1
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from unit_tests.workflows.test_acd_2100a_1 import (  # noqa: E402 -- shared real-execution harness
    _IN_REPO_STUB,
    _ADD_VERB,
    _SETUP_LABEL,
    _granted_workspace_setup_permission,
    _make_fixture,
    _run,
    _run_plan_feature_real,
)

_PROBE_LABEL = "resolve-maker-path"


def _drive(cwd: Path, label_responses: dict | None = None) -> dict:
    return _run_plan_feature_real(
        cwd,
        label_responses=label_responses or {},
        args={"workspace_setup_permission": _granted_workspace_setup_permission()},
    )


def _assert_halted_without_maker(payload: dict, *quoted: str) -> str:
    """The run ended status error quoting each `quoted` fragment, and the maker
    was never dispatched (no workspace-ensure step, no `worktree.py ensure`)."""
    result = payload.get("result")
    assert isinstance(result, dict) and result.get("status") == "error", (
        f"Expected the run to end with status error; got result={result!r} "
        f"error={payload.get('error')!r}"
    )
    message = result.get("message") or ""
    assert message.startswith("Workspace step failed: "), (
        f"The halt must go through workspaceFailure; got message={message!r}"
    )
    for fragment in quoted:
        assert fragment in message, f"The halt must quote {fragment!r}; got message={message!r}"
    calls = payload.get("calls", [])
    ensure_steps = [c for c in calls if isinstance(c.get("opts"), dict) and c["opts"].get("label") == _SETUP_LABEL]
    ensure_prompts = [c for c in calls if isinstance(c.get("prompt"), str) and "worktree.py ensure" in c["prompt"]]
    assert not ensure_steps and not ensure_prompts, (
        f"The workspace maker was dispatched after the fallback could not resolve it: {ensure_steps or ensure_prompts}"
    )
    return message


def _add_child_repo(parent: Path, name: str) -> Path:
    """A second real child repository carrying its own in-repo maker copy."""
    repo = parent / name
    _run(["git", "init", "-b", "main", str(repo)])
    _run(["git", "-C", str(repo), "config", "user.email", "test@example.com"])
    _run(["git", "-C", str(repo), "config", "user.name", "Test"])
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _run(["git", "-C", str(repo), "add", "README.md"])
    _run(["git", "-C", str(repo), "commit", "-m", "seed"])
    scripts = repo / ".leafcutter" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "worktree.py").write_text(_IN_REPO_STUB.replace("@@ADD_VERB@@", _ADD_VERB), encoding="utf-8")
    return repo


def test_no_repository_resolves_halts_quoting_the_probe_replies():
    # covers: ACD-2100a-1
    # angle: failure
    """Neither probe finds a repository (cwd is no repo and holds no child
    repo): the run ends quoting both probes' replies; the maker never runs."""
    with tempfile.TemporaryDirectory(prefix="acd2100a1_norepo_") as tmp:
        payload = _drive(Path(tmp))
        _assert_halted_without_maker(payload, "could not be resolved", "git rev-parse", "realpath -- */.git")


def test_declined_probe_halts_quoting_the_decline():
    # covers: ACD-2100a-1
    # angle: failure
    """The shell runner declines the probe: the run ends quoting the decline,
    even though a resolvable child repository is right there."""
    decline = {"declined": True, "agent": "shell-runner", "reason": "globbing is outside my role"}
    with tempfile.TemporaryDirectory(prefix="acd2100a1_decline_") as tmp:
        fixture = _make_fixture(Path(tmp), with_repo_copy=True)
        payload = _drive(fixture["parent_dir"], {_PROBE_LABEL: decline})
        _assert_halted_without_maker(payload, "the agent declined resolve-maker-path", "globbing is outside my role")


def test_prose_probe_reply_halts_quoting_the_prose():
    # covers: ACD-2100a-1
    # angle: failure
    """The probe reply is prose, not a result: it is never taken as the probe
    having run; the run ends quoting the prose."""
    prose = "Sure, I had a look and the repository is in the usual place."
    with tempfile.TemporaryDirectory(prefix="acd2100a1_prose_") as tmp:
        fixture = _make_fixture(Path(tmp), with_repo_copy=True)
        payload = _drive(fixture["parent_dir"], {_PROBE_LABEL: prose})
        _assert_halted_without_maker(payload, "a prose reply, not a result", prose)


def test_several_child_repositories_halt_quoting_the_candidates():
    # covers: ACD-2100a-1
    # angle: failure
    """Two child repositories, each with its own maker copy, sit under the cwd:
    the location is ambiguous (the maker's AMBIGUOUS_REPO), so the run ends
    quoting both candidates instead of picking one."""
    with tempfile.TemporaryDirectory(prefix="acd2100a1_ambiguous_") as tmp:
        fixture = _make_fixture(Path(tmp), with_repo_copy=True)
        other = _add_child_repo(fixture["parent_dir"], "another-repo")
        payload = _drive(fixture["parent_dir"])
        _assert_halted_without_maker(
            payload,
            "AMBIGUOUS_REPO",
            str(fixture["repo_dir"].resolve() / ".git"),
            str(other.resolve() / ".git"),
        )
