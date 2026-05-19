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

import json
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


# ---------------------------------------------------------------------------
# Two-mode CLI helpers (list-candidates + apply-decisions)
# ---------------------------------------------------------------------------


def collect_candidates(repo_root: Path, detect_candidates_fn) -> dict[str, list[list[str]]]:
    """Enumerate files, detect candidates, deduplicate, and filter known terms.

    This is the pure-read phase — no mutations to glossary.md or blacklist.md.

    Args:
        repo_root: Absolute path to repository root.
        detect_candidates_fn: Callable(file_path) -> list[Candidate].

    Returns:
        Dict mapping term -> list of context_window lists for novel (unknown) terms.
    """
    glossary_path = repo_root / "docs" / "glossary.md"
    blacklist_path = repo_root / "docs" / "glossary_blacklist.md"

    files = _enumerate_files(repo_root)
    if not files:
        return {}

    all_candidates = []
    for f in files:
        try:
            all_candidates.extend(detect_candidates_fn(f))
        except Exception as exc:  # noqa: BLE001
            print(f"glossary-bootstrap: WARNING — could not scan {f}: {exc}", file=sys.stderr)

    by_term = _deduplicate_candidates(all_candidates)
    existing_glossary = _load_existing_glossary_terms(glossary_path)
    existing_blacklist = _load_existing_blacklist_terms(blacklist_path)
    known = existing_glossary | existing_blacklist
    return {t: occ for t, occ in by_term.items() if t.lower() not in known}


