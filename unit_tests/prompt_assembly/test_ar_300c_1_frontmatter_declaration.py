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

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300c_support import (  # noqa: E402
    GRANT_KEY,
    REPO_ROOT,
    add_registry_agent,
    compile_template,
    compiled_agent_roots,
    copy_package_slice,
    declared_entries,
    declared_ids,
    installed_skill_ids,
    migrate_or_fail,
    named_abilities,
    pristine_registry_agents,
    template_frontmatter,
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


def _registry_for(agent_id: str, used, invoked) -> list[dict]:
    return [{"id": agent_id, "template_path": f"templates/agents/{agent_id}.md",
             "skills_used": used, "skills_invoked": invoked}]


@pytest.mark.shared_layout_reader
def test_compiled_prompt_abilities_equal_the_frontmatter_declaration(shared_reference_layout):
    # covers: AR-300c-1
    # angle: deployed
    """AR-300c-1: abilities in each compiled prompt are exactly the template's
    frontmatter declaration, in EVERY platform root. Red today: no template
    declares a grant (population 0) and no compiled prompt carries a section."""
    layout = shared_reference_layout  # deployed target: compiled prompts only
    # The shared layout is built from this worktree's source, so the source
    # declarations (population) live under REPO_ROOT; evidence is the layout.
    installed = installed_skill_ids(REPO_ROOT)
    roots = compiled_agent_roots(layout)
    assert len(roots) >= 2, f"expected claude + gemini agent roots, found {roots}"
    src_agents = REPO_ROOT / "templates" / "agents"
    assert any(src_agents.glob("*.md")), "source templates not found"

    declaring = {}
    for tpl in sorted(src_agents.glob("*.md")):
        if tpl.name.startswith("_"):
            continue
        ids = declared_ids(template_frontmatter(tpl)) & installed
        if ids:
            declaring[tpl.name] = ids
    assert declaring, "0 templates declare abilities in frontmatter (examined 0) -- empty population fails"

    wrong = []
    for name, ids in declaring.items():
        for root in roots:
            compiled = (root / name).read_text(encoding="utf-8")
            got = named_abilities(compiled, installed)
            if got != ids:
                wrong.append((root.name, name, sorted(ids ^ got)))
    assert not wrong, f"{len(declaring)} declaring agents x {len(roots)} roots; mismatches: {wrong[:5]}"


def test_editing_only_the_frontmatter_changes_the_compiled_prompt(tmp_path):
    # covers: AR-300c-1
    # angle: seam
    """AR-300c-1: change ONLY the frontmatter declaration -> the compiled prompt
    changes accordingly. Red today: abilities are never delivered at all."""
    reg_path = tmp_path / "agent_registry.json"
    agents = _registry_for("zz-fixture", [], [])
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

    reg_one = _registry_for("zz-fixture", ["signoff"], [{"skill_id": "signoff", "mode": "always"}])
    reg_two = _registry_for(
        "zz-fixture", ["ticket-wiring", "route-knowledge"],
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
    declaration. Run the real migration over a copy of the real tree plus one
    planted agent whose registry record carries a condition; every registry
    conditional keeps mode, the planted one keeps its condition text.
    Red today: the migration tool does not exist."""
    pkg = copy_package_slice(tmp_path / "pkg")
    planted = {"id": "zz-fixture", "template_path": "templates/agents/zz-fixture.md",
               "skills_used": [],
               "skills_invoked": [{"skill_id": "doc-enforcer", "mode": "conditional",
                                   "condition": "when Python files changed"}]}
    add_registry_agent(pkg, planted)
    write_template(pkg / "templates" / "agents" / "zz-fixture.md",
                   {"name": "zz-fixture", "description": "d", "model": "sonnet", "tools": "Bash"})
    migrate_or_fail(pkg)

    fm = template_frontmatter(pkg / "templates" / "agents" / "zz-fixture.md")
    entry = {e["skill_id"]: e for e in declared_entries(fm)}["doc-enforcer"]
    assert entry.get("mode") == "conditional"
    assert entry.get("condition") == "when Python files changed"

    data = {"agents": pristine_registry_agents()}  # the migration's pre-consolidation input
    checked = 0
    for rec in data["agents"]:
        tp = rec.get("template_path")
        if not tp:
            continue
        mfm = template_frontmatter(pkg / tp)
        got = {e["skill_id"]: e for e in declared_entries(mfm)}
        for e in rec.get("skills_invoked") or []:
            if isinstance(e, dict) and e.get("mode") == "conditional" and not e.get("descriptive_only"):
                checked += 1
                assert got[e["skill_id"]].get("mode") == "conditional", (rec["id"], e["skill_id"])
    assert checked > 0, "no conditional grants examined"
