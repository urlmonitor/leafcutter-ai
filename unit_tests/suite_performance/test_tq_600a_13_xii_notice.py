"""
Tests for TQ-600a-13-xii (notice half) -- the `post-merge-timing` notice: opened on a red timing run, closed on a green
one, naming lane entrants with the commit that touched their file; and the follow-up workflow's timing job.

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xii.yaml

ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds this).

1. ``post_merge_notice.py apply`` gains ``--lane {correctness,timing}`` (default correctness, unchanged). With
   ``--lane timing`` it reads the runs of ``post-merge-timing.yml`` (never the suite's), reads and writes only issues
   labelled ``post-merge-timing``, accepts a verdict whose ``lane`` is ``timing``, and otherwise behaves as the
   correctness notice does (create on red, update, close on green).
2. ``apply`` gains an optional ``--previous-verdict-file PATH``: the verdict file of the previous settled timing run.
   Absent option, absent file: no entrants. Entrants are ``collected_ids`` of the current verdict not in the
   previous one, named only on a notice a red run writes (a green run opens no notice). Each entrant is ONE bullet
   line of the description carrying its node id and the first 7 hex characters of the newest commit in
   (previous head_sha, current head_sha] that touched the test's file (``git log`` in ``--repo-dir``), each in a
   code span; an entrant with no such commit says in words that the commit could not be determined, and names no sha.
3. ``post-merge-followup.yml`` gains a job ``timing-notice`` gated to ``Post-merge timing suite``; the existing
   ``notice`` job stays gated to ``Post-merge suite`` and never runs the timing lane.
"""

from __future__ import annotations

import re
import unittest

from ._ending_harness import Cases
from ._hold_harness import make_run
from ._timing_harness import FOLLOWUP_WORKFLOW, TIMING_LABEL, TimingNoticeCase, timing_verdict
from ._workflow_jobs import find_job, load_workflow

OLD_ID = "unit_tests/test_old_ratio.py::test_old"
MOVED_ID = "unit_tests/test_moved.py::test_moved"
GHOST_ID = "unit_tests/test_ghost.py::test_ghost"
FAILING_ID = "unit_tests/test_old_ratio.py::test_old_fails"
UNDETERMINED = re.compile(r"(?i)could not be determined|not determinable|cannot be determined")


def _lines_naming(body, node_id):
    return [line for line in body.splitlines() if f"`{node_id}`" in line]


class TestTq600a13XiiLaneEntrants(TimingNoticeCase):
    def _red_apply(self, current_ids, *, previous_ids=None, previous_path=None):
        """Apply a red timing run (head H) whose previous run (head P) collected ``previous_ids``; return the created body."""
        git = self.git
        results = {**dict.fromkeys(current_ids, "passed"), FAILING_ID: "failed"}  # the failure must win: FAILING_ID is also in current_ids
        verdict = timing_verdict(results, run_id=103, head_sha=git.h)
        previous = None
        if previous_ids is not None:
            previous = timing_verdict(dict.fromkeys(previous_ids, "passed"), run_id=102, head_sha=git.p)
        self.svc.timing_runs = [make_run(3, "failure", head_sha=git.h)]
        applied = self.apply_timing(verdict, 103, previous=previous, previous_path=previous_path)
        self.assertEqual(0, applied.code, applied.log)
        created = self.svc.writes_of("create")
        self.assertEqual(1, len(created), self.svc.writes())
        return created[0][1]["body"]

    def test_tq600a_13_xii_a_new_timing_lane_entrant_is_named(self):
        # covers: TQ-600a-13-xii
        # angle: criterion
        """The notice names each new lane entrant with the NEWEST commit in (previous head, head] touching its file.

        History: P (previous head) < M1 adds test_moved < D touches a bystander < M2 edits test_moved < H. Entrants:
        `test_moved` (named with M2, not M1, not D) and `test_ghost` (its file is in no commit: said in words, no sha).
        The test that was in the lane before is not an entrant.
        """
        git = self.git
        body = self._red_apply([OLD_ID, FAILING_ID, MOVED_ID, GHOST_ID], previous_ids=[OLD_ID, FAILING_ID])
        shas = {name: sha[:7] for name, sha in git.commit_shas().items()}
        rows = Cases()
        moved = _lines_naming(body, MOVED_ID)
        with rows.case("moved entrant named once, with the newest commit"):
            self.assertEqual(1, len(moved), f"one line names the entrant:\n{body}")
            self.assertIn(f"`{shas['M2']}`", moved[0])
            self.assertTrue(not any(shas[other] in moved[0] for other in ("M1", "D", "H", "P", "C0")), moved[0])
        ghost = _lines_naming(body, GHOST_ID)
        with rows.case("undeterminable entrant says so in words"):
            self.assertEqual(1, len(ghost), f"one line names the entrant:\n{body}")
            self.assertRegex(ghost[0], UNDETERMINED)
            self.assertFalse(any(sha in ghost[0] for sha in shas.values()), ghost[0])
        with rows.case("a test already in the lane is not an entrant"):
            self.assertFalse([ln for ln in _lines_naming(body, OLD_ID) if any(sha in ln for sha in shas.values())])
            self.assertFalse([ln for ln in _lines_naming(body, FAILING_ID) if any(sha in ln for sha in shas.values())])
        with rows.case("a bystander commit is named nowhere"):
            self.assertNotIn(shas["D"], body)
            self.assertNotIn(shas["M1"], body)
        rows.check()

    def test_tq600a_13_xii_no_entrant_is_named_when_membership_did_not_change(self):
        # covers: TQ-600a-13-xii
        # angle: boundary
        """Control rows for the entrant test: same membership, no previous verdict, a previous file that is absent.

        A notice is still written for the red run; it names no commit and no entrant.
        """
        shas = [sha[:7] for sha in self.git.commit_shas().values()]
        same_ids = [OLD_ID, FAILING_ID, MOVED_ID]
        rows = Cases()
        for label, kwargs in (
            ("same membership", {"previous_ids": same_ids}),
            ("no previous option", {"previous_ids": None}),
            ("previous file absent", {"previous_path": self.tmp / "no-such-verdict.json"}),
        ):
            self.svc.reset()
            with rows.case(label):
                body = self._red_apply(same_ids, **kwargs)
                self.assertFalse([sha for sha in shas if sha in body], f"{label}: a commit is named though nothing entered the lane:\n{body}")
                self.assertFalse(UNDETERMINED.search(body), f"{label}: an entrant is claimed:\n{body}")
        rows.check()


