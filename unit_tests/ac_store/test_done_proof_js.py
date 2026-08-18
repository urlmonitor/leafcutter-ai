"""
MODULE: unit_tests/ac_store/test_done_proof_js.py
GOAL: RED test stubs for BO-2500e-1 through BO-2500e-4 and BO-2500e-6 —
      teaching the done-proof oracle to recognise JavaScript/TypeScript (vitest)
      tests as proof-of-done exactly like it already does for Python (pytest).

=== Public interface contract under test ===

  Location: scripts/ac_store/done_proof.py

    verify_done_eligible(ac_id: str, *, ac_root: Path, test_root: Path) -> dict
      ADDED behaviour:
        - Discovers "// covers:<id>" tags in .ts/.tsx files under test_root.
        - For a JS-only passing vitest: eligible=True.
        - For a JS failing vitest: eligible=False, reason names the file + AC id.
        - A "// covers:<id>" tag whose id is not an active AC is dangling.
        - Mixed (py + ts): eligible only when EVERY linked test in BOTH passes.
        - Python-only ACs: same verdict as before; JS runner NOT invoked.

    run_vitest_and_parse(test_files: list[Path], *, project_dir: Path)
                         -> dict[str, str]
      JS-runner seam.  Returns {<abs-path-str>: "PASSED" | "FAILED"} per file.
      Raises JsRunnerUnavailable when vitest binary cannot be invoked.

    JsRunnerUnavailable — Exception subclass defined in done_proof.py.

  Location: scripts/ac_store/mark_ac_done.py
    mark_ac_done(ac_id, ac_root, *, test_root=None, ...) -> int
      ADDED: a JS-covered passing AC → return 0 (done); a JS-covered failing AC
      → return 3 (gate refused).

=== Mocking strategy ===

  Patch "done_proof.run_vitest_and_parse" in every test that exercises the JS
  path.  AttributeError is raised by patch() when the attribute does not yet
  exist — this is the PRIMARY red mechanism for tests that need the JS runner.
  For JsRunnerUnavailable: use hasattr() / getattr() inside the test body and
  assert its existence; AssertionError is the red mechanism there.

=== Red baseline ===

  All new JS-behaviour tests are RED until python-coder adds
  run_vitest_and_parse and JsRunnerUnavailable to done_proof.py and wires the
  JS path into verify_done_eligible.
  Python-only no-regression tests (BO-2500e-4-i) may already be green.
"""
from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
import unittest.mock
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

# ---------------------------------------------------------------------------
# Repo path wiring — same pattern as test_bo2500a_done_proof.py
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

# verify_done_eligible already exists in done_proof.py — import succeeds now.
import done_proof  # noqa: E402  (for getattr-based checks and mock targeting)
from done_proof import verify_done_eligible  # noqa: E402

# mark_ac_done already exists — import succeeds.
from mark_ac_done import mark_ac_done as _mark_done  # noqa: E402


# ---------------------------------------------------------------------------
# Shared fixture helpers (mandate: yaml.safe_dump, not hand-typed literals)
# ---------------------------------------------------------------------------


def _write_ac(
    ac_root: Path,
    ac_id: str,
    *,
    status: str = "active",
    work_status: str = "todo",
) -> Path:
    """Write a minimal AC YAML using yaml.safe_dump (fixture-authenticity mandate).

    Args:
        ac_root: Root directory of the synthetic AC store.
        ac_id: Identifier for the AC.
        status: AC lifecycle status.
        work_status: AC work status.

    Returns:
        Path to the written YAML file.
    """
    subdir = ac_root / "test-component"
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{ac_id}.yaml"
    data: dict = {
        "id": ac_id,
        "title": f"Synthetic test AC {ac_id}",
        "component": "build-orchestration",
        "level": "L2",
        "status": status,
        "work_status": work_status,
        "readiness": "draft",
        "priority": "medium",
        "depends_on": [],
        "amended_by": [],
        "covered_by": [],
        "implemented_by": [],
        "superseded_by": None,
    }
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _write_py_test(test_root: Path, filename: str, content: str) -> Path:
    """Write a Python test file (real .py with genuine test body).

    Args:
        test_root: Directory to write the test file into.
        filename: Filename (must end in .py).
        content: Python source; leading whitespace is dedented.

    Returns:
        Path to the written file.
    """
    test_root.mkdir(parents=True, exist_ok=True)
    path = test_root / filename
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


