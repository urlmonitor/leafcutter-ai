"""AR-400e-1-ii -- the architecture diagram and the knowledge graph show the abilities of the
specialists that carried only the NEWER ``skills_invoked`` field on 2026-10-12 (TDD red phase).

Population from the captured 2026-10-12 snapshot (``H.snapshot_populations``), abilities from
the templates' own declarations. The graph runs over a trimmed project root that carries the
REAL ``agents`` / ``skills`` surface entries of ``config/paths.json`` (so a change confined to
``knowledge_edges.py``'s legacy fallback is inert here, exactly as in production) and the
decision-12 label ``skills_used`` is asserted on the edges the graph actually produces.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar_400e_support as H  # noqa: E402



def test_diagram_draws_one_link_per_declared_ability(tmp_path):
    # covers: AR-400e-1-ii
    # angle: criterion
    """Over a copy of the real registry (CLI ``generate_agent_diagram.py --diagram skill``), each
    specialist that declares abilities has exactly its declared ids as links (descriptive_only
    excluded) -- including the former newer-field-only specialists. Red while the diagram reads
    the older skills_used."""
    _older, newer = H.snapshot_populations()
    root = H.lean_root(tmp_path)
    decl = {a: s for a, s in H.declared_ids(root).items() if s}
    assert set(newer) <= set(decl), "newer-field population must declare abilities"
    view = H.view_diagram(root)
    problems = [m for m in H.mismatches("diagram", view, decl) if "examined" not in m]
    wrong_newer = [p for p in problems if any(f": {a} " in p for a in newer)]
    assert not problems, (f"{len(problems)} problem(s), {len(wrong_newer)} of them for the former "
                          f"newer-field-only specialists:\n" + "\n".join(problems[:25]))


def test_knowledge_graph_has_one_edge_per_declared_ability(tmp_path):
    # covers: AR-400e-1-ii
    # angle: real_artifact
    """Knowledge graph over the real registry + real agents/skills surface entries of paths.json:
    each specialist's agent->ability edges equal its declared ids (empty declarations -> no
    edges), the TOTAL equals the sum of declarations exactly, every edge is labelled
    'skills_used' (never 'skills_invoked'), no entry is declined (dict entries resolve), and
    validate_knowledge_map accepts the relabelled edge type."""
    root = H.lean_root(tmp_path)
    decl = H.declared_ids(root)
    graph = H.view_graph(root)
    problems = [m for m in H.mismatches("graph", graph.view, decl) if "examined" not in m]
    want_total = sum(len(v) for v in decl.values())
    assert want_total > 0
    if graph.edge_total != want_total:
        problems.append(f"{graph.edge_total} agent->ability edges, declarations total {want_total}")
    if graph.edge_types != {"skills_used"}:
        problems.append(f"edge labels {sorted(graph.edge_types)}, expected exactly ['skills_used']")
    if graph.declined:
        problems.append(f"{len(graph.declined)} entries declined by the path-entry resolver: {graph.declined[:2]}")
    if graph.invalid:
        problems.append(f"validate_knowledge_map rejects the agents surface: {graph.invalid}")
    assert not problems, f"{len(problems)} problem(s):\n" + "\n".join(problems[:25])


class TestStrayOlderFieldEntry(unittest.TestCase):
    def test_stray_older_field_entry_changes_neither_view(self):
        # covers: AR-400e-1-ii
        # angle: discrimination
        """Wrong version caught: a view that still reads / unions skills_used. Baseline = the
        hook's output with any retired field removed; then a stray skills_used naming a REAL
        undeclared skill is hand-planted on several specialists: the diagram text and the edge
        set are byte-identical. Paired positive (otherwise both sides are vacuously empty): the
        baseline diagram and graph each hold exactly the declared abilities."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = H.regenerated_root(base)
            decl = H.declared_ids(root)
            before_diagram = H.diagram_stdout(root / "config" / "agent_registry.json")
            before_graph = H.view_graph(root)
            nonempty = {a: s for a, s in decl.items() if s}
            self.assertEqual([m for m in H.mismatches("diagram", H.view_diagram(root), nonempty)
                              if "examined" not in m], [], "baseline diagram must show the declarations")
            self.assertEqual([m for m in H.mismatches("graph", before_graph.view, decl)
                              if "examined" not in m], [], "baseline graph must show the declarations")
            planted = H.plant_stray(root)
            self.assertGreater(len(planted), 1)
            self.assertEqual(before_diagram, H.diagram_stdout(root / "config" / "agent_registry.json"))
            after_graph = H.view_graph(root)
            self.assertEqual(before_graph.view.abilities, after_graph.view.abilities)
            self.assertEqual(before_graph.edge_total, after_graph.edge_total)


if __name__ == "__main__":
    unittest.main()
