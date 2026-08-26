"""Behavioral tests for post-dispatch sign-off verification (BUG-23).

Covers:
  BO-2900f-1-i   — a gate that reports success but leaves no entry in the work
                   item's record is adjudicated FAILED, not passed.
  BO-2900f-1-ii  — a gate whose entry is already present is never recorded twice.
  BO-2900f-1-iii — the record check runs after EVERY dispatched gate, so
                   verification cannot hold on one work item and lapse on the next.

Every test EXECUTES a real driver through harness_build_ticket_guard.mjs. The
defect is a true statement (the gate ran and succeeded) paired with a missing
artifact, so nothing about the gate's own return value distinguishes the broken
system from the fixed one — only observing the record after the dispatch can.

Observed (run wf_cc2b46d9-f6f):
  ticket 01 — recorded: test-writer, python-coder, commit;
              MISSING despite returning ok: test-runner, pr-reviewer
  ticket 03 — recorded: test-writer, python-coder, pr-reviewer, commit,
              commit (DUPLICATE); MISSING: test-runner
  ticket 09 — recorded: test-writer, python-coder, test-runner, commit;
              MISSING: pr-reviewer
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _driver_harness as H  # noqa: E402

TWO_GATES = ["test-runner", "pr-reviewer"]

#: Tokens any of which shows the report attributes the failure to the missing
#: record entry rather than to some unrelated cause.
_UNRECORDED_TOKENS = (
    "sign-off",
    "signoff",
    "signed off",
    "no entry",
    "did not record",
    "not recorded",
    "unrecorded",
    "left no",
    "no record",
    "record entry",
)


def _serialized(result) -> str:
    return json.dumps(result, sort_keys=True) if result is not None else ""


def _completed_gates(result) -> list:
    if not isinstance(result, dict):
        return []
    gates = list(result.get("completed_phases") or [])
    for batch in result.get("completed_batches") or []:
        for entry in batch.get("tickets") or []:
            if isinstance(entry, dict):
                gates.extend(entry.get("completed_phases") or [])
    return gates


def _skipped_gates(result) -> list:
    if not isinstance(result, dict):
        return []
    out = []
    for entry in result.get("skipped_phases") or []:
        out.append(entry.get("agent") if isinstance(entry, dict) else entry)
    return out


def gate_outcome_bucket(result, gate: str) -> str:
    """Classify how the run's report presents one gate.

    Returns one of: ``completed``, ``skipped``, ``failed``, ``absent``.
    Deliberately tolerant about field names — the AC constrains the outcome a
    reader can see, not the key it is stored under.
    """
    if gate in _completed_gates(result):
        return "completed"
    if gate in _skipped_gates(result):
        return "skipped"
    text = _serialized(result)
    if gate not in text:
        return "absent"
    return "failed"


def failure_names_the_missing_entry(result, gate: str) -> bool:
    """The failure must say the gate reported success while leaving no entry."""
    text = _serialized(result).lower()
    return gate in _serialized(result) and any(t in text for t in _UNRECORDED_TOKENS)


class _VerificationCase(unittest.TestCase):
    def setUp(self):
        if not H.node_available():
            self.skipTest("node is not available on PATH")
        self._tmpdirs = []

    def tearDown(self):
        for path in self._tmpdirs:
            shutil.rmtree(path, ignore_errors=True)

    def _worktree(self) -> str:
        path = tempfile.mkdtemp(prefix="bo2900_")
        self._tmpdirs.append(path)
        return path

    def drive_both_twins(self, phases, results, **kwargs):
        """Yield (driver_name, observation, ticket_path) for each twin."""
        seeded = kwargs.pop("seeded_signoffs", ())
        classify = kwargs.pop("classify", None)
        delete_after = kwargs.pop("delete_record_after_phase", None)
        has_test_requirements = kwargs.pop("has_test_requirements", True)

        for driver_name, script in H.TWIN_DRIVERS.items():
            worktree = self._worktree()
            ticket_path = H.write_ticket_record(
                worktree,
                "01_gate_case.md",
                phases,
                title="Gate case ticket",
                seeded_signoffs=seeded,
            )
            cfg = {
                "title": "Gate case ticket",
                "phases": phases,
                "has_test_requirements": has_test_requirements,
                "results": results,
            }
            if classify:
                cfg["classify"] = classify
            if delete_after:
                cfg["delete_record_after_phase"] = delete_after
            scenario = H.single_ticket_scenario(worktree, ticket_path, cfg)
            yield driver_name, H.run_driver(script, scenario), ticket_path


# ---------------------------------------------------------------------------
# BO-2900f-1-i — a silent gate is a failed gate
# ---------------------------------------------------------------------------


class TestGateWithoutRecordEntryIsFailed(_VerificationCase):
    """BO-2900f-1-i: a gate's word for its own success is never sufficient."""

    def test_gate_reporting_success_with_no_record_entry_is_adjudicated_failed(self):
        # covers: BO-2900f-1-i
        """Two gates run and both report success; the first records its entry,
        the second does not. The second must be adjudicated FAILED, and the
        failure must say it reported success while leaving no entry."""
        results = H.phase_results({"test-runner": True, "pr-reviewer": False})

        for driver, observation, ticket_path in self.drive_both_twins(
            TWO_GATES, results
        ):
            with self.subTest(driver=driver):
                record = H.read_record(ticket_path)
                self.assertEqual(
                    record["signed_off_agents"],
                    ["test-runner"],
                    "harness precondition: only the first gate may have recorded",
                )

                result = observation["result"]
                self.assertEqual(
                    gate_outcome_bucket(result, "pr-reviewer"),
                    "failed",
                    "pr-reviewer reported success and left no entry in the "
                    "record, so it must be adjudicated failed. The run presented "
                    f"it as: {gate_outcome_bucket(result, 'pr-reviewer')!r}. "
                    f"Report: {_serialized(result)}",
                )
                self.assertTrue(
                    failure_names_the_missing_entry(result, "pr-reviewer"),
                    "the failure must name the gate AND state that it reported "
                    "success while leaving no entry, so a reader can tell it "
                    "apart from an ordinary blocker. Report: "
                    f"{_serialized(result)}",
                )
                self.assertEqual(
                    gate_outcome_bucket(result, "test-runner"),
                    "completed",
                    "the gate whose entry IS present must be unaffected",
                )

    def test_gate_with_a_present_record_entry_still_passes(self):
        # covers: BO-2900f-1-i
        """CONTROL CASE: the same driver, both gates reporting success AND
        recording, must pass both — so the failure above is attributable to the
        missing entry and not to a driver that now fails everything."""
        results = H.phase_results({g: True for g in TWO_GATES})

        for driver, observation, ticket_path in self.drive_both_twins(
            TWO_GATES, results
        ):
            with self.subTest(driver=driver):
                result = observation["result"]
                for gate in TWO_GATES:
                    self.assertEqual(
                        gate_outcome_bucket(result, gate),
                        "completed",
                        f"{driver}: {gate} reported success and its entry is "
                        f"present in the record "
                        f"({H.read_record(ticket_path)['signed_off_agents']}), so "
                        f"it must pass. Report: {_serialized(result)}",
                    )

    def test_the_verdict_carried_forward_is_the_one_derived_from_the_record(self):
        # covers: BO-2900f-1-i
        """The read-back must be the DECIDING input, not a logged warning.

        The cheapest wrong fix is to read the record, emit a warning, and still
        trust the agent's own report. That implementation leaves the observed
        defect fully intact while appearing fixed, so this test asserts the
        downstream effect: the drive must not proceed as though the silent gate
        completed.
        """
        results = H.phase_results({"test-runner": True, "pr-reviewer": False})

        for driver, observation, ticket_path in self.drive_both_twins(
            TWO_GATES, results
        ):
            with self.subTest(driver=driver):
                result = observation["result"]

                self.assertGreater(
                    len(observation["readbacks"]),
                    0,
                    f"{driver} never read the record back, so no verdict could "
                    "possibly have been derived from it. Accepted read-back "
                    f"labels: {H.ACCEPTED_READBACK_LABELS}",
                )
                self.assertNotIn(
                    "pr-reviewer",
                    _completed_gates(result),
                    f"{driver} carried pr-reviewer forward as a completed gate "
                    "even though its entry is absent from the record. The verdict "
                    "the drive carries must be the one derived from the record — "
                    "a warning that is logged and then ignored is not a verdict. "
                    f"Report: {_serialized(result)}",
                )
                self.assertEqual(
                    H.writes_for(observation, ticket_path),
                    [],
                    f"{driver} treated the work item as complete despite an "
                    "unconfirmed gate.",
                )

    def test_unreadable_record_adjudicates_the_gate_failed(self):
        # covers: BO-2900f-1-i
        """Fail closed: if the record cannot be read back, the gate is
        adjudicated failed, never credited from its own success report."""
        results = H.phase_results({g: True for g in TWO_GATES})

        for driver, observation, ticket_path in self.drive_both_twins(
            TWO_GATES, results, delete_record_after_phase="test-runner"
        ):
            with self.subTest(driver=driver):
                self.assertFalse(
                    os.path.exists(ticket_path),
                    "harness precondition: the record must be unreadable at the "
                    "moment of the read-back",
                )
                result = observation["result"]
                self.assertNotEqual(
                    gate_outcome_bucket(result, "pr-reviewer"),
                    "completed",
                    f"{driver} credited pr-reviewer from its own success report "
                    "while the work item's record was unreadable. Absent evidence "
                    "must never resolve to success. Report: "
                    f"{_serialized(result)}",
                )

    def test_verification_is_not_specific_to_any_named_gate(self):
        # covers: BO-2900f-1-i
        """Every gate in the canonical phase set, reporting success and leaving
        no entry, must be adjudicated failed.

        The observed run showed the defect on test-runner for one ticket and on
        pr-reviewer for another. A verification attached to named gates would
        satisfy the tests above and re-create the defect for the next gate
        anyone adds, so the whole real phase list is driven here — parameterized
        from the driver's own phaseOrder array, not from a hand-picked pair.
        """
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                gates = H.dispatchable_gates(script)
                self.assertGreater(
                    len(gates), 5, "harness precondition: phaseOrder must parse"
                )
                results = H.phase_results({g: False for g in gates})

                worktree = self._worktree()
                ticket_path = H.write_ticket_record(
                    worktree, "01_all_gates.md", gates, title="All gates ticket"
                )
                observation = H.run_driver(
                    script,
                    H.single_ticket_scenario(
                        worktree,
                        ticket_path,
                        {
                            "title": "All gates ticket",
                            "phases": gates,
                            "has_test_requirements": True,
                            "results": results,
                        },
                    ),
                )
                result = observation["result"]
                credited = [
                    g
                    for g in observation["dispatched"]
                    if gate_outcome_bucket(result, g) == "completed"
                ]
                self.assertEqual(
                    credited,
                    [],
                    f"{driver} credited {len(credited)} gate(s) that reported "
                    f"success while leaving no entry in the record: {credited}. "
                    "The verification belongs to the single generic post-dispatch "
                    "path every gate returns through, so no gate may be exempt.",
                )


