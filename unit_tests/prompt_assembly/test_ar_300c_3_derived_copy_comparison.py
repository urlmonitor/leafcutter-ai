"""AR-300c-3 -- a central registry record that disagrees with the agent's own
declaration is reported (declaration wins; build refuses per ADR-050).

Contract assumed: ``scripts/agent_ability_verdict.verify_abilities`` (see
_ar_300c_support.py). The unit tests call it directly; the seam and build tests
exercise the real producer (migration CLI) and the real build.py.

RED BASELINE: scripts/agent_ability_verdict.py and the migration tool do not
exist (ModuleNotFoundError == absence red for the unit cases); the build test
fails by AssertionError because the build neither finds a declaration nor
refuses on disagreement today; the compiled-prompt test fails because the
declaration is never delivered.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300c_support import (  # noqa: E402
    GRANT_KEY,
    REPO_ROOT,
    compile_template,
    copy_package_slice,
    declared_entries,
    installed_skill_ids,
    make_skills,
    migrate_or_fail,
    named_abilities,
    registry_agents,
    template_frontmatter,
    template_stem,
    write_template,
)

_COMPARE_KINDS = {"divergent", "declaration-only", "record-only"}


def _verify(declarations, agents, tmp_path, skills=("signoff", "doc-enforcer", "route-knowledge")):
    from agent_ability_verdict import verify_abilities  # noqa: PLC0415

    packaged = make_skills(tmp_path / "packaged_skills", list(skills))
    return verify_abilities(declarations, agents, packaged_skills_root=packaged,
                            project_root=tmp_path / "project")


def _rec(agent_id, entries):
    return {"id": agent_id,
            "skills_used": [e["skill_id"] for e in entries],
            "skills_invoked": [dict(e) for e in entries]}


_A = {"skill_id": "signoff", "mode": "always"}
_B = {"skill_id": "doc-enforcer", "mode": "conditional", "condition": "c"}
_C = {"skill_id": "route-knowledge", "mode": "always"}


@pytest.mark.shared_layout_mutator
def test_hand_edited_central_record_is_reported_with_both_ability_sets(shared_reference_layout):
    # covers: AR-300c-3
    # angle: criterion
    """AR-300c-3: hand-edit one agent's registry record (inputs otherwise
    correct), rebuild the private copy with the real build.py: the build
    refuses (non-zero) and names the agent, the declaration's abilities and the
    record's abilities. Red today: build exits 0 / nothing declared."""
    layout = shared_reference_layout
    installed = installed_skill_ids(layout)
    victim = None
    for tpl in sorted((layout / "templates" / "agents").glob("*.md")):
        if tpl.name.startswith("_"):
            continue
        entries = declared_entries(template_frontmatter(tpl))
        if entries:
            victim = (tpl.stem, {e["skill_id"] for e in entries})
            break
    assert victim, "0 templates declare abilities -- nothing to disagree with"
    agent_id_stem, declared = victim
    other = sorted(installed - declared)[0]

    reg_path = layout / "config" / "agent_registry.json"
    data = json.loads(reg_path.read_text(encoding="utf-8"))
    for a in data["agents"]:
        if template_stem(a) == agent_id_stem:
            agent_id = a["id"]
            a["skills_used"] = [other]
            a["skills_invoked"] = [{"skill_id": other, "mode": "always"}]
    reg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(layout / "scripts" / "build.py"), "--target-dir", str(layout)],
        cwd=str(layout), capture_output=True, text=True, timeout=300, check=False,
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, "build accepted a hand-edited central record"
    assert agent_id in out
    assert other in out
    assert all(d in out for d in declared)


def test_compiled_prompt_still_names_the_declarations_abilities_after_a_hand_edit(tmp_path):
    # covers: AR-300c-3
    # angle: deployed
    """AR-300c-3: the compiled prompt names the declaration's abilities whatever
    the central record says (asserted on the compiled text, not on which
    variable is read). Red today: the declaration is never delivered."""
    reg_path = tmp_path / "agent_registry.json"
    fm = {"name": "zz-fixture", "description": "d", "model": "sonnet", "tools": "Read",
          GRANT_KEY: [_A, _B]}
    tpl = write_template(tmp_path / "zz-fixture.md", fm)
    installed = installed_skill_ids(REPO_ROOT)
    agreeing = [_rec("zz-fixture", [_A, _B])]
    hand_edited = [_rec("zz-fixture", [_C])]
    out_ok = compile_template(tpl, agreeing, reg_path)
    out_edit = compile_template(tpl, hand_edited, reg_path)
    assert named_abilities(out_edit, installed) == {"signoff", "doc-enforcer"}
    assert out_ok == out_edit


