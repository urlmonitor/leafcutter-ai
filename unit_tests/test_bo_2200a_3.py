"""
MODULE: test_bo_2200a_3
GOAL: RED test stubs for AC BO-2200a-3 — A purely internal refactor does not demand
      documentation.

TICKET: EPIC-DocumentationCoverageGuarantee/03_TICKET-20260715-BO-2200a-3.md
COVERS: BO-2200a-3

What must be implemented to make these tests green:
  1. Add a `non_triggering_classifications` list under `documentation_gates` in
     config/guardrail_gates.yaml that explicitly declares which (change_target,
     risk_surface) combinations must NEVER require documentation-expert:

       documentation_gates:
         change_target_triggers: [ui, schema, pipeline, docs]
         risk_surface_triggers: [contract_boundary, safety, auth, privacy]
         non_triggering_classifications:
           - {change_target: code, risk_surface: internal}
           - {change_target: config, risk_surface: internal}
           - {change_target: prompt, risk_surface: internal}
           - {change_target: infrastructure, risk_surface: internal}

  2. Modify _build_agents_map in scripts/ac_store/generate_ticket_from_ac.py to
     read `non_triggering_classifications` from `documentation_gates` and DISCARD
     documentation-expert from the computed guardrail set when the call's
     (change_target, risk_surface) pair matches any entry in that list — even if the
     general trigger lists would otherwise add it.

Design notes:
  - Tests use an ADVERSARIAL temp config where code/config/prompt/infrastructure
    ARE in change_target_triggers AND internal IS in risk_surface_triggers. This
    simulates a worst-case policy expansion or misconfiguration.
  - Without an explicit non_triggering_classifications guard in _build_agents_map,
    the generator would add documentation-expert for these combinations.
  - The assertion that no doc-expert appears DESPITE the adversarial config proves
    the negative case is an explicit, tested behavior — not merely the absence of a
    positive rule (AC BO-2200a-3 constraint).
  - This isolation approach mirrors test_bo_2200a_1.py and test_bo_2200a_2.py.
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
# Minimal per-surface guardrail sections.
#
# These define the per-(change_target, risk_surface) gate agents that will be
# included. documentation-expert is intentionally absent from every gate list
# so that the only source of any potential documentation-expert in the result
# is the documentation_gates policy — not a pre-existing gate entry.
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
    },
    "config": {
        "internal": [],
        "contract_boundary": ["status-checker", "pr-reviewer"],
    },
    "prompt": {
        "internal": ["llm-expert"],
        "contract_boundary": ["llm-expert", "architect-review", "pr-reviewer"],
    },
    "infrastructure": {
        "internal": ["pr-reviewer"],
        "contract_boundary": ["architect-review", "pr-reviewer"],
    },
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
    "docs": {
        "internal": [],
        "contract_boundary": ["pr-reviewer"],
    },
}

# ---------------------------------------------------------------------------
# Adversarial documentation_gates config.
#
# CRITICAL DESIGN: `change_target_triggers` includes ALL four internal-refactor
# change_targets (code, config, prompt, infrastructure) and `risk_surface_triggers`
# includes `internal`. Without a non_triggering_classifications guard, _build_agents_map
# would add documentation-expert for any of these paired with risk_surface=internal.
#
# The `non_triggering_classifications` list declares the explicit negative rule.
# The tests assert that documentation-expert is ABSENT even in this adversarial
# config — proving the explicit guard (not absence-of-trigger) is the mechanism.
#
# The tests are RED until _build_agents_map reads non_triggering_classifications
# and discards documentation-expert for matching pairs.
# ---------------------------------------------------------------------------

_ADVERSARIAL_DOC_GATES: dict = {
    "change_target_triggers": [
        # Standard triggering values (BO-2200a-1):
        "ui",
        "schema",
        "pipeline",
        "docs",
        # Adversarial additions — these would trigger doc-expert without the guard:
        "code",
        "config",
        "prompt",
        "infrastructure",
    ],
    "risk_surface_triggers": [
        # Standard triggering values (BO-2200a-2):
        "contract_boundary",
        "safety",
        "auth",
        "privacy",
        # Adversarial addition — this would trigger doc-expert without the guard:
        "internal",
    ],
    # The explicit negative guard (new key — must be read by _build_agents_map):
    "non_triggering_classifications": [
        {"change_target": "code", "risk_surface": "internal"},
        {"change_target": "config", "risk_surface": "internal"},
        {"change_target": "prompt", "risk_surface": "internal"},
        {"change_target": "infrastructure", "risk_surface": "internal"},
    ],
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


class TestCodeInternalDoesNotTriggerDocExpert(unittest.TestCase):
    """AC BO-2200a-3: change_target='code' with risk_surface='internal' must never
    require documentation-expert.

    Test uses an adversarial config where 'code' IS in change_target_triggers AND
    'internal' IS in risk_surface_triggers — so the test is RED until an explicit
    non_triggering_classifications guard is implemented.
    """

    def test_code_internal_does_not_trigger_doc_expert(self) -> None:
        # covers: BO-2200a-3
        """AC BO-2200a-3: change_target='code', risk_surface='internal' must NOT produce
        documentation-expert='needed', even in an adversarial config where 'code' IS in
        change_target_triggers and 'internal' IS in risk_surface_triggers.

        The adversarial config also carries a `non_triggering_classifications` entry for
        (code, internal). _build_agents_map must read that list and discard
        documentation-expert when the pair matches — so the negative constraint is an
        explicit, tested behavior, not merely the absence of a positive rule.

        This test is RED until:
          - _build_agents_map reads documentation_gates.non_triggering_classifications, AND
          - discards documentation-expert from the guardrail set when the call's
            (change_target, risk_surface) pair appears in that list.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "guardrail_gates.yaml"
            config = dict(_MINIMAL_SURFACE_SECTIONS)
            config["documentation_gates"] = _ADVERSARIAL_DOC_GATES
            _write_guardrail_yaml(config_path, config)

            agents = _build_agents_map(
                "python-coder",
                change_targets=["code"],
                risk_surface="internal",
                guardrail_config_path=config_path,
                agent_registry_path=_AGENT_REGISTRY,
            )

            doc_status = agents.get("documentation-expert")
            self.assertNotEqual(
                "needed",
                doc_status,
                msg=(
                    "documentation-expert must NOT be 'needed' for change_target='code' "
                    "with risk_surface='internal'. This is a purely internal code refactor "
                    "that imposes no documentation burden. "
                    "The adversarial config has 'code' in change_target_triggers AND 'internal' "
                    "in risk_surface_triggers — the non_triggering_classifications guard must "
                    "explicitly suppress documentation-expert for this pair. "
                    "Implement the non_triggering_classifications read-path in "
                    "_build_agents_map (AC BO-2200a-3)."
                ),
            )


