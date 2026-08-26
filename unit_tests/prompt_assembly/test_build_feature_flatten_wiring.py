"""
Structural tests for the build-feature.js flatten-wiring rewire.

These tests read templates/workflows-js/build-feature.js as source text and
assert its dispatch wiring using regex/substring checks. No JavaScript is
executed. The tests distinguish the BROKEN state (both paths dispatch
agentType: 'ticket-supervisor' for per-ticket phase execution) from the FIXED
state (both paths dispatch each needed phase individually through the flattened
driver, inlining build-ticket.js semantics).

AC-to-test mapping (leaf ACs of BO-2000f):
  BO-2000f-1   → test_bo2000f1_epic_batch_uses_flattened_driver
  BO-2000f-2   → test_bo2000f2_single_ticket_uses_flattened_driver
  BO-2000f-3   → test_bo2000f3_tdd_separation_test_writer_before_coder
  BO-2000f-4   → test_bo2000f4_structural_guard_positive
  BO-2000f-4-i → test_bo2000f4i_structural_guard_flags_inline_supervisor
  BO-2000f-5   → test_bo2000f5_batching_and_orchestration_preserved
  BO-2000f-5-i → test_bo2000f5i_dependency_ordering_preserved

Red baseline (pre-implementation):
  6 of 7 tests fail immediately because build-feature.js still dispatches
  agentType: 'ticket-supervisor' and has no per-phase dispatch loop.
  test_bo2000f4i passes immediately (synthetic-snippet guard probe).
"""

import pathlib
import re
import unittest

# ---------------------------------------------------------------------------
# Path to the file under test (absolute, resolved from __file__)
# ---------------------------------------------------------------------------
_BUILD_FEATURE_JS = (
    pathlib.Path(__file__).resolve().parents[2]
    / "templates"
    / "workflows-js"
    / "build-feature.js"
)


