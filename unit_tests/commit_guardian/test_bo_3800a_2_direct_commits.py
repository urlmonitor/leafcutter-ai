"""
MODULE: unit_tests/commit_guardian/test_bo_3800a_2_direct_commits.py
COVERS: BO-3800a-2 arm 3 -- a session or a person running ``git commit`` themselves is
    refused with the declared next step and nothing else: no party is engaged, nothing
    is held on their behalf, no handoff artifact is written.

GOAL: Behavioural proof through a REAL ``git commit`` in a scratch repo wired by a real
    ``pre-commit install`` with the ``check-complexity`` stanza copied from the
    ``.pre-commit-config.yaml`` build.py generated into the shared deployed layout. The
    routing table is the REAL seed, unedited. The change raises plan_batches from 30 to
    31 (its ceiling is 30); the source is generated, never a checked-in literal.

REACHABILITY ENTRY POINT (resolved, BP-1100g-2 Step 1.2): the registered pre-commit hook
    -- ``git commit`` -> pre-commit -> generated stanza -> deployed run_hook.py ->
    deployed check_complexity.py.

MARKERS: the layout is only READ, so the test is ``shared_layout_reader``.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ge_132a_1_harness import (  # noqa: E402
    GIT_TIMEOUT,
    HOOK_TIMEOUT,
    SEED_RELS,
    _deployed_guardian,
    _dump,
    _git,
    _head,
    _real_seed,
)

TARGET = "scripts/planner.py"
DEMAND = re.compile(r"complexity 31[^\n]*only 30 allowed")


def _function(name: str, score: int) -> str:
    """Source for a function scoring exactly ``score`` (base 1, +1 per ``if``)."""
    body = "".join(f"    if x == {i}:\n        pass\n" for i in range(score - 1))
    return f"def {name}(x):\n{body}    return x\n"


def _env(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE") and k != "COMMIT_AGENT_MODE"}
    env.update(extra)
    return env


def _scratch(layout: Path, root: Path) -> Path:
    """Real git repo: plan_batches=30 committed, 31 staged, check-complexity wired,
    the REAL unedited seed routing table in place."""
    config = yaml.safe_load((layout / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    stanza = dict({h["id"]: h for repo in config["repos"] for h in repo["hooks"]}["check-complexity"])
    root.mkdir(parents=True)
    shutil.copytree(_deployed_guardian(layout), root / "scripts" / "commit_guardian", ignore=shutil.ignore_patterns("__pycache__"))
    marker = "scripts/commit_guardian/"
    stanza["entry"] = " ".join(
        str(root / tok[tok.index(marker):]) if marker in tok else tok for tok in stanza["entry"].split()
    )
    for rel in SEED_RELS:
        _dump(root / rel, _real_seed())
    (root / "scripts").mkdir(exist_ok=True)
    (root / TARGET).write_text(_function("plan_batches", 30), encoding="utf-8")
    _git(["init", "-q", "-b", "main"], root)
    _git(["config", "user.email", "bo3800a2@example.com"], root)
    _git(["config", "user.name", "BO-3800a-2 fixture"], root)
    _git(["add", "-A"], root)
    _git(["commit", "-q", "--no-verify", "-m", "baseline"], root)
    (root / ".pre-commit-config.yaml").write_text(yaml.safe_dump({"repos": [{"repo": "local", "hooks": [stanza]}]}), encoding="utf-8")
    installed = subprocess.run(
        ["pre-commit", "install", "--hook-type", "pre-commit"], cwd=str(root), capture_output=True, text=True,
        timeout=GIT_TIMEOUT, check=False,
    )
    assert installed.returncode == 0, f"pre-commit install: {installed.stdout}{installed.stderr}"
    (root / TARGET).write_text(_function("plan_batches", 31), encoding="utf-8")
    _git(["add", TARGET], root)
    return root


def _snapshot(repo: Path) -> dict:
    """Everything a refusal could have touched: HEAD, index, working tree, stash, and
    every file under the repo root outside .git."""
    files = {
        p.relative_to(repo).as_posix(): p.read_bytes()
        for p in sorted(repo.rglob("*"))
        if p.is_file() and not {".git", "__pycache__"} & set(p.relative_to(repo).parts)
    }
    return {
        "head": _head(repo),
        "status": _git(["status", "--porcelain"], repo).stdout,
        "index": _git(["diff", "--cached"], repo).stdout,
        "stash": _git(["stash", "list"], repo).stdout,
        "files": files,
    }


def _refuse(repo: Path, env: dict[str, str]) -> str:
    done = subprocess.run(
        ["git", "commit", "-m", "raise plan_batches"], cwd=str(repo), capture_output=True, text=True,
        timeout=HOOK_TIMEOUT, check=False, env=env,
    )
    output = done.stdout + done.stderr
    assert done.returncode != 0, f"commit was accepted: {output!r}"
    return output


@pytest.mark.shared_layout_reader
def test_bo3800a2_direct_commits_engage_nobody_and_show_declared_next_step(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BO-3800a-2
    # angle: boundary
    # reachability surface: real `git commit` in a scratch repo through the generated stanza
    """Arm 3. The commit is made once with no env marker (a person at a terminal) and
    once with CLAUDECODE=1 (an interactive session). Each refusal leaves HEAD, the
    index and the working tree exactly as they were, writes no handoff artifact, and
    shows 'complexity 31, only 30 allowed' with restructuring-specialist and
    complexity-reduction named as the next step. This arm is a REGRESSION BOUNDARY: the
    refusal text shipped with GE-132a-3, so it is green at baseline; it goes red if the
    work for arms 1-2 makes a direct commit write an artifact, hold anything, or lose
    the text.

    Wrong versions caught: engaging/holding for a direct commit (state changes or an
    artifact appears); a refusal for a direct committer that omits the specialist.
    """
    repo = _scratch(shared_reference_layout, tmp_path / "arm3")
    outputs = {}
    for who, env in (("person at a terminal", _env()), ("interactive session", _env(CLAUDECODE="1"))):
        before = _snapshot(repo)
        handoff_before = {p for p in tmp_path.rglob("*") if p.is_file() and "handoff" in p.name.lower()}
        outputs[who] = _refuse(repo, env)
        after = _snapshot(repo)
        assert after == before, f"{who}: the refusal changed the repository: {outputs[who]!r}"
        # Only files the refusal wrote count: the shipped remedy_handoff.py helper predates it.
        written = [p for p in after["files"] if "handoff" in p.lower() and p not in before["files"]]
        assert not written, f"{who}: a handoff artifact was written: {written}"
        appeared = {p for p in tmp_path.rglob("*") if p.is_file() and "handoff" in p.name.lower()} - handoff_before
        assert not appeared, f"{who}: a handoff artifact appeared outside the repo: {sorted(appeared)}"

    for who, output in outputs.items():
        flat = " ".join(output.split())
        assert DEMAND.search(flat), f"{who}: no 'complexity 31 ... only 30 allowed': {output!r}"
        assert "restructuring-specialist" in flat, f"{who}: the specialist to bring in is not named: {output!r}"
        assert "complexity-reduction" in flat, f"{who}: the skill is not named: {output!r}"
        assert "python-coder" not in flat, f"{who}: the author is named as the next step: {output!r}"
