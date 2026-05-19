"""
MODULE: glossary_bootstrap_helpers
GOAL: I/O helpers for glossary_bootstrap.py — file enumeration, term loading,
    candidate deduplication, decision application, git commit, and summary table.
BUSINESS CONTEXT: Extracted from glossary_bootstrap.py to satisfy the 400-line
    limit. These helpers are internal to the GlossaryAutomation bootstrap system
    and are not intended to be imported directly by external callers.
ARCHITECTURE: All functions in this module are private helpers (prefixed _) or
    the public apply_decisions() surface. Imported by glossary_bootstrap.py.
"""

from __future__ import annotations

import subprocess
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_CONTEXT_WINDOWS = 5  # max occurrences stored per term

# ---------------------------------------------------------------------------
# File enumeration
# ---------------------------------------------------------------------------


def _enumerate_files(repo_root: Path) -> list[Path]:
    """Return all .md/.py/.sql files tracked by git in repo_root.

    Uses ``git ls-files`` to respect .gitignore automatically.

    Args:
        repo_root: Absolute path to the repository root.

    Returns:
        Sorted list of absolute Path objects for .md/.py/.sql files.
    """
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard",
             "*.md", "*.py", "*.sql"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(
            f"glossary-bootstrap: WARNING — git ls-files failed: {(exc.stderr or '').strip()}. "
            "Falling back to rglob.",
            file=sys.stderr,
        )
        files: list[Path] = []
        for ext in ("*.md", "*.py", "*.sql"):
            files.extend(repo_root.rglob(ext))
        return sorted(files)

    paths: list[Path] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        p = repo_root / line
        if p.suffix.lower() in (".md", ".py", ".sql") and p.is_file():
            paths.append(p)
    return sorted(paths)


# ---------------------------------------------------------------------------
# Existing term loading
# ---------------------------------------------------------------------------


def _load_existing_glossary_terms(glossary_path: Path) -> set[str]:
    """Parse ``### <term>`` headings from docs/glossary.md.

    Args:
        glossary_path: Absolute path to docs/glossary.md.

    Returns:
        Set of normalised (lowercase, stripped) term strings found.
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
    """Parse the term column from the docs/glossary_blacklist.md table.

    Expected format: ``| term | reason | YYYY-MM-DD |``

    Args:
        blacklist_path: Absolute path to docs/glossary_blacklist.md.

    Returns:
        Set of normalised (lowercase, stripped) term strings found.
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
# Candidate deduplication
# ---------------------------------------------------------------------------


def _deduplicate_candidates(candidates: list) -> dict[str, list[list[str]]]:
    """Deduplicate candidates by term; keep up to _MAX_CONTEXT_WINDOWS per term.

    Args:
        candidates: List of Candidate objects from detect_candidates().

    Returns:
        Dict mapping term -> list of context_window lists (length <= 5).
    """
    by_term: dict[str, list[list[str]]] = defaultdict(list)
    for c in candidates:
        if len(by_term[c.term]) < _MAX_CONTEXT_WINDOWS:
            by_term[c.term].append(c.context_window)
    return dict(by_term)


# ---------------------------------------------------------------------------
# Decision application
# ---------------------------------------------------------------------------


def _ensure_glossary_file(glossary_path: Path) -> None:
    """Create docs/glossary.md with minimal header if it does not exist.

    Args:
        glossary_path: Absolute path to docs/glossary.md.
    """
    if not glossary_path.exists():
        glossary_path.parent.mkdir(parents=True, exist_ok=True)
        today = date.today().isoformat()
        glossary_path.write_text(
            "---\ntitle: Glossary\ntype: reference\nstatus: active\n"
            f"created: {today}\nlast_updated: {today}\n"
            "components:\n  - documentation_system\n---\n\n"
            "# Glossary\n\nProject-specific jargon terms and their definitions.\n\n",
            encoding="utf-8",
        )


