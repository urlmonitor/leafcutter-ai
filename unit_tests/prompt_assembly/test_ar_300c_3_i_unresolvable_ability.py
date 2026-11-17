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
    registry_agents,
    template_frontmatter,
    transform_or_fail,
    write_template,
)

_ALWAYS = "always"


def _decl(*ids):
    return [{"skill_id": i, "mode": _ALWAYS} for i in ids]


def _verify(declarations, agents, packaged, project, output_root=".leafcutter"):
    from agent_ability_verdict import verify_abilities  # noqa: PLC0415

    if not agents:  # agreeing central records, so only resolution can produce findings
        agents = [{"id": a, "skills_invoked": [dict(e) for e in ents]}
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
    registry = [{"id": "a1", "skills_invoked": [{"skill_id": "signoff", "mode": _ALWAYS}]}]
    verdict = _verify({"a1": _decl("signoff", "no-such-skill")}, registry, packaged, tmp_path / "proj")
    found = _unresolved(verdict)
    assert [(f["agent"], f["ability"]) for f in found] == [("a1", "no-such-skill")]
    assert verdict["ok"] is False


def test_report_distinguishes_not_packaged_from_not_project_local(tmp_path):
    # covers: AR-300c-3-i
    # angle: criterion
    """AR-300c-3-i, retargeted by AR-400d-1 (the any-grant project-local fallback is superseded):
    an UNMARKED grant is looked up in the packaged skills only, so its finding records that one
    lookup; a grant MARKED ``provided_by: project`` is looked up in the project's own area only
    (under the declared output root), and its informational finding records that path and the
    packaged one separately -- so the reader knows which surface to add to."""
    packaged = make_skills(tmp_path / "pk", ["signoff"])
    project = tmp_path / "proj"
    verdict = _verify({"a1": _decl("ghost")}, [], packaged, project)
    (finding,) = _unresolved(verdict)
    (looked,) = finding["looked_in"]
    assert looked["surface"] == "packaged" and looked["found"] is False
    assert str(packaged) in looked["path"]

    marked = _verify({"a1": [{"skill_id": "ghost", "mode": _ALWAYS, "provided_by": "project"}]}, [], packaged, project)
    assert _unresolved(marked) == []
    (absent,) = [f for f in marked["findings"] if f["kind"] == "project-ability-absent"]
    assert str(project / ".leafcutter" / "skills") in absent["project_path"]
    assert str(packaged) in absent["packaged_path"]


def test_project_local_ability_resolves_through_the_declared_output_root(tmp_path):
    # covers: AR-300c-3-i
    # angle: deployed
    """AR-300c-3-i, retargeted by AR-400d-1 to a MARKED grant (an unmarked grant no longer
    resolves project-locally): a project-supplied skill (``provided_by: project``) under a
    NON-default declared output root resolves while no ``.claude/skills`` exists anywhere
    (fresh-worktree shape); the same grant under a different root is not found there (an
    informational finding, never a refusal). Wrong version caught: hard-coded .claude/skills
    (or hard-coded .leafcutter)."""
    packaged = make_skills(tmp_path / "pk", ["signoff"])
    project = tmp_path / "proj"
    make_skills(project / "custom-out" / "skills", ["my-local-skill"])
    assert not (project / ".claude").exists()
    local = [{"skill_id": "my-local-skill", "mode": _ALWAYS, "provided_by": "project"}]
    ok = _verify({"a1": _decl("signoff") + local}, [], packaged, project, "custom-out")
    assert _unresolved(ok) == [] and ok["findings"] == [] and ok["ok"] is True

    wrong_root = _verify({"a1": local}, [], packaged, project, ".leafcutter")
    assert _unresolved(wrong_root) == []
    assert [(f["kind"], f["ability"]) for f in wrong_root["findings"]] == [("project-ability-absent", "my-local-skill")]


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
    """AR-300c-3-i control (retargeted by AR-400d-1: the project-local ability is a MARKED
    grant): a packaged and a project-supplied ability both resolve cleanly -> no finding, ok,
    resolved_count == 2 (so the clean result is not 'nothing was looked at')."""
    packaged = make_skills(tmp_path / "pk", ["signoff"])
    project = tmp_path / "proj"
    make_skills(project / ".leafcutter" / "skills", ["local-one"])
    marked = [{"skill_id": "local-one", "mode": _ALWAYS, "provided_by": "project"}]
    verdict = _verify({"a1": _decl("signoff"), "a2": marked}, [], packaged, project)
    assert verdict["findings"] == []
    assert verdict["resolved_count"] == 2
    assert verdict["ok"] is True


def test_unresolvable_id_without_descriptive_only_is_still_reported_unresolved(tmp_path):
    # covers: AR-300c-3-i
    # angle: failure
    """AR-300c-3-i stays strict: through the REAL transform hook, a planted
    declared grant that resolves to no installed skill is reported
    ``unresolved`` (and ONLY it -- a planted descriptive_only unresolvable id
    in the registry record is preserved by the hook, never declared, never
    reported). Wrong version caught: a verifier that exempts every
    unresolvable id, or only the two known descriptive ones by name."""
    from agent_ability_verdict import verify_abilities  # noqa: PLC0415

    pkg = copy_package_slice(tmp_path / "pkg")
    add_registry_agent(pkg, {
        "id": "zz-ghost", "template_path": "templates/agents/zz-ghost.md",
        "skills_invoked": [
            {"skill_id": "phantom-described", "mode": "conditional", "descriptive_only": True},
        ],
    })
    write_template(pkg / "templates" / "agents" / "zz-ghost.md",
                   {"name": "zz-ghost", "description": "d", "model": "sonnet", "tools": "Read",
                    GRANT_KEY: [{"skill_id": "signoff", "mode": "always"},
                                {"skill_id": "ghost-skill", "mode": "always"}]})
    transform_or_fail(pkg)
    record = {a["id"]: a for a in registry_agents(pkg)}["zz-ghost"]
    assert {e["skill_id"] for e in record["skills_invoked"]} == {"signoff", "ghost-skill", "phantom-described"}

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
