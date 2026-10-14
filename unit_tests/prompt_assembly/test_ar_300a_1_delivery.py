"""AR-300a-1 -- every agent with a declared grant has the WHOLE grant named in
its COMPILED prompt, in every platform root, measured over a derived population.

Source of truth: docs/acceptance-criteria/agent-registry/AR-300-granted-abilities-arrive/AR-300a-1.yaml
(contract for the comparison module: see _ar_300ad_support.py, item 1).

Evidence rule: every assertion reads compiled prompt bytes (the deployed layout
built by the real build.py, or copies of them) -- never config/agent_registry.json,
never the template frontmatter alone (the template only supplies the population).

RED / GREEN-ALREADY map (slice 1 appended the table from frontmatter):
  test_every_granted_agent_compiled_prompt_names_its_whole_grant      GREEN-ALREADY
  test_delivery_check_fails_when_only_the_compiled_prompt_is_broken   RED (comparison module absent)
  test_comparison_covers_every_platform_root_the_build_emitted        RED (comparison module absent)
  test_examined_count_equals_the_number_of_prompts_the_build_compiled RED (comparison module absent)
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300ad_support import (  # noqa: E402
    REPO_ROOT,
    agent_prompts,
    compiled_agent_roots,
    installed_skill_ids,
    layout_roots,
    named_in_accounts,
    per_prompt_findings,
    real_declarations,
    source_templates,
    strip_delivered_sections,
    verdict_for,
)


def _ids(entries) -> set[str]:
    return {e["skill_id"] if isinstance(e, dict) else e for e in entries}


def _copy_roots(layout: Path, work: Path) -> list[Path]:
    """Byte copies of the real compiled roots, keeping their layout-relative paths."""
    out = []
    for root in compiled_agent_roots(layout):
        dst = work / root.relative_to(layout)
        shutil.copytree(root, dst)
        out.append(dst)
    return out


def _target_agent(declarations: dict) -> str:
    """A granted agent that is not the one carrying a hand-written section."""
    return next(s for s in sorted(declarations) if s != "python-coder")


@pytest.mark.shared_layout_reader
def test_every_granted_agent_compiled_prompt_names_its_whole_grant(shared_reference_layout):
    # covers: AR-300a-1
    # angle: deployed
    """AR-300a-1: after a real build, each agent whose template declares a
    non-empty grant has a compiled prompt (in EVERY platform root) naming every
    ability of that grant -- read from the compiled tree. GREEN-ALREADY: slice 1
    appends the table from frontmatter. Wrong version caught: a section naming
    a sample, or delivery in one root only."""
    installed = installed_skill_ids(REPO_ROOT)
    roots = layout_roots(shared_reference_layout)
    assert len(roots) >= 2, f"expected claude + gemini compiled roots, found {roots}"
    declarations = real_declarations()
    assert declarations, "0 granted agents examined: an empty population is not a pass"

    examined, wrong = 0, []
    for stem, entries in sorted(declarations.items()):
        want = _ids(entries)
        for root in roots:
            prompt = root / f"{stem}.md"
            assert prompt.is_file(), f"{stem}: no compiled prompt in {root}"
            examined += 1
            got = named_in_accounts(prompt.read_text(encoding="utf-8"), installed)
            if got != want:
                wrong.append((root.parent.name, stem, sorted(want ^ got)))
    assert examined == len(declarations) * len(roots) > 0
    assert not wrong, f"{len(wrong)}/{examined} (agent, root) prompts do not name the whole grant: {wrong[:5]}"


@pytest.mark.shared_layout_reader
def test_delivery_check_fails_when_only_the_compiled_prompt_is_broken(shared_reference_layout, tmp_path):
    # covers: AR-300a-1
    # angle: real_artifact
    """AR-300a-1 mutation proof: strip the abilities section from ONE compiled
    prompt of a copy of the real deployed tree, leaving the registry and the
    source template correct; the comparison must name that agent as
    undelivered. A registry- or template-based check passes this mutation (both
    are untouched) -- that is the defect. Control: the unmutated copy has no
    undelivered finding for the agent, so the failure is caused by the strip."""
    installed = installed_skill_ids(REPO_ROOT)
    declarations = real_declarations()
    copies = _copy_roots(shared_reference_layout, tmp_path / "copy")
    expected = len(source_templates()) * len(copies)
    target = _target_agent(declarations)

    baseline = verdict_for(declarations, copies, expected=expected, known=installed)
    assert not [f for f in per_prompt_findings(baseline)
                if f["agent"] == target and f["kind"] == "undelivered"], "control: target undelivered before mutation"

    victim_root = copies[0]
    victim = victim_root / f"{target}.md"
    before = victim.read_text(encoding="utf-8")
    victim.write_text(strip_delivered_sections(before), encoding="utf-8")
    assert victim.read_text(encoding="utf-8") != before, "mutation changed nothing (target had no section)"

    mutated = verdict_for(declarations, copies, expected=expected, known=installed)
    assert mutated["ok"] is False
    hits = [f for f in per_prompt_findings(mutated)
            if f["agent"] == target and f["kind"] == "undelivered"]
    assert [h["platform_root"] for h in hits] == [str(victim_root)]
    assert sorted(hits[0]["missing"]) == sorted(_ids(declarations[target]))


@pytest.mark.shared_layout_reader
def test_comparison_covers_every_platform_root_the_build_emitted(shared_reference_layout, tmp_path):
    # covers: AR-300a-1
    # angle: deployed
    """AR-300a-1: the examined set includes the gemini root as well as the claude
    one -- dropping the section from a prompt in the gemini root ALONE is still
    reported, against that root, and not against the claude root. Wrong version
    caught: a guarantee scoped to the first root only."""
    installed = installed_skill_ids(REPO_ROOT)
    declarations = real_declarations()
    copies = _copy_roots(shared_reference_layout, tmp_path / "copy")
    gemini = [r for r in copies if "gemini" in r.parts]
    claude = [r for r in copies if "gemini" not in r.parts]
    assert len(gemini) == 1 and claude, f"expected one gemini root and a claude root, got {copies}"
    expected = len(source_templates()) * len(copies)
    target = _target_agent(declarations)

    victim = gemini[0] / f"{target}.md"
    victim.write_text(strip_delivered_sections(victim.read_text(encoding="utf-8")), encoding="utf-8")

    verdict = verdict_for(declarations, copies, expected=expected, known=installed)
    assert verdict["ok"] is False
    assert str(gemini[0]) in verdict["roots_examined"] and all(str(c) in verdict["roots_examined"] for c in claude)
    roots_hit = {f["platform_root"] for f in per_prompt_findings(verdict)
                 if f["agent"] == target and f["kind"] == "undelivered"}
    assert roots_hit == {str(gemini[0])}


@pytest.mark.shared_layout_reader
def test_examined_count_equals_the_number_of_prompts_the_build_compiled(shared_reference_layout):
    # covers: AR-300a-1
    # angle: boundary
    """AR-300a-1: the reported examined count equals the number of compiled
    prompts on THIS run (one per source template per platform root, derived),
    and the granted population is derived from the declarations -- no literal 31
    or 60. Wrong version caught: a count taken from one root, or a stored figure."""
    installed = installed_skill_ids(REPO_ROOT)
    roots = layout_roots(shared_reference_layout)
    declarations = real_declarations()
    sources = source_templates()
    assert len(roots) >= 2 and declarations and sources

    on_disk = sum(len(agent_prompts(r)) for r in roots)
    assert on_disk == len(sources) * len(roots), "the build did not compile one prompt per template per root"

    verdict = verdict_for(declarations, roots, expected=on_disk, known=installed)
    assert verdict["inspected_count"] == on_disk
    assert verdict["granted_count"] == len(declarations)
    assert sorted(verdict["roots_examined"]) == sorted(str(r) for r in roots)
    assert isinstance(verdict["population_source"], str) and verdict["population_source"].strip()
    assert verdict["expected_prompt_count"] == on_disk
