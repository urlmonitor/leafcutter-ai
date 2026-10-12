"""
MODULE: unit_tests/workflows/test_inf_700a_5_iii.py
GOAL: Behavioural tests for INF-700a-5-iii as amended (BA, PR #1078; IT PO,
    PR #1090): "Two units of work finishing at the same time never lose a
    learning between them; a duplicate across unmerged branches is the
    accepted failure".

AC: docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700a-5-iii.yaml

WHAT IS UNDER TEST: the production knowledge-routing step --
    scripts/knowledge/completion_routing_cli.py (`stage` before a unit of
    work's own commit, `observe` after it, `waiting` on demand) -- run in real
    subprocesses against a real scratch install (_inf700a5iii_scratch.py: a
    bare origin, a base clone, linked worktrees on their own branches) and ONE
    shared sink and claim store. The claim step's off switch
    (claim_and_confirm_routed's `arbitration_enabled`) is deliberately not on
    the CLI (it_requirements line 2), so the two tests that need it run that
    claim step itself -- the same "find the text on origin/main, then claim"
    sequence stage_completion performs -- in separate processes sharing the
    real claim store and the real flock beside it.

THE CONFIRMATION RULE THESE TESTS HOLD THE CODE TO (BrainCandy, 2026-10-08):
    a record is never marked routed at write or commit time; a run claims it
    only once its text is on origin/main; two unmerged overlapping runs both
    write it (a bounded duplicate, never a loss); after the merge, later runs
    claim instead of writing; two runs sharing the claim store never both
    claim one record; every degraded path fails toward the duplicate.

HISTORY: until 2026-10-09 this file held three thread-based tests written to
    the pre-amendment criteria (one write across unmerged branches; two writes
    with the arbitration off). They were rewritten to the amended descriptors;
    see the DECISION HISTORY at the end of this file.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

import workflows._inf700a5_fixtures as fx  # noqa: E402
import workflows._inf700a5iii_scratch as scratch  # noqa: E402

_DEST = "memory/inf700a5iii_destination.md"
_LEARNING = "concurrent completions must not lose this learning"
_BOOKKEEPING_PAIRS = 20
_ARBITRATION_ROUNDS = 5


class _ConcurrencyCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.s = scratch.ScratchInstall(self.root / "install", {_DEST: "seed\n"})

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def record_hash(self, install: scratch.ScratchInstall | None = None) -> str:
        install = install or self.s
        records = fx.load_completion_routing()._state.read_eligible_sink_records(install.sink)
        self.assertEqual(len(records), 1, records)
        return records[0][0]

    def stage_pair(self, wa: Path, wb: Path, install: scratch.ScratchInstall | None = None) -> list[dict]:
        """Both units of work reach `stage` together; returns both replies."""
        install = install or self.s
        results = install.cli_together(
            [install.cli_argv("stage", wa), install.cli_argv("stage", wb)]
        )
        scratch.assert_overlapped(self, results)
        for result in results:
            self.assertEqual(result["returncode"], 0, result["stderr"])
        return [r["reply"] for r in results]

    def commit_own_work(self, wt: Path, branch: str, manifest: list[str]) -> None:
        """The unit of work's own commit: its output plus the manifest, by name."""
        (wt / f"own_{branch}.txt").write_text(f"{branch}\n", encoding="utf-8")
        fx.commit_paths(wt, [f"own_{branch}.txt", *manifest], f"unit of work {branch}")

    def overlapping_pair_committed(self) -> tuple[Path, Path]:
        """Emit the learning, run two overlapping stages, commit both branches."""
        self.s.emit(_LEARNING, _DEST)
        wa, wb = self.s.worktree("a"), self.s.worktree("b")
        replies = self.stage_pair(wa, wb)
        for reply in replies:
            self.assertEqual(reply["written"], 1, f"each unconfirmed run writes it: {reply}")
            self.assertEqual(reply["manifest"], [_DEST], reply)
        self.assertEqual(self.s.claims(), [], "a record must not be marked routed at write time")
        self.commit_own_work(wa, "a", replies[0]["manifest"])
        self.commit_own_work(wb, "b", replies[1]["manifest"])
        return wa, wb

    def branch_copies(self, wt: Path) -> int:
        return fx._run_git(["show", f"HEAD:{_DEST}"], wt).stdout.count(_LEARNING)

    def publish_learning(self) -> None:
        """One complete unit of work that routes the learning and merges."""
        self.s.emit(_LEARNING, _DEST)
        wt = self.s.worktree("pub")
        rc, staged = self.s.cli("stage", wt)
        self.assertEqual((rc, staged["written"]), (0, 1), staged)
        self.commit_own_work(wt, "pub", staged["manifest"])
        self.s.merge("pub")


