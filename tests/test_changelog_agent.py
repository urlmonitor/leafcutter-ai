"""Unit tests for changelog agent commit categorization and CHANGELOG.md prepend logic.

Tests use inline functions mirroring the agent's categorization heuristics to
verify correct behavior without requiring git or network access.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Inline categorization logic (mirrors changelog-agent heuristics)
# ---------------------------------------------------------------------------

_CONVENTIONAL_PREFIXES = {
    "feat": "Features",
    "fix": "Bug Fixes",
    "docs": "Documentation",
    "chore": "Infrastructure",
    "refactor": "Refactoring",
    "test": "Tests",
    "perf": "Performance",
    "style": "Style",
}

_PATH_CATEGORIES = [
    ("live_trader/", "Trading"),
    ("collector/", "Data Pipeline"),
    ("data_collector/", "Data Pipeline"),
    ("sql_functions/", "Database"),
    ("alembic/", "Database"),
    ("models/", "Database"),
    ("scripts/", "Infrastructure"),
    ("docker-compose", "Infrastructure"),
    ("Dockerfile", "Infrastructure"),
    ("docs/", "Documentation"),
    ("unit_tests/", "Tests"),
    ("tests/", "Tests"),
]


class CommitEntry(NamedTuple):
    """A parsed commit entry."""

    short_hash: str
    message: str
    files: list[str]


def categorize_commit(entry: CommitEntry) -> str:
    """Categorize a commit by message prefix or touched files.

    Args:
        entry: The CommitEntry to categorize.

    Returns:
        Category string (e.g. 'Trading', 'Database', 'Other').
    """
    # Conventional commit prefix takes priority
    msg = entry.message.lower()
    for prefix, category in _CONVENTIONAL_PREFIXES.items():
        if msg.startswith(f"{prefix}:") or msg.startswith(f"{prefix}("):
            return category

    # File-path heuristic
    for file_path in entry.files:
        for path_prefix, category in _PATH_CATEGORIES:
            if path_prefix in file_path:
                return category

    return "Other"


def prepend_changelog_entry(existing_content: str, new_entry: str) -> str:
    """Prepend a new entry to existing CHANGELOG.md content.

    Inserts after the title line (# CHANGELOG) if present,
    otherwise prepends at the top.

    Args:
        existing_content: Current CHANGELOG.md text.
        new_entry: New entry to prepend.

    Returns:
        Updated CHANGELOG.md content with new_entry prepended.
    """
    lines = existing_content.splitlines(keepends=True)
    insert_at = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("# ") and "CHANGELOG" in line.upper():
            insert_at = i + 1
            # Skip blank line after title
            if insert_at < len(lines) and lines[insert_at].strip() == "":
                insert_at += 1
            break
    lines.insert(insert_at, new_entry + "\n")
    return "".join(lines)


# ---------------------------------------------------------------------------
# Tests: categorization
# ---------------------------------------------------------------------------

class TestCommitCategorization:
    """Tests for categorize_commit() heuristics."""

    def test_feat_prefix_categorizes_as_features(self) -> None:
        entry = CommitEntry("abc1234", "feat: add new strategy", [])
        assert categorize_commit(entry) == "Features"

    def test_fix_prefix_categorizes_as_bug_fixes(self) -> None:
        entry = CommitEntry("abc1234", "fix(live-trader): correct stop loss", [])
        assert categorize_commit(entry) == "Bug Fixes"

    def test_docs_prefix_categorizes_as_documentation(self) -> None:
        entry = CommitEntry("abc1234", "docs: update trading strategies", [])
        assert categorize_commit(entry) == "Documentation"

    def test_chore_prefix_categorizes_as_infrastructure(self) -> None:
        entry = CommitEntry("abc1234", "chore: update dependencies", [])
        assert categorize_commit(entry) == "Infrastructure"

    def test_live_trader_path_categorizes_as_trading(self) -> None:
        entry = CommitEntry("abc1234", "some change", ["live_trader/main.py"])
        assert categorize_commit(entry) == "Trading"

    def test_sql_functions_path_categorizes_as_database(self) -> None:
        entry = CommitEntry("abc1234", "update procedure", ["sql_functions/procedures/update_htf.sql"])
        assert categorize_commit(entry) == "Database"

    def test_alembic_path_categorizes_as_database(self) -> None:
        entry = CommitEntry("abc1234", "add migration", ["alembic/versions/abc_add_index.py"])
        assert categorize_commit(entry) == "Database"

    def test_docs_path_categorizes_as_documentation(self) -> None:
        entry = CommitEntry("abc1234", "update docs", ["docs/trading-strategies.md"])
        assert categorize_commit(entry) == "Documentation"

    def test_no_match_categorizes_as_other(self) -> None:
        entry = CommitEntry("abc1234", "misc update", ["some/other/file.txt"])
        assert categorize_commit(entry) == "Other"

    def test_conventional_prefix_overrides_path(self) -> None:
        # docs: prefix should override the live_trader/ path
        entry = CommitEntry("abc1234", "docs: document live_trader strategy", ["live_trader/docs.md"])
        assert categorize_commit(entry) == "Documentation"


# ---------------------------------------------------------------------------
# Tests: CHANGELOG.md prepend
# ---------------------------------------------------------------------------

class TestChangelogPrepend:
    """Tests for prepend_changelog_entry()."""

    def test_prepends_after_title(self) -> None:
        existing = "# CHANGELOG\n\n## Old Entry\n\n- old commit\n"
        new_entry = "## New Entry\n\n- new commit\n"
        result = prepend_changelog_entry(existing, new_entry)
        assert result.index("## New Entry") < result.index("## Old Entry")

    def test_does_not_overwrite_existing(self) -> None:
        existing = "# CHANGELOG\n\n## Old Entry\n\n- old commit\n"
        new_entry = "## New Entry\n\n- new commit\n"
        result = prepend_changelog_entry(existing, new_entry)
        assert "- old commit" in result
        assert "- new commit" in result

    def test_prepends_to_empty_changelog(self) -> None:
        existing = ""
        new_entry = "## First Entry\n\n- first commit\n"
        result = prepend_changelog_entry(existing, new_entry)
        assert "## First Entry" in result

    def test_prepends_without_title(self) -> None:
        existing = "## Existing Entry\n\n- old commit\n"
        new_entry = "## New Entry\n\n- new commit\n"
        result = prepend_changelog_entry(existing, new_entry)
        assert result.index("## New Entry") < result.index("## Existing Entry")
