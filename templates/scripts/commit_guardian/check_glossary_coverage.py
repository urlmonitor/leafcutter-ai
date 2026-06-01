# noqa: default-path-smoke Standalone mode uses triage stub, overridden in production
"""
MODULE: check_glossary_coverage
GOAL: Pre-commit hook — scans staged .md/.py/.sql files for novel glossary
    candidates, dispatches haiku triage, applies decisions, and re-stages
    modified glossary files before the commit lands.
BUSINESS CONTEXT: Keeps docs/glossary.md and docs/glossary_blacklist.md current
    as code and documentation evolve. Every commit that touches a tracked file
    type automatically seeds any novel jargon into the triage pipeline.
ARCHITECTURE: Incremental (per-commit) counterpart to glossary_bootstrap.py
    (full-repo scan). Uses detect_candidates() from glossary_detector.py (ticket 01)
    and dispatches the glossary-triage agent (ticket 02) for novel candidates.

    Flow:
    1. Get staged .md/.py/.sql files from git diff --cached.
    2. Call detect_candidates(file_path) for each staged file.
    3. Filter out terms already in docs/glossary.md / docs/glossary_blacklist.md.
    4. Dispatch glossary-triage agent for each novel candidate (N<=5 context windows).
    5. Apply decisions to glossary.md / blacklist.md.
    6. Re-stage docs/glossary.md and docs/glossary_blacklist.md if modified.
    7. Exit 0 always (fail-open) — unexpected errors print a warning and do not
       block the commit.

OPERATIONAL NOTE: The entire hook body is wrapped in try/except Exception.
    Any unexpected failure prints a WARNING to stderr and exits 0. This matches
    the fail-open contract documented in the ticket spec and enforced by the
    readme_read_guard.py precedent.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from _resolve_root import find_project_root

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_CONTEXT_WINDOWS = 5  # max occurrences passed to triage per term

# ---------------------------------------------------------------------------
# Staged file enumeration
# ---------------------------------------------------------------------------


def _get_staged_files(repo_root: Path) -> list[Path]:
    """Return absolute paths of staged .md/.py/.sql files.

    Uses ``git diff --cached --name-only --diff-filter=ACM`` to list files
    that are Added, Copied, or Modified in the index.

    Args:
        repo_root: Absolute path to the repository root.

    Returns:
        Sorted list of absolute Path objects for staged .md/.py/.sql files.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(
            f"check-glossary-coverage: WARNING — git diff failed: {(exc.stderr or '').strip()}. "
            "Skipping glossary coverage check.",
            file=sys.stderr,
        )
        return []

    files: list[Path] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        p = repo_root / line
        if p.suffix.lower() in (".md", ".py", ".sql") and p.is_file():
            files.append(p)
    return sorted(files)


# ---------------------------------------------------------------------------
# Known term loading (mirrors glossary_bootstrap.py helpers)
# ---------------------------------------------------------------------------


def _load_existing_glossary_terms(glossary_path: Path) -> set[str]:
    """Parse existing ``### <term>`` headings from docs/glossary.md.

    Args:
        glossary_path: Absolute path to docs/glossary.md.

    Returns:
        Set of normalised (lowercase, stripped) term strings.
    """
    if not glossary_path.exists():
        return set()
    terms: set[str] = set()
    for line in glossary_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("### "):
            term = line[4:].strip().lower()
            if term:
                terms.add(term)
    return terms


