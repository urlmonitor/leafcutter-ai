"""BO-3800e-1: a refusal that asks for no craft engages no restructuring specialist and
recovers exactly the way it does before this capability exists.

One test per declared test_spec descriptor, named exactly as the AC names it, plus one
derived from the AC's last it_requirement (an unreadable outcome is a named stop).

Every assertion is an EQUALITY AGAINST A BASELINE RUN: the driver as it stood before the
handoff capability (materialised from git history by ``_bo3800e_support.baseline_script``),
driven through the same harness on the same fixture. The baseline is measured, never typed.
Every drive executes build-feature.js / build-ticket.js's own top-level body.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bo3800e_support as E  # noqa: E402

S, H, TWINS = E.S, E.H, E.TWINS
NO_DISPOSITION_SHAPES = {
    "key absent": lambda hook: {"hook_id": hook, "skills": [], "demand": S.size_demand(path=E.NAMED_FILE, lines=20)},
    "empty string": lambda hook: {"hook_id": hook, "disposition": "", "skills": [], "demand": S.size_demand(path=E.NAMED_FILE, lines=20)},
    "blank string": lambda hook: {"hook_id": hook, "disposition": "   ", "skills": [], "demand": S.size_demand(path=E.NAMED_FILE, lines=20)},
    "null": lambda hook: {"hook_id": hook, "disposition": None, "skills": [], "demand": S.size_demand(path=E.NAMED_FILE, lines=20)},
}


def _results(remedy):
    decl = E.author_clears_decl()
    return {
        "commit": [E.refusal(decl, S.size_demand(path=E.NAMED_FILE, lines=20), remedy=remedy), {"status": "ok"}],
        E.SPECIALIST: {"status": "ok"},
    }


def _specialist_results():
    decl = S.declaration("check-file-size", agent=E.SPECIALIST, skills=[])
    return {
        "commit": [S.refusal_reply(decl, S.size_demand(path=E.NAMED_FILE, lines=120)), {"status": "ok"}],
        E.SPECIALIST: {"status": "ok"},
    }


def _specialist_decls():
    return {"check-file-size": S.declaration("check-file-size", agent=E.SPECIALIST, skills=[])}


@unittest.skipUnless(E.node_available(), "node is not on PATH")
class TestBo3800e1(unittest.TestCase):
    # ---- descriptor 1 -------------------------------------------------------
    def test_author_clearable_refusal_dispatch_record_is_identical_to_the_baseline_run(self):
        # covers: BO-3800e-1
        # covers: BO-3800e
        # angle: criterion
        """An author-clearable refusal gives the same ordered dispatch record and the same
        delivery outcome as the pre-capability driver on the same fixture (both twins).
        Control: a specialist-disposition refusal on the SAME ticket does differ from that
        baseline, so the equality is a comparison that can fail."""
        for driver in TWINS:
            with self.subTest(driver=driver):
                base, cur = E.paired(driver, E.author_clearable_results, E.author_clearable_decls)
                self.assertEqual(base.labels, ["test-writer", "python-coder", "commit", "python-coder", "commit"], base.labels)
                self.assertEqual(cur.comparable(), base.comparable())
                self.assertNotIn(E.SPECIALIST, cur.labels)
                self.assertTrue(cur.completed)
                self.assertEqual(cur.declaration_reads, [])
                spec = E.drive(E.current_script(driver), _specialist_results, _specialist_decls)
                self.assertIn(E.SPECIALIST, spec.labels, "control row: the specialist case must engage it")
                self.assertNotEqual(spec.labels, base.labels)

    # ---- descriptor 2 -------------------------------------------------------
    def test_refusal_stating_no_disposition_at_all_matches_the_baseline_run(self):
        # covers: BO-3800e-1
        # angle: criterion
        """A refusal with no remedy record at all (the shape every refusing standard has
        today) produces the baseline's parties, order and outcome, and consults nothing."""
        for driver in TWINS:
            with self.subTest(driver=driver):
                base, cur = E.paired(driver, lambda: _results(None))
                self.assertEqual(base.labels, ["test-writer", "python-coder", "commit", "python-coder", "commit"], base.labels)
                self.assertEqual(cur.comparable(), base.comparable())
                self.assertNotIn(E.SPECIALIST, cur.labels)
                self.assertEqual(cur.declaration_reads, [])

    # ---- descriptor 3 -------------------------------------------------------
    def test_absent_disposition_is_not_read_as_the_specialist_case(self):
        # covers: BO-3800e-1
        # angle: failure
        # must_catch: ABSENCE READ AS THE SPECIALIST CASE -- a remedy with no usable disposition engages the specialist
        """A disposition that is absent, null, empty or blank takes the existing route (the
        baseline's record), reads no declaration and engages nobody new. Control: a remedy
        stating engage-specialist does engage the specialist, so a build that never engages
        would fail the control and one that engages on absence would fail the shapes."""
        for driver in TWINS:
            ctl = E.drive(E.current_script(driver), _specialist_results, _specialist_decls)
            self.assertIn(E.SPECIALIST, ctl.labels, f"control row ({driver})")
            for shape, make in NO_DISPOSITION_SHAPES.items():
                with self.subTest(driver=driver, shape=shape):
                    base, cur = E.paired(driver, lambda: _results(make("check-file-size")), E.author_clearable_decls)
                    self.assertEqual(base.labels.count("commit"), 2, base.labels)
                    self.assertNotIn(E.SPECIALIST, cur.labels, cur.labels)
                    self.assertEqual(cur.comparable(), base.comparable())
                    self.assertEqual(cur.declaration_reads, [])

    # ---- descriptor 4 -------------------------------------------------------
    def test_over_broad_summons_injection_reddens_both_arms_here(self):
        # covers: BO-3800e-1
        # angle: failure
        # must_catch: THE OVER-BROAD SUMMONS -- act on any refusal without reading the stated disposition
        """The named mutation, EXECUTED on real recorded runs. Unmutated, both arms hold.
        Under the over-broad summons both arms go RED, while the accepted-run arm of
        BO-3800e-2 (no refusal in it) stays GREEN. Coupling to BO-3800b-2's paired arm is
        reported, not suppressed."""
        driver = "build-feature.js"
        base1, cur1 = E.paired(driver, E.author_clearable_results, E.author_clearable_decls)
        base2, cur2 = E.paired(driver, lambda: _results(None))
        base3, cur3 = E.paired(driver, E.accepted_results)
        for cur, base in ((cur1, base1), (cur2, base2), (cur3, base3)):
            self.assertTrue(E.arm_nobody_extra_engaged(cur, base))
            self.assertTrue(E.arm_same_as_baseline(cur, base))
        for cur, base, arm in ((cur1, base1, "arm 1 (author-clearable)"), (cur2, base2, "arm 2 (no disposition)")):
            mutated = E.mutate_over_broad_summons(cur)
            self.assertFalse(E.arm_nobody_extra_engaged(mutated, base), arm)
            self.assertFalse(E.arm_same_as_baseline(mutated, base), arm)
        mutated_accepted = E.mutate_over_broad_summons(cur3)
        self.assertTrue(E.arm_nobody_extra_engaged(mutated_accepted, base3), "BO-3800e-2 must stay green")
        self.assertTrue(E.arm_no_extra_work(mutated_accepted, base3), "BO-3800e-2 must stay green")

    # ---- descriptor 5 -------------------------------------------------------
    def test_a_hook_absent_from_the_gating_list_still_engages_nobody(self):
        # covers: BO-3800e-1
        # angle: seam
        # must_catch: GATING LIST BYPASSED -- the specialist route selected for a hook that does not gate a commit
        """SEAM: the REAL remedy_handoff.py (run over the real package routing table) feeds
        the REAL driver. check-ticket-ac-limits is declared engage-specialist in that table
        yet is not in blocking_hook_ids, so it does not gate a commit and no handoff may be
        produced for it: the helper must refuse with a non-zero exit and an empty stdout, and
        the driver, given the commit step's resulting report, engages nobody new. Control:
        check-complexity (listed in blocking_hook_ids) produces a handoff and engages the
        specialist, so the arm can fail. Asserted from runs, never from reading the config."""
        table = E.seed_table()
        self.assertNotIn("check-ticket-ac-limits", table["blocking_hook_ids"], "fixture hook must be non-gating")
        self.assertIn("check-complexity", table["blocking_hook_ids"])
        record = json.dumps([{"path": "docs/x.yaml", "lines_to_remove": 3}])
        output = f"[check-ticket-ac-limits] refused\nAC_LIMITS_REFUSAL_RECORD: {record}\n"
        non_gating = E.real_handoff(table, "check-ticket-ac-limits", output)
        self.assertNotEqual(non_gating.returncode, 0, f"a handoff was produced for a non-gating hook: {non_gating.stdout!r}")
        self.assertEqual(non_gating.stdout.strip(), "")
        complexity_record = json.dumps(S.complexity_demand())
        gating = E.real_handoff(table, "check-complexity", f"[check-complexity] refused\nCOMPLEXITY_REFUSAL_RECORD: {complexity_record}\n")
        self.assertEqual(gating.returncode, 0, gating.stderr)
        payload = json.loads(gating.stdout)
        for driver in TWINS:
            with self.subTest(driver=driver):
                def results(non_gating=non_gating):
                    reply = {"status": "blocker", "message": non_gating.stderr or "no handoff"}
                    return {"commit": [reply, {"status": "ok"}], E.SPECIALIST: {"status": "ok"}}

                decls = {"check-ticket-ac-limits": S.declaration("check-ticket-ac-limits"), "check-complexity": S.declaration("check-complexity")}
                run = E.drive(E.current_script(driver), results, lambda: decls)
                self.assertNotIn(E.SPECIALIST, run.labels, run.labels)
                self.assertEqual(run.labels.count("python-coder"), 1, f"someone was engaged in the hook's place: {run.labels}")
                ctl = E.drive(
                    E.current_script(driver),
                    lambda: {"commit": [payload, {"status": "ok"}], E.SPECIALIST: {"status": "ok"}},
                    lambda: decls,
                )
                self.assertIn(E.SPECIALIST, ctl.labels, "control row: a gating hook's handoff engages the specialist")

    # ---- descriptor 6 -------------------------------------------------------
    def test_the_negative_promise_is_reachable_from_the_drivers_own_top_level_body(self):
        # covers: BO-3800e-1
        # angle: reachability
        # reachability surface: unit_tests/prompt_assembly/_driver_harness.py executing templates/workflows-js/build-feature.js
        """Driven through the harness executing build-feature.js's own top-level body: the
        author-clearable refusal runs the existing route to completion (its result consumed
        in control flow: the retry lands and the ticket is recorded done), engaging nobody
        new; the same run with a specialist disposition takes a different route."""
        base, cur = E.paired("build-feature.js", E.author_clearable_results, E.author_clearable_decls)
        self.assertEqual(cur.comparable(), base.comparable())
        self.assertIsNone(cur.obs.get("error"), cur.obs.get("error"))
        self.assertTrue(cur.completed)
        self.assertEqual(cur.labels.count("commit"), 2)
        spec = E.drive(E.current_script("build-feature.js"), _specialist_results, _specialist_decls)
        self.assertNotEqual(spec.labels, cur.labels)

    # ---- derived from it_requirements[-1] -----------------------------------
    def test_unreadable_delivery_outcome_is_a_named_stop_not_an_absent_disposition(self):
        # covers: BO-3800e-1
        # angle: failure
        # must_catch: UNREADABLE READ AS ABSENT -- a remedy that cannot be understood silently takes the existing route
        """it_requirements: 'A delivery outcome that cannot be read must surface as a named
        stop, never as an absent disposition.' A remedy that is not an object, or whose
        disposition is not text, is unreadable (distinct from absent/empty/blank, which take
        the existing route). The run must stop: nobody is re-engaged, delivery is not
        re-attempted, the ticket is not recorded done, and the outcome is not a success."""
        unreadable = {
            "remedy is a list": ["engage-specialist"],
            "remedy is text": "engage-specialist",
            "disposition is a number": {"hook_id": "check-file-size", "disposition": 7, "skills": [], "demand": S.size_demand(path=E.NAMED_FILE, lines=20)},
            "disposition is a list": {"hook_id": "check-file-size", "disposition": ["author-clears"], "skills": [], "demand": S.size_demand(path=E.NAMED_FILE, lines=20)},
        }
        for driver in TWINS:
            for shape, remedy in unreadable.items():
                with self.subTest(driver=driver, shape=shape):
                    run = E.drive(E.current_script(driver), lambda remedy=remedy: _results(remedy), E.author_clearable_decls)
                    self.assertNotIn(E.SPECIALIST, run.labels, run.labels)
                    self.assertEqual(run.labels.count("commit"), 1, f"delivery retried over an unreadable outcome: {run.labels}")
                    self.assertEqual(run.labels.count("python-coder"), 1, f"the author was re-engaged: {run.labels}")
                    self.assertFalse(run.completed)
                    self.assertFalse(H.is_success_outcome(run.obs.get("result")), run.obs.get("result"))


if __name__ == "__main__":
    unittest.main()
