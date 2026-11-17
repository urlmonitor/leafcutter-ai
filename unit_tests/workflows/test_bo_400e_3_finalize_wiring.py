"""
MODULE: unit_tests/workflows/test_bo_400e_3_finalize_wiring.py
GOAL: RED tests proving finalize-feature.js Step 3.5 is WIRED to the derive/close module and CONSUMES
      its results in control flow (BO-400e-3-ii, -iii, -iv, -v, -vi).

The real workflow runs under the E2 engine harness (unit_tests/_workflow_engine_harness.py); every
dispatch reply is the REAL module's output for a real scratch repository, so the listing, the results
and the leak report under test are the ones the module actually produces. Assertions read the recorded
dispatches and the terminal payload -- never the source text. See _bo400e3_finalize_harness for the
dispatch contract these tests pin.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bo400e3_finalize_harness as H  # noqa: E402
from _bo400e3_support import A01, A02, A04, ac_rel, epic_store  # noqa: E402

ALPHA_SET = {A02, ac_rel("BO-9100a-2")}
PROBE = "step-3.5-closure-probe"
RESET_MERGE = "step-3.5-reset-merge"
CLOSURE_MESSAGE = "chore(tickets): close tickets and source ACs"


class _Case(unittest.TestCase):
    def alpha(self, *, leak=None, **store_kw):
        """(store, derive reply, close reply) -- both from the real module, over a real scratch store."""
        store = epic_store(self, **store_kw)
        derived = store.derive(branch="EPIC-Alpha")
        kw = {}
        if leak is not None:
            kw["scripts_root"] = store.leaky_scripts([leak])
        closed = store.close(derived["set_file"], **kw)
        return store, derived, closed

    def confirmed(self, store, derived, closed, **kw):
        return H.confirmed_run("EPIC-Alpha", str(store.repo), derive=derived, close=closed, **kw)


class TestWiring(_Case):
    def test_finalize_dispatches_the_derivation_and_carries_no_selection_prose(self):
        # covers: BO-400e-3-ii
        # angle: reachability
        """finalize-feature.js dispatches the derivation, hands the closer no record list of its own, and
        no Step 3.5 prompt carries selection logic. The derive reply is CONSUMED: the same run with a
        'nothing to close' reply dispatches no close."""
        store, derived, closed = self.alpha()
        first, second = self.confirmed(store, derived, closed)
        derive_calls = H.calls(first, H.DERIVE)
        self.assertEqual(len(derive_calls), 1, H.labels(first))
        self.assertIn("finalize_closable_set.py", H.prompt_of(derive_calls[0]))
        self.assertIn("derive", H.prompt_of(derive_calls[0]))
        close_calls = H.calls(second, H.CLOSE)
        self.assertEqual(len(close_calls), 1, H.labels(second))
        close_prompt = H.prompt_of(close_calls[0])
        self.assertIn("finalize_closable_set.py", close_prompt)
        for path in ALPHA_SET:
            self.assertNotIn(path, close_prompt, "the closer was handed its own record list")
        for prompt in H.step35_prompts(first) + H.step35_prompts(second):
            for banned in ("git diff --name-only", "origin/main HEAD", "OPEN_TICKETS", "FIND IN-SCOPE",
                           "tickets/**/*.md", "walk the whole"):
                self.assertNotIn(banned, prompt, "selection logic is still in an agent prompt")
        empty = {**derived, "outcome": "nothing_to_close", "reason_code": "no_records_changed",
                 "records": []}
        third = H.run_finalize("EPIC-Alpha", str(store.repo), derive=empty, close=closed)
        self.assertEqual(len(H.calls(third, H.DERIVE)), 1, H.labels(third))
        self.assertEqual(H.calls(third, H.CLOSE), [], "a nothing-to-close reply still dispatched a close")

    def test_leak_report_reaches_the_finalize_report_and_step_is_not_completed(self):
        # covers: BO-400e-3-iii
        # angle: reachability
        """The real close step leaked a write onto alpha-01: the run's report names alpha-01.md as closed
        outside its set with before/after status, Step 3.5 is absent from completed_steps, no outcome
        line says the closure completed, and no closure commit is dispatched."""
        leak = {"after": "ticket", "target": "", "mode": "status", "key": "status", "to": "done"}
        store = epic_store(self)
        leak["target"] = str(store.repo / A01)
        derived = store.derive(branch="EPIC-Alpha")
        closed = store.close(derived["set_file"], scripts_root=store.leaky_scripts([leak]))
        _first, second = self.confirmed(store, derived, closed)
        text = H.report_text(second)
        self.assertIn("closed outside its set", text)
        self.assertTrue(H.near(text, "alpha-01.md", "todo") and H.near(text, "alpha-01.md", "done"), text[:600])
        self.assertNotIn("3.5", H.completed_steps(second))
        outcomes = [str(o).lower() for o in (second.result or {}).get("step_outcomes", [])
                    if "3.5" in str(o)]
        self.assertFalse(any("closure completed" in o for o in outcomes), outcomes)
        self.assertEqual(H.calls(second, H.COMMIT), [], "a closure commit was dispatched over a leak")

    def test_finalize_report_carries_refused_and_left_open_from_the_close_reply(self):
        # covers: BO-400e-3-iv
        # angle: reachability
        """The close reply for the refusal fixture (alpha-01 refused by the real checker): the final report
        names alpha-01.md as refused and BO-9100a-1 as left open because its ticket was not closed."""
        store, derived, closed = self.alpha(alpha01="refused")
        _first, second = self.confirmed(store, derived, closed)
        text = H.report_text(second)
        self.assertTrue(H.near(text, "alpha-01.md", "refused"), text[:800])
        self.assertTrue(H.near(text, "bo-9100a-1", "left open"), text[:800])
        self.assertTrue(H.near(text, "bo-9100a-1", "not closed"), text[:800])

    def test_closure_survives_finalize_start_without_discarding_dirty_edits(self):
        # covers: BO-400e-3-v
        # angle: reachability
        """No Step 3.5 dispatch instructs `git reset --hard`, `git add tickets/`, `git add
        docs/acceptance-criteria/` or a raw git commit, and the closure commit dispatch names exactly the
        module's commit_paths. (Dirty-edit survival itself is proven on a real repo in
        test_bo_400e_3_v_closure_commit.)"""
        store, derived, closed = self.alpha(parent=False, dirty=True)
        first, second = self.confirmed(store, derived, closed)
        for prompt in H.step35_prompts(first) + H.step35_prompts(second):
            for banned in ("reset --hard", "git add tickets/", "git add docs/acceptance-criteria/"):
                self.assertNotIn(banned, prompt)
        for run in (first, second):
            for call in run.agent_calls:
                if str(call.label or "").startswith("step-3.5") and call.label != H.COMMIT:
                    self.assertNotIn("COMMIT_AGENT_MODE", H.prompt_of(call))
                    self.assertIsNone(re.search(r"git\s+(?:-C\s+\S+\s+)?commit\b", H.prompt_of(call)))
        commits = H.calls(second, H.COMMIT)
        self.assertEqual(len(commits), 1, H.labels(second))
        named = set(re.findall(r"(?:tickets|docs)/[\w./-]+", H.prompt_of(commits[0])))
        self.assertEqual(named, set(closed["commit_paths"]), named)


class TestListingAndReport(_Case):
    def test_listing_is_shown_before_any_record_is_written(self):
        # covers: BO-400e-3-vi
        # angle: criterion
        """The listing (counts header plus id, path and status per record) is in the closure gate's
        prompt, which is persisted BEFORE any close dispatch exists in the run."""
        store, derived, closed = self.alpha()
        first = H.first_run("EPIC-Alpha", str(store.repo), derive=derived, close=closed)
        _record, prompt = H.closure_pause(first)
        for line in derived["listing_text"].splitlines():
            self.assertIn(line.strip(), prompt, f"listing line missing from the gate prompt: {line!r}")
        self.assertEqual(H.calls(first, H.CLOSE), [], "a close was dispatched before the person answered")
        self.assertLess(H.labels(first).index(H.DERIVE), H.labels(first).index("pause-persist"))

    def test_final_report_repeats_the_list_with_per_record_outcome(self):
        # covers: BO-400e-3-vi
        # angle: reachability
        """The final report lists alpha-02.md closed and BO-9100a-2 closed; with the refusal fixture it
        lists alpha-01.md refused and BO-9100a-1 left open."""
        with self.subTest(case="all closed"):
            store, derived, closed = self.alpha()
            _first, second = self.confirmed(store, derived, closed)
            text = H.report_text(second)
            self.assertTrue(H.near(text, "alpha-02.md", "closed"), text[:800])
            self.assertTrue(H.near(text, "bo-9100a-2", "closed"), text[:800])
        with self.subTest(case="refusal"):
            store, derived, closed = self.alpha(alpha01="refused")
            _first, second = self.confirmed(store, derived, closed)
            text = H.report_text(second)
            self.assertTrue(H.near(text, "alpha-01.md", "refused"), text[:800])
            self.assertTrue(H.near(text, "bo-9100a-1", "left open"), text[:800])

    def test_record_closed_outside_the_shown_list_is_reported_and_step_not_completed(self):
        # covers: BO-400e-3-vi
        # angle: failure
        """The real close reply (with an injected leak) shows alpha-01.md changed: the report marks it
        closed outside the shown list and Step 3.5 is not in completed_steps. NEGATIVE CONTROL: Step 6b's
        scope-probe reply naming an extra done ticket does not add it to the report's closed list."""
        store = epic_store(self)
        leak = {"after": "ticket", "target": str(store.repo / A01), "mode": "status", "key": "status",
                "to": "done"}
        derived = store.derive(branch="EPIC-Alpha")
        closed = store.close(derived["set_file"], scripts_root=store.leaky_scripts([leak]))
        _first, second = self.confirmed(store, derived, closed)
        text = H.report_text(second)
        self.assertTrue(H.near(text, "alpha-01.md", "outside the shown list"), text[:800])
        self.assertNotIn("3.5", H.completed_steps(second))

        clean_store, clean_derived, clean_closed = self.alpha()
        extra = A04
        probe = {"scope": "epic", "tickets_in_scope": [extra], "tickets_done": [extra],
                 "tickets_not_done": [], "skipped": False}
        _f, run = H.confirmed_run("EPIC-Alpha", str(clean_store.repo), derive=clean_derived,
                                  close=clean_closed, extra={"step-6-scope-detect": probe})
        reported = (run.result or {}).get("tickets_closed") or []
        self.assertTrue(any(A02 in str(t) for t in reported), f"control: the real closure is not reported {reported}")
        self.assertFalse(any(extra in str(t) for t in reported), f"step 6b added a ticket to the list: {reported}")


