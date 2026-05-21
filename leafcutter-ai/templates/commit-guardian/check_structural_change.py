"""
Pre-commit hook: structural-change detector.

MODULE: check_structural_change
GOAL: Block commits that introduce a structural change to the codebase
      (new model, new docker-compose service, new top-level package,
      large behavior change in existing modules, or SQL procedure signature
      change) without also touching docs/components.json in the same commit.
BUSINESS CONTEXT: No hook previously detected "the architecture grew". A
      developer could add a brand-new service or model with zero prompt to
      update the component registry. This closes that gap. Extended in
      EPIC-ArchitectureDocsEnforcement ticket 07 to also catch large behavior
      changes in existing modules (>50 added lines in live_trader/, collector/,
      models/) and SQL procedure argument-list changes.
ARCHITECTURE: Not needed.

Logic:
    Detect structural-change signals in the staged diff. Signals are loaded
    from commit_guardian.json → structural_change.signals. Defaults include:
      new model, new live-trader module, new collector worker,
      new top-level package, and new SQL procedure namespaces.
    Also detects new services added to docker-compose files.
    Extended rules (ticket 07):
      - Large diff (>50 added lines) in live_trader/*.py,
        collector/services/*/*.py, or models/*.py where the file already
        exists in HEAD fires as "large diff in <category>".
      - SQL procedure argument-list change in any staged .sql file
        fires as "SQL procedure signature change".
    If any signal fires AND the required_doc (docs/components.json by default)
    is NOT staged in the same commit AND the commit message does NOT contain
    the bypass_token ([NO-ARCH-UPDATE] by default), the commit is blocked.

Exit codes:
    0 - No structural changes, or changes covered by a components.json update,
        or bypass_token escape hatch in commit message.
    1 - Structural change detected without a matching required_doc update.

Escape hatch:
    Include the bypass_token (default: [NO-ARCH-UPDATE]) anywhere in the
    commit message to skip this check. This is intended for vendored code,
    pure refactors that preserve component identity, and similar cases.
    Override bypass_token in commit_guardian.json → structural_change.bypass_token.

Usage (invoked by pre-commit):
    python scripts/commit_guardian/check_structural_change.py

DOC_LINKS: None
DECISION HISTORY:
  - 2026-05-14 11:00 [Agent]: Added large-diff detection for existing modules and
    SQL procedure signature change detection (EPIC-ArchitectureDocsEnforcement
    ticket 07). Large-diff threshold defaults to 50 added lines, configurable
    via commit_guardian.json structural_change.large_diff_threshold. SQL
    signature detection uses regex on per-file diff context.
  - 2026-05-13 12:00 [Agent]: Made signals, required_doc, and bypass_token
    config-driven via commit_guardian.json (TICKET-20260513-Portable_Commit_Guardian_Paths).
  - 2026-05-12 00:00 [Agent]: Created structural-change detector
    (EPIC-ArchitectureDocs ticket 22). Fires only on additions (status=A in
    git diff), not edits. Escape hatch: [NO-ARCH-UPDATE] in commit message.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# Fix import path so the module works when invoked directly
_current_dir = Path(__file__).resolve().parent
_project_root = _current_dir.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from scripts.commit_guardian.config import (
    STRUCTURAL_SIGNALS,
    STRUCTURAL_REQUIRED_DOC,
    STRUCTURAL_BYPASS_TOKEN,
    _get as _cfg_get,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
# Source values from config; local names preserved for backward compatibility.
COMPONENTS_JSON_PATH = STRUCTURAL_REQUIRED_DOC
ESCAPE_HATCH = STRUCTURAL_BYPASS_TOKEN

# Large-diff threshold: added-line count above which an edit to an existing
# module in live_trader/, collector/services/*/, or models/ is treated as a
# structural behavior change. Configurable via commit_guardian.json →
# structural_change.large_diff_threshold (default: 50).
LARGE_DIFF_THRESHOLD: int = _cfg_get("structural_change", "large_diff_threshold", 50)

# Patterns for structural signals — all must match ADDED files only (status=A).
# Tuples of (signal_name, compiled_re_for_path).
# Loaded from commit_guardian.json → structural_change.signals.
_STRUCTURAL_SIGNALS: list[tuple[str, re.Pattern[str]]] = [
    (entry["name"], re.compile(entry["pattern"]))
    for entry in STRUCTURAL_SIGNALS
]

# Patterns for large-diff detection — (signal_name, compiled_re_for_path).
# These fire on MODIFIED (not new) files when added lines > LARGE_DIFF_THRESHOLD.
_LARGE_DIFF_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("large diff in live_trader module", re.compile(r"^live_trader/[^/]+\.py$")),
    ("large diff in collector service", re.compile(r"^collector/services/[^/]+/[^/]+\.py$")),
    ("large diff in model", re.compile(r"^models/[^/]+\.py$")),
]

# Regex to match CREATE OR REPLACE PROCEDURE header lines in SQL diff context.
_PROC_HEADER_RE = re.compile(
    r"CREATE\s+OR\s+REPLACE\s+PROCEDURE\s+\S+\s*\(", re.IGNORECASE
)

# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _get_staged_additions() -> list[str]:
    """Return a list of added (status=A) file paths in the staged index.

    Returns:
        List of repo-relative path strings for staged-added files.
    """
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-status"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        return []
    additions = []
    for line in result.stdout.splitlines():
        parts = line.split("\t", 1)
        if len(parts) == 2 and parts[0].startswith("A"):
            additions.append(parts[1])
    return additions


def _is_components_json_staged() -> bool:
    """Return True if docs/components.json is in the staged index.

    Returns:
        True if the file is staged (any status); False otherwise.
    """
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        return False
    staged = result.stdout.strip().splitlines()
    return COMPONENTS_JSON_PATH in staged


def _get_commit_message() -> str:
    """Return the pending commit message text, or empty string if unavailable.

    Reads COMMIT_EDITMSG from the git directory so the escape hatch can be
    checked before the commit is finalized.

    Returns:
        Commit message string, or empty string on read failure.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--git-path", "COMMIT_EDITMSG"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        return ""
    editmsg_path = Path(result.stdout.strip())
    if not editmsg_path.is_absolute():
        result2 = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if result2.returncode != 0:
            return ""
        editmsg_path = Path(result2.stdout.strip()) / "COMMIT_EDITMSG"
    try:
        return editmsg_path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _get_staged_service_additions() -> list[str]:
    """Return new service names added to docker-compose files.

    Parses git diff --cached on docker-compose*.yml files and extracts
    new top-level service keys from added lines.

    Returns:
        List of newly-added service name strings.
    """
    result = subprocess.run(
        ["git", "diff", "--cached", "--", "docker-compose*.yml", "docker-compose*.yaml"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        return []
    new_services: list[str] = []
    in_services = False
    service_pattern = re.compile(r"^\+  ([a-zA-Z][a-zA-Z0-9_-]*):\s*$")
    services_marker = re.compile(r"^\+?services:\s*$")
    for line in result.stdout.splitlines():
        if services_marker.match(line):
            in_services = True
            continue
        if in_services and line.startswith("+") and not line.startswith("+++"):
            match = service_pattern.match(line)
            if match:
                new_services.append(match.group(1))
    return new_services


def _get_staged_numstat() -> list[tuple[str, int, int]]:
    """Return (path, added, removed) tuples for all staged files.

    Uses git diff --cached --numstat for machine-readable line counts.

    Returns:
        List of (repo-relative path, added-lines, removed-lines) tuples.
        Returns empty list on subprocess failure.
    """
    result = subprocess.run(
        ["git", "diff", "--cached", "--numstat"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        return []
    entries: list[tuple[str, int, int]] = []
    for line in result.stdout.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        added_str, removed_str, path = parts
        try:
            entries.append((path, int(added_str), int(removed_str)))
        except ValueError:
            # Binary files show '-' — skip them.
            pass
    return entries


def _file_exists_in_head(path: str) -> bool:
    """Return True if the given repo-relative path exists in HEAD.

    Args:
        path: Repo-relative file path (posix slashes).

    Returns:
        True if HEAD contains the file; False for new (untracked-in-HEAD) files
        or if the git command fails.
    """
    result = subprocess.run(
        ["git", "cat-file", "-e", f"HEAD:{path}"],
        capture_output=True,
    )
    return result.returncode == 0


def _get_sql_file_diff(path: str) -> str:
    """Return the full cached diff for a single SQL file.

    Args:
        path: Repo-relative path to the SQL file.

    Returns:
        Unified diff string; empty string on failure.
    """
    result = subprocess.run(
        ["git", "diff", "--cached", "--", path],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def _extract_proc_args(text: str) -> str | None:
    """Extract the argument list string from a CREATE OR REPLACE PROCEDURE header.

    Handles simple single-line and multi-line signatures. Returns the raw
    argument text between the first `(` after the proc name and the matching `)`,
    or None if no PROCEDURE header is found.

    Args:
        text: SQL text to search (may be a diff chunk or a full file).

    Returns:
        Argument list string (stripped), or None.
    """
    match = _PROC_HEADER_RE.search(text)
    if not match:
        return None
    start = match.end()
    depth = 1
    i = start
    while i < len(text) and depth > 0:
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
        i += 1
    return text[start : i - 1].strip()


def _get_head_file_text(path: str) -> str:
    """Return the HEAD version of a file as a string.

    Args:
        path: Repo-relative file path.

    Returns:
        File content string; empty string on failure.
    """
    result = subprocess.run(
        ["git", "show", f"HEAD:{path}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def detect_large_diff_signals(
    numstat: list[tuple[str, int, int]],
    threshold: int = LARGE_DIFF_THRESHOLD,
) -> list[tuple[str, str]]:
    """Detect large behavior-change diffs in existing modules.

    Checks staged files against _LARGE_DIFF_PATTERNS. Only fires for files
    that already exist in HEAD (not new additions — those are caught by the
    existing structural signals).

    Args:
        numstat: List of (path, added, removed) from _get_staged_numstat().
        threshold: Minimum added-line count to trigger. Defaults to
                   LARGE_DIFF_THRESHOLD from config.

    Returns:
        List of (signal_name, file_path) tuples for each match.
    """
    hits: list[tuple[str, str]] = []
    for path, added, _ in numstat:
        if added <= threshold:
            continue
        if not _file_exists_in_head(path):
            continue  # New file — covered by existing addition signals.
        for signal_name, pattern in _LARGE_DIFF_PATTERNS:
            if pattern.match(path):
                hits.append((signal_name, path))
                break
    return hits


def detect_sql_signature_changes(staged_files: list[str]) -> list[tuple[str, str]]:
    """Detect SQL procedure argument-list changes in staged .sql files.

    For each staged .sql file, compares the argument list of every
    CREATE OR REPLACE PROCEDURE header in the diff against the HEAD version.
    Fires if the argument list differs or if a new PROCEDURE header appears
    in an existing SQL file.

    Args:
        staged_files: List of all staged file paths (any status).

    Returns:
        List of ("SQL procedure signature change", file_path) tuples.
    """
    hits: list[tuple[str, str]] = []
    sql_files = [f for f in staged_files if f.lower().endswith(".sql")]
    for path in sql_files:
        diff_text = _get_sql_file_diff(path)
        if not diff_text:
            continue
        # Extract only the added lines from the diff (lines starting with '+',
        # excluding the '+++' header line).
        added_lines = "\n".join(
            line[1:] for line in diff_text.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        )
        new_args = _extract_proc_args(added_lines)
        if new_args is None:
            continue  # No PROCEDURE header in the diff additions.
        head_text = _get_head_file_text(path)
        if not head_text:
            # File is new — the addition signal handles this; skip here.
            continue
        head_args = _extract_proc_args(head_text)
        if head_args is None or new_args != head_args:
            hits.append(("SQL procedure signature change", path))
    return hits


def _get_all_staged_files() -> list[str]:
    """Return repo-relative paths for all staged files (any status).

    Returns:
        List of repo-relative path strings.
    """
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        return []
    return result.stdout.strip().splitlines()


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------


def detect_structural_signals(
    added_files: list[str],
    new_services: list[str],
) -> list[tuple[str, str]]:
    """Detect structural-change signals from the staged additions.

    Args:
        added_files: List of added file paths from the staged index.
        new_services: List of new service names from docker-compose diffs.

    Returns:
        List of (signal_name, file_or_service) tuples for each hit.
    """
    hits: list[tuple[str, str]] = []
    for path_str in added_files:
        for signal_name, pattern in _STRUCTURAL_SIGNALS:
            if pattern.search(path_str):
                hits.append((signal_name, path_str))
                break
    for service in new_services:
        hits.append(("new docker-compose service", service))
    return hits


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    """Run the structural-change detector against the staged diff.

    Checks for:
    1. New structural additions (models, services, packages, SQL namespaces).
    2. Large behavior diffs (>threshold added lines) in existing modules.
    3. SQL procedure argument-list changes in staged .sql files.

    Returns:
        Exit code: 0 if clean or escape hatch; 1 if structural change
        detected without a matching components.json update.
    """
    commit_msg = _get_commit_message()
    if ESCAPE_HATCH in commit_msg:
        return 0

    added_files = _get_staged_additions()
    new_services = _get_staged_service_additions()
    numstat = _get_staged_numstat()
    all_staged = _get_all_staged_files()

    addition_hits = detect_structural_signals(added_files, new_services)
    large_diff_hits = detect_large_diff_signals(numstat)
    sql_sig_hits = detect_sql_signature_changes(all_staged)

    hits = addition_hits + large_diff_hits + sql_sig_hits
    if not hits:
        return 0

    if _is_components_json_staged():
        return 0

    # Structural change detected without a components.json update.
    print(
        "\n🏗️  Structural-Change Detected — Architecture Docs Required\n",
        file=sys.stderr,
    )
    print(
        "  The following structural changes were found in this commit:\n",
        file=sys.stderr,
    )
    for signal_name, target in hits:
        print(f"  • {signal_name}: {target}", file=sys.stderr)
    print(
        "\n  Rule: structural changes must include a matching update to\n"
        "  docs/components.json in the same commit.\n\n"
        "  Options:\n"
        "    1. Add or update the component entry in docs/components.json.\n"
        "    2. If this change genuinely does not affect architecture (e.g.\n"
        "       vendored code, pure rename, large refactor preserving\n"
        "       component identity), include [NO-ARCH-UPDATE] in your\n"
        "       commit message to skip this check.\n"
        "    3. For large diffs: if the diff is a refactor not adding new\n"
        "       behavior, use [NO-ARCH-UPDATE].\n"
        "    4. For SQL signature changes: update docs/components.json to\n"
        "       reflect the new procedure contract.\n",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
