"""
Regression tests for BO-203: AC-coverage phase gates sort before commit/pull-request.

THE BUG: In both templates/workflows-js/build-feature.js and
templates/workflows-js/build-ticket.js, the agents ``ac-validator``,
``ac-fulfillment-gate``, and ``live-surface-tester`` are ABSENT from the
phaseOrder array.  getPriority() returns phaseOrder.length for any agent not
in the array, so those AC-coverage gates sort AFTER ``commit`` and
``pull-request`` — they fire after the commit/PR they were meant to gate.

These tests are RED against the current unmodified code: the three AC-coverage
agents are absent from phaseOrder in both JS files, causing 6 of the 9 tests
below to fail with AssertionError.

AC-to-test mapping (BO-203):
  Presence + ordering (build-feature.js):
    test_ac_validator_present_and_before_commit_in_build_feature
    test_ac_fulfillment_gate_present_and_before_commit_in_build_feature
    test_live_surface_tester_present_and_before_commit_in_build_feature
  Baseline ordering guard (build-feature.js):
    test_commit_before_pull_request_in_build_feature
  Presence + ordering (build-ticket.js):
    test_ac_validator_present_and_before_commit_in_build_ticket
    test_ac_fulfillment_gate_present_and_before_commit_in_build_ticket
    test_live_surface_tester_present_and_before_commit_in_build_ticket
  Baseline ordering guard (build-ticket.js):
    test_commit_before_pull_request_in_build_ticket
  Twin invariant (cross-file):
    test_phaseorder_twin_invariant

Red baseline (pre-implementation):
  6 of 9 tests fail immediately because ac-validator, ac-fulfillment-gate,
  and live-surface-tester are absent from phaseOrder in both JS files.
  The 3 tests for commit<pull-request and the twin invariant pass vacuously
  (those agents are present and the files are identically broken).
"""

from __future__ import annotations

import pathlib
import re
import unittest

# ---------------------------------------------------------------------------
# Paths to files under test (absolute, resolved from __file__)
# ---------------------------------------------------------------------------

_BUILD_FEATURE_JS = (
    pathlib.Path(__file__).resolve().parents[2]
    / "templates"
    / "workflows-js"
    / "build-feature.js"
)

_BUILD_TICKET_JS = (
    pathlib.Path(__file__).resolve().parents[2]
    / "templates"
    / "workflows-js"
    / "build-ticket.js"
)


# ---------------------------------------------------------------------------
# Module-level helpers (mirror the _phase_order_index pattern in
# test_build_feature_flatten_wiring.py, adapted for two-file comparison)
# ---------------------------------------------------------------------------


def _parse_phase_order(source_text: str) -> list:
    """
    Parse the ``const phaseOrder = [...]`` array from JS source text and return
    the quoted entries in declaration order.

    Returns an empty list if no phaseOrder array is found.

    Mirrors the regex approach in TestBuildFeatureFlattenWiring._phase_order_index.
    """
    match = re.search(
        r"const phaseOrder\s*=\s*\[(.*?)\]", source_text, re.DOTALL
    )
    if not match:
        return []
    array_body = match.group(1)
    return re.findall(r'["\']([^"\']+)["\']', array_body)


