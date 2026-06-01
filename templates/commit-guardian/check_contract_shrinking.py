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
_PRODUCTION_FILE_RE = re.compile(
    r"^diff --git a/(.*\.py) b/",
    re.MULTILINE,
)
_TEST_PATH_RE = re.compile(
    r"(unit_tests/|tests/|test_[^/]+\.py$|[^/]+_test\.py$|conftest\.py$)",
    re.IGNORECASE,
)

# Patterns for test-weakening changes (lines ADDED in the diff)
_WEAKENING_PATTERNS: list[tuple[str, str]] = [
    # Entire test file deleted (git shows it as deleted file)
    (r"^--- a/(test_[^/]+\.py|[^/]+_test\.py)", "test file deleted"),
    # Individual test function deleted (line removed from diff)
    (r"^-\s*def test_", "test function deleted"),
    # pytest.skip call added
    (r"^\+.*pytest\.skip\s*\(", "pytest.skip added"),
    # pytest.mark.xfail decorator added
    (r"^\+.*pytest\.mark\.xfail", "pytest.mark.xfail added"),
    # @unittest.skip decorator added
    (r"^\+.*@unittest\.skip\s*\(", "@unittest.skip added"),
    # @unittest.expectedFailure decorator added
    (r"^\+.*@unittest\.expectedFailure", "@unittest.expectedFailure added"),
]
_COMPILED_WEAKENING_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(pattern, re.MULTILINE), label)
    for pattern, label in _WEAKENING_PATTERNS
]


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

    # --- Test-weakening pattern detection ---
    for pattern, label in _COMPILED_WEAKENING_PATTERNS:
        for match in pattern.finditer(diff):
            # Extract a short context snippet (first 120 chars of the matching line)
            line = match.group(0).rstrip("\n")[:120]
            result.violations.append((label, line))

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