def test_agent_present_on_only_one_side_is_reported_as_a_disagreement(tmp_path):
    # covers: AR-300c-3
    # angle: boundary
    """AR-300c-3: declaration without a central entry, and an entry without a
    declaration, are both disagreements (not gaps)."""
    verdict = _verify({"only-decl": [_A]}, [_rec("only-record", [_B])], tmp_path)
    kinds = {(f["agent"], f["kind"]) for f in verdict["findings"] if f["kind"] in _COMPARE_KINDS}
    assert kinds == {("only-decl", "declaration-only"), ("only-record", "record-only")}
    assert verdict["examined_count"] == 2


def test_agreeing_agent_is_not_reported(tmp_path):
    # covers: AR-300c-3
    # angle: failure
    """AR-300c-3 control: agreeing agents -- including ones holding no grant on
    either side -- produce no finding, yet are counted as examined. A
    disagreeing sibling proves the comparison runs at all."""
    agents = [_rec("agrees", [_A, _B]), {"id": "no-grant", "skills_used": [], "skills_invoked": []},
              _rec("drifts", [_C])]
    verdict = _verify({"agrees": [_A, _B], "drifts": [_A]}, agents, tmp_path)
    assert [f["agent"] for f in verdict["findings"] if f["kind"] in _COMPARE_KINDS] == ["drifts"]
    assert verdict["examined_count"] == 3


def test_comparison_reports_the_count_examined(tmp_path):
    # covers: AR-300c-3
    # angle: boundary
    """AR-300c-3: examined count is the union of both sides; an empty
    population fails (raises) rather than reporting no disagreements."""
    verdict = _verify({"a": [_A], "b": [_B]}, [_rec("b", [_B]), _rec("c", [_C])], tmp_path)
    assert verdict["examined_count"] == 3
    with pytest.raises(ValueError):
        _verify({}, [], tmp_path)


def test_formatting_difference_is_not_a_disagreement_and_mode_change_is(tmp_path):
    # covers: AR-300c-3
    # angle: boundary
    """AR-300c-3: reordering entries / dict keys is no finding; always ->
    conditional on one ability is a divergent finding naming that agent."""
    reordered = {"id": "x", "skills_used": ["doc-enforcer", "signoff"],
                 "skills_invoked": [{"mode": "conditional", "skill_id": "doc-enforcer", "condition": "c"},
                                    {"mode": "always", "skill_id": "signoff"}]}
    verdict = _verify({"x": [_A, _B]}, [reordered], tmp_path)
    assert [f for f in verdict["findings"] if f["kind"] in _COMPARE_KINDS] == []

    mode_changed = _rec("x", [{"skill_id": "signoff", "mode": "conditional", "condition": "c"}, _B])
    verdict2 = _verify({"x": [_A, _B]}, [mode_changed], tmp_path)
    kinds = [(f["agent"], f["kind"]) for f in verdict2["findings"] if f["kind"] in _COMPARE_KINDS]
    assert kinds == [("x", "divergent")]


def test_migrated_declarations_and_regenerated_registry_agree_on_day_one(tmp_path):
    # covers: AR-300c-3
    # angle: seam
    """AR-300c-3 seam: the REAL migration's output (producer) piped into the
    REAL verifier (consumer) yields zero comparison findings and an examined
    count covering the registry. Red today: neither module exists."""
    from agent_ability_verdict import verify_abilities  # noqa: PLC0415

    pkg = copy_package_slice(tmp_path / "pkg")
    migrate_or_fail(pkg)
    agents = registry_agents(pkg)
    declarations = {}
    for a in agents:
        if template_stem(a):
            fm = template_frontmatter(pkg / "templates" / "agents" / f"{template_stem(a)}.md")
            if GRANT_KEY in fm:
                declarations[a["id"]] = declared_entries(fm)
    assert declarations
    verdict = verify_abilities(declarations, agents, packaged_skills_root=pkg / "templates" / "skills",
                               project_root=tmp_path / "project")
    assert verdict["examined_count"] >= len(agents)
    assert [f for f in verdict["findings"] if f["kind"] in _COMPARE_KINDS] == []
    # descriptive_only entries were not declared, so the REAL tree resolves
    # cleanly: zero unresolved findings is the proof the real build will not refuse.
    unresolved = [f for f in verdict["findings"] if f["kind"] == "unresolved"]
    assert unresolved == [], unresolved
    assert verdict["resolved_count"] == verdict["abilities_examined"] > 0
    assert verdict["findings"] == [] and verdict["ok"] is True
