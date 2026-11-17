"""
MODULE: test_generate_ticket_from_ac_bo510
GOAL: BO-510-1 registry checks: every agent_registry.json entry carries a 'produces' value from the
      defined enum, and the role -> produces mapping holds, with the ACD-2500f-2 exception: an agent
      whose registry entry or template frontmatter declares a mutates surface on the requirement store
      (docs/acceptance-criteria/) must produce requirement_records; every other agent keeps the role
      mapping.
BUSINESS CONTEXT: Moved verbatim (class TestBO510Registry and the two constants only it uses) out of
      test_generate_ticket_from_ac.py, which is far over its size limit, so the ACD-2500f-2 exception
      could be written out normally. ACD-2500f-2 amended the produces guidance: writing requirement
      records outranks the role signal.
COVERS: BO-510-1
"""

from __future__ import annotations

import json as _json
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_generate_ticket_from_ac import _AGENT_REGISTRY_PATH, _REPO_ROOT  # noqa: E402

_REQUIREMENT_STORE = "docs/acceptance-criteria/"

# Enum values from BO-510-1 AC definition.
_VALID_PRODUCES_ENUM = frozenset({
    "production_code",
    "documentation",
    "configuration",
    "prompt",
    "review_verdict",
    "orchestration",
    "test_artifact",
    "analysis",
    "requirement_records",
})

# Role → produces mapping from BO-510-1 criteria
_ROLE_PRODUCES_MAPPING = {
    "coding": "production_code",
    "documentation": "documentation",
    "review": "review_verdict",
    "orchestration": "orchestration",
    "quality": "test_artifact",
    "analysis": "analysis",
}


def _writes_requirement_store(agent: dict) -> bool:
    """ACD-2500f-2: True when the registry entry or the agent's template declares a mutates surface
    on the requirement store (the templates carry mutates; the registry entries normally do not)."""
    text = (_REPO_ROOT / agent["template_path"]).read_text(encoding="utf-8")
    match = re.match(r"---\r?\n(.*?)\r?\n---", text, re.DOTALL)
    front = yaml.safe_load(match.group(1)) if match else {}
    mutates = list(agent.get("mutates") or []) + list((front or {}).get("mutates") or [])
    return any(_REQUIREMENT_STORE in str(entry.get("surface", "")) for entry in mutates if isinstance(entry, dict))


# ---------------------------------------------------------------------------
# TestBO510Registry
# BO-510-1: Agent registry entries carry a produces trait field from a defined enum
# ---------------------------------------------------------------------------


class TestBO510Registry:
    """BO-510-1: Every agent_registry.json entry carries a 'produces' field
    with a value from the 9-member enum; the role→produces mapping is consistent.
    """

    def test_bo510_1_all_registry_entries_have_produces_field(self) -> None:
        # covers: BO-510-1
        """BO-510-1: Every entry in agent_registry.json must have a 'produces' field
        (not absent and not null). The field is required by the BO-510-1 schema contract.
        """
        assert _AGENT_REGISTRY_PATH.exists(), (
            f"agent_registry.json not found at {_AGENT_REGISTRY_PATH}"
        )
        with open(_AGENT_REGISTRY_PATH, encoding="utf-8") as fh:
            registry = _json.load(fh)

        missing = []
        for agent in registry.get("agents", []):
            agent_id = agent.get("id", "<unknown>")
            if "produces" not in agent or agent["produces"] is None:
                missing.append(agent_id)

        assert not missing, (
            f"BO-510-1: The following agents are missing the 'produces' field or have "
            f"produces: null:\n  {missing}\n\n"
            "Every agent entry must carry a non-null 'produces' field per BO-510-1."
        )

    def test_bo510_1_produces_values_match_defined_enum(self) -> None:
        # covers: BO-510-1
        """BO-510-1: Every produces field value must be one of the 9-member enum:
        production_code, documentation, configuration, prompt, review_verdict,
        orchestration, test_artifact, analysis.
        """
        with open(_AGENT_REGISTRY_PATH, encoding="utf-8") as fh:
            registry = _json.load(fh)

        invalid = []
        for agent in registry.get("agents", []):
            agent_id = agent.get("id", "<unknown>")
            produces = agent.get("produces")
            if produces is not None and produces not in _VALID_PRODUCES_ENUM:
                invalid.append(f"{agent_id}: {produces!r}")

        assert not invalid, (
            f"BO-510-1: The following agents have produces values outside the defined enum "
            f"{sorted(_VALID_PRODUCES_ENUM)}:\n  " + "\n  ".join(invalid)
        )

    def test_bo510_1_role_coding_maps_to_production_code(self) -> None:
        # covers: BO-510-1
        """BO-510-1: Agents with role='coding' must have produces='production_code'.

        The AC criteria states: 'agents with role "coding" have produces: production_code'.

        ACD-2500f-2 exception: an agent whose registry entry or template declares a mutates
        surface on the requirement store must produce requirement_records; every other agent
        keeps the role mapping.
        """
        with open(_AGENT_REGISTRY_PATH, encoding="utf-8") as fh:
            registry = _json.load(fh)

        violations = []
        for agent in registry.get("agents", []):
            role = agent.get("role", "")
            produces = agent.get("produces")
            agent_id = agent.get("id", "<unknown>")
            if _writes_requirement_store(agent):
                # ACD-2500f-2: writing requirement records outranks the role signal.
                expected = "requirement_records"
            elif role in _ROLE_PRODUCES_MAPPING:
                expected = _ROLE_PRODUCES_MAPPING[role]
            else:
                continue
            if produces != expected:
                violations.append(
                    f"{agent_id}: role={role!r} → expected produces={expected!r}, "
                    f"got {produces!r}"
                )

        assert not violations, (
            "BO-510-1: Role→produces mapping violated for the following agents:\n  "
            + "\n  ".join(violations)
            + "\n\nExpected mapping: "
            + str(_ROLE_PRODUCES_MAPPING)
        )
