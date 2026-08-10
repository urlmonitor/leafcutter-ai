"""
MODULE: unit_tests/ac_store/test_bo2500a_done_proof.py
GOAL: RED test stubs for BO-2500a-1, BO-2500a-2, BO-2500a-3, BO-2500a-1-i, BO-2500a-2-i.

=== Interface contract under test (to be implemented by python-coder) ===

  Location: scripts/ac_store/test_enforcement.py

    verify_done_eligible(
        ac_id: str,
        *,
        ac_root: Path,
        test_root: Path,
    ) -> dict

  The returned dict must contain at minimum:
      "eligible"      bool      — True iff ≥1 covers-linked test exists AND every
                                  such test PASSES in the current run; False otherwise.
                                  xfail, skip, xpass, and error outcomes all count as
                                  non-passing for this purpose.
      "reason"        str       — Empty string when eligible; a human-readable
                                  explanation when not, naming the specific cause
                                  (e.g. "no linked test found for <ac_id>",
                                   "linked test failed: <nodeid>",
                                   "linked test xfailed: <nodeid>").
      "passing_tests" list[str] — pytest nodeids of covers-linked tests that PASSED.
      "failing_tests" list[str] — pytest nodeids of covers-linked tests that were
                                  not passing (FAILED, XFAIL, SKIPPED, ERROR).
      "dangling_tags" list[dict]— covers tags found anywhere in test_root pointing
                                  at an id that is absent from or non-active in
                                  ac_root.  Each entry: {"id": str, "location": str}.

  Location: scripts/ac_store/mark_ac_done.py (extended signature)

    mark_ac_done(
        ac_id: str,
        ac_root: Path,
        *,
        test_root: Path | None = None,
        dry_run: bool = False,
        ticket_path: Path | None = None,
    ) -> int

  When test_root is provided, mark_ac_done must call verify_done_eligible first.
  When the AC is not eligible, mark_ac_done must return non-zero without writing
  the YAML and print a refusal message that names the reason and the AC id.
  Use exit code 3 to distinguish the coverage-gate refusal from existing codes
  (1 = lookup/read failure, 2 = status != active).

=== Fixture authenticity mandate (BO-2500a dogfood) ===

  All AC YAML fixtures are written with yaml.safe_dump (not hand-typed YAML
  strings).  All test fixtures are real .py files with genuine test bodies that
  pass, fail, xfail, or skip under pytest.  No mocking of pass/fail signals.

=== Red baseline ===

  All tests are RED until python-coder implements verify_done_eligible in
  scripts/ac_store/test_enforcement.py and extends the mark_ac_done signature
  in scripts/ac_store/mark_ac_done.py.
"""
from __future__ import annotations

import io
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Repo path wiring — same pattern as sibling ac_store tests
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

# These imports will fail (ImportError) until python-coder implements
# verify_done_eligible in scripts/ac_store/test_enforcement.py.
# That ImportError IS the intended red state — it confirms the production
# code does not yet exist.
from test_enforcement import verify_done_eligible  # noqa: E402

# mark_ac_done already exists; calling it with test_root= will raise TypeError
# until the extended signature is implemented.  Either error is a valid red state.
from mark_ac_done import mark_ac_done as _mark_done  # noqa: E402


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

_PYTHON_EXE = sys.executable


