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
# blocked (GE-111f, renumbered from GE-119 by TICKET-20260817-GE-122e-1). They
# are detected by _find_deleted_tests /
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


_GIT_TIMEOUT = 30


def _name_only(*extra: str) -> list[str] | None:
    """Return staged path names via ``git diff --cached -z --name-only``.

    ``-z`` is required, not cosmetic. Without it git C-quotes any path holding
    a non-ASCII byte (``core.quotePath`` defaults to true), and splitting the
    output on whitespace tears any path containing a space into two tokens.
    Either way the resulting strings match no file, the scoped diff silently
    comes back empty, and the guard passes on a commit it should have blocked.
    NUL separation is unambiguous for every legal path.

    Args:
        *extra: Additional arguments appended to the git command (e.g. a ref).

    Returns:
        Repo-relative path strings, or None when the git call fails.
    """
    try:
        proc = subprocess.run(
            ["git", "diff", "--cached", "-z", "--name-only", *extra],
            capture_output=True, text=True, timeout=_GIT_TIMEOUT, check=True,
        )
    except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
        print(
            f"[contract-shrinking guard] WARNING: `git diff --name-only {' '.join(extra)}` "
            f"failed: {exc} — falling back to the unscoped diff",
            file=sys.stderr,
        )
        return None
    return [p for p in proc.stdout.split("\0") if p]


def _merge_scoped_paths() -> list[str] | None:
    """Return paths differing from BOTH merge parents, or None when not merging.

    A merge stages the ENTIRE incoming branch, so an unscoped ``git diff
    --cached`` shows every test the other side ever deleted or skipped. The
    merge author neither wrote those changes nor can improve them — they are
    already on the branch being merged — so blocking on them only makes merging
    impossible and trains people to reach for ``SKIP=``.

    Content differing from both parents is authored BY the merge (a conflict
    resolution, or an edit made while resolving), so it stays in scope. That is
    what stops merge-scoping from becoming a way to smuggle weakening through.

    Returns:
        Repo-relative paths to scope to; an empty list when the merge introduces
        no such file; or None when this is not a merge, or the merge state
        cannot be determined (caller then uses the unscoped diff — the stricter
        behaviour).
    """
    try:
        probe = subprocess.run(
            ["git", "rev-parse", "-q", "--verify", "MERGE_HEAD"],
            capture_output=True, text=True, timeout=_GIT_TIMEOUT, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(
            f"[contract-shrinking guard] WARNING: MERGE_HEAD probe failed: {exc} "
            "— scanning the full staged diff",
            file=sys.stderr,
        )
        return None
    if probe.returncode != 0:
        return None  # not a merge

    ours = _name_only()
    theirs = _name_only("MERGE_HEAD")
    if ours is None or theirs is None:
        return None
    theirs_set = set(theirs)
    return [p for p in ours if p in theirs_set]


def _git_diff(paths: list[str] | None = None) -> str:
    """Return the staged diff, optionally restricted to *paths*.

    Pathspecs are prefixed with ``:(top)`` because ``--name-only`` emits
    repo-root-relative paths while a pathspec after ``--`` is resolved against
    the CURRENT directory. Invoked from a subdirectory — which this repo's own
    CLAUDE.md prescribes for manual hook runs — unanchored pathspecs would match
    nothing and turn the gate off.

    Args:
        paths: Repo-relative paths to restrict to, or None for the whole diff.

    Returns:
        The diff text.
    """
    cmd = ["git", "diff", "--cached"]
    if paths:
        cmd += ["--", *(f":(top){p}" for p in paths)]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=_GIT_TIMEOUT, check=True,
        )
        return result.stdout
    except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
        print(f"[contract-shrinking guard] ERROR: git diff --cached failed: {exc}", file=sys.stderr)
        sys.exit(1)


