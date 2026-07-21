"""
MODULE: test_bo_2200b_5_i
GOAL: RED test stubs for AC BO-2200b-5-i — A hand-edited not_needed on the
      verifier is restored to needed at generation time.

      When someone hand-edits a ticket (whose documentation-verifier was set to
      needed at generation time) to set documentation-verifier (or
      documentation-expert) to not_needed, a subsequent re-generation or
      re-validation must restore both agents to needed. The restoration must be
      silent-proof: either the value is overwritten or a validation error is
      surfaced — never silently accepted.

      BO-2200b-5-i extends BO-2200b-5 with the specific sub-case: a hand-edit
      that targets ONLY documentation-verifier (without also editing
      documentation-expert), and the "at generation time" framing that tests
      the re-generation path rather than the general override-pass-through path
      tested by BO-2200b-5.

TICKET: tickets/00_inbox/epics/EPIC-DocumentationCoverageGuarantee/
        15_TICKET-20260715-BO-2200b-5-i.md
COVERS: BO-2200b-5-i
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


def _make_doc_triggering_ac() -> dict:
    """Minimal AC record that triggers documentation-expert via change_target_triggers.

    Uses change_target='ui' which is present in
    documentation_gates.change_target_triggers in config/guardrail_gates.yaml.
    risk_surface='production' is not a recognised guardrail key, so no
    guardrail agents are added from the ui/production pair — the doc trigger
    fires purely from change_target_triggers.  This mirrors the triggering
    scenario used in test_bo_2200b_5.py to keep scenarios consistent.
    """
    return {
        "id": "TEST-BO-2200b-5-i-VERIFIER-HAND-EDIT",
        "title": "UI surface change — verifier-only hand-edit restoration test",
        "assigned_agent": "python-coder",
        "change_target": "ui",
        "risk_surface": "production",
        "estimated_complexity": "S",
        "criteria": (
            "Given a UI-surface ticket with documentation-expert and "
            "documentation-verifier both needed,\n"
            "When someone hand-edits documentation-verifier to not_needed,\n"
            "Then re-generation restores documentation-verifier to needed.\n"
            "And the restore is silent-proof."
        ),
    }


# ---------------------------------------------------------------------------
# Tests — class 1: verifier-only sub-case of the overwrite path
# ---------------------------------------------------------------------------


class TestVerifierOnlyOverrideRestoredOnRegeneration(unittest.TestCase):
    """AC BO-2200b-5-i (overwrite path): when ONLY documentation-verifier is
    hand-edited to not_needed (documentation-expert is not touched), the
    restored value at generation time must be 'needed' for BOTH agents.

    This is the verifier-specific sub-case that distinguishes BO-2200b-5-i from
    its parent BO-2200b-5: the parent tests both agents overridden simultaneously;
    this class targets the single-agent override that is the literal scenario
    described in the AC title ("A hand-edited not_needed ON THE VERIFIER")."""

    def test_hand_edited_not_needed_restored_on_regeneration(self):
        # covers: BO-2200b-5-i
        """AC BO-2200b-5-i (core — verifier-only sub-case): a ticket was generated
        with documentation-verifier: needed. Someone hand-edits ONLY
        documentation-verifier to not_needed (leaving documentation-expert
        unchanged at its generated value). When the ticket is re-generated/re-validated
        — modelled by calling _build_agents_map with the hand-edited state as
        not_needed_overrides — both documentation-expert and documentation-verifier
        must come out as 'needed'.

        This is NOT covered by test_bo_2200b_5.py, which only tests the case where
        BOTH doc agents are overridden simultaneously. Here only documentation-verifier
        is overridden. The doc-mandatory protection must protect the verifier even when
        the expert override is absent from the call.

        Until the BO-2200b-5-i guard is confirmed to cover this case, the overrides
        loop in _build_agents_map might fail to protect the verifier when the expert
        is not present in overrides. If so, documentation-verifier would come out as
        'not_needed' and these assertions fail with AssertionError.
        """
        ac = _make_doc_triggering_ac()

        # Simulate hand-editing ONLY documentation-verifier (not the expert).
        verifier_only_override = {"documentation-verifier": "not_needed"}

        agents_map = _build_agents_map(
            assigned_agent=ac["assigned_agent"],
            change_targets=[ac["change_target"]],
            risk_surface=ac["risk_surface"],
            not_needed_overrides=verifier_only_override,
            guardrail_config_path=_GUARDRAIL_CONFIG,
            agent_registry_path=_AGENT_REGISTRY,
        )

        # --- documentation-verifier must be restored to 'needed' ---
        self.assertIn(
            "documentation-verifier",
            agents_map,
            "Expected 'documentation-verifier' to appear in the agents map after "
            f"a verifier-only hand-edit, but map contains: {list(agents_map.keys())}",
        )
        self.assertEqual(
            agents_map.get("documentation-verifier"),
            "needed",
            "AC BO-2200b-5-i: documentation-verifier must be restored to 'needed' "
            "when a verifier-only not_needed override is passed (simulating a "
            "hand-edit at re-generation time). "
            f"Got: {agents_map.get('documentation-verifier')!r}. "
            "Implementation: ensure documentation-verifier is in the doc-mandatory "
            "protected set in _build_agents_map so that a verifier-only not_needed "
            "override is overwritten by the computed trigger chain.",
        )

        # --- documentation-expert must also remain 'needed' (not collaterally dropped) ---
        self.assertIn(
            "documentation-expert",
            agents_map,
            "Expected 'documentation-expert' to appear in the agents map; "
            f"map contains: {list(agents_map.keys())}",
        )
        self.assertEqual(
            agents_map.get("documentation-expert"),
            "needed",
            "AC BO-2200b-5-i: documentation-expert must remain 'needed' when only "
            "documentation-verifier is hand-edited — the expert must not be collaterally "
            f"removed. Got: {agents_map.get('documentation-expert')!r}.",
        )

    def test_expert_only_override_restores_both_agents(self):
        # covers: BO-2200b-5-i
        """AC BO-2200b-5-i (symmetric sub-case): when ONLY documentation-expert is
        hand-edited to not_needed (documentation-verifier not touched), both
        documentation-expert AND documentation-verifier must still be 'needed' in
        the re-generated output.

        The AC criteria state: 'the ticket is re-generated or re-validated, Then the
        status is restored to needed for BOTH agents'. This test verifies the
        expert-only override variant: removing only the expert must not leave the
        verifier orphaned at 'needed' while the expert becomes 'not_needed'.

        The doc-mandatory protection must cover both agents independently — not only
        when both are simultaneously overridden.
        """
        ac = _make_doc_triggering_ac()

        # Simulate hand-editing ONLY documentation-expert (not the verifier).
        expert_only_override = {"documentation-expert": "not_needed"}

        agents_map = _build_agents_map(
            assigned_agent=ac["assigned_agent"],
            change_targets=[ac["change_target"]],
            risk_surface=ac["risk_surface"],
            not_needed_overrides=expert_only_override,
            guardrail_config_path=_GUARDRAIL_CONFIG,
            agent_registry_path=_AGENT_REGISTRY,
        )

        # --- documentation-expert must be restored to 'needed' despite the override ---
        self.assertEqual(
            agents_map.get("documentation-expert"),
            "needed",
            "AC BO-2200b-5-i: documentation-expert must be restored to 'needed' "
            "when an expert-only not_needed override is passed. "
            f"Got: {agents_map.get('documentation-expert')!r}.",
        )

        # --- documentation-verifier must remain 'needed' as companion ---
        self.assertEqual(
            agents_map.get("documentation-verifier"),
            "needed",
            "AC BO-2200b-5-i: documentation-verifier must remain 'needed' when the "
            "expert alone is hand-edited (companion verifier must not be dropped). "
            f"Got: {agents_map.get('documentation-verifier')!r}.",
        )


# ---------------------------------------------------------------------------
# Tests — class 2: silent-proof guarantee
# ---------------------------------------------------------------------------


class TestDowngradeNotSilentlyAccepted(unittest.TestCase):
    """AC BO-2200b-5-i ('silent-proof' guarantee): the hand-edited not_needed
    must be either overwritten or surfaced as a validation error — never silently
    accepted.

    The AC criteria state: 'the restore is silent-proof: the change is either
    overwritten or surfaced as a validation error, never silently accepted.'

    The 'silently accepted' failure mode has two variants:
    1. The override takes effect (the value is 'not_needed' in the output) — tested
       by TestVerifierOnlyOverrideRestoredOnRegeneration.
    2. The override is ignored but no signal is given to the caller — this class.

    The silent-proof requirement means _build_agents_map must emit a WARNING-level
    log message explicitly naming the blocked agent when a doc-mandatory override
    attempt is detected. This distinguishes BO-2200b-5-i from BO-2200b-5: the parent
    AC only requires that the override NOT take effect; the child AC additionally
    requires the attempt to be surfaced so operators can detect hand-edit interference.
    """

    def test_downgrade_not_silently_accepted(self):
        # covers: BO-2200b-5-i
        """AC BO-2200b-5-i (silent-proof): when _build_agents_map detects and blocks
        a not_needed override for documentation-verifier (a doc-mandatory agent),
        it must emit a WARNING-level log message that explicitly names the blocked
        agent. This ensures the hand-edit attempt is surfaced — not overwritten
        silently — so that downstream auditors, operators, or CI tooling can identify
        that the ticket's agents map was hand-edited away from its computed value.

        The AC states the restore must be 'silent-proof': overwriting alone is not
        sufficient because a silent overwrite produces no audit signal. The WARNING
        log is the minimum surfacing that satisfies the 'surfaced as a validation
        error' alternative without raising a hard exception that would break callers.

        Implementation required: add a logger.warning() call in _build_agents_map
        whenever a not_needed override for a doc-mandatory agent (documentation-expert
        or documentation-verifier) is detected and blocked by the doc_protected set.
        The warning message must contain the agent name so this test can locate it.

        Until this WARNING is implemented, the assertLogs context captures only the
        unrelated 'No guardrail entry' warning for the ('ui', 'production') pair
        (because 'production' is not a recognised risk_surface in guardrail_gates.yaml),
        and the assertion that the log output contains 'documentation-verifier' together
        with an override-related keyword fails with AssertionError (RED baseline).
        """
        ac = _make_doc_triggering_ac()
        verifier_only_override = {"documentation-verifier": "not_needed"}

        # Capture WARNING-level logs from the generate_ticket_from_ac logger.
        # assertLogs will succeed as long as at least one WARNING is emitted
        # (the 'No guardrail entry' warning for 'production' risk_surface ensures
        # the context does not fail with 'no logs captured'). The key assertion
        # is on the CONTENT of the captured messages below.
        with self.assertLogs("generate_ticket_from_ac", level="WARNING") as cm:
            agents_map = _build_agents_map(
                assigned_agent=ac["assigned_agent"],
                change_targets=[ac["change_target"]],
                risk_surface=ac["risk_surface"],
                not_needed_overrides=verifier_only_override,
                guardrail_config_path=_GUARDRAIL_CONFIG,
                agent_registry_path=_AGENT_REGISTRY,
            )

        # The warning must explicitly name the blocked agent AND use a keyword that
        # distinguishes it from the unrelated 'No guardrail entry' warning.
        # Keywords accepted: 'override', 'not_needed', 'blocked', 'restored',
        # 'protected', 'mandatory'.
        _override_keywords = frozenset({
            "override", "not_needed", "blocked", "restored", "protected", "mandatory"
        })
        blocked_override_warnings = [
            msg for msg in cm.output
            if "documentation-verifier" in msg
            and any(kw in msg.lower() for kw in _override_keywords)
        ]
        self.assertTrue(
            blocked_override_warnings,
            "AC BO-2200b-5-i (silent-proof): expected _build_agents_map to emit "
            "a WARNING log naming 'documentation-verifier' when its not_needed "
            "override was detected and blocked by the doc-mandatory protection. "
            "A generic 'No guardrail entry' warning does NOT satisfy this requirement "
            "— the warning must specifically surface the blocked hand-edit attempt. "
            f"Captured log output: {cm.output}. "
            "Implementation required: add logger.warning() in _build_agents_map when "
            "a doc-mandatory agent override is blocked (n_location_rule=1 in "
            "scripts/ac_store/generate_ticket_from_ac.py).",
        )

        # Also confirm the overwrite took effect (both behavioral paths verified):
        self.assertEqual(
            agents_map.get("documentation-verifier"),
            "needed",
            "documentation-verifier must be 'needed' (overwrite confirmed) — "
            f"got {agents_map.get('documentation-verifier')!r}.",
        )
        self.assertEqual(
            agents_map.get("documentation-expert"),
            "needed",
            "documentation-expert must remain 'needed' — "
            f"got {agents_map.get('documentation-expert')!r}.",
        )


if __name__ == "__main__":
    unittest.main()