class TestTwoOverlappingUnmergedRuns(_ConcurrencyCase):
    def test_two_overlapping_unmerged_runs_lose_nothing_and_duplicate_at_most_once_per_branch(
        self,
    ) -> None:
        # covers: INF-700a-5-iii
        # angle: criterion
        wa, wb = self.overlapping_pair_committed()
        for wt in (wa, wb):
            rc, observed = self.s.cli("observe", wt, "--commit-status", "ok")
            self.assertEqual((rc, observed["written"]), (0, 1), observed)
            self.assertEqual(self.branch_copies(wt), 1, "at most one copy per branch")
        self.assertEqual(self.s.claims(), [], "a record must not be marked routed at commit time")

        self.s.merge("a")
        self.s.merge("b")
        merged = self.s.on_origin_main(_DEST).count(_LEARNING)
        self.assertGreaterEqual(merged, 1, "the learning was lost between the two runs")
        self.assertLessEqual(merged, 2, "more copies than branches that staged it")

        wc = self.s.worktree("c")
        rc, later = self.s.cli("stage", wc)
        self.assertEqual(rc, 0, later)
        self.assertEqual((later["written"], later["manifest"]), (0, []), later)
        self.assertEqual(self.s.claims(), [self.record_hash()], "the later run claims it")
        self.commit_own_work(wc, "c", later["manifest"])
        added = fx._run_git(["diff", "origin/main", "HEAD", "--", _DEST], wc).stdout
        self.assertEqual(added, "", "the later run's branch adds no further copy")


class TestNeitherRunConcludesTheOtherHasIt(_ConcurrencyCase):
    def test_neither_run_concludes_the_other_has_it(self) -> None:
        # covers: INF-700a-5-iii
        # angle: failure
        wa, wb = self.overlapping_pair_committed()
        self.assertEqual(self.branch_copies(wa) + self.branch_copies(wb), 2,
                         "neither run deferred to the other")
        self.assertEqual(self.s.claims(), [], "no unmerged write marks the record")
        rc, waiting = self.s.cli("waiting", None)
        self.assertEqual((rc, waiting["waiting"]), (0, 1), f"still eligible: {waiting}")

        self.s.merge("a")
        self.assertGreaterEqual(self.s.on_origin_main(_DEST).count(_LEARNING), 1)
        rc, next_run = self.s.cli("stage", wb)
        self.assertEqual(rc, 0, next_run)
        self.assertEqual(next_run["written"], 0, f"claims rather than writes: {next_run}")
        self.assertEqual(self.s.claims(), [self.record_hash()], next_run)
        rc, waiting = self.s.cli("waiting", None)
        self.assertEqual(waiting["waiting"], 0, waiting)


class TestTheRoutingBookkeepingSurvives(_ConcurrencyCase):
    def test_the_routing_bookkeeping_survives_two_runs_updating_it_at_once(self) -> None:
        # covers: INF-700a-5-iii
        # angle: boundary
        self.publish_learning()
        published = self.record_hash()
        wa, wb = self.s.worktree("a"), self.s.worktree("b")
        expected = {published}
        for i in range(_BOOKKEEPING_PAIRS):
            results = self.s.claim_together([
                {"working_dir": wa, "extra_ids": [f"shared-{i}", f"a-{i}"]},
                {"working_dir": wb, "extra_ids": [f"shared-{i}", f"b-{i}"]},
            ], arbitration=True)
            scratch.assert_overlapped(self, results)
            for result in results:
                self.assertIn(published, result["reply"]["ids"], "both found it on origin/main")
            expected |= {f"shared-{i}", f"a-{i}", f"b-{i}"}
            try:
                claims = self.s.claims()
            except json.JSONDecodeError as exc:
                self.fail(f"pair {i}: claim store torn or half-written: {exc}")
            self.assertIsInstance(claims, list, f"pair {i}")
            self.assertEqual(set(claims), expected,
                             f"pair {i}: the store must hold every claim of both runs, "
                             f"not only the last writer's")
            shared_claims = sum(f"shared-{i}" in r["reply"]["newly"] for r in results)
            self.assertEqual(shared_claims, 1, f"pair {i}: {results!r}")


