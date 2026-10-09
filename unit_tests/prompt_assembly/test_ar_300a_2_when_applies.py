"""AR-300a-2 -- the delivered abilities section says WHEN each ability applies:
purpose text sourced from the installed ability, every-task vs conditional grants
distinguishable, the condition rendered in the SAME row as its ability, and a
conditional grant with no condition refused by name.

Source of truth: .../AR-300a-2.yaml.

CONDITION TEXT IS NOW APPROVED (/home/henzeh/ar300_probe/conditions_decisions.md):
the real-tree tests assert the RULES (every conditional grant has a condition and it
is delivered on the compiled row; no compiled row says conditional without when;
onboard has no webapp-testing grant; product-owner/business-analyst declare
ac-tree-split) -- never the approved sentences. They are RED until the coder applies
the approved data. The refusal rule is also proven on PLANTED fixtures.

Planted fixtures are compiled by the REAL compile_agent_template (frontmatter
serialised with yaml.safe_dump; fixture SKILL.md files serialised likewise).

RED / GREEN-ALREADY map:
  test_compiled_prompt_names_each_ability_with_what_it_is_for            GREEN-ALREADY (slice 1 renders descriptions)
  test_unconditional_and_conditional_grants_are_distinguishable_...      GREEN-ALREADY (slice 1 renders the Mode column)
  test_condition_text_appears_in_the_same_section_as_its_ability         GREEN-ALREADY (slice 1 renders condition text on the row)
  test_conditional_grant_without_a_condition_is_reported_by_name         RED (gate accepts a bare conditional grant)
  test_always_grant_needs_no_condition_and_is_not_reported               GREEN-ALREADY control (passes for the opposite reason)
  test_refusal_is_the_build_exit_status_not_only_a_message               RED
  test_every_granted_row_in_every_compiled_prompt_carries_its_skills_purpose GREEN-ALREADY (real tree)
  test_counts_of_granted_agents_and_conditional_grants_are_stated        RED (comparison module absent)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300ad_support import (  # noqa: E402
    REPO_ROOT,
    ability_rows,
    agent_fm,
    agent_prompts,
    compile_with,
    installed_skill_ids,
    layout_roots,
    make_skill,
    planted_package,
    real_declarations,
    skill_description,
    verdict_for,
    write_compiled_tree,
    write_template,
)

SKILLS = {
    "zz-alpha": "Alpha skill forges alpha widgets on request",
    "zz-beta": "Beta skill audits beta ledgers before release",
    "zz-gamma": "Gamma skill reconciles gamma queues nightly",
}
COND_BETA = "when the ticket changes a Python file"
COND_GAMMA = "only for release-branch tickets"
GRANT = [
    {"skill_id": "zz-alpha", "mode": "always"},
    {"skill_id": "zz-beta", "mode": "conditional", "condition": COND_BETA},
    {"skill_id": "zz-gamma", "mode": "conditional", "condition": COND_GAMMA},
]


def _skills_root(tmp_path: Path) -> Path:
    root = tmp_path / "skills"
    for sid, desc in SKILLS.items():
        make_skill(root, sid, desc)
    return root


def _compiled(tmp_path: Path, grant=None) -> tuple[str, Path]:
    skills_root = _skills_root(tmp_path)
    tpl = write_template(tmp_path / "src" / "zz-two-kinds.md",
                         agent_fm("zz-two-kinds", grant if grant is not None else GRANT),
                         "# Agent\n\nDo the work.\n")
    return compile_with(tpl, agents=None, skills_root=skills_root), skills_root


def test_compiled_prompt_names_each_ability_with_what_it_is_for(tmp_path):
    # covers: AR-300a-2
    # angle: deployed
    """AR-300a-2: for an agent granted an unconditional AND conditional abilities,
    the compiled prompt names each ability together with the purpose text taken
    from the INSTALLED ability's own SKILL.md description (not retyped in the
    grant). GREEN-ALREADY via slice 1's table builder."""
    text, skills_root = _compiled(tmp_path)
    rows = ability_rows(text, set(SKILLS))
    assert set(rows) == set(SKILLS), f"abilities named: {sorted(rows)}"
    for sid in SKILLS:
        assert len(rows[sid]) == 1, f"{sid} named {len(rows[sid])} times"
        purpose = skill_description(skills_root / sid / "SKILL.md")
        assert purpose and purpose in rows[sid][0], f"{sid}: row lacks its SKILL.md purpose: {rows[sid][0]!r}"