def _get_staged_diff() -> str:
    """Return the FULL staged diff — the basis for production-change detection.

    Deliberately unscoped even during a merge. This guard's predicate spans two
    disjoint file sets ("production changed AND a test weakened"), so narrowing
    both halves would break the conjunction: an author could take main's
    production edit verbatim (removing it from scope) and skip the tests it
    broke, and the pairing would never form. The production change lands in this
    commit whichever parent authored it, so it counts as context regardless.

    Uses HOOK_TEST_DIFF env var when set (for unit testing only).
    """
    test_diff_path = os.environ.get("HOOK_TEST_DIFF")
    if test_diff_path:
        try:
            return Path(test_diff_path).read_text(encoding="utf-8")
        except OSError as exc:
            print(f"[contract-shrinking guard] ERROR: could not read HOOK_TEST_DIFF: {exc}", file=sys.stderr)
            sys.exit(1)
    return _git_diff()


def _get_weakening_diff(full_diff: str) -> str:
    """Return the diff that test-weakening is judged against.

    Outside a merge this is the full staged diff. During a merge it is narrowed
    to files differing from both parents, so the author is judged on the
    weakening they authored rather than on everything the incoming branch ever
    did.

    Args:
        full_diff: The unscoped staged diff, reused verbatim when no narrowing
            applies (also the HOOK_TEST_DIFF passthrough).

    Returns:
        The diff text to scan for weakening patterns.
    """
    if os.environ.get("HOOK_TEST_DIFF"):
        return full_diff

    scoped = _merge_scoped_paths()
    if scoped is None:
        return full_diff  # not a merge, or undeterminable — stay strict
    if not scoped:
        return ""  # merge introduces no content of its own

    scoped_diff = _git_diff(scoped)
    if not scoped_diff.strip():
        # Contradiction: we named files but git produced nothing for them. That
        # means the pathspecs did not resolve (mangled path, wrong CWD, ...) —
        # historically the silent failure mode that turns this gate off. Say so
        # and fall back to the strict, unscoped diff.
        print(
            "[contract-shrinking guard] WARNING: merge scope named "
            f"{len(scoped)} file(s) but produced an empty diff — pathspecs did "
            "not resolve. Falling back to the full staged diff.",
            file=sys.stderr,
        )
        return full_diff
    return scoped_diff


def _scan_diff(diff: str, weakening_diff: str | None = None) -> ScanResult:
    """Scan for production changes and test-weakening patterns.

    The two halves of the predicate are scanned over DIFFERENT inputs during a
    merge (see :func:`_get_staged_diff` and :func:`_get_weakening_diff`):
    production changes over everything the commit lands, weakening only over
    what the merge author actually authored. Outside a merge both are the same
    text and behaviour is unchanged.

    Args:
        diff: The full staged diff — basis for production-change detection.
        weakening_diff: The diff to judge test weakening against. Defaults to
            *diff*, which is the correct non-merge behaviour.

    Returns:
        A ScanResult describing what was found.
    """
    if weakening_diff is None:
        weakening_diff = diff
    result = ScanResult()

    # --- Production file detection (full diff) ---
    for match in _PRODUCTION_FILE_RE.finditer(diff):
        filepath = match.group(1)
        if not _TEST_PATH_RE.search(filepath):
            result.has_production_changes = True
            result.production_files.append(filepath)

    # --- Test-weakening pattern detection (single-line, additive) ---
    for pattern, label in _COMPILED_WEAKENING_PATTERNS:
        for match in pattern.finditer(weakening_diff):
            # Extract a short context snippet (first 120 chars of the matching line)
            line = match.group(0).rstrip("\n")[:120]
            result.violations.append((label, line))

    # --- Deletion detection (needs both sides of the diff correlated) ---
    for name in _find_deleted_tests(weakening_diff):
        result.violations.append(("test function deleted", name))
    for path in _find_deleted_test_files(weakening_diff):
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

    scan = _scan_diff(diff, _get_weakening_diff(diff))

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
