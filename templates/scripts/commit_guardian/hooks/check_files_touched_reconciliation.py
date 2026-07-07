"""
MODULE: check_files_touched_reconciliation
GOAL: Pre-commit hook that reports source files changed by a ticket's work but
    absent from the ticket's declared files_touched UNION out_of_scope,
    immediately before the ticket is allowed to reach status: done.
BUSINESS CONTEXT: BP-1100e-1 / BP-1100e-2 — advisory by default: reports
    undeclared source changes (.py, .sql, .ts, .tsx, .js) as a non-blocking
    advisory. Strict blocking is opt-in via predone_scope.strict: true in
    commit_guardian.json. Complements BP-1100a (fires before work starts;
    this hook fires after work is done).
ARCHITECTURE: Standalone hook in templates/scripts/commit_guardian/hooks/
    (portable — no leafcutter-internal imports). Computes branch diff plus
    staged source files, compares against files_touched UNION out_of_scope.
    Advisory by default (exit 0); blocks (exit 1) only in strict mode
    (predone_scope.strict: true in commit_guardian.json). Fail-open on all
    errors per BP-1100e-2. Registered in hooks_manifest.hooks[] of
    commit_guardian.json. When multiple done tickets are staged together,
    reconciliation uses the UNION of all their declared scopes so that a file
    declared by any one ticket is not cross-flagged against the others.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SOURCE_EXTENSIONS: frozenset[str] = frozenset({".py", ".sql", ".ts", ".tsx", ".js"})

# Path segment and filename markers that identify code-generated files.
# Slashed markers match full path segments; dot/underscore markers match
# generated filename stems (e.g. ".generated.", "_generated.").
GENERATED_PATH_PATTERNS: frozenset[str] = frozenset({
    "/generated/",
    "/.generated/",
    "/__generated__/",
    "/dist/",
    ".generated.",
    "_generated.",
})

# Well-known lock-file base-names (always exempt; no declarable behavior).
LOCKFILE_NAMES: frozenset[str] = frozenset({
    "poetry.lock",
    "Pipfile.lock",
    "package-lock.json",
    "yarn.lock",
    "composer.lock",
    "Gemfile.lock",
    "go.sum",
    "Cargo.lock",
    "pnpm-lock.yaml",
    "uv.lock",
})

_BRANCH_BASE_CANDIDATES: list[str] = ["origin/main", "main"]
_HOOK_TAG = "[check-predone-scope]"

# Module-level cache for the case-insensitivity probe result.  None means
# the probe has not yet run; True/False are cached outcomes.
_FS_CASE_INSENSITIVE: bool | None = None


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _get_staged_files() -> list[str]:
    """Return staged file paths from the git index, or empty list on error."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"{_HOOK_TAG} WARNING: git diff --cached failed: {exc}", file=sys.stderr)
        return []
    return [ln for ln in result.stdout.strip().splitlines() if ln.strip()]


