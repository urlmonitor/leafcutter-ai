"""Behavioral tests for the completion-time re-read of an epic's work (BUG-19).

Covers:
  BO-300a-5   — the epic's work is re-read before the drive reports, and
                anything added after planning is named.
  BO-300a-5-i — an epic whose work cannot be re-read is reported unverified, and
                pre-existing or removed work raises no false alarm.

Every test EXECUTES templates/workflows-js/build-feature.js through
harness_build_ticket_guard.mjs with an enumeration stub that answers
DIFFERENTLY on its second call — a condition no static test can express — and
asserts on the completion output the run emitted.

n_location_rule for both ACs is 1: build-feature.js drives an epic and owns the
re-read; build-ticket.js drives a single piece of work and has no epic set to
re-read. The twin obligation is therefore to CONFIRM the twin correctly carries
no counterpart, not to add a stub — see
TestTwinCarriesNoEpicRecheckCounterpart at the bottom of this file.

Observed (run wf_cc2b46d9-f6f): the batch plan was computed once and enumerated
ten pieces of work. Three more were committed to the epic branch twenty-six
minutes later. They were never built — defensible — AND never appeared in the
final output's halted or skipped lists. The drive would have reported the epic
complete having never seen them.

SCOPE NOTE ON BO-300a-5's fifth descriptor. That descriptor asks that "the four
sections BO-300a-2 specifies remain present and in order". BO-300a-2 is written
against build-epic.js (the older /build-epic driver, out of scope here), and
build-feature.js has already drifted from it: build-feature.js's completion
message carries a summary but no manual-tests or finalize section. Asserting the
four literal sections against build-feature.js would force a port of another
driver's output format under cover of this AC, which contradicts the descriptor's
own intent ("the new section is an addition rather than a rewrite"). The
descriptor is therefore implemented as a no-rewrite regression guard over the
completion fields build-feature.js actually emits today.
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

GATES = ["test-runner", "commit"]

_DISCOVERED_TOKENS = (
    "discovered",
    "after planning",
    "after the plan",
    "unplanned",
    "not planned",
    "added during",
    "not in the plan",
)
_UNREADABLE_TOKENS = (
    "could not be read",
    "cannot be read",
    "unreadable",
    "not verified",
    "unverified",
    "failed to read",
    "re-read failed",
    "enumeration failed",
)
_REMOVED_TOKENS = (
    "no longer present",
    "removed",
    "vanished",
    "gone from",
    "missing from the epic",
)


def _serialized(result) -> str:
    return json.dumps(result, sort_keys=True) if result is not None else ""


def _mentions_any(result, tokens) -> bool:
    text = _serialized(result).lower()
    return any(token in text for token in tokens)


class _EpicRecheckCase(unittest.TestCase):
    def setUp(self):
        if not H.node_available():
            self.skipTest("node is not available on PATH")
        self._tmpdirs = []

    def tearDown(self):
        for path in self._tmpdirs:
            shutil.rmtree(path, ignore_errors=True)

    def _worktree(self) -> str:
        path = tempfile.mkdtemp(prefix="bo300_")
        self._tmpdirs.append(path)
        return path

    def build_epic(self, worktree, names):
        """Write real ticket records for the epic; return (epic_path, {name: path})."""
        epic_subdir = os.path.join("tickets", "00_inbox", "epics", "EPIC-Growth")
        epic_path = os.path.join(worktree, epic_subdir)
        os.makedirs(epic_path, exist_ok=True)
        paths = {}
        for name in names:
            paths[name] = H.write_ticket_record(
                worktree, name, GATES, title=name, subdir=epic_subdir
            )
        return epic_path, paths

    def drive_epic(self, worktree, epic_path, paths, reads):
        """Run build-feature.js over the epic with the given enumeration answers."""
        tickets = {
            path: {
                "title": os.path.basename(path),
                "phases": GATES,
                "has_test_requirements": True,
                "results": H.phase_results({g: True for g in GATES}),
            }
            for path in paths.values()
        }
        scenario = H.epic_scenario(worktree, epic_path, tickets, reads)
        return H.run_driver(H.BUILD_FEATURE_JS, scenario)

    @staticmethod
    def present(paths, names, done=()):
        return [
            {"path": paths[n], "status": "done" if n in done else "todo"} for n in names
        ]


# ---------------------------------------------------------------------------
# BO-300a-5 — detect and report work added after planning
# ---------------------------------------------------------------------------


class TestWorkAddedAfterPlanningIsNamed(_EpicRecheckCase):
    """BO-300a-5: an epic that grows during a drive never loses the additions
    from both the built list and the outstanding list at once."""

    def _grown_epic(self):
        worktree = self._worktree()
        planned = ["01_a.md", "02_b.md"]
        added = ["03_c.md", "04_d.md", "05_e.md"]
        epic_path, paths = self.build_epic(worktree, planned + added)
        reads = [
            {"present": self.present(paths, planned)},
            {"present": self.present(paths, planned + added)},
        ]
        observation = self.drive_epic(worktree, epic_path, paths, reads)
        return observation, paths, added

    def test_work_added_after_planning_is_named_in_the_completion_output(self):
        # covers: BO-300a-5
        """Three pieces of work appear in the epic between the plan and the end.

        All three must be named in the emitted completion output as discovered
        after planning. The contract is detect-and-report: they are surfaced,
        named, and left outstanding — building them inside the same drive would
        leave the drive with no termination condition.
        """
        observation, paths, added = self._grown_epic()
        result = observation["result"]

        self.assertGreaterEqual(
            len(observation["enumerations"]),
            2,
            "build-feature.js enumerated the epic's work "
            f"{len(observation['enumerations'])} time(s). The set must be read "
            "AGAIN at the moment the completion output is produced and compared "
            "with the set the plan was built from.",
        )
        for name in added:
            self.assertIn(
                paths[name],
                _serialized(result),
                f"{name} was added to the epic after planning and is named "
                "nowhere in the completion output — invisible in both the built "
                f"list and the outstanding list at once. Output: "
                f"{_serialized(result)}",
            )
        self.assertTrue(
            _mentions_any(result, _DISCOVERED_TOKENS),
            "the additions must be identified AS discovered after planning, not "
            "merely mentioned. The output must also state what the operator "
            f"should do about them. Output: {_serialized(result)}",
        )

    def test_the_epic_complete_statement_is_withheld_while_unplanned_work_exists(self):
        # covers: BO-300a-5
        """Suppressing the complete claim is the load-bearing half.

        Naming the additions in a list while still emitting an epic-complete
        statement leaves the operator with two contradictory sentences and an
        archive attempt that will fail later.
        """
        observation, _paths, _added = self._grown_epic()
        result = observation["result"]

        self.assertFalse(
            H.claims_epic_complete(result),
            "the drive emitted an epic-complete statement while three pieces of "
            "work exist in the epic that it never planned and never built. "
            f"Output: {_serialized(result)}",
        )

    def test_unchanged_epic_still_reports_complete_with_no_additions_section(self):
        # covers: BO-300a-5
        """CONTROL CASE: an epic whose set is identical at both reads produces
        the existing completion output unchanged, with no discovered entries.

        The cheapest way to pass the two assertions above is to stop claiming
        completion at all; this control makes that fix visible.
        """
        worktree = self._worktree()
        planned = ["01_a.md", "02_b.md"]
        epic_path, paths = self.build_epic(worktree, planned)
        reads = [
            {"present": self.present(paths, planned)},
            {"present": self.present(paths, planned)},
        ]
        result = self.drive_epic(worktree, epic_path, paths, reads)["result"]

        self.assertTrue(
            H.claims_epic_complete(result),
            "an epic whose work set did not change must still report complete — "
            "otherwise the fix is 'never claim completion', which passes every "
            f"negative case and helps nobody. Output: {_serialized(result)}",
        )
        self.assertFalse(
            _mentions_any(result, _DISCOVERED_TOKENS),
            "nothing was added, so no discovered-after-planning entries may be "
            f"emitted. Output: {_serialized(result)}",
        )

    def test_the_comparison_is_by_identity_not_by_count(self):
        # covers: BO-300a-5
        """One piece of work added and one removed leaves the count unchanged.

        A comparison by count sees nothing; the addition must still be named.
        """
        worktree = self._worktree()
        planned = ["01_a.md", "02_b.md"]
        epic_path, paths = self.build_epic(worktree, planned + ["03_new.md"])
        reads = [
            {"present": self.present(paths, planned)},
            # 02_b.md removed, 03_new.md added — count is still 2.
            {"present": self.present(paths, ["01_a.md", "03_new.md"])},
        ]
        result = self.drive_epic(worktree, epic_path, paths, reads)["result"]

        self.assertIn(
            paths["03_new.md"],
            _serialized(result),
            "03_new.md was added after planning while 02_b.md was removed, so "
            "the set size is unchanged. The comparison must be by identity, not "
            f"by count. Output: {_serialized(result)}",
        )

    def test_existing_completion_sections_are_unchanged(self):
        # covers: BO-300a-5
        """The new section must be an ADDITION to the completion output, not a
        rewrite of it.

        See the SCOPE NOTE in this module's docstring: BO-300a-2's four literal
        sections belong to build-epic.js, which build-feature.js has already
        drifted from. This is therefore a no-rewrite regression guard over the
        completion facts build-feature.js emits today — the epic title, the
        worktree path, the batch count and the ticket count. It is expected to
        be GREEN before and after the fix; it fails only if the fix rewrites the
        existing output instead of extending it.
        """
        worktree = self._worktree()
        planned = ["01_a.md", "02_b.md"]
        epic_path, paths = self.build_epic(worktree, planned)
        reads = [
            {"present": self.present(paths, planned)},
            {"present": self.present(paths, planned)},
        ]
        result = self.drive_epic(worktree, epic_path, paths, reads)["result"]

        self.assertIsInstance(result, dict)
        for field in ("epic_path", "title", "worktree_path", "batches_run", "message"):
            self.assertIn(
                field,
                result,
                f"the completion output lost its existing '{field}' field. The "
                "discovered-after-planning report is an addition to the output, "
                f"not a rewrite of it. Output: {_serialized(result)}",
            )
        self.assertEqual(
            result["worktree_path"],
            worktree,
            "the completion output must still name the worktree on disk",
        )


# ---------------------------------------------------------------------------
# BO-300a-5-i — fail closed when the set cannot be read; stay quiet otherwise
# ---------------------------------------------------------------------------


class TestRecheckFailsClosedAndRaisesNoFalseAlarm(_EpicRecheckCase):
    """BO-300a-5-i: the check fails closed when it cannot see, and stays quiet
    when nothing was added."""

    def test_unreadable_work_set_reports_the_epic_not_verified_complete(self):
        # covers: BO-300a-5-i
        """The re-read fails at completion time.

        A re-read that fails must not be treated as a re-read that found nothing
        new. An implementation that returns an empty set on error re-creates the
        original defect exactly, while appearing to have fixed it.
        """
        worktree = self._worktree()
        planned = ["01_a.md", "02_b.md"]
        epic_path, paths = self.build_epic(worktree, planned)
        reads = [
            {"present": self.present(paths, planned)},
            {"error": "EACCES: permission denied reading the epic folder"},
        ]
        observation = self.drive_epic(worktree, epic_path, paths, reads)
        result = observation["result"]

        self.assertFalse(
            H.claims_epic_complete(result),
            "the epic's work set could not be read back, so no epic-complete "
            f"statement may be emitted. Output: {_serialized(result)}",
        )
        self.assertTrue(
            _mentions_any(result, _UNREADABLE_TOKENS),
            "the output must report the epic as NOT VERIFIED complete and name "
            f"why the set could not be read. Output: {_serialized(result)}",
        )

    def test_unchanged_work_set_names_nothing_as_discovered_after_planning(self):
        # covers: BO-300a-5-i
        """Both reads return the same set, including one piece of work that was
        already complete before the drive started.

        If already-complete work shows up as discovered after planning, every
        drive emits the section and operators learn to skip it — a failure that
        is slower and harder to detect than the original.
        """
        worktree = self._worktree()
        names = ["01_a.md", "02_b.md", "03_already_done.md"]
        epic_path, paths = self.build_epic(worktree, names)
        # 03 was already complete before the drive: present in both reads, but
        # omitted from the plan because its status is done.
        present = self.present(paths, names, done={"03_already_done.md"})
        reads = [{"present": present}, {"present": present}]
        observation = self.drive_epic(worktree, epic_path, paths, reads)
        result = observation["result"]

        self.assertGreaterEqual(
            len(observation["enumerations"]),
            2,
            "the completion-time re-read must happen even when nothing changed — "
            "it is what makes the claim in the output true at the moment it is "
            f"made. Enumerations observed: {len(observation['enumerations'])}",
        )
        self.assertNotIn(
            paths["03_already_done.md"],
            _serialized(result),
            "a piece of work that was already complete before the drive must not "
            f"be named at all. Output: {_serialized(result)}",
        )
        self.assertFalse(
            _mentions_any(result, _DISCOVERED_TOKENS),
            "nothing was added after planning, so nothing may be named as "
            f"discovered after planning. Output: {_serialized(result)}",
        )

    def test_work_removed_during_the_drive_is_reported_as_no_longer_present(self):
        # covers: BO-300a-5-i
        """A removal is not an addition, and is not silently absent from both
        lists — which is the same class of omission BUG-19 is."""
        worktree = self._worktree()
        planned = ["01_a.md", "02_b.md"]
        epic_path, paths = self.build_epic(worktree, planned)
        reads = [
            {"present": self.present(paths, planned)},
            {"present": self.present(paths, ["01_a.md"])},
        ]
        result = self.drive_epic(worktree, epic_path, paths, reads)["result"]

        self.assertIn(
            paths["02_b.md"],
            _serialized(result),
            "02_b.md was planned and is no longer in the epic; it must be named "
            f"rather than dropped from both lists. Output: {_serialized(result)}",
        )
        self.assertTrue(
            _mentions_any(result, _REMOVED_TOKENS),
            "work that was planned and is now gone is a different event with a "
            "different action: it must be reported as no longer present, not as "
            f"unbuilt and not as an addition. Output: {_serialized(result)}",
        )
        self.assertFalse(
            _mentions_any(result, _DISCOVERED_TOKENS),
            "a removal must not be reported as work discovered after planning. "
            f"Output: {_serialized(result)}",
        )

    def test_an_empty_second_read_is_not_treated_as_a_failed_read_or_the_reverse(self):
        # covers: BO-300a-5-i
        """An empty set and a failed read are the same value in the most likely
        implementation. Once they are conflated the fail-closed guarantee is
        decorative, so the two must produce different outputs.
        """
        worktree = self._worktree()
        epic_path, paths = self.build_epic(worktree, ["01_a.md"])

        # Case A — the epic genuinely contains no work.
        empty_result = self.drive_epic(
            worktree, epic_path, paths, [{"present": []}, {"present": []}]
        )["result"]

        # Case B — the read failed. Same epic, same paths.
        failed_result = self.drive_epic(
            worktree,
            epic_path,
            paths,
            [
                {"present": self.present(paths, ["01_a.md"])},
                {"error": "ENOENT: the epic folder could not be listed"},
            ],
        )["result"]

        self.assertFalse(
            _mentions_any(empty_result, _UNREADABLE_TOKENS),
            "an epic that genuinely contains no work must NOT be reported as "
            f"unreadable. Output: {_serialized(empty_result)}",
        )
        self.assertTrue(
            _mentions_any(failed_result, _UNREADABLE_TOKENS),
            "a read that failed must be reported as such. Output: "
            f"{_serialized(failed_result)}",
        )
        self.assertNotEqual(
            _serialized(empty_result),
            _serialized(failed_result),
            "an empty second read and a failed second read produced identical "
            "output, so the two states are conflated and the fail-closed "
            "guarantee is decorative.",
        )


# ---------------------------------------------------------------------------
# Twin obligation — n_location_rule: 1
# ---------------------------------------------------------------------------


class TestTwinCarriesNoEpicRecheckCounterpart(unittest.TestCase):
    """BO-300a-5 / BO-300a-5-i declare n_location_rule: 1.

    build-ticket.js drives a single piece of work and has no epic set to
    re-read, so the twin obligation is to confirm and record that it correctly
    carries NO counterpart — not to add a stub.

    This test is expected to be GREEN before and after the fix. It exists so the
    twins do not silently drift into two different completion contracts: it
    fails if a coder mechanically mirrors the epic re-read into the
    single-ticket driver.
    """

    def setUp(self):
        if not H.node_available():
            self.skipTest("node is not available on PATH")
        self._worktree = tempfile.mkdtemp(prefix="bo300_twin_")

    def tearDown(self):
        shutil.rmtree(self._worktree, ignore_errors=True)

    def test_single_ticket_driver_performs_no_epic_enumeration(self):
        # covers: BO-300a-5
        # covers: BO-300a-5-i
        """build-ticket.js must perform zero epic enumerations and emit no
        discovered-after-planning report."""
        ticket_path = H.write_ticket_record(
            self._worktree, "01_solo.md", GATES, title="Solo ticket"
        )
        scenario = H.single_ticket_scenario(
            self._worktree,
            ticket_path,
            {
                "title": "Solo ticket",
                "phases": GATES,
                "has_test_requirements": True,
                "results": H.phase_results({g: True for g in GATES}),
            },
        )
        observation = H.run_driver(H.BUILD_TICKET_JS, scenario)

        self.assertEqual(
            observation["enumerations"],
            [],
            "build-ticket.js drives a single piece of work and has no epic set "
            "to re-read. An epic enumeration here means the re-read was "
            "mirrored into the wrong twin.",
        )
        self.assertFalse(
            _mentions_any(observation["result"], _DISCOVERED_TOKENS),
            "build-ticket.js must not emit a discovered-after-planning report. "
            f"Output: {_serialized(observation['result'])}",
        )


if __name__ == "__main__":
    unittest.main()