class TestALostLearningIsTheFailure(_ConcurrencyCase):
    def test_a_lost_learning_is_the_failure_the_arbitration_must_not_produce(self) -> None:
        # covers: INF-700a-5-iii
        # angle: failure
        wa, _ = self.overlapping_pair_committed()
        self.s.discard(wa, "a")
        self.assertEqual(self.s.claims(), [],
                         "the discarded branch's write must not have marked the record")
        self.s.merge("b")
        self.assertEqual(self.s.on_origin_main(_DEST).count(_LEARNING), 1,
                         "the learning must survive the discarded branch")
        wc = self.s.worktree("c")
        rc, later = self.s.cli("stage", wc)
        self.assertEqual((rc, later["written"]), (0, 0), later)
        self.assertEqual(self.s.claims(), [self.record_hash()], later)


class TestConcurrentUnitsDoNotDelayOrFailEachOther(_ConcurrencyCase):
    @staticmethod
    def outcome(stage_rc: int, staged: dict, observe_rc: int, observed: dict) -> tuple:
        return (stage_rc, staged["case"], staged["written"], staged["unwritten"],
                observe_rc, observed["case"], observed["written"], observed["unwritten"])

    def test_concurrent_units_of_work_do_not_delay_or_fail_each_other(self) -> None:
        # covers: INF-700a-5-iii
        # angle: criterion
        solo = scratch.ScratchInstall(self.root / "solo", {_DEST: "seed\n"})
        solo.emit(_LEARNING, _DEST)
        wt = solo.worktree("solo")
        stage_rc, staged = solo.cli("stage", wt)
        self.commit_own_work(wt, "solo", staged["manifest"])
        observe_rc, observed = solo.cli("observe", wt, "--commit-status", "ok")
        alone = self.outcome(stage_rc, staged, observe_rc, observed)
        self.assertEqual(alone[:2] + alone[4:6], (0, "completed", 0, "completed"), alone)

        self.s.emit(_LEARNING, _DEST)
        wa, wb = self.s.worktree("a"), self.s.worktree("b")
        stages = self.s.cli_together([self.s.cli_argv("stage", wa), self.s.cli_argv("stage", wb)])
        scratch.assert_overlapped(self, stages)
        self.commit_own_work(wa, "a", stages[0]["reply"]["manifest"])
        self.commit_own_work(wb, "b", stages[1]["reply"]["manifest"])
        observes = self.s.cli_together([
            self.s.cli_argv("observe", wa, "--commit-status", "ok"),
            self.s.cli_argv("observe", wb, "--commit-status", "ok"),
        ])
        scratch.assert_overlapped(self, observes)
        for name, stage, observe in zip(("a", "b"), stages, observes):
            together = self.outcome(stage["returncode"], stage["reply"],
                                    observe["returncode"], observe["reply"])
            self.assertEqual(together, alone, f"unit of work {name} differs from the solo run")