# ---------------------------------------------------------------------------
# BO-2900f-1-ii — adjudicate a duplicated gate from its LATEST entry, and
# surface the duplication rather than erasing it
#
# AMENDED 2026-08-18. The original criteria required the on-disk record to end
# with exactly one entry per gate. That is unsatisfiable from the driver — its
# whole mutation surface over the record is append, a status-line rewrite and
# whole-record deletion, none of which removes a single heading — and it would
# be wrong even if it were possible, because the heading belongs to another
# agent's audit trail. Production evidence: ticket 03 of
# EPIC-DeploymentCompleteness carries two `commit (status: ok)` entries, both
# written by the commit agent. The cardinality-on-disk requirement moved to the
# write-side AC BO-2900f-2-ii (batch 2, deliberately untested here).
#
# Retired from this file with the amendment:
#   test_gate_reentered_after_a_retry_leaves_exactly_one_entry  -> BO-2900f-2-ii
#   test_entry_count_equals_the_number_of_gates_that_reached_an_outcome
#                                                               -> BO-2900f-2
#   test_first_pass_still_writes_exactly_one_entry (its control) -> BO-2900f-2-ii
# What survives is the verdict: given a record it did not write, the driver
# must produce the right answer from it, leave it untouched, and say when it
# saw a duplicate.
# ---------------------------------------------------------------------------

