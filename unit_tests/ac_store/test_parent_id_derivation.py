"""
MODULE: test_parent_id_derivation
GOAL: Unit tests for derive_parent_id() in scan_ac_store.py.
TICKET: EPIC-AcParentChildLinkEnforcement/01_TICKET-20260607-ACS-100i-1.md
COVERS: ACS-100i-1
"""

from __future__ import annotations

import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from scan_ac_store import derive_parent_id  # noqa: E402


# ---------------------------------------------------------------------------
# ACS-100i-1: derive_parent_id strips the last segment
# ---------------------------------------------------------------------------


class TestDeriveParentIdBasicCases:
    """AC-1 (ACS-100i-1): parent ID is derived by stripping the last segment."""

    def test_strip_last_numeric_segment(self) -> None:
        # covers: ACS-100i-1
        """ACS-100i-1: ACS-300h-1 → parent is ACS-300h."""
        assert derive_parent_id("ACS-300h-1") == "ACS-300h"

    def test_strip_last_letter_segment_after_hyphen(self) -> None:
        # covers: ACS-100i-1
        """ACS-100i-1: ACS-300h-2-i → parent is ACS-300h-2."""
        assert derive_parent_id("ACS-300h-2-i") == "ACS-300h-2"

    def test_root_pattern_has_no_parent(self) -> None:
        # covers: ACS-100i-1
        """ACS-100i-1: ACS-100 is the root pattern (PREFIX-NNN) — returns None."""
        assert derive_parent_id("ACS-100") is None

    def test_level1_letter_suffix_parent_is_root(self) -> None:
        # covers: ACS-100i-1
        """ACS-100i-1: ACS-100a → parent is ACS-100 (strip the -a suffix)."""
        assert derive_parent_id("ACS-100a") == "ACS-100"


class TestDeriveParentIdEdgeCases:
    """Additional edge cases for derive_parent_id()."""

    def test_root_pattern_three_digit_prefix(self) -> None:
        # covers: ACS-100i-1
        """Longer prefix still treated as root when format is PREFIX-NNN."""
        assert derive_parent_id("ACD-050") is None

    def test_level1_multi_letter_suffix(self) -> None:
        # covers: ACS-100i-1
        """Level-1 ID with multi-letter suffix (e.g. ACS-100ab) → root ACS-100."""
        assert derive_parent_id("ACS-100ab") == "ACS-100"

    def test_level2_numeric_segment(self) -> None:
        # covers: ACS-100i-1
        """Level-2 numeric segment stripped: ACD-050a-1 → ACD-050a."""
        assert derive_parent_id("ACD-050a-1") == "ACD-050a"

    def test_level3_letter_segment(self) -> None:
        # covers: ACS-100i-1
        """Level-3 letter segment stripped: ACD-050a-1-i → ACD-050a-1."""
        assert derive_parent_id("ACD-050a-1-i") == "ACD-050a-1"

    def test_actual_ticket_source_ac(self) -> None:
        # covers: ACS-100i-1
        """ACS-100i-1 is the source AC for this ticket; its parent is ACS-100i."""
        assert derive_parent_id("ACS-100i-1") == "ACS-100i"

    def test_level1_of_source_ac(self) -> None:
        # covers: ACS-100i-1
        """ACS-100i parent is ACS-100 (root)."""
        assert derive_parent_id("ACS-100i") == "ACS-100"

    def test_source_root_ac_no_parent(self) -> None:
        # covers: ACS-100i-1
        """ACS-100 (root of source AC chain) has no parent."""
        assert derive_parent_id("ACS-100") is None

    def test_various_root_patterns(self) -> None:
        # covers: ACS-100i-1
        """Multiple root patterns from different components all return None."""
        for root_id in ("FIN-001", "BP-042", "AUTH-007", "ACS-300", "ACD-200"):
            assert derive_parent_id(root_id) is None, (
                f"Expected None for root {root_id!r}, got {derive_parent_id(root_id)!r}"
            )

    def test_return_type_is_str_or_none(self) -> None:
        # covers: ACS-100i-1
        """derive_parent_id always returns str or None, never other types."""
        result_none = derive_parent_id("ACS-100")
        result_str = derive_parent_id("ACS-100a")
        assert result_none is None
        assert isinstance(result_str, str)

    def test_depth_three_chain_traversal(self) -> None:
        # covers: ACS-100i-1
        """Verifying the full depth chain: ACS-300h-2-i → ACS-300h-2 → ACS-300h → ACS-300 (None)."""
        assert derive_parent_id("ACS-300h-2-i") == "ACS-300h-2"
        assert derive_parent_id("ACS-300h-2") == "ACS-300h"
        assert derive_parent_id("ACS-300h") == "ACS-300"
        assert derive_parent_id("ACS-300") is None
