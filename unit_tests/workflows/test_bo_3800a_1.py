"""BO-3800a-1: a refusal that asks for a craft leaves the author's change untouched,
does not advance the run past delivery, and re-offers that same change to the same
standard once the file has been put right.

One test per declared descriptor, named exactly as the AC's test_spec names it.

Every drive EXECUTES build-feature.js and build-ticket.js (TWIN_DRIVERS) through the
driver harness (``unit_tests/prompt_assembly/_driver_harness.py``); the assertions read
what the run dispatched, in what order, and what it left in the working tree and in the
ticket record. The ticket record is written by ``yaml.safe_dump`` (the real serializer)
and the remedy declaration is lifted from the real package seed routing table. The
restructuring step is a STAND-IN supplied by the scenario, never a named party's
behaviour (BO-3800b-1's identity is out of scope here).

Named mutations (descriptors 7-9) are EXECUTED: a real recorded run is altered the way
the wrong build would alter it, and each arm predicate must go red or stay green
exactly as the AC lists.

Honest limit, stated and not hidden: the harness scripts the replies of the phase
agents, so it cannot make a real agent reset a real tree. "The change is intact" is
therefore established two ways -- the tree digest around the whole run, and the
requirement that no dispatch in the run tells anyone to reset, stash, check out, clean
or restore.
"""

from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bo3800a_support as A  # noqa: E402

S, H, TWINS = A.S, A.H, A.TWINS
LIST_ALL = list(A.ARMS)