def _write_ac(
    ac_root: Path,
    ac_id: str,
    *,
    status: str = "active",
    work_status: str = "todo",
) -> Path:
    """Write a minimal AC YAML using yaml.safe_dump (mandate-compliant).

    Args:
        ac_root: Root directory of the synthetic AC store.
        ac_id: Identifier for the AC (e.g. "BO-TEST-UNIT-A1").
        status: The AC's lifecycle status ("active", "deprecated", etc.).
        work_status: The AC's work status ("todo", "done", etc.).

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
    # Mandate: use yaml.safe_dump, not a hand-typed YAML literal.
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _write_test_file(test_root: Path, filename: str, content: str) -> Path:
    """Write a Python test file to test_root using textwrap.dedent.

    Args:
        test_root: Directory to place the test file.
        filename: Filename (e.g. "test_my_feature.py").
        content: Python source; leading whitespace is dedented automatically.

    Returns:
        Path to the written test file.
    """
    test_root.mkdir(parents=True, exist_ok=True)
    path = test_root / filename
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# BO-2500a-1 — No covers test → cannot be marked done
# ---------------------------------------------------------------------------


class TestNoCoversTest(unittest.TestCase):
    """BO-2500a-1: An AC with no linked covers test cannot be marked done."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.ac_id = "BO-TEST-UNIT-A1"
        # Write an active AC with no linked test in the test_root.
        _write_ac(self.ac_root, self.ac_id, status="active")
        # test_root is intentionally empty — no test files at all.
        self.test_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac_without_covers_test_cannot_be_marked_done(self) -> None:
        # covers: BO-2500a-1
        """An active AC with no '# covers:<id>' test must return eligible=False.

        To make this green, verify_done_eligible must:
        - Scan test_root for Python files containing '# covers: BO-TEST-UNIT-A1'
        - Find none
        - Return eligible=False
        """
        verdict = verify_done_eligible(
            self.ac_id,
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        self.assertFalse(
            verdict["eligible"],
            "An AC with no covers-linked test must NOT be eligible for done.",
        )

    def test_missing_linked_test_named_as_reason(self) -> None:
        # covers: BO-2500a-1
        """The verdict must name the missing linked test as the reason.

        To make this green, verify_done_eligible must:
        - Include a non-empty 'reason' string when eligible=False
        - The reason must reference the AC id so it is machine-readable
        """
        verdict = verify_done_eligible(
            self.ac_id,
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        self.assertFalse(verdict["eligible"])
        reason = verdict.get("reason", "")
        self.assertTrue(
            len(reason) > 0,
            "A non-eligible verdict must include a non-empty reason string.",
        )
        self.assertIn(
            self.ac_id,
            reason,
            f"The reason must name the AC id '{self.ac_id}' so it is machine-readable.",
        )


# ---------------------------------------------------------------------------
# BO-2500a-2 — Failing covers test → cannot be marked done
# ---------------------------------------------------------------------------


class TestFailingCoversTest(unittest.TestCase):
    """BO-2500a-2: An AC whose covers test fails cannot be marked done."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.ac_id = "BO-TEST-UNIT-A2"
        _write_ac(self.ac_root, self.ac_id, status="active")
        # Write a real test file whose body FAILS (assert False).
        # The covers tag is inside the function — the verifier must find it.
        _write_test_file(
            self.test_root,
            "test_failing_coverage.py",
            f"""\
            def test_covers_bo_test_unit_a2():
                # covers: {self.ac_id}
                assert False, "intentional failure — this test is supposed to fail"
            """,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac_with_failing_covers_test_cannot_be_marked_done(self) -> None:
        # covers: BO-2500a-2
        """An active AC whose covers-linked test fails must return eligible=False.

        The pass/fail signal is derived from the ACTUAL pytest outcome of the
        real test file written to disk — no mocking.  To make this green,
        verify_done_eligible must run pytest on the discovered test and observe
        a FAILED outcome, returning eligible=False.
        """
        verdict = verify_done_eligible(
            self.ac_id,
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        self.assertFalse(
            verdict["eligible"],
            "An AC whose covers test FAILS must NOT be eligible for done.",
        )
        self.assertTrue(
            len(verdict.get("failing_tests", [])) > 0,
            "The verdict must list the failing test in 'failing_tests'.",
        )

    def test_failing_linked_test_named_as_reason(self) -> None:
        # covers: BO-2500a-2
        """The verdict must name the failing linked test (nodeid) in its reason.

        To make this green, verify_done_eligible must:
        - Include the nodeid (or file+function) of the failing test in 'reason'
        - The reason must name the AC id so it is machine-readable
        """
        verdict = verify_done_eligible(
            self.ac_id,
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        self.assertFalse(verdict["eligible"])
        reason = verdict.get("reason", "")
        self.assertTrue(len(reason) > 0, "Reason must be non-empty when not eligible.")
        # The reason should name either the AC id or the failing test nodeid
        # so that the caller knows which test blocked the done transition.
        failing = verdict.get("failing_tests", [])
        self.assertTrue(
            len(failing) > 0,
            "failing_tests must be non-empty when a covers test fails.",
        )
        nodeid = failing[0]
        self.assertIn(
            "test_covers_bo_test_unit_a2",
            nodeid,
            "The failing_tests nodeid must reference the actual failing function name.",
        )


# ---------------------------------------------------------------------------
# BO-2500a-3 — Passing covers test → eligible for done
# ---------------------------------------------------------------------------


class TestPassingCoversTest(unittest.TestCase):
    """BO-2500a-3: An AC with a present, passing covers test is eligible for done."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.ac_id = "BO-TEST-UNIT-A3"
        _write_ac(self.ac_root, self.ac_id, status="active")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac_with_passing_covers_test_is_eligible_for_done(self) -> None:
        # covers: BO-2500a-3
        """An active AC with at least one passing covers test must return eligible=True.

        The test fixture is a real Python file whose test body passes (pass statement).
        To make this green, verify_done_eligible must:
        - Find the covers tag for the AC id
        - Run the test and observe a PASSED outcome
        - Return eligible=True with the passing nodeid in 'passing_tests'
        """
        _write_test_file(
            self.test_root,
            "test_passing_coverage.py",
            f"""\
            def test_covers_bo_test_unit_a3():
                # covers: {self.ac_id}
                pass  # genuinely passes
            """,
        )

        verdict = verify_done_eligible(
            self.ac_id,
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        self.assertTrue(
            verdict["eligible"],
            "An AC whose covers test PASSES must be eligible for done.",
        )
        self.assertTrue(
            len(verdict.get("passing_tests", [])) > 0,
            "The verdict must list the passing test in 'passing_tests'.",
        )
        self.assertEqual(
            verdict.get("reason", ""),
            "",
            "The reason must be empty (or absent) when the AC is eligible.",
        )

    def test_eligibility_requires_all_covers_tests_passing(self) -> None:
        # covers: BO-2500a-3
        """Eligibility requires EVERY covers-linked test to pass — one failure blocks.

        This test writes a file with two covers-tagged functions for the same AC:
        one that passes and one that fails.  The verdict must be eligible=False
        because not ALL covers tests passed.

        To make this green, verify_done_eligible must aggregate outcomes across
        ALL discovered tests for the AC id and require every one to pass.
        """
        _write_test_file(
            self.test_root,
            "test_mixed_coverage.py",
            f"""\
            def test_first_passes():
                # covers: {self.ac_id}
                pass  # passes

            def test_second_fails():
                # covers: {self.ac_id}
                assert False, "second covers test fails — eligibility must be blocked"
            """,
        )

        verdict = verify_done_eligible(
            self.ac_id,
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        self.assertFalse(
            verdict["eligible"],
            "Eligibility must be False when even one covers test fails.",
        )
        self.assertTrue(
            len(verdict.get("failing_tests", [])) > 0,
            "The failing test must appear in 'failing_tests'.",
        )
        # The passing test IS in passing_tests, showing we ran both.
        self.assertTrue(
            len(verdict.get("passing_tests", [])) > 0,
            "The passing test must appear in 'passing_tests' (both tests were run).",
        )


# ---------------------------------------------------------------------------
# BO-2500a-1-i — Covers tag pointing at non-active AC → flagged, does not count
# ---------------------------------------------------------------------------


class TestDanglingCoversTag(unittest.TestCase):
    """BO-2500a-1-i: A covers tag for a deprecated/nonexistent AC is dangling and
    does not count toward any active AC's done proof."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.active_id = "BO-TEST-UNIT-ACT1"
        self.deprecated_id = "BO-TEST-UNIT-DEPR1"
        # Active AC that we want to evaluate
        _write_ac(self.ac_root, self.active_id, status="active")
        # Deprecated AC — its covers tag should be treated as dangling
        _write_ac(self.ac_root, self.deprecated_id, status="deprecated")
        # Test file that is correctly passing but tagged for the DEPRECATED id.
        # This tag must NOT count toward the active AC's proof.
        _write_test_file(
            self.test_root,
            "test_deprecated_tag.py",
            f"""\
            def test_tagged_for_deprecated_ac():
                # covers: {self.deprecated_id}
                pass  # passes, but tagged for a deprecated AC — should not count
            """,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_covers_tag_for_nonactive_ac_does_not_count(self) -> None:
        # covers: BO-2500a-1-i
        """A covers tag for a deprecated AC must NOT satisfy the active AC's done proof.

        Even though a passing test tagged '# covers: <deprecated-id>' exists in
        test_root, that tag is for a non-active AC and must not increment coverage
        for any active AC.

        To make this green, verify_done_eligible must:
        - Derive active status from the AC store's own 'status' field (not a
          hard-coded list)
        - Exclude covers tags whose id resolves to a deprecated/superseded/nonexistent AC
        - Return eligible=False for 'active_id' because it has no valid (active) tag
        """
        verdict = verify_done_eligible(
            self.active_id,
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        self.assertFalse(
            verdict["eligible"],
            f"'{self.active_id}' has no valid covers test — a tag for a deprecated "
            "AC must not count toward its proof.",
        )

    def test_dangling_covers_tag_is_flagged(self) -> None:
        # covers: BO-2500a-1-i
        """A dangling covers tag must be reported with its id and originating location.

        To make this green, verify_done_eligible must:
        - Scan ALL covers tags in test_root (not only those for the queried AC)
        - Detect that '# covers: <deprecated-id>' points at a non-active AC
        - Report it in 'dangling_tags' as {"id": "<deprecated-id>", "location": "<file>..."}
        """
        verdict = verify_done_eligible(
            self.active_id,
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        dangling = verdict.get("dangling_tags", [])
        self.assertTrue(
            len(dangling) > 0,
            "At least one dangling tag must be reported when a covers tag points "
            "at a non-active (deprecated) AC.",
        )
        dangling_ids = [d["id"] for d in dangling]
        self.assertIn(
            self.deprecated_id,
            dangling_ids,
            f"The dangling tag for '{self.deprecated_id}' (deprecated) must be reported.",
        )
        # Each dangling entry must include a location so it can be reconciled.
        for entry in dangling:
            self.assertIn(
                "location",
                entry,
                "Each dangling_tags entry must include a 'location' key naming the "
                "test file (and ideally line) where the dangling tag appears.",
            )
            self.assertTrue(
                len(entry["location"]) > 0,
                "The 'location' value must be non-empty.",
            )

    def test_covers_tag_for_nonexistent_ac_does_not_count(self) -> None:
        # covers: BO-2500a-1-i
        """A covers tag for a completely nonexistent AC id must also be treated as dangling.

        The nonexistent id is not in the AC store at all.  The verifier must
        not count it and must report it as dangling.
        """
        nonexistent_id = "BO-TEST-UNIT-GHOST-999"
        # Write a passing test tagged for a nonexistent AC id (not in the store).
        _write_test_file(
            self.test_root,
            "test_nonexistent_tag.py",
            f"""\
            def test_tagged_for_nonexistent_ac():
                # covers: {nonexistent_id}
                pass  # passes, but the tagged AC does not exist in the store
            """,
        )

        verdict = verify_done_eligible(
            self.active_id,
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        # The active AC still has no valid covers test (both files tag non-active ids).
        self.assertFalse(verdict["eligible"])

        dangling = verdict.get("dangling_tags", [])
        dangling_ids = [d["id"] for d in dangling]
        self.assertIn(
            nonexistent_id,
            dangling_ids,
            f"A covers tag for nonexistent id '{nonexistent_id}' must be reported as dangling.",
        )


# ---------------------------------------------------------------------------
# BO-2500a-2-i — Xfailed/skipped covers test does not count as passing
# ---------------------------------------------------------------------------


class TestXfailSkipCoversTest(unittest.TestCase):
    """BO-2500a-2-i: An xfailed or skipped covers test must NOT count as passing."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.ac_id = "BO-TEST-UNIT-XF1"
        _write_ac(self.ac_root, self.ac_id, status="active")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_xfail_covers_test_does_not_count_as_passing(self) -> None:
        # covers: BO-2500a-2-i
        """An AC whose only covers test is xfail must return eligible=False.

        An xfail outcome does NOT count as a passing linked test for done-proof
        purposes — this prevents xfail-masking (see project memory: pytest
        xfail-masking) from silently satisfying the done gate.

        The test fixture is a real pytest test decorated with @pytest.mark.xfail.
        pytest returns exit code 0 for an all-xfail run, so the verifier MUST
        parse the -v output (not just the exit code) to detect XFAIL outcomes.

        To make this green, verify_done_eligible must:
        - Run the covers-linked test with pytest -v
        - Parse the output for XFAIL outcomes
        - Treat XFAIL as non-passing
        - Return eligible=False with a reason naming the xfail outcome
        """
        _write_test_file(
            self.test_root,
            "test_xfail_coverage.py",
            f"""\
            import pytest

            @pytest.mark.xfail(reason="xfail — should not satisfy done proof")
            def test_covers_xfail():
                # covers: {self.ac_id}
                assert False  # body fails; @xfail makes pytest exit 0, but NOT done-eligible
            """,
        )

        verdict = verify_done_eligible(
            self.ac_id,
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        self.assertFalse(
            verdict["eligible"],
            "An xfail covers test must NOT make the AC eligible for done.",
        )
        reason = verdict.get("reason", "")
        self.assertTrue(
            len(reason) > 0,
            "The reason must be non-empty when the only covers test is xfail.",
        )
        # The reason or failing_tests must indicate the xfail/non-passing outcome.
        failing = verdict.get("failing_tests", [])
        self.assertTrue(
            len(failing) > 0,
            "An xfail test must appear in 'failing_tests' (it is non-passing).",
        )

    def test_skipped_covers_test_does_not_count_as_passing(self) -> None:
        # covers: BO-2500a-2-i
        """An AC whose only covers test is skipped must return eligible=False.

        A SKIPPED outcome does NOT count as a passing linked test.  pytest exits
        with code 0 for skipped-only runs, so the verifier must inspect the -v
        output to detect SKIPPED outcomes.

        To make this green, verify_done_eligible must:
        - Parse the pytest -v output for SKIPPED outcomes
        - Treat SKIPPED as non-passing
        - Return eligible=False with a non-empty reason
        """
        _write_test_file(
            self.test_root,
            "test_skipped_coverage.py",
            f"""\
            import pytest

            @pytest.mark.skip(reason="skipped — should not satisfy done proof")
            def test_covers_skipped():
                # covers: {self.ac_id}
                pass  # body would pass, but the test is skipped → not done-eligible
            """,
        )

        verdict = verify_done_eligible(
            self.ac_id,
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        self.assertFalse(
            verdict["eligible"],
            "A SKIPPED covers test must NOT make the AC eligible for done.",
        )
        reason = verdict.get("reason", "")
        self.assertTrue(
            len(reason) > 0,
            "The reason must be non-empty when the only covers test is skipped.",
        )
        failing = verdict.get("failing_tests", [])
        self.assertTrue(
            len(failing) > 0,
            "A skipped test must appear in 'failing_tests' (it is non-passing).",
        )


# ---------------------------------------------------------------------------
# Integration: mark_ac_done must refuse when coverage gate is not satisfied
# ---------------------------------------------------------------------------


class TestMarkAcDoneWithCoverageGate(unittest.TestCase):
    """mark_ac_done must call verify_done_eligible and refuse when the AC is ineligible.

    These tests cover the BO-2500a-1 requirement that mark_ac_done refuses to
    set work_status: done when no valid covers test exists, naming the reason.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.test_root.mkdir(parents=True, exist_ok=True)
        self.ac_id = "BO-TEST-UNIT-GATE1"
        _write_ac(self.ac_root, self.ac_id, status="active", work_status="todo")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_mark_ac_done_refuses_when_no_covers_test(self) -> None:
        # covers: BO-2500a-1
        """mark_ac_done must return non-zero and NOT write done when no covers test exists.

        To make this green, mark_ac_done in scripts/ac_store/mark_ac_done.py must:
        1. Accept a 'test_root' keyword argument (Path | None).
        2. When test_root is provided, call verify_done_eligible(ac_id, ...) first.
        3. When not eligible, return a non-zero exit code (suggested: 3) WITHOUT
           writing work_status: done to the YAML file.
        4. Print a refusal message to stdout or stderr that names:
           - The AC id
           - The reason from verify_done_eligible
        """
        # No test files in test_root → verify_done_eligible must return eligible=False.
        result = _mark_done(self.ac_id, self.ac_root, test_root=self.test_root)

        self.assertNotEqual(
            result,
            0,
            "mark_ac_done must return non-zero when the coverage gate fails.",
        )

        # Critical: the AC YAML must NOT have been written to done.
        ac_yaml_path = self.ac_root / "test-component" / f"{self.ac_id}.yaml"
        self.assertTrue(ac_yaml_path.exists(), "AC YAML file must still exist after refused call.")
        data = yaml.safe_load(ac_yaml_path.read_text(encoding="utf-8"))
        self.assertNotEqual(
            data.get("work_status"),
            "done",
            "mark_ac_done must NOT set work_status: done when the coverage gate fails.",
        )

    def test_mark_ac_done_refusal_names_reason(self) -> None:
        # covers: BO-2500a-1
        """The refusal output must name the AC id and the reason for refusal.

        Captures stdout/stderr via sys.stdout/sys.stderr redirection.
        The reason is derived from verify_done_eligible and must be machine-readable.
        """
        from unittest.mock import patch

        buf_out = io.StringIO()
        buf_err = io.StringIO()

        with patch("sys.stdout", buf_out), patch("sys.stderr", buf_err):
            result = _mark_done(self.ac_id, self.ac_root, test_root=self.test_root)

        combined_output = buf_out.getvalue() + buf_err.getvalue()

        self.assertNotEqual(result, 0, "mark_ac_done must return non-zero on coverage-gate failure.")
        self.assertIn(
            self.ac_id,
            combined_output,
            "Refusal output must name the AC id so the caller knows which AC was refused.",
        )
        self.assertTrue(
            len(combined_output.strip()) > 0,
            "Refusal output must be non-empty — it must explain why done was refused.",
        )


if __name__ == "__main__":
    unittest.main()
