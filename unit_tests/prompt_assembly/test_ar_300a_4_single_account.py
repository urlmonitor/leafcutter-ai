"""AR-300a-4 -- no compiled prompt carries two competing accounts of what an
agent may use: one account, equal to the declaration in BOTH directions, and the
single-account property asserted over every compiled prompt in every platform
root with a count.

Source of truth: .../AR-300a-4.yaml.

MEASURED RED BASELINE (real compiled output): templates/agents/python-coder.md
has a HAND-WRITTEN ``## Your Available Skills`` section (``| Skill | Description |``,
names only ``signoff``) and slice 1 now ALSO appends the delivered section
(``| Skill | Mode | Description |``, names ``signoff`` + ``doc-enforcer``), so its
compiled prompt carries TWO accounts in both platform roots.

Account detection is anchored on structure (a ##/### heading about skills/
abilities that names installed skill ids as rows, OUTSIDE code fences) -- never on
a bare heading-string count: python-coder's body also has a fenced
``### Skills run`` example that must not count (AR-200b-1 noisy-detector lesson).

RED / GREEN map:
  test_affected_agent_compiled_prompt_carries_exactly_one_abilities_account      RED (two accounts today)
  test_the_single_account_equals_the_declaration_in_both_directions               RED (two accounts today)
  test_a_second_hand_written_account_added_to_any_template_is_caught              RED (comparison module absent)
  test_single_account_property_is_asserted_over_every_compiled_prompt_with_a_count RED (comparison module absent)
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300ad_support import (  # noqa: E402
    REPO_ROOT,
    TEMPLATES_AGENTS,
    abilities_heading_lines,
    accounts,
    compile_with,
    compiled_agent_roots,
    installed_skill_ids,
    layout_roots,
    per_prompt_findings,
    real_declarations,
    source_templates,
    verdict_for,
)

AFFECTED = "python-coder"  # the one known instance (AR-300a-4 "Given the one agent ...")


def _ids(entries) -> set[str]:
    return {e["skill_id"] if isinstance(e, dict) else e for e in entries}


@pytest.mark.shared_layout_reader
def test_affected_agent_compiled_prompt_carries_exactly_one_abilities_account(shared_reference_layout):
    # covers: AR-300a-4
    # angle: deployed
    """AR-300a-4: after delivery is repaired the affected agent's compiled prompt
    contains ONE account of its abilities, not two, in EVERY platform root.
    RED today: the hand-written section and the delivered one both arrive."""
    installed = installed_skill_ids(REPO_ROOT)
    roots = layout_roots(shared_reference_layout)
    assert len(roots) >= 2 and (TEMPLATES_AGENTS / f"{AFFECTED}.md").is_file()
    for root in roots:
        text = (root / f"{AFFECTED}.md").read_text(encoding="utf-8")
        found = accounts(text, installed)
        assert len(found) == 1, (
            f"{root.parent.name}: {len(found)} accounts of {AFFECTED}'s abilities "
            f"({[a['heading'] + ' ' + str(a['ids']) for a in found]})"
        )
        assert len(abilities_heading_lines(text)) == 1, f"{root.parent.name}: competing abilities headings"


@pytest.mark.shared_layout_reader
def test_the_single_account_equals_the_declaration_in_both_directions(shared_reference_layout):
    # covers: AR-300a-4
    # angle: deployed
    """AR-300a-4: the abilities named in the surviving (single) account are
    EXACTLY the declaration's grant -- none named that was not granted, none
    granted that goes unnamed -- checked per direction so the drift case is
    visible. RED today: there is no single account (two), and the hand-written
    one names fewer abilities than the declaration grants."""
    installed = installed_skill_ids(REPO_ROOT)
    roots = layout_roots(shared_reference_layout)
    want = _ids(real_declarations()[AFFECTED])
    assert len(roots) >= 2 and len(want) >= 2, "affected agent must hold a multi-ability grant"
    for root in roots:
        found = accounts((root / f"{AFFECTED}.md").read_text(encoding="utf-8"), installed)
        assert len(found) == 1, f"{root.parent.name}: {len(found)} accounts, expected exactly one"
        named = set(found[0]["ids"])
        assert not (named - want), f"{root.parent.name}: named but not granted: {sorted(named - want)}"
        assert not (want - named), f"{root.parent.name}: granted but unnamed: {sorted(want - named)}"


def _copy_roots(layout: Path, work: Path) -> list[Path]:
    out = []
    for root in compiled_agent_roots(layout):
        dst = work / root.relative_to(layout)
        shutil.copytree(root, dst)
        out.append(dst)
    return out


def _plant_in_template(tmp_path: Path, target: str, section: str, roots: list[Path]) -> None:
    """Plant ``section`` in a copy of the REAL template ``target``, compile it
    with the REAL compiler (real registry + real skills), and overwrite that
    agent's prompt in every copied root with the authentic compiled bytes."""
    original = (TEMPLATES_AGENTS / f"{target}.md").read_text(encoding="utf-8")
    src = tmp_path / "planted_src" / f"{target}.md"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(original.rstrip("\n") + "\n\n" + section + "\n", encoding="utf-8")
    agents = json.loads((REPO_ROOT / "config" / "agent_registry.json").read_text(encoding="utf-8"))["agents"]
    compiled = compile_with(src, agents=agents, skills_root=REPO_ROOT / "templates" / "skills")
    assert section.splitlines()[0] in compiled, "the planted section did not survive compilation"
    for root in roots:
        (root / f"{target}.md").write_text(compiled, encoding="utf-8")


