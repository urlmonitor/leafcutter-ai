"""AR-300c-5-iii -- a declared sub-agent with no DEPLOYABLE definition stops the build,
naming the agent, the sub-agent and where it was looked for; a registry row or a stale
compiled prompt never counts as the sub-agent existing.

Source of truth: .../AR-300c-5-iii.yaml and decisions 10 and 13 (architect-review-deep
and conflict-resolver-deep are REMOVED, not built). Contract: _ar_300e_support.py item 4;
the refusal is read from the build's own ability guard (``refuse_on_ability_findings``,
exit code 1 = build stops) and from the verdict it is built on.

RED BASELINE (slice 5): the guard resolves only skills, so a ghost sub-agent is silent
(assertion red); the verdict function is absent (absence red); the real tree still
carries both undeployable targets (assertion red).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300ad_support import layout_roots  # noqa: E402
from _ar_300e_support import (  # noqa: E402
    BODY,
    KEY,
    MACRO,
    REPO_ROOT,
    build_in,
    run_gate,
    sfm,
    spawn_accounts,
    spawn_package,
    spawn_verdict,
    stale_compiled,
    template_frontmatter,
    with_skilled,
    workers,
    write_template,
)

GHOST_ROW = {"id": "zz-ghost", "template_path": None, "role": "ghost role", "tier": "utility",
             "is_ticket_phase": False, "spawn_allowlist": [], "skills_used": [], "skills_invoked": []}


def _registry(pkg: Path) -> list[dict]:
    return json.loads((pkg / "config" / "agent_registry.json").read_text("utf-8"))["agents"]


def _ghost_pkg(tmp_path: Path, declared=("zz-ghost",), extra_rows=(), **kw) -> Path:
    templates = with_skilled({"zz-orch": (sfm("zz-orch", list(declared)), BODY), **workers("zz-real"), **kw})
    return spawn_package(tmp_path / "src", templates, extra_records=list(extra_rows))


def test_unresolvable_sub_agent_refuses_naming_agent_and_sub_agent(tmp_path, capsys):
    # covers: AR-300c-5-iii
    # angle: criterion
    """AR-300c-5-iii: a declared sub-agent with no packaged template and no project-local
    definition makes the build REFUSE (exit 1, not success), naming the declaring agent and
    the unresolvable sub-agent -- even though the registry holds a row for it and an earlier
    build left a compiled prompt. Control: once a template for it exists the same package
    builds (exit 0) and the sub-agent is not mentioned."""
    pkg = _ghost_pkg(tmp_path, extra_rows=[GHOST_ROW])
    stale_compiled(pkg.parent, "zz-ghost")
    rc, said = run_gate(pkg, capsys)
    assert rc == 1, f"build did not refuse (exit {rc}): {said!r}"
    assert "zz-orch" in said and "zz-ghost" in said, said
    write_template(pkg / "templates" / "agents" / "zz-ghost.md", sfm("zz-ghost", tools="Bash, Read"), BODY)
    rc, said = run_gate(pkg, capsys)
    assert rc == 0 and "zz-ghost" not in said, f"control failed (exit {rc}): {said!r}"


def test_report_distinguishes_not_packaged_from_not_project_local(tmp_path, capsys):
    # covers: AR-300c-5-iii
    # angle: criterion
    """AR-300c-5-iii: the finding says which lookups came back empty -- ``packaged`` (not
    shipped with the package) AND ``project_local`` (not among the project's own agents) --
    and the printed report names both surfaces so the reader knows what to add."""
    pkg = _ghost_pkg(tmp_path)
    rc, said = run_gate(pkg, capsys)
    assert rc == 1, f"build did not refuse (exit {rc}): {said!r}"
    lowered = said.lower()
    assert "package" in lowered and "project" in lowered, f"report does not distinguish the two lookups: {said!r}"
    verdict = spawn_verdict({"zz-orch": ["zz-ghost"]}, _registry(pkg), pkg)
    ghost = [f for f in verdict["findings"] if f.get("kind") == "unresolvable-sub-agent"]
    assert len(ghost) == 1 and ghost[0]["agent"] == "zz-orch" and ghost[0]["sub_agent"] == "zz-ghost"
    assert ghost[0]["severity"] == "refuse"
    assert sorted(ghost[0]["lookups_failed"]) == ["packaged", "project_local"]


def test_registry_row_and_stale_compiled_prompt_do_not_count_as_resolution(tmp_path, capsys):
    # covers: AR-300c-5-iii
    # angle: discrimination
    """AR-300c-5-iii: a sub-agent with a registry entry (template_path null) is still
    unresolvable; so is one whose only trace is a compiled prompt left in the output root's
    ``agents/`` by an earlier build; a sub-agent with a packaged template resolves and is not
    reported (control). Wrong versions caught: resolution consults the registry; resolution
    accepts a compiled prompt in <output_root>/agents/ as a definition."""
    pkg = _ghost_pkg(tmp_path, declared=("zz-ghost", "zz-stale", "zz-real"), extra_rows=[GHOST_ROW])
    stale_compiled(pkg.parent, "zz-stale")
    stale_compiled(pkg.parent, "zz-ghost")
    rc, said = run_gate(pkg, capsys)
    assert rc == 1 and "zz-ghost" in said and "zz-stale" in said, f"exit {rc}: {said!r}"
    declarations = {"zz-orch": ["zz-ghost", "zz-stale", "zz-real"]}
    verdict = spawn_verdict(declarations, _registry(pkg), pkg)
    unresolved = sorted(f["sub_agent"] for f in verdict["findings"] if f.get("kind") == "unresolvable-sub-agent")
    assert unresolved == ["zz-ghost", "zz-stale"], f"resolution accepted a registry row or a stale prompt: {unresolved}"


def test_empty_ticket_phase_macro_refuses_instead_of_delivering_empty(tmp_path, capsys, monkeypatch):
    # covers: AR-300c-5-iii
    # angle: boundary
    """AR-300c-5-iii: with NO agent marked ticket-phase, a declaration holding
    ``__ticket_phase_agents__`` produces a refusing finding naming the holder and the macro,
    and no empty sub-agent section (a heading followed by nothing) is compiled for it."""
    pkg = spawn_package(tmp_path / "src", with_skilled({"zz-holder": (sfm("zz-holder", [MACRO]), BODY),
                                                         **workers("zz-real")}), ticket_phase=())
    rc, said = run_gate(pkg, capsys)
    assert rc == 1 and "zz-holder" in said, f"empty macro did not refuse (exit {rc}): {said!r}"
    verdict = spawn_verdict({"zz-holder": [MACRO]}, _registry(pkg), pkg, ticket_phase_ids=[])
    hits = [f for f in verdict["findings"] if f.get("kind") == "unresolvable-sub-agent"]
    assert [(f["agent"], f["sub_agent"]) for f in hits] == [("zz-holder", MACRO)], hits
    known = {"zz-holder", "zz-real", "zz-skilled"}
    for root in build_in(pkg, tmp_path / "out", monkeypatch):
        assert spawn_accounts((root / "zz-holder.md").read_text(encoding="utf-8"), known) == []


def test_every_declared_sub_agent_resolved_with_count_and_resolvable_not_reported(tmp_path):
    # covers: AR-300c-5-iii
    # angle: failure
    """AR-300c-5-iii: every declared sub-agent of every agent is resolved and the counts are
    stated -- ``agents_examined`` and ``sub_agents_resolved`` (macro expanded, counted per
    agent) -- sub-agents that resolve produce NO finding, one ghost added makes exactly one
    finding without raising the resolved count, and a zero population raises."""
    pkg = _ghost_pkg(tmp_path, **workers("zz-a", "zz-b", "zz-c"))
    declarations = {"zz-one": ["zz-a", "zz-b"], "zz-two": [MACRO]}
    registry = [{"id": "zz-one", "spawn_allowlist": ["zz-a", "zz-b"], "is_ticket_phase": False},
                {"id": "zz-two", "spawn_allowlist": [MACRO], "is_ticket_phase": False}]
    clean = spawn_verdict(declarations, registry, pkg, ticket_phase_ids=["zz-a", "zz-c"])
    assert [f for f in clean["findings"] if f.get("severity") == "refuse"] == []
    assert (clean["agents_examined"], clean["sub_agents_resolved"]) == (2, 4), clean
    declarations["zz-one"].append("zz-ghost")
    registry[0]["spawn_allowlist"].append("zz-ghost")
    dirty = spawn_verdict(declarations, registry, pkg, ticket_phase_ids=["zz-a", "zz-c"])
    refusing = [f for f in dirty["findings"] if f.get("severity") == "refuse"]
    assert [(f["agent"], f["sub_agent"]) for f in refusing] == [("zz-one", "zz-ghost")]
    assert (dirty["agents_examined"], dirty["sub_agents_resolved"]) == (2, 4), dirty
    with pytest.raises(ValueError):
        spawn_verdict({}, [], pkg)


def _remediated(name: str, layout: Path, capsys) -> list[str]:
    """Every place on the REAL tree that still names ``name`` (empty == fully removed)."""
    found = []
    for rel in ("config/agent_registry.json", "config/package_boundary.json", "config/agent_registry.schema.json"):
        if name in (REPO_ROOT / rel).read_text(encoding="utf-8"):
            found.append(rel)
    found += [f"templates/agents/{t.name}" for t in sorted((REPO_ROOT / "templates" / "agents").glob("*.md"))
              if name in t.read_text(encoding="utf-8")]
    roots = layout_roots(layout)
    assert len(roots) >= 2
    found += [f"compiled:{r.parent.name}/{p.name}" for r in roots for p in sorted(r.glob("*.md"))
              if name in p.read_text(encoding="utf-8")]
    rc, said = run_gate(REPO_ROOT, capsys)
    if rc != 0 or name in said:
        found.append(f"ability guard: exit {rc}: {said[-300:]!r}")
    return found


@pytest.mark.shared_layout_reader
def test_real_tree_has_no_architect_review_deep_after_remediation(shared_reference_layout, capsys):
    # covers: AR-300c-5-iii
    # angle: real_artifact
    """AR-300c-5-iii (decision 10): on the REAL tree architect-review-deep is absent from
    architect-review's declaration and body, the registry, package_boundary.json, the
    registry schema's descriptions and every compiled prompt (both roots), and the build's
    own guard raises no refusing finding (exit 0) naming it. The registry copy is checked by
    NAME, never by an allowlist of names or by treating a registry row as resolution."""
    found = _remediated("architect-review-deep", shared_reference_layout, capsys)
    assert not found, f"architect-review-deep survives in: {found}"


@pytest.mark.shared_layout_reader
def test_real_tree_has_no_conflict_resolver_deep_after_remediation(shared_reference_layout, capsys):
    # covers: AR-300c-5-iii
    # angle: real_artifact
    """AR-300c-5-iii (decision 13, same treatment): conflict-resolver-deep is absent from the
    registry, package_boundary.json, the schema descriptions, every template body and every
    compiled prompt, and conflict-resolver's header no longer carries a ``spawn_allowlist``
    key at all (the removal left it empty, so the key goes rather than staying ``[]``)."""
    found = _remediated("conflict-resolver-deep", shared_reference_layout, capsys)
    assert not found, f"conflict-resolver-deep survives in: {found}"
    fm = template_frontmatter(REPO_ROOT / "templates" / "agents" / "conflict-resolver.md")
    assert KEY not in fm, f"conflict-resolver keeps an empty declaration: {fm.get(KEY)!r}"