class TestConfigPromptInfrastructureInternalDoNotTrigger(unittest.TestCase):
    """AC BO-2200a-3: config, prompt, and infrastructure with risk_surface='internal'
    must each never require documentation-expert.

    Tests use the same adversarial config where all four internal-refactor change_targets
    and 'internal' are in their respective trigger lists. The non_triggering_classifications
    guard must suppress documentation-expert for each pair.
    """

    def test_config_prompt_infrastructure_internal_do_not_trigger(self) -> None:
        # covers: BO-2200a-3
        """AC BO-2200a-3: change_target in {config, prompt, infrastructure} with
        risk_surface='internal' must NOT produce documentation-expert='needed', even in
        an adversarial config where each change_target IS in change_target_triggers and
        'internal' IS in risk_surface_triggers.

        Uses subTest so a failure clearly names the failing (change_target, risk_surface)
        pair. All three sub-tests are RED until _build_agents_map reads and applies the
        non_triggering_classifications list from documentation_gates.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "guardrail_gates.yaml"
            config = dict(_MINIMAL_SURFACE_SECTIONS)
            config["documentation_gates"] = _ADVERSARIAL_DOC_GATES
            _write_guardrail_yaml(config_path, config)

            for change_target in ("config", "prompt", "infrastructure"):
                with self.subTest(change_target=change_target, risk_surface="internal"):
                    agents = _build_agents_map(
                        "python-coder",
                        change_targets=[change_target],
                        risk_surface="internal",
                        guardrail_config_path=config_path,
                        agent_registry_path=_AGENT_REGISTRY,
                    )

                    doc_status = agents.get("documentation-expert")
                    self.assertNotEqual(
                        "needed",
                        doc_status,
                        msg=(
                            f"documentation-expert must NOT be 'needed' for "
                            f"change_target='{change_target}' with risk_surface='internal'. "
                            f"This is a purely internal refactor with no observable user-facing "
                            f"or architectural change to document. "
                            f"The adversarial config has '{change_target}' in change_target_triggers "
                            f"AND 'internal' in risk_surface_triggers — the non_triggering_classifications "
                            f"guard must explicitly suppress documentation-expert for this pair. "
                            f"Implement the non_triggering_classifications read-path in "
                            f"_build_agents_map (AC BO-2200a-3)."
                        ),
                    )


if __name__ == "__main__":
    unittest.main()
