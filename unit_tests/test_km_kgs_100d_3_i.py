"""
MODULE: unit_tests/test_km_kgs_100d_3_i.py
COVERS: KM-KGS-100d-3-i -- "An entry the builder cannot turn into an edge is
    reported, never passed over in silence"

GOAL: RED test-first stubs for the four test_spec entries of KM-KGS-100d-3-i.
    Today an element extract_edges does not turn into an edge produces no edge,
    no stderr line and no count: "contributed nothing" and "had nothing to
    contribute" render identically. The declined shape used throughout is a
    two-key labelled mapping -- a shape the shared resolver refuses (GE-118d-2)
    -- written by yaml.safe_dump and read back by the real CLI.

FIXTURE AUTHENTICITY: documents come from yaml.safe_dump; every behaviour is
    asserted from the CLI run as a subprocess (km_kgs_100d_3_shared). The
    declined entry is attributed through a test-only surface named
    ``zz_surface`` rooted at ``notes_dir/`` -- neither string is a substring of
    the other -- so a diagnostic naming the surface cannot be satisfied by the
    document path alone.

FIGURE CONTRACT PINNED HERE (see km_kgs_100d_3_shared): JSON key
    ``entries_declined``, text label ``Entries declined:`` on the summary line
    beside ``Edges:``; the pre-existing ``declined`` / ``Declined:`` figure is
    accepted as a fallback.

WRONG VERSIONS THESE TESTS CATCH: reporting declines only when non-zero (test
    3 asserts an explicit 0 and 0 != 3); printing from inside the generator so
    the two renderers disagree (test 2 compares them from separate runs);
    dedupe/cap of the count (test 3 declares three distinct entries); a stderr
    line missing any of surface/document/field/entry (test 1); stopping the
    field at the first declined entry, or exiting non-zero (test 4 puts the
    declined entry FIRST and asserts exit 0 and both accepted edges).
"""
from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from km_kgs_100d_3_shared import (
    write_doc,
    write_paths_json,
    write_target_docs,
    EXTRA_SURFACE,
    EXTRA_SURFACE_DIR,
    build_project,
    declined_from_json,
    declined_from_text,
    declined_mapping,
    edges_from_text_summary,
    extra_surface_config,
    raw_path,
    related_docs_edges,
    run_cli,
    run_json,
    stderr_lines_naming,
    summary_line,
    target_matches,
)

_DIR = EXTRA_SURFACE_DIR
_SOURCE_ID = "note-doc"
_SOURCE_REL = f"{_DIR}/{_SOURCE_ID}.md"
_GOOD_ONE = "good-one"
_GOOD_TWO = "good-two"


def _build(root: Path, entries: list) -> str:
    return build_project(
        root,
        _DIR,
        entries,
        target_names=[_GOOD_ONE, _GOOD_TWO],
        source_id=_SOURCE_ID,
        extra_surfaces=extra_surface_config(),
    )


def _one_declined_between_two_accepted() -> list:
    return [raw_path(_DIR, _GOOD_ONE), declined_mapping(_DIR, "mid"), raw_path(_DIR, _GOOD_TWO)]


