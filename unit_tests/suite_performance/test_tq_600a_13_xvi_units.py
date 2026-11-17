"""
Tests for TQ-600a-13-xvi -- the proof's pure decisions, with dict inputs (milliseconds).

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xvi.yaml

``verify`` (the prepare job's last step), ``judge`` (the prove job's verdict on a lane report) and ``_safe_ids`` are
pure; each rule below is one way a proof could be forged or could silently prove nothing.
"""

from __future__ import annotations

import unittest

from ._notice_fakes import import_production

ID_X, ID_Y = "tests/test_lane.py::test_x", "tests/test_lane.py::test_y"


def report(results, *, exitstatus=0, errors=(), expected=None):
    """A lane report as ``_lane_report_plugin`` writes it."""
    return {"runner": "r", "exitstatus": exitstatus, "expected": len(results) if expected is None else expected, "ran": len(results), "collection_errors": list(errors), "results": results}


class TestTq600a13xviProofDecisions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proof = import_production("scripts.ci.post_merge_fix_proof")

    def test_tq_600a_13_xvi_judge_counts_only_passed_as_passed(self):
        # covers: TQ-600a-13-xvi
        # angle: discrimination
        """AC-xvi: for wanted ids only ``passed`` is a pass -- skipped, xfailed, failed and not-run each fail the proof.

        Wrong versions caught: a skipped or xfailed wanted test counts as passed; a missing id is ignored.
        """
        judge = self.proof.judge
        self.assertEqual([], judge(report({ID_X: "passed", ID_Y: "passed"}), [ID_X, ID_Y]))
        for status in ("skipped", "xfailed", "failed"):
            self.assertTrue(judge(report({ID_X: "passed", ID_Y: status}, exitstatus=1 if status == "failed" else 0), [ID_X, ID_Y]), status)
        self.assertTrue(judge(report({ID_X: "passed"}), [ID_X, ID_Y]), "an id that did not run is not passed")

    def test_tq_600a_13_xvi_judge_refuses_an_unfinished_session(self):
        # covers: TQ-600a-13-xvi
        # angle: failure
        """AC-xvi: no report, a collection error, exit status 5, an empty selection and a cut-short session all fail.

        Wrong versions caught: exit 5 / empty selection reads as passed; a collection error is ignored; a missing report passes.
        """
        judge, ok = self.proof.judge, {ID_X: "passed"}
        self.assertTrue(judge(None, [ID_X]))
        self.assertTrue(judge(report(ok, errors=["tests/test_broken.py"]), [ID_X]))
        self.assertTrue(judge(report({}, exitstatus=5), [ID_X]))
        self.assertTrue(judge(report({}, exitstatus=5), None))
        self.assertTrue(judge(report(ok, exitstatus=2), [ID_X]))
        self.assertTrue(judge(report(ok, expected=3), [ID_X]))

    def test_tq_600a_13_xvi_a_whole_lane_that_shrank_or_xfailed_is_not_green(self):
        # covers: TQ-600a-13-xvi
        # angle: discrimination
        """AC-xvi: a whole-lane proof fails when any test of the baseline is missing from the head's results (identity, not
        count: a deleted test plus an added one is the same size), naming a capped list of the missing ids with the advice;
        it passes when every baseline id ran and passed, and when a test reads xfailed it fails.

        Wrong versions caught: the guard compares counts, so a head that deletes the broken test and adds a passing one
        proves a fix; a head that turns failures into xfail passes the lane.
        """
        judge, lane = self.proof.judge, {"a": "passed", "b": "passed", "c": "passed"}
        self.assertEqual([], judge(report(lane), None, ["a", "b", "c"]))
        self.assertEqual([], judge(report(lane), None, ["a"]), "extra tests at the head are fine")
        self.assertEqual([], judge(report(lane), None, []), "no baseline at all: nothing to compare (the prove step refuses to get here)")
        swapped = judge(report({"a": "passed", "b": "passed", "new": "passed"}), None, ["a", "b", "c"])
        self.assertTrue(any("head lane is missing 1 of 3 baseline tests" in p and "c" in p and "break-glass" in p for p in swapped), swapped)
        many = [f"tests/t.py::t{n}" for n in range(100)]
        capped = "\n".join(judge(report({"z": "passed"}), None, many))
        self.assertIn("missing 100 of 100", capped)
        self.assertNotIn("tests/t.py::t99", capped, "the list of missing ids is capped")
        self.assertTrue(judge(report({**lane, "c": "xfailed"}), None, ["a", "b", "c"]))

    def test_tq_600a_13_xvi_a_whole_lane_with_an_xpassed_test_is_not_green(self):
        # covers: TQ-600a-13-xvi
        # angle: discrimination
        """AC-xvi: a report built from pytest's own xpass shape (passed + wasxfail, labelled by the proof's status) and
        one built from the masking plugin's shape both fail a whole-lane judgement; a plain pass does not.

        Wrong versions caught: ``xpassed`` is accepted as green in a whole-lane proof.
        """
        from types import SimpleNamespace  # noqa: PLC0415 -- only this test builds report look-alikes

        label = self.proof._distinct_status
        xpass = label(SimpleNamespace(outcome="passed", failed=False, skipped=False, wasxfail="r"))
        masked = label(SimpleNamespace(outcome="xfailed", failed=False, skipped=False))
        plain = label(SimpleNamespace(outcome="passed", failed=False, skipped=False))
        self.assertEqual(("xpassed", "xfailed", "passed"), (xpass, masked, plain))
        for status in (xpass, masked):
            self.assertTrue(self.proof.judge(report({"a": "passed", "b": status}), None, ["a", "b"]), status)
        self.assertEqual([], self.proof.judge(report({"a": "passed", "b": plain}), None, ["a", "b"]))

    def test_tq_600a_13_xvi_the_baseline_falls_back_to_main_s_own_lane(self):
        # covers: TQ-600a-13-xvi
        # angle: boundary
        """AC-xvi: the verdict's collected ids are the baseline when there are any; when there are none (a
        did-not-complete run) main's own collect-only ids are; ``main_collected`` is not even asked for in the first case.

        Wrong versions caught: a missing list switches the shrink guard off.
        """
        asked = []

        def main_collected():
            asked.append(1)
            return ["m1", "m2"]

        self.assertEqual(["v1"], self.proof.baseline_ids(["v1"], main_collected))
        self.assertEqual([], asked)
        self.assertEqual(["m1", "m2"], self.proof.baseline_ids([], main_collected))
        self.assertEqual(1, len(asked))

    def test_tq_600a_13_xvi_the_status_label_reads_the_masking_plugin_s_outcome(self):
        # covers: TQ-600a-13-xvi
        # angle: discrimination
        """AC-xvi: ``pytest_ac_enforcement`` masks a failure by setting ``report.outcome = "xfailed"`` with ``failed`` and
        ``skipped`` both False. That reads ``xfailed``, never ``xpassed`` (which is also not green); pytest's own xfail
        (skipped + wasxfail) is ``xfailed`` and its xpass (passed + wasxfail) is ``xpassed``.

        Wrong versions caught: the masked report is labelled xpassed and a whole-lane judge lets it through.
        """
        from types import SimpleNamespace  # noqa: PLC0415 -- only this test builds report look-alikes

        def shape(outcome, *, failed=False, skipped=False, **extra):
            return SimpleNamespace(outcome=outcome, failed=failed, skipped=skipped, **extra)

        status = self.proof._distinct_status
        self.assertEqual("xfailed", status(shape("xfailed")))
        self.assertEqual("xfailed", status(shape("skipped", skipped=True, wasxfail="r")))
        self.assertEqual("xpassed", status(shape("passed", wasxfail="r")))
        self.assertEqual("passed", status(shape("passed")))
        self.assertEqual("skipped", status(shape("skipped", skipped=True)))
        self.assertEqual("failed", status(shape("failed", failed=True)))

    def test_tq_600a_13_xvi_verify_takes_the_ids_from_the_artifact_and_refuses_what_is_unsafe(self):
        # covers: TQ-600a-13-xvi
        # angle: discrimination
        """AC-xvi: ``verify`` refuses an artifact of another run; no proof is wanted without a candidate; an unsafe id is
        never emitted (the proof falls back to the whole lane); more than MAX_IDS or no ids fall back to the whole lane.

        Wrong versions caught: the artifact of a different run is trusted; an id that could be read as an option reaches argv.
        """
        lane_ids = ["tests/test_lane.py::test_a", ID_X, ID_Y]
        verify, verdict = self.proof.verify, {"run_id": 7, "failing": [ID_X, ID_Y], "collected_ids": lane_ids}
        self.assertEqual({"run_proof": "false"}, verify("false", "", False, None))
        got = verify("true", "7", False, verdict)
        self.assertEqual(("true", "false", "7", [ID_X, ID_Y]), (got["run_proof"], got["whole_lane"], got["red_run_id"], got["failing_ids"].split("\n")))
        self.assertEqual("", got["collected_ids"], "the lane's ids matter only to a whole-lane proof")
        whole = verify("true", "7", True, verdict)
        self.assertEqual(lane_ids, whole["collected_ids"].split("\n"), "a whole-lane proof is handed the verdict's lane ids")
        for bad in (["--x"], [lane_ids[0], "x.py::t\nrm"], [f"tests/t.py::t{n}" for n in range(self.proof.MAX_IDS + 1)], []):
            self.assertEqual("", verify("true", "7", True, {**verdict, "collected_ids": bad})["collected_ids"], "unsafe, too many or none: prove falls back to main's own lane")
        with self.assertRaises(self.proof.ProofInputError):
            verify("true", "8", False, verdict)
        with self.assertRaises(self.proof.ProofInputError):
            verify("true", "7", False, None)
        for unsafe in ("--rootdir=/tmp", "../x.py::t", "/abs/x.py::t", "x.py::t\nrm", "not_a_test"):
            with self.assertRaises(self.proof.ProofInputError, msg=unsafe):
                self.proof._safe_ids([ID_X, unsafe])
            fell_back = verify("true", "7", False, {**verdict, "failing": [ID_X, unsafe]})
            self.assertEqual(("true", ""), (fell_back["whole_lane"], fell_back["failing_ids"]), f"{unsafe!r} must never be emitted")
        many = [f"tests/test_lane.py::test_{n}" for n in range(self.proof.MAX_IDS + 1)]
        self.assertEqual("true", verify("true", "7", False, {**verdict, "failing": many})["whole_lane"])
        self.assertEqual("false", verify("true", "7", False, {**verdict, "failing": many[: self.proof.MAX_IDS]})["whole_lane"])
        self.assertEqual("true", verify("true", "7", False, {**verdict, "failing": []})["whole_lane"])


if __name__ == "__main__":
    unittest.main()
