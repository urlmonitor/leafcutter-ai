"""
MODULE: unit_tests/test_km_kgs_100d_3.py
COVERS: KM-KGS-100d-3 -- "A relationship entry becomes an edge whichever
    accepted shape it uses"

GOAL: RED test-first stubs for the four test_spec entries of KM-KGS-100d-3.
    The defect site is extract_edges() in scripts/knowledge_query.py: a
    related_docs element that is not a plain string produces no edge, no
    warning and no error, so a document declaring a bare and a labelled entry
    contributes one relationship (or none) to the map instead of two. Through
    the real frontmatter loader a labelled item arrives as the flattened text
    ``label: path`` (knowledge_frontmatter_reader treats mapping items as a
    non-goal), so the edge it would yield targets that text and is dropped by
    the membership filter -- the resolver-backed branch (GE-118f's shared
    resolver) must see the real shapes the loader produces.

FIXTURE AUTHENTICITY: every document is written with yaml.safe_dump (column-0
    block lists) and read from disk by the real CLI run as a subprocess; no
    test calls extract_edges on a typed dict. Targets are written as both a
    stem-id document and a raw-path-id alias (see km_kgs_100d_3_shared) so an
    edge survives the membership filter under either target spelling.

WRONG VERSIONS THESE TESTS CATCH: (1) the status quo (labelled entry dropped);
    (2) an edge whose target is the mapping's label, its repr, or the whole
    element (test 2 compares against the bare-form edge and forbids a node or
    target named after the label); (3) a related_docs special case that works
    on one surface only (test 3 derives the surface list from config/paths.json
    at test time); (4) a fix that works on a dict handed to extract_edges but
    not through the loader and CLI (test 4).
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from km_kgs_100d_3_shared import (
    BARE_NAME,
    LABELLED_NAME,
    REAL_PATHS_JSON,
    build_project,
    raw_path,
    related_docs_edges,
    run_json,
    target_matches,
)

_DOCS_DIR = "docs"
_SOURCE_ID = "src-doc"


def _entries(directory: str, labelled: bool) -> list:
    """related_docs: one bare entry then the second entry, labelled or bare."""
    bare = raw_path(directory, BARE_NAME)
    second = raw_path(directory, LABELLED_NAME)
    return [bare, {"reference": second} if labelled else second]


def _build(root: Path, directory: str, labelled: bool) -> str:
    return build_project(
        root,
        directory,
        _entries(directory, labelled),
        target_names=[BARE_NAME, LABELLED_NAME],
        source_id=_SOURCE_ID,
    )


def _surfaces_declaring_related_docs() -> list[tuple[str, str]]:
    """(surface, directory) for every directory surface whose configuration
    declares related_docs among its edge_fields -- READ at test time."""
    surfaces = json.loads(REAL_PATHS_JSON.read_text(encoding="utf-8"))["surfaces"]
    return [
        (name, cfg["path"].rstrip("/"))
        for name, cfg in surfaces.items()
        if "related_docs" in cfg.get("edge_fields", []) and cfg["path"].endswith("/")
    ]


class TestKmKgs100d3LabelledAndBareEntries(unittest.TestCase):
    def test_km_kgs_100d_3_labelled_and_bare_entries_each_produce_one_edge(self) -> None:
        # covers: KM-KGS-100d-3
        # angle: criterion
        """A document whose related_docs holds one bare entry and one labelled
        entry yields EXACTLY TWO related_docs edges from that document.

        FAILS TODAY: the labelled entry arrives as the text
        ``reference: <path>``, which is neither resolved nor matched to a
        node, so only one edge (or none) survives. What must be implemented:
        extract_edges calls the shared resolver for every element so the
        labelled entry denotes its path, and that edge survives the
        membership filter.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build(root, _DOCS_DIR, labelled=True)
            _result, payload = run_json(root, ["--surface", "docs"])

        edges = related_docs_edges(payload, _SOURCE_ID)
        self.assertEqual(2, len(edges), msg=f"want one related_docs edge per entry; got {edges!r}")
        self.assertEqual(2, len({t for t, _ in edges}), msg=f"two distinct targets expected: {edges!r}")
        self.assertTrue(target_matches(edges[0][0], _DOCS_DIR, BARE_NAME), msg=edges)
        self.assertTrue(target_matches(edges[1][0], _DOCS_DIR, LABELLED_NAME), msg=edges)

    def test_km_kgs_100d_3_labelled_entry_edge_equals_the_edge_the_bare_form_would_have_produced(
        self,
    ) -> None:
        # covers: KM-KGS-100d-3
        # angle: criterion
        """Two fixture trees identical except one writes the second entry
        labelled and the other bare: the edge sets (type AND target, in order)
        are equal, the node sets are equal, and nothing in either map is named
        after the label or the element's repr.

        Wrong versions this catches: an edge whose target is 'reference', the
        text 'reference: <path>', the dict repr, or the whole element; and a
        fix that mints a node for the label.
        FAILS TODAY: the labelled tree's second edge is missing, so the edge
        lists differ.
        """
        with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
            _build(Path(tmp_a), _DOCS_DIR, labelled=True)
            _build(Path(tmp_b), _DOCS_DIR, labelled=False)
            _ra, labelled_payload = run_json(Path(tmp_a), ["--surface", "docs"])
            _rb, bare_payload = run_json(Path(tmp_b), ["--surface", "docs"])

        labelled_edges = related_docs_edges(labelled_payload, _SOURCE_ID)
        bare_edges = related_docs_edges(bare_payload, _SOURCE_ID)
        self.assertEqual(2, len(bare_edges), msg=f"control: the bare tree must give two edges: {bare_edges!r}")
        self.assertEqual(bare_edges, labelled_edges, msg="labelled edge must equal the bare-form edge")

        labelled_nodes = sorted(n["id"] for n in labelled_payload["nodes"])
        bare_nodes = sorted(n["id"] for n in bare_payload["nodes"])
        self.assertEqual(bare_nodes, labelled_nodes, msg="the change must not create or remove any node")
        for target, _etype in labelled_edges:
            self.assertNotEqual("reference", target)
            self.assertFalse(target.startswith("reference:"), msg=target)
            self.assertNotIn("{", target, msg=f"target must not be an element repr: {target!r}")
        self.assertNotIn("reference", labelled_nodes, msg="the label must not become a node")

    def test_km_kgs_100d_3_holds_for_every_surface_that_declares_the_field(self) -> None:
        # covers: KM-KGS-100d-3
        # angle: boundary
        """For EVERY surface config/paths.json declares related_docs on (read
        at test time, three today: docs, adrs, components) the labelled entry
        yields its edge. A related_docs special case that only works for the
        first surface read fails on a later one.

        FAILS TODAY: the labelled entry yields no surviving edge on any
        surface (two edges expected on each).
        """
        declared = _surfaces_declaring_related_docs()
        self.assertGreaterEqual(len(declared), 1, msg="paths.json declares no surface with related_docs")
        for surface, directory in declared:
            with self.subTest(surface=surface), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                _build(root, directory, labelled=True)
                _result, payload = run_json(root, ["--surface", surface])
                edges = related_docs_edges(payload, _SOURCE_ID)
                self.assertEqual(
                    2, len(edges), msg=f"surface {surface!r}: want 2 related_docs edges, got {edges!r}"
                )
                self.assertTrue(target_matches(edges[1][0], directory, LABELLED_NAME), msg=edges)

    def test_km_kgs_100d_3_edge_appears_for_a_pyyaml_serialised_document_through_the_cli(
        self,
    ) -> None:
        # covers: KM-KGS-100d-3
        # angle: real_artifact
        """The fixture is PyYAML's own serialisation (block-list dashes at
        column 0), read from disk by the real loader, and the edge is parsed
        out of the stdout of ``knowledge_query.py --format json`` run as a
        subprocess (default surface traversal, every surface).

        FAILS TODAY: the labelled entry never becomes a surviving edge on the
        real loader's output. What must be implemented: the loader's labelled
        item reaches the resolver as a shape it accepts.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build(root, _DOCS_DIR, labelled=True)
            on_disk = (root / _DOCS_DIR / f"{_SOURCE_ID}.md").read_text(encoding="utf-8")
            self.assertIn("\nrelated_docs:\n- ", on_disk, msg="fixture must carry column-0 dashes")
            self.assertIn("\n- reference: ", on_disk, msg="fixture must carry the labelled form")
            _result, payload = run_json(root)

        edges = related_docs_edges(payload, _SOURCE_ID)
        self.assertEqual(2, len(edges), msg=f"want two related_docs edges via the CLI, got {edges!r}")


if __name__ == "__main__":
    unittest.main()
