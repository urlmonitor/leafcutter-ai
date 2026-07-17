"""
Tests for BO-2200d-1: documentation-expert is added via the post-coder
per-surface (canonical-order) path, NOT via the pre-coder flow-change gate slot.

These tests are RED before the implementation because:
  1. test_documentation_expert_added_via_post_coder_path:
       Currently documentation-expert is injected via _FLOW_CHANGE_PHASE_ORDER
       which places it BEFORE python-coder.  The AC requires it to appear AFTER
       the coder (canonical order).
  2. test_documentation_expert_absent_from_flow_change_gates:
       Currently all four flow_change_gates entries (code|schema x
       contract_boundary|safety) list documentation-expert in mandatory_agents.
       The AC requires it to be absent from those lists.
  3. test_architect_review_retained_in_flow_change_gates:
       Guard test: architect-review must remain in all four flow_change_gates
       mandatory_agents lists after the surgical removal of documentation-expert.
       NOTE: this test passes immediately (architect-review already present)
       because it guards against accidental removal during the fix.

Implementation targets:
  - config/guardrail_gates.yaml  — remove documentation-expert from the four
      flow_change_gates mandatory_agents lists (code|schema x
      contract_boundary|safety, ~lines 266-327).
  - scripts/ac_store/generate_ticket_from_ac.py  — ensure documentation-expert
      is ordered via _CANONICAL_PHASE_ORDER (after the coder) even for
      flow-change pairs, not via _FLOW_CHANGE_PHASE_ORDER (before the coder).

AC source: docs/acceptance-criteria/build-orchestration/
           BO-2200-documentation-coverage-guarantee/BO-2200d-1.yaml
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from generate_ticket_from_ac import _build_agents_map  # noqa: E402

_GUARDRAIL_CONFIG = _REPO_ROOT / "config" / "guardrail_gates.yaml"
_AGENT_REGISTRY_PATH = _REPO_ROOT / "config" / "agent_registry.json"

# The four (change_target, risk_surface) pairs that constitute the pre-coder
# flow-change gate slots.  documentation-expert must be absent from ALL of them.
_FLOW_CHANGE_PAIRS = [
    ("code", "contract_boundary"),
    ("code", "safety"),
    ("schema", "contract_boundary"),
    ("schema", "safety"),
]


def _load_guardrail_config() -> dict:
    """Load guardrail_gates.yaml from the repo config directory."""
    with open(_GUARDRAIL_CONFIG, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


# ---------------------------------------------------------------------------
# test_documentation_expert_added_via_post_coder_path
# BO-2200d-1: doc-expert ordered via canonical path (after coder)
# ---------------------------------------------------------------------------


class TestDocumentationExpertPostCoderPath(unittest.TestCase):
    """BO-2200d-1: For a doc-triggering flow-change ticket (schema/contract_boundary),
    documentation-expert must appear AFTER python-coder in the computed agents map.

    RED before implementation: currently documentation-expert is injected via
    _FLOW_CHANGE_PHASE_ORDER which places it BEFORE python-coder (at the front of the
    flow-change gate slot, immediately after architect-review).  The fix must:
      1. Remove documentation-expert from flow_change_gates mandatory_agents in the YAML.
      2. Ensure the phase ordering for documentation-expert uses _CANONICAL_PHASE_ORDER
         (which places it after the coder) even when the ticket is a flow-change pair.
    """

    def test_documentation_expert_added_via_post_coder_path(self) -> None:
        # covers: BO-2200d-1
        """For a doc-triggering flow-change ticket (schema/contract_boundary),
        documentation-expert must appear AFTER python-coder in the computed agents map.

        The test uses schema/contract_boundary because:
          - schema/contract_boundary is a flow-change pair (listed in flow_change_gates).
          - schema is in documentation_gates.change_target_triggers, so doc-expert is
            injected by the documentation_gates policy.

        RED state: currently _build_agents_map uses _FLOW_CHANGE_PHASE_ORDER for
        flow-change pairs, which places documentation-expert at index 1 (after
        architect-review, BEFORE python-coder).

        Green state (after fix): documentation-expert is ordered via
        _CANONICAL_PHASE_ORDER and appears AFTER python-coder.
        """
        result = _build_agents_map(
            "python-coder",
            change_targets=["schema"],
            risk_surface="contract_boundary",
            guardrail_config_path=_GUARDRAIL_CONFIG,
            agent_registry_path=_AGENT_REGISTRY_PATH,
        )
        keys = list(result.keys())

        self.assertIn(
            "documentation-expert",
            keys,
            "documentation-expert must be in the agents map for schema/contract_boundary "
            "(a doc-triggering flow-change pair).\n"
            f"Full map keys: {keys}",
        )
        self.assertIn(
            "python-coder",
            keys,
            "python-coder must be in the agents map for schema/contract_boundary.\n"
            f"Full map keys: {keys}",
        )

        de_idx = keys.index("documentation-expert")
        pc_idx = keys.index("python-coder")

        self.assertGreater(
            de_idx,
            pc_idx,
            f"BO-2200d-1: documentation-expert (index {de_idx}) must appear AFTER "
            f"python-coder (index {pc_idx}) for the schema/contract_boundary "
            "flow-change pair.\n\n"
            "This test is RED because documentation-expert is currently ordered via "
            "_FLOW_CHANGE_PHASE_ORDER which places it BEFORE python-coder.\n\n"
            "Fix: ensure documentation-expert is ordered via _CANONICAL_PHASE_ORDER "
            "(post-coder position) and is NOT injected via the flow-change gate slot.\n\n"
            f"Full map keys: {keys}",
        )


# ---------------------------------------------------------------------------
# test_documentation_expert_absent_from_flow_change_gates
# BO-2200d-1: doc-expert absent from all four flow_change_gates mandatory_agents
# ---------------------------------------------------------------------------


class TestDocumentationExpertAbsentFromFlowChangeGates(unittest.TestCase):
    """BO-2200d-1: documentation-expert must be absent from all four
    flow_change_gates mandatory_agents lists in guardrail_gates.yaml.

    RED before implementation: the four entries (code|schema x
    contract_boundary|safety) each list documentation-expert in mandatory_agents.
    """

    def test_documentation_expert_absent_from_flow_change_gates(self) -> None:
        # covers: BO-2200d-1
        """documentation-expert must not appear in any of the four
        flow_change_gates mandatory_agents lists:
          - code / contract_boundary
          - code / safety
          - schema / contract_boundary
          - schema / safety

        RED state: all four entries currently list documentation-expert in
        mandatory_agents.

        Green state (after fix): documentation-expert has been surgically
        removed from all four mandatory_agents lists and is injected via the
        per-surface documentation_gates path instead.
        """
        gates = _load_guardrail_config()
        flow_change_entries = gates.get("flow_change_gates", []) or []

        # Build a lookup: (change_target, risk_surface) -> mandatory_agents
        entry_lookup: dict[tuple[str, str], list[str]] = {}
        for entry in flow_change_entries:
            if not isinstance(entry, dict):
                continue
            ct = entry.get("change_target", "")
            rs = entry.get("risk_surface", "")
            mandatory = entry.get("mandatory_agents") or []
            entry_lookup[(ct, rs)] = mandatory

        violations: list[str] = []
        for change_target, risk_surface in _FLOW_CHANGE_PAIRS:
            pair_key = (change_target, risk_surface)
            if pair_key not in entry_lookup:
                # Entry not found — the pair may have been removed or not yet added.
                # This is acceptable for test purposes; the "absent" requirement is met
                # trivially when the entry itself does not exist.
                continue
            mandatory = entry_lookup[pair_key]
            if "documentation-expert" in mandatory:
                violations.append(
                    f"  {change_target}/{risk_surface}: documentation-expert "
                    f"found in mandatory_agents={mandatory}"
                )

        self.assertEqual(
            violations,
            [],
            "BO-2200d-1: documentation-expert must be absent from all four "
            "flow_change_gates mandatory_agents lists.\n\n"
            "Current violations (documentation-expert still present):\n"
            + "\n".join(violations)
            + "\n\nFix: remove documentation-expert from mandatory_agents in "
            "config/guardrail_gates.yaml for all four flow_change_gates entries "
            "(code/contract_boundary, code/safety, schema/contract_boundary, "
            "schema/safety).\n\n"
            "documentation-expert will continue to be injected via "
            "documentation_gates.change_target_triggers — removing it from "
            "flow_change_gates does NOT remove it from generated tickets that "
            "cover schema, ui, pipeline, or docs change_targets.",
        )


# ---------------------------------------------------------------------------
# test_architect_review_retained_in_flow_change_gates
# BO-2200d-1: architect-review must remain in all four flow_change_gates lists
# ---------------------------------------------------------------------------


class TestArchitectReviewRetainedInFlowChangeGates(unittest.TestCase):
    """BO-2200d-1: architect-review must remain in all four flow_change_gates
    mandatory_agents lists after the surgical removal of documentation-expert.

    NOTE: This test passes immediately (architect-review is already present)
    because it guards against accidental removal during the implementation.
    The overall test file is RED due to the two tests above.
    """

    def test_architect_review_retained_in_flow_change_gates(self) -> None:
        # covers: BO-2200d-1
        """architect-review must be present in all four flow_change_gates
        mandatory_agents lists:
          - code / contract_boundary
          - code / safety
          - schema / contract_boundary
          - schema / safety

        The AC specifies: 'the removal of documentation-expert is surgical and
        does not remove other pre-coder gates.'  architect-review is the primary
        pre-coder gate that must remain.

        This guard test ensures that the fix only removes documentation-expert
        and does not accidentally drop architect-review from the mandatory_agents
        lists.

        NOTE: This test passes immediately (before the fix) because architect-review
        is already present in all four entries.  The overall test suite is RED due
        to the other two tests in this module.
        """
        gates = _load_guardrail_config()
        flow_change_entries = gates.get("flow_change_gates", []) or []

        # Build a lookup: (change_target, risk_surface) -> mandatory_agents
        entry_lookup: dict[tuple[str, str], list[str]] = {}
        for entry in flow_change_entries:
            if not isinstance(entry, dict):
                continue
            ct = entry.get("change_target", "")
            rs = entry.get("risk_surface", "")
            mandatory = entry.get("mandatory_agents") or []
            entry_lookup[(ct, rs)] = mandatory

        missing: list[str] = []
        for change_target, risk_surface in _FLOW_CHANGE_PAIRS:
            pair_key = (change_target, risk_surface)
            if pair_key not in entry_lookup:
                missing.append(
                    f"  {change_target}/{risk_surface}: flow_change_gates entry not found"
                )
                continue
            mandatory = entry_lookup[pair_key]
            if "architect-review" not in mandatory:
                missing.append(
                    f"  {change_target}/{risk_surface}: architect-review absent "
                    f"from mandatory_agents={mandatory}"
                )

        self.assertEqual(
            missing,
            [],
            "BO-2200d-1: architect-review must be present in all four "
            "flow_change_gates mandatory_agents lists after the surgical removal "
            "of documentation-expert.\n\n"
            "Missing or absent entries:\n"
            + "\n".join(missing)
            + "\n\nFix: ensure that removing documentation-expert from the four "
            "mandatory_agents lists does NOT also remove architect-review.",
        )


if __name__ == "__main__":
    unittest.main()
