"""AR-300c-3-i -- a declared ability that resolves to no installed skill is
reported naming agent, ability, and WHERE it was looked (packaged vs
project-local), resolved against the DECLARATION (never the registry fields),
with the project-local half reached through the declared output root.

Contract: ``scripts/agent_ability_verdict.verify_abilities`` (see
_ar_300c_support.py). RED BASELINE: the module does not exist
(ModuleNotFoundError == absence red; there is no pre-existing behaviour to
reach, so an assertion-shaped red is not available for these pure-unit cases).
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300c_support import (  # noqa: E402
    GRANT_KEY,
    add_registry_agent,
    copy_package_slice,
    declared_entries,
    make_skills,
    migrate_or_fail,
    registry_agents,
    template_frontmatter,
    write_template,
)

_ALWAYS = "always"


def _decl(*ids):
    return [{"skill_id": i, "mode": _ALWAYS} for i in ids]


def _verify(declarations, agents, packaged, project, output_root=".leafcutter"):
    from agent_ability_verdict import verify_abilities  # noqa: PLC0415

    if not agents:  # agreeing central records, so only resolution can produce findings
        agents = [{"id": a, "skills_used": [e["skill_id"] for e in ents],
                   "skills_invoked": [dict(e) for e in ents]}
                  for a, ents in declarations.items() if ents]
    return verify_abilities(declarations, agents, packaged_skills_root=packaged,
                            project_root=project, output_root_name=output_root)


def _unresolved(verdict):
    return [f for f in verdict["findings"] if f["kind"] == "unresolved"]


def test_unresolvable_ability_is_reported_naming_agent_and_ability(tmp_path):
    # covers: AR-300c-3-i
    # angle: criterion
    """AR-300c-3-i: unresolvable declared ability -> finding naming agent and
    ability; verdict not ok. The registry lists ONLY a resolvable skill, so an
    implementation reading the registry field would miss it (discrimination)."""
    packaged = make_skills(tmp_path / "pk", ["signoff"])
    registry = [{"id": "a1", "skills_used": ["signoff"],
                 "skills_invoked": [{"skill_id": "signoff", "mode": _ALWAYS}]}]
    verdict = _verify({"a1": _decl("signoff", "no-such-skill")}, registry, packaged, tmp_path / "proj")
    found = _unresolved(verdict)
    assert [(f["agent"], f["ability"]) for f in found] == [("a1", "no-such-skill")]
    assert verdict["ok"] is False


def test_report_distinguishes_not_packaged_from_not_project_local(tmp_path):
    # covers: AR-300c-3-i
    # angle: criterion
    """AR-300c-3-i: the finding records BOTH lookups separately, each with its
    own path (packaged under the package skills root; project-local under the
    declared output root), so the reader knows which surface to add to."""
    packaged = make_skills(tmp_path / "pk", ["signoff"])
    project = tmp_path / "proj"
    verdict = _verify({"a1": _decl("ghost")}, [], packaged, project)
    (finding,) = _unresolved(verdict)
    by_surface = {e["surface"]: e for e in finding["looked_in"]}
    assert set(by_surface) == {"packaged", "project_local"}
    assert str(packaged) in by_surface["packaged"]["path"]
    assert str(project / ".leafcutter" / "skills") in by_surface["project_local"]["path"]
    assert by_surface["packaged"]["found"] is False and by_surface["project_local"]["found"] is False


def test_project_local_ability_resolves_through_the_declared_output_root(tmp_path):
    # covers: AR-300c-3-i
    # angle: deployed
    """AR-300c-3-i: a project-local skill under a NON-default declared output
    root resolves while no ``.claude/skills`` exists anywhere (fresh-worktree
    shape); the same skill under a different root does not. Wrong version
    caught: hard-coded .claude/skills (or hard-coded .leafcutter)."""
    packaged = make_skills(tmp_path / "pk", ["signoff"])
    project = tmp_path / "proj"
    make_skills(project / "custom-out" / "skills", ["my-local-skill"])
    assert not (project / ".claude").exists()
    ok = _verify({"a1": _decl("signoff", "my-local-skill")}, [], packaged, project, "custom-out")
    assert _unresolved(ok) == [] and ok["ok"] is True

    wrong_root = _verify({"a1": _decl("my-local-skill")}, [], packaged, project, ".leafcutter")
    assert [f["ability"] for f in _unresolved(wrong_root)] == ["my-local-skill"]


def test_every_declared_ability_is_resolved_and_the_count_reported(tmp_path):
    # covers: AR-300c-3-i
    # angle: boundary
    """AR-300c-3-i: resolved_count counts ABILITIES across every agent (exactly
    4 here, 3 resolvable + 1 not); an empty ability population raises."""
    packaged = make_skills(tmp_path / "pk", ["signoff", "doc-enforcer", "route-knowledge"])
    decls = {"a1": _decl("signoff", "doc-enforcer"), "a2": _decl("route-knowledge", "ghost")}
    verdict = _verify(decls, [], packaged, tmp_path / "proj")
    assert verdict["abilities_examined"] == 4
    assert verdict["resolved_count"] == 3
    with pytest.raises(ValueError):
        _verify({"a1": []}, [], packaged, tmp_path / "proj")


def test_resolvable_ability_is_not_reported(tmp_path):
    # covers: AR-300c-3-i
    # angle: failure
    """AR-300c-3-i control: a packaged and a project-local ability both resolve
    cleanly -> no finding, ok, resolved_count == 2 (so the clean result is not
    'nothing was looked at')."""
    packaged = make_skills(tmp_path / "pk", ["signoff"])
    project = tmp_path / "proj"
    make_skills(project / ".leafcutter" / "skills", ["local-one"])
    verdict = _verify({"a1": _decl("signoff"), "a2": _decl("local-one")}, [], packaged, project)
    assert verdict["findings"] == []
    assert verdict["resolved_count"] == 2
    assert verdict["ok"] is True


def test_unresolvable_id_without_descriptive_only_is_still_reported_unresolved(tmp_path):
    # covers: AR-300c-3-i
    # angle: failure
    """AR-300c-3-i stays strict: through the REAL migration, a planted
    registry grant that resolves to no installed skill and is NOT
    descriptive_only is declared and reported ``unresolved`` (and ONLY it --
    a planted descriptive_only unresolvable id is left out, never reported).
    Wrong version caught: a verifier/migration that exempts every unresolvable
    id, or only the two known descriptive ones by name."""
    from agent_ability_verdict import verify_abilities  # noqa: PLC0415

    pkg = copy_package_slice(tmp_path / "pkg")
    add_registry_agent(pkg, {
        "id": "zz-ghost", "template_path": "templates/agents/zz-ghost.md",
        "skills_used": [],
        "skills_invoked": [
            {"skill_id": "signoff", "mode": "always"},
            {"skill_id": "ghost-skill", "mode": "always"},
            {"skill_id": "phantom-described", "mode": "conditional", "descriptive_only": True},
        ],
    })
    write_template(pkg / "templates" / "agents" / "zz-ghost.md",
                   {"name": "zz-ghost", "description": "d", "model": "sonnet", "tools": "Read"})
    migrate_or_fail(pkg)

    agents = registry_agents(pkg)
    declarations = {}
    for a in agents:
        stem = (a.get("template_path") or "").rsplit("/", 1)[-1][:-3]
        if stem:
            fm = template_frontmatter(pkg / "templates" / "agents" / f"{stem}.md")
            if GRANT_KEY in fm:
                declarations[a["id"]] = declared_entries(fm)
    assert "phantom-described" not in {e["skill_id"] for e in declarations["zz-ghost"]}
    verdict = verify_abilities(declarations, agents, packaged_skills_root=pkg / "templates" / "skills",
                               project_root=tmp_path / "project")
    found = [(f["agent"], f["ability"]) for f in verdict["findings"] if f["kind"] == "unresolved"]
    assert found == [("zz-ghost", "ghost-skill")]
    assert verdict["ok"] is False