class TestTq600a13XiiNoticeLifecycle(TimingNoticeCase):
    def test_tq600a_13_xii_the_timing_notice_opens_on_red_and_closes_on_green(self):
        # covers: TQ-600a-13-xii
        # angle: criterion
        """Red run 1 creates ONE `post-merge-timing` issue; red run 2 updates it (no second issue); green run 3 closes it.

        Every read and write is on the timing label and the timing workflow's runs; the correctness suite's runs and the
        `post-merge-red` label are never touched.
        """
        git = self.git
        self.svc.timing_runs = [make_run(1, "failure", head_sha=git.h)]
        first = self.apply_timing(timing_verdict({FAILING_ID: "failed"}, run_id=101, head_sha=git.h), 101)
        self.assertEqual(0, first.code, first.log)
        self.assertEqual([("create", None)], self.svc.writes())
        self.assertEqual([TIMING_LABEL], self.svc.writes_of("create")[0][1]["labels"])

        self.svc.write_attempts.clear()
        self.svc.timing_runs = [make_run(1, "failure", head_sha=git.h), make_run(2, "failure", head_sha=git.h)]
        second = self.apply_timing(timing_verdict({FAILING_ID: "failed"}, run_id=102, head_sha=git.h), 102)
        self.assertEqual(0, second.code, second.log)
        self.assertEqual([("comment", 1), ("edit", 1)], self.svc.writes(), "a second red run updates the one notice")

        self.svc.write_attempts.clear()
        self.svc.timing_runs = [make_run(n, "failure" if n < 3 else "success", head_sha=git.h) for n in (1, 2, 3)]
        third = self.apply_timing(timing_verdict({FAILING_ID: "passed"}, run_id=103, head_sha=git.h), 103)
        self.assertEqual(0, third.code, third.log)
        self.assertEqual([("close", 1), ("comment", 1)], self.svc.writes(), "a green run closes the notice")
        self.assertEqual({TIMING_LABEL}, set(self.listings()))
        history = [path for _method, path in self.svc.requests if "/actions/workflows/" in path]
        self.assertTrue(history and all("post-merge-timing.yml" in path for path in history), history)


class TestTq600a13XiiFollowup(unittest.TestCase):
    def test_tq600a_13_xii_the_followup_has_a_timing_job_beside_the_correctness_one(self):
        # covers: TQ-600a-13-xii
        # angle: boundary
        """Structural by necessity (a `workflow_run` name gate cannot be evaluated offline).

        Each lane's job is gated to its own workflow's name, so a timing run never writes the `post-merge-red` notice
        and a correctness run never writes the timing one; the timing job applies with `--lane timing`, the other does not.
        """
        doc = load_workflow(FOLLOWUP_WORKFLOW)
        timing, notice = find_job(doc, "timing-notice"), find_job(doc, "notice")
        self.assertIsNotNone(timing, "the follow-up workflow carries a job `timing-notice`")
        self.assertIsNotNone(notice, "the follow-up workflow keeps its job `notice`")
        self.assertIn("'Post-merge timing suite'", str(timing[1].get("if")))
        self.assertIn("'Post-merge suite'", str(notice[1].get("if")))
        self.assertNotIn("timing", str(notice[1].get("if")).replace("Post-merge suite", ""))
        self.assertEqual({"issues": "write", "actions": "read", "contents": "read"}, timing[1].get("permissions"))
        runs = [step["run"] for step in timing[1].get("steps") or [] if "run" in step]
        self.assertTrue(any("post_merge_notice.py" in text and "apply" in text and "--lane timing" in text for text in runs), runs)
        self.assertFalse([text for text in runs if "${{" in text], "context reaches the module through env:")
        notice_runs = " ".join(step.get("run", "") for step in notice[1].get("steps") or [])
        self.assertNotIn("--lane timing", notice_runs)
        concurrency = timing[1].get("concurrency") or {}
        self.assertTrue(concurrency.get("group"), "two applies must never interleave")
        self.assertIs(False, concurrency.get("cancel-in-progress"))


if __name__ == "__main__":
    unittest.main()