def test_unconditional_and_conditional_grants_are_distinguishable_in_the_section(tmp_path):
    # covers: AR-300a-2
    # angle: deployed
    """AR-300a-2: a reader of the compiled section can tell an every-task grant
    from a conditional one without the registry -- the conditional rows say
    ``conditional`` and the every-task row does not. Control inside: the three
    rows are not all alike, and the conditional ones are distinct from each other."""
    text, _ = _compiled(tmp_path)
    rows = {k: v[0] for k, v in ability_rows(text, set(SKILLS)).items()}
    assert set(rows) == set(SKILLS), f"rows present for {sorted(rows)}, expected all of {sorted(SKILLS)}"
    always_row, beta_row, gamma_row = rows["zz-alpha"], rows["zz-beta"], rows["zz-gamma"]
    # strip the purpose cell: the purpose text must not decide the verdict
    def mode_view(row: str, sid: str) -> str:
        return row.replace(SKILLS[sid], "").lower()
    assert "conditional" not in mode_view(always_row, "zz-alpha")
    assert "conditional" in mode_view(beta_row, "zz-beta")
    assert "conditional" in mode_view(gamma_row, "zz-gamma")
    assert "always" in mode_view(always_row, "zz-alpha")


def test_condition_text_appears_in_the_same_section_as_its_ability(tmp_path):
    # covers: AR-300a-2
    # angle: seam
    """AR-300a-2: the condition recorded on a conditional grant is rendered on the
    SAME row as that ability (adjacent), not elsewhere and not omitted; and a
    condition is never attached to the OTHER conditional ability's row. Wrong
    version caught: a footnote / second table / swapped rows."""
    text, _ = _compiled(tmp_path)
    rows = {k: v[0] for k, v in ability_rows(text, set(SKILLS)).items()}
    assert set(rows) == set(SKILLS), f"rows present for {sorted(rows)}, expected all of {sorted(SKILLS)}"
    assert COND_BETA in rows["zz-beta"] and COND_GAMMA not in rows["zz-beta"]
    assert COND_GAMMA in rows["zz-gamma"] and COND_BETA not in rows["zz-gamma"]
    assert COND_BETA not in rows["zz-alpha"] and COND_GAMMA not in rows["zz-alpha"]
    assert text.count(COND_BETA) == 1 and text.count(COND_GAMMA) == 1


def _gate_package(base: Path, conditional_condition: str | None) -> Path:
    cond = {"skill_id": "zz-beta", "mode": "conditional"}
    if conditional_condition:
        cond["condition"] = conditional_condition
    grant = [{"skill_id": "zz-alpha", "mode": "always"}, cond]
    record = {"id": "zz-cond", "template_path": "templates/agents/zz-cond.md",
              "skills_used": [], "skills_invoked": [dict(g) for g in grant]}
    return planted_package(base, {"zz-cond": (agent_fm("zz-cond", grant), "# Agent\n\nDo the work.\n")},
                           SKILLS, registry_agents=[record])


def test_conditional_grant_without_a_condition_is_reported_by_name(tmp_path):
    # covers: AR-300a-2
    # angle: failure
    """AR-300a-2: a grant declared conditional with no condition string fails
    the build's ability gate, naming the AGENT and the ABILITY; it is not
    delivered as a bare name. The registry record agrees with the declaration, so
    no other finding can be the cause. Controls: the same package WITH a condition
    produces no error, and the ``always`` grant (no condition by design) is never
    named -- the failure is caused by the missing condition alone."""
    from agent_ability_gate import ability_errors

    config = {"output_root": ".leafcutter"}
    bare = ability_errors(_gate_package(tmp_path / "bare", None), config)
    assert bare, "a conditional grant with no condition was accepted by the build gate"
    named = [e for e in bare if "zz-cond" in e and "zz-beta" in e]
    assert named, f"no error names both the agent and the ability: {bare}"
    assert any("condition" in e.lower() for e in named), f"error does not say what is missing: {named}"
    assert not [e for e in bare if "zz-alpha" in e], f"the always grant was reported: {bare}"

    ok = ability_errors(_gate_package(tmp_path / "ok", COND_BETA), config)
    assert ok == [], f"a conditional grant WITH a condition was refused: {ok}"


def test_always_grant_needs_no_condition_and_is_not_reported(tmp_path):
    # covers: AR-300a-2
    # angle: boundary
    """AR-300a-2: an ``always`` grant carries no condition and is accepted --
    guards a wrong version that demands a condition on every grant."""
    from agent_ability_gate import ability_errors

    grant = [{"skill_id": "zz-alpha", "mode": "always"}]
    record = {"id": "zz-always", "template_path": "templates/agents/zz-always.md",
              "skills_used": [], "skills_invoked": [dict(g) for g in grant]}
    pkg = planted_package(tmp_path, {"zz-always": (agent_fm("zz-always", grant), "# Agent\n")},
                          SKILLS, registry_agents=[record])
    assert ability_errors(pkg, {"output_root": ".leafcutter"}) == []


