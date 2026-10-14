"""AR-300a-1-i -- a delivery comparison that examined no agents (or only part of
the tree) FAILS and says which side came back empty; it cannot pass by looking
at nothing (KI-ACS-001).

Source of truth: .../AR-300a-1-i.yaml. Contract for the comparison module (new,
exercisable in isolation per the it_requirements): _ar_300ad_support.py item 1.

All trees here are authentic: templates serialised with yaml.safe_dump and
compiled by the REAL compile_agent_template (never hand-typed compiled text).

RED BASELINE: scripts/agent_grant_delivery.py does not exist, so every test
fails on the import of the comparison module (an absence red).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300ad_support import (  # noqa: E402
    agent_fm,
    make_skill,
    verdict_for,
    write_compiled_tree,
)

SKILLS = {
    "zz-alpha": "Alpha skill forges alpha widgets on request",
    "zz-beta": "Beta skill audits beta ledgers before release",
    "zz-gamma": "Gamma skill reconciles gamma queues nightly",
}


def _skills_root(tmp_path: Path) -> Path:
    root = tmp_path / "skills"
    for sid, desc in SKILLS.items():
        make_skill(root, sid, desc)
    return root


def _grant(*ids: str) -> list[dict]:
    return [{"skill_id": i, "mode": "always"} for i in ids]


def _granted_templates(n: int) -> dict:
    return {f"zz-granted-{k:02d}": (agent_fm(f"zz-granted-{k:02d}", _grant("zz-alpha", "zz-beta")),
                                    "# Agent\n\nDo the work.\n") for k in range(n)}


def _sides(verdict: dict) -> set[str]:
    return {f["side"] for f in verdict["findings"] if f["kind"] == "empty-population"}


def _healthy(tmp_path: Path):
    templates = _granted_templates(3)
    templates["zz-plain"] = (agent_fm("zz-plain"), "# Agent\n\nDo the work.\n")
    roots = write_compiled_tree(tmp_path, templates, _skills_root(tmp_path))
    declarations = {s: fm["skills"] for s, (fm, _b) in templates.items() if "skills" in fm}
    return templates, roots, declarations


def test_control_a_full_healthy_population_passes_and_states_its_counts(tmp_path):
    # covers: AR-300a-1-i
    # angle: criterion
    """AR-300a-1-i control: the same comparison over a complete, correct tree is
    ok with non-zero counts -- so the failures below are caused by the empty /
    short population and not by the comparison failing everything."""
    templates, roots, declarations = _healthy(tmp_path)
    expected = len(templates) * len(roots)
    verdict = verdict_for(declarations, roots, expected=expected, known=set(SKILLS))
    assert verdict["ok"] is True, verdict["findings"]
    assert verdict["inspected_count"] == expected == 8
    assert verdict["granted_count"] == 3
    assert not verdict["findings"]


def test_zero_compiled_prompts_fails_naming_the_prompt_side(tmp_path):
    # covers: AR-300a-1-i
    # angle: failure
    """AR-300a-1-i: with no compiled prompts available the comparison FAILS and
    names the compiled-prompt side as the empty one; it does not report that
    every granted ability arrived. Declarations are non-empty, so the
    declaration side must NOT be named (the cause is not guessed)."""
    _templates, _roots, declarations = _healthy(tmp_path)
    empty_roots = [tmp_path / "empty" / "agents", tmp_path / "empty" / "gemini" / "agents"]
    for root in empty_roots:
        root.mkdir(parents=True)
    verdict = verdict_for(declarations, empty_roots, expected=8, known=set(SKILLS))
    assert verdict["ok"] is False
    assert verdict["inspected_count"] == 0
    assert _sides(verdict) == {"compiled_prompts"}


def test_zero_recognised_declarations_fails_naming_the_declaration_side(tmp_path):
    # covers: AR-300a-1-i
    # angle: failure
    """AR-300a-1-i: compiled prompts are present but no grant declaration is
    recognised -> the comparison FAILS and names the declaration side only."""
    templates = {f"zz-plain-{k}": (agent_fm(f"zz-plain-{k}"), "# Agent\n\nDo the work.\n") for k in range(3)}
    roots = write_compiled_tree(tmp_path, templates, _skills_root(tmp_path))
    verdict = verdict_for({}, roots, expected=len(templates) * len(roots), known=set(SKILLS))
    assert verdict["ok"] is False
    assert verdict["inspected_count"] == len(templates) * len(roots) > 0
    assert verdict["granted_count"] == 0
    assert _sides(verdict) == {"declarations"}


def test_both_sides_empty_names_both_sides(tmp_path):
    # covers: AR-300a-1-i
    # angle: failure
    """AR-300a-1-i: when BOTH come back empty the failure names both, so neither
    cause is hidden behind the other."""
    empty = tmp_path / "agents"
    empty.mkdir()
    verdict = verdict_for({}, [empty], expected=0, known=set(SKILLS))
    assert verdict["ok"] is False
    assert _sides(verdict) == {"compiled_prompts", "declarations"}


def test_population_shorter_than_compiled_prompt_count_fails(tmp_path):
    # covers: AR-300a-1-i
    # angle: boundary
    """AR-300a-1-i: examining 6 of 60 compiled prompts fails -- a partial reach
    is not read as a clean run. The compiled count comes from the caller (the
    build), not from a stored figure. Control: the same 6 prompts against an
    expected count of 6 are ok, so the failure is the shortfall alone."""
    roots = write_compiled_tree(tmp_path, _granted_templates(6), _skills_root(tmp_path), root_names=("agents",))
    declarations = {f"zz-granted-{k:02d}": _grant("zz-alpha", "zz-beta") for k in range(6)}

    short = verdict_for(declarations, roots, expected=60, known=set(SKILLS))
    assert short["ok"] is False
    assert short["inspected_count"] == 6
    shortfalls = [f for f in short["findings"] if f["kind"] == "short-population"]
    assert len(shortfalls) == 1
    assert (shortfalls[0]["inspected"], shortfalls[0]["expected"]) == (6, 60)
    assert not [f for f in short["findings"] if f["kind"] == "empty-population"]

    exact = verdict_for(declarations, roots, expected=6, known=set(SKILLS))
    assert exact["ok"] is True, exact["findings"]


def test_missing_output_root_fails_rather_than_skipping(tmp_path):
    # covers: AR-300a-1-i
    # angle: failure
    """AR-300a-1-i: an absent compiled-prompt directory (fresh worktree) and a
    BROKEN SYMLINK (a dangling .claude/agents shim) both fail and name the
    compiled-prompt side; neither resolves to an empty set and exits clean. A
    good root next to a missing one is also a failure (the partial reach)."""
    templates, roots, declarations = _healthy(tmp_path)
    expected = len(templates) * len(roots)

    absent = tmp_path / "fresh-worktree" / ".leafcutter" / "agents"
    verdict = verdict_for(declarations, [absent], expected=expected, known=set(SKILLS))
    assert verdict["ok"] is False
    assert "compiled_prompts" in _sides(verdict)

    dangling = tmp_path / "shim" / "agents"
    dangling.parent.mkdir()
    dangling.symlink_to(tmp_path / "shim" / "does-not-exist")
    verdict = verdict_for(declarations, [dangling], expected=expected, known=set(SKILLS))
    assert verdict["ok"] is False
    assert "compiled_prompts" in _sides(verdict)

    verdict = verdict_for(declarations, [roots[0], absent], expected=expected, known=set(SKILLS))
    assert verdict["ok"] is False
    assert verdict["inspected_count"] == len(templates) < expected