@unittest.skipUnless(S.node_available(), "node is not on PATH")
class TestBo3800a1(unittest.TestCase):
    def setUp(self):
        self._dirs = []

    def tearDown(self):
        for d in self._dirs:
            shutil.rmtree(d, ignore_errors=True)

    def _run(self, driver, second_demand):
        wt = S.make_worktree("bo3800a1-")
        self._dirs.append(wt)
        return A.drive_hold(driver, wt, second_demand)

    @staticmethod
    def _still_short():
        return S.size_demand(path=A.NAMED_FILE, lines=40)

    def _recorded(self, second_demand):
        """A real recorded run on build-feature.js."""
        run, _obs, _path = self._run("build-feature.js", second_demand)
        return run

    # ---- descriptor 1 -------------------------------------------------------
    def test_held_refusal_leaves_the_authors_change_byte_identical(self):
        # covers: BO-3800a-1
        # angle: criterion
        """After a refusal that names the restructuring craft, the working tree the
        author left is byte-identical, and nobody was told to put it back."""
        for driver in TWINS:
            with self.subTest(driver=driver):
                run, _obs, _path = self._run(driver, self._still_short())
                self.assertIn(S.SPECIALIST, run.labels, "the refusal path was not taken")
                self.assertTrue(run.tree_before, "no author's change was standing")
                self.assertIn(A.NAMED_FILE, run.tree_before)
                self.assertEqual(run.tree_after, run.tree_before)
                for label, _att, prompt in run.prompts:
                    self.assertIsNone(A.TREE_MUTATION.search(prompt), f"{label}: {prompt[:300]}")

    # ---- descriptor 2 -------------------------------------------------------
    def test_held_refusal_does_not_record_the_delivery_phase_completed(self):
        # covers: BO-3800a-1
        # angle: criterion
        """The ticket record the run actually wrote is not 'done' after a refused,
        unmet delivery, and no completion write was applied to it."""
        for driver in TWINS:
            with self.subTest(driver=driver):
                run, obs, path = self._run(driver, self._still_short())
                self.assertFalse(S.completed(path), obs.get("result"))
                self.assertEqual(H.read_record(path)["lifecycle_status"], "todo")
                self.assertEqual(run.applied_completion_writes, 0)
                self.assertFalse(H.is_success_outcome(obs.get("result")))

    # ---- descriptor 3 -------------------------------------------------------
    def test_no_phase_after_delivery_runs_while_the_change_is_held(self):
        # covers: BO-3800a-1
        # angle: criterion
        """A phase ordered after delivery (pull-request) never appears between the
        refusal and the re-offer; it runs only after the retry lands."""
        order = H.canonical_phase_order()
        self.assertGreater(order.index(A.AFTER_DELIVERY), order.index("commit"))
        for driver in TWINS:
            with self.subTest(driver=driver):
                held, _o, _p = self._run(driver, self._still_short())
                self.assertNotIn(A.AFTER_DELIVERY, held.labels, held.labels)
                landed, _o, _p = self._run(driver, None)
                last_commit = max(i for i, v in enumerate(landed.labels) if v == "commit")
                self.assertIn(A.AFTER_DELIVERY, landed.labels, "control row: it must run once delivery lands")
                self.assertEqual(landed.labels.count(A.AFTER_DELIVERY), 1)
                self.assertGreater(landed.labels.index(A.AFTER_DELIVERY), last_commit, landed.labels)

    # ---- descriptor 4 -------------------------------------------------------
    def test_second_delivery_attempt_carries_the_authors_original_change(self):
        # covers: BO-3800a-1
        # angle: criterion
        """Delivery is attempted exactly twice, for the same ticket, over the tree the
        author left, and nothing was re-authored or re-staged in between."""
        for driver in TWINS:
            with self.subTest(driver=driver):
                run, _obs, _path = self._run(driver, None)
                self.assertEqual(run.commit_attempts, 2, run.labels)
                self.assertEqual(run.tree_after, run.tree_before)
                first, second = [p for (lab, _a, p) in run.prompts if lab == "commit"]
                self.assertIsNone(A.TREE_MUTATION.search(second), second[:300])
                # The same delivery dispatch for the same ticket, not a rewritten one.
                self.assertEqual(second.split("\n")[0], first.split("\n")[0])
                self.assertEqual(sum(1 for (lab, _a, _p) in run.prompts if lab == "python-coder"), 1)

    # ---- descriptor 5 -------------------------------------------------------
    def test_second_attempt_is_judged_by_the_same_unsuppressed_standard(self):
        # covers: BO-3800a-1
        # angle: criterion
        """Control pair: when the standard accepts the retry the ticket completes; when
        it refuses again the very same run does not. The retried dispatch carries no
        skip, override, waiver or exemption in either case."""
        for driver in TWINS:
            with self.subTest(driver=driver):
                landed, _o, lpath = self._run(driver, None)
                refused, _o, rpath = self._run(driver, self._still_short())
                for run in (landed, refused):
                    (retried,) = run.retried_commit_prompts()
                    self.assertIsNone(A.PAST_THE_STANDARD.search(retried), retried[:400])
                self.assertTrue(S.completed(lpath))
                self.assertFalse(S.completed(rpath))
                self.assertEqual(landed.applied_completion_writes, 1)
                self.assertEqual(refused.applied_completion_writes, 0)

    # ---- descriptor 6 -------------------------------------------------------
    def test_the_re_offer_never_precedes_the_restructuring_step(self):
        # covers: BO-3800a-1
        # angle: boundary
        """The sequence is exactly commit, stand-in step, commit: one step between the
        attempts, and no second attempt before it. Inspected at the moment after the
        refusal, the dispatch record shows a single commit."""
        for driver in TWINS:
            with self.subTest(driver=driver):
                run, _obs, _path = self._run(driver, None)
                ls = run.labels
                commits = [i for i, v in enumerate(ls) if v == "commit"]
                self.assertEqual(len(commits), 2, ls)
                self.assertEqual(ls[commits[0] + 1 : commits[1]], [S.SPECIALIST], ls)
                self.assertEqual(ls.count(S.SPECIALIST), 1, ls)
                after_refusal = ls[: commits[0] + 1]
                self.assertEqual(after_refusal.count("commit"), 1, after_refusal)
                self.assertNotIn(S.SPECIALIST, after_refusal)

    # ---- descriptors 7-9: the named mutations, executed ----------------------
    def test_discard_injection_reddens_only_the_hold_arms(self):
        # covers: BO-3800a-1
        # angle: failure
        """Mutation (1) THE DISCARD. RED: change-still-present, second-attempt-carries-
        the-change. STAY GREEN: ordering, nothing-after-delivery, not-recorded-completed,
        same-standard, completes-because. (The BO-3800b-1/-2 halves are deferred with
        those records, INF-800f.)"""
        real = self._recorded(None)
        self.assertEqual(A.verdicts(real), dict.fromkeys(LIST_ALL, True), "the unmutated run must satisfy every arm")
        v = A.verdicts(A.mutate_discard(real))
        for red in ("intact", "second_attempt"):
            self.assertFalse(v[red], v)
        for green in ("order", "nothing_after", "not_completed", "same_standard", "completes_because"):
            self.assertTrue(v[green], v)

    def test_forced_pass_injection_reddens_only_the_same_standard_arms(self):
        # covers: BO-3800a-1
        # angle: failure
        """Mutation (2) THE FORCED PASS, applied to a run whose retry the standard
        refused. RED: judged-by-the-same-standard, completes-because-the-file-meets-the-
        demand. STAY GREEN: the hold arms and ordering."""
        real = self._recorded(self._still_short())
        v0 = A.verdicts(real)
        self.assertEqual(v0, dict.fromkeys(LIST_ALL, True), f"the unmutated refused run must satisfy every arm: {v0}")
        v = A.verdicts(A.mutate_forced_pass(real))
        for red in ("same_standard", "completes_because"):
            self.assertFalse(v[red], v)
        for green in ("intact", "not_completed", "nothing_after", "second_attempt", "order"):
            self.assertTrue(v[green], v)

    def test_dropped_retry_injection_reddens_only_the_second_attempt_arms(self):
        # covers: BO-3800a-1
        # angle: failure
        """Mutation (3) THE DROPPED RETRY. RED: second-attempt, completes. STAY GREEN:
        change-still-present, not-recorded-completed, ordering, nothing-after-delivery."""
        real = self._recorded(None)
        v = A.verdicts(A.mutate_dropped_retry(real))
        for red in ("second_attempt", "completes_because"):
            self.assertFalse(v[red], v)
        for green in ("intact", "not_completed", "order", "nothing_after"):
            self.assertTrue(v[green], v)

    # ---- descriptor 10: the twins ------------------------------------------
    def test_the_hold_branch_behaves_identically_in_both_phase_loop_twins(self):
        # covers: BO-3800a-1
        # angle: seam
        # reachability surface: templates/workflows-js/build-ticket.js
        """The same refusal, driven through both twins, gives the same hold, the same
        non-completion and the same re-offer -- asserted from two runs per scenario."""
        self.assertEqual(sorted(TWINS), ["build-feature.js", "build-ticket.js"])
        for second in (None, self._still_short()):
            runs = {d: self._run(d, second)[0] for d in TWINS}
            a, b = runs["build-feature.js"], runs["build-ticket.js"]
            with self.subTest(second_accepted=second is None):
                self.assertEqual(a.labels, b.labels)
                self.assertEqual(A.verdicts(a), A.verdicts(b))
                self.assertEqual(A.verdicts(b), dict.fromkeys(LIST_ALL, True))
                self.assertEqual((a.completed, a.applied_completion_writes), (b.completed, b.applied_completion_writes))
                self.assertEqual(a.tree_after == a.tree_before, b.tree_after == b.tree_before)

    # ---- descriptor 11: reachability ---------------------------------------
    def test_hold_and_re_offer_are_reachable_from_the_drivers_own_top_level_body(self):
        # covers: BO-3800a-1
        # angle: reachability
        # reachability surface: unit_tests/prompt_assembly/_driver_harness.py executing build-feature.js
        """Driven through the harness executing build-feature.js's own top-level body,
        a refusal that names the craft makes the run hold, ask, and re-offer; the same
        run for a refusal that names no craft does not (so the outcome is consumed in
        control flow, not merely present)."""
        wt = S.make_worktree("bo3800a1-reach-")
        self._dirs.append(wt)
        held, obs, path = A.drive_hold("build-feature.js", wt, None)
        self.assertEqual(held.labels.count(S.SPECIALIST), 1, held.labels)
        self.assertEqual(held.commit_attempts, 2)
        self.assertTrue(S.completed(path))
        self.assertEqual(A.verdicts(held), dict.fromkeys(LIST_ALL, True))
        # Control: an author-clears refusal (check-doc-links) engages nobody.
        wt2 = S.make_worktree("bo3800a1-reach-ctl-")
        self._dirs.append(wt2)
        control, _o, _p = A.drive_hold("build-feature.js", wt2, None, hook_id="check-doc-links")
        self.assertNotIn(S.SPECIALIST, control.labels)
        self.assertNotEqual(control.labels, held.labels)


if __name__ == "__main__":
    unittest.main()