def _runner_reply(closed: dict, **overrides) -> dict:
    """The command-step-runner's result shape {command, workspace, exit_status, stdout, stderr} around the
    REAL close output (stdout is the module's printed JSON, as the runner relays it verbatim)."""
    reply = {"command": "finalize_closable_set.py close", "workspace": "", "exit_status": 0,
             "stdout": json.dumps(closed), "stderr": ""}
    reply.update(overrides)
    return reply


class TestCloserRunnerReplyIsChecked(_Case):
    def _resumed(self, close_reply):
        store, derived, closed = self.alpha()
        first = H.first_run("EPIC-Alpha", str(store.repo), derive=derived, close=closed)
        record, _prompt = H.closure_pause(first)
        run = H.resume_run("EPIC-Alpha", str(store.repo), record, "confirm", derive=derived,
                           close=close_reply(closed), commit=H.committed_answer())
        return run

    def assert_halted_before_merge(self, run, label):
        self.assertEqual(len(H.calls(run, H.CLOSE)), 1, f"{label}: control, the close was dispatched")
        self.assertEqual(H.calls(run, H.COMMIT), [], f"{label}: a closure commit followed an unusable close reply")
        self.assertEqual(H.calls(run, H.MERGE), [], f"{label}: the merge was dispatched")
        self.assertEqual((run.result or {}).get("status"), "halted", f"{label}: {run.result}")
        self.assertNotIn("3.5", H.completed_steps(run), label)

    def test_closer_exit_status_nonzero_or_non_string_stdout_halts_before_merge(self):
        # covers: BO-400e-3-iv
        # angle: failure
        """AC BO-400e-3-iv (review finding M-1): the closer runner's reply carries an exit_status and a
        string stdout. A non-zero exit_status (even with a well-formed stdout), or a stdout that is not a
        string, is a failed close: Step 3.5 halts before the merge, dispatching no closure commit and no
        merge. CONTROL: the same real close output with exit_status 0 and string stdout proceeds.
        WRONG VERSIONS: the exit status is never read; a non-string stdout is read as the body itself."""
        with self.subTest(case="control: exit 0, string stdout"):
            run = self._resumed(lambda closed: _runner_reply(closed))
            self.assertEqual(len(H.calls(run, H.COMMIT)), 1, H.labels(run))
            self.assertGreaterEqual(len(H.calls(run, H.MERGE)), 1, H.labels(run))
        with self.subTest(case="exit_status 1 with well-formed stdout"):
            run = self._resumed(lambda closed: _runner_reply(closed, exit_status=1, stderr="boom"))
            self.assert_halted_before_merge(run, "exit_status 1")
        with self.subTest(case="exit_status 0, stdout is an object"):
            run = self._resumed(lambda closed: _runner_reply(closed, stdout=closed))
            self.assert_halted_before_merge(run, "object stdout")
        with self.subTest(case="exit_status 0, stdout null but the close output spread beside it"):
            run = self._resumed(lambda closed: {**closed, **_runner_reply(closed, stdout=None)})
            self.assert_halted_before_merge(run, "null stdout")


