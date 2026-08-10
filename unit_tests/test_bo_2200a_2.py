"""
MODULE: test_bo_2200a_2
GOAL: RED test stubs for AC BO-2200a-2 — a boundary, safety, auth, or privacy
      risk surface also demands documentation.

TICKET: EPIC-DocumentationCoverageGuarantee/02_TICKET-20260715-BO-2200a-2.md
COVERS: BO-2200a-2

What must be implemented to make these tests green:
  1. Extend the `documentation_gates` policy evaluation in _build_agents_map
     (scripts/ac_store/generate_ticket_from_ac.py) to also read
     `risk_surface_triggers` from the `documentation_gates` config section.
  2. When the call's `risk_surface` matches any entry in `risk_surface_triggers`,
     add `documentation-expert` to the agents map as 'needed', independently of
     the `change_target_triggers` check (BO-2200a-1).
  3. The two trigger dimensions must be evaluated with OR semantics:
     documentation-expert is required if EITHER `change_target` intersects
     `change_target_triggers` OR `risk_surface` intersects `risk_surface_triggers`.
  4. Add `risk_surface_triggers: [contract_boundary, safety, auth, privacy]` to
     config/guardrail_gates.yaml under `documentation_gates` if not yet present
     (the config already carries this key as of the BO-2200a-1 implementation,
     but the generator does not yet read it).

Design notes:
  - Tests use a temporary guardrail config that intentionally omits
    `flow_change_gates` — the flow-change mechanism also injects documentation-expert
    for (code, contract_boundary) and (code, safety) pairs, which would mask a missing
    risk_surface_triggers implementation and make those tests falsely green.
  - `change_target='code'` is deliberately NOT in `change_target_triggers` so that
    the only possible trigger for documentation-expert in all three tests is the
    new risk_surface_triggers path.
"""

from __future__ import annotations

import logging
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from generate_ticket_from_ac import _build_agents_map  # noqa: E402

_AGENT_REGISTRY = _REPO_ROOT / "config" / "agent_registry.json"

# ---------------------------------------------------------------------------
# Minimal guardrail config sections shared across all tests.
#
# CRITICAL ISOLATION PROPERTIES:
#  1. No `documentation-expert` appears in ANY per-surface gate list below.
#     This ensures doc-expert can only enter via `documentation_gates` policy.
#  2. `flow_change_gates` is intentionally absent. Without it, the pairs
#     (code, contract_boundary) and (code, safety) do NOT get documentation-expert
#     through the flow-change path, so any doc-expert in the result comes
#     exclusively from risk_surface_triggers (the mechanism under test).
# ---------------------------------------------------------------------------

_MINIMAL_SURFACE_SECTIONS: dict = {
    "code": {
        "internal": ["test-writer", "test-runner"],
        "contract_boundary": [
            "architect-review",
            "test-writer",
            "test-runner",
            "pr-reviewer",
        ],
        "auth": [
            "architect-review",
            "test-writer",
            "test-runner",
            "pr-reviewer",
        ],
        "privacy": [
            "architect-review",
            "test-writer",
            "test-runner",
            "pr-reviewer",
        ],
        "safety": [
            "architect-review",
            "test-writer",
            "test-runner",
            "pr-reviewer",
        ],
        "cost": [
            "architect-review",
            "test-writer",
            "test-runner",
            "pr-reviewer",
        ],
    },
    "ui": {
        "internal": ["test-writer", "test-runner"],
        "contract_boundary": [
            "architect-review",
            "test-writer",
            "test-runner",
            "pr-reviewer",
        ],
        "auth": [
            "architect-review",
            "test-writer",
            "test-runner",
            "pr-reviewer",
        ],
        "privacy": ["test-writer", "test-runner", "pr-reviewer"],
        "safety": [
            "architect-review",
            "test-writer",
            "test-runner",
            "pr-reviewer",
        ],
        "cost": ["pr-reviewer"],
    },
    "infrastructure": {
        "internal": ["pr-reviewer"],
        "contract_boundary": ["architect-review", "pr-reviewer"],
        "auth": ["architect-review", "pr-reviewer"],
        "privacy": ["architect-review", "pr-reviewer"],
        "safety": ["architect-review", "pr-reviewer"],
        "cost": ["architect-review", "pr-reviewer"],
    },
}


