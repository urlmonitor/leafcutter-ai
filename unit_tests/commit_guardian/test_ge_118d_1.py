"""
MODULE: unit_tests/commit_guardian/test_ge_118d_1.py
COVERS: GE-118d-1 -- "An entry in a shape the guard does not accept is refused
    by name, and the guard never raises"

GOAL: RED test-first stubs for all four test_spec entries on GE-118d-1
    (angles: deployed, criterion, failure, boundary), written after GE-118d's
    resolver landed. The resolver already classifies a 7, a nested list and a
    mapping-of-mapping as refusals, but validate_paths() reports them as
    "Unsupported entry in '<field>': accepted shapes are ..." -- it names the
    field and the accepted set and NOTHING ELSE: not the offending entry as the
    parser rendered it, and the resolver still ACCEPTS the empty string as a
    path. Those are the two gaps these tests pin.

MESSAGE CONTRACT these tests establish (single physical line per refused
    entry, so the entry and the accepted set are attributable to one finding):
    the line names the field, shows the entry as ``repr(entry)`` (which is what
    distinguishes the integer 7 from the string '7'), and contains every string
    in ``frontmatter_path_resolver.ACCEPTED_SHAPES``. The document is named by
    the hook's own "FRONTMATTER VIOLATION: '<doc>'" header line.

FIXTURE AUTHENTICITY: every document is written with yaml.safe_dump
    (`_ge_118d_refusal_fixtures.doc_text`) and re-read from disk by the real
    hook. The deployed arm reads the shared session reference layout
    (`get_or_produce_shared_layout()`), read-only, instead of spawning its own
    build.py (CLAUDE.md "Tests must not spawn their own build.py").
"""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from scripts.suite_performance._shared_layout_producer import get_or_produce_shared_layout

from ._ge_118d_fixtures import _init_repo, _run_hook_against_source, _write
from ._ge_118d_refusal_fixtures import (
    doc_text,
    import_resolver,
    run_deployed_hook,
    write_existing_targets,
)

_INT_ENTRY = 7
_NESTED_LIST_ENTRY = ["docs/explanation/architecture.md"]
_MAPPING_OF_MAPPING_ENTRY = {"explanation": {"inner": "docs/explanation/architecture.md"}}
_BAD_ENTRIES = [_INT_ENTRY, _NESTED_LIST_ENTRY, _MAPPING_OF_MAPPING_ENTRY]
_CONTROL_RELATED_CODE = ["scripts/ge118d_temp_helper.py"]
_DOC_REL = "docs/ge118d1_refusal_doc.md"
_TRACEBACK = "Traceback (most recent call last)"


def _lines_for_entry(combined: str, field: str, entry: object) -> list[str]:
    """Lines of *combined* that name *field* and show *entry* as parsed."""
    if isinstance(entry, int):
        # The integer 7, not the string '7', not a digit inside a path.
        shown = re.compile(r"(?<![\w'/.])7(?![\w'/.])")
        return [ln for ln in combined.splitlines() if field in ln and shown.search(ln)]
    return [ln for ln in combined.splitlines() if field in ln and repr(entry) in ln]


class _RefusalDocMixin:
    """Builds the AC's document in a real isolated git repo."""

    def _make_repo(self) -> Path:
        tmp = tempfile.TemporaryDirectory(prefix="ge118d1_")
        self.addCleanup(tmp.cleanup)  # type: ignore[attr-defined]
        repo = Path(tmp.name)
        _init_repo(repo)
        write_existing_targets(repo)
        _write(
            repo / _DOC_REL,
            doc_text({"related_docs": _BAD_ENTRIES, "related_code": _CONTROL_RELATED_CODE}),
        )
        return repo


