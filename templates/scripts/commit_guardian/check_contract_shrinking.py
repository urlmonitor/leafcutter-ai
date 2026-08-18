"""
MODULE: check_contract_shrinking
GOAL: Pre-commit hook that blocks commits when test weakening is concurrent with
    production code changes (contract-shrinking guard).
BUSINESS CONTEXT: Enforces the TDD contract: you may not delete, skip, or xfail
    tests while also modifying production code. If a test is genuinely wrong,
    fix it in a separate commit with no production code changes. This is the
    hook-enforcement layer of the three-layer contract-shrinking guard
    (hook + supervisor warn + honor-system docs). See EPIC-TDDWorkflowEnforcement.
ARCHITECTURE: Reads staged diff via git diff --cached (or HOOK_TEST_DIFF env var
    for testing), applies two independent scans (production file presence scan +
    test-weakening pattern scan), and exits non-zero only when both are present.
    Fast: no subprocess spawns beyond one git diff call. O(lines in diff).
    Self-exclusion: commit_guardian/ paths (hook infrastructure scripts) are
    excluded from the production-file scan so that staging hook scripts alongside
    test changes does not trigger a false-positive block.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants — detection patterns
# ---------------------------------------------------------------------------

# Patterns for production code files (any .py not in test directories)
# conftest.py is explicitly excluded — it is test infrastructure, not production code.
# commit_guardian/ is explicitly excluded — hook infrastructure is not production
# application code and must not trigger the guard when its own scripts are staged.
_PRODUCTION_FILE_RE = re.compile(
    r"^diff --git a/(.*\.py) b/",
    re.MULTILINE,
)
_TEST_PATH_RE = re.compile(
    r"(unit_tests/|tests/|test_[^/]+\.py$|[^/]+_test\.py$|conftest\.py$"
    r"|commit[_-]guardian/)",
    re.IGNORECASE,
)

# Patterns for test-weakening changes (lines ADDED in the diff).
#
# Deletion of a test function or a whole test file is NOT in this list — those
# two cannot be decided from a single line. A body edit renders as a removed
# `-    def test_x` AND an added `+    def test_x` for the same name, and an
# ordinary modification of a test file still puts it on the `--- a/` side. Both
# were reported as deletions, so every edited test and every merge commit was
# blocked (GE-119). They are detected by _find_deleted_tests /
# _find_deleted_test_files below, which correlate the two sides of the diff.
# Each pattern anchors the token to the START of the added line (after the
# diff's own "+" and the line's indentation) and requires real call/decorator
# syntax. The previous `^\+.*<token>` form matched the token ANYWHERE in an
# added line, so it fired on text that merely mentions these names:
#
#   +        \"\"\"A diff exercising pytest.skip, pytest.mark.xfail   <- docstring
#   +            "pytest.mark.xfail                                    <- string literal
#   +            +    @unittest.skip(                                  <- a diff INSIDE a
#                                                                         fixture string, so
#                                                                         the real line starts
#                                                                         with a second "+"
#   +description: "... check_contract_shrinking ... xfail ..."         <- changelog prose
#
# That made this guard unable to review its own test suite or any changelog
# describing it, and it blocked merge commits that imported such files.
# Anchoring keeps every genuine form (`+    @unittest.skip("flaky")`,
# `+        pytest.skip("reason")`) while rejecting all of the above.
#
# Deliberate narrowing: a skip called mid-statement (`+  if x: pytest.skip(y)`)
# is no longer flagged. Prose and fixtures mentioning these tokens are far more
# common than mid-statement skips, and this guard is a backstop, not a parser —
# a false block on every merge commit is worse than missing that rare form.
#
# `@unittest.skip\s*\(` does NOT match `@unittest.skipUnless(` / `skipIf(`,
# because those have a letter, not `(` or whitespace, after "skip" — a
# conditional guard is not a disabled test.
_WEAKENING_PATTERNS: list[tuple[str, str]] = [
    # pytest.skip call added as its own statement
    (r"^\+\s*pytest\.skip\s*\(", "pytest.skip added"),
    # pytest.mark.xfail added as a decorator or a module-level pytestmark
    (
        r"^\+\s*(?:@|pytestmark\s*=\s*)pytest\.mark\.xfail\b",
        "pytest.mark.xfail added",
    ),
    # @unittest.skip decorator added (not skipUnless / skipIf)
    (r"^\+\s*@unittest\.skip\s*\(", "@unittest.skip added"),
    # @unittest.expectedFailure decorator alone on its line
    (r"^\+\s*@unittest\.expectedFailure\s*$", "@unittest.expectedFailure added"),
]
_COMPILED_WEAKENING_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(pattern, re.MULTILINE), label)
    for pattern, label in _WEAKENING_PATTERNS
]


# Test-function definitions on each side of the diff, capturing the NAME so a
# removal can be paired with its re-addition. The old pattern had no capture
# group at all, so the guard could not even report which test it meant.
_REMOVED_TEST_DEF_RE = re.compile(r"^-\s*(?:async\s+)?def\s+(test_\w+)", re.MULTILINE)
_ADDED_TEST_DEF_RE = re.compile(r"^\+\s*(?:async\s+)?def\s+(test_\w+)", re.MULTILINE)

# A file is only DELETED when its new-side header is /dev/null. Matching the
# `--- a/...` side alone also matches every ordinary modification.
_DELETED_FILE_RE = re.compile(
    r"^--- a/(?P<path>.+)\n\+\+\+ /dev/null\s*$",
    re.MULTILINE,
)
_TEST_FILE_RE = re.compile(r"(^|/)(test_[^/]+\.py|[^/]+_test\.py)$")


def _find_deleted_tests(diff: str) -> list[str]:
    """Return names of test functions removed and never re-added.

    A test whose body is edited appears on BOTH sides of the diff with the same
    name; that is a modification, not a deletion. Only a name that is removed
    with no matching addition anywhere in the diff has actually gone away.

    Args:
        diff: The full text of the staged git diff.

    Returns:
        Sorted list of deleted test-function names (may be empty).
    """
    removed = set(_REMOVED_TEST_DEF_RE.findall(diff))
    added = set(_ADDED_TEST_DEF_RE.findall(diff))
    return sorted(removed - added)


def _find_deleted_test_files(diff: str) -> list[str]:
    """Return paths of test files the diff deletes outright.

    Args:
        diff: The full text of the staged git diff.

    Returns:
        Sorted list of deleted test-file paths (may be empty).
    """
    deleted = {
        match.group("path")
        for match in _DELETED_FILE_RE.finditer(diff)
        if _TEST_FILE_RE.search(match.group("path"))
    }
    return sorted(deleted)


@dataclass
class ScanResult:
    """Result of scanning the staged diff."""
    has_production_changes: bool = False
    production_files: list[str] = field(default_factory=list)
    violations: list[tuple[str, str]] = field(default_factory=list)  # (label, context)

    @property
    def is_contract_shrinking(self) -> bool:
        """True iff both production changes and test-weakening are present."""
        return self.has_production_changes and bool(self.violations)


def _get_staged_diff() -> str:
    """Return the staged diff as a string.

    Uses HOOK_TEST_DIFF env var when set (for unit testing only).
    Otherwise calls git diff --cached.
    """
    test_diff_path = os.environ.get("HOOK_TEST_DIFF")
    if test_diff_path:
        try:
            return Path(test_diff_path).read_text(encoding="utf-8")
        except OSError as exc:
            print(f"[contract-shrinking guard] ERROR: could not read HOOK_TEST_DIFF: {exc}", file=sys.stderr)
            sys.exit(1)

    try:
        result = subprocess.run(
            ["git", "diff", "--cached"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as exc:
        print(f"[contract-shrinking guard] ERROR: git diff --cached failed: {exc}", file=sys.stderr)
        sys.exit(1)


def _scan_diff(diff: str) -> ScanResult:
    """Scan the diff for production changes and test-weakening patterns.

    Args:
        diff: The full text of the staged git diff.

    Returns:
        A ScanResult describing what was found.
    """
    result = ScanResult()

    # --- Production file detection ---
    for match in _PRODUCTION_FILE_RE.finditer(diff):
        filepath = match.group(1)
        if not _TEST_PATH_RE.search(filepath):
            result.has_production_changes = True
            result.production_files.append(filepath)

    # --- Test-weakening pattern detection (single-line, additive) ---
    for pattern, label in _COMPILED_WEAKENING_PATTERNS:
        for match in pattern.finditer(diff):
            # Extract a short context snippet (first 120 chars of the matching line)
            line = match.group(0).rstrip("\n")[:120]
            result.violations.append((label, line))

    # --- Deletion detection (needs both sides of the diff correlated) ---
    for name in _find_deleted_tests(diff):
        result.violations.append(("test function deleted", name))
    for path in _find_deleted_test_files(diff):
        result.violations.append(("test file deleted", path))

    return result


def main() -> int:
    """Run the contract-shrinking guard.

    Returns:
        0 if the commit is allowed, 1 if it is blocked.
    """
    diff = _get_staged_diff()

    if not diff.strip():
        # Nothing staged — pass silently.
        return 0

    scan = _scan_diff(diff)

    if not scan.is_contract_shrinking:
        # Either no production changes, or no test weakening, or neither — OK.
        return 0

    # --- BLOCKED ---
    lines: list[str] = [
        "",
        "[contract-shrinking guard] BLOCKED",
        "Reason: Staged diff contains test-weakening changes concurrent with production code changes.",
        "Violations detected:",
    ]
    for label, context in scan.violations:
        lines.append(f"  - {label}: {context!r}")
    lines.append("")
    lines.append("Production files modified:")
    for filepath in scan.production_files:
        lines.append(f"  - {filepath}")
    lines.append("")
    lines.append("You may not delete, skip, or xfail tests while also modifying production code.")
    lines.append("If a test is genuinely wrong, fix the test in a separate commit with no production code changes.")
    lines.append("See docs/how-to/writing-a-tdd-ticket.md for the full policy.")
    lines.append("")

    print("\n".join(lines))
    return 1


if __name__ == "__main__":
    sys.exit(main())


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-06-04 12:00 [EPIC-BuildPathCorrectness/T02]: Created canonical template at templates/scripts/commit_guardian/. Extended _TEST_PATH_RE to exclude commit_guardian/ paths (self-exclusion fix for false-positive when hook scripts are staged). (#EPIC-BuildPathCorrectness/T02)
# ===========================================================================