def test_refusal_is_the_build_exit_status_not_only_a_message(tmp_path):
    # covers: AR-300a-2
    # angle: failure
    """AR-300a-2 (ADR-050 refuse-not-warn): the gate entry the build calls returns
    exit code 1 for a bare conditional grant and 0 for the same package with its
    condition -- the finding is consumed in control flow, not only printed."""
    from agent_ability_gate import refuse_on_ability_findings

    config = {"output_root": ".leafcutter"}
    assert refuse_on_ability_findings(_gate_package(tmp_path / "bare", None), config, False) == 1
    assert refuse_on_ability_findings(_gate_package(tmp_path / "ok", COND_BETA), config, False) == 0


@pytest.mark.shared_layout_reader
def test_every_granted_row_in_every_compiled_prompt_carries_its_skills_purpose(shared_reference_layout):
    # covers: AR-300a-2
    # angle: deployed
    """AR-300a-2 (real tree): in EVERY platform root, every ability of every
    granted agent is named on a row that carries the installed ability's own
    SKILL.md purpose text. GREEN-ALREADY via slice 1."""
    installed = installed_skill_ids(REPO_ROOT)
    roots = layout_roots(shared_reference_layout)
    declarations = real_declarations()
    assert len(roots) >= 2 and declarations
    examined, bad = 0, []
    for stem, entries in sorted(declarations.items()):
        for entry in entries:
            sid = entry["skill_id"] if isinstance(entry, dict) else entry
            purpose = skill_description(REPO_ROOT / "templates" / "skills" / sid / "SKILL.md")
            assert purpose, f"installed ability {sid} has no description to deliver"
            for root in roots:
                examined += 1
                rows = ability_rows((root / f"{stem}.md").read_text(encoding="utf-8"), installed).get(sid, [])
                if not any(purpose[:60] in row for row in rows):
                    bad.append((root.parent.name, stem, sid))
    assert examined > 0
    assert not bad, f"{len(bad)}/{examined} (agent, ability, root) rows lack the purpose text: {bad[:5]}"


def _real_conditional_grants() -> list[tuple[str, dict]]:
    """(template stem, entry) for every conditional grant in the real templates
    (derived by parsing; entries normalised to dicts)."""
    out = []
    for stem, entries in sorted(real_declarations().items()):
        for e in entries:
            e = e if isinstance(e, dict) else {"skill_id": e}
            if e.get("mode") == "conditional":
                out.append((stem, e))
    return out


def test_every_real_conditional_grant_carries_a_non_empty_condition():
    # covers: AR-300a-2
    # angle: criterion
    """AR-300a-2 (real tree, rule-based): every grant whose mode is ``conditional``
    in the real templates carries a non-empty ``condition`` string. Population
    derived from the templates; zero conditional grants fails. RED today: none
    carries one. The approved wording lives in the data, not here."""
    grants = _real_conditional_grants()
    assert grants, "0 conditional grants examined: an empty population is not a pass"
    bare = [(s, e["skill_id"]) for s, e in grants if not str(e.get("condition") or "").strip()]
    assert not bare, f"{len(bare)}/{len(grants)} conditional grants have no condition: {bare[:5]}"


@pytest.mark.shared_layout_reader
def test_every_real_conditional_grants_condition_is_in_the_compiled_section_of_both_roots(shared_reference_layout):
    # covers: AR-300a-2
    # angle: deployed
    """AR-300a-2 (real tree, rule-based): for every conditional grant, the
    condition declared on the template appears on that ability's row of the
    COMPILED prompt, in every platform root. RED today: no condition is declared
    (and so none is delivered)."""
    from _ar_300ad_support import REPO_ROOT as root_, installed_skill_ids as inst_
    installed = inst_(root_)
    roots = layout_roots(shared_reference_layout)
    grants = _real_conditional_grants()
    assert len(roots) >= 2 and grants
    missing, examined = [], 0
    for stem, entry in grants:
        cond = str(entry.get("condition") or "").strip()
        for root in roots:
            examined += 1
            rows = ability_rows((root / f"{stem}.md").read_text(encoding="utf-8"), installed).get(entry["skill_id"], [])
            if not cond or not any(" ".join(cond.replace("|", "\\|").split()) in r for r in rows):
                missing.append((root.parent.name, stem, entry["skill_id"]))
    assert examined == len(grants) * len(roots)
    assert not missing, f"{len(missing)}/{examined} (grant, root) pairs lack the condition in the compiled row: {missing[:5]}"


