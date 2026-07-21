"""
MODULE: test_bp_1100f_5
GOAL: Behavioral tests for BP-1100f-5 — a work item declaring a durable side-effect
      is routed through the observable-side-effect smoke check (user-surface-smoker)
      automatically, AND a work item NOT declaring one is not force-routed (BP-1100f-5-i).

COVERS: BP-1100f-5, BP-1100f-5-i
TICKET: tickets/00_inbox/TICKET-20260721-BP-1100f-5.md

Tests exercise the REAL routing function (_build_agents_map in generate_ticket_from_ac.py)
against realistic AC fixture dicts — not mocks of the router.

RED baseline before implementation:
  - test_side_effect_item_routes_to_smoker_automatically: FAIL (user-surface-smoker not wired)
  - test_docs_only_item_not_force_routed_to_smoker: FAIL (user-surface-smoker may appear if wiring is too broad)
  - test_user_facing_surface_existing_routing_regression: PASS (no regression if routing unchanged)
"""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Path setup: unit_tests/ac_store/ is 3 levels below the repo root
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from generate_ticket_from_ac import _build_agents_map  # noqa: E402


# ---------------------------------------------------------------------------
# Helper: find config paths relative to repo root
# ---------------------------------------------------------------------------

_GUARDRAIL_CONFIG = _REPO_ROOT / "config" / "guardrail_gates.yaml"
_AGENT_REGISTRY = _REPO_ROOT / "config" / "agent_registry.json"


def _build_map(ac_data: dict, ac_id: str = "TEST-FIXTURE") -> dict[str, str]:
    """Run _build_agents_map with real config files against the given AC fixture dict.

    Exercises the REAL router — not a mock. Passes the real guardrail_gates.yaml
    and agent_registry.json so that routing decisions are computed against the
    actual on-disk configuration, catching any config/code divergence.

    Args:
        ac_data: AC record fields. Must include assigned_agent, change_target,
                 risk_surface. May include declares_side_effect.
        ac_id: AC identifier (for error messages only).

    Returns:
        Computed agents map dict (agent name → status string).
    """
    assigned_agent = ac_data.get("assigned_agent", "python-coder")
    change_target = ac_data.get("change_target")
    change_targets = [change_target] if isinstance(change_target, str) and change_target else change_target
    risk_surface = ac_data.get("risk_surface") or None
    files_touched_raw = ac_data.get("_files_touched", [])
    declares_side_effect = bool(ac_data.get("declares_side_effect", False))

    return _build_agents_map(
        assigned_agent,
        change_targets=change_targets if change_targets else None,
        risk_surface=risk_surface,
        files_touched=files_touched_raw,
        declares_side_effect=declares_side_effect,
        guardrail_config_path=_GUARDRAIL_CONFIG,
        agent_registry_path=_AGENT_REGISTRY,
    )


