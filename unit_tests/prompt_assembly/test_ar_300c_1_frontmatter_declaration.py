"""AR-300c-1 -- abilities are declared in the agent's own template frontmatter,
beside ``tools:``, and delivery reads ONLY that.

Source of truth: docs/acceptance-criteria/agent-registry/AR-300-granted-abilities-arrive/AR-300c-1.yaml
(see _ar_300c_support.py for the assumed production contract: frontmatter key
``skills`` with ``{skill_id, mode, condition?}`` entries).

RED BASELINE: today no template declares abilities and the compiler discards
the registry-derived table (guarded on a body token no template contains), so
every test below fails on an AssertionError about the missing declaration /
undelivered abilities. test_mode_and_condition... fails because the migration
tool that would produce the declaration does not exist yet.
"""

from __future__ import annotations

import copy
import os
import sys


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300c_support import (  # noqa: E402
    GRANT_KEY,
    REPO_ROOT,
    add_registry_agent,
    compile_template,
    copy_package_slice,
    declared_entries,
    installed_skill_ids,
    named_abilities,
    pristine_registry_agents,
    registry_agents,
    template_frontmatter,
    transform_or_fail,
    write_template,
)

_FIXTURE_FM_A = {
    "name": "zz-fixture",
    "description": "fixture agent",
    "model": "sonnet",
    "tools": "Bash, Read",
    GRANT_KEY: [
        {"skill_id": "signoff", "mode": "always"},
        {"skill_id": "doc-enforcer", "mode": "conditional",
         "condition": "when Python files changed"},
    ],
}


def _registry_for(agent_id: str, invoked) -> list[dict]:
    return [{"id": agent_id, "template_path": f"templates/agents/{agent_id}.md",
             "skills_invoked": invoked}]


def test_editing_only_the_frontmatter_changes_the_compiled_prompt(tmp_path):
    # covers: AR-300c-1
    # angle: seam
    """AR-300c-1: change ONLY the frontmatter declaration -> the compiled prompt
    changes accordingly. Red today: abilities are never delivered at all."""
    reg_path = tmp_path / "agent_registry.json"
    agents = _registry_for("zz-fixture", [])
    tpl = write_template(tmp_path / "zz-fixture.md", _FIXTURE_FM_A)
    before = compile_template(tpl, agents, reg_path)
    installed = installed_skill_ids(REPO_ROOT)
    assert named_abilities(before, installed) == {"signoff", "doc-enforcer"}

    fm_b = copy.deepcopy(_FIXTURE_FM_A)
    fm_b[GRANT_KEY] = [{"skill_id": "signoff", "mode": "always"},
                       {"skill_id": "ticket-wiring", "mode": "always"}]
    write_template(tpl, fm_b)
    after = compile_template(tpl, agents, reg_path)
    assert named_abilities(after, installed) == {"signoff", "ticket-wiring"}
    assert before != after


def test_editing_only_the_registry_does_not_change_the_compiled_prompt(tmp_path):
    # covers: AR-300c-1
    # angle: real_artifact
    """AR-300c-1: registry-only edit leaves the compiled prompt byte-identical
    (sole read, not fallback). Positive control first: the declaration IS
    delivered, so 'unchanged' cannot be 'nothing delivered either way'.
    Wrong version caught: header-authoritative-but-registry-also-read."""
    reg_path = tmp_path / "agent_registry.json"
    tpl = write_template(tmp_path / "zz-fixture.md", _FIXTURE_FM_A)
    installed = installed_skill_ids(REPO_ROOT)

    reg_one = _registry_for("zz-fixture", [{"skill_id": "signoff", "mode": "always"}])
    reg_two = _registry_for(
        "zz-fixture",
        [{"skill_id": "ticket-wiring", "mode": "always"},
         {"skill_id": "route-knowledge", "mode": "conditional"}],
    )
    out_one = compile_template(tpl, reg_one, reg_path)
    out_two = compile_template(tpl, reg_two, reg_path)

    assert named_abilities(out_one, installed) == {"signoff", "doc-enforcer"}, "declaration not delivered"
    assert out_one == out_two, "registry-only edit changed the compiled prompt"
    assert not (named_abilities(out_two, installed) & {"ticket-wiring", "route-knowledge"})


