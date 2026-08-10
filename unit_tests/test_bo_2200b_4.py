"""
MODULE: test_bo_2200b_4
GOAL: RED test stubs for AC BO-2200b-4 — Generating a ticket from a
      doc-triggering AC injects both the writer (documentation-expert) and
      the verifier (documentation-verifier) into the agents map, and sets
      documentation_required: true in the frontmatter.

      When the AC does NOT trigger a documentation demand, neither
      documentation_required nor documentation-verifier appears.

TICKET: tickets/00_inbox/epics/EPIC-DocumentationCoverageGuarantee/
        13_TICKET-20260715-BO-2200b-4.md
COVERS: BO-2200b-4
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from generate_ticket_from_ac import (  # noqa: E402
    _build_agents_map,
    _build_frontmatter,
)

# ---------------------------------------------------------------------------
# Path to the guardrail config used by the computed map
# ---------------------------------------------------------------------------

_GUARDRAIL_CONFIG = _REPO_ROOT / "config" / "guardrail_gates.yaml"
_AGENT_REGISTRY = _REPO_ROOT / "config" / "agent_registry.json"

# ---------------------------------------------------------------------------
# Minimal AC record helpers
# ---------------------------------------------------------------------------


def _make_triggering_ac() -> dict:
    """Minimal AC record whose change_target='ui' triggers documentation-expert
    via the documentation_gates.change_target_triggers list (BO-2200a-1).

    risk_surface='production' is not in risk_surface_triggers and not in
    non_triggering_classifications, so the trigger fires cleanly via
    change_target alone.
    """
    return {
        "id": "TEST-DOC-TRIGGER",
        "title": "UI surface change that triggers documentation demand",
        "assigned_agent": "python-coder",
        "change_target": "ui",
        "risk_surface": "production",
        "estimated_complexity": "M",
        "criteria": (
            "Given a UI-surface AC,\n"
            "When the generator processes it,\n"
            "Then documentation-expert is injected as needed."
        ),
    }


def _make_non_triggering_ac() -> dict:
    """Minimal AC record whose change_target='code' does NOT trigger documentation-expert.

    'code' is absent from documentation_gates.change_target_triggers and
    'production' is absent from risk_surface_triggers — no documentation demand fires.
    """
    return {
        "id": "TEST-NO-DOC-TRIGGER",
        "title": "Internal code change that does not require documentation",
        "assigned_agent": "python-coder",
        "change_target": "code",
        "risk_surface": "production",
        "estimated_complexity": "S",
        "criteria": (
            "Given an internal code AC,\n"
            "When the generator processes it,\n"
            "Then documentation-expert is NOT injected."
        ),
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDocTriggeringAcInjectsBothWriterAndVerifier(unittest.TestCase):
    """AC BO-2200b-4: doc-triggering ACs must carry documentation-verifier and
    documentation_required: true alongside documentation-expert."""

    def setUp(self):
        self.ac = _make_triggering_ac()
        self.agents_map = _build_agents_map(
            assigned_agent=self.ac["assigned_agent"],
            change_targets=[self.ac["change_target"]],
            risk_surface=self.ac["risk_surface"],
            guardrail_config_path=_GUARDRAIL_CONFIG,
            agent_registry_path=_AGENT_REGISTRY,
        )

    def test_doc_triggering_ac_sets_documentation_required_and_verifier(self):
        # covers: BO-2200b-4
        """AC BO-2200b-4 (part 1): generating a ticket from a doc-triggering AC
        (change_target in documentation_gates.change_target_triggers) must:

        a) set documentation_required: true in the ticket frontmatter, AND
        b) inject documentation-verifier: needed in the agents map.

        These two conditions enforce that whenever documentation-expert is wired,
        its companion verification phase (documentation-verifier) is also wired
        and the frontmatter flag signals the demand to downstream agents.

        Implementation required: python-coder must modify _build_agents_map (to
        inject documentation-verifier when documentation-expert is injected) and
        _build_frontmatter (to set documentation_required: true when
        documentation-verifier is in the agents map as 'needed').

        Until that implementation lands this test fails with AssertionError.
        """
        # --- Part (a): agents map must contain documentation-verifier: needed ---
        self.assertIn(
            "documentation-verifier",
            self.agents_map,
            "Expected 'documentation-verifier' in agents map when documentation-expert "
            f"is injected, but only found: {list(self.agents_map.keys())}",
        )
        self.assertEqual(
            self.agents_map["documentation-verifier"],
            "needed",
            f"Expected documentation-verifier='needed', "
            f"got {self.agents_map.get('documentation-verifier')!r}",
        )

        # --- Part (b): frontmatter must carry documentation_required: true ---
        ac_id = self.ac["id"]
        frontmatter_str = _build_frontmatter(
            ac=self.ac,
            ac_id=ac_id,
            files_touched=[],
            agents=self.agents_map,
            ac_store_path=None,
        )
        # Strip the YAML delimiters and parse
        fm_body = frontmatter_str.strip("---").strip()
        fm = yaml.safe_load(fm_body)
        self.assertIsInstance(fm, dict, f"Frontmatter did not parse to a dict: {fm!r}")
        self.assertIn(
            "documentation_required",
            fm,
            "Expected 'documentation_required' key in frontmatter when "
            "documentation-verifier is in the agents map as 'needed', "
            f"but frontmatter keys are: {list(fm.keys())}",
        )
        self.assertIs(
            fm["documentation_required"],
            True,
            f"Expected documentation_required=True in frontmatter, "
            f"got {fm.get('documentation_required')!r}",
        )


class TestNonTriggeringAcSetsNeitherFlagNorVerifier(unittest.TestCase):
    """AC BO-2200b-4: non-triggering ACs must NOT carry documentation-verifier
    or documentation_required: true."""

    def setUp(self):
        self.ac = _make_non_triggering_ac()
        self.agents_map = _build_agents_map(
            assigned_agent=self.ac["assigned_agent"],
            change_targets=[self.ac["change_target"]],
            risk_surface=self.ac["risk_surface"],
            guardrail_config_path=_GUARDRAIL_CONFIG,
            agent_registry_path=_AGENT_REGISTRY,
        )

    def test_non_triggering_ac_sets_neither_flag_nor_verifier(self):
        # covers: BO-2200b-4
        """AC BO-2200b-4 (part 2): generating a ticket from a non-triggering AC
        (change_target NOT in documentation_gates.change_target_triggers AND
        risk_surface NOT in risk_surface_triggers) must:

        a) NOT include documentation-verifier in the agents map (at all), AND
        b) NOT include documentation_required: true in the frontmatter.

        This ensures the injection is strictly gated on the BO-2200a-1 trigger
        decision: tickets that don't require documentation carry no noise.

        Implementation required: the same guards added for the positive case
        must naturally absent when the trigger condition is false.
        Until implementation lands this test fails with AssertionError only
        when the positive test also fails (because the feature doesn't exist yet);
        if the feature is partially added and incorrectly fires unconditionally
        this test independently catches it.
        """
        # --- Part (a): agents map must NOT contain documentation-verifier ---
        self.assertNotIn(
            "documentation-verifier",
            self.agents_map,
            "Expected 'documentation-verifier' to be ABSENT from agents map for a "
            "non-triggering AC, but found it with status: "
            f"{self.agents_map.get('documentation-verifier')!r}",
        )
        # For completeness: also confirm documentation-expert is absent
        self.assertNotIn(
            "documentation-expert",
            {k for k, v in self.agents_map.items() if v == "needed"},
            "Expected 'documentation-expert' to be NOT needed for a non-triggering AC, "
            f"but agents_map contains: {self.agents_map}",
        )

        # --- Part (b): frontmatter must NOT carry documentation_required: true ---
        ac_id = self.ac["id"]
        frontmatter_str = _build_frontmatter(
            ac=self.ac,
            ac_id=ac_id,
            files_touched=[],
            agents=self.agents_map,
            ac_store_path=None,
        )
        fm_body = frontmatter_str.strip("---").strip()
        fm = yaml.safe_load(fm_body)
        self.assertIsInstance(fm, dict, f"Frontmatter did not parse to a dict: {fm!r}")
        # documentation_required must either be absent or explicitly False/None
        doc_required = fm.get("documentation_required")
        self.assertIsNot(
            doc_required,
            True,
            "Expected 'documentation_required' to be absent or not True in frontmatter "
            f"for a non-triggering AC, but got documentation_required={doc_required!r}",
        )


if __name__ == "__main__":
    unittest.main()
