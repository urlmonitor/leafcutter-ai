"""Support for the TQ-600a-13-xxiv tests: a synthetic pull-request repository and the Proof-of-done selector run on it.

Test infrastructure, not a test (the filename starts with an underscore). The same helpers produced the recorded baseline
(``tests/fixtures/tq_600a_13_xxiv/baseline.json``) from the selector at origin/main, before the post-merge live lane landed,
and produce the current run: ``scripts_dir`` names which tree's selector runs.

The synthetic repository holds an AC store written with ``yaml.safe_dump`` and covers-tagged tests, at a ``base`` commit and
three one-commit pull-request branches off it:

* ``pr-live``  -- flips SYN-100 (its covers-tagged live test passes) to done;
* ``pr-fail``  -- flips SYN-400 (its covers-tagged live test fails) to done;
* ``pr-none``  -- changes no done criterion (retitles the todo SYN-300).

SYN-200 is done at ``base`` with a covers-tagged test that FAILS: no pull request touches it, so a selector that widens its
selection beyond the changed criteria reports it.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
PR_BRANCHES = ("pr-live", "pr-fail", "pr-none")
PASSING_BODY = "def test_{n}_live_proof():\n    # covers: SYN-{num}\n    assert 1 + 1 == 2\n"
FAILING_BODY = "def test_{n}_live_proof():\n    # covers: SYN-{num}\n    assert 1 + 1 == 3\n"
GIT = ["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", "-c", "user.name=t", "-c", "user.email=t@example.com"]


def _git(repo, *args):
    done = subprocess.run([*GIT, "-C", str(repo), *args], capture_output=True, text=True, check=False, timeout=60)
    if done.returncode != 0:
        message = f"git {args} failed: {done.stderr}"
        raise AssertionError(message)
    return done.stdout


def _write_ac(repo, num, work_status, title=None):
    record = {
        "id": f"SYN-{num}",
        "title": title or f"Synthetic criterion {num}",
        "component": "synthetic",
        "level": "L3",
        "status": "active",
        "work_status": work_status,
        "readiness": "approved",
        "priority": "medium",
        "depends_on": [],
        "covered_by": [],
        "implemented_by": [],
        "superseded_by": None,
    }
    path = repo / "docs" / "acceptance-criteria" / "synthetic" / f"SYN-{num}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(record, allow_unicode=True), encoding="utf-8")


def _write_test(repo, num, passing):
    path = repo / "tests" / "knowledge_live" / f"test_syn_{num}.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (PASSING_BODY if passing else FAILING_BODY).format(n=num, num=num)
    path.write_text(body, encoding="utf-8")


def build_pr_repo(root):
    """Create the synthetic repository under ``root``; return its path (checked out at ``base``)."""
    repo = Path(root) / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "base")
    # Like the real repository, a pytest.ini at the root: it anchors the proof's child pytest there, so the relative
    # `--test-root .` of the done-proof job resolves.
    (repo / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    _write_ac(repo, "100", "todo")
    _write_ac(repo, "200", "done")
    _write_ac(repo, "300", "todo")
    _write_ac(repo, "400", "todo")
    for num, passing in (("100", True), ("200", False), ("400", False)):
        _write_test(repo, num, passing)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    for branch, change in (
        ("pr-live", lambda: _write_ac(repo, "100", "done")),
        ("pr-fail", lambda: _write_ac(repo, "400", "done")),
        ("pr-none", lambda: _write_ac(repo, "300", "todo", title="Retitled, still todo")),
    ):
        _git(repo, "checkout", "-q", "-b", branch, "base")
        change()
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", branch)
    _git(repo, "checkout", "-q", "base")
    return repo


def checkout(repo, branch):
    _git(repo, "checkout", "-q", branch)


def load_selector(scripts_dir):
    """Import ``check_done_proof`` from ``scripts_dir`` (its siblings and ``ac_store`` come from the same tree)."""
    for sub in ("ac_store", "commit_guardian"):
        entry = str(Path(scripts_dir) / sub)
        if entry not in sys.path:
            sys.path.insert(0, entry)
    import check_done_proof

    return check_done_proof


def _normal(text, repo):
    return str(text).replace(str(repo), "<repo>")


@contextlib.contextmanager
def _in_directory(path):
    previous = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def select_in_process(selector, repo, branch):
    """Run the selector's PR-scoped check in-process on ``branch``; return what it evaluated, selected and returned."""
    checkout(repo, branch)
    evaluated = []
    real = selector.verify_done_eligible

    def recording(ac_id, **kwargs):
        verdict = real(ac_id, **kwargs)
        evaluated.append(
            {
                "ac_id": ac_id,
                "tests": sorted(_normal(t, repo) for t in verdict.get("passing_tests", []) + verdict.get("failing_tests", [])),
            }
        )
        return verdict

    with _in_directory(repo):
        changed = selector._get_changed_ac_yaml_paths("base", repo)
        with mock.patch.object(selector, "verify_done_eligible", side_effect=recording):
            violations = selector.check_changed_done_acs(changed, ac_root=repo / "docs" / "acceptance-criteria", test_root=repo)
    return {
        "changed": sorted(p.name for p in changed),
        "evaluated": evaluated,
        "violations": [{"ac_id": v["ac_id"], "reason": _normal(v["reason"], repo)} for v in violations],
    }


def write_verdict(repo, verdict):
    """Drop a post-merge verdict file where a reader of the artifact could look for it (untracked, never committed)."""
    document = {"lane": "correctness", "verdict": verdict, "stage": "live_database", "live_database": {"verdict": verdict}}
    for rel in ("post-merge-verdict.json", "verdict/post-merge-verdict.json", "artifacts/post-merge-verdict/post-merge-verdict.json"):
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(document), encoding="utf-8")


def run_cli(scripts_dir, repo, branch, argv=None):
    """Run ``check_done_proof.py`` as the ``done-proof`` job does, as a child process, on ``branch``."""
    checkout(repo, branch)
    command = [sys.executable, str(Path(scripts_dir) / "commit_guardian" / "check_done_proof.py")]
    command += argv or ["--mode", "ci-changed", "--base", "base", "--test-root", "."]
    done = subprocess.run(command, cwd=repo, capture_output=True, text=True, check=False, timeout=300)
    lines = sorted(_normal(line, repo) for line in done.stdout.splitlines() if line.startswith("[check-done-proof]"))
    return {"exit": done.returncode, "lines": lines}


def job_shape(document, name="done-proof"):
    """What of the ``done-proof`` job the baseline pins: every key but its steps, and the proof step's argument list."""
    job = document["jobs"][name]
    steps = [s for s in job["steps"] if "check_done_proof.py" in str(s.get("run", ""))]
    argv = steps[0]["run"].split("check_done_proof.py", 1)[1].split()
    return {"job": {k: v for k, v in job.items() if k != "steps"}, "proof_step_argv": argv, "proof_steps": len(steps)}