def _run_dry_run_via_main(ac_data: dict, ac_id: str) -> dict:
    """Run generate_ticket_from_ac main() with --dry-run and return parsed frontmatter.

    Writes a temporary AC YAML file, invokes main() with --dry-run, captures
    stdout, and parses the YAML frontmatter block from the output. Used to
    verify the end-to-end pipeline including frontmatter emission.

    Args:
        ac_data: AC record dict. The 'id' key is set to *ac_id* automatically.
        ac_id:   The AC id to use.

    Returns:
        Parsed frontmatter dict, or an empty dict when parsing fails.
    """
    from generate_ticket_from_ac import main as _main  # noqa: PLC0415

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        ac_root = tmppath / "docs" / "acceptance-criteria" / "fixture-component"
        ac_root.mkdir(parents=True)

        ac_yaml_data = dict(ac_data)
        ac_yaml_data["id"] = ac_id
        # Remove private helper key
        ac_yaml_data.pop("_files_touched", None)

        ac_file = ac_root / f"{ac_id}.yaml"
        ac_file.write_text(yaml.dump(ac_yaml_data, allow_unicode=True), encoding="utf-8")

        captured = io.StringIO()
        with __import__("unittest.mock", fromlist=["patch"]).patch("sys.stdout", captured):
            _main(
                [
                    "--ac", ac_id,
                    "--ac-root", str(tmppath / "docs" / "acceptance-criteria"),
                    "--dry-run",
                ]
            )

        output = captured.getvalue()

    # Output format: ---\n<YAML>\n---\n\n<body>
    parts = output.split("---")
    if len(parts) >= 3:
        try:
            parsed = yaml.safe_load(parts[1])
            if isinstance(parsed, dict):
                return parsed
        except yaml.YAMLError:
            pass
    return {}


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestDeclaredSideEffectRoutesToSmoker(unittest.TestCase):
    """BP-1100f-5: AC with declares_side_effect=True must route to user-surface-smoker.

    The routing must be automatic (data-driven), not opt-in. The router MUST
    include user-surface-smoker as a 'needed' phase in the computed agents map
    when the AC declares a durable side-effect.

    These tests are RED before implementation because _build_agents_map currently
    has no declares_side_effect parameter and never includes user-surface-smoker
    in the computed agents map via the generator path.
    """

    def test_side_effect_item_routes_to_smoker_automatically(self) -> None:
        # covers: BP-1100f-5
        """AC with declares_side_effect=True must produce user-surface-smoker: needed.

        Uses the REAL _build_agents_map function against real config files.

        MUST be RED before implementation: _build_agents_map has no
        declares_side_effect parameter today, so it never adds user-surface-smoker
        to the agents map via the generator. AssertionError: got None, expected 'needed'.
        """
        ac_data = {
            "title": "Side-effect-declaring AC fixture — BP-1100f-5 routing test",
            "level": "L2",
            "status": "active",
            "work_status": "todo",
            "assigned_agent": "python-coder",
            "component": "build-pipeline",
            "estimated_complexity": "M",
            "change_target": "pipeline",
            "risk_surface": "contract_boundary",
            # NEW FIELD: declares that this work item produces a durable observable side-effect.
            # The router MUST include user-surface-smoker as needed when this is true.
            "declares_side_effect": True,
            "criteria": (
                "Given a work item declares a durable, observable side-effect,\n"
                "When the pipeline runs its verification phase,\n"
                "Then user-surface-smoker runs automatically and produces a smoke result,\n"
                "And the work item cannot reach done with the smoke check unrun."
            ),
        }

        agents = _build_map(ac_data, ac_id="BP-1100f-5-side-effect-fixture")

        self.assertEqual(
            agents.get("user-surface-smoker"),
            "needed",
            (
                "user-surface-smoker must be wired as 'needed' when the AC declares "
                "declares_side_effect: true. The router must add user-surface-smoker "
                "automatically (data-driven), not require an opt-in flag. "
                f"Current agents map: {agents!r}. "
                "Fix: add declares_side_effect parameter to _build_agents_map and include "
                "user-surface-smoker in all_needed when declares_side_effect is True."
            ),
        )

    def test_side_effect_frontmatter_emits_declares_side_effect_field(self) -> None:
        # covers: BP-1100f-5
        """End-to-end: ticket generated from an AC with declares_side_effect=True
        must carry declares_side_effect: true in the ticket frontmatter.

        Uses the real main() --dry-run pipeline to verify that the field
        propagates from the AC YAML through to the ticket frontmatter.

        MUST be RED before implementation: _build_frontmatter does not emit
        declares_side_effect today, so the field will be absent from the output.
        """
        ac_data = {
            "title": "Side-effect end-to-end frontmatter test — BP-1100f-5",
            "level": "L2",
            "status": "active",
            "work_status": "todo",
            "assigned_agent": "python-coder",
            "component": "build-pipeline",
            "estimated_complexity": "S",
            "change_target": "pipeline",
            "risk_surface": "contract_boundary",
            "declares_side_effect": True,
            "criteria": (
                "Given the AC has declares_side_effect: true,\n"
                "When generate_ticket_from_ac generates a ticket from it,\n"
                "Then the ticket frontmatter carries declares_side_effect: true."
            ),
        }

        fm = _run_dry_run_via_main(ac_data, ac_id="BP-1100f-5-e2e-frontmatter")

        self.assertTrue(
            fm.get("declares_side_effect"),
            (
                "The generated ticket frontmatter must carry declares_side_effect: true "
                "when the source AC has declares_side_effect: true. "
                f"Current frontmatter: {fm!r}. "
                "Fix: emit declares_side_effect in _build_frontmatter when present on the AC."
            ),
        )

        agents = fm.get("agents", {})
        self.assertEqual(
            agents.get("user-surface-smoker"),
            "needed",
            (
                "The generated ticket's agents map must include user-surface-smoker: needed "
                "when the AC has declares_side_effect: true. "
                f"Current agents map: {agents!r}."
            ),
        )


