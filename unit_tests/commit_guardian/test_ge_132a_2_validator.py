"""
MODULE: unit_tests/commit_guardian/test_ge_132a_2_validator.py
COVERS: GE-132a-2 -- a remedy declaration naming a specialist or a skill that does
    not exist, or giving the author no instructions, is refused. One test per
    arm of the AC, each through a real ``git commit``.

GOAL, REACHABILITY ENTRY POINT and REGISTRY PLACEMENT: see the shared fixture
    _ge_132a_2_fixture.py (built on the GE-132a-1 harness).

MARKERS: the layout is only READ, so every test is ``shared_layout_reader``; no
    private build.py is spawned.

DECISION HISTORY
- 2026-10-12 [GE-132a-2/test-writer]: Initial RED authoring.
- 2026-10-12 [GE-132a-2/BrainCandy]: Real-table assertions pinned to the decided disposition table.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ge_132a_1_harness import (  # noqa: E402
    _DRIVER,
    GIT_TIMEOUT,
    _accepted,
    _hooks,
    _lines_naming,
    _real_manifest,
    _refused,
)
from _ge_132a_2_fixture import (  # noqa: E402
    DEL,
    DOC_LINKS_INSTRUCTION,
    attempt,
    block_around,
    complexity_decl,
    declare,
    real_scratch,
    rule_of,
)

# The disposition table decided by BrainCandy, 2026-10-12.
ENGAGE_SPECIALIST_AGENTS = {
    "check-complexity": "restructuring-specialist",
    "check-ac-schema": "python-coder",
    "check-contract-shrinking": "python-coder",
    "check-exception-handling": "python-coder",
    "check-file-size": "python-coder",
    "check-glossary-coverage": "glossary-triage",
    "check-sql-complexity": "sql-coder",
    "check-ticket-ac-limits": "python-coder",
}
AUTHOR_CLEARS_HOOKS = ("check-doc-links", "check-secrets", "check-commit-scope", "check-build-epic-gate-verdicts")


def _loaded(repo: Path, *hook_ids: str) -> dict:
    """Run the DEPLOYED shared loader in a fresh process at the repo root."""
    done = subprocess.run(
        [sys.executable, "-c", _DRIVER, str(repo / "scripts" / "commit_guardian"), *hook_ids],
        cwd=str(repo), capture_output=True, text=True, timeout=GIT_TIMEOUT, check=False,
    )
    assert done.returncode == 0, f"loader failed: {done.stdout}{done.stderr}"
    return json.loads(done.stdout)


@pytest.mark.shared_layout_reader
def test_ge132a2_real_declarations_with_specialist_and_author_clears_are_accepted(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: GE-132a-2
    # angle: real_artifact
    """Arm 1, the regression boundary. REAL tracked table and registries.

    The real table (BrainCandy, 2026-10-12): check-complexity engage-specialist
    (restructuring-specialist + complexity-reduction, arm-one instruction); the
    structural coder-routed checks engage-specialist keeping their agent;
    check-doc-links, check-secrets and check-commit-scope author-clears naming
    no agent; every other general-purpose rule mechanical-autofix naming
    general-purpose. A commit
    touching the declarations then passes and names neither check.

    Wrong versions caught: a validator that refuses every declaration; naming no
    specialist mistaken for naming one that does not exist.
    """
    repo, stanza, base = real_scratch(shared_reference_layout, tmp_path / "arm1")
    seed = json.loads((repo / "templates/scripts/precommit-autofix.json").read_text(encoding="utf-8"))
    registered = {h["id"] for h in _hooks(_real_manifest())}
    loaded = _loaded(repo, "check-complexity", "check-doc-links")

    cx = loaded["check-complexity"]
    assert cx and cx["disposition"] == "engage-specialist", cx
    assert cx["agent"] == "restructuring-specialist", cx
    assert "complexity-reduction" in cx["skills"], cx
    assert "restructuring" in cx["instruction"].lower() and "never raise the limit" in cx["instruction"].lower(), cx

    dl = loaded["check-doc-links"]
    assert dl and dl["disposition"] == "author-clears", dl
    assert not dl["agent"] and not dl["skills"], f"author-clears must name no agent or skill: {dl}"
    assert DOC_LINKS_INSTRUCTION in dl["instruction"].lower(), dl

    by_id = {rule["hook_id"]: rule for rule in seed["rules"]}
    for hook_id, agent in ENGAGE_SPECIALIST_AGENTS.items():
        rule = by_id[hook_id]
        assert rule["disposition"] == "engage-specialist" and rule["agent"] == agent, f"{hook_id}: {rule}"
    for hook_id in AUTHOR_CLEARS_HOOKS:
        rule = by_id[hook_id]
        assert rule["disposition"] == "author-clears", f"{hook_id}: {rule}"
        assert not rule.get("agent") and not rule.get("skills"), f"{hook_id} names an agent or skill: {rule}"

    for rule in seed["rules"]:
        if rule["hook_id"] not in registered:
            continue
        assert str(rule.get("instruction", "")).strip(), f"{rule['hook_id']} gives the author no instruction"
        if rule.get("subagent_type") == "general-purpose" and rule["hook_id"] not in AUTHOR_CLEARS_HOOKS:
            assert rule.get("disposition") == "mechanical-autofix", f"{rule['hook_id']}: {rule.get('disposition')!r}"
            assert rule.get("agent") == "general-purpose", f"{rule['hook_id']} names {rule.get('agent')!r}"

    touched = copy.deepcopy(seed)
    touched["_comment"] = touched["_comment"] + " (touched)"
    before, commit = attempt(repo, base, touched)
    output = _accepted(repo, before, commit, stanza)
    assert not _lines_naming(output, "check-complexity"), output
    assert not _lines_naming(output, "check-doc-links"), output


@pytest.mark.shared_layout_reader
def test_ge132a2_unknown_agent_is_refused_naming_it(shared_reference_layout: Path, tmp_path: Path) -> None:
    # covers: GE-132a-2
    # angle: failure
    """Arm 2. check-complexity is engage-specialist naming complexity-fixer: refused,
    naming check-complexity and complexity-fixer as an agent that does not exist,
    and the file that supplied it. Control: the same declaration naming
    restructuring-specialist commits. Subcases: an absent disposition, an unknown
    value, author-clears naming an agent, engage-specialist naming none and
    mechanical-autofix naming none are each refused naming the hook.

    Wrong version caught: the route inferred from the agent name (author-clears
    plus a real specialist name treated as engage-specialist) instead of read
    from the declared disposition.
    """
    repo, stanza, base = real_scratch(shared_reference_layout, tmp_path / "arm2")
    seed = json.loads((repo / "templates/scripts/precommit-autofix.json").read_text(encoding="utf-8"))

    before, commit = attempt(repo, base, declare(seed, "check-complexity", **complexity_decl()))
    _accepted(repo, before, commit, stanza)  # control: the same shape with a real specialist

    before, commit = attempt(repo, base, declare(seed, "check-complexity", **complexity_decl(agent="complexity-fixer")))
    output = _refused(repo, before, commit)
    named = block_around(output, "complexity-fixer")
    assert named, f"complexity-fixer not named: {output!r}"
    assert "check-complexity" in named, f"check-complexity not named beside it: {output!r}"
    assert "agent" in named and "not exist" in named, f"not stated as an agent that does not exist: {output!r}"
    assert "precommit-autofix.json" in output, f"supplying file not named: {output!r}"

    shapes = {
        "absent disposition": ("check-complexity", complexity_decl(disposition=DEL)),
        "unknown disposition": ("check-complexity", complexity_decl(disposition="auto-fix")),
        "author-clears naming an agent": ("check-complexity", complexity_decl(disposition="author-clears", skills=[])),
        "engage-specialist naming none": ("check-complexity", complexity_decl(agent=None)),
        "mechanical-autofix naming none": ("check-doc-frontmatter", {"disposition": "mechanical-autofix", "agent": None}),
    }
    for label, (hook_id, fields) in shapes.items():
        before, commit = attempt(repo, base, declare(seed, hook_id, **fields))
        shaped = _refused(repo, before, commit)
        assert _lines_naming(shaped, hook_id), f"{label}: {hook_id} not named: {shaped!r}"


@pytest.mark.shared_layout_reader
def test_ge132a2_unknown_skill_is_refused_naming_it(shared_reference_layout: Path, tmp_path: Path) -> None:
    # covers: GE-132a-2
    # angle: failure
    """Arm 3. check-complexity names the skill complexity-reducer (the agent is the
    real restructuring-specialist): refused, naming check-complexity and
    complexity-reducer as a skill that does not exist, and not accusing the agent.
    """
    repo, _, base = real_scratch(shared_reference_layout, tmp_path / "arm3")
    seed = json.loads((repo / "templates/scripts/precommit-autofix.json").read_text(encoding="utf-8"))
    before, commit = attempt(repo, base, declare(seed, "check-complexity", **complexity_decl(skills=["complexity-reducer"])))
    output = _refused(repo, before, commit)
    named = block_around(output, "complexity-reducer")
    assert named, f"complexity-reducer not named: {output!r}"
    assert "check-complexity" in named, f"check-complexity not named beside it: {output!r}"
    assert "skill" in named and "not exist" in named, f"not stated as a skill that does not exist: {output!r}"
    assert not _lines_naming(output, "restructuring-specialist"), f"the real agent was wrongly refused: {output!r}"
    assert "precommit-autofix.json" in output, f"supplying file not named: {output!r}"


@pytest.mark.shared_layout_reader
def test_ge132a2_declaration_with_no_instruction_is_refused(shared_reference_layout: Path, tmp_path: Path) -> None:
    # covers: GE-132a-2
    # angle: boundary
    """Arm 4. check-doc-links with an absent, an empty and a whitespace-only
    instruction is refused, naming check-doc-links as a declaration that tells
    the author nothing. The rule keeps its non-empty ``description`` throughout,
    so a validator that falls back to the description when the instruction is
    absent is caught by the absent subcase. Control: the real instruction commits.
    """
    repo, stanza, base = real_scratch(shared_reference_layout, tmp_path / "arm4")
    seed = json.loads((repo / "templates/scripts/precommit-autofix.json").read_text(encoding="utf-8"))
    assert str(rule_of(seed, "check-doc-links").get("description", "")).strip(), "fixture needs a description to fall back on"

    ok_seed = declare(seed, "check-doc-links", disposition="author-clears", agent=None, skills=[], instruction=DOC_LINKS_INSTRUCTION)
    before, commit = attempt(repo, base, ok_seed)
    _accepted(repo, before, commit, stanza)

    for label, value in (("absent", DEL), ("empty", ""), ("whitespace-only", "  \t \n ")):
        bad = declare(ok_seed, "check-doc-links", instruction=value)
        before, commit = attempt(repo, base, bad)
        output = _refused(repo, before, commit)
        named = block_around(output, "check-doc-links")
        assert named, f"{label}: check-doc-links not named: {output!r}"
        assert "instruction" in named or "nothing" in named, f"{label}: not stated as telling the author nothing: {output!r}"
        assert "precommit-autofix.json" in output, f"{label}: supplying file not named: {output!r}"

