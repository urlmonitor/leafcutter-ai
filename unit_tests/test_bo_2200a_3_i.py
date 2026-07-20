"""
MODULE: test_bo_2200a_3_i
GOAL: RED test stubs for AC BO-2200a-3-i — A cost risk surface and an unclassified
      AC do not demand documentation.

TICKET: EPIC-DocumentationCoverageGuarantee/04_TICKET-20260715-BO-2200a-3-i.md
COVERS: BO-2200a-3-i

What must be implemented to make these tests green:

  1. Add the (code, cost) explicit exclusion to non_triggering_classifications in
     config/guardrail_gates.yaml:

       documentation_gates:
         non_triggering_classifications:
           ...existing entries...
           - {change_target: code, risk_surface: cost}

     This is the failing assertion in test_risk_surface_cost_does_not_trigger_doc_expert
     (Part 1). The cost risk surface must be an EXPLICIT negative so that any future
     expansion of risk_surface_triggers to include 'cost' does NOT impose a
     documentation burden on code+cost tickets.

  2. No generator code change is needed — _build_agents_map already reads and
     applies non_triggering_classifications (implemented in BO-2200a-3). The Part 2
     adversarial behavioral test confirms the mechanism works for the cost pair once
     the config entry exists.

  3. The legacy path (change_targets=None, risk_surface=None) must remain immune to
     documentation_gates — unclassified ACs that predate computed-gates classification
     must never be forced into a documentation demand by policy additions. This is
     tested in test_unclassified_ac_completes_without_forcing_doc_expert, which
     verifies the legacy path's fail-safe behaviour in a maximally adversarial config.

Design notes:
  - test_risk_surface_cost_does_not_trigger_doc_expert is RED because the actual
    config/guardrail_gates.yaml does not yet contain a {change_target: code,
    risk_surface: cost} entry under documentation_gates.non_triggering_classifications.
  - test_unclassified_ac_completes_without_forcing_doc_expert may pass immediately
    (the legacy path already ignores documentation_gates); it is included as a
    regression guard against future code changes that might incorrectly consult
    documentation_gates for unclassified ACs.
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
_GUARDRAIL_CONFIG = _REPO_ROOT / "config" / "guardrail_gates.yaml"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _write_guardrail_yaml(path: Path, content: dict) -> None:
    """Write a guardrail config dict to *path* as YAML.

    Args:
        path: Absolute path where the YAML file will be written.
        content: Dict to serialise as YAML.

    Raises:
        OSError: When the file cannot be written.
        yaml.YAMLError: When the content cannot be serialised.
    """
    try:
        with open(path, "w", encoding="utf-8") as fh:
            yaml.dump(content, fh, default_flow_style=False, allow_unicode=True)
    except OSError as exc:
        _logger.warning("Could not write temp guardrail config %s: %s", path, exc)
        raise


# ---------------------------------------------------------------------------
# Test 1 — cost risk surface must be explicitly excluded
# ---------------------------------------------------------------------------


class TestRiskSurfaceCostDoesNotTriggerDocExpert(unittest.TestCase):
    """AC BO-2200a-3-i: change_target='code' with risk_surface='cost' must NEVER
    require documentation-expert. The cost risk surface is explicitly excluded from
    the triggering set by a non_triggering_classifications entry in guardrail_gates.yaml.

    This class is RED until:
      {change_target: code, risk_surface: cost} is added to
      documentation_gates.non_triggering_classifications in
      config/guardrail_gates.yaml.
    """

    def test_risk_surface_cost_does_not_trigger_doc_expert(self) -> None:
        # covers: BO-2200a-3-i
        """AC BO-2200a-3-i: change_target='code', risk_surface='cost' must NOT produce
        documentation-expert='needed'.

        This is a two-part test:

        Part 1 (RED before implementation): Asserts that the actual
          config/guardrail_gates.yaml explicitly contains
          {change_target: code, risk_surface: cost} under
          documentation_gates.non_triggering_classifications.
          Without this entry the cost surface is excluded only by its absence from
          risk_surface_triggers — the AC requires an EXPLICIT declaration so that
          any future policy expansion cannot silently impose a documentation burden.

        Part 2 (behavioral, green immediately): Uses an adversarial config where
          'cost' IS in risk_surface_triggers AND the exclusion entry IS present,
          then asserts documentation-expert is absent. Confirms the mechanism in
          _build_agents_map correctly reads and applies non_triggering_classifications
          for the cost pair.
        """
        # --- Part 1: Assert explicit config entry in the ACTUAL guardrail config ---
        try:
            with open(_GUARDRAIL_CONFIG, encoding="utf-8") as fh:
                actual_gates = yaml.safe_load(fh)
        except (OSError, yaml.YAMLError) as exc:
            self.fail(f"Could not load guardrail config {_GUARDRAIL_CONFIG}: {exc}")

        doc_gates = (actual_gates or {}).get("documentation_gates") or {}
        non_triggering = doc_gates.get("non_triggering_classifications") or []

        code_cost_excluded = any(
            isinstance(entry, dict)
            and entry.get("change_target") == "code"
            and entry.get("risk_surface") == "cost"
            for entry in non_triggering
        )
        self.assertTrue(
            code_cost_excluded,
            msg=(
                "Expected {change_target: code, risk_surface: cost} in "
                "documentation_gates.non_triggering_classifications in "
                "config/guardrail_gates.yaml — but the entry was absent.\n\n"
                "The cost risk surface must be an EXPLICIT negative declaration: "
                "add the entry to non_triggering_classifications so that any future "
                "expansion of risk_surface_triggers to include 'cost' does NOT "
                "silently impose a documentation burden on code+cost tickets.\n\n"
                "Fix: add the following line to guardrail_gates.yaml under "
                "documentation_gates.non_triggering_classifications:\n"
                "  - {change_target: code, risk_surface: cost}\n"
                "(AC BO-2200a-3-i constraint: cost is explicitly excluded from the "
                "triggering set, not merely absent from it.)"
            ),
        )

        # --- Part 2: Behavioral adversarial confirmation ---
        # Adversarial config: 'cost' IS in risk_surface_triggers (which would normally
        # add documentation-expert), AND the explicit exclusion for (code, cost) IS
        # present. Confirms _build_agents_map reads and applies the exclusion.
        with tempfile.TemporaryDirectory() as tmp_dir:
            adversarial_path = Path(tmp_dir) / "guardrail_gates.yaml"
            adversarial_config: dict = {
                "code": {
                    "cost": [
                        "architect-review",
                        "test-writer",
                        "test-runner",
                        "pr-reviewer",
                    ],
                },
                "documentation_gates": {
                    "change_target_triggers": ["ui", "schema", "pipeline", "docs"],
                    "risk_surface_triggers": [
                        "contract_boundary",
                        "safety",
                        "auth",
                        "privacy",
                        # Adversarial addition: cost now in risk_surface_triggers
                        "cost",
                    ],
                    "non_triggering_classifications": [
                        # Explicit exclusion for (code, cost) — must be read by
                        # _build_agents_map to suppress documentation-expert:
                        {"change_target": "code", "risk_surface": "cost"},
                    ],
                },
            }
            try:
                _write_guardrail_yaml(adversarial_path, adversarial_config)
            except (OSError, yaml.YAMLError) as exc:
                self.fail(f"Could not write adversarial guardrail config: {exc}")

            agents = _build_agents_map(
                "python-coder",
                change_targets=["code"],
                risk_surface="cost",
                guardrail_config_path=adversarial_path,
                agent_registry_path=_AGENT_REGISTRY,
            )

            self.assertNotEqual(
                "needed",
                agents.get("documentation-expert"),
                msg=(
                    "documentation-expert must NOT be 'needed' for "
                    "change_target='code' with risk_surface='cost'. "
                    "The adversarial config has 'cost' in risk_surface_triggers AND "
                    "{change_target: code, risk_surface: cost} in "
                    "non_triggering_classifications — _build_agents_map must read the "
                    "exclusion list and discard documentation-expert for this pair. "
                    "(AC BO-2200a-3-i)"
                ),
            )


# ---------------------------------------------------------------------------
# Test 2 — unclassified AC must never force documentation-expert
# ---------------------------------------------------------------------------


class TestUnclassifiedAcCompletesWithoutForcingDocExpert(unittest.TestCase):
    """AC BO-2200a-3-i: An AC with neither change_target nor risk_surface must
    complete without error and must NOT force documentation-expert from the
    documentation_gates policy.

    The legacy path (change_targets=None, risk_surface=None) is completely
    isolated from documentation_gates — unclassified ACs have no documentation
    burden regardless of policy configuration.

    NOTE: This test may pass immediately (the legacy path already ignores
    documentation_gates). It is kept as a regression guard against future code
    changes that might incorrectly route unclassified ACs through the computed
    path and inadvertently impose a documentation demand.
    """

    def test_unclassified_ac_completes_without_forcing_doc_expert(self) -> None:
        # covers: BO-2200a-3-i
        """AC BO-2200a-3-i: An AC with neither change_target nor risk_surface must
        complete without error and must NOT impose a documentation-expert requirement.

        Uses a maximally adversarial documentation_gates config where EVERY
        change_target and EVERY risk_surface value is in the trigger lists and
        non_triggering_classifications is empty. Even in this worst-case config,
        calling _build_agents_map with change_targets=None and risk_surface=None
        must:
          (a) not raise any exception, and
          (b) not return documentation-expert='needed'.

        This confirms the legacy path (no change_targets, no risk_surface) is fully
        isolated from documentation_gates — the absence of classification is a
        fail-safe to no-demand (AC BO-2200a-3-i constraint).
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            adversarial_path = Path(tmp_dir) / "guardrail_gates.yaml"
            # Maximally adversarial: every change_target and risk_surface triggers
            # documentation-expert; non_triggering_classifications is empty.
            adversarial_config: dict = {
                "code": {
                    "internal": ["test-writer", "test-runner"],
                },
                "documentation_gates": {
                    "change_target_triggers": [
                        "code",
                        "schema",
                        "ui",
                        "infrastructure",
                        "pipeline",
                        "prompt",
                        "model",
                        "config",
                        "docs",
                        "dependency",
                    ],
                    "risk_surface_triggers": [
                        "internal",
                        "contract_boundary",
                        "auth",
                        "privacy",
                        "safety",
                        "cost",
                    ],
                    # Empty — no explicit negatives to fall back on
                    "non_triggering_classifications": [],
                },
            }
            try:
                _write_guardrail_yaml(adversarial_path, adversarial_config)
            except (OSError, yaml.YAMLError) as exc:
                self.fail(f"Could not write adversarial guardrail config: {exc}")

            # Must not raise — the absence of classification (None/None) is a
            # guaranteed fail-safe. Any exception here means the code is broken.
            # We deliberately do NOT wrap in try/except: if _build_agents_map raises,
            # the test fails with the actual traceback, which is the correct signal.
            agents = _build_agents_map(
                "python-coder",
                change_targets=None,
                risk_surface=None,
                guardrail_config_path=adversarial_path,
                agent_registry_path=_AGENT_REGISTRY,
            )

            self.assertNotEqual(
                "needed",
                agents.get("documentation-expert"),
                msg=(
                    "documentation-expert must NOT be 'needed' for an unclassified AC "
                    "(change_targets=None, risk_surface=None). "
                    "Even with a maximally adversarial documentation_gates config that "
                    "triggers doc-expert for every classification, the legacy path must "
                    "be completely isolated — absence of classification is an explicit "
                    "fail-safe to no-demand (AC BO-2200a-3-i)."
                ),
            )


if __name__ == "__main__":
    unittest.main()
