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


# ---------------------------------------------------------------------------
# Edge-case coverage — malformed, degenerate, and unexpected inputs
# ---------------------------------------------------------------------------


class TestDeriveParentIdEdgeCases:
    """Edge-case tests for derive_parent_id() covering malformed and unexpected inputs.

    These tests probe the boundaries of Rule 3 (rfind fallback), the regex
    anchors, and the absence of any explicit type-guard on the public API.
    They are intentionally descriptive: each test states what the function
    *currently does*, so that any future change to the contract surfaces
    immediately as a test failure rather than silent drift.
    """

    # -- Empty / whitespace inputs ------------------------------------------

    def test_empty_string_returns_none(self) -> None:
        """Empty string: no hyphen found, rfind returns -1 → returns None.

        Rule 3 falls through (no root match, no alpha match). rfind('-') == -1,
        so the function returns None (treated as root-equivalent).
        """
        result = derive_parent_id("")
        assert result is None, (
            f"Expected None for empty string input, got {result!r}"
        )

    def test_whitespace_only_returns_none(self) -> None:
        """Whitespace-only string: no hyphen → rfind returns -1 → returns None.

        Whitespace does not match either compiled pattern, and '   '.rfind('-')
        == -1, so the function returns None (root-equivalent branch).
        """
        result = derive_parent_id("   ")
        assert result is None, (
            f"Expected None for whitespace-only input, got {result!r}"
        )

    # -- No-hyphen inputs ----------------------------------------------------

    def test_single_segment_no_dash_returns_none(self) -> None:
        """Single-segment ID with no dash (e.g. 'ACS'): no hyphen → None.

        'ACS' does not match _ROOT_PATTERN (requires 'PREFIX-NNN'), does not
        match _ALPHA_SUBLEVEL_PATTERN, and rfind('-') == -1, so returns None.
        """
        result = derive_parent_id("ACS")
        assert result is None, (
            f"Expected None for 'ACS' (no hyphen), got {result!r}"
        )

    def test_numeric_only_segments_no_prefix_hyphen(self) -> None:
        """ID like '100-200-300': has hyphens but no uppercase prefix.

        Neither compiled pattern anchors match (no uppercase prefix). Rule 3
        fires: rfind('-') finds the last '-', returning '100-200'.
        """
        result = derive_parent_id("100-200-300")
        assert result == "100-200", (
            f"Expected '100-200' from '100-200-300', got {result!r}"
        )

    # -- Trailing dash -------------------------------------------------------

    def test_trailing_dash_strips_to_base(self) -> None:
        """ID with trailing dash (e.g. 'ACS-100-'): rfind strips after last '-'.

        Neither pattern matches 'ACS-100-'. rfind('-') finds position 7
        (the final '-'), and ac_id[:7] == 'ACS-100'. So the result is 'ACS-100'.

        Note: 'ACS-100' is a valid root ID, but derive_parent_id() does NOT
        recursively validate the result — it just returns the stripped string.
        """
        result = derive_parent_id("ACS-100-")
        assert result == "ACS-100", (
            f"Expected 'ACS-100' from 'ACS-100-', got {result!r}"
        )

    # -- All-dashes input ----------------------------------------------------

    def test_only_dashes_strips_to_before_last_dash(self) -> None:
        """ID composed only of dashes (e.g. '---'): rfind returns last dash index.

        '---' does not match either pattern. rfind('-') is 2 (last char),
        ac_id[:2] == '--'. Returns '--'.
        """
        result = derive_parent_id("---")
        assert result == "--", (
            f"Expected '--' from '---', got {result!r}"
        )

    # -- Deep nesting --------------------------------------------------------

    def test_very_deeply_nested_strips_one_level(self) -> None:
        """Very deeply nested ID (e.g. 'ACS-100a-1b-2c-3d-4e'): strips last segment.

        Rule 3 fires (no pattern match). rfind('-') finds '-4e' and strips it,
        returning 'ACS-100a-1b-2c-3d'.
        """
        result = derive_parent_id("ACS-100a-1b-2c-3d-4e")
        assert result == "ACS-100a-1b-2c-3d", (
            f"Expected 'ACS-100a-1b-2c-3d' from 'ACS-100a-1b-2c-3d-4e', "
            f"got {result!r}"
        )

    # -- Mixed separators ----------------------------------------------------

    def test_underscore_separator_treated_as_opaque_segment(self) -> None:
        """ID with underscore separator (e.g. 'ACS_100-200'): underscore is opaque.

        Neither pattern matches (underscore in prefix position breaks both
        anchors). rfind('-') finds '-200' at position 7 and strips it,
        returning 'ACS_100'.
        """
        result = derive_parent_id("ACS_100-200")
        assert result == "ACS_100", (
            f"Expected 'ACS_100' from 'ACS_100-200', got {result!r}"
        )

    # -- Unicode input -------------------------------------------------------

    def test_unicode_characters_in_id(self) -> None:
        """ID with Unicode characters (e.g. 'ACS-1øø-1'): rfind strips last segment.

        Unicode chars do not satisfy the ASCII-only regex patterns. Rule 3 fires:
        rfind('-') strips '-1', returning 'ACS-1øø'.

        The character U+00F8 is 'o with stroke' (ø).
        """
        result = derive_parent_id("ACS-1øø-1")
        assert result == "ACS-1øø", (
            f"Expected 'ACS-1\\u00f8\\u00f8' from 'ACS-1\\u00f8\\u00f8-1', "
            f"got {result!r}"
        )

    # -- None input ----------------------------------------------------------

    def test_none_input_raises_attribute_error(self) -> None:
        """None input: function has no type guard, so re.match(None) raises TypeError.

        derive_parent_id() is typed as ``str`` but has no runtime isinstance
        check. Passing None causes ``re.Pattern.match()`` to raise TypeError
        (cannot use a non-string pattern argument).

        This test documents the *current* behaviour. If a type-guard is added
        in the future, this test must be updated to reflect the new contract.
        """
        with pytest.raises((TypeError, AttributeError)):
            derive_parent_id(None)  # type: ignore[arg-type]
