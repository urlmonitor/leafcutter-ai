"""
MODULE: test_bo_2200a_4
GOAL: RED test stubs for AC BO-2200a-4 — A list-valued change target triggers
      documentation if any element triggers (union semantics).

TICKET: EPIC-DocumentationCoverageGuarantee/05_TICKET-20260715-BO-2200a-4.md
COVERS: BO-2200a-4

AC BO-2200a-4 criteria:
  Given the declarative documentation_gates policy and the ticket generator building
    the agents map for a leaf AC whose change_target is a list,
  When change_target is [config, code] (no element in the triggering set) and
    risk_surface is internal,
  Then the generated agents map does NOT include documentation-expert.
  And when change_target is [config, ui] (at least one element, ui, is in the
    triggering set), the generated agents map DOES include documentation-expert.
  And the policy evaluates a list-valued change_target as the union of its elements:
    the documentation demand is raised when ANY element is in the triggering set.

What must be implemented (or fixed) to make these tests green:
  1. _build_agents_map in scripts/ac_store/generate_ticket_from_ac.py must handle
     list-valued change_targets with UNION semantics:
     - If ANY element of change_targets is in documentation_gates.change_target_triggers,
       documentation-expert must be added.
     - The non_triggering_classifications check must NOT suppress documentation-expert
       when a DIFFERENT element in change_targets independently triggers it via
       change_target_triggers. Non-triggering for one element cannot cancel a trigger
       from another element (union semantics).

Design notes:
  test_list_change_target_no_triggering_element_no_doc_expert:
    Uses a simple config (no non_triggering, no risk_surface_triggers).
    Tests [config, code] with risk_surface=internal — neither element is in the
    trigger set, so no documentation-expert. This test passes with the current
    implementation (the "none triggers" case already works). It is included to
    verify that list-valued change_targets do NOT accidentally trigger
    documentation-expert when no element matches the trigger set.

  test_list_change_target_any_triggering_element_requires_doc_expert:
    Uses an adversarial config where:
      - 'ui' IS in change_target_triggers (triggers documentation-expert)
      - {change_target: config, risk_surface: internal} IS in non_triggering_classifications
    Tests [config, ui] with risk_surface=internal.
    The adversarial design proves the union-semantics bug in the current implementation:
      - 'ui' in change_targets correctly adds documentation-expert via the trigger check
      - BUT non_triggering logic then checks "entry_ct in change_targets" which fires for
        config, and INCORRECTLY discards documentation-expert
      - After the correct fix, the non_triggering_classifications entry for (config, internal)
        must NOT suppress documentation-expert when a different element (ui) independently
        triggers it.
    This test is RED until the union-semantics fix lands in _build_agents_map.
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
# Shared per-surface guardrail sections.
#
# documentation-expert is intentionally absent from every gate list so that
# the only source of any potential documentation-expert in the result is the
# documentation_gates policy — not a pre-existing per-surface rule.
# ---------------------------------------------------------------------------

_MINIMAL_SURFACE_SECTIONS: dict = {
    "ui": {
        "internal": ["test-writer", "test-runner"],
        "contract_boundary": [
            "architect-review",
            "test-writer",
            "test-runner",
            "pr-reviewer",
        ],
    },
    "config": {
        "internal": [],
        "contract_boundary": ["pr-reviewer"],
    },
    "code": {
        "internal": ["test-writer", "test-runner"],
        "contract_boundary": [
            "architect-review",
            "test-writer",
            "test-runner",
            "pr-reviewer",
        ],
    },
    "schema": {
        "internal": ["architect-review", "test-writer"],
        "contract_boundary": [
            "architect-review",
            "test-writer",
            "test-runner",
            "pr-reviewer",
        ],
    },
    "pipeline": {
        "internal": ["pr-reviewer"],
        "contract_boundary": ["architect-review", "pr-reviewer"],
    },
    "docs": {
        "internal": ["pr-reviewer"],
        "contract_boundary": ["pr-reviewer"],
    },
}


def _write_guardrail_yaml(path: Path, content: dict) -> None:
    """Write a guardrail config dict to *path* as YAML.

    Args:
        path: Absolute path where the YAML file will be written.
        content: Dict to serialise as YAML.

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


