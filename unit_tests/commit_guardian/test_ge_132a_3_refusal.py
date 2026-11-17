"""
MODULE: unit_tests/commit_guardian/test_ge_132a_3_refusal.py
COVERS: GE-132a-3 -- a complexity refusal says "<function> has complexity X, only Y
    allowed" and what to do next (bring in the restructuring specialist with the
    complexity-reduction skill), and every reader gets that same text, taken from
    the check's remedy declaration and not from text kept inside the check.

GOAL: Behavioural proof through a REAL ``git commit``. The scratch repo is wired by
    a real ``pre-commit install`` with the ``check-complexity`` stanza copied from
    the ``.pre-commit-config.yaml`` build.py generated into the shared deployed
    layout (never hand-typed), running the DEPLOYED guardian scripts copied into
    the scratch repo. The routing table is the REAL seed re-serialised with
    ``json.dumps``, edited in memory only where an arm needs the change under test.
    The change under test raises plan_batches in scripts/planner.py from 30 to 31
    (30 is its ceiling); the source is generated, never a checked-in literal.

REACHABILITY ENTRY POINT (resolved, BP-1100g-2 Step 1.2): the registered
    pre-commit hook -- ``git commit`` -> pre-commit -> generated stanza ->
    deployed run_hook.py -> deployed check_complexity.py.

MARKERS: the layout is only READ, so every test is ``shared_layout_reader``.

DECISION HISTORY
- 2026-10-12 [GE-132a-3/test-writer]: Initial RED authoring.
"""

from __future__ import annotations

import json
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
from _ge_132a_2_fixture import COMPLEXITY_INSTRUCTION, complexity_decl, declare  # noqa: E402

TARGET = "scripts/planner.py"
NEW_INSTRUCTION = "bring in the restructuring specialist to split plan_batches until it scores at or under 30"
DEMAND = re.compile(r"plan_batches[^\n]*has complexity 31[^\n]*only 30 allowed")


def _function(name: str, score: int) -> str:
    """Source for a function scoring exactly ``score`` (base 1, +1 per ``if``)."""
    body = "".join(f"    if x == {i}:\n        pass\n" for i in range(score - 1))
    return f"def {name}(x):\n{body}    return x\n"


def _env(**extra: str) -> dict[str, str]:
    """The process env with every caller-identifying signal removed, then ``extra``."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE") and k != "COMMIT_AGENT_MODE"}
    env.update(extra)
    return env


def _scratch_complexity(layout: Path, root: Path, instruction: str) -> Path:
    """Real git repo: plan_batches=30 committed, 31 staged, check-complexity wired."""
    config = yaml.safe_load((layout / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    stanza = dict({h["id"]: h for repo in config["repos"] for h in repo["hooks"]}["check-complexity"])
    root.mkdir(parents=True)
    shutil.copytree(_deployed_guardian(layout), root / "scripts" / "commit_guardian", ignore=shutil.ignore_patterns("__pycache__"))
    marker = "scripts/commit_guardian/"
    stanza["entry"] = " ".join(
        str(root / tok[tok.index(marker):]) if marker in tok else tok for tok in stanza["entry"].split()
    )
    seed = declare(_real_seed(), "check-complexity", **complexity_decl(instruction=instruction))
    for rel in SEED_RELS:
        _dump(root / rel, seed)
    (root / "scripts").mkdir(exist_ok=True)
    (root / TARGET).write_text(_function("plan_batches", 30), encoding="utf-8")
    _git(["init", "-q", "-b", "main"], root)
    _git(["config", "user.email", "ge132a3@example.com"], root)
    _git(["config", "user.name", "GE-132a-3 fixture"], root)
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


def _refusal(repo: Path, env: dict[str, str]) -> str:
    """Commit the staged change, require a refusal, and return the hook's own output block."""
    before = _head(repo)
    done = subprocess.run(
        ["git", "commit", "-m", "raise plan_batches"], cwd=str(repo), capture_output=True, text=True,
        timeout=HOOK_TIMEOUT, check=False, env=env,
    )
    output = done.stdout + done.stderr
    assert done.returncode != 0, f"commit was accepted: {output!r}"
    assert _head(repo) == before, "HEAD moved on a refused commit"
    lines = output.splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith("- exit code:")]
    assert starts, f"no hook output block in: {output!r}"
    block = "\n".join(lines[starts[0] + 1:]).strip()
    assert block, f"the hook printed nothing: {output!r}"
    return block