class TestClosureProbeIsRanged(_Case):
    """The 'closure already committed' probe must look only at the branch's OWN commits."""

    def _probe_line(self, run) -> str:
        probes = H.calls(run, PROBE)
        self.assertEqual(len(probes), 1, H.labels(run))
        for line in H.prompt_of(probes[0]).splitlines():
            if " log " in line and "--grep" in line:
                text = line.strip()
                return text[4:].strip() if text.startswith("Run:") else text
        self.fail(f"no git log --grep command in the probe prompt: {H.prompt_of(probes[0])!r}")

    def _probe_output(self, store, run) -> str:
        proc = subprocess.run(self._probe_line(run), shell=True, cwd=store.scratch, env=store.env,
                              capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout.strip()

    def _first(self, store):
        derived = store.derive(branch="EPIC-Alpha")
        closed = store.close(derived["set_file"])
        return H.first_run("EPIC-Alpha", str(store.repo), derive=derived, close=closed)

    def test_closure_message_only_in_base_history_does_not_skip_step_35(self):
        # covers: BO-400e-3-ii
        # angle: discrimination
        """AC BO-400e-3-ii (review finding H-2): origin/main already holds a commit whose message is the
        closure message and the branch has merged main in, so that commit is in HEAD's history, but the
        branch has none of its own. The probe command the workflow dispatches, run
        for real against that repository, must find nothing (so Step 3.5 derives), and must find the
        closure commit once the branch itself carries one (so Step 3.5 skips). WRONG VERSION: the unranged
        `git log --grep ... -1`, which sees main's history and skips Step 3.5 on every branch."""
        main_only = epic_store(self)
        main_only.advance_main_elsewhere({"docs/other.md": "other\n"}, CLOSURE_MESSAGE)
        main_only.merge_origin_main()  # Step 2 merged main in: its closure commit is now in HEAD's history
        run = self._first(main_only)
        self.assertEqual(len(H.calls(run, H.DERIVE)), 1, H.labels(run))
        self.assertEqual(self._probe_output(main_only, run), "",
                         "the probe saw a closure commit that exists only in the base history")
        own = epic_store(self)
        own.advance_main_elsewhere({"docs/other.md": "other\n"}, CLOSURE_MESSAGE)
        own.merge_origin_main()
        own.write("docs/own-closure.md", "closed on the branch\n")
        own.commit(CLOSURE_MESSAGE)
        run = self._first(own)
        self.assertIn(CLOSURE_MESSAGE, self._probe_output(own, run),
                      "control: the branch's own closure commit was not found by the probe")

    def test_a_found_reply_skips_only_the_probed_branch_commits(self):
        # covers: BO-400e-3-ii
        # angle: criterion
        """Consumption of the probe reply: {already_committed: true} skips derivation, {false} does not.
        (Pins that the reply is read; the range itself is proven by the real-repository test above.)"""
        store = epic_store(self)
        derived = store.derive(branch="EPIC-Alpha")
        closed = store.close(derived["set_file"])
        skipped = H.run_finalize("EPIC-Alpha", str(store.repo), derive=derived, close=closed,
                                 extra={PROBE: {"already_committed": True}})
        self.assertEqual(H.calls(skipped, H.DERIVE), [], H.labels(skipped))
        derived_run = H.run_finalize("EPIC-Alpha", str(store.repo), derive=derived, close=closed,
                                     extra={PROBE: {"already_committed": False}})
        self.assertEqual(len(H.calls(derived_run, H.DERIVE)), 1, H.labels(derived_run))


class TestMergeStillInProgressHalts(_Case):
    def _run(self, reply):
        store, derived, closed = self.alpha()
        return H.first_run("EPIC-Alpha", str(store.repo), derive=derived, close=closed,
                           extra={RESET_MERGE: reply})

    def test_merge_head_surviving_the_abort_halts_before_close_and_merge(self):
        # covers: BO-400e-3-v
        # angle: failure
        """AC BO-400e-3-v (review finding M-4): sub-step A reports that the abort did not clear the
        merge (status still_merging). Step 3.5 halts there: no derive-driven
        close, no closure commit, no merge, no closure-gate pause. CONTROLS: replies 'aborted' and
        'no_merge' carry on to the closure gate. WRONG VERSION: the sub-step reply is never read.
        CONTRACT (as the sub-step prompt now states it): the step-3.5-reset-merge reply status is
        aborted | no_merge | still_merging, still_merging when MERGE_HEAD survives the abort."""
        for reply in ({"status": "still_merging", "merge_head_present": True},):
            with self.subTest(reply=reply["status"]):
                run = self._run(reply)
                self.assertEqual(H.calls(run, H.CLOSE), [], H.labels(run))
                self.assertEqual(H.calls(run, H.COMMIT), [], H.labels(run))
                self.assertEqual(H.calls(run, H.MERGE), [], "the merge was dispatched over a live merge")
                self.assertEqual(H.calls(run, "pause-persist"), [], "the closure gate was reached")
                self.assertEqual((run.result or {}).get("status"), "halted", run.result)
                self.assertEqual((run.result or {}).get("halted_at_step"), "3.5", run.result)
        for status in ("aborted", "no_merge"):
            with self.subTest(control=status):
                run = self._run({"status": status})
                self.assertEqual(len(H.calls(run, "pause-persist")), 1, H.labels(run))

    def test_unreadable_or_unknown_reset_merge_reply_fails_closed(self):
        # covers: BO-400e-3-v
        # angle: failure
        """AC BO-400e-3-v: sub-step A fails closed. Only status aborted | no_merge continue; an
        unknown status, an empty object, a status-less object and unparseable text each halt at 3.5
        with no close, commit, merge or gate pause. (The control rows are in the test above.)
        WRONG VERSION: only the literal still_merging halts, so a garbled answer reads as clean."""
        for name, reply in (("unknown status", {"status": "ok"}), ("empty object", {}),
                            ("no status key", {"merge_head_present": False}),
                            ("unparseable text", "the agent rambled instead of answering")):
            with self.subTest(reply=name):
                run = self._run(reply)
                self.assertEqual(H.calls(run, H.CLOSE), [], H.labels(run))
                self.assertEqual(H.calls(run, H.COMMIT), [], H.labels(run))
                self.assertEqual(H.calls(run, H.MERGE), [], "the merge was dispatched")
                self.assertEqual(H.calls(run, "pause-persist"), [], "the closure gate was reached")
                self.assertEqual((run.result or {}).get("status"), "halted", run.result)
                self.assertEqual((run.result or {}).get("halted_at_step"), "3.5", run.result)


if __name__ == "__main__":
    unittest.main()
