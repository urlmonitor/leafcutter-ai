"""
MODULE: test_bo_2200b_1
GOAL: Verify AC BO-2200b-1 — a documentation-verifier phase agent is registered
      in config/agent_registry.json at priority 11.9 with conditional:true and
      signoff capability, and sorts after documentation-expert and before commit.
TICKET: tickets/00_inbox/epics/EPIC-DocumentationCoverageGuarantee/08_TICKET-20260715-BO-2200b-1.md
COVERS: BO-2200b-1
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_REGISTRY_PATH = _REPO_ROOT / "config" / "agent_registry.json"

_AGENT_ID = "documentation-verifier"
_EXPECTED_PRIORITY = 11.9


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_registry() -> dict:
    """Load and parse config/agent_registry.json."""
    assert _REGISTRY_PATH.exists(), f"agent_registry.json not found at {_REGISTRY_PATH}"
    with _REGISTRY_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _find_agent(registry: dict, agent_id: str) -> dict:
    """Return the registry entry for agent_id, or raise AssertionError via assert."""
    agents = registry.get("agents", [])
    for entry in agents:
        if entry.get("id") == agent_id:
            return entry
    available = [e.get("id") for e in agents]
    # Use assert (not raise) to avoid TRY003: long messages in raise statements.
    assert agent_id in available, (
        f"Agent '{agent_id}' not found in agent_registry.json. "
        f"Available IDs: {available}"
    )
    return {}  # unreachable — assert above always fails when we reach this point


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDocumentationVerifierAtPriority(unittest.TestCase):
    """AC BO-2200b-1: documentation-verifier phase registered at priority 11.9."""

    def setUp(self):
        self.registry = _load_registry()

    def test_documentation_verifier_registered_at_priority_11_9(self):
        # covers: BO-2200b-1
        """config/agent_registry.json must contain a documentation-verifier entry
        with priority 11.9, conditional:true, is_ticket_phase:true, and
        'signoff' in skills_used.

        Implementation required: python-coder must add a 'documentation-verifier'
        entry to config/agent_registry.json satisfying all four properties above.
        Until that entry exists this test will fail with AssertionError.
        """
        entry = _find_agent(self.registry, _AGENT_ID)

        # --- priority must be exactly 11.9 ---
        self.assertEqual(
            entry.get("priority"),
            _EXPECTED_PRIORITY,
            f"Expected documentation-verifier priority={_EXPECTED_PRIORITY!r}, "
            f"got {entry.get('priority')!r}",
        )

        # --- conditional must be True ---
        self.assertIs(
            entry.get("conditional"),
            True,
            f"Expected documentation-verifier 'conditional': true, "
            f"got {entry.get('conditional')!r}",
        )

        # --- is_ticket_phase must be True ---
        self.assertIs(
            entry.get("is_ticket_phase"),
            True,
            f"Expected documentation-verifier 'is_ticket_phase': true, "
            f"got {entry.get('is_ticket_phase')!r}",
        )

        # --- signoff capability: 'signoff' in skills_used ---
        skills_used = entry.get("skills_used", [])
        self.assertIn(
            "signoff",
            skills_used,
            f"Expected 'signoff' in documentation-verifier skills_used, "
            f"got skills_used={skills_used!r}",
        )

    def test_documentation_verifier_sorts_after_doc_expert_before_commit(self):
        # covers: BO-2200b-1
        """In the resolved phase order (sorted by priority), documentation-verifier
        must appear AFTER documentation-expert and BEFORE commit.

        Concretely: priority 11.9 is between documentation-expert (10) and commit (12).
        Implementation required: the entry does not yet exist; this test is red until
        python-coder registers documentation-verifier at priority 11.9.
        """
        agents = self.registry.get("agents", [])

        # Collect only phase agents that carry a numeric priority
        phase_agents = [
            a for a in agents
            if a.get("is_ticket_phase") and isinstance(a.get("priority"), (int, float))
        ]
        sorted_agents = sorted(phase_agents, key=lambda a: a["priority"])
        sorted_ids = [a["id"] for a in sorted_agents]

        # All three anchor agents must be present for the ordering to be meaningful
        self.assertIn(
            _AGENT_ID,
            sorted_ids,
            f"'documentation-verifier' not found among is_ticket_phase agents with "
            f"numeric priorities. Present phase agents: {sorted_ids}",
        )
        self.assertIn(
            "documentation-expert",
            sorted_ids,
            f"'documentation-expert' not found among phase agents with priorities: "
            f"{sorted_ids}",
        )
        self.assertIn(
            "commit",
            sorted_ids,
            f"'commit' not found among phase agents with priorities: {sorted_ids}",
        )

        dv_idx = sorted_ids.index(_AGENT_ID)
        de_idx = sorted_ids.index("documentation-expert")
        commit_idx = sorted_ids.index("commit")

        self.assertGreater(
            dv_idx,
            de_idx,
            f"documentation-verifier (idx={dv_idx}) must sort AFTER "
            f"documentation-expert (idx={de_idx}). "
            f"Resolved order: {sorted_ids}",
        )
        self.assertLess(
            dv_idx,
            commit_idx,
            f"documentation-verifier (idx={dv_idx}) must sort BEFORE "
            f"commit (idx={commit_idx}). "
            f"Resolved order: {sorted_ids}",
        )


if __name__ == "__main__":
    unittest.main()
