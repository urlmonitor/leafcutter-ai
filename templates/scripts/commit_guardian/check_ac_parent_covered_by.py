"""
MODULE: check_ac_parent_covered_by
GOAL: Pre-commit hook that blocks a commit when a staged child AC YAML file
    declares a parent via depends_on, but the parent AC YAML file's covered_by
    field does not include the child's ID.
BUSINESS CONTEXT: The AC store uses a parent-child hierarchy enforced at two
    levels: the tree-structure (handled by check_ac_limits.py) and the
    covered_by back-link (this hook). When a child AC is committed, the parent
    must explicitly list that child in its covered_by field so the store remains
    internally consistent and tooling can navigate the hierarchy in both
    directions. This hook enforces the back-link at commit time, before
    inconsistencies enter the shared history.
ARCHITECTURE: Reads staged .yaml files from docs/acceptance-criteria/ (via
    git diff --cached, or HOOK_TEST_FILES env var for testing). For each staged
    AC child file, derives the parent ID using derive_parent_id() from
    scripts/ac_store/ac_parent_id.py. Resolves the parent file on disk (using
    the same directory tree as the child), loads its covered_by field, and
    checks that the child ID appears in the list. If not, emits a structured
    error message naming the child ID, parent ID, parent file path, and the
    corrective action required.

    Fail-open: any unexpected exception exits 0 with [check-ac-parent-covered-by]
    prefix on stderr so pre-commit never hard-blocks an unrelated staging failure.

Exit codes:
    0 - All staged AC YAML files pass the covered_by check (or no files staged)
    1 - One or more parent/covered_by violations detected

Usage:
    python scripts/commit_guardian/run_hook.py \\
        scripts/commit_guardian/check_ac_parent_covered_by.py

DOC_LINKS:
  - docs/reference/ac-schema.md
  - docs/architecture/adrs/ADR-008-ac-store-schema-id-format-enforcement.md

DECISION HISTORY:
  - 2026-06-08 [python-coder/ACS-100i-2]: Created check_ac_parent_covered_by.py.
    Implements ACS-100i-2 Gherkin spec: block commit when child AC staged but
    parent covered_by omits the child ID. Reuses derive_parent_id() from
    scripts/ac_store/ac_parent_id.py (ACS-100i-1 deliverable).
    Fail-open on unexpected exceptions. Uses HOOK_TEST_FILES for unit testing.
    (#EPIC-AcParentChildLinkEnforcement/02)
  - 2026-06-08 [python-coder/ACS-100i-3]: Verified full ancestry chain traversal.
    The hook enforces only the immediate parent link (using derive_parent_id on
    the child's own ID), not the grandparent. Only the immediate parent must list
    the child in covered_by; grandparent ACs are not required to list grandchildren
    directly. Six new TestThreeLevelAncestryChain tests added to confirm L1→L2→L3
    chain behaviour: blocked when L2 omits L3, allowed when L2 includes L3, and
    grandparent (L1) does NOT need to list L3.
    (#EPIC-AcParentChildLinkEnforcement/03)
  - 2026-06-08 [python-coder/ACS-100i-2-i]: Fixed binary-content fail-open bug.
    UnicodeDecodeError (subclass of ValueError, not OSError) was propagating
    uncaught from _load_file_yaml and _resolve_parent_file when reading binary
    .yaml files, crashing the hook instead of failing open. Fixed by widening
    except OSError to except (OSError, ValueError) in both functions. The
    _load_file_yaml warning message now includes the exception class name for
    observability. (AC: ACS-100i-2-i)
  - 2026-07-07 [python-coder/ACS-100i-2-i]: Narrowed _load_file_yaml exception
    handling to separate UnicodeDecodeError from OSError. UnicodeDecodeError now
    emits "WARNING: <filepath> -- non-UTF-8 content, skipping: <error>" (the
    canonical format from the AC spec). OSError retains its own message.
    Behaviour is identical (fail-open, return None); only the message format
    changes. Tests added in test_check_ac_parent_covered_by.py.
  - 2026-06-29 [python-coder/perf-fix]: Index-once performance fix. Replaced
    per-call full-store rglob walk in _resolve_parent_file with a single
    _build_parent_index() call in main(). The index (dict[str, str] mapping
    AC id -> absolute file path) is built once and threaded through _check_file
    and _resolve_parent_file as an explicit parameter. Cost drops from
    O(staged_files × store_files) to O(store_files + staged_files).
  - 2026-06-30 [python-coder/TICKET-20260629-AC_Hook_Store_Index]: Replaced the
    per-invocation _build_parent_index store walk in main() with a call to
    _ac_store_index.get_ac_index(). The rich id->dict index is used to derive the
    id->abs_path mapping that _build_parent_index previously built. The O(store_size)
    walk is now shared across all four AC guardrail hooks via the mtime cache.
  - 2026-08-25 [python-coder/GE-120a-1]: Replaced the silent fail-open branch in
    main() (previously: catch bare ImportError around _get_derive_parent_id(),
    print "cannot import derive_parent_id ...; skipping check (fail-open)", return
    an ordinary success). Now catches (ImportError, OSError) -- the OSError arm
    closes a second, previously-uncaught cannot-run shape where ac_parent_id.py
    exists as a directory (a corrupted/partial deploy), which used to fall through
    to the generic bottom-of-file catch-all. Both arms now call the new
    _emit_could_not_check() helper, which names the unreachable prerequisite and
    the number of staged files left unevaluated on stderr, and emits a
    machine-readable "RESULT: could_not_check" line via the new shared
    check_outcome module (OUTCOME_COULD_NOT_CHECK) -- independent of exit code,
    since GE-120a-2 may still choose to exit 0 for an "announce" disposition.
    The legacy "skipping check (fail-open)" line is no longer produced. The
    reachable-prerequisite path (main-checkout behaviour) is unchanged: the same
    staged set still blocks with the same violations. This criterion does not by
    itself decide block-vs-announce; that remains GE-120a-2's concern.
    (#EPIC-TrustThatAGreenCheckActuallyChecked/01)
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

try:
    from _ac_store_index import get_ac_index  # type: ignore[import]
    _AC_STORE_INDEX_AVAILABLE = True
except ImportError:
    _AC_STORE_INDEX_AVAILABLE = False

try:
    from check_outcome import OUTCOME_COULD_NOT_CHECK, emit_result  # type: ignore[import]
except ImportError:
    # check_outcome.py is deployed alongside this file in every real layout
    # (build.py copies the whole templates/scripts/commit_guardian/ tree), so
    # this fallback exists only for a working copy that exposes this check
    # script in isolation (e.g. a test fixture) -- exactly the kind of
    # partially-deployed layout GE-120a-1 is about. The values here MUST stay
    # in sync with check_outcome.py.
    OUTCOME_COULD_NOT_CHECK = "could_not_check"

    def emit_result(outcome: str) -> None:
        """Fallback RESULT-line emitter used when check_outcome is absent."""
        print(f"RESULT: {outcome}", file=sys.stdout)

_HOOK_PREFIX = "[check-ac-parent-covered-by]"
_AC_STORE_DIR = "docs/acceptance-criteria"


# ---------------------------------------------------------------------------
# Project root detection
# ---------------------------------------------------------------------------


def _find_project_root() -> Path | None:
    """Find the project root by walking up from cwd.

    Uses HOOK_ROOT env var when set (testing / CI override).

    Returns:
        Absolute Path of the project root, or None if not found.
    """
    env_root = os.environ.get("HOOK_ROOT")
    if env_root:
        return Path(env_root)

    for ancestor in [Path.cwd(), *Path.cwd().parents]:
        if (ancestor / ".git").exists() or (ancestor / "CLAUDE.md").exists():
            return ancestor

    return None


# ---------------------------------------------------------------------------
# Staged file detection
# ---------------------------------------------------------------------------


def _get_staged_ac_paths() -> list[str]:
    """Return staged .yaml file paths under docs/acceptance-criteria/.

    Uses HOOK_TEST_FILES env var when set (OS pathsep- or newline-separated).
    In HOOK_NO_GIT mode, returns an empty list (no git interaction).

    Returns:
        List of path strings (absolute when from HOOK_TEST_FILES,
        relative to repo root when from git diff --cached).
    """
    test_files = os.environ.get("HOOK_TEST_FILES")
    if test_files:
        raw_paths = test_files.replace(os.pathsep, "\n").splitlines()
        return [
            p.strip()
            for p in raw_paths
            if p.strip() and p.strip().endswith(".yaml")
        ]

    if os.environ.get("HOOK_NO_GIT"):
        return []

    def _name_only(extra: list[str]) -> set[str] | None:
        """Run the staged name-only diff with *extra* args appended."""
        try:
            proc = subprocess.run(
                ["git", "diff", "--cached", "--name-only", "--diff-filter=AM", *extra],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            print(
                f"{_HOOK_PREFIX} WARNING: could not run git diff: {exc}",
                file=sys.stderr,
            )
            return None
        if proc.returncode != 0:
            return None
        return {line.strip() for line in proc.stdout.splitlines() if line.strip()}

    changed = _name_only([])
    if changed is None:
        return []

    # Merge commits: a merge stages the ENTIRE incoming branch, so a plain
    # --cached diff names every AC the other side ever touched. This gate would
    # then demand that the merge author repair parent/child back-links in AC
    # trees they neither authored nor modified — unfixable for them, so the only
    # way through is to bypass the hook, which is how a real missing back-link
    # later slips past it. Narrow the scope to files whose merge result differs
    # from BOTH parents (the content the merge itself introduces); anything
    # taken verbatim from either side was already gated on that side.
    # Non-merge commits are unaffected. Mirrors the same fix in check_ac_limits.
    try:
        merge_probe = subprocess.run(
            ["git", "rev-parse", "-q", "--verify", "MERGE_HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        in_merge = merge_probe.returncode == 0
    except (subprocess.SubprocessError, OSError) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: could not check MERGE_HEAD: {exc}",
            file=sys.stderr,
        )
        in_merge = False

    if in_merge:
        vs_other_parent = _name_only(["MERGE_HEAD"])
        if vs_other_parent is not None:
            changed &= vs_other_parent

    return [
        line
        for line in sorted(changed)
        if _AC_STORE_DIR in line
        and line.endswith(".yaml")
    ]


# ---------------------------------------------------------------------------
# YAML loading (soft dependency on PyYAML; minimal fallback)
# ---------------------------------------------------------------------------


def _load_yaml_safe(content: str, source_label: str) -> dict | None:
    """Parse a YAML string, returning a dict or None on failure.

    Tries PyYAML first; falls back to a minimal line-oriented parser for
    simple top-level scalar/list fields when PyYAML is unavailable.

    Args:
        content: Raw YAML string.
        source_label: Human-readable label used in error messages.

    Returns:
        Parsed dict on success, None on parse failure (fail-open).
    """
    try:
        import yaml  # type: ignore[import]

        try:
            data = yaml.safe_load(content)
            return data if isinstance(data, dict) else None
        except yaml.YAMLError as exc:
            print(
                f"{_HOOK_PREFIX} WARNING: YAML parse error in {source_label}: {exc}",
                file=sys.stderr,
            )
            return None
    except ImportError:
        pass  # PyYAML absent — use minimal fallback

    # Minimal line-based fallback: handles top-level scalars only.
    # Lists (e.g. covered_by: [ACS-100a, ACS-100b]) are parsed as raw strings.
    result: dict = {}
    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        if not line or line.startswith("#") or line[0:1] in (" ", "\t"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip()
    return result or None


def _load_file_yaml(file_path: str) -> dict | None:
    """Read and parse a YAML file from disk.

    Fails open on UnicodeDecodeError (binary content): logs a WARNING naming
    the file path and the decode error, then returns None so the hook
    continues without blocking the commit (ACS-100i-2-i).

    Args:
        file_path: Absolute or repo-relative path to the YAML file.

    Returns:
        Parsed dict on success, None on I/O or parse failure.
    """
    path = Path(file_path)
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: {file_path} -- non-UTF-8 content, skipping: {exc}",
            file=sys.stderr,
        )
        return None
    except OSError as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: cannot read file {file_path}: {exc}",
            file=sys.stderr,
        )
        return None
    return _load_yaml_safe(content, source_label=str(file_path))


# ---------------------------------------------------------------------------
# covered_by extraction
# ---------------------------------------------------------------------------


def _extract_covered_by(data: dict) -> list[str]:
    """Extract the covered_by list from a parsed AC YAML dict.

    Handles three YAML representations produced by safe_load or the minimal
    fallback:
    - PyYAML list: ``covered_by: [ACS-100a, ACS-100b]``  → ``["ACS-100a", "ACS-100b"]``
    - PyYAML empty list: ``covered_by: []``               → ``[]``
    - Minimal fallback string: ``"[ACS-100a, ACS-100b]"``→ parsed via split
    - PyYAML null / missing / None                        → ``[]``

    Args:
        data: Parsed YAML dict from an AC file.

    Returns:
        List of child AC ID strings. Empty list when covered_by is absent or empty.
    """
    raw = data.get("covered_by")
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if item is not None and str(item).strip()]
    if isinstance(raw, str):
        # Minimal fallback: strip outer brackets and split on commas.
        stripped = raw.strip()
        if stripped in ("[]", ""):
            return []
        stripped = stripped.strip("[]")
        return [item.strip() for item in stripped.split(",") if item.strip()]
    return []


# ---------------------------------------------------------------------------
# Parent file resolution
# ---------------------------------------------------------------------------


def _build_parent_index(ac_store_root: Path) -> dict[str, str]:
    """Walk the AC store once and build an id -> absolute_path index.

    Reads every .yaml file under ac_store_root exactly once. Files that cannot
    be read or parsed are silently skipped (fail-open: hook must not block on
    unreadable store files). First occurrence of each id wins (depth-first).

    Args:
        ac_store_root: Root Path of the AC store directory.

    Returns:
        Dict mapping AC id strings to their absolute file path strings.
        Returns an empty dict when ac_store_root is not a directory.
    """
    if not ac_store_root.is_dir():
        return {}

    index: dict[str, str] = {}
    for yaml_file in ac_store_root.rglob("*.yaml"):
        try:
            content = yaml_file.read_text(encoding="utf-8")
        except (OSError, ValueError):
            continue
        data = _load_yaml_safe(content, source_label=str(yaml_file))
        if data is None:
            continue
        file_id = str(data.get("id", "")).strip()
        if file_id and file_id not in index:
            index[file_id] = str(yaml_file.resolve())
    return index


def _resolve_parent_file(
    child_path: str,
    parent_id: str,
    project_root: Path | None,
    parent_index: dict[str, str] | None = None,
) -> str | None:
    """Locate the YAML file for parent_id in the AC store.

    When a pre-built index is provided (preferred), performs an O(1) dict
    lookup and avoids any filesystem walk.  When no index is provided (legacy
    / direct-call path), falls back to the original exhaustive rglob walk so
    that callers that do not thread the index continue to work correctly.

    Args:
        child_path: Absolute or relative path to the child AC YAML file.
        parent_id: The parent AC ID string to find (e.g. "ACS-300h").
        project_root: Resolved project root Path, or None.
        parent_index: Optional pre-built id->path mapping from
            _build_parent_index(). When provided, the AC store is NOT walked.

    Returns:
        Absolute path string to the parent YAML file, or None if not found.
    """
    # Fast path: use the pre-built index when available.
    if parent_index is not None:
        return parent_index.get(parent_id)

    # Slow path (fallback): walk the AC store.  Used when the function is
    # called directly without a pre-built index (e.g. from older tests or
    # external callers that have not been updated).
    if project_root:
        ac_store_root = project_root / _AC_STORE_DIR
    else:
        ac_store_root = Path.cwd() / _AC_STORE_DIR

    if not ac_store_root.is_dir():
        # AC store absent — nothing to search.
        return None

    for yaml_file in ac_store_root.rglob("*.yaml"):
        try:
            content = yaml_file.read_text(encoding="utf-8")
        except (OSError, ValueError):
            continue
        data = _load_yaml_safe(content, source_label=str(yaml_file))
        if data is None:
            continue
        file_id = str(data.get("id", "")).strip()
        if file_id == parent_id:
            return str(yaml_file.resolve())

    return None


# ---------------------------------------------------------------------------
# derive_parent_id import (graceful fallback when module path not on sys.path)
# ---------------------------------------------------------------------------


def _get_derive_parent_id():
    """Import and return the derive_parent_id function.

    Attempts three strategies in order:

    1. Standard package import (works when scripts/ is on sys.path).
    2. Locate ac_parent_id.py relative to this script's own location
       (works when the hook is invoked directly from the project tree, which
       is the normal pre-commit use case).
    3. Locate ac_parent_id.py relative to the project root detected by
       _find_project_root() excluding any HOOK_ROOT override (HOOK_ROOT is
       used for AC store filesystem checks, not for Python module resolution).

    Returns:
        The derive_parent_id callable.

    Raises:
        ImportError: When the module cannot be found by any strategy.
    """
    try:
        from scripts.ac_store.ac_parent_id import derive_parent_id  # type: ignore[import]
    except ImportError:
        pass
    else:
        return derive_parent_id

    import importlib.util

    def _load_from_path(module_path: Path):
        """Load derive_parent_id from an explicit path."""
        spec = importlib.util.spec_from_file_location("ac_parent_id", str(module_path))
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod.derive_parent_id

    # Strategy 2: relative to this script's own location.
    # This script lives at <project_root>/scripts/commit_guardian/check_*.py.
    # ac_parent_id.py lives at <project_root>/scripts/ac_store/ac_parent_id.py.
    script_dir = Path(__file__).resolve().parent  # .../scripts/commit_guardian/
    candidate = script_dir.parent / "ac_store" / "ac_parent_id.py"
    if candidate.exists():
        fn = _load_from_path(candidate)
        if fn is not None:
            return fn

    # Strategy 3: project root via cwd / .git / CLAUDE.md walk (no HOOK_ROOT).
    # Intentionally bypass HOOK_ROOT here — it points to a test tmpdir, not the
    # real project, and would give a false "not found" during unit tests.
    for ancestor in [Path.cwd(), *Path.cwd().parents]:
        if (ancestor / ".git").exists() or (ancestor / "CLAUDE.md").exists():
            candidate3 = ancestor / "scripts" / "ac_store" / "ac_parent_id.py"
            if candidate3.exists():
                fn = _load_from_path(candidate3)
                if fn is not None:
                    return fn
            break

    msg = "ac_parent_id.py not found via package import, script-relative, or project-root walk."
    raise ImportError(msg)


# ---------------------------------------------------------------------------
# Per-file check
# ---------------------------------------------------------------------------


def _check_file(
    file_path: str,
    derive_parent_id,
    parent_index: dict[str, str] | None = None,
    ac_store_index: dict[str, dict] | None = None,
) -> list[str]:
    """Run the parent covered_by check for a single staged AC YAML file.

    Algorithm:
    1. Load and parse the staged file.
    2. Extract the child's AC id and its depends_on list.
    3. For each entry in depends_on, derive the parent ID using derive_parent_id().
       (The depends_on list may contain direct parent IDs or grandparent IDs;
       we check each one independently.)
    4. Locate the parent AC data — via ac_store_index (O(1) dict lookup) when
       available, or via parent_index id->path + disk read as a fallback.
    5. Load the parent's covered_by list.
    6. Verify the child's ID appears in covered_by.

    Args:
        file_path: Absolute path to the staged AC YAML file.
        derive_parent_id: The derive_parent_id callable from ac_parent_id module.
        parent_index: Optional pre-built id->path mapping from
            _build_parent_index(). When provided and ac_store_index is None,
            parent resolution is O(1) instead of a full AC store walk.
            Pass None to use the legacy per-call walk (backward-compatible).
        ac_store_index: Optional pre-built id->full-dict mapping from
            _ac_store_index.get_ac_index(). When provided, parent data is
            fetched directly from the index without any filesystem read.
            Takes precedence over parent_index when both are non-None.

    Returns:
        List of human-readable violation strings. Empty list = no violations.
    """
    violations: list[str] = []

    project_root = _find_project_root()

    staged_data = _load_file_yaml(file_path)
    if staged_data is None:
        # Cannot parse file — fail-open (do not block on parse error)
        return []

    child_id = str(staged_data.get("id", "")).strip()
    if not child_id:
        # No id field — not a recognisable AC file; skip
        return []

    # Extract depends_on: may be a list, a string, or absent
    raw_depends = staged_data.get("depends_on")
    if raw_depends is None:
        depends_on_list: list[str] = []
    elif isinstance(raw_depends, list):
        depends_on_list = [str(d).strip() for d in raw_depends if d is not None and str(d).strip()]
    elif isinstance(raw_depends, str):
        # Minimal fallback: strip outer brackets and split
        stripped = raw_depends.strip().strip("[]")
        depends_on_list = [item.strip() for item in stripped.split(",") if item.strip()]
    else:
        depends_on_list = []

    if not depends_on_list:
        # No dependencies — no parent link to check
        return []

    # Derive the immediate parent ID from the child's own ID (not from depends_on).
    # The depends_on list may reference grandparent or cross-branch dependencies;
    # the covered_by enforcement applies only to the immediate structural parent
    # (the ID derived by stripping the last segment from child_id).
    immediate_parent_id = derive_parent_id(child_id)
    if immediate_parent_id is None:
        # Root-level AC — no parent by definition
        return []

    # Only enforce the covered_by link when the immediate parent appears in
    # depends_on. This prevents false positives for cross-branch depends_on
    # entries (e.g. a child that depends on a sibling, not its structural parent).
    if immediate_parent_id not in depends_on_list:
        return []

    # Fetch parent AC data.
    # Fast path: use the shared ac_store_index (no disk I/O needed).
    if ac_store_index is not None:
        parent_data = ac_store_index.get(immediate_parent_id)
        if parent_data is None:
            # Parent not in index — cannot enforce; fail-open
            print(
                f"{_HOOK_PREFIX} WARNING: parent AC '{immediate_parent_id}' "
                f"not found in index; skipping covered_by check for '{child_id}'",
                file=sys.stderr,
            )
            return []
        parent_file_label = immediate_parent_id  # no path available
    else:
        # Slow path: locate parent file on disk via parent_index or rglob walk.
        parent_file_path = _resolve_parent_file(
            file_path, immediate_parent_id, project_root, parent_index
        )
        if parent_file_path is None:
            print(
                f"{_HOOK_PREFIX} WARNING: parent file for ID '{immediate_parent_id}' "
                f"not found on disk; skipping covered_by check for '{child_id}'",
                file=sys.stderr,
            )
            return []

        parent_data = _load_file_yaml(parent_file_path)
        if parent_data is None:
            print(
                f"{_HOOK_PREFIX} WARNING: cannot parse parent file {parent_file_path}; "
                f"skipping covered_by check for '{child_id}'",
                file=sys.stderr,
            )
            return []
        parent_file_label = parent_file_path

    covered_by = _extract_covered_by(parent_data)

    if child_id not in covered_by:
        violations.append(
            f"child AC '{child_id}' is staged but parent AC '{immediate_parent_id}' "
            f"does not include '{child_id}' in its covered_by field. "
            f"Parent file: {parent_file_label}. "
            f"Add '{child_id}' to covered_by in {parent_file_label} and stage the parent file."
        )

    return violations


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _emit_violations(violations: list[str]) -> None:
    """Print violation messages to stderr for human-readable CI output.

    Args:
        violations: List of violation description strings.
    """
    print(f"\n{_HOOK_PREFIX} BLOCKED — AC parent covered_by violation(s):", file=sys.stderr)
    for i, v in enumerate(violations, start=1):
        print(f"  [{i}] {v}", file=sys.stderr)
    print(
        "\nTo fix: update the parent AC YAML file's covered_by list to include "
        "each child's ID, then stage both the child and parent files together.",
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _emit_could_not_check(prerequisite: str, reason: str, unevaluated_count: int) -> None:
    """Emit the could-not-check outcome for a cannot-run condition.

    Prints a reader-actionable WARNING to stderr naming both the unreachable
    prerequisite and the unverified scope, then emits the shared
    machine-readable RESULT line so a caller can distinguish this from an
    ordinary clean pass without parsing prose or relying on exit code
    (GE-120a-2 may still exit 0 for an "announce" disposition).

    Args:
        prerequisite: Name of the unreachable prerequisite (e.g.
            "derive_parent_id").
        reason: The underlying exception message.
        unevaluated_count: Number of staged files left unevaluated as a
            result.
    """
    print(
        f"{_HOOK_PREFIX} WARNING: could not reach prerequisite "
        f"'{prerequisite}' ({reason}); parent covered_by links were not "
        f"evaluated for {unevaluated_count} staged files",
        file=sys.stderr,
    )
    emit_result(OUTCOME_COULD_NOT_CHECK)


def main() -> int:
    """Run the AC parent covered_by check.

    Returns:
        0 when all staged AC YAML files pass the check (or no files staged,
        or the check could not reach its prerequisite -- see
        _emit_could_not_check).
        1 when one or more violations are detected.
    """
    # Staged files are needed both for the normal path and, if the
    # prerequisite below cannot be reached, to name the unverified scope.
    staged_paths = _get_staged_ac_paths()

    # Discover derive_parent_id
    try:
        derive_parent_id = _get_derive_parent_id()
    except (ImportError, OSError) as exc:
        _emit_could_not_check("derive_parent_id", str(exc), len(staged_paths))
        return 0

    # Discover AC store
    project_root = _find_project_root()
    if project_root is not None:
        ac_store = project_root / _AC_STORE_DIR
    else:
        ac_store = Path.cwd() / _AC_STORE_DIR

    if not ac_store.is_dir():
        # No AC store — nothing to check
        return 0

    if not staged_paths:
        return 0

    # Build the parent lookup index ONCE for the entire batch.
    # When the shared mtime-cached index is available, use it to get full parsed
    # AC dicts directly — no additional rglob walk needed. The ac_store_index
    # (id->dict) is passed to _check_file, which uses it to look up the parent
    # AC's covered_by field by ID without requiring a file path.
    # When the index module is unavailable, fall back to the original
    # _build_parent_index() rglob walk to get id->abs_path.
    if _AC_STORE_INDEX_AVAILABLE:
        ac_store_index = get_ac_index(str(ac_store))
        parent_index: dict[str, str] | None = None  # not needed with index
    else:
        ac_store_index = None
        parent_index = _build_parent_index(ac_store)

    # Resolve absolute paths for disk reads
    all_violations: list[str] = []
    for staged_path in staged_paths:
        abs_path = staged_path
        if not Path(staged_path).is_absolute():
            if project_root:
                abs_path = str(project_root / staged_path)
        file_violations = _check_file(
            abs_path, derive_parent_id, parent_index, ac_store_index=ac_store_index
        )
        all_violations.extend(file_violations)

    if not all_violations:
        return 0

    _emit_violations(all_violations)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(
            f"{_HOOK_PREFIX} unexpected error (fail-open): {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        sys.exit(0)
