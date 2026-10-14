"""
MODULE: unit_tests/commit_guardian/test_ge_132a_4_committed_table.py
COVERS: GE-132a-4 -- the commit-time remedy checks (check-hook-parity's registration
    and validity legs) judge the package's COMMITTED declaration table
    (templates/scripts/precommit-autofix.json), so a stale or absent local copy can
    neither refuse a correct commit nor pass a defective one. Run-time readers
    (check-complexity's refusal text, the BO-3800 run) keep the shared loader's
    local-table-first view.

GOAL: Behavioural proof through a REAL ``git commit``. Scratch repos are built by
    the GE-132a-2 fixture (``real_scratch``): the generated ``check-hook-parity``
    stanza, the DEPLOYED guardian scripts, and the REAL tracked table, registries
    and manifest re-serialised with ``json.dumps``. The stale local table is the
    REAL GE-132a-1-era table read with ``git show``; the local table is written
    after the baseline commit, gitignored, and never staged.

REACHABILITY ENTRY POINT (resolved, BP-1100g-2 Step 1.2): the registered pre-commit
    hook -- ``git commit`` -> pre-commit -> generated stanza -> deployed run_hook.py
    -> deployed check_hook_parity.py (arms 1, 2, 4) / check_complexity.py (arm 3).

MARKERS: the layout is only READ, so every test is ``shared_layout_reader``; no
    private build.py is spawned.

DECISION HISTORY
- 2026-10-12 [GE-132a-4/test-writer]: Initial RED authoring (arms 1 and 2 red by
  design; arms 3 and 4 are regression boundaries that are green today).
"""

from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ge_132a_1_harness import (  # noqa: E402
    _DRIVER,
    GIT_TIMEOUT,
    LOCAL_REL,
    REPO_ROOT,
    SEED_REL,
    _accepted,
    _commit,
    _dump,
    _git,
    _head,
    _lines_naming,
    _real_seed,
    _refused,
    _stage,
)
from _ge_132a_2_fixture import block_around, complexity_decl, declare, real_scratch  # noqa: E402
from test_ge_132a_3_refusal import _env, _refusal, _scratch_complexity  # noqa: E402

GE_132A_1_ERA_REF = "5d8bb260a"
DEPLOYED_ONLY = re.compile(r"(?<!templates/)scripts/precommit-autofix\.json")
COULD_NOT_CHECK = re.compile(r"could[ _-]not[ _-]check")
LOCAL_INSTRUCTION = "split plan_batches into two functions"
SEED_INSTRUCTION = "bring in the restructuring specialist to apply the complexity-reduction skill to the named function"


def _stale_local_table() -> dict:
    """The REAL GE-132a-1-era table plus a check-docstrings rule that carries a disposition."""
    shown = subprocess.run(
        ["git", "show", f"{GE_132A_1_ERA_REF}:{SEED_REL}"], cwd=str(REPO_ROOT),
        capture_output=True, text=True, timeout=GIT_TIMEOUT, check=False,
    )
    assert shown.returncode == 0, f"GE-132a-1-era table not retrievable: {shown.stderr}"
    table = json.loads(shown.stdout)
    mechanical = [r for r in table["rules"] if r.get("disposition") == "mechanical-autofix"]
    assert len(mechanical) == 9 and all(r["agent"] is None for r in mechanical), "stale table is not the real one"
    assert any(r["hook_id"] == "check-doc-frontmatter" for r in mechanical)
    table["rules"].append({
        "hook_id": "check-docstrings", "category": "mechanical", "model": "haiku",
        "subagent_type": "general-purpose", "description": "Missing docstring.",
        "disposition": "mechanical-autofix", "instruction": "Add the missing docstring.",
        "agent": None, "skills": [],
    })
    return table


def _ignore_local(repo: Path) -> None:
    """List the local table in .gitignore, as a real install does, in its own commit."""
    (repo / ".gitignore").write_text(f"{LOCAL_REL}\n", encoding="utf-8")
    _git(["add", ".gitignore"], repo)
    _git(["commit", "-q", "--no-verify", "-m", "ignore the local routing table", "--", ".gitignore"], repo)


