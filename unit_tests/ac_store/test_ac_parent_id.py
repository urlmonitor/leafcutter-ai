"""
MODULE: test_ac_parent_id
GOAL: Unit tests for derive_parent_id() and is_root_ac() in ac_parent_id.py.
TICKET: EPIC-AcParentChildLinkEnforcement/01_TICKET-20260607-ACS-100i-1.md
COVERS: ACS-100i-1

These tests verify the four Gherkin scenarios from ACS-100i-1:
  - ACS-300h-1   → ACS-300h  (strip last hyphen segment "-1")
  - ACS-300h-2-i → ACS-300h-2 (strip last hyphen segment "-i")
  - ACS-100      → None       (root pattern, no parent)
  - ACS-100a     → ACS-100    (strip trailing alpha suffix "a")
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from ac_parent_id import derive_parent_id, is_root_ac  # noqa: E402


# ---------------------------------------------------------------------------
# ACS-100i-1 Gherkin scenarios — four canonical examples
# ---------------------------------------------------------------------------


class TestDeriveParentIdGherkinScenarios:
    """Direct coverage of the four Gherkin scenarios in ACS-100i-1."""

    def test_scenario_1_strip_numeric_suffix(self) -> None:
        # covers: ACS-100i-1
        """ACS-300h-1 → ACS-300h: strip last hyphen-delimited segment '-1'."""
        result = derive_parent_id("ACS-300h-1")
        assert result == "ACS-300h", (
            f"Expected 'ACS-300h' from 'ACS-300h-1', got {result!r}"
        )

    def test_scenario_2_strip_letter_suffix(self) -> None:
        # covers: ACS-100i-1
        """ACS-300h-2-i → ACS-300h-2: strip last hyphen-delimited segment '-i'."""
        result = derive_parent_id("ACS-300h-2-i")
        assert result == "ACS-300h-2", (
            f"Expected 'ACS-300h-2' from 'ACS-300h-2-i', got {result!r}"
        )

    def test_scenario_3_root_has_no_parent(self) -> None:
        # covers: ACS-100i-1
        """ACS-100 → None: root pattern PREFIX-NNN, no parent."""
        result = derive_parent_id("ACS-100")
        assert result is None, (
            f"Expected None for root AC 'ACS-100', got {result!r}"
        )

    def test_scenario_4_strip_alpha_sublevel_suffix(self) -> None:
        # covers: ACS-100i-1
        """ACS-100a → ACS-100: strip trailing alpha suffix 'a' after PREFIX-NNN."""
        result = derive_parent_id("ACS-100a")
        assert result == "ACS-100", (
            f"Expected 'ACS-100' from 'ACS-100a', got {result!r}"
        )


# ---------------------------------------------------------------------------
# Additional coverage — common AC ID patterns in the real store
# ---------------------------------------------------------------------------


class TestDeriveParentIdRealPatterns:
    """Additional tests using patterns observed in the real AC store."""

    def test_three_level_depth(self) -> None:
        # covers: ACS-100i-1
        """ACS-400a-3-i → ACS-400a-3 (strip '-i')."""
        assert derive_parent_id("ACS-400a-3-i") == "ACS-400a-3"

    def test_l2_to_l1_alpha(self) -> None:
        # covers: ACS-100i-1
        """ACS-400a-3 → ACS-400a (strip '-3')."""
        assert derive_parent_id("ACS-400a-3") == "ACS-400a"

    def test_l1_alpha_to_l0_root(self) -> None:
        # covers: ACS-100i-1
        """ACS-400a → ACS-400 (strip trailing 'a')."""
        assert derive_parent_id("ACS-400a") == "ACS-400"

    def test_root_l0_returns_none(self) -> None:
        # covers: ACS-100i-1
        """ACS-400 → None (root)."""
        assert derive_parent_id("ACS-400") is None

    def test_multi_letter_prefix(self) -> None:
        # covers: ACS-100i-1
        """FIN-001 → None (six-char prefix at root)."""
        assert derive_parent_id("FIN-001") is None

    def test_multi_letter_prefix_with_child(self) -> None:
        # covers: ACS-100i-1
        """FIN-001a → FIN-001 (alpha sub-level on multi-letter prefix)."""
        assert derive_parent_id("FIN-001a") == "FIN-001"

    def test_two_letter_prefix_root(self) -> None:
        # covers: ACS-100i-1
        """BP-042 → None (two-letter prefix, root)."""
        assert derive_parent_id("BP-042") is None

    def test_two_letter_prefix_child(self) -> None:
        # covers: ACS-100i-1
        """BP-042a → BP-042."""
        assert derive_parent_id("BP-042a") == "BP-042"

    def test_numeric_only_segment_suffix(self) -> None:
        # covers: ACS-100i-1
        """ACS-100a-2 → ACS-100a (numeric segment stripped)."""
        assert derive_parent_id("ACS-100a-2") == "ACS-100a"

    def test_multi_alpha_suffix_at_sublevel(self) -> None:
        # covers: ACS-100i-1
        """ACS-100ab → ACS-100 (multi-letter alpha suffix stripped)."""
        assert derive_parent_id("ACS-100ab") == "ACS-100"


# ---------------------------------------------------------------------------
# is_root_ac() tests
# ---------------------------------------------------------------------------


class TestIsRootAc:
    """Unit tests for the is_root_ac() helper."""

    @pytest.mark.parametrize(
        "ac_id",
        ["ACS-100", "ACS-400", "FIN-001", "BP-042", "AUTH-007"],
    )
    def test_root_ids_return_true(self, ac_id: str) -> None:
        # covers: ACS-100i-1
        assert is_root_ac(ac_id), f"Expected is_root_ac({ac_id!r}) to be True"

    @pytest.mark.parametrize(
        "ac_id",
        ["ACS-100a", "ACS-100a-1", "ACS-300h-1", "ACS-300h-2-i", "FIN-001a"],
    )
    def test_non_root_ids_return_false(self, ac_id: str) -> None:
        # covers: ACS-100i-1
        assert not is_root_ac(ac_id), f"Expected is_root_ac({ac_id!r}) to be False"