class TestGe118d1Deployed(_RefusalDocMixin, unittest.TestCase):
    """Deployed-layout arm: the hook as build.py ships it."""

    def test_ge_118d_1_each_unaccepted_entry_is_reported_by_name_with_the_accepted_shape_set(
        self,
    ) -> None:
        # covers: GE-118d-1
        # angle: deployed
        """Run the DEPLOYED hook against related_docs = [7, nested list,
        mapping-of-mapping]. One error per entry, each naming the field, the
        entry as parsed and BOTH accepted shapes -- and the accepted-shape text
        equals the resolver's declared set, not a hard-coded sentence.

        FAILS TODAY: the message names the field and the shapes but never the
        offending entry, so no line carries repr(entry).
        What must be implemented: validate_paths() formats the refusal from
        PathEntryRefusal.field / .entry / .accepted_shapes.
        """
        layout = get_or_produce_shared_layout()
        repo = self._make_repo()
        result = run_deployed_hook(layout, repo, _DOC_REL)
        combined = result.stdout + result.stderr
        accepted = import_resolver().ACCEPTED_SHAPES
        self.assertEqual(2, len(accepted), msg="the declared accepted set is the two shapes")

        for entry in _BAD_ENTRIES:
            lines = _lines_for_entry(combined, "related_docs", entry)
            self.assertEqual(
                1,
                len(lines),
                msg=f"expected exactly one error naming related_docs and {entry!r}; "
                f"got {lines!r}\nfull output:\n{combined}",
            )
            for shape in accepted:
                self.assertIn(shape, lines[0], msg=f"error must name accepted shape {shape!r}")
        self.assertNotIn("ModuleNotFoundError", combined, msg=combined)
        self.assertNotIn(_TRACEBACK, combined, msg=combined)

    def test_ge_118d_1_message_reads_the_declared_set_not_a_hard_coded_sentence(self) -> None:
        # covers: GE-118d-1
        # angle: criterion
        """Wrong version this catches: a message that restates the two shapes
        as a literal sentence. The resolver's declared set is swapped for a
        sentinel set in-process; the refusal text built by validate_paths()
        must then carry the sentinel strings (and the entry as parsed) -- a
        hard-coded sentence cannot follow the swap.

        FAILS TODAY: the refusal line carries no entry, so the entry-as-parsed
        assertion fails (the sentinel assertion is the guard against the
        hard-coded wrong version once the entry is added).
        """
        import sys

        from ._ge_118d_fixtures import _TEMPLATES_CG_DIR

        resolver = import_resolver()
        if str(_TEMPLATES_CG_DIR) not in sys.path:
            sys.path.insert(0, str(_TEMPLATES_CG_DIR))
        from frontmatter_validators import validate_paths

        sentinel = ("sentinel shape alpha", "sentinel shape beta")
        original = resolver.ACCEPTED_SHAPES
        resolver.ACCEPTED_SHAPES = sentinel
        self.addCleanup(setattr, resolver, "ACCEPTED_SHAPES", original)

        errors = validate_paths({"related_docs": [_MAPPING_OF_MAPPING_ENTRY]}, Path("/nonexistent"))
        self.assertEqual(1, len(errors), msg=f"one refusal expected: {errors!r}")
        for shape in sentinel:
            self.assertIn(shape, errors[0], msg="accepted set must be read, not restated")
        self.assertIn(repr(_MAPPING_OF_MAPPING_ENTRY), errors[0])
        self.assertIn("related_docs", errors[0])


class TestGe118d1Criterion(_RefusalDocMixin, unittest.TestCase):
    """Control arm: the pass completes across entries and fields."""

    def test_ge_118d_1_remaining_entries_and_remaining_fields_are_still_checked_after_a_refusal(
        self,
    ) -> None:
        # covers: GE-118d-1
        # angle: criterion
        """THE CONTROL THAT A WEAK TEST DROPS. The same document carries one
        bare related_code entry naming a path that exists. Total error count
        for the document is exactly three and no error mentions related_code --
        the pass completed rather than ending at the first refusal.

        FAILS TODAY: the three refusals are reported, but with no entry shown,
        so the per-entry attribution (one line each carrying the entry as
        parsed) cannot be made and the exact-three assertion on attributable
        errors fails.
        """
        repo = self._make_repo()
        result = _run_hook_against_source(repo, [_DOC_REL])
        combined = result.stdout + result.stderr

        attributable = [
            ln
            for entry in _BAD_ENTRIES
            for ln in _lines_for_entry(combined, "related_docs", entry)
        ]
        self.assertEqual(3, len(attributable), msg=f"one error per entry:\n{combined}")
        related_docs_errors = [ln for ln in combined.splitlines() if "related_docs" in ln]
        self.assertEqual(
            3, len(related_docs_errors), msg=f"exactly three related_docs errors:\n{combined}"
        )
        self.assertNotIn(
            "related_code",
            combined,
            msg=f"the existing bare related_code entry must not be reported:\n{combined}",
        )