def _ensure_blacklist_file(blacklist_path: Path) -> None:
    """Create docs/glossary_blacklist.md with table header if it does not exist.

    Args:
        blacklist_path: Absolute path to docs/glossary_blacklist.md.
    """
    if not blacklist_path.exists():
        blacklist_path.parent.mkdir(parents=True, exist_ok=True)
        today = date.today().isoformat()
        blacklist_path.write_text(
            "---\ntitle: Glossary Blacklist\ntype: reference\nstatus: active\n"
            f"created: {today}\nlast_updated: {today}\n"
            "components:\n  - documentation_system\n---\n\n"
            "# Glossary Blacklist\n\nTerms explicitly excluded from the glossary.\n\n"
            "| term | reason | date |\n| --- | --- | --- |\n",
            encoding="utf-8",
        )


def apply_decisions(
    results: list,
    glossary_path: Path,
    blacklist_path: Path,
) -> tuple[list[str], list[str]]:
    """Apply triage decisions to glossary.md and glossary_blacklist.md.

    Args:
        results: List of TriageResult objects (duck-typed: needs .action, .term,
            .draft_entry, .reason attributes).
        glossary_path: Absolute path to docs/glossary.md.
        blacklist_path: Absolute path to docs/glossary_blacklist.md.

    Returns:
        Tuple of (terms_added_to_glossary, terms_added_to_blacklist).
    """
    added_to_glossary: list[str] = []
    added_to_blacklist: list[str] = []
    today = date.today().isoformat()

    for result in results:
        if result.action == "add_to_glossary":
            _ensure_glossary_file(glossary_path)
            entry_text = result.draft_entry or f"### {result.term}\n\nTODO: add definition.\n"
            if not entry_text.startswith("### "):
                entry_text = f"### {result.term}\n\n{entry_text}\n"
            with glossary_path.open("a", encoding="utf-8") as fh:
                fh.write(f"\n{entry_text.rstrip()}\n")
            added_to_glossary.append(result.term)

        elif result.action in ("add_to_blacklist", "false_positive"):
            _ensure_blacklist_file(blacklist_path)
            safe_reason = result.reason.replace("|", "/")
            row = f"| {result.term} | {safe_reason} | {today} |\n"
            with blacklist_path.open("a", encoding="utf-8") as fh:
                fh.write(row)
            added_to_blacklist.append(result.term)

    return added_to_glossary, added_to_blacklist


# ---------------------------------------------------------------------------
# Git commit helper
# ---------------------------------------------------------------------------


def _git_commit(repo_root: Path, n_added: int, n_blacklisted: int) -> None:
    """Stage glossary files and commit with a summary message.

    Args:
        repo_root: Repository root path.
        n_added: Number of terms added to glossary.
        n_blacklisted: Number of terms added to blacklist.
    """
    try:
        subprocess.run(
            ["git", "add", "docs/glossary.md", "docs/glossary_blacklist.md"],
            cwd=str(repo_root),
            check=True,
        )
        msg = (
            f"chore(glossary): bootstrap glossary — "
            f"{n_added} term{'s' if n_added != 1 else ''} added, "
            f"{n_blacklisted} blacklisted"
        )
        subprocess.run(["git", "commit", "-m", msg], cwd=str(repo_root), check=True)
        print(f"glossary-bootstrap: committed — {msg}")
    except subprocess.CalledProcessError as exc:
        print(
            f"glossary-bootstrap: WARNING — git commit failed: {exc}. "
            "Files were written; stage and commit manually.",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------


def _print_summary(results: list) -> None:
    """Print a formatted summary table to stdout.

    Args:
        results: Completed triage results (duck-typed: needs .term, .action, .reason).
    """
    if not results:
        print("glossary-bootstrap: no novel candidates found — glossary is up to date.")
        return

    col_term = max(len(r.term) for r in results)
    col_action = max(len(r.action) for r in results)
    fmt = f"{{:<{col_term}}}  {{:<{col_action}}}  {{}}"

    print("\n" + fmt.format("TERM", "ACTION", "REASON"))
    print("-" * (col_term + col_action + 40))
    for r in results:
        print(fmt.format(r.term, r.action, r.reason[:80]))
    print()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-18 19:45 [python-coder/EPIC-GlossaryAutomation/ticket-03]: Extracted (#EPIC-GlossaryAutomation/03)
#   from glossary_bootstrap.py to satisfy 400-line limit. Contains all I/O
#   helpers: file enumeration, term loading, deduplication, decision application,
#   git commit, summary table.
# ====================================================================