@pytest.mark.shared_layout_reader
def test_no_compiled_prompt_says_a_conditional_grant_applies_without_saying_when(shared_reference_layout):
    # covers: AR-300a-2
    # angle: deployed
    """AR-300a-2 (compiled-only rule): in every compiled prompt of every root, a
    row whose Mode cell says ``conditional`` also says WHEN (text after
    ``conditional:``). Read from compiled bytes alone. RED today: the Mode cell is
    the bare word."""
    import re
    installed = installed_skill_ids(REPO_ROOT)
    roots = layout_roots(shared_reference_layout)
    seen, bare = 0, []
    for root in roots:
        for prompt in agent_prompts(root):
            for sid, rows in ability_rows(prompt.read_text(encoding="utf-8"), installed).items():
                for row in rows:
                    cells = [c.strip() for c in re.split(r"(?<!\\)\|", row)]
                    if len(cells) > 3 and cells[2].lower().startswith("conditional"):
                        seen += 1
                        if not re.match(r"(?i)conditional:\s*\S", cells[2]):
                            bare.append((root.parent.name, prompt.stem, sid))
    assert seen > 0, "no conditional row examined in any compiled prompt"
    assert not bare, f"{len(bare)}/{seen} conditional rows say nothing about when: {bare[:5]}"


def test_onboard_declares_no_webapp_testing_grant():
    # covers: AR-300a-2
    # angle: criterion
    """AR-300a-2 (approved decision 4): the onboard template declares no
    ``webapp-testing`` grant. Control: onboard is a real template that still
    parses with its other frontmatter."""
    from _ar_300ad_support import TEMPLATES_AGENTS, declared_ids, template_frontmatter
    fm = template_frontmatter(TEMPLATES_AGENTS / "onboard.md")
    assert fm.get("name") == "onboard"
    assert "webapp-testing" not in declared_ids(fm)


def test_product_owner_and_business_analyst_declare_ac_tree_split():
    # covers: AR-300a-2
    # angle: criterion
    """AR-300a-2 (approved decision 1): product-owner and business-analyst each
    declare ``ac-tree-split`` as a CONDITIONAL grant with a non-empty condition.
    Only these two facts are asserted; the rest of their grant is derived."""
    from _ar_300ad_support import TEMPLATES_AGENTS, template_frontmatter
    for stem in ("product-owner", "business-analyst"):
        entries = {(e if isinstance(e, dict) else {"skill_id": e})["skill_id"]:
                   (e if isinstance(e, dict) else {"skill_id": e})
                   for e in template_frontmatter(TEMPLATES_AGENTS / f"{stem}.md").get("skills") or []}
        assert "ac-tree-split" in entries, f"{stem} does not declare ac-tree-split"
        assert entries["ac-tree-split"].get("mode") == "conditional"
        assert str(entries["ac-tree-split"].get("condition") or "").strip()


def test_counts_of_granted_agents_and_conditional_grants_are_stated(tmp_path):
    # covers: AR-300a-2
    # angle: boundary
    """AR-300a-2 (it_requirements): the run states how many granted agents it
    examined and how many conditional grants it found, so a run that recognised
    no conditional grants is distinguishable from one where every condition was
    delivered. 2 granted agents / 3 conditional grants here; a tree with none
    reports 0 conditional grants (control)."""
    templates = {
        "zz-one": (agent_fm("zz-one", GRANT), "# Agent\n"),
        "zz-two": (agent_fm("zz-two", [{"skill_id": "zz-alpha", "mode": "always"},
                                       {"skill_id": "zz-beta", "mode": "conditional", "condition": COND_BETA}]),
                   "# Agent\n"),
        "zz-plain": (agent_fm("zz-plain"), "# Agent\n"),
    }
    roots = write_compiled_tree(tmp_path / "a", templates, _skills_root(tmp_path / "a"))
    declarations = {s: fm["skills"] for s, (fm, _b) in templates.items() if "skills" in fm}
    verdict = verdict_for(declarations, roots, expected=len(templates) * len(roots), known=set(SKILLS))
    assert verdict["granted_count"] == 2
    assert verdict["conditional_grant_count"] == 3

    always_only = {"zz-solo": (agent_fm("zz-solo", [{"skill_id": "zz-alpha", "mode": "always"}]), "# Agent\n")}
    roots_b = write_compiled_tree(tmp_path / "b", always_only, _skills_root(tmp_path / "b"))
    decl_b = {"zz-solo": always_only["zz-solo"][0]["skills"]}
    verdict_b = verdict_for(decl_b, roots_b, expected=len(roots_b), known=set(SKILLS))
    assert verdict_b["granted_count"] == 1
    assert verdict_b["conditional_grant_count"] == 0