def _write_guardrail_yaml(path: Path, content: dict) -> None:
    """Write a guardrail config dict to *path* as YAML.

    Raises:
        OSError: When the file cannot be written (propagated to the test as a
                 clear failure rather than silently swallowed).
        yaml.YAMLError: When the content cannot be serialised.
    """
    try:
        with open(path, "w", encoding="utf-8") as fh:
            yaml.dump(content, fh, default_flow_style=False, allow_unicode=True)
    except OSError as exc:
        _logger.warning("Could not write temp guardrail config %s: %s", path, exc)
        raise


class TestRiskSurfaceDocumentationGatesPolicy(unittest.TestCase):
    """Behavioral tests for the risk_surface-driven documentation-gates policy (BO-2200a-2).

    All three tests exercise _build_agents_map with a temporary guardrail config
    that has:
      - documentation_gates.risk_surface_triggers: [contract_boundary, safety, auth, privacy]
      - documentation_gates.change_target_triggers: [ui, schema, pipeline, docs]
        (change_target='code' is intentionally absent — NOT a trigger)
      - No flow_change_gates (to prevent that mechanism from masking the gap)
      - No documentation-expert in any per-surface gate (same reason)

    All three tests will be RED until _build_agents_map reads `risk_surface_triggers`
    and adds documentation-expert when `risk_surface` intersects the trigger list.
    """

    # -----------------------------------------------------------------------
    # test_risk_surface_contract_boundary_triggers_doc_expert
    # -----------------------------------------------------------------------

    def test_risk_surface_contract_boundary_triggers_doc_expert(self) -> None:
        # covers: BO-2200a-2
        """AC BO-2200a-2: risk_surface='contract_boundary' must cause documentation-expert='needed'.

        Given change_target='code' (which is NOT in change_target_triggers — so the
        change-target axis alone does not trigger documentation-expert) and
        risk_surface='contract_boundary' (which IS in risk_surface_triggers), when
        _build_agents_map is called, then the returned agents map must include
        documentation-expert with status 'needed'.

        The temp config explicitly omits flow_change_gates, so the (code, contract_boundary)
        pair does NOT receive documentation-expert via the flow-change path. The only
        possible trigger is risk_surface_triggers.

        This test will be RED until:
          - _build_agents_map reads documentation_gates.risk_surface_triggers, AND
          - adds documentation-expert='needed' when risk_surface intersects that set.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "guardrail_gates.yaml"
            config = dict(_MINIMAL_SURFACE_SECTIONS)
            config["documentation_gates"] = {
                "change_target_triggers": ["ui", "schema", "pipeline", "docs"],
                "risk_surface_triggers": [
                    "contract_boundary",
                    "safety",
                    "auth",
                    "privacy",
                ],
            }
            _write_guardrail_yaml(config_path, config)

            agents = _build_agents_map(
                "python-coder",
                change_targets=["code"],
                risk_surface="contract_boundary",
                guardrail_config_path=config_path,
                agent_registry_path=_AGENT_REGISTRY,
            )

            self.assertEqual(
                "needed",
                agents.get("documentation-expert"),
                msg=(
                    "Expected documentation-expert='needed' when risk_surface='contract_boundary' "
                    "is in documentation_gates.risk_surface_triggers. "
                    "change_target='code' is NOT in change_target_triggers — the risk_surface "
                    "trigger must fire independently. "
                    "Implement the risk_surface_triggers read-path in _build_agents_map (BO-2200a-2)."
                ),
            )

    # -----------------------------------------------------------------------
    # test_each_triggering_risk_surface_requires_doc_expert
    # -----------------------------------------------------------------------

    def test_each_triggering_risk_surface_requires_doc_expert(self) -> None:
        # covers: BO-2200a-2
        """AC BO-2200a-2: safety, auth, privacy each independently trigger
        documentation-expert='needed' even when change_target='code' would not.

        When documentation_gates.risk_surface_triggers lists
        [contract_boundary, safety, auth, privacy], calling _build_agents_map with
        any one of {safety, auth, privacy} as the sole risk_surface and
        change_target='code' (which is NOT in change_target_triggers) must yield
        documentation-expert='needed'.

        This test uses subTest so a failure clearly names the failing risk_surface.

        Will be RED until the risk_surface_triggers read-path is implemented —
        the current code does not inspect risk_surface_triggers at all.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "guardrail_gates.yaml"
            config = dict(_MINIMAL_SURFACE_SECTIONS)
            config["documentation_gates"] = {
                "change_target_triggers": ["ui", "schema", "pipeline", "docs"],
                "risk_surface_triggers": [
                    "contract_boundary",
                    "safety",
                    "auth",
                    "privacy",
                ],
            }
            _write_guardrail_yaml(config_path, config)

            for risk_surface in ("safety", "auth", "privacy"):
                with self.subTest(risk_surface=risk_surface):
                    agents = _build_agents_map(
                        "python-coder",
                        change_targets=["code"],
                        risk_surface=risk_surface,
                        guardrail_config_path=config_path,
                        agent_registry_path=_AGENT_REGISTRY,
                    )
                    self.assertEqual(
                        "needed",
                        agents.get("documentation-expert"),
                        msg=(
                            f"Expected documentation-expert='needed' when "
                            f"risk_surface='{risk_surface}' is in "
                            f"documentation_gates.risk_surface_triggers. "
                            f"change_target='code' alone does NOT trigger doc-expert "
                            f"(code is absent from change_target_triggers). "
                            f"Implement the risk_surface_triggers read-path (BO-2200a-2)."
                        ),
                    )

    # -----------------------------------------------------------------------
    # test_change_target_and_risk_surface_are_ORed
    # -----------------------------------------------------------------------

    def test_change_target_and_risk_surface_are_ORed(self) -> None:
        # covers: BO-2200a-2
        """AC BO-2200a-2: risk_surface and change_target triggers use OR semantics.

        The risk-surface trigger is evaluated independently of the change-target trigger.
        Documentation-expert must be required if EITHER dimension matches its
        triggering set.

        OR arm 1 (risk_surface trigger only):
          change_target='code' — NOT in change_target_triggers
          risk_surface='auth' — IS in risk_surface_triggers
          Expected: documentation-expert='needed' via risk_surface path alone.

        OR arm 2 (change_target trigger only):
          change_target='ui' — IS in change_target_triggers (BO-2200a-1, already live)
          risk_surface='internal' — NOT in risk_surface_triggers
          Expected: documentation-expert='needed' via change_target path alone.

        This test will be RED (on arm 1) until the risk_surface_triggers read-path is
        implemented. Arm 2 exercises the existing BO-2200a-1 path — it should be green
        already but confirms BO-2200a-1 is not broken by the BO-2200a-2 implementation.

        NOTE: arm 1 executes first. A failure there (AssertionError) makes the whole
        test RED before arm 2 is reached — which is the correct red-state signal.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "guardrail_gates.yaml"
            config = dict(_MINIMAL_SURFACE_SECTIONS)
            config["documentation_gates"] = {
                "change_target_triggers": ["ui", "schema", "pipeline", "docs"],
                "risk_surface_triggers": [
                    "contract_boundary",
                    "safety",
                    "auth",
                    "privacy",
                ],
            }
            _write_guardrail_yaml(config_path, config)

            # --- OR arm 1: non-triggering change_target + triggering risk_surface ---
            # change_target='code' is NOT in change_target_triggers
            # risk_surface='auth'  IS in risk_surface_triggers
            agents_risk_arm = _build_agents_map(
                "python-coder",
                change_targets=["code"],
                risk_surface="auth",
                guardrail_config_path=config_path,
                agent_registry_path=_AGENT_REGISTRY,
            )
            self.assertEqual(
                "needed",
                agents_risk_arm.get("documentation-expert"),
                msg=(
                    "Expected documentation-expert='needed' when change_target='code' "
                    "(non-triggering) + risk_surface='auth' (triggering via risk_surface_triggers). "
                    "OR semantics require that a triggering risk_surface is sufficient even when "
                    "the change_target alone would not trigger doc-expert. "
                    "Implement the risk_surface_triggers read-path (BO-2200a-2)."
                ),
            )

            # --- OR arm 2: triggering change_target + non-triggering risk_surface ---
            # change_target='ui' IS in change_target_triggers (BO-2200a-1)
            # risk_surface='internal' is NOT in risk_surface_triggers
            agents_target_arm = _build_agents_map(
                "python-coder",
                change_targets=["ui"],
                risk_surface="internal",
                guardrail_config_path=config_path,
                agent_registry_path=_AGENT_REGISTRY,
            )
            self.assertEqual(
                "needed",
                agents_target_arm.get("documentation-expert"),
                msg=(
                    "Expected documentation-expert='needed' when change_target='ui' "
                    "(triggering via change_target_triggers) + risk_surface='internal' "
                    "(non-triggering). The existing BO-2200a-1 change_target trigger must "
                    "still fire independently — BO-2200a-2 must not break it."
                ),
            )


if __name__ == "__main__":
    unittest.main()