def _write_ts_test(test_root: Path, filename: str, content: str) -> Path:
    """Write a TypeScript/Vitest test stub (real .ts/.tsx file on disk).

    The file contains "// covers:<id>" comment tags and a minimal vitest
    test body.  The actual test execution is mocked via run_vitest_and_parse;
    the file only needs to exist on disk for tag-discovery assertions.

    Args:
        test_root: Directory to write the test file into.
        filename: Filename (must end in .ts or .tsx).
        content: TypeScript source; leading whitespace is dedented.

    Returns:
        Path to the written file.
    """
    test_root.mkdir(parents=True, exist_ok=True)
    path = test_root / filename
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# BO-2500e-1 — JS "// covers:" tags are discovered and linked
# ---------------------------------------------------------------------------


class TestJsCoversTagDiscovery(unittest.TestCase):
    """BO-2500e-1: verify_done_eligible discovers "// covers:" in .ts/.tsx files."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.ac_id = "BO-E1-TAG-001"
        _write_ac(self.ac_root, self.ac_id, status="active")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_js_covers_tag_discovered_and_linked(self) -> None:
        # covers: BO-2500e-1
        """A "// covers:<id>" tag in a .ts test file must be discovered and linked.

        To make this test green, verify_done_eligible must:
        - Scan .ts/.tsx files under test_root for "// covers:<id>" comments.
        - Detect that a passing vitest result for the linked .ts file means the
          AC is covered.
        - Return eligible=True (when run_vitest_and_parse returns PASSED).

        RED mechanism: patch("done_proof.run_vitest_and_parse") raises
        AttributeError because run_vitest_and_parse does not exist yet.
        """
        ts_path = _write_ts_test(
            self.test_root,
            "someFeature.test.ts",
            f"""\
            import {{ test, expect }} from 'vitest'

            test('covers the AC', () => {{
              // covers: {self.ac_id}
              expect(true).toBe(true)
            }})
            """,
        )

        passing_results = {str(ts_path): "PASSED"}

        with patch(
            "done_proof.run_vitest_and_parse",
            return_value=passing_results,
        ):
            verdict = verify_done_eligible(
                self.ac_id,
                ac_root=self.ac_root,
                test_root=self.test_root,
            )

        self.assertTrue(
            verdict["eligible"],
            "A JS-covered AC with a PASSED vitest result must be eligible. "
            "verify_done_eligible must discover '// covers:' tags in .ts files.",
        )

    def test_js_and_python_covers_use_same_seam(self) -> None:
        # covers: BO-2500e-1
        """The same tag-extraction seam must handle both "# covers:" and "// covers:".

        The shared-seam property is observable: both .py and .ts covers tags
        for the same AC must be found, meaning neither tag type is silently
        dropped.  The test asserts that when a .py tag (passing) AND a .ts tag
        (mocked PASSED) both exist, the verdict reflects both.

        RED mechanism: patch("done_proof.run_vitest_and_parse") raises
        AttributeError because run_vitest_and_parse does not exist yet.
        """
        # Python test — will actually run via pytest subprocess
        _write_py_test(
            self.test_root,
            "test_py_cover.py",
            f"""\
            def test_py_covers():
                # covers: {self.ac_id}
                pass  # passes genuinely
            """,
        )
        ts_path = _write_ts_test(
            self.test_root,
            "tsFeature.test.ts",
            f"""\
            import {{ test, expect }} from 'vitest'

            test('ts covers', () => {{
              // covers: {self.ac_id}
              expect(1).toBe(1)
            }})
            """,
        )

        passing_results = {str(ts_path): "PASSED"}

        with patch(
            "done_proof.run_vitest_and_parse",
            return_value=passing_results,
        ):
            verdict = verify_done_eligible(
                self.ac_id,
                ac_root=self.ac_root,
                test_root=self.test_root,
            )

        # Both .py and .ts tests are passing — eligible must be True.
        self.assertTrue(
            verdict["eligible"],
            "With both passing .py and passing .ts covers tests, eligible must be True. "
            "The shared seam must discover both tag types.",
        )
        # At least the py test appears in passing_tests.
        passing = verdict.get("passing_tests", [])
        self.assertTrue(
            len(passing) >= 1,
            "The passing .py test must appear in passing_tests when both lang tests pass.",
        )

    def test_js_covers_tag_for_nonactive_ac_does_not_count(self) -> None:
        # covers: BO-2500e-1-i
        """A "// covers:<deprecated-id>" tag in a .ts file must NOT satisfy any active AC.

        The deprecated AC's covers tag is dangling.  It must not propagate
        coverage to the active AC being evaluated.

        PARTIAL RED mechanism: the active AC has no valid covers test (eligible=False
        is already true via Python path).  The RED-specific assertion is that the
        dangling tag from the .ts file appears in dangling_tags with a .ts location —
        which requires the implementation to scan .ts files for dangling detection.
        AssertionError: current impl does not scan .ts files for dangling tags.
        """
        deprecated_id = "BO-E1-TAG-DEPR"
        _write_ac(self.ac_root, deprecated_id, status="deprecated")

        _write_ts_test(
            self.test_root,
            "deprecatedCover.test.ts",
            f"""\
            import {{ test, expect }} from 'vitest'

            test('tagged for deprecated AC', () => {{
              // covers: {deprecated_id}
              expect(true).toBe(true)
            }})
            """,
        )

        verdict = verify_done_eligible(
            self.ac_id,
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        # The active AC must not be eligible (no valid covers test).
        self.assertFalse(
            verdict["eligible"],
            "A .ts tag for a deprecated AC must NOT satisfy the active AC's done proof.",
        )

        # RED-specific assertion: the .ts dangling tag must appear in dangling_tags
        # with a .ts location.  Current impl does not scan .ts files → AssertionError.
        dangling = verdict.get("dangling_tags", [])
        ts_dangling_locations = [
            d.get("location", "")
            for d in dangling
            if ".ts" in d.get("location", "")
        ]
        self.assertTrue(
            len(ts_dangling_locations) > 0,
            "The deprecated AC's '// covers:' tag in the .ts file must appear in "
            "dangling_tags with a .ts location. "
            "verify_done_eligible must scan .ts files for dangling tag detection.",
        )

    def test_dangling_js_covers_tag_is_flagged(self) -> None:
        # covers: BO-2500e-1-i
        """A "// covers:<nonexistent-id>" tag in a .ts file must be reported as dangling.

        The nonexistent AC id is not in the store at all.  The dangling entry
        must include the .ts file location.

        RED mechanism: AssertionError — current impl does not scan .ts files,
        so no .ts entry appears in dangling_tags.
        """
        nonexistent_id = "BO-E1-GHOST-TS-999"

        _write_ts_test(
            self.test_root,
            "ghostCover.test.ts",
            f"""\
            import {{ test, expect }} from 'vitest'

            test('tags a nonexistent AC', () => {{
              // covers: {nonexistent_id}
              expect(true).toBe(true)
            }})
            """,
        )

        verdict = verify_done_eligible(
            self.ac_id,
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        dangling = verdict.get("dangling_tags", [])
        dangling_ids = [d.get("id", "") for d in dangling]

        self.assertIn(
            nonexistent_id,
            dangling_ids,
            f"A '// covers: {nonexistent_id}' tag in a .ts file must appear in "
            "dangling_tags. Current impl does not scan .ts files → AssertionError.",
        )

        # The location must name the .ts file.
        ts_location_entries = [
            d for d in dangling
            if d.get("id") == nonexistent_id and ".ts" in d.get("location", "")
        ]
        self.assertTrue(
            len(ts_location_entries) > 0,
            "The dangling_tags entry for the .ts covers tag must include a .ts location.",
        )


# ---------------------------------------------------------------------------
# BO-2500e-2 — Passing vitest makes AC eligible
# ---------------------------------------------------------------------------


class TestVitestIntegration(unittest.TestCase):
    """BO-2500e-2: A passing vitest result makes a JS-covered AC eligible."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.ac_id = "BO-E2-VITEST-001"
        _write_ac(self.ac_root, self.ac_id, status="active")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_passing_vitest_makes_js_ac_eligible(self) -> None:
        # covers: BO-2500e-2
        """When run_vitest_and_parse returns PASSED for a linked .ts file, eligible=True.

        To make this green:
        - verify_done_eligible must call run_vitest_and_parse for discovered .ts files.
        - When every result is PASSED, the AC is eligible.

        RED mechanism: patch("done_proof.run_vitest_and_parse") raises AttributeError.
        """
        ts_path = _write_ts_test(
            self.test_root,
            "passingFeature.test.ts",
            f"""\
            import {{ test, expect }} from 'vitest'

            test('passing test', () => {{
              // covers: {self.ac_id}
              expect(2 + 2).toBe(4)
            }})
            """,
        )

        with patch(
            "done_proof.run_vitest_and_parse",
            return_value={str(ts_path): "PASSED"},
        ):
            verdict = verify_done_eligible(
                self.ac_id,
                ac_root=self.ac_root,
                test_root=self.test_root,
            )

        self.assertTrue(
            verdict["eligible"],
            "run_vitest_and_parse returning PASSED must make the JS-covered AC eligible.",
        )
        self.assertEqual(
            verdict.get("reason", ""),
            "",
            "reason must be empty when the JS AC is eligible.",
        )

    def test_oracle_actually_invokes_vitest(self) -> None:
        # covers: BO-2500e-2
        """verify_done_eligible must call run_vitest_and_parse when a .ts file is linked.

        The assertion is that the JS-runner seam is actually invoked with the
        discovered .ts file, not merely detected.

        RED mechanism: patch("done_proof.run_vitest_and_parse") raises AttributeError.
        """
        ts_path = _write_ts_test(
            self.test_root,
            "invokeCheck.test.ts",
            f"""\
            import {{ test }} from 'vitest'

            test('should invoke vitest', () => {{
              // covers: {self.ac_id}
            }})
            """,
        )

        mock_runner = MagicMock(return_value={str(ts_path): "PASSED"})

        with patch("done_proof.run_vitest_and_parse", mock_runner):
            verify_done_eligible(
                self.ac_id,
                ac_root=self.ac_root,
                test_root=self.test_root,
            )

        mock_runner.assert_called_once()
        # The .ts file must have been passed to the runner.
        call_args = mock_runner.call_args
        called_files = call_args[0][0] if call_args[0] else call_args[1].get("test_files", [])
        called_file_strs = [str(p) for p in called_files]
        self.assertIn(
            str(ts_path),
            called_file_strs,
            "run_vitest_and_parse must be called with the discovered .ts file path.",
        )

    def test_mixed_coverage_eligible_only_when_all_pass(self) -> None:
        # covers: BO-2500e-2-i
        """Mixed (.py + .ts) coverage: eligible only when ALL linked tests pass.

        A passing .py test AND a passing (mocked) .ts test must both contribute
        to eligibility.  When both pass, eligible=True.

        RED mechanism: patch("done_proof.run_vitest_and_parse") raises AttributeError.
        """
        _write_py_test(
            self.test_root,
            "test_py_mixed.py",
            f"""\
            def test_py_mixed_passes():
                # covers: {self.ac_id}
                pass  # genuinely passes
            """,
        )
        ts_path = _write_ts_test(
            self.test_root,
            "mixedPassing.test.ts",
            f"""\
            import {{ test, expect }} from 'vitest'

            test('mixed passing ts', () => {{
              // covers: {self.ac_id}
              expect(true).toBe(true)
            }})
            """,
        )

        with patch(
            "done_proof.run_vitest_and_parse",
            return_value={str(ts_path): "PASSED"},
        ):
            verdict = verify_done_eligible(
                self.ac_id,
                ac_root=self.ac_root,
                test_root=self.test_root,
            )

        self.assertTrue(
            verdict["eligible"],
            "Mixed coverage: both .py (passing) and .ts (PASSED) must yield eligible=True.",
        )

    def test_mixed_coverage_blocked_when_either_fails(self) -> None:
        # covers: BO-2500e-2-i
        """Mixed (.py + .ts) coverage: eligible=False when the .ts test FAILS.

        The passing .py test does not rescue eligibility — every linked test
        in every language must pass.  The reason must name the failing .ts file.

        RED mechanism: patch("done_proof.run_vitest_and_parse") raises AttributeError.
        """
        _write_py_test(
            self.test_root,
            "test_py_mixed_pass.py",
            f"""\
            def test_py_mixed_passes():
                # covers: {self.ac_id}
                pass  # passes — does not rescue the failing .ts test
            """,
        )
        ts_path = _write_ts_test(
            self.test_root,
            "mixedFailing.test.ts",
            f"""\
            import {{ test, expect }} from 'vitest'

            test('mixed failing ts', () => {{
              // covers: {self.ac_id}
              expect(false).toBe(true)  // intentional failure
            }})
            """,
        )

        with patch(
            "done_proof.run_vitest_and_parse",
            return_value={str(ts_path): "FAILED"},
        ):
            verdict = verify_done_eligible(
                self.ac_id,
                ac_root=self.ac_root,
                test_root=self.test_root,
            )

        self.assertFalse(
            verdict["eligible"],
            "Mixed coverage: a FAILED .ts test must block eligibility even if "
            "the .py test passes.",
        )
        reason = verdict.get("reason", "")
        self.assertTrue(
            len(reason) > 0,
            "The reason must be non-empty when the .ts test fails.",
        )
        # The reason must name either the failing .ts file or the AC id.
        failing = verdict.get("failing_tests", [])
        self.assertTrue(
            len(failing) > 0,
            "The FAILED .ts test must appear in failing_tests.",
        )


