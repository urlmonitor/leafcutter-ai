"""
MODULE: test_bp_1100f_5
GOAL: Behavioral tests verifying that a side-effect-declaring work item CANNOT reach
      a done state with the user-surface-smoker phase unrun or silently skipped.

COVERS: BP-1100f-5
TICKET: tickets/00_inbox/TICKET-20260721-BP-1100f-5.md

These tests exercise the REAL routing functions — not mocks — to assert that:
1. user-surface-smoker is present in _CANONICAL_PHASE_ORDER so it is correctly
   ordered as a gating phase.
2. A ticket that declares a side-effect and has user-surface-smoker: needed in
   its agents map cannot be considered done if user-surface-smoker is still needed.
3. The phase-order position ensures user-surface-smoker runs before commit (12),
   not after.

RED baseline: tests 1 and 3 are RED before implementation because
user-surface-smoker is not in _CANONICAL_PHASE_ORDER and _build_agents_map has
no declares_side_effect parameter.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup: unit_tests/ is 2 levels below the repo root
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

import generate_ticket_from_ac as _gtfac  # noqa: E402


# ---------------------------------------------------------------------------
# Config paths
# ---------------------------------------------------------------------------

_GUARDRAIL_CONFIG = _REPO_ROOT / "config" / "guardrail_gates.yaml"
_AGENT_REGISTRY = _REPO_ROOT / "config" / "agent_registry.json"


class TestSmokecheckCannotBeSilentlySkippedBeforeDone(unittest.TestCase):
    """BP-1100f-5: smoke check cannot be silently skipped before done.

    Verifies the invariant structurally — by checking that:
      (a) user-surface-smoker is in _CANONICAL_PHASE_ORDER (so it is part of the
          deterministic dispatch order and cannot be silently skipped by falling
          outside the canonical list)
      (b) user-surface-smoker appears BEFORE commit and pull-request in that order
          (so a ticket cannot be committed with the smoke check unrun)
      (c) A ticket with declares_side_effect: True computes user-surface-smoker: needed
          in its agents map — so the done-gate sees a pending required phase and cannot
          mark the ticket done until it signs off.
    """

    def test_user_surface_smoker_in_canonical_phase_order(self) -> None:
        # covers: BP-1100f-5
        """user-surface-smoker must be in _CANONICAL_PHASE_ORDER.

        When an agent is missing from _CANONICAL_PHASE_ORDER, the generator
        places it in the non-canonical bucket (sorted before commit/pull-request
        but without a stable position guarantee). Being in the canonical list
        means the agent CANNOT be silently omitted from the dispatch order —
        it is always positioned correctly relative to its neighbouring phases.

        MUST be RED before implementation: user-surface-smoker is not in
        _CANONICAL_PHASE_ORDER in the current codebase.
        """
        self.assertIn(
            "user-surface-smoker",
            _gtfac._CANONICAL_PHASE_ORDER,
            (
                "user-surface-smoker must be present in _CANONICAL_PHASE_ORDER so "
                "it cannot be silently skipped. When omitted from the canonical list, "
                "the agent falls into the non-canonical bucket with no guaranteed "
                "position relative to pr-reviewer/commit, meaning a ticket could "
                "be committed before the smoke check runs (violating BP-1100f-5). "
                f"Current _CANONICAL_PHASE_ORDER: {_gtfac._CANONICAL_PHASE_ORDER!r}. "
                "Fix: add 'user-surface-smoker' after 'pr-reviewer' and before "
                "'ac-validator' in _CANONICAL_PHASE_ORDER."
            ),
        )

    def test_user_surface_smoker_before_commit_in_phase_order(self) -> None:
        # covers: BP-1100f-5
        """user-surface-smoker must appear BEFORE commit in _CANONICAL_PHASE_ORDER.

        If the smoke check runs after commit, the work item can be committed with
        the smoke check unrun — violating "cannot reach done with smoke check
        unrun or silently skipped".

        MUST be RED before implementation: user-surface-smoker is absent from
        _CANONICAL_PHASE_ORDER so its position relative to commit is undefined.
        """
        order = _gtfac._CANONICAL_PHASE_ORDER
        self.assertIn(
            "user-surface-smoker",
            order,
            "user-surface-smoker must be in _CANONICAL_PHASE_ORDER (prerequisite for this check).",
        )
        self.assertIn(
            "commit",
            order,
            "commit must be in _CANONICAL_PHASE_ORDER.",
        )
        smoker_idx = order.index("user-surface-smoker")
        commit_idx = order.index("commit")
        self.assertLess(
            smoker_idx,
            commit_idx,
            (
                "user-surface-smoker must appear BEFORE commit in _CANONICAL_PHASE_ORDER. "
                f"Current positions: user-surface-smoker={smoker_idx}, commit={commit_idx}. "
                "A smoke check that runs after commit cannot prevent committing untested "
                "side-effects — it would be advisory, not mandatory (BP-1100f-5 violation)."
            ),
        )

    def test_side_effect_ticket_has_smoker_as_needed_phase(self) -> None:
        # covers: BP-1100f-5
        """A side-effect-declaring AC must produce user-surface-smoker: needed in agents map.

        This simulates the done-gate invariant: the ticket-supervisor checks the
        agents map; if user-surface-smoker is 'needed', the ticket cannot be
        marked done until it transitions to 'signed_off'. By asserting the field
        is 'needed' in the computed map, we verify that the smoke check is
        mandatory and cannot be silently skipped.

        MUST be RED before implementation: _build_agents_map has no
        declares_side_effect parameter and never adds user-surface-smoker.
        """
        agents = _gtfac._build_agents_map(
            "python-coder",
            change_targets=["pipeline"],
            risk_surface="contract_boundary",
            files_touched=["config/agent_registry.json"],
            declares_side_effect=True,
            guardrail_config_path=_GUARDRAIL_CONFIG,
            agent_registry_path=_AGENT_REGISTRY,
        )

        self.assertEqual(
            agents.get("user-surface-smoker"),
            "needed",
            (
                "A ticket declaring a durable side-effect MUST have "
                "user-surface-smoker: needed in its agents map. "
                "When needed, the ticket-supervisor's done-gate sees a pending "
                "required phase, preventing the ticket from reaching done with "
                "the smoke check unrun or silently skipped (BP-1100f-5). "
                f"Current agents map: {agents!r}. "
                "Fix: add declares_side_effect parameter to _build_agents_map "
                "and include user-surface-smoker in all_needed when true."
            ),
        )

    def test_flow_change_order_also_has_smoker(self) -> None:
        # covers: BP-1100f-5
        """user-surface-smoker must also be in _FLOW_CHANGE_PHASE_ORDER.

        Flow-change tickets use an alternate phase ordering that puts documentation
        before coders. If user-surface-smoker is only in _CANONICAL_PHASE_ORDER
        but not in _FLOW_CHANGE_PHASE_ORDER, flow-change tickets with a declared
        side-effect would silently skip the smoke check (the non-canonical
        bucket places it at the end, potentially after commit).
        """
        self.assertIn(
            "user-surface-smoker",
            _gtfac._FLOW_CHANGE_PHASE_ORDER,
            (
                "user-surface-smoker must be in _FLOW_CHANGE_PHASE_ORDER so that "
                "flow-change tickets with a declared side-effect also route through "
                "the smoke check. Omitting it from this list would silently skip "
                "the check for flow-change tickets. "
                f"Current _FLOW_CHANGE_PHASE_ORDER: {_gtfac._FLOW_CHANGE_PHASE_ORDER!r}."
            ),
        )


if __name__ == "__main__":
    unittest.main()