class TestKmKgs100d3IDeclinedEntryIsReported(unittest.TestCase):
    def test_km_kgs_100d_3_i_declined_entry_is_named_on_stderr_with_surface_document_field_and_entry(
        self,
    ) -> None:
        # covers: KM-KGS-100d-3-i
        # angle: criterion
        """CLI subprocess over a tree whose related_docs carries one entry the
        resolver declines between two it accepts: ONE stderr line names the
        surface, the repo-relative document, the field AND the entry, and
        stdout is still parseable JSON.

        FAILS TODAY: nothing is written to stderr for the declined element.
        What must be implemented: extract_edges' declined outcome reaches the
        caller as data and the CLI writes one diagnostic line per decline.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build(root, _one_declined_between_two_accepted())
            result, payload = run_json(root)  # json.loads(stdout) proves parseable

        self.assertIn("edges", payload)
        lines = stderr_lines_naming(result.stderr, "declined-mid-first")
        self.assertEqual(
            1, len(lines), msg=f"want exactly one stderr line naming the entry; stderr={result.stderr!r}"
        )
        line = lines[0]
        self.assertIn(EXTRA_SURFACE, line, msg=f"line must name the surface: {line!r}")
        self.assertIn(_SOURCE_REL, line, msg=f"line must name the document: {line!r}")
        self.assertNotIn(str(root), line, msg=f"document must be repo-relative: {line!r}")
        self.assertIn("related_docs", line, msg=f"line must name the field: {line!r}")
        related_lines = stderr_lines_naming(result.stderr, "related_docs")
        self.assertEqual(1, len(related_lines), msg=f"one related_docs decline line: {related_lines!r}")

    def test_km_kgs_100d_3_i_declined_count_appears_beside_the_edge_count_in_both_renderers(
        self,
    ) -> None:
        # covers: KM-KGS-100d-3-i
        # angle: criterion
        """The same fixture is run with --format json and with the default
        text format. Both carry the declined figure, it is 1 in both (the same
        number from the same fixture), and the text figure sits on the very
        line that carries ``Edges:``.

        FAILS TODAY: neither renderer reports the declined entry (figure 0).
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build(root, _one_declined_between_two_accepted())
            _res_json, payload = run_json(root)
            res_text = run_cli(root)

        self.assertEqual(0, res_text.returncode, msg=res_text.stderr)
        figure_json = declined_from_json(payload)
        figure_text = declined_from_text(res_text.stdout)
        self.assertEqual(1, figure_json, msg=f"JSON declined figure; payload keys={sorted(payload)}")
        self.assertEqual(1, figure_text, msg=f"text summary: {summary_line(res_text.stdout)!r}")
        self.assertEqual(figure_json, figure_text, msg="renderers must report the same figure")
        self.assertEqual(
            len(payload["edges"]),
            edges_from_text_summary(res_text.stdout),
            msg="control: the text Edges figure is the JSON edge count",
        )
        self.assertIn("Edges:", summary_line(res_text.stdout))

    def test_km_kgs_100d_3_i_zero_declines_is_stated_and_differs_from_three_declines(self) -> None:
        # covers: KM-KGS-100d-3-i
        # angle: boundary
        """Two trees whose related_docs field contributes ZERO edges: one
        declares nothing (``related_docs: []``), one declares three distinct
        entries that are all declined. The reported figures are an explicit 0
        and 3 -- in both renderers, and reconcilable against the stderr lines.

        FAILS TODAY: the three-entry tree reports nothing, so the two runs
        are indistinguishable. Wrong versions: report only when non-zero;
        omit the zero; cap or dedupe the count.
        """
        three = [declined_mapping(_DIR, tag) for tag in ("a", "b", "c")]
        figures = {}
        for label, entries in (("zero", []), ("three", three)):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                _build(root, entries)
                result, payload = run_json(root)
                text = run_cli(root)
            self.assertEqual([], related_docs_edges(payload, _SOURCE_ID), msg=f"{label}: control, no edges")
            figures[label] = (
                declined_from_json(payload),
                declined_from_text(text.stdout),
                len(stderr_lines_naming(result.stderr, "related_docs")),
            )

        self.assertEqual((0, 0, 0), figures["zero"], msg="zero must be STATED as 0 (json, text, stderr lines)")
        self.assertEqual((3, 3, 3), figures["three"], msg="three declined entries: json, text, stderr lines")
        self.assertNotEqual(figures["zero"], figures["three"])

    def test_km_kgs_100d_3_i_accepted_entries_still_contribute_and_the_build_exits_zero(self) -> None:
        # covers: KM-KGS-100d-3-i
        # angle: failure
        """The declined entry is FIRST, followed by two accepted entries. The
        build exits 0, both accepted edges are in the map in order, nothing
        was made of the declined entry, and the decline IS announced (one
        stderr line, figure 1) -- so the arm is red until the decline path
        exists, and green only if nothing was broken to get there.

        Wrong versions this catches: raising/exiting non-zero on a decline;
        stopping the field at the first declined entry (accepted entries
        after it lost); emitting an edge for the declined element.
        FAILS TODAY: exit 0 and both edges hold, but the decline is silent.
        """
        entries = [declined_mapping(_DIR, "first"), raw_path(_DIR, _GOOD_ONE), raw_path(_DIR, _GOOD_TWO)]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build(root, entries)
            result = run_cli(root, ["--format", "json"])
            self.assertEqual(0, result.returncode, msg=f"a decline must not fail the build: {result.stderr}")
            _res, payload = run_json(root)

        edges = related_docs_edges(payload, _SOURCE_ID)
        self.assertEqual(2, len(edges), msg=f"two accepted edges, none for the declined entry: {edges!r}")
        self.assertTrue(target_matches(edges[0][0], _DIR, _GOOD_ONE), msg=edges)
        self.assertTrue(target_matches(edges[1][0], _DIR, _GOOD_TWO), msg=edges)
        self.assertEqual(1, len(stderr_lines_naming(result.stderr, "declined-first-first")), msg=result.stderr)
        self.assertEqual(1, declined_from_json(payload), msg="declined figure beside the two edges")


