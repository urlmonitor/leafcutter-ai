r"""
MODULE: unit_tests/workflows/test_bo3900d_leading_slash_scanner.py
GOAL: Unit tests for BO-3900d — a POSIX-only absolute-path test added to any
    workflow script is caught automatically, over a set of scripts that is
    DERIVED rather than listed.
BUSINESS CONTEXT: a guard against reintroduction is worthless if it examines
    a hand-written file list (the next new script is never looked at) or if
    it refuses everything (discharged by broadening an exemption until it
    means nothing). See unit_tests/workflows/_bo3900d_scanner.py's own
    module docstring for the derivation rule this file exercises.
ARCHITECTURE: The scanner accepts a target directory (BO-3900d's
    it_requirements), so every seeded-shape and count-derivation test here
    runs against a tempdir of FIXTURE copies and never writes to
    templates/workflows-js/. Only the real-artifact test scans the genuine
    directory.
"""
from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from unit_tests.workflows import _bo3900d_scanner as scanner  # noqa: E402

_REAL_SCRIPTS_DIR = _REPO_ROOT / "templates" / "workflows-js"


class TestExaminedCountIsDerivedFromTheDirectory(unittest.TestCase):
    def test_every_workflow_script_is_examined_and_the_count_is_derived(self) -> None:
        # covers: BO-3900d
        # angle: criterion
        """The stated examined count equals the number of .js scripts in the
        directory, and adding a temporary script in a FIXTURE COPY raises it
        by one — proving the count comes from a directory listing, not a
        hard-coded number.
        """
        with tempfile.TemporaryDirectory() as tmp:
            fixture_dir = Path(tmp)
            for name in ("a.js", "b.js", "c.js"):
                (fixture_dir / name).write_text("// no offending shape here\n", encoding="utf-8")

            before = scanner.scan_workflow_scripts(fixture_dir)
            self.assertEqual(before.examined_count, 3)

            (fixture_dir / "d.js").write_text("// a ninth script, or a fourth here\n", encoding="utf-8")
            after = scanner.scan_workflow_scripts(fixture_dir)
            self.assertEqual(after.examined_count, 4)


class TestEachLeadingSlashShapeIsReported(unittest.TestCase):
    def test_each_leading_slash_absoluteness_shape_is_reported_with_script_line_and_expression(
        self,
    ) -> None:
        # covers: BO-3900d
        # angle: failure
        """A seeded fixture script carrying each of the five shapes fails the
        check once per shape, naming the script, the 1-based line, and the
        matched expression text — not just the first finding.
        """
        seeded = "\n".join(
            [
                "function classify(p) {",
                '  if (p.startsWith("/")) { return "a"; }',
                "  if (p.startsWith('/')) { return 'b'; }",
                '  if (p[0] === "/") { return "c"; }',
                "  if (p.charAt(0) === '/') { return 'd'; }",
                "  const re = /^\\//;",
                "  return re.test(p) ? 'e' : null;",
                "}",
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            fixture_dir = Path(tmp)
            (fixture_dir / "seeded.js").write_text(seeded, encoding="utf-8")
            result = scanner.scan_workflow_scripts(fixture_dir)

        self.assertEqual(len(result.findings), 5, result.findings)
        shapes_found = {f.expression for f in result.findings}
        self.assertEqual(len(shapes_found), 5, result.findings)
        for f in result.findings:
            self.assertEqual(f.script, "seeded.js")
            self.assertGreaterEqual(f.line, 1)


class TestSharedClassificationAndReasonedMarkerAreAcceptable(unittest.TestCase):
    def test_shared_classification_and_reasoned_marker_are_not_reported(self) -> None:
        # covers: BO-3900d
        # angle: boundary
        """Paired acceptable inputs: a leading-'/' test that sits inside a
        classification function that ALSO recognises drive-letter and UNC
        forms is not reported; a leading-'/' test carrying a reasoned
        NOT-A-PATH marker is not reported; a marker with NO reason text is
        reported as though it were absent.
        """
        shared_classification = "\n".join(
            [
                "function classifyPathForm(input) {",
                "  if (/^(\\\\\\\\|\\/\\/)[^\\\\/]/.test(input)) { return 'absolute'; }",
                "  if (/^[A-Za-z]:[\\\\/]/.test(input)) { return 'absolute'; }",
                '  if (input.charAt(0) === "/") { return "absolute"; }',
                "  return 'relative';",
                "}",
            ]
        )
        reasoned_marker = "\n".join(
            [
                "function routeUrl(p) {",
                "  // NOT-A-PATH: URL route, not a file-system path",
                '  if (p.startsWith("/")) { return "api"; }',
                "  return 'other';",
                "}",
            ]
        )
        unreasoned_marker = "\n".join(
            [
                "function other(p) {",
                "  // NOT-A-PATH:",
                '  if (p.startsWith("/")) { return "x"; }',
                "  return null;",
                "}",
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            fixture_dir = Path(tmp)
            (fixture_dir / "shared.js").write_text(shared_classification, encoding="utf-8")
            (fixture_dir / "reasoned.js").write_text(reasoned_marker, encoding="utf-8")
            (fixture_dir / "unreasoned.js").write_text(unreasoned_marker, encoding="utf-8")
            result = scanner.scan_workflow_scripts(fixture_dir)

        reported_scripts = {f.script for f in result.findings}
        self.assertNotIn("shared.js", reported_scripts)
        self.assertNotIn("reasoned.js", reported_scripts)
        self.assertIn("unreasoned.js", reported_scripts)


class TestCheckPassesOnTheRealWorkflowScripts(unittest.TestCase):
    def test_check_passes_on_the_real_workflow_scripts(self) -> None:
        # covers: BO-3900d
        # angle: real_artifact
        """Run over the real templates/workflows-js directory after BO-3900,
        the check passes, states an examined count equal to the directory's
        actual script count, and completes in under 5 seconds.
        """
        real_count = len(list(_REAL_SCRIPTS_DIR.glob("*.js")))
        started = time.monotonic()
        result = scanner.scan_workflow_scripts(_REAL_SCRIPTS_DIR)
        elapsed = time.monotonic() - started

        self.assertEqual(result.examined_count, real_count)
        self.assertEqual(result.findings, [], result.findings)
        self.assertLess(elapsed, 5.0)


if __name__ == "__main__":
    unittest.main()