def _get_repo_root() -> str:
    """Return the absolute git repo root path, or empty string on error."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(
            f"{_HOOK_TAG} WARNING: git rev-parse --show-toplevel failed: {exc}",
            file=sys.stderr,
        )
        return ""
    return result.stdout.strip()


def _get_branch_diff_files() -> frozenset[str]:
    """Return files changed in this branch relative to origin/main.

    Tries origin/main, then main; uses three-dot merge-base syntax.
    Fails open — returns empty frozenset when git is unavailable.

    Returns:
        frozenset of repo-relative path strings changed since the branch point.
    """
    for base in _BRANCH_BASE_CANDIDATES:
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", f"{base}...HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            print(
                f"{_HOOK_TAG} WARNING: git diff {base}...HEAD failed: {exc}",
                file=sys.stderr,
            )
            continue
        if result.returncode == 0:
            return frozenset(
                ln.strip()
                for ln in result.stdout.strip().splitlines()
                if ln.strip()
            )
    return frozenset()


def _is_case_insensitive_fs() -> bool:
    """Return True if the git working tree is on a case-insensitive filesystem.

    Detects case-insensitivity by querying ``git config --get core.ignoreCase``.
    Result is cached at module level so the subprocess call runs at most once
    per process invocation.  Fails open — returns False on any subprocess error,
    consistent with the hook's BP-1100e-2 fail-open policy.

    Returns:
        bool: True when ``core.ignoreCase`` is ``true`` (NTFS / APFS),
        False otherwise.
    """
    global _FS_CASE_INSENSITIVE
    if _FS_CASE_INSENSITIVE is not None:
        return _FS_CASE_INSENSITIVE
    try:
        result = subprocess.run(
            ["git", "config", "--get", "core.ignoreCase"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(
            f"{_HOOK_TAG} WARNING: git config core.ignoreCase failed: {exc}",
            file=sys.stderr,
        )
        _FS_CASE_INSENSITIVE = False
        return False
    _FS_CASE_INSENSITIVE = result.stdout.strip().lower() == "true"
    return _FS_CASE_INSENSITIVE


# ---------------------------------------------------------------------------
# Frontmatter parsing (pure — no I/O, no try/except)
# ---------------------------------------------------------------------------


def _extract_frontmatter(content: str) -> str | None:
    """Extract the YAML frontmatter block from ticket content.

    Args:
        content: Full file content.

    Returns:
        YAML block text between the leading and closing --- delimiters, or
        None when the frontmatter block is absent or malformed.
    """
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    return match.group(1) if match else None


def _strip_yaml_value(raw: str) -> str:
    """Strip surrounding quotes or inline YAML comment from a scalar value.

    Checks for a surrounding matching quote pair FIRST.  When the value is
    quoted, the literal interior is returned verbatim — a space-hash sequence
    inside the quoted span belongs to the path value, not to a YAML comment
    (e.g. ``"scripts/build #1.py"`` → ``scripts/build #1.py``).

    For unquoted values, a trailing inline YAML comment is stripped via the
    space-before-hash rule, which preserves hashes that appear directly in
    path segments without a leading space (e.g. ``scripts/build#1.py``).

    Args:
        raw: Raw string captured from YAML parsing.

    Returns:
        Cleaned scalar string value.
    """
    value = raw.strip()
    # Quoted value: return the interior directly without comment scanning.
    if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
        return value[1:-1]
    # Unquoted value: strip inline comment (space-hash rule).
    comment_idx = value.find(" #")
    if comment_idx != -1:
        value = value[:comment_idx].strip()
    return value


def _get_status(frontmatter: str) -> str:
    """Extract the status value from frontmatter text.

    Handles both unquoted (``status: done``) and quoted
    (``status: "done"`` / ``status: 'done'``) values.

    Args:
        frontmatter: Raw YAML text between the --- delimiters.

    Returns:
        Status string (e.g. 'done', 'in_progress'), or empty string if absent.
    """
    match = re.search(r"^status:\s*(\S+)", frontmatter, re.MULTILINE)
    return _strip_yaml_value(match.group(1)) if match else ""


def _split_flow_items(items_str: str) -> list[str]:
    """Split a YAML flow-sequence item string on commas, respecting quote pairs.

    A naive ``split(",")`` corrupts items that contain commas inside a quoted
    span (e.g. ``["scripts/a,b.py"]`` → two broken fragments).  This function
    tracks single and double quote state and splits only on commas that are
    outside any quoted span.

    Args:
        items_str: Raw substring between the ``[`` and ``]`` of a flow-sequence.

    Returns:
        List of raw (un-stripped) item strings suitable for passing to
        :func:`_strip_yaml_value`.
    """
    items: list[str] = []
    current: list[str] = []
    in_quote: str | None = None
    for char in items_str:
        if in_quote is None and char in ('"', "'"):
            in_quote = char
            current.append(char)
        elif in_quote is not None and char == in_quote:
            in_quote = None
            current.append(char)
        elif in_quote is None and char == ",":
            items.append("".join(current))
            current = []
        else:
            current.append(char)
    items.append("".join(current))
    return items


def _parse_yaml_list_field(frontmatter: str, field_name: str) -> list[str]:
    """Parse a YAML list field from raw frontmatter text.

    Supports both block-sequence (dashes at column 0 or indented — matching
    the PyYAML default column-0 dump as well as indented forms) and inline
    flow-sequence ``[item, item]`` syntax.  Strips surrounding single or double
    quotes and inline YAML comments from each item.

    For flow-sequences, uses :func:`_split_flow_items` to split on commas
    only outside quoted spans so that paths containing commas inside quotes
    (e.g. ``["scripts/a,b.py"]``) parse as single items.

    Args:
        frontmatter: Raw YAML text between the --- delimiters.
        field_name: Field to extract (e.g. 'files_touched', 'out_of_scope').

    Returns:
        List of stripped string values, or empty list if the field is absent.
    """
    # Block-sequence: field:\n[  ]*- item  (zero-or-more leading whitespace)
    pattern = rf"^{re.escape(field_name)}:\s*\n((?:[ \t]*-[ \t]+\S[^\n]*\n?)+)"
    match = re.search(pattern, frontmatter, re.MULTILINE)
    if match:
        raw_items = re.findall(r"^[ \t]*-[ \t]+(\S[^\n]*)", match.group(1), re.MULTILINE)
        return [v for v in (_strip_yaml_value(i) for i in raw_items) if v]

    # Flow-sequence: field: [item, item]  — split quote-aware to avoid
    # corrupting items whose values contain commas inside a quoted span.
    flow_pattern = rf"^{re.escape(field_name)}:\s*\[([^\]]*)\]"
    flow_match = re.search(flow_pattern, frontmatter, re.MULTILINE)
    if flow_match:
        raw_items = _split_flow_items(flow_match.group(1))
        return [v for v in (_strip_yaml_value(i) for i in raw_items) if v]

    return []


def _field_is_declared(frontmatter: str, field_name: str) -> bool:
    """Return True if the field key appears in the frontmatter, regardless of value.

    Differs from :func:`_parse_yaml_list_field` which returns an empty list for
    both absent and empty fields.  Use this function to distinguish a ticket that
    carries *no* ``files_touched`` key (absent — no declared baseline) from one
    that carries the key with an empty or non-list value.

    Args:
        frontmatter: Raw YAML text between the --- delimiters.
        field_name: Field name to test (e.g. 'files_touched').

    Returns:
        bool: True when ``<field_name>:`` appears at the start of any line in
        the frontmatter block.
    """
    pattern = rf"^{re.escape(field_name)}:"
    return bool(re.search(pattern, frontmatter, re.MULTILINE))


# ---------------------------------------------------------------------------
# Core reconciliation logic (pure — no I/O)
# ---------------------------------------------------------------------------


def _normalise_path(path: str) -> str:
    """Strip leading ./ and normalise path separators; apply case-folding on
    case-insensitive filesystems.

    Removes only a single leading ``./`` prefix using ``removeprefix`` so that
    hidden files and directories (e.g. ``.github/ci.py``, ``.hidden.py``) are
    never incorrectly stripped. The previous ``lstrip("./")`` call stripped ALL
    leading dot and slash characters, which destroyed leading-dot filenames.

    Args:
        path: Raw file path from frontmatter or git output.

    Returns:
        Normalised repo-relative path string, lowercased on case-insensitive
        filesystems.
    """
    normalised = path.strip().removeprefix("./").replace("\\", "/")
    if _is_case_insensitive_fs():
        return normalised.lower()
    return normalised


def is_source_file(path: str) -> bool:
    """Return True if the file has a source/executable extension.

    Source extensions (from BP-1100e-1): .py, .sql, .ts, .tsx, .js
    All other extensions (e.g. .md, .yaml, .json, .txt, .toml) are not source
    files and are never flagged as undeclared by the reconciliation hook.

    Args:
        path: File path to test.

    Returns:
        bool: True when the file extension is in SOURCE_EXTENSIONS.
    """
    return Path(path).suffix in SOURCE_EXTENSIONS


def is_docs_only_or_config_only_ticket(declared_files: list[str]) -> bool:
    """Return True if ALL declared files are non-source (docs-only or config-only).

    A ticket is considered docs-only or config-only when every path in its
    declared ``files_touched`` list has a non-source extension (i.e. NOT one
    of ``.py``, ``.sql``, ``.ts``, ``.tsx``, ``.js``).  Such tickets have
    legitimately narrow scope and should never be false-flagged for undeclared
    changes, because the reconciliation hook only flags undeclared SOURCE files.

    An empty ``declared_files`` list returns ``False`` — a ticket with no
    declared scope is not classified as a narrow docs/config-only ticket; it
    simply has nothing to reconcile against.

    Args:
        declared_files: List of file paths from the ticket's ``files_touched``
            frontmatter field.

    Returns:
        bool: True when every declared file is a non-source file; False when at
        least one declared file has a source extension, or when ``declared_files``
        is empty.
    """
    if not declared_files:
        return False
    return all(not is_source_file(p) for p in declared_files)


def _is_generated_file(path: str) -> bool:
    """Return True if the path belongs to a code-generated artifact.

    Prepends a leading slash before checking GENERATED_PATH_PATTERNS so
    segment markers (e.g. ``/generated/``) match full segments only, not
    substrings of unrelated names like ``not_generated/``.

    Args:
        path: File path to test (repo-relative or absolute).

    Returns:
        bool: True when a GENERATED_PATH_PATTERNS marker is found.
    """
    norm = "/" + path.replace("\\", "/").lstrip("/")
    return any(marker in norm for marker in GENERATED_PATH_PATTERNS)


def _is_lockfile(path: str) -> bool:
    """Return True if the file is a well-known dependency lock-file.

    Provides an explicit, readable guard even though most lock-files are
    already implicitly exempt because their extensions are not in
    SOURCE_EXTENSIONS.

    Args:
        path: File path to test.

    Returns:
        bool: True when the filename matches a known lock-file name.
    """
    return Path(path).name in LOCKFILE_NAMES


def _compute_undeclared(
    declared_scope: set[str],
    branch_diff_files: frozenset[str],
    staged_files: list[str],
) -> list[str]:
    """Compute source files changed but not in the declared scope.

    Args:
        declared_scope: Normalised set of paths from files_touched UNION out_of_scope.
        branch_diff_files: Files changed in commits on this branch (from git diff).
        staged_files: Files staged for the current commit.

    Returns:
        Sorted list of undeclared source file paths.
    """
    all_changed = branch_diff_files | frozenset(staged_files)
    changed_sources = {
        _normalise_path(p)
        for p in all_changed
        if is_source_file(p) and not _is_generated_file(p) and not _is_lockfile(p)
    }
    return sorted(changed_sources - declared_scope)


# ---------------------------------------------------------------------------
# Ticket scope extraction
# ---------------------------------------------------------------------------


def _get_ticket_scope(rel_path: str, repo_root: str) -> set[str] | None:
    """Return the normalised declared source scope for a done ticket.

    Reads the ticket file, parses frontmatter, and returns the set of
    normalised paths from ``files_touched`` UNION ``out_of_scope`` when the
    ticket is status: done and declares a ``files_touched`` key.

    Wires the ``is_docs_only_or_config_only_ticket`` guard explicitly (AC
    BP-1100e-1-iii): a ticket whose declared files are all non-source returns
    an empty set, contributing no source paths to the reconciliation union.

    Args:
        rel_path: Repo-relative path to the staged ticket .md file.
        repo_root: Absolute git repo root path (may be empty string).

    Returns:
        set[str] with normalised declared paths when the ticket is done and
        has a parseable scope; empty set for docs-only tickets; None when the
        ticket should be skipped (not done, key absent, read error, or empty
        scope after parsing).
    """
    abs_path = Path(repo_root, rel_path) if repo_root else Path(rel_path)

    try:
        content = abs_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(
            f"{_HOOK_TAG} WARNING: cannot read {rel_path}: {exc} — skipping",
            file=sys.stderr,
        )
        return None

    frontmatter = _extract_frontmatter(content)
    if frontmatter is None or _get_status(frontmatter) != "done":
        return None

    if not _field_is_declared(frontmatter, "files_touched"):
        print(
            f"{_HOOK_TAG} skipped (no files_touched declared in ticket): {rel_path}",
            file=sys.stderr,
        )
        return None

    files_touched = _parse_yaml_list_field(frontmatter, "files_touched")
    out_of_scope = _parse_yaml_list_field(frontmatter, "out_of_scope")

    if not files_touched and not out_of_scope:
        return None  # declared key present but resolves to empty — skip

    # Explicit docs/config-only guard (AC BP-1100e-1-iii): a ticket whose
    # declared files are all non-source has no source paths to add to the
    # reconciliation union.  Source changes are still caught because they are
    # absent from the (empty) union declared scope.
    if is_docs_only_or_config_only_ticket(files_touched):
        return set()

    return {_normalise_path(p) for p in files_touched + out_of_scope}


# ---------------------------------------------------------------------------
# Main entry point helpers
# ---------------------------------------------------------------------------


def _print_errors(all_errors: list[tuple[str, list[str]]]) -> None:
    """Print structured error output for undeclared source file violations.

    Args:
        all_errors: List of (ticket_path, undeclared_files) tuples.
    """
    print(
        f"\n{_HOOK_TAG} ERROR: source files changed but not declared in "
        "files_touched or out_of_scope",
        flush=True,
    )
    for ticket_path, undeclared_files in all_errors:
        print(f"\n  Ticket : {ticket_path}", flush=True)
        print("  Undeclared source files:", flush=True)
        for path in undeclared_files:
            print(f"    - {path}", flush=True)
    print(
        "\n  Fix: add the above files to files_touched (or out_of_scope if",
        flush=True,
    )
    print(
        "  intentionally excluded) in the ticket frontmatter before marking done.",
        flush=True,
    )


def _print_advisory(all_errors: list[tuple[str, list[str]]]) -> None:
    """Print advisory output for undeclared source file violations (non-blocking).

    Args:
        all_errors: List of (ticket_path, undeclared_files) tuples.
    """
    print(
        f"\n{_HOOK_TAG} ADVISORY: source files changed but not declared in "
        "files_touched or out_of_scope (advisory mode — commit not blocked).",
        flush=True,
    )
    for ticket_path, undeclared_files in all_errors:
        print(f"\n  Ticket : {ticket_path}", flush=True)
        print("  Undeclared source files (advisory — not blocking):", flush=True)
        for path in undeclared_files:
            print(f"    - {path}", flush=True)
    print(
        "\n  To block commits on this condition, set predone_scope.strict: true",
        flush=True,
    )
    print(
        "  in commit_guardian.json. To suppress this advisory, add the above",
        flush=True,
    )
    print(
        "  files to files_touched (or out_of_scope) in the ticket frontmatter.",
        flush=True,
    )


def _load_strict_mode(repo_root: str) -> bool:
    """Load the strict mode setting from commit_guardian.json.

    Reads the predone_scope.strict field from commit_guardian.json. Fails open
    — returns False when the file is absent, unreadable, or malformed.

    Searches for commit_guardian.json at two locations in order:
    1. scripts/commit_guardian/commit_guardian.json (installed path)
    2. templates/scripts/commit_guardian/commit_guardian.json (worktree path)

    Args:
        repo_root: Absolute path to the git repo root.

    Returns:
        bool: True when strict mode is explicitly enabled; False otherwise.
    """
    if not repo_root:
        return False
    primary = Path(repo_root, "scripts", "commit_guardian", "commit_guardian.json")
    templates = Path(
        repo_root, "templates", "scripts", "commit_guardian", "commit_guardian.json"
    )
    config_path = (
        primary if primary.exists() else (templates if templates.exists() else None)
    )
    if config_path is None:
        return False
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        # Shape guard: wrong-shape configs (None, list, etc.) must not crash.
        # Only a Python bool True (JSON true) enables strict mode; truthy
        # non-bool values such as "yes" or 1 do not enable it.
        if not isinstance(data, dict):
            return False
        section = data.get("predone_scope")
        if not isinstance(section, dict):
            return False
        return section.get("strict") is True
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        print(
            f"{_HOOK_TAG} WARNING: cannot read commit_guardian.json: {exc}"
            " — using advisory mode",
            file=sys.stderr,
        )
        return False


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Run the pre-done scope reconciliation pre-commit hook.

    Two-pass algorithm for multi-ticket commits:
      Pass 1 — identify every staged done ticket and collect the UNION of all
               their declared source scopes (files_touched UNION out_of_scope).
      Pass 2 — compute undeclared source files against that union, so a file
               declared by ANY staged done ticket is not cross-flagged against
               the others (fixes the multi-ticket cross-flag defect).

    Fail-open contract (BP-1100e-2): every sub-function in this hook returns a
    safe default on error rather than propagating. _get_staged_files returns [],
    _get_repo_root returns "", _get_ticket_scope returns None, and
    _load_strict_mode returns False — so any internal error collapses to a
    clean 0-exit.

    Returns:
        0 when clean, in advisory mode (default), or on any reconciliation error.
        1 only when strict mode is enabled AND undeclared source files are found.
    """
    staged_files = _get_staged_files()
    if not staged_files:
        return 0

    repo_root = _get_repo_root()

    # Pass 1: collect all done ticket scopes and compute their union.
    done_ticket_scopes: list[tuple[str, set[str]]] = []
    for rel_path in staged_files:
        if not rel_path.startswith("tickets/") or not rel_path.endswith(".md"):
            continue
        scope = _get_ticket_scope(rel_path, repo_root)
        if scope is not None:
            done_ticket_scopes.append((rel_path, scope))

    if not done_ticket_scopes:
        return 0

    union_declared: set[str] = set()
    for _, scope in done_ticket_scopes:
        union_declared.update(scope)

    # Pass 2: compute undeclared against the union scope.
    branch_diff = _get_branch_diff_files()
    ticket_path_norms = {_normalise_path(rp) for rp, _ in done_ticket_scopes}
    all_undeclared = _compute_undeclared(union_declared, branch_diff, staged_files)
    all_undeclared = [p for p in all_undeclared if p not in ticket_path_norms]

    if not all_undeclared:
        return 0

    all_errors: list[tuple[str, list[str]]] = [
        (rp, all_undeclared) for rp, _ in done_ticket_scopes
    ]

    strict = _load_strict_mode(repo_root)
    if strict:
        _print_errors(all_errors)
        return 1
    _print_advisory(all_errors)
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-07-06 [python-coder/BP-1100e-1]: Initial implementation.
#   AC BP-1100e-1: fires at the pre-done commit gate when a staged ticket
#   has status: done. Computes branch diff (origin/main...HEAD) plus staged
#   files, filters to source extensions (.py/.sql/.ts/.tsx/.js), and flags
#   paths absent from files_touched UNION out_of_scope. Fail-open on all
#   git/IO errors per BP-1100e-2. Standalone — no leafcutter-internal
#   imports for portability (ADR-001). Mirrors check-agent-spawn-consistency
#   entry in commit_guardian.json hooks_manifest.hooks[].
# - 2026-07-06 [python-coder/BP-1100e-1-i]: Add generated-file and
#   lockfile exemptions (AC BP-1100e-1-i). GENERATED_PATH_PATTERNS covers
#   path segments (/generated/, /__generated__/, /dist/, /.generated/) and
#   stem markers (.generated., _generated.). LOCKFILE_NAMES covers common
#   lock-files by basename. Both _is_generated_file() and _is_lockfile()
#   are pure (no I/O). _compute_undeclared() filters both categories.
# - 2026-07-06 [python-coder/BP-1100e-1-ii]: Add case-folding to
#   _normalise_path() for case-insensitive filesystems (NTFS/APFS).
#   AC BP-1100e-1-ii: paths that differ only by case (e.g.
#   "Scripts/Build_Phases.py" vs "scripts/build_phases.py") are treated
#   as matching on case-insensitive filesystems.
#   _is_case_insensitive_fs() queries git config --get core.ignoreCase,
#   caches the boolean result at module level (_FS_CASE_INSENSITIVE), and
#   fails open (returns False on SubprocessError) per BP-1100e-2 policy.
#   Separator normalisation (backslash → forward slash) and case-folding
#   compose correctly in _normalise_path() — both applied in sequence.
# - 2026-07-06 [python-coder/BP-1100e-1-iii]: Add narrow-scope exemption
#   for docs-only and config-only tickets.
#   AC BP-1100e-1-iii: a ticket whose actual changes touch only declared
#   documentation or config files (no .py/.sql/.ts/.tsx/.js source file) is
#   a clean pass and must not be false-flagged.
#   Changes: renamed _is_source_file() → is_source_file() (public API); added
#   is_docs_only_or_config_only_ticket() public helper that returns True when
#   every declared file is a non-source file. The key invariant — that
#   _compute_undeclared() only ever collects SOURCE files into changed_sources
#   — was already correct; these two public functions make the contract
#   explicit and testable by downstream consumers.
# - 2026-07-07 [python-coder/BP-1100e-1-iv]: Add absent-frontmatter no-op
#   guard (AC BP-1100e-1-iv).
#   When the files_touched YAML key is entirely absent from a ticket's
#   frontmatter (not merely an empty list), _check_ticket() now skips
#   reconciliation and prints an advisory to stderr so the skip is visible
#   rather than silent. This keeps the hook harmless in consumer projects
#   that do not use the files_touched convention at all.
#   Changes: added _field_is_declared(frontmatter, field_name) -> bool pure
#   helper that uses a regex line-anchor to detect key presence without
#   parsing the value; added early-return branch in _check_ticket() that
#   fires when _field_is_declared(frontmatter, "files_touched") is False;
#   updated _check_ticket() docstring to document the no-op behaviour.
# - 2026-07-07 [python-coder/BP-1100e-2]: Make reconciliation advisory by
#   default; strict blocking is opt-in (AC BP-1100e-2).
#   Changes: added `import json` at module level; added _print_advisory()
#   for non-blocking output; added _load_strict_mode(repo_root) -> bool
#   which reads predone_scope.strict from commit_guardian.json — searches
#   primary path (scripts/commit_guardian/) then templates path; fails open
#   (returns False) on any read/parse error. Modified main() to call
#   _load_strict_mode() when errors are found and branch on the result:
#   strict=True → _print_errors() + return 1 (blocking as before); strict=False
#   (default) → _print_advisory() + return 0 (advisory, no block). The fail-open
#   contract is preserved: each sub-function returns a safe default on error so
#   the whole hook exits 0 on any internal failure. Added predone_scope section
#   to commit_guardian.json with strict: false default.
# - 2026-07-07 [python-coder/EPIC-PhantomDoneFilesTouched BP-1100e remediation]:
#   Fix 8 confirmed defects discovered by code review and adversarial testing.
#   D1 (CRITICAL — column-0 block sequences): _parse_yaml_list_field regex
#     changed from [ \t]+ to [ \t]* (zero-or-more leading whitespace) in both
#     the outer pattern and the items findall, so PyYAML default column-0 dashes
#     parse correctly. Real-ticket parse test added.
#   D2 (CRITICAL — FileNotFoundError fail-open hole): all four subprocess-calling
#     functions (_get_staged_files, _get_repo_root, _get_branch_diff_files,
#     _is_case_insensitive_fs) now catch (OSError, subprocess.SubprocessError)
#     instead of subprocess.SubprocessError only, so a missing git binary
#     produces fail-open exit 0 rather than an uncaught traceback.
#   D3 (quoted declared paths): _strip_yaml_value() pure helper added; called
#     by _parse_yaml_list_field() and _get_status() to remove surrounding
#     single/double quotes and trailing inline comments from every parsed item.
#   D4 (multi-ticket cross-flag): main() restructured to two-pass algorithm.
#     Pass 1 collects all staged done tickets and computes the UNION of their
#     declared scopes via _get_ticket_scope(). Pass 2 compares against that
#     union, preventing cross-flagging between tickets in the same commit.
#     _check_ticket() replaced by _get_ticket_scope() which returns set[str]|None.
#   D5 (flow-style lists): _parse_yaml_list_field() now falls through to a
#     flow-sequence branch when the block-sequence pattern fails: parses
#     field: [a, b] via split(",") + _strip_yaml_value().
#   D6 (_normalise_path lstrip over-strips): lstrip("./") replaced with
#     str.removeprefix("./") so only a single leading "./" is removed and
#     hidden files (.github/ci.py, .hidden.py) retain their leading dot.
#   D7 (dead code wired): is_docs_only_or_config_only_ticket() is now called
#     explicitly in _get_ticket_scope() as the AC BP-1100e-1-iii guard.
#     Docs-only tickets return set() (empty source scope), contributing no
#     source paths to the union; source changes are still caught as undeclared.
#   D8 (quoted status): _get_status() now passes its captured value through
#     _strip_yaml_value() so status: "done" and status: 'done' are recognised.
# - 2026-07-07 [python-coder/EPIC-PhantomDoneFilesTouched BP-1100e remediation round 2]:
#   Fix 4 confirmed defects and 1 low-priority gap found by code review of commit
#   08b225cf (remediation round 1).
#   R2-Fix1 (HIGH — fail-open hole in _load_strict_mode): a valid-JSON-but-wrong-shape
#     config such as {"predone_scope": null} or [] raised AttributeError from .get()
#     which propagated through main() and crashed the hook (exit 1 even in advisory
#     mode). Fix: explicit isinstance checks before .get() calls; only JSON boolean
#     true (Python True) enables strict mode (section.get("strict") is True); caught
#     exception tuple broadened to (OSError, ValueError, TypeError, AttributeError)
#     as belt-and-suspenders. Tests: null, [], {"strict":"yes"}, {} all return False;
#     {"strict":true} still returns True; integration test verifies advisory exit 0
#     with strict:"yes" config and an undeclared file staged.
#   R2-Fix2 (MEDIUM — Rule 3 violation in _get_branch_diff_files): the except block
#     previously had bare `continue` with no WARNING log. Fixed by binding `as exc`
#     and adding print(..., file=sys.stderr) before continue. Test verifies WARNING
#     appears in stderr when git raises OSError.
#   R2-Fix3 (MEDIUM — false-positive for quoted paths containing ' #'): _strip_yaml_value
#     stripped a trailing ' #comment' BEFORE checking for surrounding quotes, so
#     "scripts/build #1.py" was mangled to "scripts/build (dangling quote). Fixed by
#     reversing the order: quoted values return their interior verbatim; comment
#     stripping only applies to unquoted values. Tests: quoted path with ' #' is
#     preserved; integration test verifies main() does not flag it as undeclared.
#   R2-Fix4 (MEDIUM — test gaps): added tests: (a) docs-only ticket with stray source
#     file staged → stray source is caught in strict mode (exit 1) and reported
#     in advisory mode (exit 0); (b) end-to-end main() test using real ticket 02
#     verbatim — clean with declared files, flagged with an extra undeclared .py;
#     (c) D4 cross-flag test converted to column-0 (PyYAML default) fixtures.
#   R2-Fix5 (LOW — flow-list comma in quoted items): naive split(",") corrupted
#     ["a,b.py"] into two broken fragments. Added _split_flow_items() pure helper
#     that splits only on commas outside quoted spans; _parse_yaml_list_field flow
#     branch now uses it instead of str.split(","). Tests: single comma-in-quoted
#     item, multiple unquoted items, mixed quoted/unquoted items.
# ====================================================================
