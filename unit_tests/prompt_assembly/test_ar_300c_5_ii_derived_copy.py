"""AR-300c-5-ii -- a central sub-agent record that disagrees with the agent's own
declaration is REPORTED, the declaration wins, the build completes and never writes the
package source; the copy is regenerated at commit time (that half: see
test_ar_300c_3_ii_registry_transform.py, widened for spawn lists).

Source of truth: .../AR-300c-5-ii.yaml and user decision 5 (report, never refuse).
Contract: _ar_300e_support.py items 2 and 4. Findings are read from the build's own
ability guard (``refuse_on_ability_findings``) and from the verdict it is built on.

RED BASELINE (slice 5): the guard compares only skills, so a disagreeing spawn record
is silent (assertion red); ``verify_spawn_allowlists`` does not exist (absence red).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300e_support import (  # noqa: E402
    BODY,
    MACRO,
    build_in,
    drop_registry_records,
    named_sub_agents,
    run_gate,
    sfm,
    snapshot_tree,
    spawn_package,
    spawn_verdict,
    with_skilled,
    workers,
)


def _registry(pkg: Path) -> list[dict]:
    return json.loads((pkg / "config" / "agent_registry.json").read_text("utf-8"))["agents"]


def _orch_pkg(tmp_path: Path, registry_spawn: dict | None = None, **extra) -> Path:
    templates = with_skilled({"zz-orch": (sfm("zz-orch", ["zz-a"]), BODY), **workers("zz-a", "zz-b", "zz-c"), **extra})
    return spawn_package(tmp_path / "src", templates, registry_spawn=registry_spawn)


def test_hand_edited_registry_spawn_allowlist_is_reported_and_build_completes(tmp_path, capsys):
    # covers: AR-300c-5-ii
    # angle: criterion
    """AR-300c-5-ii: an agent whose registry ``spawn_allowlist`` differs from its declaration
    is reported -- naming the agent, the sub-agents its declaration permits and the ones the
    record names -- and the build still completes (exit 0 on that account). Control: while
    the record AGREES nothing is said about the agent (so the report is caused by the edit)."""
    pkg = _orch_pkg(tmp_path)
    rc, quiet = run_gate(pkg, capsys)
    assert rc == 0 and "zz-orch" not in quiet, f"control: an agreeing record was reported: {quiet!r}"
    edited = _orch_pkg(tmp_path / "edited", registry_spawn={"zz-orch": ["zz-b"]})
    rc, said = run_gate(edited, capsys)
    assert rc == 0, f"the build stopped (exit {rc}) over a stale registry copy; it must report and continue"
    for token in ("zz-orch", "zz-a", "zz-b"):
        assert token in said, f"report lacks {token!r}: {said!r}"


def test_compiled_prompt_names_the_declaration_after_a_registry_hand_edit(tmp_path, monkeypatch):
    # covers: AR-300c-5-ii
    # angle: deployed
    """AR-300c-5-ii: after the registry hand edit, the compiled sub-agent section in BOTH
    platform roots still names the DECLARATION's sub-agents, so the edit changes nothing the
    agent sees (and never names the record's sub-agent)."""
    pkg = _orch_pkg(tmp_path, registry_spawn={"zz-orch": ["zz-b"]})
    known = {"zz-orch", "zz-a", "zz-b", "zz-c", "zz-skilled"}
    roots = build_in(pkg, tmp_path / "out", monkeypatch)
    assert len(roots) == 2
    for root in roots:
        assert named_sub_agents((root / "zz-orch.md").read_text(encoding="utf-8"), known) == {"zz-a"}


def test_one_sided_agent_is_a_disagreement_not_a_gap_in_the_comparison(tmp_path, capsys):
    # covers: AR-300c-5-ii
    # angle: boundary
    """AR-300c-5-ii: an agent present on ONE side only is reported -- one with a declaration
    and no registry record at all, and one with a registry permission and no declaration --
    while an agreeing agent is not (control row)."""
    extra = {"zz-decl": (sfm("zz-decl", ["zz-a"]), BODY), "zz-rec": (sfm("zz-rec"), BODY),
             "zz-ok": (sfm("zz-ok", ["zz-b"]), BODY)}
    pkg = _orch_pkg(tmp_path, registry_spawn={"zz-rec": ["zz-a"]}, **extra)
    drop_registry_records(pkg, "zz-decl")
    rc, said = run_gate(pkg, capsys)
    assert rc == 0
    assert "zz-decl" in said and "zz-rec" in said, f"one-sided agents not reported: {said!r}"
    assert "zz-ok" not in said


def test_verdict_states_counts_and_a_zero_population_fails(tmp_path):
    # covers: AR-300c-5-ii
    # angle: boundary
    """AR-300c-5-ii: the comparison covers every agent holding a declaration OR a central
    entry, with the count examined stated (exactly 4 here: zz-orch and zz-ok agree, zz-decl
    is declaration-only, zz-rec is record-only), the one-sided kinds are named, and a
    population of zero raises instead of reading clean."""
    extra = {"zz-decl": (sfm("zz-decl", ["zz-a"]), BODY), "zz-rec": (sfm("zz-rec"), BODY),
             "zz-ok": (sfm("zz-ok", ["zz-b"]), BODY)}
    pkg = _orch_pkg(tmp_path, registry_spawn={"zz-rec": ["zz-a"]}, **extra)
    drop_registry_records(pkg, "zz-decl")
    declarations = {"zz-orch": ["zz-a"], "zz-decl": ["zz-a"], "zz-ok": ["zz-b"]}
    verdict = spawn_verdict(declarations, _registry(pkg), pkg)
    assert verdict["examined_count"] == 4, verdict
    kinds = {f["agent"]: f["kind"] for f in verdict["findings"] if f.get("severity") == "report"}
    assert kinds == {"zz-decl": "declaration-only", "zz-rec": "record-only"}, kinds
    empty = spawn_package(tmp_path / "empty", with_skilled({}))
    with pytest.raises(ValueError):
        spawn_verdict({}, _registry(empty), empty)


def test_agreeing_agent_and_macro_entry_are_not_reported(tmp_path, capsys):
    # covers: AR-300c-5-ii
    # angle: discrimination
    """AR-300c-5-ii: an agent whose registry copy matches its declaration -- including a
    ticket-supervisor-like agent holding the macro on both sides, in a different list order
    -- produces no finding, while a disagreeing control row produces exactly one, and a
    registry that holds the macro's EXPANSION instead of the literal entry IS a disagreement.
    Checked through the build's own guard first, then on the verdict's fields. Wrong versions
    caught: the macro expanded on one side before comparing; list order treated as a
    disagreement."""
    templates = with_skilled({"zz-ts": (sfm("zz-ts", [MACRO, "zz-b"]), BODY),
                              "zz-ord": (sfm("zz-ord", ["zz-a", "zz-b"]), BODY),
                              "zz-bad": (sfm("zz-bad", ["zz-a"]), BODY), **workers("zz-a", "zz-b", "zz-c")})
    gated = spawn_package(tmp_path / "gated", templates, ticket_phase=("zz-a", "zz-c"),
                          registry_spawn={"zz-ts": ["zz-b", MACRO], "zz-ord": ["zz-b", "zz-a"], "zz-bad": ["zz-b"]})
    rc, said = run_gate(gated, capsys)
    assert rc == 0 and "zz-bad" in said, f"control: the disagreeing row was not reported: {said!r}"
    assert "zz-ts" not in said and "zz-ord" not in said, f"an agreeing agent was reported: {said!r}"
    pkg = _orch_pkg(tmp_path)
    phase = ["zz-a", "zz-c"]
    declarations = {"zz-ts": [MACRO, "zz-b"], "zz-ord": ["zz-a", "zz-b"], "zz-bad": ["zz-a"]}

    def registry(ts, ord_, bad):
        return [{"id": "zz-ts", "spawn_allowlist": ts, "is_ticket_phase": False},
                {"id": "zz-ord", "spawn_allowlist": ord_, "is_ticket_phase": False},
                {"id": "zz-bad", "spawn_allowlist": bad, "is_ticket_phase": False},
                {"id": "zz-a", "spawn_allowlist": [], "is_ticket_phase": True},
                {"id": "zz-c", "spawn_allowlist": [], "is_ticket_phase": True}]

    verdict = spawn_verdict(declarations, registry(["zz-b", MACRO], ["zz-b", "zz-a"], ["zz-b"]), pkg,
                            ticket_phase_ids=phase)
    report = [f for f in verdict["findings"] if f.get("severity") == "report"]
    assert [f["agent"] for f in report] == ["zz-bad"], report
    assert report[0]["kind"] == "divergent" and report[0]["field"] == "spawn_allowlist"
    assert report[0]["declared"] == ["zz-a"] and report[0]["recorded"] == ["zz-b"]
    expanded = spawn_verdict(declarations, registry(["zz-a", "zz-c", "zz-b"], ["zz-a", "zz-b"], ["zz-a"]), pkg,
                             ticket_phase_ids=phase)
    assert {f["agent"] for f in expanded["findings"] if f.get("severity") == "report"} == {"zz-ts"}


def test_build_never_writes_the_registry_source(tmp_path, monkeypatch, capsys):
    # covers: AR-300c-5-ii
    # angle: deployed
    """AR-300c-5-ii: a build over a tree with a disagreeing registry copy leaves
    config/agent_registry.json (and every template) byte-identical; regeneration happens
    only through the commit-time hook. Control: the disagreement WAS reported (red today:
    nothing is reported), so 'unchanged' is not 'the build never looked'."""
    pkg = _orch_pkg(tmp_path, registry_spawn={"zz-orch": ["zz-b"]})
    before = snapshot_tree(pkg)
    rc, said = run_gate(pkg, capsys)
    assert rc == 0 and "zz-orch" in said, f"control: the disagreement was not reported: {said!r}"
    build_in(pkg, tmp_path / "out", monkeypatch)
    assert snapshot_tree(pkg) == before, "the build wrote to the package source tree"