class TestRemovingTheArbitration(_ConcurrencyCase):
    def test_removing_the_arbitration_makes_the_single_claim_test_fail(self) -> None:
        # covers: INF-700a-5-iii
        # angle: reachability
        # surface_invoked: the claim step of two completion paths sharing one
        # claim store, driven with the arbitration enabled and then disabled
        self.publish_learning()
        published = self.record_hash()
        wa, wb = self.s.worktree("a"), self.s.worktree("b")
        runs = [{"working_dir": wa}, {"working_dir": wb}]
        for enabled, label in ((True, "on"), (False, "off")):
            for i in range(_ARBITRATION_ROUNDS):
                state = self.s.logs / f"claims-{label}-{i}.json"
                results = self.s.claim_together(runs, arbitration=enabled, state=state)
                scratch.assert_overlapped(self, results)
                for result in results:
                    self.assertEqual(result["reply"]["ids"], [published],
                                     "both runs must find the text on origin/main")
                newly = sum(len(r["reply"]["newly"]) for r in results)
                stored = json.loads(state.read_text(encoding="utf-8"))
                if enabled:
                    self.assertEqual(newly, 1, f"arbitration on, round {i}: one claim: {results!r}")
                    self.assertEqual(stored, [published])
                else:
                    lost = published not in stored
                    self.assertTrue(
                        newly == 2 or lost,
                        f"arbitration off, round {i}: still a single claim, so the "
                        f"'on' result was passing on timing, not arbitration: {results!r}",
                    )


class TestEveryDegradedPathFailsTowardTheDuplicate(_ConcurrencyCase):
    def test_a_base_branch_that_cannot_be_fetched_or_resolved_writes_again_and_marks_nothing(
        self,
    ) -> None:
        # covers: INF-700a-5-iii
        # angle: failure
        self.s.emit(_LEARNING, _DEST)
        unresolved, unfetched = self.s.worktree("unresolved"), self.s.worktree("unfetched")
        self.s.push_from_outside(_DEST, _LEARNING)  # the text IS on origin/main now

        rc, reply = self.s.cli("stage", unresolved, "--base", "origin/no-such-branch")
        self.assertEqual((rc, reply["written"]), (0, 1), f"unresolvable base: {reply}")
        self.assertEqual(self.s.claims(), [], "unresolvable base must not mark")

        bogus = str(self.root / "no-such-remote.git")
        fx._run_git(["remote", "set-url", "origin", bogus], self.s.base)
        rc, reply = self.s.cli("stage", unfetched)
        self.assertEqual((rc, reply["written"]), (0, 1), f"unfetchable base: {reply}")
        self.assertEqual(self.s.claims(), [], "unfetchable base must not mark")

        # Control: with the base reachable again the same run claims instead.
        fx._run_git(["remote", "set-url", "origin", str(self.s.origin)], self.s.base)
        rc, reply = self.s.cli("stage", unfetched)
        self.assertEqual((rc, reply["written"]), (0, 0), reply)
        self.assertEqual(self.s.claims(), [self.record_hash()], reply)

    def test_a_claim_whose_arbitration_cannot_be_obtained_proceeds_unarbitrated(self) -> None:
        # covers: INF-700a-5-iii
        # angle: failure
        not_a_dir = self.root / "a-regular-file"
        not_a_dir.write_text("", encoding="utf-8")
        results = self.s.claim_together(
            [{"extra_ids": ["degraded-claim"], "lock": not_a_dir / "routing.lock"}],
            arbitration=True,
        )
        self.assertEqual(results[0]["returncode"], 0, results[0]["stderr"])
        self.assertEqual(results[0]["reply"]["newly"], ["degraded-claim"],
                         "an unobtainable lock must not skip the claim")
        self.assertEqual(self.s.claims(), ["degraded-claim"])


if __name__ == "__main__":
    unittest.main()


# DECISION HISTORY
# ================================================================================
# - 2026-09-21 [test-writer]: RED baseline, three thread-based tests against
#   claim_and_confirm_routed only.
# - 2026-10-09 [test-writer/INF-700a-5-iii amended]: Rewritten to the amended
#   criteria (PR #1078) and IT PO pass (PR #1090). Retracted:
#   test_two_overlapping_routing_steps_write_the_same_learning_once (one write
#   across unmerged branches) and test_removing_the_arbitration_makes_the_
#   write_once_test_fail (two claims off, never contrasted with one claim on).
#   test_neither_run_concludes_the_other_has_it kept its name, rewritten to its
#   new assertions. Added the three descriptors that had no test (bookkeeping,
#   lost learning, no delay) and the degraded-path clause. Every test now runs
#   the real CLI / claim step in separate processes over real scratch git and
#   one shared claim store. (#INF-700a-5-iii)