#: A record staged with two entries for one gate, in each order. Both entries
#: carry the SAME minute-resolution timestamp (write_ticket_record stamps every
#: seeded entry 09:00), so the two orderings are distinguishable ONLY by append
#: order. A timestamp-comparing adjudicator is non-deterministic across this
#: pair — which is the point: recency must come from the record's own ordering.
PASS_THEN_FAIL = (("test-runner", "ok"), ("commit", "ok"), ("commit", "blocker"))
FAIL_THEN_PASS = (("test-runner", "ok"), ("commit", "blocker"), ("commit", "ok"))


def _read_bytes(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _comments_section(text: str) -> str:
    marker = "## Comments"
    index = text.find(marker)
    return text[index:] if index != -1 else text


class TestDuplicatedGateAdjudication(_VerificationCase):
    """BO-2900f-1-ii: a gate reached twice still yields one correct verdict, and
    the audit trail that produced that verdict survives intact."""

    STAGED_GATES = ["test-runner", "commit"]

    def drive_staged_record(self, seeded, gates=None):
        """Drive both twins over a record STAGED BEFORE THE RUN.

        Every gate is dispatched with ``record: false``, so no phase stub
        appends anything: the record the driver adjudicates is exactly the one
        staged here, and it is a record the driver did not write — the AC's
        framing. That also makes a before/after byte comparison meaningful,
        because the only possible writer during the run is the driver itself.

        Yields ``(driver, observation, ticket_path, before_text, after_text)``.
        """
        phases = list(gates or self.STAGED_GATES)
        for driver, script in H.TWIN_DRIVERS.items():
            worktree = self._worktree()
            ticket_path = H.write_ticket_record(
                worktree,
                "01_duplicated_gate.md",
                phases,
                title="Duplicated gate ticket",
                seeded_signoffs=seeded,
            )
            before = _read_bytes(ticket_path)
            scenario = H.single_ticket_scenario(
                worktree,
                ticket_path,
                {
                    "title": "Duplicated gate ticket",
                    "phases": phases,
                    "has_test_requirements": True,
                    "results": H.phase_results({g: False for g in phases}),
                },
            )
            observation = H.run_driver(script, scenario)
            yield driver, observation, ticket_path, before, _read_bytes(ticket_path)

    @staticmethod
    def duplicate_report(result):
        """The run's duplicate report, as {gate: entry_count}."""
        if not isinstance(result, dict):
            return {}
        entries = result.get("duplicate_signoff_entries") or []
        report = {}
        for entry in entries:
            if isinstance(entry, dict) and entry.get("agent"):
                report[entry["agent"]] = entry.get("entries")
        return report

    def test_verdict_for_a_duplicated_gate_is_taken_from_the_latest_entry(self):
        # covers: BO-2900f-1-ii
        """The verdict for a duplicated gate comes from its LATEST entry and
        from no other entry.

        Asserted on the verdict, never on how many entries the file ends with —
        the file's shape is the write side's problem (BO-2900f-2-ii).

        The two orderings are byte-identical apart from the order of the two
        commit entries, and both entries carry the same minute stamp. So the
        only input that can produce different verdicts is append order: an
        adjudicator that keys on the first entry, on the most favourable
        outcome, or on a timestamp comparison cannot produce both answers.
        """
        for seeded, expected, order in (
            (FAIL_THEN_PASS, "completed", "fail-then-pass"),
            (PASS_THEN_FAIL, "failed", "pass-then-fail"),
        ):
            for driver, observation, ticket_path, _before, after in (
                self.drive_staged_record(seeded)
            ):
                with self.subTest(driver=driver, order=order):
                    commit_entries = [
                        s
                        for s in H.read_record(ticket_path)["signoffs"]
                        if s["agent"] == "commit"
                    ]
                    self.assertEqual(
                        [s["status"] for s in commit_entries],
                        [status for agent, status in seeded if agent == "commit"],
                        "harness precondition: the record must still carry both "
                        "staged commit entries, in the staged order, at the "
                        f"moment the verdict is read. Record:\n{after}",
                    )

                    self.assertEqual(
                        gate_outcome_bucket(observation["result"], "commit"),
                        expected,
                        f"{driver} ({order}): the latest commit entry reads "
                        f"{commit_entries[-1]['status']!r}, so the gate must be "
                        f"adjudicated {expected!r}. The run reported "
                        f"{gate_outcome_bucket(observation['result'], 'commit')!r}. "
                        f"Report: {_serialized(observation['result'])}",
                    )

    def test_a_stale_pass_does_not_outlive_a_later_failure(self):
        # covers: BO-2900f-1-ii
        """Entries in pass-then-fail order: the gate is adjudicated FAILED.

        Catches an implementation that keeps the first entry, or the most
        favourable one. Paired with its opposite below — either direction alone
        is passed by an adjudicator that selects on outcome instead of recency.
        """
        for driver, observation, ticket_path, _before, after in (
            self.drive_staged_record(PASS_THEN_FAIL)
        ):
            with self.subTest(driver=driver):
                result = observation["result"]
                self.assertNotIn(
                    "commit",
                    _completed_gates(result),
                    f"{driver}: the earlier commit entry says the gate passed and "
                    "the later one says it failed. A stale pass must never "
                    f"outlive a later failure. Report: {_serialized(result)}\n"
                    f"Record:\n{after}",
                )
                self.assertFalse(
                    (result or {}).get("ticket_completed"),
                    f"{driver}: the ticket must not be recorded complete while "
                    "the commit gate's latest entry is a failure.",
                )
                self.assertIn(
                    "commit",
                    _serialized(result),
                    f"{driver}: the failing gate must be named in the report.",
                )

    def test_a_retry_success_is_not_discarded_by_the_earlier_failure(self):
        # covers: BO-2900f-1-ii
        """The opposite order — fail-then-pass — is adjudicated PASSED.

        A retry's success is never discarded in favour of the failure that
        preceded it. This is the direction an implementation that keeps the
        FIRST entry gets wrong.
        """
        for driver, observation, ticket_path, _before, after in (
            self.drive_staged_record(FAIL_THEN_PASS)
        ):
            with self.subTest(driver=driver):
                result = observation["result"]
                self.assertIn(
                    "commit",
                    _completed_gates(result),
                    f"{driver}: the later commit entry says the gate passed, so "
                    "the retry's success must decide. Reporting the earlier "
                    "failure discards a result that actually happened. Report: "
                    f"{_serialized(result)}\nRecord:\n{after}",
                )
                self.assertNotIn(
                    "commit",
                    (result or {}).get("unverified_phases") or [],
                    f"{driver}: commit must not be carried as unverified when its "
                    "latest entry passes.",
                )

    def test_duplicate_entries_are_counted_and_reported_with_the_gate_name(self):
        # covers: BO-2900f-1-ii
        """The run's output names the duplicated gate and its entry count.

        A duplicate that only affects which entry was read, and is never named,
        leaves the write-side defect invisible for as long as the adjudication
        keeps compensating for it. Both orderings are asserted, because the
        report must survive the case where the adjudication resolves cleanly —
        that is precisely the case in which the duplicate would otherwise be
        absorbed and never seen.
        """
        for seeded, order in (
            (PASS_THEN_FAIL, "pass-then-fail"),
            (FAIL_THEN_PASS, "fail-then-pass"),
        ):
            for driver, observation, ticket_path, _before, after in (
                self.drive_staged_record(seeded)
            ):
                with self.subTest(driver=driver, order=order):
                    report = self.duplicate_report(observation["result"])
                    self.assertIn(
                        "commit",
                        report,
                        f"{driver} ({order}): the record carries two entries for "
                        "the commit gate, but the run's output does not name it "
                        "as duplicated. Report the count alongside the verdict "
                        "(the implementation's field is "
                        "duplicate_signoff_entries) so the write-side failure is "
                        "visible to the operator rather than silently tolerated. "
                        f"Report: {_serialized(observation['result'])}\n"
                        f"Record:\n{after}",
                    )
                    self.assertEqual(
                        report.get("commit"),
                        2,
                        f"{driver} ({order}): the duplicate report must carry the "
                        f"entry count for the gate. Got {report!r}.",
                    )

    def test_the_drive_leaves_every_existing_entry_untouched(self):
        # covers: BO-2900f-1-ii
        """The record is captured before and after the adjudication and must be
        unchanged: no entry deleted, rewritten, reordered or merged.

        THIS IS THE CLAUSE THAT DISTINGUISHES THIS AC FROM THE WRITE-SIDE HALF,
        and the guard against the retired exactly-one-entry-on-disk requirement
        creeping back in as an implementation detail. A driver that quietly
        deletes the older heading to make its own adjudication tidy would pass
        every other descriptor here — and would be one agent rewriting another
        agent's audit trail to cover a write-side defect.

        Both orderings are covered. In the pass-then-fail case the ticket does
        not complete, so the file must be byte-for-byte identical. In the
        fail-then-pass case the ticket completes and the driver rewrites the
        frontmatter status line — an allowed channel — so the assertion is
        scoped to the ## Comments section, which must still be byte-for-byte
        identical.
        """
        # Pass-then-fail: no completion write, so NOTHING may change.
        for driver, observation, ticket_path, before, after in (
            self.drive_staged_record(PASS_THEN_FAIL)
        ):
            with self.subTest(driver=driver, order="pass-then-fail"):
                self.assertEqual(
                    after,
                    before,
                    f"{driver}: the drive modified a record it did not write. "
                    "It adjudicates; it never edits the record to make the "
                    "adjudication come out tidy.\n"
                    f"--- before ---\n{before}\n--- after ---\n{after}",
                )

        # Fail-then-pass: the ticket completes, so only the frontmatter status
        # line may change. Every existing entry must survive verbatim.
        for driver, observation, ticket_path, before, after in (
            self.drive_staged_record(FAIL_THEN_PASS)
        ):
            with self.subTest(driver=driver, order="fail-then-pass"):
                self.assertEqual(
                    _comments_section(after),
                    _comments_section(before),
                    f"{driver}: the ## Comments section changed across the "
                    "adjudication. The completion write may rewrite the "
                    "frontmatter status line and nothing else — an entry another "
                    "agent wrote may not be deleted, rewritten, reordered or "
                    "collapsed.\n"
                    f"--- before ---\n{_comments_section(before)}\n"
                    f"--- after ---\n{_comments_section(after)}",
                )
                self.assertEqual(
                    [
                        (s["agent"], s["status"])
                        for s in H.read_record(ticket_path)["signoffs"]
                    ],
                    list(FAIL_THEN_PASS),
                    f"{driver}: the ordered entry list must be exactly as staged.",
                )

    def test_a_single_entry_gate_adjudicates_normally_and_is_not_reported_as_duplicated(
        self,
    ):
        # covers: BO-2900f-1-ii
        """CONTROL CASE over the canonical phase set with no duplicates.

        Every gate adjudicates from its one entry and the duplicate report is
        empty. Without this the AC is satisfiable by an implementation that
        reports every gate as duplicated, which is the same as reporting none.
        """
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                gates = H.dispatchable_gates(script)
                seeded = tuple((gate, "ok") for gate in gates)

                worktree = self._worktree()
                ticket_path = H.write_ticket_record(
                    worktree,
                    "01_single_entry.md",
                    gates,
                    title="Single entry ticket",
                    seeded_signoffs=seeded,
                )
                observation = H.run_driver(
                    script,
                    H.single_ticket_scenario(
                        worktree,
                        ticket_path,
                        {
                            "title": "Single entry ticket",
                            "phases": gates,
                            "has_test_requirements": True,
                            "results": H.phase_results({g: False for g in gates}),
                        },
                    ),
                )
                result = observation["result"]

                self.assertEqual(
                    self.duplicate_report(result),
                    {},
                    f"{driver}: every gate carries exactly one entry, so no gate "
                    "may appear in the duplicate report. Reporting them all is "
                    "indistinguishable from reporting none. Report: "
                    f"{_serialized(result)}",
                )
                credited = _completed_gates(result)
                self.assertEqual(
                    sorted(credited),
                    sorted(observation["dispatched"]),
                    f"{driver}: each gate must be adjudicated from its single "
                    f"entry. Credited {sorted(credited)} of dispatched "
                    f"{sorted(observation['dispatched'])}. Report: "
                    f"{_serialized(result)}",
                )


# ---------------------------------------------------------------------------
# BO-2900f-1-iii — uniformity: the check belongs to the dispatch path
# ---------------------------------------------------------------------------


class TestVerificationIsUniformAcrossTheDrive(_VerificationCase):
    """BO-2900f-1-iii: the guarantee is a property of the DRIVE, not of a lucky
    work item.

    The multi-work-item descriptors run against build-feature.js, the only twin
    that carries several work items through one dispatch loop; the
    generic-point descriptors run against both twins, because the verification
    must be the same single post-dispatch point in each.
    """

    def _epic_run(self, ticket_specs):
        """Drive N work items through build-feature.js in one epic run."""
        worktree = self._worktree()
        epic_subdir = os.path.join("tickets", "00_inbox", "epics", "EPIC-Uniformity")
        epic_path = os.path.join(worktree, epic_subdir)
        os.makedirs(epic_path, exist_ok=True)

        tickets = {}
        paths = []
        for index, (phases, results) in enumerate(ticket_specs, start=1):
            path = H.write_ticket_record(
                worktree,
                f"0{index}_item.md",
                phases,
                title=f"Work item {index}",
                subdir=epic_subdir,
            )
            paths.append(path)
            tickets[path] = {
                "title": f"Work item {index}",
                "phases": phases,
                "has_test_requirements": True,
                "results": results,
            }
        present = [{"path": p, "status": "todo"} for p in paths]
        scenario = H.epic_scenario(
            worktree,
            epic_path,
            tickets,
            [{"present": present}, {"present": present}],
        )
        return H.run_driver(H.BUILD_FEATURE_JS, scenario), paths

    def test_three_work_items_each_missing_a_different_gate_entry_all_report_failed(
        self,
    ):
        # covers: BO-2900f-1-iii
        """One drive, three work items, a DIFFERENT gate silently failing to
        record on each. All three must report that gate as failed.

        This is the observed shape: ticket 01 lost test-runner, ticket 03 lost
        test-runner but recorded pr-reviewer, ticket 09 recorded test-runner but
        lost pr-reviewer. No gate is reliably broken and no gate is reliably
        sound, so uniformity can only be falsified across several items at once.
        """
        gates = ["test-runner", "pr-reviewer", "commit"]
        silent_per_item = ["test-runner", "pr-reviewer", "commit"]
        specs = [
            (gates, H.phase_results({g: (g != silent) for g in gates}))
            for silent in silent_per_item
        ]

        observation, paths = self._epic_run(specs)
        result = observation["result"]

        for path, silent in zip(paths, silent_per_item, strict=True):
            with self.subTest(work_item=os.path.basename(path), silent_gate=silent):
                record = H.read_record(path)
                self.assertNotIn(
                    silent,
                    record["signed_off_agents"],
                    "harness precondition: the silent gate must have left no entry",
                )
                self.assertNotIn(
                    path,
                    [
                        t
                        for batch in (result or {}).get("completed_batches") or []
                        for t in batch.get("tickets") or []
                    ],
                    f"work item {os.path.basename(path)} was reported as completed "
                    f"although its {silent} gate ran and left no entry. All three "
                    "items must report that gate as failed, whichever gate and "
                    f"whichever item it happened to be. Report: "
                    f"{_serialized(result)}",
                )
                self.assertIn(
                    silent,
                    _serialized(result),
                    f"the report must name {silent} for work item "
                    f"{os.path.basename(path)} so a reader can tell, from that "
                    "item alone, that the gate ran and did not record.",
                )

    def test_no_work_item_finishes_carrying_an_unconfirmed_success(self):
        # covers: BO-2900f-1-iii
        """Across the same multi-item run, EVERY gate the run reached must have
        had its outcome confirmed against the work item's record."""
        gates = ["test-runner", "pr-reviewer", "commit"]
        specs = [
            (gates, H.phase_results({g: (g != silent) for g in gates}))
            for silent in ("test-runner", "pr-reviewer", "commit")
        ]

        observation, paths = self._epic_run(specs)

        for path in paths:
            with self.subTest(work_item=os.path.basename(path)):
                dispatches = [
                    d
                    for d in observation["dispatches"]
                    if d.get("ticket_path") == path
                ]
                readbacks = H.readback_count_for(observation, path)
                self.assertGreaterEqual(
                    readbacks,
                    len(dispatches),
                    f"work item {os.path.basename(path)} reached "
                    f"{len(dispatches)} gate dispatch(es) but only {readbacks} "
                    "record read-back(s). Some gate's success went unchecked, "
                    "which is exactly how the guarantee held on one work item and "
                    f"lapsed on the next. Accepted read-back labels: "
                    f"{H.ACCEPTED_READBACK_LABELS}",
                )

    def test_verification_point_is_reached_once_per_dispatch_over_the_real_phase_set(
        self,
    ):
        # covers: BO-2900f-1-iii
        """The number of read-back verifications must equal the number of gate
        dispatches over the canonical phase set.

        This is the durable descriptor: tying the verification count to the
        dispatch count fails the day someone adds a gate that returns through a
        different path, which is the mechanism by which this defect comes back.
        """
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                gates = H.dispatchable_gates(script)
                worktree = self._worktree()
                ticket_path = H.write_ticket_record(
                    worktree, "01_generic_point.md", gates, title="Generic point"
                )
                observation = H.run_driver(
                    script,
                    H.single_ticket_scenario(
                        worktree,
                        ticket_path,
                        {
                            "title": "Generic point",
                            "phases": gates,
                            "has_test_requirements": True,
                            "results": H.phase_results({g: True for g in gates}),
                        },
                    ),
                )
                self.assertEqual(
                    len(observation["readbacks"]),
                    len(observation["dispatched"]),
                    f"{driver} dispatched {len(observation['dispatched'])} gates "
                    f"but performed {len(observation['readbacks'])} record "
                    "read-backs. There must be exactly one generic verification "
                    "point per driver, reached once per dispatch — not one added "
                    "at each gate's call site. Dispatched: "
                    f"{observation['dispatched']}",
                )

    def test_ran_and_did_not_record_is_reported_apart_from_skipped_and_from_never_requested(
        self,
    ):
        # covers: BO-2900f-1-iii
        """Three distinguishable results in ONE run.

        Reporting the ran-and-did-not-record case as skipped attributes a
        configuration cause to a recording failure, and sends the reader to turn
        on a gate that is already on.
        """
        ran_silently = "test-runner"
        requested_and_skipped = "pr-reviewer"
        never_requested = "documentation-expert"
        phases = [ran_silently, requested_and_skipped, "commit"]

        results = H.phase_results({ran_silently: False, "commit": True})
        results[requested_and_skipped] = {"status": "blocker", "record": False}

        for driver, observation, ticket_path in self.drive_both_twins(
            phases, results, classify={requested_and_skipped: "cross_agent"}
        ):
            with self.subTest(driver=driver):
                result = observation["result"]
                buckets = {
                    gate: gate_outcome_bucket(result, gate)
                    for gate in (ran_silently, requested_and_skipped, never_requested)
                }

                self.assertEqual(
                    buckets[never_requested],
                    "absent",
                    f"{driver}: a gate that was never requested must produce no "
                    f"entry at all. Buckets: {buckets}",
                )
                self.assertEqual(
                    buckets[requested_and_skipped],
                    "skipped",
                    f"{driver}: harness precondition — the cross_agent blocker "
                    f"must be reported as skipped. Buckets: {buckets}",
                )
                self.assertEqual(
                    buckets[ran_silently],
                    "failed",
                    f"{driver}: a gate that ran and did not record must be its own "
                    "outcome — distinct from skipped and from never requested. It "
                    f"was reported as {buckets[ran_silently]!r}. Buckets: "
                    f"{buckets}. Report: {_serialized(result)}",
                )
                self.assertNotEqual(
                    buckets[ran_silently],
                    buckets[requested_and_skipped],
                    f"{driver}: ran-and-did-not-record and requested-and-skipped "
                    "must be distinguishable from the work item alone.",
                )


if __name__ == "__main__":
    unittest.main()