def _change_committed(repo: Path, **agent_override: object) -> None:
    """Touch ``_comment`` of the committed table (and optionally set rule fields) and stage it."""
    path = repo / SEED_REL
    table = json.loads(path.read_text(encoding="utf-8"))
    table["_comment"] = table["_comment"] + " (touched by GE-132a-4)"
    for hook_id, fields in agent_override.items():
        next(r for r in table["rules"] if r["hook_id"] == hook_id.replace("_", "-")).update(fields)
    _dump(path, table)
    _stage(repo, SEED_REL)


def _loaded(repo: Path, *hook_ids: str) -> dict:
    """Run the DEPLOYED shared loader in a fresh process at the repo root."""
    done = subprocess.run(
        [sys.executable, "-c", _DRIVER, str(repo / "scripts" / "commit_guardian"), *hook_ids],
        cwd=str(repo), capture_output=True, text=True, timeout=GIT_TIMEOUT, check=False,
    )
    assert done.returncode == 0, f"loader failed: {done.stdout}{done.stderr}"
    return json.loads(done.stdout)


@pytest.mark.shared_layout_reader
def test_ge132a4_stale_local_table_does_not_refuse_a_correct_committed_table(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: GE-132a-4
    # angle: real_artifact
    """Arm 1. A stale gitignored local table (null-agent mechanical-autofix rules and a
    check-docstrings rule no check has) must neither refuse a correct committed table
    nor be named in any output line.

    Wrong versions caught: THE LOCAL JUDGE (commit-time legs read the merged view);
    a half fix where validity reads the committed table but the reason-(c) loop still
    iterates the local table (check-docstrings would still be named).
    """
    repo, stanza, _base = real_scratch(shared_reference_layout, tmp_path / "arm1")
    _ignore_local(repo)
    _dump(repo / LOCAL_REL, _stale_local_table())
    _change_committed(repo)
    before = _head(repo)
    output = _accepted(repo, before, _commit(repo, "touch the committed routing table"), stanza)
    for name in ("check-doc-frontmatter", "check-docstrings"):
        assert not _lines_naming(output, name), f"output names {name}: {output!r}"
    assert ".claude/precommit-autofix.json" not in output, f"output names the local table: {output!r}"
    assert not _COULD(output), f"leg could not check: {output!r}"


def _COULD(output: str) -> bool:  # noqa: N802 - tiny predicate shared by two arms
    return COULD_NOT_CHECK.search(output.lower()) is not None


@pytest.mark.shared_layout_reader
def test_ge132a4_defective_committed_table_is_refused_despite_a_perfect_local_table(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: GE-132a-4
    # angle: failure
    """Arm 2. The committed table gives check-doc-frontmatter no agent; the local table
    and the deployed scripts/ copy are both correct. The commit is refused naming the
    check, "names no agent" and the COMMITTED path. Subcase: with the committed table
    deleted the leg reports could-not-check (never falls back to a correct copy).

    Wrong versions caught: THE MASK (correct local rule hides the defect); THE
    DEPLOYED JUDGE; THE DEPLOYED FALLBACK (absent committed table judged from
    scripts/ or the local table).
    """
    failures: list[str] = []

    repo, _stanza, _base = real_scratch(shared_reference_layout, tmp_path / "arm2")
    _ignore_local(repo)
    _dump(repo / LOCAL_REL, _real_seed())
    _change_committed(repo, check_doc_frontmatter={"agent": None})
    before = _head(repo)
    try:
        output = _refused(repo, before, _commit(repo, "break the committed routing table"))
        block = block_around(output, "check-doc-frontmatter")
        if "check-doc-frontmatter" not in block or "names no agent" not in block:
            failures.append(f"refusal does not say check-doc-frontmatter names no agent: {output!r}")
        if SEED_REL not in output:
            failures.append(f"refusal does not name the committed table {SEED_REL}: {output!r}")
        if ".claude/precommit-autofix.json" in output:
            failures.append(f"refusal names the local table: {output!r}")
        if DEPLOYED_ONLY.search(output):
            failures.append(f"refusal names the deployed scripts/ copy: {output!r}")
    except AssertionError as exc:
        failures.append(f"defective committed table: {exc}")

    absent, _stanza2, _base2 = real_scratch(shared_reference_layout, tmp_path / "arm2_absent")
    _ignore_local(absent)
    _dump(absent / LOCAL_REL, _real_seed())
    _git(["rm", "-q", SEED_REL], absent)
    # pre-commit never passes a deleted path to a hook, so the deletion alone would skip
    # the stanza ("no files to check"); stage a second path the stanza's files regex matches.
    (absent / "scripts" / "commit_guardian" / "note.txt").write_text("accompanies the deletion\n", encoding="utf-8")
    _stage(absent, "scripts/commit_guardian/note.txt")
    before = _head(absent)
    try:
        output = _refused(absent, before, _commit(absent, "delete the committed routing table"))
        if not _COULD(output):
            failures.append(f"absent committed table not reported as could-not-check: {output!r}")
        if SEED_REL not in output:
            failures.append(f"could-not-check does not name the missing {SEED_REL}: {output!r}")
        lowered = output.lower()
        if "names no agent" in lowered or "needs a remedy declaration" in lowered:
            failures.append(f"absent table reported as a declaration finding: {output!r}")
    except AssertionError as exc:
        failures.append(f"absent committed table: {exc}")

    assert not failures, "\n".join(failures)


@pytest.mark.shared_layout_reader
def test_ge132a4_run_time_readers_keep_the_local_declaration(shared_reference_layout: Path, tmp_path: Path) -> None:
    # covers: GE-132a-4
    # angle: boundary
    """Arm 3, the regression boundary. The local table's check-complexity instruction
    wins at run time: the refusal shows it and not the seed's, and the DEPLOYED shared
    loader returns it with a source ending in .claude/precommit-autofix.json.

    Wrong version caught: THE OVERREACH (shared loader pointed at the committed table).
    """
    repo = _scratch_complexity(shared_reference_layout, tmp_path / "arm3", SEED_INSTRUCTION)
    _ignore_local(repo)
    local = declare(copy.deepcopy(_real_seed()), "check-complexity", **complexity_decl(instruction=LOCAL_INSTRUCTION))
    _dump(repo / LOCAL_REL, local)
    block = _refusal(repo, _env())
    flat = " ".join(block.split())
    assert LOCAL_INSTRUCTION in flat, f"local instruction not shown: {block!r}"
    assert SEED_INSTRUCTION not in flat, f"the seed's instruction is shown: {block!r}"
    declared = _loaded(repo, "check-complexity")["check-complexity"]
    assert declared and declared["instruction"] == LOCAL_INSTRUCTION, declared
    assert declared["source"].endswith(LOCAL_REL), f"not reported as the local table: {declared}"


@pytest.mark.shared_layout_reader
def test_ge132a4_absent_local_table_with_correct_committed_table_passes(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: GE-132a-4
    # angle: boundary
    """Arm 4. No .claude/ directory at all; the correct committed table is touched and
    staged. check-hook-parity passes, with no could-not-check and no mention of the
    local table.

    Wrong version caught: THE ABSENT-LOCAL REFUSAL (leg demands a local table).
    """
    repo, stanza, _base = real_scratch(shared_reference_layout, tmp_path / "arm4")
    assert not (repo / ".claude").exists(), "fixture must have no .claude/ directory"
    _change_committed(repo)
    before = _head(repo)
    output = _accepted(repo, before, _commit(repo, "touch the committed routing table"), stanza)
    assert not _COULD(output), f"leg could not check: {output!r}"
    assert ".claude/precommit-autofix.json" not in output, f"output names the local table: {output!r}"
