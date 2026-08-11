"""
MODULE: test_bo_2200d_2_i
GOAL: RED tests for BO-2200d-2-i — multi-coder phase ordering (frontend-coder).
BUSINESS CONTEXT: When a documentation-required ticket includes more than one coder
    (e.g. both python-coder and frontend-coder), documentation-expert must be ordered
    after the LAST coder, and documentation-verifier must still run last before commit.
    Root cause: frontend-coder is absent from _CANONICAL_PHASE_ORDER, so it is inserted
    as a non-canonical agent just before commit (after documentation-expert/verifier),
    violating the AC.
ARCHITECTURE: Tests call _build_agents_map with frontend-coder as the assigned agent
    and a doc-triggering scenario (schema/contract_boundary) to produce a map where
    both frontend-coder and documentation-expert are needed. The phase ordering of the
    resulting dict is then asserted.

Both tests are RED before the fix because frontend-coder is absent from
_CANONICAL_PHASE_ORDER. It is inserted just before commit as a non-canonical agent,
placing it AFTER documentation-expert and documentation-verifier.

Target file to implement: scripts/ac_store/generate_ticket_from_ac.py
AC source: docs/acceptance-criteria/build-orchestration/
           BO-2200-documentation-coverage-guarantee/BO-2200d-2-i.yaml
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
# Canonical multi-coder doc-required scenario:
#
# - assigned_agent = "frontend-coder" → frontend-coder in all_needed.
# - change_targets = ["schema"] → documentation_gates fires → documentation-expert.
# - risk_surface = "contract_boundary" → risk_surface_triggers fires → documentation-expert.
# - documentation-verifier injected as documentation-expert companion.
# - files_touched contains a .tsx source file → ac-validator + ac-fulfillment-gate.
# - assigned_agent = "frontend-coder" → test-writer + test-runner injected (coder).
#
# This is the scenario where the ordering bug surfaces:
#   BROKEN: frontend-coder inserted before commit (non-canonical), AFTER documentation-expert.
#   FIXED:  frontend-coder at its canonical coder slot, BEFORE documentation-expert.
# ---------------------------------------------------------------------------

_FRONTEND_CHANGE_TARGETS = ["schema"]
_FRONTEND_RISK_SURFACE = "contract_boundary"
_FRONTEND_ASSIGNED_AGENT = "frontend-coder"
_FRONTEND_FILES_TOUCHED = ["scripts/ui/component.tsx"]


def _build_frontend_doc_required_map() -> dict[str, str]:
    """Build the agents map for a frontend-coder doc-required ticket."""
    return _build_agents_map(
        _FRONTEND_ASSIGNED_AGENT,
        change_targets=_FRONTEND_CHANGE_TARGETS,
        risk_surface=_FRONTEND_RISK_SURFACE,
        guardrail_config_path=_GUARDRAIL_CONFIG,
        agent_registry_path=_AGENT_REGISTRY_PATH,
        files_touched=_FRONTEND_FILES_TOUCHED,
    )


# ---------------------------------------------------------------------------
# TestDocExpertOrderedAfterLastCoder
# BO-2200d-2-i
# ---------------------------------------------------------------------------


class TestDocExpertOrderedAfterLastCoder(unittest.TestCase):
    """BO-2200d-2-i: documentation-expert is ordered after EVERY coder in the
    resolved agents map, not merely after the first.

    RED before implementation: frontend-coder is absent from _CANONICAL_PHASE_ORDER.
    The non-canonical insertion logic places frontend-coder just before commit (position ~10),
    AFTER documentation-expert (position ~6). So index(documentation-expert) < index(frontend-coder).
    This violates the AC: documentation-expert must follow the LAST coder.

    Fix: add frontend-coder to _CANONICAL_PHASE_ORDER adjacent to the other coders
    (python-coder, sql-coder) so that documentation-expert's canonical position remains
    after ALL coders.
    """

    def test_doc_expert_ordered_after_last_coder(self) -> None:
        # covers: BO-2200d-2-i
        """With frontend-coder as the assigned agent and a doc-triggering scenario,
        documentation-expert must appear at a higher map index than frontend-coder.

        The test uses schema/contract_boundary because both triggers fire:
          - schema is in documentation_gates.change_target_triggers
          - contract_boundary is in documentation_gates.risk_surface_triggers

        Red state (before fix): frontend-coder is not in _CANONICAL_PHASE_ORDER.
        The non-canonical insertion loop places it in the map just before commit.
        The resulting order includes: ..., documentation-expert, documentation-verifier,
        frontend-coder, commit, ... — frontend-coder appears AFTER documentation-expert,
        violating the 'after the last coder' invariant.

        Green state (after fix): frontend-coder is in _CANONICAL_PHASE_ORDER at the
        coder slot (between sql-coder and test-runner), before documentation-expert.
        index(documentation-expert) > index(frontend-coder).
        """
        result = _build_frontend_doc_required_map()
        keys = list(result.keys())

        self.assertIn(
            "frontend-coder",
            keys,
            "frontend-coder must be in the resolved agents map for the frontend "
            "doc-required scenario.\n"
            f"Full map keys: {keys}",
        )
        self.assertIn(
            "documentation-expert",
            keys,
            "documentation-expert must be in the resolved agents map for "
            "schema/contract_boundary (both triggers fire).\n"
            f"Full map keys: {keys}",
        )

        fc_idx = keys.index("frontend-coder")
        de_idx = keys.index("documentation-expert")

        self.assertGreater(
            de_idx,
            fc_idx,
            f"BO-2200d-2-i: documentation-expert (index {de_idx}) must appear AFTER "
            f"frontend-coder (index {fc_idx}) in the resolved phase order.\n\n"
            f"Current broken order: frontend-coder is inserted as a non-canonical agent "
            f"just before commit (after documentation-expert). The fix: add frontend-coder "
            f"to _CANONICAL_PHASE_ORDER at the coder slot before documentation-expert.\n\n"
            f"Full map keys: {keys}",
        )


# ---------------------------------------------------------------------------
# TestVerifierAfterDocExpertAndLastBeforeCommitMultiCoder
# BO-2200d-2-i
# ---------------------------------------------------------------------------


class TestVerifierAfterDocExpertAndLastBeforeCommitMultiCoder(unittest.TestCase):
    """BO-2200d-2-i: documentation-verifier runs after documentation-expert and
    is the last 'needed' phase before commit in the multi-coder case.

    RED before implementation: when frontend-coder is inserted just before commit
    as a non-canonical agent, the needed phase order becomes:
        ..., documentation-verifier, frontend-coder, commit, ...
    documentation-verifier is no longer adjacent to commit (gap = 2, not 1).

    Fix: once frontend-coder is in _CANONICAL_PHASE_ORDER (before documentation-expert),
    the verifier position is restored: documentation-verifier → commit (gap = 1).
    """

    def test_verifier_after_doc_expert_and_last_before_commit_multi_coder(self) -> None:
        # covers: BO-2200d-2-i
        """documentation-verifier must:
        1. appear after documentation-expert in the resolved needed-phases list;
        2. be the last 'needed' phase immediately before commit (commit_idx - dv_idx == 1).

        The test uses the same frontend-coder + schema/contract_boundary scenario
        as test_doc_expert_ordered_after_last_coder to produce the full phase set
        including documentation-expert and documentation-verifier.

        Red state: needed phase order contains:
            ..., documentation-verifier, frontend-coder, commit
        commit_idx - dv_idx == 2 (not 1) → assertion fails.

        Green state (after fix): frontend-coder is canonical (before doc-expert);
        needed phase order becomes:
            ..., documentation-verifier, commit
        commit_idx - dv_idx == 1 → assertion passes.
        """
        result = _build_frontend_doc_required_map()
        needed_keys = [k for k, v in result.items() if v == "needed"]

        self.assertIn(
            "documentation-verifier",
            needed_keys,
            "documentation-verifier must be a 'needed' phase for a frontend "
            "doc-required ticket (schema/contract_boundary).\n"
            f"Full needed phases: {needed_keys}",
        )
        self.assertIn(
            "documentation-expert",
            needed_keys,
            "documentation-expert must be a 'needed' phase.\n"
            f"Full needed phases: {needed_keys}",
        )
        self.assertIn(
            "commit",
            needed_keys,
            "commit must be a 'needed' phase.\n"
            f"Full needed phases: {needed_keys}",
        )

        dv_idx = needed_keys.index("documentation-verifier")
        de_idx = needed_keys.index("documentation-expert")
        commit_idx = needed_keys.index("commit")

        self.assertGreater(
            dv_idx,
            de_idx,
            f"BO-2200d-2-i: documentation-verifier (needed-index {dv_idx}) must "
            f"appear AFTER documentation-expert (needed-index {de_idx}).\n"
            f"Full needed phases: {needed_keys}",
        )

        self.assertEqual(
            commit_idx - dv_idx,
            1,
            f"BO-2200d-2-i: documentation-verifier must be the LAST needed phase "
            f"immediately before commit (commit_idx - dv_idx must equal 1).\n\n"
            f"Current needed phase order: {needed_keys}\n\n"
            f"documentation-verifier is at needed-index {dv_idx}; "
            f"commit is at needed-index {commit_idx}. "
            f"Gap = {commit_idx - dv_idx} (expected 1).\n\n"
            f"Phases between documentation-verifier and commit "
            f"(must be empty after fix): {needed_keys[dv_idx + 1:commit_idx]}\n\n"
            f"Fix: add frontend-coder to _CANONICAL_PHASE_ORDER at the coder slot "
            f"(before documentation-expert) in "
            f"scripts/ac_store/generate_ticket_from_ac.py.",
        )


if __name__ == "__main__":
    unittest.main()