@pytest.mark.shared_layout_reader
def test_a_second_hand_written_account_added_to_any_template_is_caught(shared_reference_layout, tmp_path):
    # covers: AR-300a-4
    # angle: real_artifact
    """AR-300a-4: planting a hand-written abilities account in a DIFFERENT
    template (a real granted one, compiled by the real compiler) makes the
    whole-population single-account assertion fail, naming that template, in
    every root. Two planted shapes -- the same heading with a different table,
    and a differently-worded list heading -- so a heading-string counter fails.
    Control: a prose section about skills (no ids as rows) is NOT flagged, and
    the unplanted baseline has no second-account finding for that agent."""
    installed = installed_skill_ids(REPO_ROOT)
    declarations = real_declarations()
    target = next(s for s in sorted(declarations) if s != AFFECTED)
    some_id = sorted(_ids(declarations[target]))[0]
    plants = {
        "same-heading-table": f"## Your Available Skills\n\n| Skill | Description |\n|---|---|\n| {some_id} | hand-written |",
        "reworded-list": f"## Abilities\n\n- {some_id}: hand-written note about when to use it",
    }
    prose_control = "## Skill discipline\n\nInvoke skills sparingly and prefer reading the file first."

    for label, section in {**plants, "prose-control": prose_control}.items():
        copies = _copy_roots(shared_reference_layout, tmp_path / label)
        expected = len(source_templates()) * len(copies)
        baseline = verdict_for(declarations, copies, expected=expected, known=installed)
        assert not [f for f in per_prompt_findings(baseline)
                    if f["agent"] == target and f["kind"] == "second-account"], "control: baseline already doubled"

        _plant_in_template(tmp_path / label, target, section, copies)
        verdict = verdict_for(declarations, copies, expected=expected, known=installed)
        doubled = {f["platform_root"] for f in per_prompt_findings(verdict)
                   if f["agent"] == target and f["kind"] == "second-account"}
        if label in plants:
            assert verdict["ok"] is False, label
            assert doubled == {str(c) for c in copies}, f"{label}: second account not caught in every root: {doubled}"
        else:
            assert not doubled, "a prose section about skills was flagged as a second account"


@pytest.mark.shared_layout_reader
def test_single_account_property_is_asserted_over_every_compiled_prompt_with_a_count(shared_reference_layout, tmp_path):
    # covers: AR-300a-4
    # angle: boundary
    """AR-300a-4: the single-account assertion reports how many compiled prompts
    it examined and covers EVERY platform root, so it cannot pass over an empty
    or partial population: no roots -> failure with 0 examined; only one of the
    two roots -> short population against the build's count."""
    installed = installed_skill_ids(REPO_ROOT)
    declarations = real_declarations()
    roots = layout_roots(shared_reference_layout)
    expected = len(source_templates()) * len(roots)
    assert len(roots) >= 2 and declarations

    full = verdict_for(declarations, roots, expected=expected, known=installed)
    assert full["inspected_count"] == expected
    assert sorted(full["roots_examined"]) == sorted(str(r) for r in roots)

    nothing = verdict_for(declarations, [], expected=expected, known=installed)
    assert nothing["ok"] is False and nothing["inspected_count"] == 0

    partial = verdict_for(declarations, roots[:1], expected=expected, known=installed)
    assert partial["ok"] is False
    assert partial["inspected_count"] == expected // len(roots) < expected
    assert [f for f in partial["findings"] if f["kind"] == "short-population"]