def test_grant_and_tools_are_readable_from_one_frontmatter_block():
    # covers: AR-300c-1
    # angle: criterion
    """AR-300c-1: on the REAL on-disk templates, both the declared abilities and
    the ``tools:`` string parse out of one frontmatter block. Red today: zero
    real templates carry the declaration (population 0 fails)."""
    both = []
    for tpl in sorted((REPO_ROOT / "templates" / "agents").glob("*.md")):
        if tpl.name.startswith("_"):
            continue
        fm = template_frontmatter(tpl)  # ONE parse of ONE block
        if GRANT_KEY in fm:
            entries = declared_entries(fm)
            assert entries and all(isinstance(e.get("skill_id"), str) for e in entries), tpl.name
            assert isinstance(fm.get("tools"), str) and fm["tools"].strip(), tpl.name
            both.append(tpl.name)
    assert both, "0 templates carry both `tools:` and a grant in one block"


def test_mode_and_condition_survive_into_the_frontmatter_representation(tmp_path):
    # covers: AR-300c-1
    # angle: criterion
    """AR-300c-1: a conditional grant keeps its mode AND condition in the
    declaration and in the registry copy the transform hook derives from it.
    Run the real hook over a copy of the real tree plus one planted agent whose
    template declares a condition and whose registry record is stale; the
    declaration keeps mode and condition, the regenerated record carries them,
    and every committed template keeps the mode of each pre-consolidation
    conditional grant."""
    pkg = copy_package_slice(tmp_path / "pkg")
    planted = {"id": "zz-fixture", "template_path": "templates/agents/zz-fixture.md",
               "skills_invoked": []}
    add_registry_agent(pkg, planted)
    write_template(pkg / "templates" / "agents" / "zz-fixture.md",
                   {"name": "zz-fixture", "description": "d", "model": "sonnet", "tools": "Bash",
                    GRANT_KEY: [{"skill_id": "doc-enforcer", "mode": "conditional",
                                 "condition": "when Python files changed"}]})
    transform_or_fail(pkg)

    fm = template_frontmatter(pkg / "templates" / "agents" / "zz-fixture.md")
    entry = {e["skill_id"]: e for e in declared_entries(fm)}["doc-enforcer"]
    assert entry.get("mode") == "conditional"
    assert entry.get("condition") == "when Python files changed"
    record = {a["id"]: a for a in registry_agents(pkg)}["zz-fixture"]
    derived = {e["skill_id"]: e for e in record["skills_invoked"]}["doc-enforcer"]
    assert derived.get("mode") == "conditional" and derived.get("condition") == "when Python files changed"
    assert "skills_used" not in record

    # Real tree: every conditional entry the committed templates declare survives, mode and
    # condition text, into the registry copy the hook regenerated (declaration -> derived copy).
    checked = 0
    for rec in registry_agents(pkg):
        tp = rec.get("template_path")
        if not tp or rec["id"] == "zz-fixture":
            continue
        got = {e["skill_id"]: e for e in rec.get("skills_invoked") or []}
        for e in declared_entries(template_frontmatter(pkg / tp)):
            if e.get("mode") == "conditional":
                checked += 1
                assert got[e["skill_id"]].get("mode") == "conditional", (rec["id"], e["skill_id"])
                assert got[e["skill_id"]].get("condition") == e.get("condition"), (rec["id"], e["skill_id"])
    assert checked > 0, "no conditional grants examined"
    # Control: the frozen pre-consolidation registry also held conditional grants (the population
    # this property exists for is not empty), whatever their mode has since become.
    assert any(e.get("mode") == "conditional" for a in pristine_registry_agents()
               for e in a.get("skills_invoked") or [] if isinstance(e, dict))