# ---------------------------------------------------------------------------
# BO-2500e-3 — Failing vitest blocks the AC; unavailable runner fails closed
# ---------------------------------------------------------------------------


class TestFailingVitestBlocking(unittest.TestCase):
    """BO-2500e-3: A FAILED or unavailable vitest blocks eligibility (fail-closed)."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.ac_id = "BO-E3-FAIL-001"
        _write_ac(self.ac_root, self.ac_id, status="active")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_failing_vitest_blocks_js_ac(self) -> None:
        # covers: BO-2500e-3
        """When run_vitest_and_parse returns FAILED, eligible=False.

        To make this green:
        - verify_done_eligible must treat a FAILED vitest result as non-passing.
        - eligible must be False.

        RED mechanism: patch("done_proof.run_vitest_and_parse") raises AttributeError.
        """
        ts_path = _write_ts_test(
            self.test_root,
            "failingFeature.test.ts",
            f"""\
            import {{ test, expect }} from 'vitest'

            test('always fails', () => {{
              // covers: {self.ac_id}
              expect(false).toBe(true)  // intentional failure
            }})
            """,
        )

        with patch(
            "done_proof.run_vitest_and_parse",
            return_value={str(ts_path): "FAILED"},
        ):
            verdict = verify_done_eligible(
                self.ac_id,
                ac_root=self.ac_root,
                test_root=self.test_root,
            )

        self.assertFalse(
            verdict["eligible"],
            "A FAILED vitest result must make the JS-covered AC ineligible.",
        )
        failing = verdict.get("failing_tests", [])
        self.assertTrue(
            len(failing) > 0,
            "The FAILED .ts test must appear in failing_tests.",
        )

    def test_failing_js_verdict_names_test_and_ac(self) -> None:
        # covers: BO-2500e-3
        """The reason for a FAILED vitest must name both the .ts file and the AC id.

        The reason string must be machine-readable — it must include the AC id
        so the caller knows which AC was blocked, and the file name so the
        developer can locate the failing test.

        RED mechanism: patch("done_proof.run_vitest_and_parse") raises AttributeError.
        """
        ts_filename = "namedFailing.test.ts"
        ts_path = _write_ts_test(
            self.test_root,
            ts_filename,
            f"""\
            import {{ test, expect }} from 'vitest'

            test('named failing test', () => {{
              // covers: {self.ac_id}
              expect(1).toBe(2)  // intentional failure
            }})
            """,
        )

        with patch(
            "done_proof.run_vitest_and_parse",
            return_value={str(ts_path): "FAILED"},
        ):
            verdict = verify_done_eligible(
                self.ac_id,
                ac_root=self.ac_root,
                test_root=self.test_root,
            )

        self.assertFalse(verdict["eligible"])
        reason = verdict.get("reason", "")
        self.assertIn(
            self.ac_id,
            reason,
            "The reason must name the AC id so the caller knows which AC was blocked.",
        )
        # The reason or failing_tests must reference the .ts file.
        all_names = reason + " ".join(verdict.get("failing_tests", []))
        self.assertTrue(
            ".ts" in all_names or ts_filename in all_names,
            "The reason or failing_tests must reference the failing .ts file. "
            f"Got reason={reason!r}, failing_tests={verdict.get('failing_tests')}",
        )

    def test_unavailable_js_runner_fails_closed(self) -> None:
        # covers: BO-2500e-3-i
        """When run_vitest_and_parse raises JsRunnerUnavailable, eligible=False.

        An unavailable vitest binary must NOT be treated as a pass or a skip.
        The oracle must fail CLOSED — ineligible with a reason naming the
        "JS runner unavailable" condition.

        RED mechanism (primary): hasattr assertion fails because JsRunnerUnavailable
        does not yet exist in done_proof.
        """
        JsRunnerUnavailable = getattr(done_proof, "JsRunnerUnavailable", None)
        self.assertIsNotNone(
            JsRunnerUnavailable,
            "done_proof.JsRunnerUnavailable must be defined as an Exception subclass. "
            "It does not exist yet — this assertion is the primary red mechanism.",
        )

        _write_ts_test(
            self.test_root,
            "unavailableRunner.test.ts",
            f"""\
            import {{ test }} from 'vitest'

            test('runner unavailable', () => {{
              // covers: {self.ac_id}
            }})
            """,
        )

        with patch(
            "done_proof.run_vitest_and_parse",
            side_effect=JsRunnerUnavailable("vitest binary not found"),
        ):
            verdict = verify_done_eligible(
                self.ac_id,
                ac_root=self.ac_root,
                test_root=self.test_root,
            )

        self.assertFalse(
            verdict["eligible"],
            "JsRunnerUnavailable must cause eligible=False (fail-closed). "
            "An unavailable runner must NEVER be treated as a pass.",
        )
        reason = verdict.get("reason", "")
        self.assertTrue(
            len(reason) > 0,
            "The reason must be non-empty when the JS runner is unavailable.",
        )
        # The reason must name the unavailability condition.
        reason_lower = reason.lower()
        self.assertTrue(
            "unavailable" in reason_lower
            or "runner" in reason_lower
            or "vitest" in reason_lower
            or "js" in reason_lower,
            f"The reason must reference the JS runner unavailability. Got: {reason!r}",
        )

    def test_missing_runner_not_treated_as_pass_or_skip(self) -> None:
        # covers: BO-2500e-3-i
        """JsRunnerUnavailable must produce ineligible=False — never True or None.

        The fail-closed contract: eligible must be explicitly False (bool),
        not None or True.  An absent runner must not silently skip the check.

        RED mechanism (primary): hasattr assertion fails because JsRunnerUnavailable
        does not yet exist.
        """
        JsRunnerUnavailable = getattr(done_proof, "JsRunnerUnavailable", None)
        self.assertIsNotNone(
            JsRunnerUnavailable,
            "done_proof.JsRunnerUnavailable must exist to test the fail-closed contract.",
        )

        _write_ts_test(
            self.test_root,
            "missingRunnerCheck.test.ts",
            f"""\
            import {{ test }} from 'vitest'

            test('missing runner', () => {{
              // covers: {self.ac_id}
            }})
            """,
        )

        with patch(
            "done_proof.run_vitest_and_parse",
            side_effect=JsRunnerUnavailable("missing node_modules/.bin/vitest"),
        ):
            verdict = verify_done_eligible(
                self.ac_id,
                ac_root=self.ac_root,
                test_root=self.test_root,
            )

        eligible = verdict.get("eligible")
        self.assertIs(
            eligible,
            False,
            "eligible must be exactly False (not None, not True) when the JS runner "
            "is unavailable. The oracle must fail CLOSED, never skip. "
            f"Got eligible={eligible!r}",
        )


# ---------------------------------------------------------------------------
# BO-2500e-4 — mark_ac_done handles JS-covered ACs via the shared path
# ---------------------------------------------------------------------------


class TestMarkAcDoneJsPath(unittest.TestCase):
    """BO-2500e-4: mark_ac_done treats JS-covered ACs via the same eligibility path."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.ac_id = "BO-E4-MARK-001"
        _write_ac(self.ac_root, self.ac_id, status="active", work_status="todo")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_js_covered_ac_marked_done_via_shared_path(self) -> None:
        # covers: BO-2500e-4
        """A JS-covered AC with a PASSED vitest is marked done (return 0).

        mark_ac_done must call verify_done_eligible, which calls
        run_vitest_and_parse for the .ts file.  When the mocked runner says
        PASSED, mark_ac_done must succeed (return 0) and set work_status: done.

        RED mechanism: patch("done_proof.run_vitest_and_parse") raises AttributeError.
        """
        ts_path = _write_ts_test(
            self.test_root,
            "markDonePassing.test.ts",
            f"""\
            import {{ test, expect }} from 'vitest'

            test('js covered AC', () => {{
              // covers: {self.ac_id}
              expect(true).toBe(true)
            }})
            """,
        )

        with patch(
            "done_proof.run_vitest_and_parse",
            return_value={str(ts_path): "PASSED"},
        ):
            result = _mark_done(
                self.ac_id,
                self.ac_root,
                test_root=self.test_root,
            )

        self.assertEqual(
            result,
            0,
            "mark_ac_done must return 0 when the JS-covered AC's vitest passes. "
            f"Got return code {result}.",
        )

        ac_yaml = self.ac_root / "test-component" / f"{self.ac_id}.yaml"
        data = yaml.safe_load(ac_yaml.read_text(encoding="utf-8"))
        self.assertEqual(
            data.get("work_status"),
            "done",
            "mark_ac_done must set work_status: done when the JS gate passes.",
        )

    def test_js_mark_done_gated_on_eligibility(self) -> None:
        # covers: BO-2500e-4
        """A JS-covered AC with a FAILED vitest is refused (return 3).

        mark_ac_done must NOT set work_status: done when the JS gate fails.
        It is gated on the eligibility verdict, not on mere tag presence.

        RED mechanism: patch("done_proof.run_vitest_and_parse") raises AttributeError.
        """
        ts_path = _write_ts_test(
            self.test_root,
            "markDoneFailing.test.ts",
            f"""\
            import {{ test, expect }} from 'vitest'

            test('js covered AC fails', () => {{
              // covers: {self.ac_id}
              expect(false).toBe(true)  // intentional failure
            }})
            """,
        )

        with patch(
            "done_proof.run_vitest_and_parse",
            return_value={str(ts_path): "FAILED"},
        ):
            result = _mark_done(
                self.ac_id,
                self.ac_root,
                test_root=self.test_root,
            )

        self.assertEqual(
            result,
            3,
            "mark_ac_done must return 3 (coverage gate refusal) when the JS vitest "
            "FAILS.  The gate is on the verdict, not tag presence alone. "
            f"Got return code {result}.",
        )

        ac_yaml = self.ac_root / "test-component" / f"{self.ac_id}.yaml"
        data = yaml.safe_load(ac_yaml.read_text(encoding="utf-8"))
        self.assertNotEqual(
            data.get("work_status"),
            "done",
            "mark_ac_done must NOT set work_status: done when the JS gate fails.",
        )

    def test_python_only_ac_verdict_unchanged_after_js_support(self) -> None:
        # covers: BO-2500e-4-i
        """Python-only ACs yield the SAME verdict as before JS support was added.

        A purely Python-covered AC (no .ts/.tsx files at all in test_root)
        must still be evaluated correctly by verify_done_eligible after JS
        support is introduced.  This is a no-regression test.

        This test MAY pass immediately (eligible=True for passing .py test).
        That is expected — it is a no-regression assertion on the Python path.
        """
        py_ac_id = "BO-E4-PYONLY-001"
        _write_ac(self.ac_root, py_ac_id, status="active")

        _write_py_test(
            self.test_root,
            "test_py_only.py",
            f"""\
            def test_py_only_passes():
                # covers: {py_ac_id}
                pass  # genuinely passes — no .ts files anywhere
            """,
        )

        # No .ts/.tsx files in test_root — pure Python scenario.
        verdict = verify_done_eligible(
            py_ac_id,
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        self.assertTrue(
            verdict["eligible"],
            "A Python-only AC with a passing covers test must remain eligible "
            "after JS support is added (no-regression).",
        )
        self.assertEqual(
            verdict.get("reason", ""),
            "",
            "reason must be empty for a Python-only eligible AC.",
        )

    def test_python_only_path_does_not_invoke_vitest(self) -> None:
        # covers: BO-2500e-4-i
        """For Python-only ACs, run_vitest_and_parse must NOT be called.

        When no .ts/.tsx files exist in test_root, verify_done_eligible must
        not invoke the JS runner at all.  This test uses create=True so the
        attribute is created for the assertion even though it does not exist yet.

        This test MAY pass immediately — it is a no-regression check.
        """
        py_ac_id = "BO-E4-PYONLY-NOJS-001"
        _write_ac(self.ac_root, py_ac_id, status="active")

        _write_py_test(
            self.test_root,
            "test_py_only_nojs.py",
            f"""\
            def test_py_no_js_runner():
                # covers: {py_ac_id}
                pass
            """,
        )

        # No .ts files — verify the JS runner is never called.
        mock_runner = MagicMock(return_value={})
        with patch(
            "done_proof.run_vitest_and_parse",
            mock_runner,
            create=True,  # create=True so the attr is created for spying
        ):
            verify_done_eligible(
                py_ac_id,
                ac_root=self.ac_root,
                test_root=self.test_root,
            )

        mock_runner.assert_not_called()


# ---------------------------------------------------------------------------
# BO-2500e-6 — CI gate includes JS-covered ACs (engine-level integration)
# ---------------------------------------------------------------------------


class TestCiGateJsIntegration(unittest.TestCase):
    """BO-2500e-6: The CI-gate engine (verify_done_eligible) includes JS-covered ACs."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.ac_id = "BO-E6-CI-001"
        _write_ac(self.ac_root, self.ac_id, status="active", work_status="done")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ci_gate_verdict_includes_js_covered_acs(self) -> None:
        # covers: BO-2500e-6
        """The CI engine verdict must include JS-covered ACs.

        When a done AC is covered by a passing vitest (mocked), the engine
        must return eligible=True — confirming the JS AC participates in the
        CI gate just like a Python AC.

        RED mechanism: patch("done_proof.run_vitest_and_parse") raises AttributeError.
        """
        ts_path = _write_ts_test(
            self.test_root,
            "ciGatePassing.test.ts",
            f"""\
            import {{ test, expect }} from 'vitest'

            test('CI gate JS coverage', () => {{
              // covers: {self.ac_id}
              expect(true).toBe(true)
            }})
            """,
        )

        with patch(
            "done_proof.run_vitest_and_parse",
            return_value={str(ts_path): "PASSED"},
        ):
            verdict = verify_done_eligible(
                self.ac_id,
                ac_root=self.ac_root,
                test_root=self.test_root,
            )

        self.assertTrue(
            verdict["eligible"],
            "CI gate: a JS-covered done AC with a PASSED vitest must be eligible. "
            "The engine must include JS-covered ACs in its verdict.",
        )

    def test_ci_gate_derives_from_committed_state_only(self) -> None:
        # covers: BO-2500e-6
        """The CI gate derives its verdict from committed files on disk only.

        Simulates the committed-state scenario: the .ts test file exists on
        disk (in test_root, representing the committed tree), but its vitest
        result is FAILED (the test doesn't actually pass).  The gate must
        return ineligible — derived only from the on-disk committed state via
        run_vitest_and_parse, not from any cache or pre-commit hook state.

        RED mechanism: patch("done_proof.run_vitest_and_parse") raises AttributeError.
        """
        ts_path = _write_ts_test(
            self.test_root,
            "ciGateFailing.test.ts",
            f"""\
            import {{ test, expect }} from 'vitest'

            test('CI gate JS failing', () => {{
              // covers: {self.ac_id}
              expect(false).toBe(true)  // committed but failing
            }})
            """,
        )

        # The committed state has a FAILING vitest → gate must block.
        with patch(
            "done_proof.run_vitest_and_parse",
            return_value={str(ts_path): "FAILED"},
        ):
            verdict = verify_done_eligible(
                self.ac_id,
                ac_root=self.ac_root,
                test_root=self.test_root,
            )

        self.assertFalse(
            verdict["eligible"],
            "CI gate: a FAILED committed .ts vitest must make the AC ineligible. "
            "The verdict is derived from committed state (test_root) only.",
        )
        self.assertTrue(
            len(verdict.get("reason", "")) > 0,
            "The CI gate must provide a reason when the JS test fails.",
        )


if __name__ == "__main__":
    unittest.main()
