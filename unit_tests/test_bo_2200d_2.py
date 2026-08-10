"""
Tests for BO-2200d-2: On a doc-required ticket, documentation-expert runs after
python-coder and test-runner, and documentation-verifier is the last phase before
commit.

Test 1 — test_doc_expert_ordered_after_coder_and_test_runner:
  Passes immediately because _CANONICAL_PHASE_ORDER already places
  documentation-expert (index 5) after python-coder (index 2) and test-runner
  (index 4) — a consequence of the BO-2200d-1 fix.  Retained as a regression
  guard; flagged "passes immediately — may be under-specified" in red_baseline.

Test 2 — test_verifier_is_last_phase_before_commit:
  RED before implementation.  Currently _CANONICAL_PHASE_ORDER places
  documentation-verifier at index 6, while pr-reviewer (7), ac-validator (8),
  and ac-fulfillment-gate (9) all precede commit (10).  For a realistic
  doc-required ticket (schema/contract_boundary with a .py file in
  files_touched), the last needed phase before commit is ac-fulfillment-gate,
  not documentation-verifier.

Implementation target:
  scripts/ac_store/generate_ticket_from_ac.py — reorder _CANONICAL_PHASE_ORDER
  so that documentation-verifier immediately precedes commit (position 10 out of
  12), after pr-reviewer, ac-validator, and ac-fulfillment-gate.

AC source: docs/acceptance-criteria/build-orchestration/
           BO-2200-documentation-coverage-guarantee/BO-2200d-2.yaml
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from generate_ticket_from_ac import _build_agents_map  # noqa: E402

_GUARDRAIL_CONFIG = _REPO_ROOT / "config" / "guardrail_gates.yaml"
_AGENT_REGISTRY_PATH = _REPO_ROOT / "config" / "agent_registry.json"

# ---------------------------------------------------------------------------
# Canonical doc-required scenario
#
# schema/contract_boundary + python-coder + a .py file in files_touched is the
# most realistic and strictest test case for this AC:
#
#   - "schema" is in documentation_gates.change_target_triggers  → documentation-expert
#   - "contract_boundary" is in documentation_gates.risk_surface_triggers  → documentation-expert
#   - documentation-verifier is injected as the companion of documentation-expert
#   - pr-reviewer comes from schema/contract_boundary guardrail gates
#   - ac-validator and ac-fulfillment-gate are injected because the file is .py
#
# Together these produce the maximum set of phases between documentation-verifier
# and commit in the current implementation, making test 2 maximally red.
# ---------------------------------------------------------------------------

_DOC_REQUIRED_CHANGE_TARGETS = ["schema"]
_DOC_REQUIRED_RISK_SURFACE = "contract_boundary"
_DOC_REQUIRED_ASSIGNED_AGENT = "python-coder"
_DOC_REQUIRED_FILES_TOUCHED = ["scripts/ac_store/generate_ticket_from_ac.py"]


def _build_doc_required_map() -> dict[str, str]:
    """Return the resolved agents map for a canonical doc-required ticket."""
    return _build_agents_map(
        _DOC_REQUIRED_ASSIGNED_AGENT,
        change_targets=_DOC_REQUIRED_CHANGE_TARGETS,
        risk_surface=_DOC_REQUIRED_RISK_SURFACE,
        guardrail_config_path=_GUARDRAIL_CONFIG,
        agent_registry_path=_AGENT_REGISTRY_PATH,
        files_touched=_DOC_REQUIRED_FILES_TOUCHED,
    )


# ---------------------------------------------------------------------------
# Test 1 — documentation-expert after python-coder and test-runner
# (passes immediately; kept as regression guard)
# ---------------------------------------------------------------------------


class TestDocExpertOrderedAfterCoderAndTestRunner(unittest.TestCase):
    """BO-2200d-2: documentation-expert must appear AFTER python-coder and
    test-runner in the resolved agents map for a doc-required ticket.

    NOTE: This test passes immediately (before python-coder implements BO-2200d-2)
    because the BO-2200d-1 fix already ordered documentation-expert via
    _CANONICAL_PHASE_ORDER (post-coder position).  It is retained as a regression
    guard; the primary red signal for this ticket is test 2.
    """

    def test_doc_expert_ordered_after_coder_and_test_runner(self) -> None:
        # covers: BO-2200d-2
        """For a doc-required schema/contract_boundary ticket, documentation-expert
        must appear at a higher index than both python-coder and test-runner in the
        resolved agents map.

        The scenario uses schema/contract_boundary because:
          - schema is in documentation_gates.change_target_triggers → doc-expert injected
          - contract_boundary is in documentation_gates.risk_surface_triggers → doc-expert injected

        Red state (before BO-2200d-1): documentation-expert was ordered via
        _FLOW_CHANGE_PHASE_ORDER which placed it BEFORE python-coder.  That
        regression is fixed by BO-2200d-1; this test guards against re-introducing it.

        Green state (current, and after BO-2200d-2): documentation-expert appears
        at canonical index 5, after python-coder (index 2) and test-runner (index 4).
        """
        result = _build_doc_required_map()
        keys = list(result.keys())

        self.assertIn(
            "documentation-expert",
            keys,
            "documentation-expert must be in the resolved agents map for "
            "schema/contract_boundary (a doc-triggering pair).\n"
            f"Full map keys: {keys}",
        )
        self.assertIn(
            "python-coder",
            keys,
            f"python-coder must be in the resolved agents map.\n"
            f"Full map keys: {keys}",
        )
        self.assertIn(
            "test-runner",
            keys,
            f"test-runner must be in the resolved agents map.\n"
            f"Full map keys: {keys}",
        )

        de_idx = keys.index("documentation-expert")
        pc_idx = keys.index("python-coder")
        tr_idx = keys.index("test-runner")

        self.assertGreater(
            de_idx,
            pc_idx,
            f"BO-2200d-2: documentation-expert (index {de_idx}) must appear AFTER "
            f"python-coder (index {pc_idx}) in the resolved phase order.\n"
            f"Full map keys: {keys}",
        )
        self.assertGreater(
            de_idx,
            tr_idx,
            f"BO-2200d-2: documentation-expert (index {de_idx}) must appear AFTER "
            f"test-runner (index {tr_idx}) in the resolved phase order.\n"
            f"Full map keys: {keys}",
        )


# ---------------------------------------------------------------------------
# Test 2 — documentation-verifier is the LAST needed phase before commit
# (RED before implementation)
# ---------------------------------------------------------------------------


class TestVerifierIsLastPhaseBeforeCommit(unittest.TestCase):
    """BO-2200d-2: documentation-verifier must be the last 'needed' phase before
    the 'commit' phase in the resolved agents map for a doc-required ticket.

    RED before implementation: the current _CANONICAL_PHASE_ORDER has
    documentation-verifier at index 6 while pr-reviewer (7), ac-validator (8),
    and ac-fulfillment-gate (9) all precede commit (10).  For a realistic
    schema/contract_boundary ticket with a .py file, the last needed phase before
    commit is ac-fulfillment-gate — NOT documentation-verifier.

    Fix: reorder _CANONICAL_PHASE_ORDER so that documentation-verifier appears
    immediately before commit (at position 10 in the new ordering), after
    pr-reviewer, ac-validator, and ac-fulfillment-gate.
    """

    def test_verifier_is_last_phase_before_commit(self) -> None:
        # covers: BO-2200d-2
        """documentation-verifier must be the last 'needed' phase immediately
        before the 'commit' phase in the resolved agents map.

        The test uses schema/contract_boundary with a .py file in files_touched
        so that ac-validator and ac-fulfillment-gate are also injected — this is
        the most realistic and strictest scenario for this constraint.

        Red state (current): the needed phase order is approximately:
          ..., documentation-verifier, pr-reviewer, ac-validator,
          ac-fulfillment-gate, commit, ...
        Phases between documentation-verifier and commit: at least pr-reviewer.
        commit_idx - dv_idx > 1 → assertion fails.

        Green state (after fix): the needed phase order becomes:
          ..., pr-reviewer, ac-validator, ac-fulfillment-gate,
          documentation-verifier, commit, ...
        Exactly one phase separates documentation-verifier and commit (none —
        they are adjacent), so commit_idx - dv_idx == 1.
        """
        result = _build_doc_required_map()

        # Only consider 'needed' phases.  not_needed agents are excluded from
        # the resolved phase list by definition.
        needed_keys = [k for k, v in result.items() if v == "needed"]

        self.assertIn(
            "documentation-verifier",
            needed_keys,
            "documentation-verifier must be a 'needed' phase for a doc-required "
            "schema/contract_boundary ticket.\n"
            f"Full map: {result}",
        )
        self.assertIn(
            "commit",
            needed_keys,
            "commit must be a 'needed' phase in the resolved agents map.\n"
            f"Full map: {result}",
        )

        commit_idx = needed_keys.index("commit")
        dv_idx = needed_keys.index("documentation-verifier")

        self.assertEqual(
            commit_idx - dv_idx,
            1,
            f"BO-2200d-2: documentation-verifier must be the LAST needed phase "
            f"immediately before commit (commit_idx - dv_idx must equal 1).\n\n"
            f"Current needed phase order: {needed_keys}\n\n"
            f"documentation-verifier is at needed-index {dv_idx}; "
            f"commit is at needed-index {commit_idx}. "
            f"Gap = {commit_idx - dv_idx} (expected 1).\n\n"
            f"Phases between documentation-verifier and commit "
            f"(must be empty after fix): {needed_keys[dv_idx + 1:commit_idx]}\n\n"
            f"Fix: reorder _CANONICAL_PHASE_ORDER in "
            f"scripts/ac_store/generate_ticket_from_ac.py so that "
            f"documentation-verifier appears at the position immediately before "
            f"'commit' (after pr-reviewer, ac-validator, and ac-fulfillment-gate).",
        )


if __name__ == "__main__":
    unittest.main()
