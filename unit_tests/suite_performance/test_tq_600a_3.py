"""
RED test stubs for TQ-600a-3 -- "Read-only is proved, not promised -- a run
that dirties the shared layout says so and names the test."

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-3.yaml

ASSUMED PRODUCTION CONTRACT (scripts/suite_performance/shared_layout_integrity.py,
new file, does not exist yet -- python-coder implements against these exact
names; every symbol below is REQUIRED, not illustrative):

Low-level functions (importable directly, exercised by the unit-angle tests):

    def capture_record(root: Path) -> dict:
        Walks `root` recursively and returns
        {"files": {relpath_posix_str: sha256_hexdigest, ...}, "count": int}.
        SKIPS any directory literally named "__pycache__" and any file whose
        name ends in ".pyc" (Implementation Notes point 3 -- the false-
        positive control this repo has already been bitten by once). Digest
        is a CONTENT digest (sha256 of the file's bytes) -- NEVER mtime or
        size (Implementation Notes point 2: a deploy writes its whole tree
        within one second, so mtime-based comparison is blind to a same-
        second rewrite).

    def compare_record(root: Path, record: dict, *, consumer_count: int = 0,
                        offending_test: str | None = None) -> dict:
        Re-walks `root` with the IDENTICAL exclusion rules as capture_record,
        and diffs its current file set + digests against `record["files"]`.
        Returns:
          {
            "compared_count": int,   # len(record["files"]) -- the size of
                                      # the BASELINE, so a comparison whose
                                      # baseline was itself captured over an
                                      # empty/absent root is distinguishable
                                      # at 0 from one that inspected a real
                                      # tree and found no differences.
            "added":   [relpath, ...],  # present now, absent from record
            "changed": [relpath, ...],  # present in both, digest differs
            "missing": [relpath, ...],  # present in record, absent now
            "consumer_count": consumer_count,   # passed through verbatim
            "offending_test": offending_test,   # passed through verbatim
            "files_ok": bool,   # False when compared_count == 0 OR any of
                                 # added/changed/missing is non-empty. A
                                 # comparison must NEVER report files_ok=True
                                 # merely because the three lists are empty
                                 # when compared_count is ALSO 0 -- that is
                                 # exactly the AC-store-validator defect this
                                 # AC's Implementation Notes name by name.
            "had_consumers": consumer_count > 0,
          }
        The added-file check MUST walk the UNION of the current tree and the
        recorded file list, never just the recorded list (Implementation
        Notes' one-directional-walk bait: a comparison that iterates only
        `record["files"]` and asks "does this still match" can report
        changed/missing correctly but is structurally blind to a brand-new
        path it never had a reason to look at).

Pytest plugin (session-level; exercised by the integration-angle tests via a
real child `pytest` subprocess, never by calling a hook function directly):

    Registered via an EXPLICIT `-p scripts.suite_performance.
    shared_layout_integrity` override -- this AC's own files_touched names
    ONLY this one file, so (unlike the routing plugin) it is deliberately
    NOT added to pytest.ini's addopts. See _test_helpers_tq_600a_3.py's
    run_integrity_child_session.

    Does NOT eagerly call get_or_produce_shared_layout() at session start
    (that would force a deploy even when zero tests ever consume the shared
    layout, contradicting TQ-600a-1-i's laziness guarantee). Instead it
    detects production via the read-only
    `_shared_layout_coordination.check_published(...)` probe: the record is
    captured, from that now-published root, the FIRST time any
    shared_layout_reader-marked test is observed to have completed setup
    with the shared root already published -- i.e. immediately after the
    single deploy that produced it returns, never lazily on some LATER
    request (Implementation Notes point 1).

    For PER-TEST ATTRIBUTION (the "which test dirtied it" requirement), the
    plugin re-walks and re-compares once after EACH shared_layout_reader-
    marked consumer test completes (the explicitly-requested, more expensive
    per-test attribution mode the Implementation Notes distinguish from the
    cheap default of "digest once at capture and once at comparison"). The
    FIRST consumer whose post-test comparison newly reports a difference
    (that the immediately-prior checkpoint did not) is recorded as
    `offending_test`, by pytest node id.

    At pytest_sessionfinish, writes exactly one JSON report to the path
    named by env var LEAFCUTTER_SHARED_LAYOUT_INTEGRITY_REPORT (no-op if
    unset), shaped like compare_record's return value, with one addition:
    when consumer_count == 0 (no shared_layout_reader-marked test ever ran,
    so the shared layout may never even have been produced), the report is
    {"consumer_count": 0, "compared_count": None, "added": [], "changed":
    [], "missing": [], "offending_test": None, "files_ok": True,
    "had_consumers": False} -- None (not 0) for compared_count is the
    field that makes this state distinguishable from "checked a real,
    unchanged layout" (Implementation Notes' 2026-09-28 clause: a run that
    had nothing to check and a run that checked everything and found it
    untouched must not read the same). The session FAILS (non-zero exit)
    only when files_ok is False; had_consumers being False must NEVER by
    itself fail the session.

REACHABILITY RESOLUTION (BP-1100g-2 -- this AC's test_spec named no entry
point): this is a pytest plugin, not a CLI/hook/slash-command/workflow-step.
Its only real caller is a real, un-augmented-by-import pytest session that
loads it via -p and runs a real deploy + real consumer test through it --
mirroring TQ-600a-1's own test 7 / TQ-600a-5's own test 10 precedent for a
plugin-shaped production surface. See
test_tq_600a_3_reachable_from_entry_point below.

CROSS-LAYER SEAM (BP-1100g-5): the producing side is the REAL
`shared_reference_layout` fixture / `get_or_produce_shared_layout()`
(TQ-600a-1); the consuming side is THIS AC's comparison plugin. Every
integration-angle test in the sibling file `test_tq_600a_3_integration.py`
pipes the producer's real deployed output through a real child pytest
session into the real plugin -- the seam is covered by construction, not by
a separate dedicated test.

FILE SPLIT: the integration-angle tests (1, 2, 7, 8, 9, 10, and the mandatory
reachability test) live in `test_tq_600a_3_integration.py`, split out purely
to keep both files under the repo's GE-127a-1 400-line file-size limit,
mirroring the `test_tq_600a_1.py`/`test_tq_600a_1_multiworker.py` and
`test_tq_600a_5.py`/`test_tq_600a_5_reporting.py` precedents. This file
(`test_tq_600a_3.py`) holds only the low-level, no-subprocess unit-angle
tests (3, 4, 5, 6) that exercise `capture_record`/`compare_record` directly.
"""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.suite_performance.shared_layout_integrity import (
    capture_record,
    compare_record,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestTQ600a3Unit(unittest.TestCase):
    """Low-level, no-subprocess tests (tests 3, 4, 5, 6 -- unit angle)."""

    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "layout"
        self.root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Test 3 -- boundary. NAMED MUTATION: one-directional walk of the
    # recorded file list; an ADDED file is then invisible.
    # ------------------------------------------------------------------
    def test_tq600a_3_an_added_file_and_a_missing_file_are_each_reported(self):
        # covers: TQ-600a-3
        # angle: boundary
        """
        An ADDED file (present now, absent from the record) and a MISSING
        file (present in the record, absent now) are each reported by name.

        NAMED MUTATION this test alone catches: implement the comparison as
        a one-directional walk of `record["files"]` (checking each recorded
        path still exists and still matches). That walk never visits a path
        it has no entry for, so a brand-new file is structurally invisible
        to it -- `added` would stay empty and this test's first assertion
        goes RED, even though `missing` (which that same buggy walk CAN see)
        would still pass.
        """
        _write(self.root / "kept.txt", "unchanged content")
        _write(self.root / "will_be_removed.txt", "goodbye")
        record = capture_record(self.root)

        (self.root / "will_be_removed.txt").unlink()
        _write(self.root / "brand_new.txt", "hello")

        report = compare_record(self.root, record)
        self.assertIn(
            "brand_new.txt",
            report["added"],
            msg=f"added file not reported: {report}",
        )
        self.assertIn(
            "will_be_removed.txt",
            report["missing"],
            msg=f"missing file not reported: {report}",
        )
        self.assertEqual([], report["changed"], msg=f"unexpected changed: {report}")

    # ------------------------------------------------------------------
    # Test 4 -- failure. NAMED MUTATION: compare by mtime and size instead
    # of content digest.
    # ------------------------------------------------------------------
    def test_tq600a_3_a_content_rewrite_with_an_unchanged_modification_time_is_reported(
        self,
    ):
        # covers: TQ-600a-3
        # angle: failure
        """
        A file rewritten to DIFFERENT content of the SAME length, with its
        mtime explicitly restored to the original, is still reported as
        changed.

        NAMED MUTATION this test alone catches: compare by (mtime, size)
        instead of a content digest. Same length + restored mtime is exactly
        the case that mutation cannot distinguish from "untouched" -- this
        test's assertion goes RED under it, even though the boundary test
        above (a real size change) would still pass.
        """
        target = self.root / "rewritten.bin"
        _write(target, "AAAAAAAAAA")
        original_mtime_ns = target.stat().st_mtime_ns
        record = capture_record(self.root)

        target.write_text("BBBBBBBBBB", encoding="utf-8")  # same length, new content
        os.utime(target, ns=(original_mtime_ns, original_mtime_ns))
        self.assertEqual(
            original_mtime_ns,
            target.stat().st_mtime_ns,
            msg="test setup failed to restore mtime -- fixture is broken",
        )

        report = compare_record(self.root, record)
        self.assertIn(
            "rewritten.bin",
            report["changed"],
            msg=f"content rewrite with restored mtime not reported: {report}",
        )

    # ------------------------------------------------------------------
    # Test 5 -- criterion.
    # ------------------------------------------------------------------
    def test_tq600a_3_the_comparison_states_how_many_files_it_compared(self):
        # covers: TQ-600a-3
        # angle: criterion
        """
        The comparison states a `compared_count` that is present, greater
        than zero for a real layout, and equal to the number of files in
        the record.
        """
        for n in range(5):
            _write(self.root / f"file_{n}.txt", f"content {n}")
        record = capture_record(self.root)
        self.assertEqual(5, record["count"], msg=f"unexpected record: {record}")

        report = compare_record(self.root, record)
        self.assertIn("compared_count", report)
        self.assertGreater(report["compared_count"], 0)
        self.assertEqual(len(record["files"]), report["compared_count"])

    # ------------------------------------------------------------------
    # Test 6 -- failure. NAMED MUTATION: return "clean" on an empty file
    # list. This is the AC-store-validator shape, reproduced deliberately.
    # ------------------------------------------------------------------
    def test_tq600a_3_a_comparison_that_inspected_nothing_fails_rather_than_reporting_clean(
        self,
    ):
        # covers: TQ-600a-3
        # angle: failure
        """
        Pointed at an empty layout root, the comparison reports a compared
        count of 0 and a FAILING status (files_ok is False) -- never a
        clean pass. Also exercised against an ABSENT root (never created at
        all), which must fail identically rather than raising.

        NAMED MUTATION this test alone catches: compute
        `files_ok = not (added or changed or missing)` with no additional
        `compared_count > 0` guard. Against a record captured over zero
        files, all three lists are trivially empty, so that formula reports
        files_ok=True -- exactly the AC-store validator's own defect (globbed
        zero files, printed a success-shaped message, exited 0 for eight
        days). This test's assertion goes RED under that mutation.
        """
        empty_record = capture_record(self.root)  # root exists, but is empty
        self.assertEqual(0, empty_record["count"])

        report = compare_record(self.root, empty_record)
        self.assertEqual(0, report["compared_count"])
        self.assertFalse(
            report["files_ok"],
            msg=(
                "a comparison over zero files reported files_ok=True -- "
                f"a comparison that inspected nothing must fail: {report}"
            ),
        )

        absent_root = self.root / "does_not_exist"
        report_absent = compare_record(absent_root, empty_record)
        self.assertEqual(0, report_absent["compared_count"])
        self.assertFalse(
            report_absent["files_ok"],
            msg=f"comparison against an absent root did not fail: {report_absent}",
        )


if __name__ == "__main__":
    unittest.main()
