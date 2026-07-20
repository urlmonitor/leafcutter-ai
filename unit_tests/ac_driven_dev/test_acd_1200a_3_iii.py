"""
MODULE: unit_tests/ac_driven_dev/test_acd_1200a_3_iii.py
GOAL: Failing stubs for ACD-1200a-3-iii — Epic slug is ASCII-safe for non-ASCII
      punctuation, is not truncated mid-word, and is identical in dry-run and real run.
BUSINESS CONTEXT: Three defects exist in goal_to_epic.py as of this authoring:
  (1) _to_pascal_case does not strip non-ASCII punctuation (em-dash passes through
      via re.split, which does not match U+2014 "—"), so the folder name is
      "ShipPartsTree—TheFastPath" instead of "ShipPartsTreeTheFastPath";
  (2) long titles that contain an em-dash produce a truncated result that still
      contains the em-dash (since _truncate_pascal_at operates on the raw
      PascalCase string and the em-dash is preserved at a word boundary);
  (3) assemble_epic_folder re-applies _to_pascal_case() on the already-PascalCase
      epic_name from _derive_epic_name(), and str.capitalize() lowercases all chars
      after the first — so the real-run folder is "EPIC-Shippartstreethefastpath"
      while dry-run reports "EPIC-ShipPartsTreeTheFastPath" (casing drift / parity
      failure).
ARCHITECTURE: Pure unit tests; no I/O, no DB, no subprocess. Imports internal
      functions directly from goal_to_epic.py (added to sys.path).
DECISION HISTORY
- 2026-07-17 [ACD-1200a-3-iii/test-writer]: Initial failing stubs. All three tests
  are RED (non-zero exit) before the python-coder fix lands.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from goal_to_epic import _derive_epic_name, _to_pascal_case


class TestAcd1200a3iii(unittest.TestCase):
    """Tests for ACD-1200a-3-iii: ASCII-safe epic slug, word-boundary truncation,
    and dry-run/real-run parity."""

    def test_em_dash_title_yields_ascii_slug(self) -> None:
        # covers: ACD-1200a-3-iii
        """AC-1/AC-2: _to_pascal_case must strip or normalize non-ASCII punctuation
        (em-dash U+2014 and similar) so the derived folder name contains only ASCII
        alphanumeric characters.

        Current defect: re.split(r'[\\s\\-_]+', ...) does not match the em-dash,
        so it is treated as its own word token and "—".capitalize() = "—", producing
        "ShipPartsTree—TheFastPath" instead of "ShipPartsTreeTheFastPath".

        This test MUST be RED until goal_to_epic._to_pascal_case strips non-ASCII
        punctuation before splitting into words.
        """
        result = _to_pascal_case("Ship parts tree — the fast path")

        self.assertTrue(
            result.isascii(),
            f"Result contains non-ASCII chars (em-dash passed through): {result!r}",
        )
        self.assertEqual(
            result,
            "ShipPartsTreeTheFastPath",
            f"Expected 'ShipPartsTreeTheFastPath' (em-dash stripped), got {result!r}",
        )

    def test_long_title_truncates_at_word_boundary(self) -> None:
        # covers: ACD-1200a-3-iii
        """AC-3/AC-4: _derive_epic_name must truncate long titles only at a PascalCase
        word boundary, with no mid-word cut, no dangling separator (e.g. a trailing
        em-dash), and no non-ASCII character in the result.

        The title below is 71 chars and contains an em-dash. After _to_pascal_case,
        the naive result is "SeeAutomationWorkingInRealTime—BecauseItMakesEverythingBetter"
        (61 chars; em-dash at position 30). The LLM summariser is unavailable in CI,
        so _truncate_pascal_at falls back and finds the largest word boundary ≤ 40 chars.
        The backward-walk lands on pascal[:40] = "SeeAutomationWorkingInRealTime—BecauseIt"
        (40 chars), which still contains the em-dash — so result.isascii() is False.

        This test MUST be RED until goal_to_epic strips non-ASCII punctuation before
        truncation.
        """
        long_title = (
            "See automation working in real time — because it makes everything better"
        )
        result = _derive_epic_name(long_title)

        self.assertLessEqual(
            len(result),
            40,
            f"Result exceeds 40 chars: {result!r} (len={len(result)})",
        )
        self.assertTrue(
            result.isascii(),
            f"Result contains non-ASCII chars after truncation (em-dash not stripped): {result!r}",
        )
        # Last char must be a letter or digit — no dangling separator at the end
        self.assertTrue(
            result and (result[-1].islower() or result[-1].isdigit()),
            f"Result ends mid-word or with a dangling separator: {result!r}",
        )

    def test_dry_run_matches_real_run(self) -> None:
        # covers: ACD-1200a-3-iii
        """AC-5: The epic folder name reported by --dry-run must be byte-for-byte
        identical to the folder name created by the real run.

        Dry-run code path:
            epic_name = _derive_epic_name(ac_title)   # e.g. "ShipPartsTreeTheFastPath"
            print(f"Would create: EPIC-{epic_name}")  # "EPIC-ShipPartsTreeTheFastPath"

        Real-run code path:
            epic_name = _derive_epic_name(ac_title)   # same "ShipPartsTreeTheFastPath"
            assemble_epic_folder(paths, epic_name, inbox_dir)
            # inside: pascal = _to_pascal_case(epic_name)  ← re-applies conversion!
            # _to_pascal_case("ShipPartsTreeTheFastPath") splits on no separator,
            # then "ShipPartsTreeTheFastPath".capitalize() = "Shippartstreethefastpath"
            # folder name becomes "EPIC-Shippartstreethefastpath" — casing drift!

        This test MUST be RED until assemble_epic_folder is fixed to use the
        already-derived PascalCase name without re-applying _to_pascal_case.
        """
        title = "Ship parts tree the fast path"
        derived = _derive_epic_name(title)

        # What dry-run reports: uses derived directly
        dry_run_folder = f"EPIC-{derived}"

        # What real-run creates: assemble_epic_folder calls _to_pascal_case(epic_name)
        # on the already-PascalCase derived string, clobbering the casing.
        real_run_folder = f"EPIC-{_to_pascal_case(derived)}"

        self.assertEqual(
            dry_run_folder,
            real_run_folder,
            (
                f"Dry-run reports {dry_run_folder!r} but real-run would create "
                f"{real_run_folder!r}. "
                f"assemble_epic_folder re-applies _to_pascal_case on an already-PascalCase "
                f"string, lowercasing all chars after the first via str.capitalize()."
            ),
        )
