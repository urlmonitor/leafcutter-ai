"""
MODULE: test_bo_2200c_3
GOAL: RED tests for BO-2200c-3 — genre resolved from parent L1's documentation_triggers.
BUSINESS CONTEXT: The generator must source the Diataxis genre from the PARENT L1 AC's
    documentation_triggers field, not the leaf's own field. When the parent has multiple
    triggers, each genre must be reflected in the contract lines.
ARCHITECTURE: Tests call _build_agent_contracts_section with an ac_root pointing to a
    temporary directory containing a parent AC YAML. The leaf AC's own documentation_triggers
    is intentionally empty so the test distinguishes parent-sourced vs leaf-sourced genre.

These tests are RED before the BO-2200c-3 implementation because:
  - _build_agent_contracts_section does not accept an ac_root parameter.
  - _extract_doc_genre reads only the LEAF AC's own documentation_triggers field.
  - The parent L1 is never loaded or consulted.

Target file to implement: scripts/ac_store/generate_ticket_from_ac.py
AC source: docs/acceptance-criteria/build-orchestration/
           BO-2200-documentation-coverage-guarantee/BO-2200c-3.yaml
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from generate_ticket_from_ac import _build_agent_contracts_section  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Leaf ID: "BO-9999t-1".
#   derive_parent_id("BO-9999t-1") → "BO-9999t" (strip last segment).
# Parent ID: "BO-9999t".
#   derive_parent_id("BO-9999t") → "BO-9999" (strip trailing alpha "t").
_LEAF_AC_ID = "BO-9999t-1"
_PARENT_AC_ID = "BO-9999t"


def _make_leaf_ac() -> dict:
    """Return a leaf AC whose own documentation_triggers is empty.

    By leaving documentation_triggers empty on the leaf, any genre that appears
    in the contract line MUST come from the parent AC (or from the (unspecified
    genre) marker) — it cannot be a false-positive from the leaf's own field.
    """
    return {
        "id": _LEAF_AC_ID,
        "title": "Test leaf AC for parent genre resolution",
        "component": "build-orchestration",
        "assigned_agent": "python-coder",
        "estimated_complexity": "S",
        "documentation_triggers": [],
        "criteria": (
            "Given a leaf AC with an empty documentation_triggers field,\n"
            "When the generator builds the contract line,\n"
            "Then the genre is resolved from the parent L1's documentation_triggers."
        ),
        "doc_links": [
            {
                "path": "docs/how-to/test-guide.md",
                "relationship": "creates",
                "status": "missing",
            }
        ],
    }


def _make_parent_ac_single_trigger() -> dict:
    """Return a parent L1 AC with a single documentation_triggers entry."""
    return {
        "id": _PARENT_AC_ID,
        "title": "Parent L1 AC — single trigger",
        "level": "L1",
        "documentation_triggers": ["how-to"],
    }


def _make_parent_ac_multi_triggers() -> dict:
    """Return a parent L1 AC with multiple documentation_triggers entries."""
    return {
        "id": _PARENT_AC_ID,
        "title": "Parent L1 AC — multi triggers",
        "level": "L1",
        "documentation_triggers": ["how-to", "sequence-diagram"],
    }


def _make_agents_map_with_doc_expert() -> dict:
    """Return a pre-computed agents map with documentation-expert as needed."""
    return {
        "test-writer": "needed",
        "python-coder": "needed",
        "documentation-expert": "needed",
        "pr-reviewer": "needed",
        "commit": "needed",
        "pull-request": "needed",
    }


def _write_ac_yaml(directory: Path, ac_dict: dict) -> Path:
    """Write an AC dict to a YAML file in *directory*.

    Args:
        directory: Target directory.
        ac_dict: AC record to serialise.

    Returns:
        Path to the written file.
    """
    ac_id = ac_dict.get("id", "unknown")
    path = directory / f"{ac_id}.yaml"
    path.write_text(yaml.dump(ac_dict, allow_unicode=True), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# TestGenreResolvedFromParentL1
# BO-2200c-3
# ---------------------------------------------------------------------------


class TestGenreResolvedFromParentL1(unittest.TestCase):
    """BO-2200c-3: Genre is sourced from the parent L1's documentation_triggers,
    not the leaf's own field.

    RED before implementation: _build_agent_contracts_section ignores the
    parent L1 and calls _extract_doc_genre(ac) on the leaf, which reads the
    leaf's own documentation_triggers. Because the leaf fixture has an empty
    documentation_triggers list, the current implementation returns the
    fallback genre "explanation" — not "how-to" from the parent.

    Fix: resolve the parent L1 via _load_parent_ac(ac_id, ac_root), read its
    documentation_triggers, and use those genres in the contract lines.
    """

    def test_genre_resolved_from_parent_l1_documentation_triggers(self) -> None:
        # covers: BO-2200c-3
        """Generating a contract line for a leaf AC resolves the parent L1 and
        sources the genre from the parent's documentation_triggers.

        Fixture: leaf has documentation_triggers: [] (empty). Parent has
        documentation_triggers: ["how-to"]. The genre "how-to" must appear
        in the contract line — it can only come from the parent.

        Red state (current): _extract_doc_genre returns the fallback "explanation"
        because the leaf's own documentation_triggers is empty. The parent is never
        consulted. "how-to" is absent from the output.

        Green state (after fix): _build_agent_contracts_section resolves the parent
        and uses "how-to" from the parent's documentation_triggers.
        """
        leaf_ac = _make_leaf_ac()
        agents_map = _make_agents_map_with_doc_expert()

        with tempfile.TemporaryDirectory() as tmp:
            ac_root = Path(tmp)
            _write_ac_yaml(ac_root, _make_parent_ac_single_trigger())

            section = _build_agent_contracts_section(
                leaf_ac,
                _LEAF_AC_ID,
                agents_map,
                ac_root=ac_root,
            )

        self.assertIn(
            "### documentation-expert",
            section,
            "The '### documentation-expert' subsection must be present.\n"
            f"Actual section:\n{section}",
        )
        self.assertIn(
            "[how-to]",
            section,
            "Genre 'how-to' (from parent's documentation_triggers) must appear in "
            "the contract line. The leaf's own documentation_triggers is empty, so "
            "'how-to' can only come from the resolved parent L1.\n\n"
            "Red state: _extract_doc_genre(leaf_ac) returns 'explanation' (fallback) "
            "because the leaf has no triggers. The parent is never consulted.\n\n"
            f"Actual section:\n{section}",
        )

    def test_multiple_parent_triggers_each_reflected(self) -> None:
        # covers: BO-2200c-3
        """When the parent L1 declares multiple documentation_triggers, each genre
        is reflected in the contract lines.

        Fixture: parent has documentation_triggers: ["how-to", "sequence-diagram"].
        Both genre strings must appear in the contract section.

        Red state (current): only one genre is ever emitted (the first from the leaf,
        but since the leaf is empty, "explanation" is returned and "sequence-diagram"
        never appears).

        Green state (after fix): one AC-N line is emitted per genre, so both
        "how-to" and "sequence-diagram" appear in the section.
        """
        leaf_ac = _make_leaf_ac()
        agents_map = _make_agents_map_with_doc_expert()

        with tempfile.TemporaryDirectory() as tmp:
            ac_root = Path(tmp)
            _write_ac_yaml(ac_root, _make_parent_ac_multi_triggers())

            section = _build_agent_contracts_section(
                leaf_ac,
                _LEAF_AC_ID,
                agents_map,
                ac_root=ac_root,
            )

        self.assertIn(
            "how-to",
            section,
            "First genre 'how-to' must be reflected in the contract section.\n"
            f"Actual section:\n{section}",
        )
        self.assertIn(
            "sequence-diagram",
            section,
            "Second genre 'sequence-diagram' must be reflected in the contract section. "
            "Both parent triggers must produce a contract line, not just the first.\n\n"
            f"Actual section:\n{section}",
        )


if __name__ == "__main__":
    unittest.main()