_SECOND_FIELD = "see_also"
_TEXT_FIELD_FIGURES = r"{field}\W.*?edges\D*(\d+).*?declined\D*(\d+)"


def _two_field_surface() -> dict:
    """Test-only surface declaring TWO relationship fields on one document."""
    return {EXTRA_SURFACE: {"path": f"{EXTRA_SURFACE_DIR}/", "edge_fields": ["related_docs", _SECOND_FIELD]}}


def _build_two_fields(root: Path, entries: list) -> None:
    """related_docs carries *entries*; see_also is present but empty."""
    write_paths_json(root, _two_field_surface())
    write_target_docs(root, _DIR, [_GOOD_ONE, _GOOD_TWO])
    write_doc(
        root / _DIR / f"{_SOURCE_ID}.md",
        {"id": _SOURCE_ID, "title": "Source", "related_docs": entries, _SECOND_FIELD: []},
    )


def _field_figures_from_json(payload: dict, field: str):
    """(edges, declined) for *field* from ``payload["field_counts"]``, else None."""
    entry = (payload.get("field_counts") or {}).get(field)
    if not isinstance(entry, dict):
        return None
    return entry.get("edges"), entry.get("declined")


def _field_figures_from_text(text_stdout: str, field: str):
    """(edges, declined) from the text line naming *field*, else None."""
    pattern = re.compile(_TEXT_FIELD_FIGURES.format(field=re.escape(field)), re.IGNORECASE)
    for line in text_stdout.splitlines():
        if line.startswith("Surfaces:"):
            continue
        match = pattern.search(line)
        if match:
            return int(match.group(1)), int(match.group(2))
    return None


