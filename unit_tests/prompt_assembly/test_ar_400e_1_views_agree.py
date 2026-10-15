"""AR-400e-1 -- for every specialist, each view of its abilities lists exactly what its own
definition's ``skills:`` declaration grants (TDD red phase).

The six views are the REAL readers (see ``_ar_400e_support``): the briefing, the build's
registry validation, the architecture diagram, the knowledge graph, the published card and
the ability verdict. The population is derived at run time from the templates' frontmatter,
never hard-coded.
"""

from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar_400e_support as H  # noqa: E402

logging.disable(logging.CRITICAL)  # the scanners warn about the slice's absent AC store / CLAUDE.md


def test_every_view_lists_exactly_the_declared_abilities_for_every_specialist(tmp_path):
    # covers: AR-400e-1
    # angle: real_artifact
    """Part A: over a copy of the real tree (committed registry) every view equals the
    declaration for every specialist. Part B (wrong versions): a copy whose registry is the
    hook's output, with a hand-planted descriptive_only entry naming a REAL undeclared skill on
    several specialists -- briefing, diagram and graph must not show it as an ability, and the
    graph must hold its dict skills_invoked entries (zero declined, label skills_used, agents
    surface valid). A reader still on skills_used, or one that lists descriptive entries, or a
    graph that refuses dict entries, each goes red here. Red until readers move AND the
    committed registry is regenerated."""
    problems: list[str] = []
    real = H.lean_root(tmp_path, name="real")
    decl = H.declared_ids(real)
    assert len(decl) > 0 and any(not v for v in decl.values()), "population must include empty declarations"
    for name, view in H.all_views(real, tmp_path).items():
        problems += H.mismatches(name, view, decl)

    planted_root = H.lean_root(tmp_path, name="planted")
    assert H.run_hook(planted_root).returncode == 0
    H.strip_retired(planted_root)
    planted = H.plant_descriptive(planted_root)
    graph = H.view_graph(planted_root)
    views = {"briefing": H.view_briefing(planted_root, sorted(planted)), "diagram": H.view_diagram(planted_root),
             "graph": graph.view}
    for name, view in views.items():
        subset = {a: decl[a] for a in planted}
        problems += [m for m in H.mismatches(f"{name}[descriptive planted]", view, subset)
                     if "examined" not in m]
    if graph.declined:
        problems.append(f"graph declined {len(graph.declined)} entries: {graph.declined[:2]}")
    if graph.invalid:
        problems.append(f"validate_knowledge_map rejects the agents surface: {graph.invalid}")
    if graph.edge_types != {"skills_used"}:
        problems.append(f"agent->ability edge labels are {sorted(graph.edge_types)}, expected exactly ['skills_used']")
    by_view = {v: sum(1 for p in problems if p.startswith(v)) for v in
               ("briefing", "validation", "diagram", "graph", "card", "verdict")}
    assert not problems, f"{len(problems)} disagreement(s) by view {by_view}:\n" + "\n".join(
        [p for p in problems if "diagram" not in p or "absent" not in p][:30])


def test_empty_declaration_appears_in_every_view_with_no_abilities(tmp_path):
    # covers: AR-400e-1
    # angle: boundary
    """A planted specialist whose declaration grants nothing, and every real one that grants
    nothing, are PRESENT in every view's population with an empty set -- not absent from some
    views. Control in the same run: the population holds specialists that DO grant."""
    root = H.lean_root(tmp_path)
    H.plant_specialist(root, "probe-empty", [])
    assert H.run_hook(root).returncode == 0
    H.strip_retired(root)
    decl = H.declared_ids(root)
    empties = {a: set() for a, v in decl.items() if not v}
    assert "probe-empty" in empties and len(empties) > 1, "need planted + real empty declarations"
    assert any(decl.values()), "control: some specialist must grant something"
    problems: list[str] = []
    for name, view in H.all_views(root, tmp_path).items():
        problems += [m for m in H.mismatches(f"{name}[empty]", view, empties) if "examined" not in m]
        if view.count != len(decl):
            problems.append(f"{name}: examined {view.count}, tree has {len(decl)}")
    assert not problems, f"{len(problems)} problem(s):\n" + "\n".join(sorted(set(problems))[:30])


def test_each_view_reports_examined_count_equal_to_definitions(tmp_path):
    # covers: AR-400e-1
    # angle: boundary
    """Every view's examined-specialist count equals the number of specialist definitions
    derived from templates/agents/ and from the registry (and those two agree)."""
    root = H.lean_root(tmp_path)
    from_templates = set(H.declared(root))
    from_registry = {a["id"] for a in H.registry(root)["agents"]}
    assert from_templates == from_registry and from_templates, (from_templates ^ from_registry)
    wrong = {n: v.count for n, v in H.all_views(root, tmp_path).items() if v.count != len(from_templates)}
    assert not wrong, f"views whose examined count != {len(from_templates)} definitions: {wrong}"
