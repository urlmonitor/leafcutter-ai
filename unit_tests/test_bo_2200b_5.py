"""
MODULE: test_bo_2200b_5
GOAL: RED test stubs for AC BO-2200b-5 — Once triggered, the writer and
      verifier cannot be suppressed by a not_needed override.

      When a ticket's classification triggers a documentation demand (injecting
      documentation-expert and documentation-verifier), a subsequent attempt to
      set either agent's status to not_needed via not_needed_overrides must NOT
      take effect — both agents must remain 'needed'.

      This non-suppressibility must be enforced by the same mandatory-agent
      protection mechanism that guards test-writer and test-runner (BO-550-1-i):
      a _DOC_MANDATORY protected set (or equivalent) inside _build_agents_map
      whose members cannot be discarded once the trigger fires.

TICKET: tickets/00_inbox/epics/EPIC-DocumentationCoverageGuarantee/
        14_TICKET-20260715-BO-2200b-5.md
COVERS: BO-2200b-5
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from generate_ticket_from_ac import _build_agents_map  # noqa: E402

# ---------------------------------------------------------------------------
# Paths to config fixtures used by _build_agents_map
# ---------------------------------------------------------------------------

_GUARDRAIL_CONFIG = _REPO_ROOT / "config" / "guardrail_gates.yaml"
_AGENT_REGISTRY = _REPO_ROOT / "config" / "agent_registry.json"


# ---------------------------------------------------------------------------
# Minimal AC record helpers
# ---------------------------------------------------------------------------


def _make_triggering_ac() -> dict:
    """Minimal AC record whose change_target='ui' triggers documentation-expert
    via documentation_gates.change_target_triggers (BO-2200a-1).

    'ui' is present in documentation_gates.change_target_triggers in
    config/guardrail_gates.yaml — the trigger fires cleanly via change_target.
    risk_surface='production' is not in the guardrail keys, so no guardrail
    agents are added from the ui/production pair (the doc trigger fires purely
    from change_target_triggers).  This mirrors the pattern used in
    test_bo_2200b_4.py to keep the triggering scenario consistent across tests.
    """
    return {
        "id": "TEST-BO-2200b-5-OVERRIDE",
        "title": "UI surface change — override suppression test",
        "assigned_agent": "python-coder",
        "change_target": "ui",
        "risk_surface": "production",
        "estimated_complexity": "M",
        "criteria": (
            "Given a UI-surface AC,\n"
            "When an override attempts to strip documentation agents,\n"
            "Then both documentation-expert and documentation-verifier remain needed."
        ),
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNotNeededOverrideDoesNotStripDocAgents(unittest.TestCase):
    """AC BO-2200b-5: not_needed_overrides must not strip documentation-expert
    or documentation-verifier once the documentation trigger has fired."""

    def test_not_needed_override_does_not_strip_doc_expert_or_verifier(self):
        # covers: BO-2200b-5
        """AC BO-2200b-5 (core behaviour): After the documentation trigger fires
        (change_target='ui' is in documentation_gates.change_target_triggers),
        passing not_needed_overrides={'documentation-expert': 'not_needed',
        'documentation-verifier': 'not_needed'} must leave BOTH agents as
        'needed' in the computed agents map.

        The computed trigger chain wins — exactly as test-writer and test-runner
        cannot be stripped by not_needed_overrides when they are auto-injected by
        the presence of a production_code agent (BO-550-1-i).

        Implementation required: python-coder must extend _build_agents_map in
        scripts/ac_store/generate_ticket_from_ac.py to protect documentation-expert
        and documentation-verifier from not_needed_overrides when the trigger fires,
        analogous to the existing _TDD_MANDATORY frozenset.

        Until that implementation lands, the current code honours the override and
        sets both agents to 'not_needed', causing these assertions to fail with
        AssertionError (expected 'needed', got 'not_needed').
        """
        ac = _make_triggering_ac()
        override_attempt = {
            "documentation-expert": "not_needed",
            "documentation-verifier": "not_needed",
        }
        agents_map = _build_agents_map(
            assigned_agent=ac["assigned_agent"],
            change_targets=[ac["change_target"]],
            risk_surface=ac["risk_surface"],
            not_needed_overrides=override_attempt,
            guardrail_config_path=_GUARDRAIL_CONFIG,
            agent_registry_path=_AGENT_REGISTRY,
        )

        # --- documentation-expert must remain 'needed' despite the override ---
        self.assertIn(
            "documentation-expert",
            agents_map,
            "Expected 'documentation-expert' to appear in agents map even after "
            f"a not_needed override, but map only contains: {list(agents_map.keys())}",
        )
        self.assertEqual(
            agents_map.get("documentation-expert"),
            "needed",
            "Expected documentation-expert='needed' (override must be suppressed by "
            "the mandatory-agent protection), but the override took effect: "
            f"got {agents_map.get('documentation-expert')!r}. "
            "Implementation required: add documentation-expert to a doc-mandatory "
            "protected set in _build_agents_map (BO-2200b-5).",
        )

        # --- documentation-verifier must remain 'needed' despite the override ---
        self.assertIn(
            "documentation-verifier",
            agents_map,
            "Expected 'documentation-verifier' to appear in agents map even after "
            f"a not_needed override, but map only contains: {list(agents_map.keys())}",
        )
        self.assertEqual(
            agents_map.get("documentation-verifier"),
            "needed",
            "Expected documentation-verifier='needed' (override must be suppressed by "
            "the mandatory-agent protection), but the override took effect: "
            f"got {agents_map.get('documentation-verifier')!r}. "
            "Implementation required: add documentation-verifier to a doc-mandatory "
            "protected set in _build_agents_map (BO-2200b-5).",
        )


class TestDocAgentsProtectedLikeTddMandatory(unittest.TestCase):
    """AC BO-2200b-5 (structural parity): documentation-expert and
    documentation-verifier protection must be behaviourally identical to the
    existing TDD-mandatory protection for test-writer and test-runner.

    'Same mechanism' is verified by behavioural parity: identical override
    attempts applied to both pairs yield identical outcomes ('needed' in both
    cases).  The same _build_agents_map override-blocking guard must cover both
    the TDD pair and the doc pair."""

    def _build_map_with_overrides(self, overrides: dict) -> dict:
        """Build a doc-triggering agents map with the given not_needed_overrides."""
        ac = _make_triggering_ac()
        return _build_agents_map(
            assigned_agent=ac["assigned_agent"],
            change_targets=[ac["change_target"]],
            risk_surface=ac["risk_surface"],
            not_needed_overrides=overrides,
            guardrail_config_path=_GUARDRAIL_CONFIG,
            agent_registry_path=_AGENT_REGISTRY,
        )

    def test_doc_agents_protected_like_tdd_mandatory(self):
        # covers: BO-2200b-5
        """AC BO-2200b-5 (parity): The protection of documentation-expert and
        documentation-verifier from not_needed_overrides must be structurally
        equivalent to the TDD-mandatory protection that guards test-writer and
        test-runner (BO-550-1-i).

        Test strategy:
          1. Confirm the TDD pre-condition: test-writer and test-runner survive
             a not_needed_overrides attempt (existing BO-550-1-i behaviour).
          2. Assert the same behavioural outcome for documentation-expert and
             documentation-verifier: they too survive a not_needed_overrides
             attempt when the trigger fired.
          3. Verify value-level parity: both TDD agents and doc agents resolve
             to 'needed' — the same string — confirming the protection behaves
             identically across both pairs.

        Until the BO-2200b-5 implementation lands, step 2 (and step 3) fail
        with AssertionError because the current code honours the override for
        the doc pair while blocking it only for the TDD pair.  The TDD
        pre-condition in step 1 must remain green — if it turns red, the
        existing BO-550-1-i protection itself is broken, which is a separate
        regression.
        """
        # --- Step 1: TDD pre-condition (must stay green) ---
        tdd_override = {
            "test-writer": "not_needed",
            "test-runner": "not_needed",
        }
        tdd_map = self._build_map_with_overrides(tdd_override)

        self.assertEqual(
            tdd_map.get("test-writer"),
            "needed",
            "Pre-condition failed: test-writer was stripped by a not_needed_override — "
            "the existing BO-550-1-i TDD-mandatory protection appears to be broken. "
            "This failure is independent of BO-2200b-5; fix BO-550-1-i first.",
        )
        self.assertEqual(
            tdd_map.get("test-runner"),
            "needed",
            "Pre-condition failed: test-runner was stripped by a not_needed_override — "
            "the existing BO-550-1-i TDD-mandatory protection appears to be broken. "
            "This failure is independent of BO-2200b-5; fix BO-550-1-i first.",
        )

        # --- Step 2: Doc agents must survive the same treatment (parity assertion) ---
        doc_override = {
            "documentation-expert": "not_needed",
            "documentation-verifier": "not_needed",
        }
        doc_map = self._build_map_with_overrides(doc_override)

        self.assertEqual(
            doc_map.get("documentation-expert"),
            "needed",
            "documentation-expert was stripped by a not_needed override even though "
            "the documentation trigger fired — the doc-mandatory protection is absent. "
            f"Got: {doc_map.get('documentation-expert')!r}. "
            "Expected: 'needed' (same outcome as test-writer under TDD-mandatory).",
        )
        self.assertEqual(
            doc_map.get("documentation-verifier"),
            "needed",
            "documentation-verifier was stripped by a not_needed override even though "
            "the documentation trigger fired — the doc-mandatory protection is absent. "
            f"Got: {doc_map.get('documentation-verifier')!r}. "
            "Expected: 'needed' (same outcome as test-runner under TDD-mandatory).",
        )

        # --- Step 3: Value-level parity (confirms identical mechanism outcome) ---
        self.assertEqual(
            doc_map.get("documentation-expert"),
            tdd_map.get("test-writer"),
            "Parity check failed: documentation-expert and test-writer resolve to "
            "different values under analogous override attempts. "
            f"documentation-expert={doc_map.get('documentation-expert')!r}, "
            f"test-writer={tdd_map.get('test-writer')!r}. "
            "The protection must produce identical outcomes for both pairs.",
        )
        self.assertEqual(
            doc_map.get("documentation-verifier"),
            tdd_map.get("test-runner"),
            "Parity check failed: documentation-verifier and test-runner resolve to "
            "different values under analogous override attempts. "
            f"documentation-verifier={doc_map.get('documentation-verifier')!r}, "
            f"test-runner={tdd_map.get('test-runner')!r}. "
            "The protection must produce identical outcomes for both pairs.",
        )


if __name__ == "__main__":
    unittest.main()