class TestDocsOnlyItemNotForceRoutedToSmoker(unittest.TestCase):
    """BP-1100f-5-i: AC without declares_side_effect must NOT be force-routed to smoker.

    The exemption is data-driven (ABSENCE of declares_side_effect), never by
    hard-coded item name or type. This test also verifies that the mandatory
    routing for side-effect-declaring items is not weakened by the narrowing
    (by running both cases in the same test).
    """

    def test_docs_only_item_not_force_routed_to_smoker(self) -> None:
        # covers: BP-1100f-5-i
        """AC without declares_side_effect must not include user-surface-smoker in agents map.

        Also verifies (in the same test run) that a side-effect-declaring AC still
        DOES include user-surface-smoker — the narrowing must not weaken the mandatory case.

        The docs-only AC has:
        - assigned_agent: documentation-expert (non-coder)
        - change_target: docs
        - risk_surface: internal
        - NO declares_side_effect field
        User-surface-smoker must NOT be in the agents map for this AC.

        The side-effect AC has:
        - assigned_agent: python-coder
        - declares_side_effect: True
        User-surface-smoker MUST be in the agents map for this AC.

        If the narrowing weakens the mandatory case (both get omitted), both
        assertions fail. If the smoke check is over-broad (both get included),
        the first assertion fails. Only correct routing passes both.
        """
        docs_only_ac = {
            "title": "Docs-only AC — no side-effect declared (BP-1100f-5-i)",
            "level": "L2",
            "status": "active",
            "work_status": "todo",
            "assigned_agent": "documentation-expert",
            "component": "build-pipeline",
            "estimated_complexity": "S",
            "change_target": "docs",
            "risk_surface": "internal",
            # No declares_side_effect field — this item makes no durable side-effect claim.
            "criteria": (
                "Given a documentation-only work item with no declared durable side-effect,\n"
                "When the pipeline runs its verification phase,\n"
                "Then user-surface-smoker is NOT required for this item."
            ),
        }
        side_effect_ac = {
            "title": "Side-effect AC — declares_side_effect true (BP-1100f-5)",
            "level": "L2",
            "status": "active",
            "work_status": "todo",
            "assigned_agent": "python-coder",
            "component": "build-pipeline",
            "estimated_complexity": "S",
            "change_target": "pipeline",
            "risk_surface": "contract_boundary",
            "declares_side_effect": True,
            "criteria": (
                "Given a work item that declares a durable side-effect,\n"
                "When the pipeline runs its verification phase,\n"
                "Then user-surface-smoker runs automatically."
            ),
        }

        docs_agents = _build_map(docs_only_ac, ac_id="BP-1100f-5-i-docs-fixture")
        side_effect_agents = _build_map(side_effect_ac, ac_id="BP-1100f-5-i-side-effect-fixture")

        # The docs-only item must NOT include user-surface-smoker.
        smoker_status_docs = docs_agents.get("user-surface-smoker")
        self.assertNotEqual(
            smoker_status_docs,
            "needed",
            (
                "user-surface-smoker must NOT be wired as 'needed' for a docs-only AC "
                "that declares no durable side-effect (BP-1100f-5-i). "
                f"The docs-only agents map contains: user-surface-smoker={smoker_status_docs!r}. "
                "The exemption must be data-driven (absence of declares_side_effect), "
                "never by hard-coded item name. "
                f"Full docs-only agents map: {docs_agents!r}."
            ),
        )

        # The side-effect item MUST include user-surface-smoker (narrowing must not weaken mandatory case).
        self.assertEqual(
            side_effect_agents.get("user-surface-smoker"),
            "needed",
            (
                "user-surface-smoker MUST still be 'needed' for a side-effect-declaring AC "
                "even after applying the BP-1100f-5-i narrowing. "
                "The narrowing must not weaken the mandatory routing for items that DO declare "
                "a durable side-effect. "
                f"Side-effect agents map: {side_effect_agents!r}."
            ),
        )