class TestBuildFeatureFlattenWiring(unittest.TestCase):
    """
    Structural regression tests for build-feature.js phase-dispatch wiring.

    Each test targets one leaf AC of BO-2000f. Tests fail in the broken state
    (ticket-supervisor dispatched for per-ticket phase execution) and pass once
    build-feature.js inlines the flattened per-phase dispatch loop.
    """

    def setUp(self):
        """Read build-feature.js source once per test."""
        self.source = _BUILD_FEATURE_JS.read_text(encoding="utf-8")

    # ------------------------------------------------------------------
    # Guard helpers (pure functions — no I/O, suitable as reusable checks)
    # ------------------------------------------------------------------

    @staticmethod
    def _has_inline_supervisor_dispatch(source_text: str) -> bool:
        """
        Returns True if source_text dispatches agentType 'ticket-supervisor'
        for per-ticket phase execution (the broken anti-pattern that prevents
        phase-agent templates from applying).

        Used as the negative structural guard: any occurrence in agent() opts
        is the regression marker.
        """
        return bool(
            re.search(r'agentType\s*:\s*["\']ticket-supervisor["\']', source_text)
        )

    @staticmethod
    def _has_per_phase_dispatch(source_text: str) -> bool:
        """
        Returns True if source_text contains the flattened per-phase dispatch
        pattern: agentType: phaseName (a variable, not a string literal).

        This is the positive structural marker that the build-ticket.js-style
        phase loop has been inlined into build-feature.js.
        """
        return bool(re.search(r"agentType\s*:\s*phaseName\b", source_text))

    @staticmethod
    def _phase_order_index(source_text: str, agent_name: str) -> int:
        """
        Return the position of *agent_name* within the phaseOrder array in
        source_text, or -1 if the array is absent or the agent is not listed.

        Parses the first `const phaseOrder = [...]` block and extracts
        quoted entries in declaration order.
        """
        match = re.search(
            r"const phaseOrder\s*=\s*\[(.*?)\]", source_text, re.DOTALL
        )
        if not match:
            return -1
        array_body = match.group(1)
        entries = re.findall(r'["\']([^"\']+)["\']', array_body)
        try:
            return entries.index(agent_name)
        except ValueError:
            return -1

    # ------------------------------------------------------------------
    # BO-2000f-1: epic-batch path routes phases through flattened driver
    # ------------------------------------------------------------------

    def test_bo2000f1_epic_batch_uses_flattened_driver(self):
        # covers: BO-2000f-1
        """
        BO-2000f-1: The epic-batch path drives each ready ticket's phases through
        the flattened script-driver semantics (per-phase depth-1 dispatch), NOT
        via a single agentType: 'ticket-supervisor' that runs every phase inline.

        Fails now: build-feature.js dispatches agentType: 'ticket-supervisor'
        inside the epic batch loop (lines ~311-318 in the broken file).
        Passes after: the epic batch loop dispatches individual phase agents
        (agentType: phaseName variable reference, like build-ticket.js does).
        """
        self.assertFalse(
            self._has_inline_supervisor_dispatch(self.source),
            "build-feature.js dispatches agentType: 'ticket-supervisor' for "
            "per-ticket phase execution on the epic-batch path. "
            "The epic batch loop must be rewired to the flattened per-phase "
            "driver (BO-2000f-1): remove the ticket-supervisor dispatch and "
            "replace with a phase loop dispatching agentType: phaseName.",
        )
        self.assertTrue(
            self._has_per_phase_dispatch(self.source),
            "build-feature.js does not contain the per-phase dispatch pattern "
            "(agentType: phaseName). The epic-batch path requires a flattened "
            "per-phase loop matching build-ticket.js semantics (BO-2000f-1).",
        )
        # Path-specific (M-1): the EPIC path must fan out via parallel() and drive
        # each ticket through driveTicketPhases. A regression that rewired only the
        # single-ticket path would still pass the shared checks above but fail here.
        self.assertRegex(
            self.source,
            r"parallel\([\s\S]*?driveTicketPhases\(",
            "The epic-batch path must fan out via parallel() and drive each ready "
            "ticket through driveTicketPhases (BO-2000f-1).",
        )

    # ------------------------------------------------------------------
    # BO-2000f-2: single-ticket path routes phases through flattened driver
    # ------------------------------------------------------------------

    def test_bo2000f2_single_ticket_uses_flattened_driver(self):
        # covers: BO-2000f-2
        """
        BO-2000f-2: The single-ticket (else-branch) path drives the ticket's
        phases through the flattened driver, NOT a single agentType:
        'ticket-supervisor' that runs every phase inline.

        Fails now: the single-ticket else-branch dispatches
        agentType: 'ticket-supervisor' directly (~lines 398-407).
        Passes after: the single-ticket path uses the same per-phase dispatch
        loop as the epic-batch path (BO-2000f-1 / BO-2000f-2 share the loop).
        """
        self.assertFalse(
            self._has_inline_supervisor_dispatch(self.source),
            "build-feature.js dispatches agentType: 'ticket-supervisor' for "
            "the single-ticket path. Both paths must use the flattened "
            "per-phase driver (BO-2000f-2).",
        )
        self.assertTrue(
            self._has_per_phase_dispatch(self.source),
            "build-feature.js does not contain the per-phase dispatch pattern "
            "(agentType: phaseName). The single-ticket path requires the "
            "flattened driver (BO-2000f-2).",
        )
        # Path-specific (M-1): the SINGLE-TICKET branch must call driveTicketPhases
        # directly. A regression that rewired only the epic path would still pass
        # the shared checks above but fail here.
        self.assertRegex(
            self.source,
            r"Single-ticket path[\s\S]*?driveTicketPhases\(",
            "The single-ticket path must call driveTicketPhases directly "
            "(BO-2000f-2).",
        )

    # ------------------------------------------------------------------
    # BO-2000f-3: test-writer dispatched before coder as a separate phase
    # ------------------------------------------------------------------

    def test_bo2000f3_tdd_separation_test_writer_before_coder(self):
        # covers: BO-2000f-3
        """
        BO-2000f-3: TDD separation — 'test-writer' is listed before 'python-coder'
        in the canonical phaseOrder array so each runs as a separate depth-1
        agent call rather than being collapsed into a single inline supervisor.

        Fails now: build-feature.js has no phaseOrder array (it delegates
        everything to ticket-supervisor, so no phase ordering exists at all).
        Passes after: the inlined phaseOrder array (from build-ticket.js) lists
        'test-writer' at an earlier index than 'python-coder'.
        """
        tw_idx = self._phase_order_index(self.source, "test-writer")
        pc_idx = self._phase_order_index(self.source, "python-coder")

        self.assertGreater(
            tw_idx,
            -1,
            "build-feature.js does not contain a phaseOrder array with "
            "'test-writer'. The flattened driver must define a canonical "
            "phase ordering so test-writer runs before the coder (BO-2000f-3).",
        )
        self.assertGreater(
            pc_idx,
            -1,
            "build-feature.js does not contain a phaseOrder array with "
            "'python-coder'. The canonical phase ordering must be present "
            "for TDD separation to be enforced (BO-2000f-3).",
        )
        self.assertLess(
            tw_idx,
            pc_idx,
            f"'test-writer' (phaseOrder index {tw_idx}) must precede "
            f"'python-coder' (index {pc_idx}) in the phaseOrder array to "
            "preserve TDD separation under the flattened driver (BO-2000f-3).",
        )

    # ------------------------------------------------------------------
    # BO-2000f-4: structural guard positive — correctly-wired file passes
    # ------------------------------------------------------------------

    def test_bo2000f4_structural_guard_positive(self):
        # covers: BO-2000f-4
        """
        BO-2000f-4: The structural regression guard PASSES for a correctly-wired
        build-feature.js. That means: no agentType: 'ticket-supervisor' for
        per-ticket phase execution AND a per-phase dispatch (agentType: phaseName)
        is present.

        Fails now: build-feature.js is in the broken state — it dispatches
        ticket-supervisor for both paths and has no per-phase loop.
        Passes after: the rewire removes the ticket-supervisor dispatch and adds
        the per-phase loop; the guard passes cleanly.
        """
        self.assertFalse(
            self._has_inline_supervisor_dispatch(self.source),
            "Structural guard FAILED (BO-2000f-4): agentType: 'ticket-supervisor' "
            "found in build-feature.js for per-ticket phase execution. "
            "Phase execution must route through the flattened driver, not a "
            "single supervisor that runs all phases inline.",
        )
        self.assertTrue(
            self._has_per_phase_dispatch(self.source),
            "Structural guard FAILED (BO-2000f-4): no per-phase dispatch "
            "(agentType: phaseName) found in build-feature.js. The flattened "
            "driver must dispatch each needed phase as its own depth-1 agent call.",
        )

    # ------------------------------------------------------------------
    # BO-2000f-4-i: guard negative — synthetic bad snippet is flagged
    #   NOTE: passes immediately (synthetic input controlled by test).
    # ------------------------------------------------------------------

    def test_bo2000f4i_structural_guard_flags_inline_supervisor(self):
        # covers: BO-2000f-4-i
        """
        BO-2000f-4-i: The guard correctly FLAGS a synthetic snippet that
        dispatches agentType: 'ticket-supervisor' for per-ticket phase execution.
        This proves the guard function itself works — it is not a tautology that
        vacuously passes.

        NOTE: This test uses a synthetic snippet (controlled input) and therefore
        passes immediately. It does not depend on the state of build-feature.js.
        Included to satisfy BO-2000f-4-i: confirm the guard can detect the
        regression when reintroduced. Will remain green both before and after the fix.
        """
        # Synthetic snippet reproducing the broken anti-pattern exactly.
        bad_snippet = (
            "const result = await agent(\n"
            '  "Drive ticket to completion: ${worktreeTicketPath}. '
            "Execute all needed phase agents in order.\",\n"
            "  {\n"
            '    agentType: "ticket-supervisor",\n'
            '    label: "ticket:foo",\n'
            "    phase: \"Build\",\n"
            "  }\n"
            ");\n"
        )

        # Guard must detect agentType: 'ticket-supervisor' in the bad snippet.
        self.assertTrue(
            self._has_inline_supervisor_dispatch(bad_snippet),
            "Guard did not detect agentType: 'ticket-supervisor' in the synthetic "
            "bad snippet. The _has_inline_supervisor_dispatch helper is broken — "
            "it must return True for the anti-pattern (BO-2000f-4-i).",
        )

        # Guard must NOT find per-phase dispatch in the bad snippet.
        self.assertFalse(
            self._has_per_phase_dispatch(bad_snippet),
            "Guard incorrectly found agentType: phaseName in the synthetic bad "
            "snippet. The bad snippet only dispatches ticket-supervisor, so "
            "_has_per_phase_dispatch must return False (BO-2000f-4-i).",
        )

    # ------------------------------------------------------------------
    # BO-2000f-5: batching and orchestration preserved after rewire
    # ------------------------------------------------------------------

    def test_bo2000f5_batching_and_orchestration_preserved(self):
        # covers: BO-2000f-5
        """
        BO-2000f-5: Rewiring build-feature.js to the flattened driver must not
        drop the worktree guard, planner batching, or failure adjudication. Assert
        that BATCH_SIZE, the worktreeResult guard, and the per-phase dispatch
        coexist in the rewired file.

        Fails now: per-phase dispatch (agentType: phaseName) is absent — even
        though BATCH_SIZE and worktreeResult are already present.
        Passes after: per-phase dispatch is added alongside the preserved
        batching/guard logic.
        """
        # Batching logic must survive the rewire.
        self.assertIn(
            "BATCH_SIZE",
            self.source,
            "build-feature.js no longer defines BATCH_SIZE. The planner "
            "batching logic must be preserved after the rewire (BO-2000f-5).",
        )
        # Worktree guard must survive the rewire.
        self.assertIn(
            "worktreeResult",
            self.source,
            "build-feature.js no longer references worktreeResult. The worktree "
            "quality-gate guard must be preserved after the rewire (BO-2000f-5).",
        )
        # Per-phase dispatch must now be present — this assertion fails before the fix.
        self.assertTrue(
            self._has_per_phase_dispatch(self.source),
            "build-feature.js does not contain the per-phase dispatch pattern "
            "(agentType: phaseName). The rewire must add this alongside the "
            "preserved batching logic and worktree guard (BO-2000f-5).",
        )

    # ------------------------------------------------------------------
    # BO-2000f-5-i: dependency ordering preserved after rewire
    # ------------------------------------------------------------------

    def test_bo2000f5i_dependency_ordering_preserved(self):
        # covers: BO-2000f-5-i
        """
        BO-2000f-5-i: The depends_on ordering logic is preserved after the rewire
        — a ticket is not dispatched until its dependency predecessors complete.
        Assert that 'depends_on' is still referenced in the planner prompt AND
        the per-phase dispatch loop is present.

        Fails now: per-phase dispatch (agentType: phaseName) is absent — even
        though 'depends_on' is already referenced in the current broken file.
        Passes after: per-phase dispatch is present alongside the preserved
        dependency-ordering logic.
        """
        # depends_on must still be referenced in the planner prompt or batch logic.
        self.assertIn(
            "depends_on",
            self.source,
            "build-feature.js no longer references 'depends_on'. The dependency "
            "ordering step must survive the rewire (BO-2000f-5-i).",
        )
        # Per-phase dispatch must now be present — fails before the fix.
        self.assertTrue(
            self._has_per_phase_dispatch(self.source),
            "build-feature.js does not contain the per-phase dispatch pattern "
            "(agentType: phaseName). The rewire must implement flattened dispatch "
            "while preserving depends_on dependency ordering (BO-2000f-5-i).",
        )


    # ------------------------------------------------------------------
    # Hardening (code-review M-3): null / empty phase result must halt
    # ------------------------------------------------------------------

    def test_null_phase_result_halts_not_completes(self):
        # covers: code-review M-3 (hardens BO-2000f-1 / BO-2000f-2)
        """
        A phase agent returning null (agent died / was skipped), an empty status,
        or an UNRECOGNISED status must HALT the driver, not be silently recorded
        as a completed phase — which would let the driver proceed to commit /
        pull-request on incomplete work.

        Asserts driveTicketPhases guards the phase result before the
        blocker/failed check.

        The guard was originally `if (!phaseResult || !resultStatus)`, and this
        assertion matched that literal text. Truthiness turned out to be weaker
        than the guard's own docstring claimed: a hallucinated-but-truthy status
        ("complete", "done") passed it and then matched neither the
        blocker/failed nor the handoff branch, landing back in the silent-success
        hole the guard exists to close (KI-SS-001). The guard now tests
        membership in PHASE_STATUS_VALUES, so this assertion tracks the stronger
        form.

        NOTE: this remains a source-level assertion, which per CLAUDE.md
        ("Gate / Workflow ACs — Verify Behaviorally, Not by Grep") cannot prove
        the guard actually runs. Behavioral coverage of the same failure mode —
        executing the workflow under the E2 harness with a dead agent and
        asserting the terminal payload — lives in
        unit_tests/test_fail_closed_agent_results.py.
        """
        self.assertRegex(
            self.source,
            r"if\s*\(\s*!phaseResult\s*\|\|\s*"
            r"!PHASE_STATUS_VALUES\.includes\(\s*resultStatus\s*\)",
            "build-feature.js does not guard against a null / empty / "
            "unrecognised phase result. driveTicketPhases must halt (not record "
            "as completed) when a phase agent returns null or a status outside "
            "PHASE_STATUS_VALUES, so the driver never proceeds to commit on "
            "incomplete work (code-review M-3).",
        )


if __name__ == "__main__":
    unittest.main()
