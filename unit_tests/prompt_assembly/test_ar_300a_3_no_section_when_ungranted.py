"""AR-300a-3 -- an agent granted nothing receives NO abilities section (no
heading, no empty list), absent and empty declarations behave identically, and
every compiled prompt is either a complete section or no section -- never a
short one.

Source of truth: .../AR-300a-3.yaml. Evidence is compiled bytes only.

RED / GREEN-ALREADY map:
  test_agent_with_absent_grant_declaration_gets_no_abilities_section         GREEN-ALREADY (slice 1 returns the body unchanged)
  test_every_real_ungranted_agent_has_no_section_in_every_platform_root      GREEN-ALREADY (real tree)
  test_agent_with_explicitly_empty_grant_gets_the_identical_result           GREEN-ALREADY
  test_every_compiled_prompt_is_complete_section_or_no_section               GREEN-ALREADY (real tree, test-side partition)
  test_the_verifier_reports_the_two_counts_and_the_partition_holds           RED (comparison module absent)
  test_a_section_naming_fewer_abilities_than_the_grant_is_a_failure          RED (comparison module absent)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300ad_support import (  # noqa: E402
    REPO_ROOT,
    abilities_heading_lines,
    accounts,
    agent_fm,
    compile_with,
    installed_skill_ids,
    layout_roots,
    make_skill,
    named_in_accounts,
    per_prompt_findings,
    real_declarations,
    source_templates,
    verdict_for,
    write_compiled_tree,
    write_template,
)

SKILLS = {
    "zz-alpha": "Alpha skill forges alpha widgets on request",
    "zz-beta": "Beta skill audits beta ledgers before release",
}
BODY = "# Agent\n\nDo the work.\n"


def _skills_root(tmp_path: Path) -> Path:
    root = tmp_path / "skills"
    for sid, desc in SKILLS.items():
        make_skill(root, sid, desc)
    return root


def _compile(tmp_path: Path, stem: str, fm: dict) -> str:
    tpl = write_template(tmp_path / "src" / f"{stem}.md", fm, BODY)
    return compile_with(tpl, agents=None, skills_root=_skills_root(tmp_path))


def test_agent_with_absent_grant_declaration_gets_no_abilities_section(tmp_path):
    # covers: AR-300a-3
    # angle: deployed
    """AR-300a-3: an agent whose frontmatter omits the grant key entirely compiles
    to a prompt with no abilities heading, no account and no empty list.
    Control: the SAME body with a grant DOES get a section, so 'no section' is
    not 'the compiler never emits one'."""
    text = _compile(tmp_path, "zz-absent", agent_fm("zz-absent"))
    assert abilities_heading_lines(text) == []
    assert accounts(text, set(SKILLS)) == []
    assert "Available Skills" not in text

    granted = _compile(tmp_path, "zz-granted", agent_fm("zz-granted", [{"skill_id": "zz-alpha", "mode": "always"}]))
    assert len(abilities_heading_lines(granted)) == 1 and named_in_accounts(granted, set(SKILLS)) == {"zz-alpha"}


@pytest.mark.shared_layout_reader
def test_every_real_ungranted_agent_has_no_section_in_every_platform_root(shared_reference_layout):
    # covers: AR-300a-3
    # angle: deployed
    """AR-300a-3 (real tree): for every real template that declares no grant (a
    population derived from the templates, ~16 today), the compiled prompt in
    EVERY platform root has no abilities heading and no account. Zero ungranted
    agents examined fails (empty population)."""
    installed = installed_skill_ids(REPO_ROOT)
    roots = layout_roots(shared_reference_layout)
    granted = set(real_declarations())
    ungranted = [t.stem for t in source_templates() if t.stem not in granted]
    assert len(roots) >= 2 and ungranted, "0 ungranted agents / roots examined"
    offenders = []
    for stem in ungranted:
        for root in roots:
            text = (root / f"{stem}.md").read_text(encoding="utf-8")
            if abilities_heading_lines(text) or accounts(text, installed):
                offenders.append((root.parent.name, stem))
    assert not offenders, f"{len(offenders)}/{len(ungranted) * len(roots)} ungranted prompts carry a section: {offenders[:5]}"


def test_agent_with_explicitly_empty_grant_gets_the_identical_result(tmp_path):
    # covers: AR-300a-3
    # angle: boundary
    """AR-300a-3: an explicit empty grant (``skills: []``) and a bare ``skills:``
    (null) produce a compiled prompt BYTE-IDENTICAL to the omitted-key case --
    one normalisation, not two branches. Same name in all three so the only
    difference is the key. Control: a one-ability grant differs."""
    omitted = _compile(tmp_path / "a", "zz-same", agent_fm("zz-same"))
    empty_list = _compile(tmp_path / "b", "zz-same", agent_fm("zz-same", []))
    null_key = _compile(tmp_path / "c", "zz-same", agent_fm("zz-same", None) | {"skills": None})
    one = _compile(tmp_path / "d", "zz-same", agent_fm("zz-same", [{"skill_id": "zz-alpha", "mode": "always"}]))
    assert omitted == empty_list == null_key
    assert abilities_heading_lines(empty_list) == [] and abilities_heading_lines(null_key) == []
    assert one != omitted and abilities_heading_lines(one)


@pytest.mark.shared_layout_reader
def test_every_compiled_prompt_is_complete_section_or_no_section(shared_reference_layout):
    # covers: AR-300a-3
    # angle: deployed
    """AR-300a-3: across EVERY compiled prompt in EVERY platform root each falls
    into exactly one of two cases -- a section naming the agent's whole grant, or
    no section at all; a section naming fewer abilities fails. Both counts are
    stated and neither is zero (a one-sided partition would pass vacuously).
    GREEN-ALREADY via slice 1."""
    installed = installed_skill_ids(REPO_ROOT)
    roots = layout_roots(shared_reference_layout)
    declarations = real_declarations()
    sources = [t.stem for t in source_templates()]
    assert len(roots) >= 2 and declarations and sources
    complete = none = 0
    neither = []
    for stem in sources:
        want = {e["skill_id"] if isinstance(e, dict) else e for e in declarations.get(stem, [])}
        for root in roots:
            text = (root / f"{stem}.md").read_text(encoding="utf-8")
            got = named_in_accounts(text, installed)
            has_account = bool(accounts(text, installed)) or bool(abilities_heading_lines(text))
            if want and has_account and got == want:
                complete += 1
            elif not want and not has_account:
                none += 1
            else:
                neither.append((root.parent.name, stem, sorted(want ^ got), has_account))
    assert not neither, f"{len(neither)} prompts are neither complete nor section-free: {neither[:5]}"
    assert complete + none == len(sources) * len(roots)
    assert complete == len(declarations) * len(roots) > 0
    assert none == (len(sources) - len(declarations)) * len(roots) > 0


@pytest.mark.shared_layout_reader
def test_the_verifier_reports_the_two_counts_and_the_partition_holds(shared_reference_layout):
    # covers: AR-300a-3
    # angle: deployed
    """AR-300a-3 (it_requirements): the comparison module classifies every
    compiled prompt and REPORTS the two counts; complete + section-free + flagged
    == inspected, so a prompt that is neither is a finding, not a third category."""
    installed = installed_skill_ids(REPO_ROOT)
    roots = layout_roots(shared_reference_layout)
    declarations = real_declarations()
    expected = len(source_templates()) * len(roots)
    verdict = verdict_for(declarations, roots, expected=expected, known=installed)
    flagged = {(f["agent"], f["platform_root"]) for f in per_prompt_findings(verdict)}
    assert verdict["inspected_count"] == expected
    assert verdict["complete_count"] > 0 and verdict["no_section_count"] > 0
    assert verdict["complete_count"] + verdict["no_section_count"] + len(flagged) == verdict["inspected_count"]
    assert verdict["no_section_count"] == (len(source_templates()) - len(declarations)) * len(roots)


def test_a_section_naming_fewer_abilities_than_the_grant_is_a_failure(tmp_path):
    # covers: AR-300a-3
    # angle: boundary
    """AR-300a-3: a compiled section naming 1 of the agent's 2 granted abilities
    is a failure (the shape a per-ability filter silently produces), reported as
    a short section for that agent in that root, and the partition counts add
    up around it. Control: the whole-grant sibling is complete."""
    skills_root = _skills_root(tmp_path)
    grant_two = [{"skill_id": "zz-alpha", "mode": "always"}, {"skill_id": "zz-beta", "mode": "always"}]
    # compiled from a template granting ONE ability, but the agent's declaration says TWO
    compiled_from = {
        "zz-short": (agent_fm("zz-short", grant_two[:1]), BODY),
        "zz-whole": (agent_fm("zz-whole", grant_two), BODY),
        "zz-plain": (agent_fm("zz-plain"), BODY),
    }
    roots = write_compiled_tree(tmp_path, compiled_from, skills_root, root_names=("agents",))
    declarations = {"zz-short": grant_two, "zz-whole": grant_two}
    verdict = verdict_for(declarations, roots, expected=3, known=set(SKILLS))
    assert verdict["ok"] is False
    short = [f for f in per_prompt_findings(verdict) if f["kind"] == "short-section"]
    assert [(f["agent"], f["platform_root"]) for f in short] == [("zz-short", str(roots[0]))]
    assert verdict["complete_count"] == 1 and verdict["no_section_count"] == 1
    assert verdict["complete_count"] + verdict["no_section_count"] + len(short) == verdict["inspected_count"] == 3