class TestDeclaredSideEffectCannotBeOverriddenToNotNeeded(unittest.TestCase):
    """BP-1100f-5: not_needed_overrides cannot cancel a declared side-effect gate.

    When declares_side_effect=True, user-surface-smoker must be mandatory —
    an explicit not_needed_overrides={"user-surface-smoker": "not_needed"} call
    must NOT remove it from the agents map (mirrors BO-550-1-i for TDD agents).

    Without this protection a ticket author could add user-surface-smoker: not_needed
    to their AC's overrides and silently bypass the mandatory smoke check, defeating
    the entire purpose of BP-1100f-5.
    """

    def test_not_needed_override_cannot_bypass_declared_side_effect_gate(self) -> None:
        # covers: BP-1100f-5
        """user-surface-smoker must remain 'needed' even with an explicit not_needed override.

        This verifies that declares_side_effect=True creates a mandatory (non-overridable)
        gate, consistent with how test-writer and test-runner are protected by BO-550-1-i.

        MUST be RED before fix: the initial implementation adds user-surface-smoker to
        all_needed but does not protect it from not_needed_overrides, so a caller who
        passes not_needed_overrides={"user-surface-smoker": "not_needed"} would silently
        remove it from the computed map.

        After the fix (side_effect_protected analogous to tdd_protected), passing
        not_needed_overrides for user-surface-smoker when declares_side_effect=True
        must have no effect — the computed chain wins.
        """
        from generate_ticket_from_ac import _build_agents_map as _bam  # noqa: PLC0415

        agents = _bam(
            "python-coder",
            change_targets=["pipeline"],
            risk_surface="contract_boundary",
            files_touched=["config/agent_registry.json"],
            declares_side_effect=True,
            not_needed_overrides={"user-surface-smoker": "not_needed"},
            guardrail_config_path=_GUARDRAIL_CONFIG,
            agent_registry_path=_AGENT_REGISTRY,
        )

        self.assertEqual(
            agents.get("user-surface-smoker"),
            "needed",
            (
                "user-surface-smoker must remain 'needed' even when "
                "not_needed_overrides contains user-surface-smoker: not_needed, "
                "provided declares_side_effect=True. The declared side-effect is "
                "a mandatory gate (BP-1100f-5); the computed chain must win over "
                "the override, mirroring the BO-550-1-i protection for TDD agents. "
                f"Current agents map: {agents!r}. "
                "Fix: compute side_effect_protected (analogous to tdd_protected) "
                "and exclude user-surface-smoker from the not_needed discard loop "
                "when declares_side_effect=True."
            ),
        )


class TestUserFacingSurfaceExistingRoutingRegression(unittest.TestCase):
    """Regression: existing user_facing_surface routing behavior is unchanged.

    This test exercises the existing path (user_facing_surface in ticket frontmatter)
    to confirm the new declares_side_effect path does not break or alter it.

    Note: the generator currently does NOT auto-include user-surface-smoker based on
    user_facing_surface (that field is only checked by ticket-supervisor directly,
    not by the generator). This test confirms that the generator's behavior for
    an AC without declares_side_effect remains unchanged — user-surface-smoker
    is NOT included unless declares_side_effect is explicitly true.
    """

    def test_no_side_effect_no_smoker_without_user_facing_surface(self) -> None:
        # covers: BP-1100f-5-i (regression guard)
        """An AC with neither declares_side_effect nor user_facing_surface must
        not include user-surface-smoker in the generated agents map.

        This is a regression guard: the existing behavior (user-surface-smoker
        is NOT auto-included by the generator) must not be accidentally broken.
        """
        standard_ac = {
            "title": "Standard code AC — no side-effect declaration (regression guard)",
            "level": "L2",
            "status": "active",
            "work_status": "todo",
            "assigned_agent": "python-coder",
            "component": "build-pipeline",
            "estimated_complexity": "S",
            "change_target": "pipeline",
            "risk_surface": "internal",
            # Neither declares_side_effect nor user_facing_surface is set.
            # user-surface-smoker must NOT appear in the agents map.
            "criteria": (
                "Given a standard code AC with no declared side-effect,\n"
                "When a ticket is generated from it,\n"
                "Then user-surface-smoker is NOT in the agents map."
            ),
        }

        agents = _build_map(standard_ac, ac_id="BP-1100f-5-regression-fixture")

        smoker_status = agents.get("user-surface-smoker")
        self.assertNotEqual(
            smoker_status,
            "needed",
            (
                "Regression: user-surface-smoker must NOT be wired as 'needed' for a "
                "standard AC that declares no durable side-effect. "
                f"Current status: user-surface-smoker={smoker_status!r}. "
                f"Full agents map: {agents!r}."
            ),
        )


if __name__ == "__main__":
    unittest.main()
