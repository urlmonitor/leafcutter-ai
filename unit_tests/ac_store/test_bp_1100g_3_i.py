"""
MODULE: unit_tests/ac_store/test_bp_1100g_3_i.py
COVERS: BP-1100g-3-i

GOAL: Negative-control test suite proving the `# angle: <kind>` tag axis
    (added by BP-1100g-3 to scripts/ac_store/done_proof.py's single-pass
    scanner) feeds NO pass, done, or eligibility decision anywhere. This
    ticket adds no production code (n_location_rule: "0" -- see the ticket's
    Scope correction section); its entire deliverable is these tests.

BUSINESS CONTEXT: BP-1100g-3 taught test-writer to tag every test with a
    `# angle: <kind>` comment naming the kind of proof it gives (criterion,
    seam, real_artifact, reachability, etc.) -- a planning declaration, not a
    verdict. This AC is the proof that the declaration stays a declaration:
    stripping every angle tag from a suite must change no run outcome
    (`_classify_outcomes`, `verify_done_eligible`'s eligibility computation)
    and no completion decision (whether a piece of work counts as done).

=== A GREEN FIRST RUN IS THE EXPECTED, CORRECT RESULT ===

    This is a negative control asserting an ABSENCE. `_scan_single_test_file`
    (the function `verify_done_eligible` actually consumes) filters
    `_scan_test_file_for_all_tags`'s output down to `tag_type == "covers"`
    entries only (see done_proof.py) -- the angle axis structurally never
    reaches `_collect_linked_tests`, `_classify_outcomes`, or
    `verify_done_eligible`. `pytest_ac_enforcement.py`'s masking decision
    (scripts/ac_store/pytest_ac_enforcement.py) reads only
    `extract_covers_tag` -- it has no angle-axis code path at all. If
    BP-1100g-3 was implemented correctly (confirmed: `_classify_outcomes` and
    `verify_done_eligible` are byte-for-byte unmodified by BP-1100g-3,
    2f740cc4), these tests are GREEN ON ARRIVAL BY CONSTRUCTION. That is the
    proof this ticket exists to produce, not a TDD-order violation. A RED
    result here would name a real leak of the angle axis into an enforcement
    or completion decision -- see the ticket's "If any test goes RED" note.

FIXTURE AUTHENTICITY (2h.2 / BP-1100g-3-i's own constraints):
    Every AC YAML fixture is written with yaml.safe_dump, never a hand-typed
    YAML literal. Every test-tree fixture is a REAL .py file written to a
    real temp directory with Path.write_text() and read back by the
    production scanner off disk -- never an in-memory record handed directly
    to a hypothetical parsing entry point. The angle-stripping test operates
    by rewriting real bytes on a real file on disk and re-invoking the
    production scan, never by filtering an already-parsed record -- a tag
    consumed anywhere in the file-reading path would otherwise go uncaught.

AC MAPPING (ticket's Acceptance Criteria checklist):
    AC-1 ("both carry the same existing coverage tag for the same piece of
        work") is a fixture PRECONDITION satisfied by construction in every
        test below (the compared test functions/files always share one
        `# covers: <ac_id>` value).
    AC-2/AC-3 ("both tests are treated identically ... the existing coverage
        tag alone continues to decide which failing tests are treated as
        blocking") -- see TestClassifyOutcomesIgnoresAngleAxis (criterion)
        and TestRealScannerOutputFeedsRealEnforcementUnaffectedByAngle (seam).
    AC-4/AC-5 ("a piece of work whose tests all carry kind tags is no closer
        to being counted done ... removing every kind tag from the suite
        changes no run outcome and no completion decision anywhere") -- see
        TestStrippingEveryAngleTagChangesNoOutcomeOrCompletionDecision
        (real_artifact) and the companion CI-gate reachability test in
        unit_tests/commit_guardian/test_bp_1100g_3_i.py.
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_AC_STORE_DIR = _REPO_ROOT / "scripts" / "ac_store"
if str(_AC_STORE_DIR) not in sys.path:
    sys.path.insert(0, str(_AC_STORE_DIR))

# Real production entry points under test -- unchanged by this ticket
# (n_location_rule: "0"). Importing them at module scope is safe: BP-1100g-3
# already shipped these symbols on main.
from done_proof import _classify_outcomes, verify_done_eligible  # noqa: E402

_ANGLE_LINE_RE = re.compile(r"^[ \t]*#\s*angle:.*\n", re.MULTILINE)


def _write_ac(ac_root: Path, ac_id: str, *, work_status: str = "todo") -> Path:
    """Write a minimal AC YAML using yaml.safe_dump (fixture authenticity mandate)."""
    component_dir = ac_root / "test-component"
    component_dir.mkdir(parents=True, exist_ok=True)
    path = component_dir / f"{ac_id}.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "id": ac_id,
                "title": f"synthetic BP-1100g-3-i fixture AC {ac_id}",
                "component": "build-orchestration",
                "status": "active",
                "work_status": work_status,
                "covered_by": [],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    return path


class TestClassifyOutcomesIgnoresAngleAxis(unittest.TestCase):
    """test_spec: test_bp_1100g_3_i_tagged_and_untagged_failing_tests_are_treated_identically
    (angle: criterion)."""

    def test_bp_1100g_3_i_tagged_and_untagged_failing_tests_are_treated_identically(
        self,
    ) -> None:
        # covers: BP-1100g-3-i
        # angle: criterion
        """AC-1/AC-2/AC-3: two failing tests covering the same AC -- one
        record carrying an 'angles' entry (as if it had a kind tag), one
        carrying none -- are classified identically by `_classify_outcomes`,
        the real function that decides which failing tests block. The
        function does not even read an 'angles' key when present; the
        classification is the one it would be with no tag at all."""
        linked_with_angle_hint = [
            {"file": "test_a.py", "function": "test_tagged", "angles": ["criterion"]},
            {"file": "test_b.py", "function": "test_untagged", "angles": []},
        ]
        linked_with_no_angle_key_at_all = [
            {"file": "test_a.py", "function": "test_tagged"},
            {"file": "test_b.py", "function": "test_untagged"},
        ]
        pytest_results = {
            "test_a.py::test_tagged": "FAILED",
            "test_b.py::test_untagged": "FAILED",
        }

        passing_with, failing_with = _classify_outcomes(
            linked_with_angle_hint, pytest_results
        )
        passing_without, failing_without = _classify_outcomes(
            linked_with_no_angle_key_at_all, pytest_results
        )

        self.assertEqual(
            passing_with,
            passing_without,
            "presence of an 'angles' entry on a linked-test record must not "
            "change the passing classification",
        )
        self.assertEqual(
            failing_with,
            failing_without,
            "presence of an 'angles' entry on a linked-test record must not "
            "change the failing classification",
        )
        self.assertEqual(passing_with, [])
        self.assertCountEqual(
            failing_with,
            ["test_a.py::test_tagged", "test_b.py::test_untagged"],
            "the existing coverage tag alone decides which failing tests "
            "block -- both tests here share one coverage tag and both must "
            "block identically regardless of the angle hint",
        )


class TestRealScannerOutputFeedsRealEnforcementUnaffectedByAngle(unittest.TestCase):
    """test_spec: test_bp_1100g_3_i_kind_tag_never_reaches_the_enforcement_decision
    (angle: seam)."""

    def test_bp_1100g_3_i_kind_tag_never_reaches_the_enforcement_decision(
        self,
    ) -> None:
        # covers: BP-1100g-3-i
        # angle: seam
        """AC-2/AC-3: pipe the REAL scanner's output for a real on-disk test
        tree (both axes populated) into the REAL enforcement consumer
        (`verify_done_eligible`) and confirm the verdict is byte-for-byte
        identical to the verdict produced after physically removing the
        angle tag from the same file on disk."""
        ac_id = "ZZ-1100g-3-i-seam"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ac_root = root / "acs"
            test_root = root / "tests"
            test_root.mkdir(parents=True)
            _write_ac(ac_root, ac_id)

            tagged_file = test_root / "test_tagged.py"
            tagged_file.write_text(
                textwrap.dedent(
                    f"""\
                    def test_covers_with_angle():
                        # covers: {ac_id}
                        # angle: criterion
                        assert False, "intentional failure for the seam test"
                    """
                ),
                encoding="utf-8",
            )
            untagged_file = test_root / "test_untagged.py"
            untagged_file.write_text(
                textwrap.dedent(
                    f"""\
                    def test_covers_without_angle():
                        # covers: {ac_id}
                        assert False, "intentional failure for the seam test"
                    """
                ),
                encoding="utf-8",
            )

            verdict_with_angle = verify_done_eligible(
                ac_id, ac_root=ac_root, test_root=test_root
            )

            # Strip the angle tag from the REAL file on disk and re-invoke the
            # REAL scanner via the same production entry point -- not a
            # filtered in-memory copy of already-parsed records.
            original = tagged_file.read_text(encoding="utf-8")
            stripped = _ANGLE_LINE_RE.sub("", original)
            self.assertNotEqual(
                original, stripped, "fixture must actually carry an angle tag"
            )
            tagged_file.write_text(stripped, encoding="utf-8")

            verdict_without_angle = verify_done_eligible(
                ac_id, ac_root=ac_root, test_root=test_root
            )

        self.assertEqual(
            verdict_with_angle,
            verdict_without_angle,
            "the enforcement verdict must be identical whether or not the "
            "angle tag is present on the covering test's file",
        )
        self.assertFalse(
            verdict_with_angle["eligible"],
            "fixture sanity: both linked tests fail, so eligible must be "
            "False -- otherwise the equality assertion above is vacuous",
        )
        self.assertEqual(len(verdict_with_angle["failing_tests"]), 2)


class TestStrippingEveryAngleTagChangesNoOutcomeOrCompletionDecision(unittest.TestCase):
    """test_spec: test_bp_1100g_3_i_stripping_every_kind_tag_changes_no_outcome_and_no_completion_decision
    (angle: real_artifact)."""

    def test_bp_1100g_3_i_stripping_every_kind_tag_changes_no_outcome_and_no_completion_decision(
        self,
    ) -> None:
        # covers: BP-1100g-3-i
        # angle: real_artifact
        """AC-4/AC-5: copy a real on-disk test subtree to a temp dir, run the
        whole-suite outcome and the completion decision for every AC it
        covers, strip every '# angle:' tag from the copied files ON DISK,
        and re-run both decisions again -- both must be identical to the
        tag-present run. The comparison reuses the SAME working directory
        across both passes (only its file contents are mutated) so nodeids
        stay directly comparable without path normalisation.

        DISCRIMINATING FIXTURE -- DO NOT REMOVE `# angle: failure` FROM
        `test_beta_two`. The most likely real leak is "an angle-tagged test
        proves what it claims, so count it as passing", and that leak is only
        observable on a test which is BOTH angle-tagged AND failing. An
        earlier revision of this fixture tagged only passing tests, and a
        two-step mutation of done_proof.py (plumb `angles` through
        `_scan_single_test_file`, then treat angle-carrying records as passing
        in `_classify_outcomes`) was caught by the criterion and seam tests
        while this one stayed GREEN -- a negative control that could not
        observe the very leak it exists to forbid. With the tag present the
        same mutation flips `ac_two` from ineligible to eligible in the
        tag-present pass only, so the two passes diverge and this test fails
        as it should."""
        ac_one = "ZZ-1100g-3-i-real-one"
        ac_two = "ZZ-1100g-3-i-real-two"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src_dir = root / "src"
            work_dir = root / "work"
            ac_root = root / "acs"
            src_dir.mkdir(parents=True)

            _write_ac(ac_root, ac_one)
            _write_ac(ac_root, ac_two)

            (src_dir / "test_alpha.py").write_text(
                textwrap.dedent(
                    f"""\
                    def test_alpha_one():
                        # covers: {ac_one}
                        # angle: criterion
                        assert True


                    def test_alpha_two():
                        # covers: {ac_one}
                        assert True
                    """
                ),
                encoding="utf-8",
            )
            (src_dir / "test_beta.py").write_text(
                textwrap.dedent(
                    f"""\
                    def test_beta_one():
                        # covers: {ac_two}
                        # angle: seam
                        assert True


                    def test_beta_two():
                        # covers: {ac_two}
                        # angle: failure
                        assert False, "intentional failure for the real_artifact negative control"
                    """
                ),
                encoding="utf-8",
            )

            # "Copy a real test subtree to a temp dir" -- both runs below
            # execute against this SAME copy; only its on-disk bytes change
            # between passes.
            shutil.copytree(src_dir, work_dir)

            verdict_one_with_angle = verify_done_eligible(
                ac_one, ac_root=ac_root, test_root=work_dir
            )
            verdict_two_with_angle = verify_done_eligible(
                ac_two, ac_root=ac_root, test_root=work_dir
            )

            stripped_any = False
            for py_file in sorted(work_dir.rglob("*.py")):
                original = py_file.read_text(encoding="utf-8")
                stripped = _ANGLE_LINE_RE.sub("", original)
                if stripped != original:
                    stripped_any = True
                    py_file.write_text(stripped, encoding="utf-8")
            self.assertTrue(
                stripped_any,
                "expected at least one angle tag to be stripped from the "
                "copied subtree -- otherwise this test proves nothing",
            )

            verdict_one_without_angle = verify_done_eligible(
                ac_one, ac_root=ac_root, test_root=work_dir
            )
            verdict_two_without_angle = verify_done_eligible(
                ac_two, ac_root=ac_root, test_root=work_dir
            )

        self.assertEqual(
            verdict_one_with_angle,
            verdict_one_without_angle,
            "the completion decision for the fully-passing AC must be "
            "unchanged by stripping its angle tags",
        )
        self.assertEqual(
            verdict_two_with_angle,
            verdict_two_without_angle,
            "the completion decision for the partially-failing AC must be "
            "unchanged by stripping its angle tags",
        )

        # Sanity: the fixture exercises both a fully-passing AC and a
        # mixed pass/fail AC, so neither equality assertion above is vacuous.
        self.assertTrue(verdict_one_with_angle["eligible"])
        self.assertFalse(verdict_two_with_angle["eligible"])


if __name__ == "__main__":
    unittest.main()