class TestListChangeTargetNoTriggeringElement(unittest.TestCase):
    """AC BO-2200a-4: When no element of a list-valued change_target is in the
    triggering set, documentation-expert must NOT appear in the agents map.

    Negative case: change_target=[config, code] with risk_surface=internal yields
    no documentation-expert because neither 'config' nor 'code' is in
    change_target_triggers: [ui, schema, pipeline, docs].
    """

    def test_list_change_target_no_triggering_element_no_doc_expert(self) -> None:
        # covers: BO-2200a-4
        """AC BO-2200a-4 (negative): change_target=[config, code] with risk_surface=
        internal must NOT yield documentation-expert.

        Given a guardrail config with change_target_triggers: [ui, schema, pipeline,
        docs] and no non_triggering_classifications, when _build_agents_map is called
        with change_targets=['config', 'code'] and risk_surface='internal', the
        returned agents map must NOT include documentation-expert: 'needed'.

        Neither 'config' nor 'code' is in the triggering set, so the union of the
        two elements does not intersect the trigger list — no documentation-expert
        should be added.

        This test verifies the absence of spurious triggers for list-valued
        change_targets where NO element matches the trigger set.

        Note: This test passes with the current implementation (the "none triggers"
        negative case is already handled correctly). It guards against regressions
        where a list-valued change_target might accidentally trigger documentation-expert
        when no element is in the trigger set.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "guardrail_gates.yaml"
            config = dict(_MINIMAL_SURFACE_SECTIONS)
            config["documentation_gates"] = {
                "change_target_triggers": ["ui", "schema", "pipeline", "docs"],
                # No non_triggering_classifications — testing the pure negative case.
            }
            _write_guardrail_yaml(config_path, config)

            agents = _build_agents_map(
                "python-coder",
                change_targets=["config", "code"],
                risk_surface="internal",
                guardrail_config_path=config_path,
                agent_registry_path=_AGENT_REGISTRY,
            )

            doc_status = agents.get("documentation-expert")
            self.assertNotEqual(
                "needed",
                doc_status,
                msg=(
                    "documentation-expert must NOT be 'needed' when "
                    "change_target=['config', 'code'] and risk_surface='internal'. "
                    "Neither 'config' nor 'code' is in change_target_triggers "
                    "[ui, schema, pipeline, docs], so the union of list elements "
                    "does not trigger documentation-expert. "
                    "Verify that list-valued change_targets do not spuriously "
                    "trigger documentation-expert (AC BO-2200a-4)."
                ),
            )


class TestListChangeTargetUnionSemanticsRequiresDocExpert(unittest.TestCase):
    """AC BO-2200a-4: When at least one element of a list-valued change_target is
    in the triggering set, documentation-expert MUST appear in the agents map.

    Union-semantics case: change_target=[config, ui] with risk_surface=internal.
    'ui' IS in change_target_triggers — so the union-semantics rule fires and
    documentation-expert must be required even though 'config' is NOT a trigger.

    ADVERSARIAL CONFIG DESIGN (intentional):
    The guardrail config carries non_triggering_classifications that includes
    {change_target: config, risk_surface: internal}. This simulates the real
    guardrail_gates.yaml behavior and exposes the union-semantics bug:

      Current buggy behavior in _build_agents_map:
        1. 'ui' in change_targets triggers documentation-expert → added to guardrail_set
        2. non_triggering_classifications loop fires because
           "entry_ct='config' in change_targets=['config', 'ui']" evaluates True
        3. documentation-expert is INCORRECTLY discarded

      Expected behavior after the AC BO-2200a-4 fix:
        1. 'ui' triggers documentation-expert → added to guardrail_set
        2. non_triggering entry for (config, internal) must NOT suppress
           documentation-expert because 'ui' independently triggered it — the
           union-semantics rule ensures that a non-triggering entry for one element
           cannot cancel a trigger from a different element in the same list.
        3. documentation-expert remains in the agents map as 'needed'.

    This test is RED until the union-semantics fix lands in _build_agents_map.
    """

    def test_list_change_target_any_triggering_element_requires_doc_expert(self) -> None:
        # covers: BO-2200a-4
        """AC BO-2200a-4 (union semantics): change_target=[config, ui] must yield
        documentation-expert='needed' because 'ui' IS in change_target_triggers.

        Uses an adversarial guardrail config where:
          - change_target_triggers: [ui, schema, pipeline, docs]   — 'ui' triggers
          - non_triggering_classifications: [{change_target: config, risk_surface: internal}]
            — 'config' is explicitly non-triggering for risk_surface=internal

        With change_targets=['config', 'ui'] and risk_surface='internal', the
        union of change_targets intersects the trigger set (via 'ui'). Therefore
        documentation-expert MUST be required.

        The adversarial non_triggering_classifications entry for (config, internal)
        must NOT cancel the trigger raised by the separate 'ui' element — the fix
        must ensure that non-triggering for ONE element in a list cannot suppress
        the documentation demand raised by a DIFFERENT element.

        This test is RED until _build_agents_map is fixed to apply union semantics
        correctly: non_triggering_classifications entries only suppress
        documentation-expert when NO element in change_targets independently
        triggers it (AC BO-2200a-4).
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "guardrail_gates.yaml"
            config = dict(_MINIMAL_SURFACE_SECTIONS)
            config["documentation_gates"] = {
                "change_target_triggers": ["ui", "schema", "pipeline", "docs"],
                # Adversarial: 'config' is non-triggering for (config, internal).
                # This simulates the real guardrail_gates.yaml and exposes the bug:
                # the current code discards documentation-expert because
                # entry_ct='config' is found in change_targets=['config', 'ui'],
                # even though 'ui' independently triggers it.
                "non_triggering_classifications": [
                    {"change_target": "config", "risk_surface": "internal"},
                ],
            }
            _write_guardrail_yaml(config_path, config)

            agents = _build_agents_map(
                "python-coder",
                change_targets=["config", "ui"],
                risk_surface="internal",
                guardrail_config_path=config_path,
                agent_registry_path=_AGENT_REGISTRY,
            )

            doc_status = agents.get("documentation-expert")
            self.assertEqual(
                "needed",
                doc_status,
                msg=(
                    "Expected documentation-expert='needed' when "
                    "change_target=['config', 'ui'] because 'ui' IS in "
                    "change_target_triggers [ui, schema, pipeline, docs]. "
                    "The union-semantics rule requires that a non_triggering entry "
                    "for (config, internal) must NOT cancel the trigger raised by "
                    "the separate 'ui' element. "
                    "Current buggy behavior: the non_triggering_classifications check "
                    "fires because 'config' is found in change_targets=['config', 'ui'] "
                    "and incorrectly discards documentation-expert even though 'ui' "
                    "independently triggered it. "
                    "Fix _build_agents_map to apply union semantics: non-triggering "
                    "for one element cannot suppress a trigger from a different element "
                    "(AC BO-2200a-4)."
                ),
            )


if __name__ == "__main__":
    unittest.main()