def _assert_states_demand_and_next_step(block: str) -> None:
    """Score, ceiling and the declared next step; no hard-coded tip, no coder fallback."""
    found = DEMAND.search(block)
    assert found, f"no 'plan_batches has complexity 31, only 30 allowed': {block!r}"
    after = block[found.start():].lower()
    assert "restructuring" in after, f"restructuring specialist not named as the next step: {block!r}"
    assert "complexity-reduction" in after, f"complexity-reduction skill not named as the next step: {block!r}"
    assert "safely refactor and extract" not in block, f"the hard-coded tip is still printed: {block!r}"
    assert "python-coder" not in block, f"python-coder still named (extension lookup or fallback literal): {block!r}"


@pytest.mark.shared_layout_reader
def test_ge132a3_refusal_states_complexity_ceiling_and_declared_next_step(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: GE-132a-3
    # angle: criterion
    """Arm 1. plan_batches 30 -> 31: the refused commit says plan_batches has
    complexity 31 and only 30 is allowed, then names the restructuring specialist
    and complexity-reduction as the next step.

    Wrong version caught: THE BARE VERDICT -- refuse with 'too complex' and no numbers.
    """
    repo = _scratch_complexity(shared_reference_layout, tmp_path / "arm1", COMPLEXITY_INSTRUCTION)
    block = _refusal(repo, _env())
    _assert_states_demand_and_next_step(block)
    assert "pure move" in block.lower() and "SKIP=check-complexity" in block, f"GE-131a-3 pure-move line lost: {block!r}"


@pytest.mark.shared_layout_reader
def test_ge132a3_three_committers_get_identical_refusal_text(shared_reference_layout: Path, tmp_path: Path) -> None:
    # covers: GE-132a-3
    # angle: boundary
    """Arm 2. The same staged change committed from a terminal (no marker), as the
    commit agent (COMMIT_AGENT_MODE=1) and from an interactive session
    (CLAUDECODE=1): three byte-identical refusal blocks, each carrying the score,
    the ceiling and the declared next step.

    Wrong version caught: text branching on COMMIT_AGENT_MODE, CLAUDECODE or a TTY.
    """
    repo = _scratch_complexity(shared_reference_layout, tmp_path / "arm2", COMPLEXITY_INSTRUCTION)
    blocks = {
        "terminal": _refusal(repo, _env()),
        "commit agent": _refusal(repo, _env(COMMIT_AGENT_MODE="1")),
        "interactive session": _refusal(repo, _env(CLAUDECODE="1")),
    }
    for block in blocks.values():
        _assert_states_demand_and_next_step(block)
    assert len(set(blocks.values())) == 1, f"refusal text varies by committer: {json.dumps(blocks, indent=1)}"


@pytest.mark.shared_layout_reader
def test_ge132a3_changed_declaration_instruction_changes_the_refusal(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: GE-132a-3
    # angle: discrimination
    """Arm 3. Only the declaration's instruction changes (data, never the check).
    Control: the arm-one instruction recurs as the next step. Then the refusal
    shows 'split plan_batches until it scores at or under 30' and not the old
    sentence, while still stating score and ceiling.

    Wrong version caught: THE COPY -- printing a hard-coded copy of the declared
    instruction (passes arms one and two, fails here).
    """
    control = _refusal(_scratch_complexity(shared_reference_layout, tmp_path / "arm3_old", COMPLEXITY_INSTRUCTION), _env())
    assert "never raise the limit" in control.lower(), f"control: declared instruction not shown: {control!r}"

    changed = _refusal(_scratch_complexity(shared_reference_layout, tmp_path / "arm3_new", NEW_INSTRUCTION), _env())
    flat = " ".join(changed.split())
    assert NEW_INSTRUCTION in flat, f"changed instruction not shown: {changed!r}"
    assert "never raise the limit" not in flat.lower() and "to the named function" not in flat.lower(), (
        f"the earlier next step is still shown: {changed!r}"
    )
    assert DEMAND.search(changed), f"score and ceiling lost: {changed!r}"