class TestKmKgs100d3IPerFieldCounts(unittest.TestCase):
    def test_km_kgs_100d_3_i_declined_count_is_stated_per_field_beside_that_fields_edge_count(
        self,
    ) -> None:
        # covers: KM-KGS-100d-3-i
        # angle: discrimination
        """The build states, PER FIELD, the edges the field contributed and the
        entries it declined, so a field that contributed nothing is
        distinguishable from a field that had nothing to contribute.

        OUTPUT SHAPE THE CODER MUST IMPLEMENT (the AC pins no key names; this
        test does):
          JSON: top-level ``field_counts``: a mapping
                ``{<field name>: {"edges": <int>, "declined": <int>}}``
                holding one entry for every edge field the build looked at,
                zero included, never omitted.
          text: one line per field (not the ``Surfaces:`` summary line) of the
                form ``Field <name>: edges=<n> declined=<m>``.
        The existing global ``entries_declined`` / ``Entries declined:`` figure
        stays and must equal the sum of the per-field ``declined`` figures.

        Fixture: related_docs = two accepted entries around one declined
        two-key mapping (edges 2 / declined 1); see_also = [] (edges 0 /
        declined 0, the control: it had nothing to contribute).

        FAILS TODAY: only a single global ``entries_declined`` exists, so
        neither field is attributable. Wrong versions: a global-only total;
        counting declines under the wrong field; omitting the zero field.
        """
        entries = _one_declined_between_two_accepted()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build_two_fields(root, entries)
            _res, payload = run_json(root)
            res_text = run_cli(root)

        self.assertEqual(0, res_text.returncode, msg=res_text.stderr)
        self.assertEqual(
            2, len(related_docs_edges(payload, _SOURCE_ID)), msg="control: two accepted related_docs edges"
        )
        self.assertEqual(
            (2, 1),
            _field_figures_from_json(payload, "related_docs"),
            msg=f"JSON field_counts for the failing field; keys={sorted(payload)}",
        )
        self.assertEqual(
            (0, 0),
            _field_figures_from_json(payload, _SECOND_FIELD),
            msg="the empty field must be STATED as edges 0 / declined 0, distinct from the failing field",
        )
        self.assertEqual(
            declined_from_json(payload),
            sum(
                figures[1]
                for figures in (
                    _field_figures_from_json(payload, "related_docs"),
                    _field_figures_from_json(payload, _SECOND_FIELD),
                )
                if figures is not None
            ),
            msg="global total must reconcile with the per-field figures",
        )
        self.assertEqual(
            (2, 1),
            _field_figures_from_text(res_text.stdout, "related_docs"),
            msg=f"text output must carry 'Field related_docs: edges=2 declined=1': {res_text.stdout!r}",
        )
        self.assertEqual(
            (0, 0),
            _field_figures_from_text(res_text.stdout, _SECOND_FIELD),
            msg=f"text output must state the empty field as edges=0 declined=0: {res_text.stdout!r}",
        )


class TestKmKgs100d3IEmptyStringEntryIsNotSilent(unittest.TestCase):
    def test_km_kgs_100d_3_i_empty_string_entry_is_reported_counted_and_does_not_fail_the_build(
        self,
    ) -> None:
        # covers: KM-KGS-100d-3-i
        # angle: discrimination
        """related_docs holds ``""`` beside one accepted entry. The shared
        resolver and the commit guard refuse an empty string, so the map
        builder must not skip it before the resolver: exactly one
        ``ENTRY-DECLINED`` stderr line names the surface, the document and the
        field; the declined figure for related_docs is 1; the accepted entry
        still yields its one edge; the build exits 0.

        FAILS TODAY: knowledge_query.extract_edges does ``if item == "":
        continue`` ahead of the resolver, so the empty entry is passed over in
        silence (no stderr line, declined figure 0). Wrong versions: the early
        skip kept; the empty entry counted but not announced; the build
        failing on it; the accepted entry lost.
        """
        entries = ["", raw_path(_DIR, _GOOD_ONE)]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build(root, entries)
            result = run_cli(root, ["--format", "json"])
            self.assertEqual(0, result.returncode, msg=f"a decline must not fail the build: {result.stderr}")
            payload = json.loads(result.stdout)

        lines = stderr_lines_naming(result.stderr, "ENTRY-DECLINED", EXTRA_SURFACE, _SOURCE_REL, "related_docs")
        self.assertEqual(
            1, len(lines), msg=f"empty entry must be announced exactly once; stderr={result.stderr!r}"
        )
        edges = related_docs_edges(payload, _SOURCE_ID)
        self.assertEqual(1, len(edges), msg=f"the accepted entry still contributes its edge: {edges!r}")
        self.assertTrue(target_matches(edges[0][0], _DIR, _GOOD_ONE), msg=edges)
        self.assertEqual(1, declined_from_json(payload), msg="the empty entry counts as declined")
        self.assertEqual(
            (1, 1),
            _field_figures_from_json(payload, "related_docs"),
            msg="related_docs: one edge contributed, one entry (the empty string) declined",
        )


if __name__ == "__main__":
    unittest.main()