class TestGe118d1Failure(_RefusalDocMixin, unittest.TestCase):
    """Failure arm: a refusing verdict, never a traceback, never exit zero."""

    def test_ge_118d_1_refusing_verdict_reached_with_no_traceback_on_any_stream(self) -> None:
        # covers: GE-118d-1
        # angle: failure
        """Non-zero exit, the document path in the output, neither stream
        carrying 'Traceback (most recent call last)' or 'TypeError'. Exit zero
        also fails: a swallow-and-continue implementation produces no
        traceback and no refusal.

        FAILS TODAY: the refusal verdict and no-traceback parts already hold,
        but the refusal does not show the entry as parsed, which this test also
        requires so a verdict that merely refuses (without naming what it
        refused) does not pass.
        """
        repo = self._make_repo()
        result = _run_hook_against_source(repo, [_DOC_REL])
        combined = result.stdout + result.stderr

        self.assertNotEqual(0, result.returncode, msg=f"must refuse, got exit 0:\n{combined}")
        self.assertIn(_DOC_REL, combined, msg="the refusal must name the document")
        self.assertNotIn(_TRACEBACK, result.stdout)
        self.assertNotIn(_TRACEBACK, result.stderr)
        self.assertNotIn("TypeError", combined)
        self.assertEqual(
            1,
            len(_lines_for_entry(combined, "related_docs", _MAPPING_OF_MAPPING_ENTRY)),
            msg=f"the refusal must show the offending entry as parsed:\n{combined}",
        )


class TestGe118d1Boundary(unittest.TestCase):
    """Boundary arm: the resolver over an open set of unaccepted inputs."""

    def test_ge_118d_1_resolver_refuses_every_unaccepted_shape_without_raising(self) -> None:
        # covers: GE-118d-1
        # angle: boundary
        """Direct on the resolver: integer, float, None, empty string, empty
        mapping, nested list, mapping-of-mapping, object without __fspath__.
        Every one returns a PathEntryRefusal; none raises.

        FAILS TODAY: the empty string is returned as a "path" (it is a str),
        so it is accepted rather than refused; joining it to the project root
        would make the guard check the root directory itself and pass.
        What must be implemented: the resolver refuses an empty string.
        """
        resolver = import_resolver()
        unaccepted = {
            "integer": 7,
            "float": 1.5,
            "none": None,
            "empty string": "",
            "empty mapping": {},
            "nested list": ["docs/a.md"],
            "mapping of mapping": {"label": {"inner": "docs/a.md"}},
            "object without __fspath__": object(),
        }
        for label, entry in unaccepted.items():
            with self.subTest(shape=label):
                refusal = resolver.resolve_frontmatter_path_entry(entry, "related_code")
                self.assertIsInstance(refusal, resolver.PathEntryRefusal, msg=f"{label} accepted")
                self.assertEqual("related_code", refusal.field)
                self.assertIs(refusal.entry, entry)
                self.assertEqual(tuple(resolver.ACCEPTED_SHAPES), tuple(refusal.accepted_shapes))

        # Control: the accepted shapes still resolve, so the refusals above are
        # not an artefact of a resolver that refuses everything.
        self.assertEqual("docs/a.md", resolver.resolve_frontmatter_path_entry("docs/a.md", "f"))
        self.assertEqual(
            "docs/b.md", resolver.resolve_frontmatter_path_entry({"label": "docs/b.md"}, "f")
        )


if __name__ == "__main__":
    unittest.main()
