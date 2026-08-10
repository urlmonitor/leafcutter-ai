"""
MODULE: test_bo_2200a_1
GOAL: RED test stubs for AC BO-2200a-1 — a declarative documentation-gates policy
      demands docs for user-facing, data, flow, and docs changes.

TICKET: EPIC-DocumentationCoverageGuarantee/01_TICKET-20260715-BO-2200a-1.md
COVERS: BO-2200a-1

What must be implemented to make these tests green:
  1. Add a `documentation_gates` section to config/guardrail_gates.yaml:
       documentation_gates:
         change_target_triggers: [ui, schema, pipeline, docs]
  2. Modify _build_agents_map in scripts/ac_store/generate_ticket_from_ac.py to:
       - Load `documentation_gates` from the guardrail config YAML.
       - When the AC's change_target(s) intersect `change_target_triggers`, add
         `documentation-expert` to the agents map as 'needed'.
       - The trigger list must be read from config — no hard-coded list in the
         generator — so adding/removing a value is purely a config edit.
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
# These intentionally omit `documentation-expert` from every per-surface gate
# list so that the ONLY source of the documentation-expert requirement in the
# tested scenarios is the `documentation_gates` policy — not a pre-existing
# per-surface rule from the real guardrail_gates.yaml.  Using a temp config
# also isolates the tests from future changes to the real file.
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
    # docs: intentionally NO documentation-expert here — the documentation_gates
    # trigger is the mechanism under test; the legacy per-surface rule must not
    # interfere.
    "docs": {
        "internal": ["pr-reviewer"],
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
    # flow_change_gates intentionally absent so no legacy flow-change path
    # contributes documentation-expert for the (ui|schema|pipeline|docs, internal)
    # test pairs.
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


class TestDocumentationGatesPolicy(unittest.TestCase):
    """Behavioral tests for the declarative documentation-gates policy (BO-2200a-1).

    All three tests use a temporary guardrail config to isolate the
    `documentation_gates` trigger from the existing per-surface rules.
    """

    # -----------------------------------------------------------------------
    # test_change_target_ui_triggers_documentation_expert
    # -----------------------------------------------------------------------

    def test_change_target_ui_triggers_documentation_expert(self) -> None:
        # covers: BO-2200a-1
        """AC BO-2200a-1: change_target='ui' must cause documentation-expert='needed'.

        Given a guardrail config that contains a `documentation_gates` section with
        `change_target_triggers: [ui, schema, pipeline, docs]`, when _build_agents_map
        is called with change_targets=['ui'] and risk_surface='internal', then the
        returned agents map must include documentation-expert with status 'needed'.

        This test will be RED until:
          - config/guardrail_gates.yaml carries the `documentation_gates` section, AND
          - _build_agents_map reads that section and promotes documentation-expert
            to 'needed' when change_target intersects change_target_triggers.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "guardrail_gates.yaml"
            config = dict(_MINIMAL_SURFACE_SECTIONS)
            config["documentation_gates"] = {
                "change_target_triggers": ["ui", "schema", "pipeline", "docs"],
            }
            _write_guardrail_yaml(config_path, config)

            agents = _build_agents_map(
                "python-coder",
                change_targets=["ui"],
                risk_surface="internal",
                guardrail_config_path=config_path,
                agent_registry_path=_AGENT_REGISTRY,
            )

            self.assertEqual(
                "needed",
                agents.get("documentation-expert"),
                msg=(
                    "Expected documentation-expert='needed' when change_target='ui' "
                    "and documentation_gates.change_target_triggers includes 'ui'. "
                    "Implement the documentation_gates read-path in _build_agents_map."
                ),
            )

    # -----------------------------------------------------------------------
    # test_each_triggering_change_target_requires_doc_expert
    # -----------------------------------------------------------------------

    def test_each_triggering_change_target_requires_doc_expert(self) -> None:
        # covers: BO-2200a-1
        """AC BO-2200a-1: each of schema, pipeline, docs independently triggers
        documentation-expert='needed'.

        When the guardrail config lists change_target_triggers: [ui, schema, pipeline,
        docs], calling _build_agents_map with any one of {schema, pipeline, docs} as
        the sole change_target must yield documentation-expert='needed', regardless of
        risk_surface (tested with 'internal').

        This test uses subTest so a failure names the exact failing change_target.
        Will be RED until the documentation_gates read-path is implemented.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "guardrail_gates.yaml"
            config = dict(_MINIMAL_SURFACE_SECTIONS)
            config["documentation_gates"] = {
                "change_target_triggers": ["ui", "schema", "pipeline", "docs"],
            }
            _write_guardrail_yaml(config_path, config)

            for change_target in ("schema", "pipeline", "docs"):
                with self.subTest(change_target=change_target):
                    agents = _build_agents_map(
                        "python-coder",
                        change_targets=[change_target],
                        risk_surface="internal",
                        guardrail_config_path=config_path,
                        agent_registry_path=_AGENT_REGISTRY,
                    )
                    self.assertEqual(
                        "needed",
                        agents.get("documentation-expert"),
                        msg=(
                            f"Expected documentation-expert='needed' when "
                            f"change_target='{change_target}' and "
                            f"documentation_gates.change_target_triggers includes "
                            f"'{change_target}'. "
                            f"Implement the documentation_gates read-path."
                        ),
                    )

    # -----------------------------------------------------------------------
    # test_documentation_gates_is_data_driven_not_hardcoded
    # -----------------------------------------------------------------------

    def test_documentation_gates_is_data_driven_not_hardcoded(self) -> None:
        # covers: BO-2200a-1
        """AC BO-2200a-1: documentation-expert requirement is data-driven, not hard-coded.

        Removing 'ui' from documentation_gates.change_target_triggers must suppress
        the documentation-expert requirement for change_target='ui', while 'schema'
        (which remains in the list) must still require documentation-expert.

        This proves that the trigger is read from the config at call-time, not baked
        into the generator as a literal Python set.

        Red state before implementation:
          - The second assertion (schema triggers doc-expert) will FAIL because the
            code does not yet read documentation_gates.
        Green state after implementation:
          - Both assertions pass: 'ui' is excluded (no doc-expert) and 'schema'
            is included (doc-expert='needed').
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "guardrail_gates.yaml"
            # 'ui' intentionally omitted from change_target_triggers
            config = dict(_MINIMAL_SURFACE_SECTIONS)
            config["documentation_gates"] = {
                "change_target_triggers": ["schema", "pipeline", "docs"],  # no 'ui'
            }
            _write_guardrail_yaml(config_path, config)

            # 'ui' is NOT in triggers — must NOT require documentation-expert
            agents_ui = _build_agents_map(
                "python-coder",
                change_targets=["ui"],
                risk_surface="internal",
                guardrail_config_path=config_path,
                agent_registry_path=_AGENT_REGISTRY,
            )
            self.assertNotEqual(
                "needed",
                agents_ui.get("documentation-expert"),
                msg=(
                    "documentation-expert must NOT be 'needed' when 'ui' is absent "
                    "from documentation_gates.change_target_triggers. "
                    "This confirms the trigger is data-driven, not hard-coded."
                ),
            )

            # 'schema' IS in triggers — must require documentation-expert
            agents_schema = _build_agents_map(
                "python-coder",
                change_targets=["schema"],
                risk_surface="internal",
                guardrail_config_path=config_path,
                agent_registry_path=_AGENT_REGISTRY,
            )
            self.assertEqual(
                "needed",
                agents_schema.get("documentation-expert"),
                msg=(
                    "documentation-expert must be 'needed' when 'schema' IS in "
                    "documentation_gates.change_target_triggers. "
                    "This confirms the config is actively read at call-time."
                ),
            )


if __name__ == "__main__":
    unittest.main()