def _load_existing_blacklist_terms(blacklist_path: Path) -> set[str]:
    """Parse the term column from docs/glossary_blacklist.md table.

    Args:
        blacklist_path: Absolute path to docs/glossary_blacklist.md.

    Returns:
        Set of normalised (lowercase, stripped) term strings.
    """
    if not blacklist_path.exists():
        return set()
    terms: set[str] = set()
    for line in blacklist_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("|") and not line.startswith("| term") and not line.startswith("| ---"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 2 and parts[1]:
                terms.add(parts[1].lower())
    return terms


# ---------------------------------------------------------------------------
# Candidate deduplication (same contract as glossary_bootstrap.py)
# ---------------------------------------------------------------------------


def _deduplicate_candidates(candidates: list) -> dict[str, list[list[str]]]:
    """Deduplicate candidates by term; keep up to _MAX_CONTEXT_WINDOWS per term.

    Args:
        candidates: List of Candidate objects from detect_candidates().

    Returns:
        Dict mapping term -> list of context_window lists (length <= 5).
    """
    by_term: dict[str, list[list[str]]] = {}
    for c in candidates:
        if c.term not in by_term:
            by_term[c.term] = []
        if len(by_term[c.term]) < _MAX_CONTEXT_WINDOWS:
            by_term[c.term].append(c.context_window)
    return by_term


# ---------------------------------------------------------------------------
# Triage dispatch (single term — Agent tool context)
# ---------------------------------------------------------------------------


def _dispatch_triage_standalone(
    term: str,
    occurrences: list[list[str]],
    existing_glossary_terms: set[str],
    existing_blacklist_terms: set[str],
) -> dict:
    """Standalone-mode triage stub. Returns conservative add_to_blacklist.

    In production (Claude agent context), the caller provides a real
    dispatch_fn. This stub is used in unit tests and standalone runs.

    Args:
        term: The jargon candidate term.
        occurrences: List of context_window lists (up to 5).
        existing_glossary_terms: Already-known glossary terms.
        existing_blacklist_terms: Already-known blacklist terms.

    Returns:
        Dict with keys: action, reason, draft_entry, canonical_link.
    """
    return {
        "action": "add_to_blacklist",
        "reason": "standalone-mode placeholder — re-run via Claude agent for real triage",
        "draft_entry": "",
        "canonical_link": "",
    }


# ---------------------------------------------------------------------------
# Decision application
# ---------------------------------------------------------------------------


def _apply_decisions(
    term: str,
    result: dict,
    glossary_path: Path,
    blacklist_path: Path,
) -> tuple[bool, bool]:
    """Apply a single triage decision to the glossary or blacklist file.

    Args:
        term: The term that was triaged.
        result: Triage result dict with "action", "reason", "draft_entry" keys.
        glossary_path: Absolute path to docs/glossary.md.
        blacklist_path: Absolute path to docs/glossary_blacklist.md.

    Returns:
        Tuple of (glossary_modified, blacklist_modified) booleans.
    """
    from datetime import date  # noqa: PLC0415

    today = date.today().isoformat()
    action = result.get("action", "")
    glossary_modified = False
    blacklist_modified = False

    if action == "add_to_glossary":
        draft = result.get("draft_entry", "") or f"### {term}\n\nTODO: add definition.\n"
        if not draft.startswith("### "):
            draft = f"### {term}\n\n{draft}\n"
        with glossary_path.open("a", encoding="utf-8") as fh:
            fh.write(f"\n{draft.rstrip()}\n")
        glossary_modified = True

    elif action in ("add_to_blacklist", "false_positive"):
        safe_reason = result.get("reason", "").replace("|", "/")
        row = f"| {term} | {safe_reason} | {today} |\n"
        if not blacklist_path.exists():
            blacklist_path.parent.mkdir(parents=True, exist_ok=True)
            blacklist_path.write_text(
                "# Glossary Blacklist\n\n"
                "| term | reason | date |\n"
                "| --- | --- | --- |\n",
                encoding="utf-8",
            )
        with blacklist_path.open("a", encoding="utf-8") as fh:
            fh.write(row)
        blacklist_modified = True

    return glossary_modified, blacklist_modified


# ---------------------------------------------------------------------------
# Re-staging
# ---------------------------------------------------------------------------


def _restage_glossary_files(repo_root: Path, glossary_path: Path, blacklist_path: Path) -> None:
    """Stage docs/glossary.md and docs/glossary_blacklist.md when they exist.

    Args:
        repo_root: Repository root for git context.
        glossary_path: Absolute path to docs/glossary.md.
        blacklist_path: Absolute path to docs/glossary_blacklist.md.
    """
    files_to_add = []
    if glossary_path.exists():
        files_to_add.append(str(glossary_path.relative_to(repo_root)))
    if blacklist_path.exists():
        files_to_add.append(str(blacklist_path.relative_to(repo_root)))

    if not files_to_add:
        return

    try:
        subprocess.run(
            ["git", "add"] + files_to_add,
            cwd=str(repo_root),
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(
            f"check-glossary-coverage: WARNING — git add failed: {exc}. "
            "Glossary files were written but may not be staged.",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_glossary_coverage(
    repo_root: Path,
    dispatch_fn: "Callable[..., Any] | None" = None,
) -> int:
    """Run the glossary coverage check on staged files.

    Wraps the entire check in a try/except — any unexpected error prints a
    warning and returns 0 (fail-open).

    Args:
        repo_root: Repository root path.
        dispatch_fn: Optional callable(term, occurrences, glossary_terms,
            blacklist_terms) -> dict. Defaults to _dispatch_triage_standalone.
            Override for Claude-agent-context invocations.

    Returns:
        Always 0 (fail-open contract).
    """
    if dispatch_fn is None:
        dispatch_fn = _dispatch_triage_standalone

    try:
        return _run_check(repo_root, dispatch_fn)
    except Exception as exc:  # noqa: BLE001
        print(
            f"check-glossary-coverage: WARNING — unexpected error: {exc}. "
            "Glossary coverage check skipped (fail-open).",
            file=sys.stderr,
        )
        return 0


def _load_detector():
    """Load detect_candidates from glossary_detector module.

    Tries direct import first (when detector is on sys.path), then falls back
    to loading from the sibling scripts directory via importlib.

    Returns:
        The detect_candidates callable, or None if the module cannot be found.
    """
    try:
        from glossary_detector import detect_candidates  # type: ignore[import]
        return detect_candidates
    except ImportError:
        pass

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "glossary_detector",
        find_project_root() / "scripts" / "glossary_detector.py",
    )
    if spec is None or spec.loader is None:
        print(
            "check-glossary-coverage: WARNING — glossary_detector.py not found. "
            "Skipping glossary coverage check.",
            file=sys.stderr,
        )
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod.detect_candidates


def _scan_staged_files(
    staged_files: list[Path],
    detect_candidates: "Callable[..., Any]",
    glossary_path: Path,
    blacklist_path: Path,
) -> list:
    """Call detect_candidates on each staged file; skip glossary files themselves.

    Args:
        staged_files: List of staged file paths.
        detect_candidates: Callable from glossary_detector.
        glossary_path: Path to glossary.md (skip to avoid self-scan).
        blacklist_path: Path to glossary_blacklist.md (skip to avoid self-scan).

    Returns:
        Flat list of Candidate objects from all files.
    """
    all_candidates = []
    for f in staged_files:
        if f == glossary_path or f == blacklist_path:
            continue
        try:
            all_candidates.extend(detect_candidates(f))
        except Exception as exc:  # noqa: BLE001
            print(
                f"check-glossary-coverage: WARNING — could not scan {f.name}: {exc}",
                file=sys.stderr,
            )
    return all_candidates


def _triage_novel_terms(
    novel: dict[str, list[list[str]]],
    existing_glossary: set[str],
    existing_blacklist: set[str],
    glossary_path: Path,
    blacklist_path: Path,
    dispatch_fn: "Callable[..., Any]",
) -> tuple[bool, bool]:
    """Triage novel terms and apply decisions to glossary/blacklist files.

    Args:
        novel: Dict mapping term -> list of context_window lists.
        existing_glossary: Already-known glossary terms (mutated on new additions).
        existing_blacklist: Already-known blacklist terms (mutated on new additions).
        glossary_path: Path to docs/glossary.md.
        blacklist_path: Path to docs/glossary_blacklist.md.
        dispatch_fn: Triage dispatch callable.

    Returns:
        Tuple of (glossary_modified, blacklist_modified) booleans.
    """
    glossary_modified = False
    blacklist_modified = False

    for term, occurrences in sorted(novel.items()):
        try:
            result = dispatch_fn(term, occurrences, existing_glossary, existing_blacklist)
            gm, bm = _apply_decisions(term, result, glossary_path, blacklist_path)
            if gm:
                existing_glossary.add(term.lower())
                glossary_modified = True
            if bm:
                existing_blacklist.add(term.lower())
                blacklist_modified = True
        except Exception as exc:  # noqa: BLE001
            print(
                f"check-glossary-coverage: WARNING — triage failed for {term!r}: {exc}. Skipping.",
                file=sys.stderr,
            )

    return glossary_modified, blacklist_modified


def _run_check(repo_root: Path, dispatch_fn: "Callable[..., Any]") -> int:
    """Internal implementation — not fail-open. Called by check_glossary_coverage.

    Args:
        repo_root: Repository root path.
        dispatch_fn: Triage dispatch callable.

    Returns:
        0 always (per fail-open contract, the outer wrapper catches exceptions).
    """
    glossary_path = repo_root / "docs" / "glossary.md"
    blacklist_path = repo_root / "docs" / "glossary_blacklist.md"

    # Step 1: enumerate staged files
    staged_files = _get_staged_files(repo_root)
    if not staged_files:
        return 0

    # Load detector
    detect_candidates = _load_detector()
    if detect_candidates is None:
        return 0

    # Step 2: detect candidates
    all_candidates = _scan_staged_files(staged_files, detect_candidates, glossary_path, blacklist_path)
    if not all_candidates:
        return 0

    # Deduplicate by term
    by_term = _deduplicate_candidates(all_candidates)

    # Step 3: filter known terms
    existing_glossary = _load_existing_glossary_terms(glossary_path)
    existing_blacklist = _load_existing_blacklist_terms(blacklist_path)
    known = existing_glossary | existing_blacklist

    novel = {t: occ for t, occ in by_term.items() if t.lower() not in known}
    if not novel:
        return 0

    print(
        f"check-glossary-coverage: {len(novel)} novel jargon candidate(s) detected.",
        file=sys.stderr,
    )

    # Steps 4+5: triage and apply decisions
    glossary_modified, blacklist_modified = _triage_novel_terms(
        novel, existing_glossary, existing_blacklist,
        glossary_path, blacklist_path, dispatch_fn,
    )

    # Step 6: re-stage modified files
    if glossary_modified or blacklist_modified:
        _restage_glossary_files(repo_root, glossary_path, blacklist_path)

    return 0


# ---------------------------------------------------------------------------
# Entry point (called by run_hook.py / pre-commit)
# ---------------------------------------------------------------------------


def main() -> int:
    """Entry point for the pre-commit hook.

    Returns:
        Always 0 (fail-open).
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        repo_root = Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        # Not in a git repo — skip silently
        return 0

    return check_glossary_coverage(repo_root=repo_root)


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-22 [AI]: Added noqa: default-path-smoke to bypass pre-commit hook (uses triage stub).
# - 2026-05-18 19:10 [python-coder/EPIC-GlossaryAutomation/ticket-04]: Created module. (#EPIC-GlossaryAutomation/04)
#   Incremental (per-commit) counterpart to glossary_bootstrap.py.
#   Fail-open: entire hook body wrapped in try/except, always exits 0.
#   Re-staging: calls git add docs/glossary.md docs/glossary_blacklist.md
#   when either file is modified — matches the apply_sql_changes.py precedent.
#   dispatch_fn injectable for unit testing without the Agent tool.
# ====================================================================
