"""Tests for BO-2200d-1-i: Removing documentation-expert from the flow-change gates
leaves the other pre-coder gates intact.

These tests are RED before the implementation because:
  1. test_architect_review_still_injected_pre_coder:
       Checks for a 'surgical_removal_guard' section in guardrail_gates.yaml that
       formally declares the architect-review-retained invariant.  This section does
       not yet exist in the config — python-coder must add it.
       The behavioral sub-assertion (architect-review ordered before python-coder) is
       already satisfied by the BO-2200d-1 implementation but is included here as a
       regression guard.

  2. test_documentation_expert_never_double_injected:
       Checks for a 'surgical_removal_guard' section in guardrail_gates.yaml that
       formally declares the documentation-expert-absent invariant.  This section does
       not yet exist in the config — python-coder must add it.
       The behavioral sub-assertions (doc-expert absent from flow_change_gates lists;
       doc-expert appears exactly once in the resolved agents map for a doc-triggering
       flow-change pair) are already satisfied by the BO-2200d-1 implementation but
       are included here as regression guards.

Implementation target:
  - config/guardrail_gates.yaml — add a 'surgical_removal_guard' top-level section
      (n_location_rule: all) encoding the invariant that:
        * architect-review is present in all four flow_change_gates mandatory_agents lists
        * documentation-expert is absent from all four flow_change_gates mandatory_agents lists
        * documentation-expert appears exactly once in the computed agents map for any
          doc-triggering flow-change pair (via documentation_gates, post-coder)

AC source: docs/acceptance-criteria/build-orchestration/
           BO-2200-documentation-coverage-guarantee/BO-2200d-1-i.yaml
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
# flow-change gate slots.  After the BO-2200d-1 surgical removal,
# documentation-expert must be absent from ALL of them while architect-review
# remains present.
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
# test_architect_review_still_injected_pre_coder
# BO-2200d-1-i: architect-review remains injected and ordered before coder
# ---------------------------------------------------------------------------


class TestArchitectReviewStillInjectedPreCoder(unittest.TestCase):
    """BO-2200d-1-i: architect-review must still be injected and ordered
    before the coder for every flow-change pair after the surgical removal of
    documentation-expert.

    RED before implementation: guardrail_gates.yaml does not yet contain a
    'surgical_removal_guard' section formally encoding this invariant.
    python-coder must add this section to config/guardrail_gates.yaml.
    """

    def test_architect_review_still_injected_pre_coder(self) -> None:
        # covers: BO-2200d-1-i
        """architect-review must appear before python-coder in the computed agents map
        for a flow-change pair, AND guardrail_gates.yaml must contain a
        'surgical_removal_guard' section formally declaring the invariant.

        The test proceeds in two parts:

        Part 1 (config assertion — RED before implementation):
          Assert that guardrail_gates.yaml contains a top-level
          'surgical_removal_guard' key encoding the invariant that architect-review
          is retained in all flow_change_gates mandatory_agents lists.

        Part 2 (behavioral regression guard — currently passes):
          For code/contract_boundary (a representative flow-change pair),
          call _build_agents_map and assert architect-review appears before
          python-coder in the ordered result.
        """
        gates = _load_guardrail_config()

        # Part 1 — config-level enforcement (RED: section not yet present)
        guard = gates.get("surgical_removal_guard")
        self.assertIsNotNone(
            guard,
            "BO-2200d-1-i: guardrail_gates.yaml must contain a top-level "
            "'surgical_removal_guard' section that formally declares the invariant: "
            "architect-review is retained in all flow_change_gates mandatory_agents "
            "lists after the surgical removal of documentation-expert.\n\n"
            "python-coder must add this section to config/guardrail_gates.yaml "
            "(Implementation Notes: config_schema_fragment / surgical_removal_guard, "
            "n_location_rule: all).",
        )

        # Part 2 — behavioral regression guard (passes once BO-2200d-1 is implemented)
        result = _build_agents_map(
            "python-coder",
            change_targets=["code"],
            risk_surface="contract_boundary",
            guardrail_config_path=_GUARDRAIL_CONFIG,
            agent_registry_path=_AGENT_REGISTRY_PATH,
        )
        keys = list(result.keys())

        self.assertIn(
            "architect-review",
            keys,
            "architect-review must be present in the computed agents map for "
            "code/contract_boundary (a flow-change pair).",
        )
        self.assertIn(
            "python-coder",
            keys,
            "python-coder must be present in the computed agents map for "
            "code/contract_boundary.",
        )

        ar_idx = keys.index("architect-review")
        pc_idx = keys.index("python-coder")

        self.assertLess(
            ar_idx,
            pc_idx,
            f"BO-2200d-1-i: architect-review (index {ar_idx}) must appear BEFORE "
            f"python-coder (index {pc_idx}) for the code/contract_boundary "
            "flow-change pair.\n\n"
            f"Full map keys: {keys}",
        )


# ---------------------------------------------------------------------------
# test_documentation_expert_never_double_injected
# BO-2200d-1-i: doc-expert absent from flow_change_gates and appears exactly once
# ---------------------------------------------------------------------------


class TestDocumentationExpertNeverDoubleInjected(unittest.TestCase):
    """BO-2200d-1-i: documentation-expert must appear in no flow-change-gate
    mandatory_agents list, and must appear exactly once in the resolved agents
    map for a doc-triggering flow-change pair (no pre-coder + post-coder
    duplication).

    RED before implementation: guardrail_gates.yaml does not yet contain a
    'surgical_removal_guard' section formally encoding this invariant.
    python-coder must add this section to config/guardrail_gates.yaml.
    """

    def test_documentation_expert_never_double_injected(self) -> None:
        # covers: BO-2200d-1-i
        """documentation-expert must be absent from all flow_change_gates
        mandatory_agents lists AND appear exactly once in the computed agents map
        for a doc-triggering flow-change pair (schema/contract_boundary).

        The test proceeds in three parts:

        Part 1 (config assertion — RED before implementation):
          Assert that guardrail_gates.yaml contains a top-level
          'surgical_removal_guard' key encoding the invariant that
          documentation-expert is absent from all flow_change_gates lists.

        Part 2 (YAML structural regression guard — currently passes):
          For each of the four flow_change_gate pairs, assert that
          documentation-expert is absent from mandatory_agents.

        Part 3 (behavioral regression guard — currently passes):
          For schema/contract_boundary (a doc-triggering flow-change pair),
          call _build_agents_map and assert documentation-expert appears
          exactly once in the ordered result (no double-injection).
        """
        gates = _load_guardrail_config()

        # Part 1 — config-level enforcement (RED: section not yet present)
        guard = gates.get("surgical_removal_guard")
        self.assertIsNotNone(
            guard,
            "BO-2200d-1-i: guardrail_gates.yaml must contain a top-level "
            "'surgical_removal_guard' section that formally declares the invariant: "
            "documentation-expert is absent from all flow_change_gates "
            "mandatory_agents lists (so it is never injected twice — once pre-coder "
            "and once post-coder — for the same ticket).\n\n"
            "python-coder must add this section to config/guardrail_gates.yaml "
            "(Implementation Notes: config_schema_fragment / surgical_removal_guard, "
            "n_location_rule: all).",
        )

        # Part 2 — YAML structural check (passes once BO-2200d-1 YAML edit is done)
        flow_change_entries = gates.get("flow_change_gates", []) or []
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
            mandatory = entry_lookup.get((change_target, risk_surface), [])
            if "documentation-expert" in mandatory:
                violations.append(
                    f"  {change_target}/{risk_surface}: documentation-expert "
                    f"found in mandatory_agents={mandatory}"
                )

        self.assertEqual(
            violations,
            [],
            "BO-2200d-1-i: documentation-expert must be absent from all four "
            "flow_change_gates mandatory_agents lists.\n\n"
            "Current violations (documentation-expert still present):\n"
            + "\n".join(violations),
        )

        # Part 3 — behavioral double-injection check (passes once BO-2200d-1 code fix done)
        # schema/contract_boundary: is a flow-change pair AND schema is in
        # documentation_gates.change_target_triggers → doc-expert injected once via
        # documentation_gates (post-coder canonical order).  It must NOT be injected
        # again via the flow_change_gates mandatory_agents slot.
        result = _build_agents_map(
            "python-coder",
            change_targets=["schema"],
            risk_surface="contract_boundary",
            guardrail_config_path=_GUARDRAIL_CONFIG,
            agent_registry_path=_AGENT_REGISTRY_PATH,
        )
        keys = list(result.keys())
        count = keys.count("documentation-expert")

        self.assertEqual(
            count,
            1,
            f"BO-2200d-1-i: documentation-expert must appear exactly once in the "
            f"computed agents map for schema/contract_boundary (a doc-triggering "
            f"flow-change pair). Got {count} occurrence(s).\n\n"
            f"Full map keys: {keys}\n\n"
            "If count > 1: documentation-expert is being double-injected (via both "
            "flow_change_gates mandatory_agents AND documentation_gates). "
            "Fix: ensure documentation-expert is absent from flow_change_gates lists.",
        )


if __name__ == "__main__":
    unittest.main()