def _phase_index(entries: list, agent_name: str) -> int:
    """
    Return the list index of agent_name in entries, or len(entries) if absent.

    Returning len(entries) for absent agents mirrors the actual JS
    getPriority() sentinel:
        return idx === -1 ? phaseOrder.length : idx;
    so ordering assertions automatically fail when an agent is absent (the
    sentinel value equals or exceeds every valid index, including commit's).
    """
    try:
        return entries.index(agent_name)
    except ValueError:
        return len(entries)  # sentinel: absent agent sorts last (after commit/pull-request)


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestPhaseOrderAcGates(unittest.TestCase):
    """
    BO-203: ac-validator, ac-fulfillment-gate, and live-surface-tester must be
    present in phaseOrder and must sort BEFORE commit and pull-request in both
    build-feature.js and build-ticket.js.

    RED against current code: all three agents are absent from both files'
    phaseOrder arrays (6 failures expected).
    """

    def setUp(self) -> None:
        """Read both JS files once and parse their phaseOrder arrays."""
        self.bf_source = _BUILD_FEATURE_JS.read_text(encoding="utf-8")
        self.bt_source = _BUILD_TICKET_JS.read_text(encoding="utf-8")
        self.bf_order = _parse_phase_order(self.bf_source)
        self.bt_order = _parse_phase_order(self.bt_source)

    # ------------------------------------------------------------------
    # build-feature.js — presence + ordering for each AC-coverage gate
    # ------------------------------------------------------------------

    def test_ac_validator_present_and_before_commit_in_build_feature(self) -> None:
        # covers: BO-203
        """
        BO-203: 'ac-validator' is present in build-feature.js phaseOrder AND
        its index is strictly less than the index of 'commit'.

        RED now: ac-validator is absent from phaseOrder; assertIn fails with a
        clear message naming the missing entry.  _phase_index returns len(entries)
        (the same sentinel getPriority() uses), which is NOT less than commit's
        index — so the ordering assertion would also fail if assertIn were skipped.

        Must implement: add 'ac-validator' to phaseOrder at a position before
        'commit' (between 'pr-reviewer'/'user-surface-smoker' and 'commit').
        """
        entries = self.bf_order
        av_idx = _phase_index(entries, "ac-validator")
        commit_idx = _phase_index(entries, "commit")

        self.assertIn(
            "ac-validator",
            entries,
            "build-feature.js: 'ac-validator' is absent from the phaseOrder array. "
            "getPriority() therefore returns phaseOrder.length for this agent, "
            "causing it to sort AFTER commit and pull-request. "
            "Fix: add 'ac-validator' to phaseOrder before 'commit' (BO-203).",
        )
        self.assertLess(
            av_idx,
            commit_idx,
            f"build-feature.js: 'ac-validator' (phaseOrder index {av_idx}) must "
            f"sort before 'commit' (index {commit_idx}). "
            "AC-coverage gates must run before the commit phase (BO-203).",
        )

    def test_ac_fulfillment_gate_present_and_before_commit_in_build_feature(self) -> None:
        # covers: BO-203
        """
        BO-203: 'ac-fulfillment-gate' is present in build-feature.js phaseOrder
        AND its index is strictly less than the index of 'commit'.

        RED now: ac-fulfillment-gate is absent from phaseOrder.
        """
        entries = self.bf_order
        afg_idx = _phase_index(entries, "ac-fulfillment-gate")
        commit_idx = _phase_index(entries, "commit")

        self.assertIn(
            "ac-fulfillment-gate",
            entries,
            "build-feature.js: 'ac-fulfillment-gate' is absent from the phaseOrder "
            "array. getPriority() therefore returns phaseOrder.length for this agent, "
            "causing it to sort AFTER commit and pull-request. "
            "Fix: add 'ac-fulfillment-gate' to phaseOrder before 'commit' (BO-203).",
        )
        self.assertLess(
            afg_idx,
            commit_idx,
            f"build-feature.js: 'ac-fulfillment-gate' (phaseOrder index {afg_idx}) "
            f"must sort before 'commit' (index {commit_idx}). "
            "AC-fulfillment gate must run before the commit phase (BO-203).",
        )

    def test_live_surface_tester_present_and_before_commit_in_build_feature(self) -> None:
        # covers: BO-203
        """
        BO-203: 'live-surface-tester' is present in build-feature.js phaseOrder
        AND its index is strictly less than the index of 'commit'.

        RED now: live-surface-tester is absent from phaseOrder.
        """
        entries = self.bf_order
        lst_idx = _phase_index(entries, "live-surface-tester")
        commit_idx = _phase_index(entries, "commit")

        self.assertIn(
            "live-surface-tester",
            entries,
            "build-feature.js: 'live-surface-tester' is absent from the phaseOrder "
            "array. getPriority() therefore returns phaseOrder.length for this agent, "
            "causing it to sort AFTER commit and pull-request. "
            "Fix: add 'live-surface-tester' to phaseOrder before 'commit' (BO-203).",
        )
        self.assertLess(
            lst_idx,
            commit_idx,
            f"build-feature.js: 'live-surface-tester' (phaseOrder index {lst_idx}) "
            f"must sort before 'commit' (index {commit_idx}). "
            "live-surface-tester must run before the commit phase (BO-203).",
        )

    def test_commit_before_pull_request_in_build_feature(self) -> None:
        # covers: BO-203
        """
        BO-203: 'commit' sorts before 'pull-request' in build-feature.js phaseOrder.

        GREEN against current code (both agents present, correct order).
        Included as a baseline guard: if commit/pull-request were accidentally
        swapped by a future edit this test catches it.
        """
        entries = self.bf_order
        commit_idx = _phase_index(entries, "commit")
        pr_idx = _phase_index(entries, "pull-request")

        self.assertIn(
            "commit",
            entries,
            "build-feature.js: 'commit' is absent from phaseOrder (BO-203).",
        )
        self.assertIn(
            "pull-request",
            entries,
            "build-feature.js: 'pull-request' is absent from phaseOrder (BO-203).",
        )
        self.assertLess(
            commit_idx,
            pr_idx,
            f"build-feature.js: 'commit' (index {commit_idx}) must sort before "
            f"'pull-request' (index {pr_idx}) (BO-203).",
        )

    # ------------------------------------------------------------------
    # build-ticket.js — presence + ordering for each AC-coverage gate
    # ------------------------------------------------------------------

    def test_ac_validator_present_and_before_commit_in_build_ticket(self) -> None:
        # covers: BO-203
        """
        BO-203: 'ac-validator' is present in build-ticket.js phaseOrder AND
        its index is strictly less than the index of 'commit'.

        RED now: ac-validator is absent from phaseOrder.
        """
        entries = self.bt_order
        av_idx = _phase_index(entries, "ac-validator")
        commit_idx = _phase_index(entries, "commit")

        self.assertIn(
            "ac-validator",
            entries,
            "build-ticket.js: 'ac-validator' is absent from the phaseOrder array. "
            "getPriority() therefore returns phaseOrder.length for this agent, "
            "causing it to sort AFTER commit and pull-request. "
            "Fix: add 'ac-validator' to phaseOrder before 'commit' (BO-203).",
        )
        self.assertLess(
            av_idx,
            commit_idx,
            f"build-ticket.js: 'ac-validator' (phaseOrder index {av_idx}) must "
            f"sort before 'commit' (index {commit_idx}). "
            "AC-coverage gates must run before the commit phase (BO-203).",
        )

    def test_ac_fulfillment_gate_present_and_before_commit_in_build_ticket(self) -> None:
        # covers: BO-203
        """
        BO-203: 'ac-fulfillment-gate' is present in build-ticket.js phaseOrder
        AND its index is strictly less than the index of 'commit'.

        RED now: ac-fulfillment-gate is absent from phaseOrder.
        """
        entries = self.bt_order
        afg_idx = _phase_index(entries, "ac-fulfillment-gate")
        commit_idx = _phase_index(entries, "commit")

        self.assertIn(
            "ac-fulfillment-gate",
            entries,
            "build-ticket.js: 'ac-fulfillment-gate' is absent from the phaseOrder "
            "array. getPriority() therefore returns phaseOrder.length for this agent, "
            "causing it to sort AFTER commit and pull-request. "
            "Fix: add 'ac-fulfillment-gate' to phaseOrder before 'commit' (BO-203).",
        )
        self.assertLess(
            afg_idx,
            commit_idx,
            f"build-ticket.js: 'ac-fulfillment-gate' (phaseOrder index {afg_idx}) "
            f"must sort before 'commit' (index {commit_idx}). "
            "AC-fulfillment gate must run before the commit phase (BO-203).",
        )

    def test_live_surface_tester_present_and_before_commit_in_build_ticket(self) -> None:
        # covers: BO-203
        """
        BO-203: 'live-surface-tester' is present in build-ticket.js phaseOrder
        AND its index is strictly less than the index of 'commit'.

        RED now: live-surface-tester is absent from phaseOrder.
        """
        entries = self.bt_order
        lst_idx = _phase_index(entries, "live-surface-tester")
        commit_idx = _phase_index(entries, "commit")

        self.assertIn(
            "live-surface-tester",
            entries,
            "build-ticket.js: 'live-surface-tester' is absent from the phaseOrder "
            "array. getPriority() therefore returns phaseOrder.length for this agent, "
            "causing it to sort AFTER commit and pull-request. "
            "Fix: add 'live-surface-tester' to phaseOrder before 'commit' (BO-203).",
        )
        self.assertLess(
            lst_idx,
            commit_idx,
            f"build-ticket.js: 'live-surface-tester' (phaseOrder index {lst_idx}) "
            f"must sort before 'commit' (index {commit_idx}). "
            "live-surface-tester must run before the commit phase (BO-203).",
        )

    def test_commit_before_pull_request_in_build_ticket(self) -> None:
        # covers: BO-203
        """
        BO-203: 'commit' sorts before 'pull-request' in build-ticket.js phaseOrder.

        GREEN against current code (both agents present, correct order).
        Included as a baseline guard: if commit/pull-request were accidentally
        swapped by a future edit this test catches it.
        """
        entries = self.bt_order
        commit_idx = _phase_index(entries, "commit")
        pr_idx = _phase_index(entries, "pull-request")

        self.assertIn(
            "commit",
            entries,
            "build-ticket.js: 'commit' is absent from phaseOrder (BO-203).",
        )
        self.assertIn(
            "pull-request",
            entries,
            "build-ticket.js: 'pull-request' is absent from phaseOrder (BO-203).",
        )
        self.assertLess(
            commit_idx,
            pr_idx,
            f"build-ticket.js: 'commit' (index {commit_idx}) must sort before "
            f"'pull-request' (index {pr_idx}) (BO-203).",
        )

    # ------------------------------------------------------------------
    # Cross-file twin invariant
    # ------------------------------------------------------------------

    def test_phaseorder_twin_invariant(self) -> None:
        # covers: BO-203
        """
        BO-203: The phaseOrder sequence in build-feature.js must be IDENTICAL to
        the phaseOrder sequence in build-ticket.js (the twin invariant).

        GREEN against current code (both files have the same, equally broken,
        phaseOrder).  Catches regressions where one file is fixed but the other
        is left stale — e.g. ac-validator added to build-feature.js but not to
        build-ticket.js would fail this test even if the per-file tests pass.
        """
        self.assertEqual(
            self.bf_order,
            self.bt_order,
            "phaseOrder sequences in build-feature.js and build-ticket.js "
            "must be IDENTICAL (twin invariant — BO-203).\n"
            f"build-feature.js ({len(self.bf_order)} entries): {self.bf_order}\n"
            f"build-ticket.js  ({len(self.bt_order)} entries): {self.bt_order}",
        )


if __name__ == "__main__":
    unittest.main()
