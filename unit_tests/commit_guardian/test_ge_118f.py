"""
MODULE: unit_tests/commit_guardian/test_ge_118f.py
COVERS: GE-118f -- "The commit-time guard and the knowledge map resolve a
    frontmatter entry through one shared rule"

GOAL: RED test-first stubs for the four test_spec entries of GE-118f. The
    producer already exists (scripts/frontmatter_path_resolver.py, GE-118d) and
    the guard (validate_paths) already calls it; the SECOND consumer,
    extract_edges() in scripts/knowledge_query.py, still applies its own
    ``isinstance(item, str)`` rule. Agreement between the two is the property
    under test, proven behaviourally -- never by grepping for the helper's name.

INTERFACE THIS SUITE ESTABLISHES for the single declaration point (the AC
    requires one but names no API): the accepted-shape rule is the module-level
    function ``frontmatter_path_resolver.resolve_frontmatter_path_entry``.
    Test 2 replaces THAT ONE OBJECT in-process -- every reference to it, in
    the resolver module and in any consumer that imported it, is rebound to a
    wrapper that additionally admits a third shape -- with no edit to either
    consumer. A consumer that carries its own copy of the rule does not move.

FIXTURE AUTHENTICITY: documents are yaml.safe_dump output (doc_text) read back
    from disk; the map builder is driven through the real CLI subprocess. The
    deployed arm reads the shared session reference layout
    (get_or_produce_shared_layout, read-only) -- a build outside this repository
    -- instead of spawning its own build.py (CLAUDE.md "Tests must not spawn
    their own build.py").

WRONG VERSIONS THESE TESTS CATCH: two independent copies of the rule that agree
    today (test 2 moves only one); agreement on the SET but not the ORDER
    (test 1 compares ordered lists); a consumer that pre-filters by type before
    calling the resolver (the tuple third shape never reaches it); a resolver
    missing from the deploy manifest (test 3); routing _doc_mentions_adr through
    the resolver (test 4 plants a tripwire on every reference to it).
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

from scripts.suite_performance._shared_layout_producer import get_or_produce_shared_layout

from ._ge_118d_fixtures import _REPO_ROOT, _TEMPLATES_CG_DIR, _init_repo
from ._ge_118d_refusal_fixtures import (
    doc_text,
    import_resolver,
    run_deployed_hook,
    write_existing_targets,
)

_UNIT_TESTS_DIR = Path(__file__).resolve().parents[1]
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from km_kgs_100d_3_shared import (  # noqa: E402
    BARE_NAME,
    LABELLED_NAME,
    raw_path,
    related_docs_edges,
    run_cli,
    write_doc,
    write_paths_json,
    write_target_docs,
)

_BROKEN = re.compile(r"Broken path in 'related_docs': '(.+)' does not exist")
_SRC_ID = "ge118f-src"
_THIRD_SHAPE = ("alias", "docs/third-shape-doc.md")


class _ResolverCalledError(AssertionError):
    """_doc_mentions_adr must not call the shared resolver."""


def _guard_module():
    """Import the SOURCE-tree guard validators (and put scripts/ on sys.path)."""
    import_resolver()
    if str(_TEMPLATES_CG_DIR) not in sys.path:
        sys.path.insert(0, str(_TEMPLATES_CG_DIR))
    import frontmatter_validators

    return frontmatter_validators


def _builder_module():
    """Import the SOURCE-tree map builder, scripts/knowledge_query.py."""
    import_resolver()
    import knowledge_query

    return knowledge_query


def _rebind_everywhere(original, replacement, test: unittest.TestCase) -> int:
    """Rebind every module-level reference to *original* to *replacement*.

    Models "admit a further shape at the ONE declaration point": the function
    object is the single routine, and every name that holds it follows the
    substitution. Restored on cleanup. Returns the number of names rebound.
    """
    rebound = []
    for module in list(sys.modules.values()):
        namespace = getattr(module, "__dict__", None)
        if not isinstance(namespace, dict):
            continue
        for name, value in list(namespace.items()):
            if value is original:
                namespace[name] = replacement
                rebound.append((namespace, name))
    for namespace, name in rebound:
        test.addCleanup(namespace.__setitem__, name, original)
    return len(rebound)


def _guard_paths(entries: list) -> list[str]:
    """Ordered paths the guard would check, read from its own error output."""
    guard = _guard_module()
    fm, _body = guard.extract_frontmatter(doc_text({"related_docs": entries}))
    with tempfile.TemporaryDirectory() as empty_root:
        errors = guard.validate_paths(fm, Path(empty_root))
    paths = [m.group(1) for e in errors if (m := _BROKEN.search(e))]
    assert len(paths) == len(errors), f"guard emitted a non-path error: {errors!r}"
    return paths


class TestGe118fSeamAndSingleDeclarationPoint(unittest.TestCase):
    def test_ge_118f_both_consumers_resolve_one_field_value_to_the_same_ordered_path_list(self) -> None:
        # covers: GE-118f
        # angle: seam
        """One related_docs value (a bare entry then a labelled entry), written
        by yaml.safe_dump. The guard's ordered list of paths-to-check and the
        map builder's ordered list of edge targets (the real CLI over the same
        document) are EQUAL -- order included, compared by filename stem so
        either target spelling is accepted.

        FAILS TODAY: the guard resolves both entries, but the builder yields
        one edge (the labelled entry is dropped), so the lists differ.
        What must be implemented: extract_edges obtains each element's path
        from the shared resolver, in the author's order.
        """
        entries = [raw_path("docs", BARE_NAME), {"reference": raw_path("docs", LABELLED_NAME)}]
        guard_list = _guard_paths(entries)
        self.assertEqual(2, len(guard_list), msg=f"control: the guard resolves both entries: {guard_list!r}")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_paths_json(root)
            write_target_docs(root, "docs", [BARE_NAME, LABELLED_NAME])
            (root / "docs" / f"{_SRC_ID}.md").write_text(
                doc_text({"related_docs": entries}), encoding="utf-8"
            )
            result = run_cli(root, ["--format", "json", "--surface", "docs"])
            self.assertEqual(0, result.returncode, msg=result.stderr)
            edges = related_docs_edges(json.loads(result.stdout), _SRC_ID)

        builder_list = [target for target, _etype in edges]
        self.assertEqual(
            [Path(p).stem for p in guard_list],
            [Path(t).stem for t in builder_list],
            msg=f"guard={guard_list!r} builder={builder_list!r}",
        )

    def test_ge_118f_admitting_a_further_shape_at_the_single_declaration_point_moves_both_consumers(
        self,
    ) -> None:
        # covers: GE-118f
        # angle: seam
        """THE ARM THAT CANNOT PASS BY COINCIDENCE. A third shape (a two-tuple
        ``(label, path)``) is refused by both consumers at baseline. The one
        resolver function is then replaced in-process by a wrapper admitting
        that shape -- no edit to either consumer -- and BOTH must now resolve
        it: the guard checks its path, the builder yields an edge for it.

        FAILS TODAY: the guard follows the substitution; extract_edges keeps
        its own ``isinstance(item, str)`` rule and yields nothing, so the
        builder does not move.
        """
        guard = _guard_module()
        builder = _builder_module()
        resolver = import_resolver()
        original = resolver.resolve_frontmatter_path_entry
        fm = {"related_docs": [_THIRD_SHAPE]}
        record = builder.NodeRecord(
            id=_SRC_ID, surface="docs", title="t", description="d", path=Path("docs/x.md")
        )

        def edges_now() -> list:
            return list(builder.extract_edges("docs", record, fm, ["related_docs"]))

        with tempfile.TemporaryDirectory() as empty_root:
            baseline_errors = guard.validate_paths(fm, Path(empty_root))
            self.assertEqual(1, len(baseline_errors), msg=f"baseline: guard refuses: {baseline_errors!r}")
            self.assertIn("Unsupported entry", baseline_errors[0])
            self.assertEqual([], edges_now(), msg="baseline: builder yields no edge for the third shape")

            def admitting(entry, field):
                if isinstance(entry, tuple) and len(entry) == 2 and all(isinstance(p, str) for p in entry):
                    return entry[1]
                return original(entry, field)

            rebound = _rebind_everywhere(original, admitting, self)
            self.assertGreaterEqual(rebound, 2, msg="the resolver must be referenced by its consumers")

            moved_errors = guard.validate_paths(fm, Path(empty_root))
            self.assertEqual(1, len(moved_errors), msg=f"guard after substitution: {moved_errors!r}")
            self.assertIn("Broken path in 'related_docs': 'docs/third-shape-doc.md'", moved_errors[0])

            moved_edges = edges_now()
            self.assertEqual(1, len(moved_edges), msg=f"builder must move too; edges={moved_edges!r}")
            self.assertEqual("related_docs", moved_edges[0].edge_type)
            self.assertIn(moved_edges[0].target_id, ("docs/third-shape-doc.md", "third-shape-doc"))

    def test_ge_118f_adr_cross_reference_still_matches_by_whole_file_substring(self) -> None:
        # covers: GE-118f
        # angle: boundary
        """The third consumer stays unaffected. An ADR id that appears ONLY in
        the document's prose (never in related_docs) is still found, matching is
        still case-insensitive, an unmentioned id is still absent (control) --
        and every reference to the resolver carries a tripwire that raises, so
        a version routed through the resolver fails here.

        PASSES TODAY by design: this guards behaviour that must NOT change.
        """
        sys.path.insert(0, str(_TEMPLATES_CG_DIR))
        self.addCleanup(sys.path.remove, str(_TEMPLATES_CG_DIR))
        import_resolver()
        import check_adr_cross_reference

        resolver = import_resolver()
        original = resolver.resolve_frontmatter_path_entry

        def tripwire(entry, field):
            raise _ResolverCalledError

        _rebind_everywhere(original, tripwire, self)
        with tempfile.TemporaryDirectory() as tmp:
            doc = write_doc(
                Path(tmp) / "doc.md",
                {"title": "Doc", "related_docs": [{"reference": "docs/unrelated.md"}]},
                body="The decision is recorded in adr-901-some-decision, see prose.\n",
            )
            self.assertTrue(check_adr_cross_reference._doc_mentions_adr(doc, "ADR-901-some-decision"))
            self.assertFalse(check_adr_cross_reference._doc_mentions_adr(doc, "ADR-902-never-mentioned"))


@pytest.mark.shared_layout_reader
# The fixture must run at SETUP, not be produced from inside the test body:
# shared_layout_integrity captures its baseline in pytest_runtest_setup, so a
# reader whose layout first appears during the call phase leaves no baseline,
# and the session then exits 1. A unittest.TestCase cannot take a fixture as
# an argument; usefixtures is how it requests one.
@pytest.mark.usefixtures("shared_reference_layout")
class TestGe118fDeployedLayout(unittest.TestCase):
    def test_ge_118f_deployed_layout_both_consumers_import_the_resolver_from_a_target_outside_this_repo(
        self,
    ) -> None:
        # covers: GE-118f
        # angle: deployed
        """Against the DEPLOYED layout (a real build.py output outside this
        repository, shared read-only), run the deployed guard hook and the
        deployed knowledge_query.py as separate fresh subprocesses over a
        document carrying a bare and a labelled entry. Neither stream carries
        ModuleNotFoundError/ImportError, the hook accepts the document, and the
        deployed builder exits 0 with TWO related_docs edges.

        FAILS TODAY: the deployed builder drops the labelled entry (one edge).
        The hook half is a control that is green today (GE-118d deployed it).
        """
        layout = get_or_produce_shared_layout()
        self.assertFalse(
            str(layout.resolve()).startswith(str(_REPO_ROOT.resolve())),
            msg=f"the reference layout must be outside this repository: {layout}",
        )
        # The build deploys both modules under the install root
        # (<layout>/.leafcutter/scripts/). <layout>/scripts/ holds only three
        # symlinks (commit_guardian, doc_compliance, feedback), so
        # knowledge_query.py does not exist there. The shipped knowledge-query
        # skill nevertheless documents `python scripts/knowledge_query.py`,
        # which fails in every adopter install. That is a separate defect,
        # filed rather than encoded here: this test proves where the code is
        # actually deployed, not where a document says it is.
        deployed_scripts = layout / ".leafcutter" / "scripts"
        deployed_query = deployed_scripts / "knowledge_query.py"
        self.assertTrue(deployed_query.exists(), msg=f"not deployed: {deployed_query}")
        self.assertTrue(
            (deployed_scripts / "frontmatter_path_resolver.py").exists(),
            msg="the resolver must be deployed beside knowledge_query.py",
        )

        bare, labelled = "docs/explanation/architecture.md", "docs/reference/configuration.md"
        doc_rel = f"docs/{_SRC_ID}.md"
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init_repo(repo)
            write_existing_targets(repo)
            write_doc(repo / "docs" / "alias-architecture.md", {"id": bare})
            write_doc(repo / "docs" / "alias-configuration.md", {"id": labelled})
            write_paths_json(repo)
            (repo / doc_rel).write_text(
                doc_text({"related_docs": [bare, {"reference": labelled}]}), encoding="utf-8"
            )

            hook = run_deployed_hook(layout, repo, doc_rel)
            query = run_cli(repo, ["--format", "json", "--surface", "docs"], script=deployed_query)

        for name, proc in (("deployed hook", hook), ("deployed knowledge_query", query)):
            combined = proc.stdout + proc.stderr
            self.assertNotIn("ModuleNotFoundError", combined, msg=f"{name}: {combined}")
            self.assertNotIn("ImportError", combined, msg=f"{name}: {combined}")
        self.assertEqual(0, hook.returncode, msg=f"hook: {hook.stdout!r} {hook.stderr!r}")
        self.assertNotIn("Broken path", hook.stdout + hook.stderr)
        self.assertEqual(0, query.returncode, msg=f"query stderr: {query.stderr!r}")
        edges = related_docs_edges(json.loads(query.stdout), _SRC_ID)
        self.assertEqual(2, len(edges), msg=f"deployed builder must yield both edges: {edges!r}")


if __name__ == "__main__":
    unittest.main()