def write_candidates_json(candidates: dict[str, list[list[str]]], output_path: Path) -> None:
    """Write the candidates dict to a JSON file for Claude to consume.

    Each element in the output array has:
        ``{"term": "<str>", "occurrences": [["line", ...], ...]}``

    Args:
        candidates: Dict mapping term -> list of context_window lists.
        output_path: Absolute path to write the JSON file.

    Raises:
        OSError: If the file cannot be written.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {"term": term, "occurrences": occurrences}
        for term, occurrences in sorted(candidates.items())
    ]
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"glossary-bootstrap: wrote {len(payload)} candidates to {output_path}")


def _term_in_glossary(term: str, glossary_path: Path) -> bool:
    """Return True if ``### <term>`` (case-insensitive) already exists in glossary.md.

    Args:
        term: The term to check.
        glossary_path: Absolute path to docs/glossary.md.

    Returns:
        True if the term heading already exists; False otherwise.
    """
    if not glossary_path.exists():
        return False
    needle = f"### {term}".lower()
    for line in glossary_path.read_text(encoding="utf-8").splitlines():
        if line.strip().lower() == needle:
            return True
    return False


def _term_in_blacklist(term: str, blacklist_path: Path) -> bool:
    """Return True if ``term`` already appears as the first table column in blacklist.md.

    Args:
        term: The term to check.
        blacklist_path: Absolute path to docs/glossary_blacklist.md.

    Returns:
        True if the term row already exists; False otherwise.
    """
    if not blacklist_path.exists():
        return False
    needle = term.lower().strip()
    for line in blacklist_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("|") and not line.startswith("| term") and not line.startswith("| ---"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 2 and parts[1].lower() == needle:
                return True
    return False


def _build_blacklist_row(term: str, decision: dict, today: str) -> str:
    """Build the table row string for a blacklist entry.

    Supports two input shapes:
    - ``blacklist_row`` key present and non-empty: use it directly (normalised to table format).
    - Otherwise: build a row from ``reason`` field.

    Args:
        term: The term being blacklisted.
        decision: The raw decision dict from the JSON file.
        today: ISO-format date string for the date column.

    Returns:
        A newline-terminated Markdown table row string.
    """
    raw_row = decision.get("blacklist_row", "").strip()
    if raw_row:
        if not raw_row.startswith("|"):
            return f"| {term} | {raw_row} | {today} |\n"
        return raw_row if raw_row.endswith("\n") else raw_row + "\n"
    safe_reason = decision.get("reason", "").replace("|", "/")
    return f"| {term} | {safe_reason} | {today} |\n"


def _apply_glossary_decision(
    term: str,
    decision: dict,
    glossary_path: Path,
    applied: list[str],
    skipped: list[str],
) -> None:
    """Apply a single add_to_glossary decision (idempotent).

    Args:
        term: The term to add.
        decision: The raw decision dict.
        glossary_path: Absolute path to docs/glossary.md.
        applied: Accumulator list for applied terms.
        skipped: Accumulator list for skipped terms.
    """
    if _term_in_glossary(term, glossary_path):
        skipped.append(term)
        return
    _ensure_glossary_file(glossary_path)
    draft = decision.get("draft_entry", "") or f"### {term}\n\nTODO: add definition.\n"
    if not draft.startswith("### "):
        draft = f"### {term}\n\n{draft}\n"
    with glossary_path.open("a", encoding="utf-8") as fh:
        fh.write(f"\n{draft.rstrip()}\n")
    applied.append(term)


def _apply_blacklist_decision(
    term: str,
    decision: dict,
    blacklist_path: Path,
    today: str,
    applied: list[str],
    skipped: list[str],
) -> None:
    """Apply a single add_to_blacklist / false_positive decision (idempotent).

    Args:
        term: The term to blacklist.
        decision: The raw decision dict.
        blacklist_path: Absolute path to docs/glossary_blacklist.md.
        today: ISO-format date string.
        applied: Accumulator list for applied terms.
        skipped: Accumulator list for skipped terms.
    """
    if _term_in_blacklist(term, blacklist_path):
        skipped.append(term)
        return
    _ensure_blacklist_file(blacklist_path)
    row = _build_blacklist_row(term, decision, today)
    with blacklist_path.open("a", encoding="utf-8") as fh:
        fh.write(row)
    applied.append(term)


def apply_decisions_from_file(
    decisions_path: Path,
    glossary_path: Path,
    blacklist_path: Path,
    no_commit: bool = False,
    repo_root: Path | None = None,
) -> tuple[list[str], list[str], list[str]]:
    """Apply decisions from a JSON file to glossary.md and glossary_blacklist.md.

    The decisions JSON must be an array of objects with at minimum:
        ``{"term": "...", "action": "add_to_glossary"|"add_to_blacklist"|"false_positive",
           "draft_entry": "...", "blacklist_row": "...", "reason": "..."}``

    Idempotent: terms already present in the target file are skipped without duplicating.

    Args:
        decisions_path: Absolute path to the decisions JSON file.
        glossary_path: Absolute path to docs/glossary.md.
        blacklist_path: Absolute path to docs/glossary_blacklist.md.
        no_commit: If True, write files but do not commit.
        repo_root: Repository root for git commit (required unless no_commit=True).

    Returns:
        Tuple of (terms_applied_to_glossary, terms_applied_to_blacklist, terms_skipped).
    """
    raw = json.loads(decisions_path.read_text(encoding="utf-8"))
    today = date.today().isoformat()

    applied_glossary: list[str] = []
    applied_blacklist: list[str] = []
    skipped: list[str] = []

    for decision in raw:
        term = decision.get("term", "").strip()
        action = decision.get("action", "").strip()
        if not term or not action:
            continue

        if action == "add_to_glossary":
            _apply_glossary_decision(term, decision, glossary_path, applied_glossary, skipped)
        elif action in ("add_to_blacklist", "false_positive"):
            _apply_blacklist_decision(
                term, decision, blacklist_path, today, applied_blacklist, skipped
            )

    total_applied = len(applied_glossary) + len(applied_blacklist)
    print(
        f"glossary-bootstrap: applied {total_applied} decisions "
        f"({len(applied_glossary)} glossary, {len(applied_blacklist)} blacklist); "
        f"{len(skipped)} skipped (already present)."
    )

    if not no_commit and repo_root is not None and (applied_glossary or applied_blacklist):
        _git_commit(repo_root, len(applied_glossary), len(applied_blacklist))

    return applied_glossary, applied_blacklist, skipped


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-19 [python-coder/TICKET-20260518-GlossaryBootstrap_OrchestrationFix]: Added
#   collect_candidates(), write_candidates_json(), _term_in_glossary(),
#   _term_in_blacklist(), apply_decisions_from_file() for the two-mode CLI split
#   (--list-candidates, --apply-decisions). Also added json import.
# - 2026-05-18 19:45 [python-coder/EPIC-GlossaryAutomation/ticket-03]: Extracted (#EPIC-GlossaryAutomation/03)
#   from glossary_bootstrap.py to satisfy 400-line limit. Contains all I/O
#   helpers: file enumeration, term loading, deduplication, decision application,
#   git commit, summary table.
# ====================================================================
