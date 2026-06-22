"""
MODULE: test_goal_to_epic_apostrophe
GOAL: Verify ACD-1200a-3-ii — apostrophe and quote characters in a goal title
    are stripped in-place (zero-width deletion) before the title is PascalCased
    into an epic folder name.

BUSINESS CONTEXT: Implements test coverage for ticket
    03_apostrophe_safe_epic_names.md (EPIC-GoalToEpicBugfixes). Ensures goals
    such as "Validate user's API inputs" yield EPIC-ValidateUsersApiInputs
    (clean, no literal quote, no split word, no empty segment).

ARCHITECTURE: Pure unit tests using unittest.TestCase. No database. No network.
    No filesystem writes. Uses importlib to load goal_to_epic from the worktree
    scripts/ directory. Must complete in < 5 seconds.

Tests in this file:
  - test_ascii_apostrophe_stripped_midword
  - test_curly_apostrophe_u2019_stripped
  - test_double_quote_stripped
  - test_backtick_stripped
  - test_all_quote_chars_in_single_title
  - test_result_contains_no_literal_quote
  - test_no_empty_segment_produced
  - test_no_trailing_separator
  - test_idempotent_derive_epic_name
  - test_idempotent_to_pascal_case
  - test_no_word_boundary_at_quote_position
  - test_strip_quote_chars_pure
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: load goal_to_epic from the worktree scripts/ directory.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_GOAL_TO_EPIC_PATH = _SCRIPTS_DIR / "goal_to_epic.py"


def _load_goal_to_epic():
    """Load goal_to_epic from scripts/ into sys.modules (idempotent)."""
    if str(_SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIR))

    module_name = "goal_to_epic"
    if module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, _GOAL_TO_EPIC_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStripQuoteChars(unittest.TestCase):
    """Unit tests for _strip_quote_chars() — the zero-width deletion helper."""

    def setUp(self) -> None:
        self._mod = _load_goal_to_epic()

    def test_strip_quote_chars_pure(self) -> None:
        """_strip_quote_chars removes all four quote character types correctly.

        Verifies that U+0027, U+0022, U+0060, and U+2019 are all deleted
        and adjacent letters join with no separator inserted.
        """
        # covers: ACD-1200a-3-ii (_strip_quote_chars core behaviour)
        strip = self._mod._strip_quote_chars
        self.assertEqual(strip("user's"), "users")        # U+0027 apostrophe
        self.assertEqual(strip('say "hi"'), "say hi")     # U+0022 double-quote
        self.assertEqual(strip("run `cmd`"), "run cmd")   # U+0060 backtick
        self.assertEqual(strip("it’s"), "its")       # U+2019 curly apostrophe

    def test_strip_quote_chars_no_separator_inserted(self) -> None:
        """_strip_quote_chars must produce zero-width deletion — no space/dash added.

        Verifies that "user's" → "users" (6 chars), not "user s" (7) or
        "user-s" (7). The adjacent letters must join directly.
        """
        # covers: ACD-1200a-3-ii (zero-width deletion, no separator)
        strip = self._mod._strip_quote_chars
        result = strip("user's")
        self.assertEqual(result, "users", msg=f"Expected 'users', got {result!r}")
        self.assertNotIn(" ", result, msg="No space must be inserted at quote position.")
        self.assertNotIn("-", result, msg="No hyphen must be inserted at quote position.")
        self.assertNotIn("_", result, msg="No underscore must be inserted at quote position.")

    def test_strip_quote_chars_idempotent(self) -> None:
        """Applying _strip_quote_chars twice produces the same result as once.

        Idempotency ensures repeated derivation does not accumulate changes.
        """
        # covers: ACD-1200a-3-ii (idempotency of stripping helper)
        strip = self._mod._strip_quote_chars
        title = "Validate user's API inputs"
        once = strip(title)
        twice = strip(once)
        self.assertEqual(once, twice, msg="Strip must be idempotent.")


class TestToPascalCaseWithQuotes(unittest.TestCase):
    """Tests for _to_pascal_case() with quote characters in input."""

    def setUp(self) -> None:
        self._mod = _load_goal_to_epic()

    def test_ascii_apostrophe_stripped_midword(self) -> None:
        """AC: ASCII apostrophe U+0027 mid-word is stripped; surrounding letters join.

        "Validate user's API inputs" → "ValidateUsersApiInputs"
        NOT "ValidateUser'sApiInputs" or "ValidateUserSApiInputs" (split word).
        """
        # covers: ACD-1200a-3-ii (ASCII apostrophe U+0027)
        to_pc = self._mod._to_pascal_case
        result = to_pc("Validate user's API inputs")
        self.assertEqual(
            result,
            "ValidateUsersApiInputs",
            msg=(
                f"Expected 'ValidateUsersApiInputs', got {result!r}. "
                "The apostrophe must be stripped so 'user's' → 'Users' (one word)."
            ),
        )

    def test_curly_apostrophe_u2019_stripped(self) -> None:
        """AC: Curly apostrophe U+2019 mid-word is stripped identically to U+0027.

        "Reject malformed customer’s payloads" → "RejectMalformedCustomersPayloads"
        """
        # covers: ACD-1200a-3-ii (curly apostrophe U+2019)
        to_pc = self._mod._to_pascal_case
        result = to_pc("Reject malformed customer’s payloads")
        self.assertEqual(
            result,
            "RejectMalformedCustomersPayloads",
            msg=(
                f"Expected 'RejectMalformedCustomersPayloads', got {result!r}. "
                "U+2019 curly apostrophe must be stripped so 'customer’s' → 'Customers'."
            ),
        )

    def test_double_quote_stripped(self) -> None:
        """AC: ASCII double-quote U+0022 is stripped in-place.

        'say "hello" world' → "SayHelloWorld"  (quotes removed, no word split at quote)
        """
        # covers: ACD-1200a-3-ii (double-quote U+0022)
        to_pc = self._mod._to_pascal_case
        result = to_pc('say "hello" world')
        self.assertEqual(
            result,
            "SayHelloWorld",
            msg=(
                f"Expected 'SayHelloWorld', got {result!r}. "
                "Double-quote must be stripped in-place."
            ),
        )

    def test_backtick_stripped(self) -> None:
        """AC: Backtick U+0060 is stripped in-place.

        "run `the` command" → "RunTheCommand"  (backticks removed)
        """
        # covers: ACD-1200a-3-ii (backtick U+0060)
        to_pc = self._mod._to_pascal_case
        result = to_pc("run `the` command")
        self.assertEqual(
            result,
            "RunTheCommand",
            msg=(
                f"Expected 'RunTheCommand', got {result!r}. "
                "Backtick must be stripped in-place."
            ),
        )

    def test_all_quote_chars_in_single_title(self) -> None:
        """AC: All four quote character types are stripped from a single title.

        Verifies the rule is applied uniformly regardless of which quote
        variant appears in the title.
        """
        # covers: ACD-1200a-3-ii (all four quote types in one input)
        to_pc = self._mod._to_pascal_case
        # Title contains all four: U+0027, U+0022, U+0060, U+2019
        title = "user's \"double\" `backtick` and it’s done"
        result = to_pc(title)
        # No literal quote char should survive in the result
        for char in ("'", '"', '`', '’'):
            self.assertNotIn(
                char,
                result,
                msg=(
                    f"Literal quote char {char!r} (U+{ord(char):04X}) must not "
                    f"appear in PascalCase result. Got: {result!r}"
                ),
            )

    def test_result_contains_no_literal_quote(self) -> None:
        """AC: The derived PascalCase name must never contain a literal quote char.

        Covers the "resulting folder name contains no literal apostrophe, quote,
        backtick, or truncated/empty path segment" requirement from the AC Gherkin.
        """
        # covers: ACD-1200a-3-ii (no literal quote in result)
        to_pc = self._mod._to_pascal_case
        titles = [
            "Validate user's API inputs",
            "Reject malformed customer’s payloads",
            'Store "pending" orders',
            "Run `batch` jobs",
        ]
        quote_chars = ("'", '"', '`', '’')
        for title in titles:
            result = to_pc(title)
            for char in quote_chars:
                self.assertNotIn(
                    char,
                    result,
                    msg=(
                        f"Quote char {char!r} must not appear in result for title {title!r}. "
                        f"Got: {result!r}"
                    ),
                )

    def test_no_empty_segment_produced(self) -> None:
        """AC: No empty PascalCase segment is produced from stripping quotes.

        A title whose words are all-apostrophe (pathological) must not
        produce an empty string or a result that is only "EPIC-".
        """
        # covers: ACD-1200a-3-ii (guard against empty segment)
        to_pc = self._mod._to_pascal_case
        # Title with leading/trailing apostrophes around a real word
        result = to_pc("'validate' inputs")
        self.assertGreater(
            len(result),
            0,
            msg=f"PascalCase result must be non-empty. Got: {result!r}",
        )
        # The word "validate" must survive the strip
        self.assertIn(
            "Validate",
            result,
            msg=f"Word 'Validate' must survive apostrophe stripping. Got: {result!r}",
        )

    def test_no_trailing_separator(self) -> None:
        """AC: Stripping trailing quotes does not produce a trailing separator.

        The PascalCase join produces no hyphen, underscore, or space at the
        start or end of the result.
        """
        # covers: ACD-1200a-3-ii (no trailing separator)
        to_pc = self._mod._to_pascal_case
        result = to_pc("inputs'")
        # Result must not start or end with a separator
        self.assertFalse(
            result.startswith(("-", "_", " ")),
            msg=f"Result must not start with a separator. Got: {result!r}",
        )
        self.assertFalse(
            result.endswith(("-", "_", " ")),
            msg=f"Result must not end with a separator. Got: {result!r}",
        )

    def test_no_word_boundary_at_quote_position(self) -> None:
        """AC: The apostrophe does NOT create a word boundary.

        "user's" must produce "Users" (one PascalCase word), not "UserS"
        (two words capitalized separately) and not "User S" (two words joined
        with a capital S).
        """
        # covers: ACD-1200a-3-ii (no word split at quote position)
        to_pc = self._mod._to_pascal_case
        result = to_pc("user's")
        # Must be a single word "Users" — if a split happened we'd get "UserS"
        self.assertEqual(
            result,
            "Users",
            msg=(
                f"Expected 'Users' (one word), got {result!r}. "
                "Apostrophe must NOT create a word boundary inside 'user's'."
            ),
        )


class TestDeriveEpicNameWithQuotes(unittest.TestCase):
    """Integration tests for _derive_epic_name() with apostrophe/quote inputs.

    These tests verify that the full _derive_epic_name() pipeline (which calls
    _to_pascal_case, LLM, or truncation) also handles quote chars correctly.
    They use short titles that do not trigger the LLM or truncation fallback,
    so they are purely testing the stripping step.
    """

    def setUp(self) -> None:
        self._mod = _load_goal_to_epic()

    def test_derive_epic_name_ascii_apostrophe(self) -> None:
        """AC (full pipeline): ASCII apostrophe goal title → clean epic name.

        "Validate user's API inputs" → "ValidateUsersApiInputs"  (≤40 chars,
        no LLM needed, so this exercises only the strip + PascalCase path).
        """
        # covers: ACD-1200a-3-ii (full _derive_epic_name pipeline, ASCII apostrophe)
        derive = self._mod._derive_epic_name
        result = derive("Validate user's API inputs")
        self.assertEqual(
            result,
            "ValidateUsersApiInputs",
            msg=(
                f"_derive_epic_name must produce 'ValidateUsersApiInputs', got {result!r}."
            ),
        )

    def test_derive_epic_name_curly_apostrophe(self) -> None:
        """AC (full pipeline): Curly apostrophe goal title → clean epic name.

        "Reject malformed customer’s payloads" → "RejectMalformedCustomersPayloads"
        """
        # covers: ACD-1200a-3-ii (full _derive_epic_name pipeline, curly apostrophe U+2019)
        derive = self._mod._derive_epic_name
        result = derive("Reject malformed customer’s payloads")
        self.assertEqual(
            result,
            "RejectMalformedCustomersPayloads",
            msg=(
                f"_derive_epic_name must produce 'RejectMalformedCustomersPayloads', "
                f"got {result!r}."
            ),
        )

    def test_idempotent_derive_epic_name(self) -> None:
        """AC: Calling _derive_epic_name twice on the same title is idempotent.

        Repeated derivation (e.g. re-running the script) must not accumulate
        changes to the derived name.
        """
        # covers: ACD-1200a-3-ii (idempotency of full _derive_epic_name)
        derive = self._mod._derive_epic_name
        title = "Validate user's API inputs"
        first = derive(title)
        second = derive(title)
        self.assertEqual(
            first,
            second,
            msg=(
                f"_derive_epic_name must be idempotent: first={first!r}, second={second!r}"
            ),
        )

    def test_idempotent_to_pascal_case(self) -> None:
        """AC: Calling _to_pascal_case twice on the same title is idempotent.

        Repeated conversions must not further modify the result.
        """
        # covers: ACD-1200a-3-ii (idempotency of _to_pascal_case)
        to_pc = self._mod._to_pascal_case
        title = "Reject malformed customer's payloads"
        first = to_pc(title)
        second = to_pc(title)
        self.assertEqual(
            first,
            second,
            msg=(
                f"_to_pascal_case must be idempotent: first={first!r}, second={second!r}"
            ),
        )

    def test_non_apostrophe_titles_unchanged(self) -> None:
        """Titles with no quote chars are unaffected by the stripping step.

        Regression guard: the fix must not alter behaviour for titles that
        contain no apostrophe or quote characters.
        """
        # covers: ACD-1200a-3-ii (regression guard for clean titles)
        to_pc = self._mod._to_pascal_case
        cases = [
            ("validate api inputs", "ValidateApiInputs"),
            ("Reject malformed payloads", "RejectMalformedPayloads"),
            ("run-batch-jobs", "RunBatchJobs"),
            ("build_epic_workflow", "BuildEpicWorkflow"),
        ]
        for title, expected in cases:
            with self.subTest(title=title):
                result = to_pc(title)
                self.assertEqual(
                    result,
                    expected,
                    msg=(
                        f"Title without quotes must be unaffected: "
                        f"expected {expected!r}, got {result!r} for {title!r}."
                    ),
                )


if __name__ == "__main__":
    unittest.main()
