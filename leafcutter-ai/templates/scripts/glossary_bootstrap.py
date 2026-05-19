"""
MODULE: glossary_bootstrap
GOAL: Full-repo glossary bootstrap script for the GlossaryAutomation system.
BUSINESS CONTEXT: Populates docs/glossary.md and docs/glossary_blacklist.md from
    scratch (or after a major codebase merge) by scanning all .md/.py/.sql files,
    dispatching the glossary-triage agent in parallel batches, applying decisions,
    and committing the result.
ARCHITECTURE: Entry point for the /glossary-bootstrap slash command
    (leafcutter/templates/skills/glossary-bootstrap/SKILL.md).
    Uses detect_candidates() from glossary_detector.py (ticket 01) and dispatches
    the glossary-triage agent (ticket 02) in configurable batch sizes.

    Flow:
    1. Enumerate tracked/untracked non-ignored files via `git ls-files`.
    2. Filter to .md/.py/.sql extensions.
    3. Call detect_candidates(file_path) for each file.
    4. Deduplicate candidates by term (keep <=5 context windows per term).
    5. Load existing glossary.md and glossary_blacklist.md to filter known terms.
    6. Dispatch glossary-triage agent in batches (default 10).
    7. Apply decisions: append to glossary.md / blacklist.md.
    8. Commit with summary message.
    9. Print summary table.

    I/O helpers live in glossary_bootstrap_helpers.py (split to stay under 400
    lines per the project file-size convention).

Usage:
    python glossary_bootstrap.py [--repo-root <path>] [--batch-size <int>]
    Called by the /glossary-bootstrap skill; can also be run standalone.
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

# Import helpers (same directory; importlib fallback for when not on sys.path).
try:
    from glossary_bootstrap_helpers import (  # type: ignore[import]
        _deduplicate_candidates,
        _enumerate_files,
        _git_commit,
        _load_existing_blacklist_terms,
        _load_existing_glossary_terms,
        _print_summary,
        apply_decisions,
        apply_decisions_from_file,
        collect_candidates,
        write_candidates_json,
    )
except ImportError:
    _helpers_spec = importlib.util.spec_from_file_location(
        "glossary_bootstrap_helpers",
        Path(__file__).parent / "glossary_bootstrap_helpers.py",
    )
    _helpers_mod = importlib.util.module_from_spec(_helpers_spec)  # type: ignore[arg-type]
    _helpers_spec.loader.exec_module(_helpers_mod)  # type: ignore[union-attr]
    _deduplicate_candidates = _helpers_mod._deduplicate_candidates
    _enumerate_files = _helpers_mod._enumerate_files
    _git_commit = _helpers_mod._git_commit
    _load_existing_blacklist_terms = _helpers_mod._load_existing_blacklist_terms
    _load_existing_glossary_terms = _helpers_mod._load_existing_glossary_terms
    _print_summary = _helpers_mod._print_summary
    apply_decisions = _helpers_mod.apply_decisions
    apply_decisions_from_file = _helpers_mod.apply_decisions_from_file
    collect_candidates = _helpers_mod.collect_candidates
    write_candidates_json = _helpers_mod.write_candidates_json

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_BATCH_SIZE = 10

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class TriageResult(NamedTuple):
    """Result returned by the glossary-triage agent for one term.

    Args:
        term: The jargon candidate term.
        action: One of "add_to_glossary", "add_to_blacklist", "false_positive".
        reason: Human-readable rationale.
        draft_entry: Proposed glossary entry text (when action == "add_to_glossary").
        canonical_link: Optional reference link (when action == "add_to_glossary").
    """

    term: str
    action: str
    reason: str
    draft_entry: str
    canonical_link: str


# ---------------------------------------------------------------------------
# Triage dispatch (standalone placeholder)
# ---------------------------------------------------------------------------


def _dispatch_triage(
    term: str,
    occurrences: list[list[str]],
    existing_glossary_terms: set[str],
    existing_blacklist_terms: set[str],
) -> TriageResult:
    """Placeholder triage function — raises immediately to prevent silent blacklisting.

    This function is the default ``dispatch_fn`` when no override is supplied.
    It exists to make standalone invocations fail loudly rather than silently
    blacklisting every term, which was the previous (broken) behaviour.

    In Claude-agent context, pass a real ``dispatch_fn`` to ``run_bootstrap()``
    or use the ``--list-candidates`` / ``--apply-decisions`` two-mode CLI so
    that Claude can orchestrate the glossary-triage agent.

    Args:
        term: The jargon candidate term.
        occurrences: List of context_window lists (up to 5).
        existing_glossary_terms: Already-known terms from glossary.md.
        existing_blacklist_terms: Already-known terms from blacklist.md.

    Raises:
        RuntimeError: Always — there is no built-in triage dispatch.
    """
    raise RuntimeError(
        "glossary_bootstrap.py has no built-in triage dispatch. "
        "Invoke via /glossary-bootstrap so Claude can orchestrate the "
        "glossary-triage agent, or pass dispatch_fn= explicitly when "
        "calling run_bootstrap() from a test."
    )


# ---------------------------------------------------------------------------
# Detector loader
# ---------------------------------------------------------------------------


def _load_detector():
    """Load detect_candidates from glossary_detector module.

    Returns:
        The detect_candidates callable, or None if module cannot be loaded.
    """
    try:
        from glossary_detector import detect_candidates  # type: ignore[import]
        return detect_candidates
    except ImportError:
        pass

    spec = importlib.util.spec_from_file_location(
        "glossary_detector",
        Path(__file__).parent / "glossary_detector.py",
    )
    if spec is None or spec.loader is None:
        print(
            "glossary-bootstrap: WARNING — glossary_detector.py not found.",
            file=sys.stderr,
        )
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod.detect_candidates


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_bootstrap(
    repo_root: Path,
    batch_size: int = _DEFAULT_BATCH_SIZE,
    dispatch_fn=None,
) -> tuple[list[str], list[str]]:
    """Run the full-repo glossary bootstrap.

    Args:
        repo_root: Absolute path to the repository root.
        batch_size: Number of terms to triage per batch (default 10).
        dispatch_fn: Optional callable(term, occurrences, glossary_terms,
            blacklist_terms) -> TriageResult. Defaults to _dispatch_triage
            (standalone mode). Override for Claude-agent-context invocations.

    Returns:
        Tuple of (terms_added_to_glossary, terms_added_to_blacklist).
    """
    if dispatch_fn is None:
        dispatch_fn = _dispatch_triage

    glossary_path = repo_root / "docs" / "glossary.md"
    blacklist_path = repo_root / "docs" / "glossary_blacklist.md"

    # Step 1-2: enumerate files
    print("glossary-bootstrap: enumerating files…")
    files = _enumerate_files(repo_root)
    print(f"glossary-bootstrap: {len(files)} .md/.py/.sql files to scan.")
    if not files:
        print("glossary-bootstrap: no files found. Is this a git repository?")
        return [], []

    # Step 3: detect candidates
    detect_candidates = _load_detector()
    if detect_candidates is None:
        return [], []

    all_candidates = []
    for f in files:
        try:
            all_candidates.extend(detect_candidates(f))
        except Exception as exc:  # noqa: BLE001
            print(f"glossary-bootstrap: WARNING — could not scan {f}: {exc}", file=sys.stderr)

    print(f"glossary-bootstrap: {len(all_candidates)} raw candidates detected.")

    # Step 4: deduplicate by term
    by_term = _deduplicate_candidates(all_candidates)
    print(f"glossary-bootstrap: {len(by_term)} unique candidate terms.")

    # Step 5: filter known terms
    existing_glossary = _load_existing_glossary_terms(glossary_path)
    existing_blacklist = _load_existing_blacklist_terms(blacklist_path)
    known = existing_glossary | existing_blacklist

    novel = {t: occ for t, occ in by_term.items() if t.lower() not in known}
    print(
        f"glossary-bootstrap: {len(novel)} novel terms "
        f"(filtered {len(by_term) - len(novel)} already known)."
    )
    if not novel:
        print("glossary-bootstrap: glossary is up to date — no new terms to triage.")
        return [], []

    # Step 6: dispatch triage in batches
    terms = sorted(novel.keys())
    results: list[TriageResult] = []
    for batch_start in range(0, len(terms), batch_size):
        batch = terms[batch_start: batch_start + batch_size]
        print(
            f"glossary-bootstrap: triaging batch {batch_start // batch_size + 1} "
            f"({len(batch)} terms)…"
        )
        for term in batch:
            try:
                result = dispatch_fn(term, novel[term], existing_glossary, existing_blacklist)
                results.append(result)
            except Exception as exc:  # noqa: BLE001
                print(
                    f"glossary-bootstrap: WARNING — triage failed for {term!r}: {exc}. Skipping.",
                    file=sys.stderr,
                )

    # Step 7: apply decisions
    added_glossary, added_blacklist = apply_decisions(results, glossary_path, blacklist_path)
    print(
        f"glossary-bootstrap: applied decisions — "
        f"{len(added_glossary)} added to glossary, {len(added_blacklist)} added to blacklist."
    )

    # Step 8: commit
    if added_glossary or added_blacklist:
        _git_commit(repo_root, len(added_glossary), len(added_blacklist))
    else:
        print("glossary-bootstrap: no changes to commit.")

    # Step 9: summary
    _print_summary(results)

    return added_glossary, added_blacklist


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Entry point for standalone invocation.

    Two modes are supported:

    **--list-candidates mode** (read-only, no mutations):
        Scans all .md/.py/.sql files, detects novel jargon candidates, and
        writes them as a JSON array to ``--output <path.json>``.  No changes
        are made to docs/glossary.md or docs/glossary_blacklist.md and no
        git commit is made.  Claude reads the JSON file, dispatches the
        glossary-triage agent in batches, and then invokes
        ``--apply-decisions`` with the results.

    **--apply-decisions mode** (mutates glossary files):
        Reads a decisions JSON file (produced by Claude after running the
        glossary-triage agent) and applies each decision to docs/glossary.md
        or docs/glossary_blacklist.md.  Idempotent: existing entries are
        skipped.  Stages and commits automatically unless ``--no-commit`` is
        passed.

    **No subcommand** (legacy / safeguard):
        Calls ``_dispatch_triage()`` which raises ``RuntimeError`` immediately.
        This ensures that running the script directly without a subcommand
        fails loudly instead of silently blacklisting every term.

    Returns:
        0 on success, 1 on unrecoverable error.
    """
    parser = argparse.ArgumentParser(
        description="Bootstrap the project glossary by scanning all .md/.py/.sql files."
    )
    parser.add_argument(
        "--repo-root", type=Path, default=None,
        help="Repository root (default: git rev-parse --show-toplevel).",
    )
    parser.add_argument(
        "--batch-size", type=int, default=_DEFAULT_BATCH_SIZE,
        help=f"Number of terms per triage batch (default {_DEFAULT_BATCH_SIZE}).",
    )

    # Mode 1: list candidates (read-only)
    parser.add_argument(
        "--list-candidates", action="store_true", default=False,
        help=(
            "Enumerate novel jargon candidates and write them to --output as JSON. "
            "Does NOT modify glossary.md or glossary_blacklist.md. "
            "Does NOT commit anything."
        ),
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Path to write candidates JSON (required with --list-candidates).",
    )

    # Mode 2: apply decisions
    parser.add_argument(
        "--apply-decisions", type=Path, default=None, metavar="DECISIONS_JSON",
        help=(
            "Path to a decisions JSON file produced by Claude after running the "
            "glossary-triage agent.  Applies decisions to glossary.md and "
            "glossary_blacklist.md.  Idempotent."
        ),
    )
    parser.add_argument(
        "--no-commit", action="store_true", default=False,
        help="With --apply-decisions: write files but do not stage or commit.",
    )

    args = parser.parse_args(argv)

    # Resolve repo root
    repo_root = args.repo_root
    if repo_root is None:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, check=True,
            )
            repo_root = Path(result.stdout.strip())
        except subprocess.CalledProcessError:
            print("glossary-bootstrap: ERROR — not inside a git repository.", file=sys.stderr)
            return 1

    # ----------------------------------------------------------------
    # Mode 1: --list-candidates
    # ----------------------------------------------------------------
    if args.list_candidates:
        if args.output is None:
            print(
                "glossary-bootstrap: ERROR — --list-candidates requires --output <path.json>.",
                file=sys.stderr,
            )
            return 1

        detect_candidates = _load_detector()
        if detect_candidates is None:
            print(
                "glossary-bootstrap: ERROR — glossary_detector.py not found.",
                file=sys.stderr,
            )
            return 1

        try:
            candidates = collect_candidates(repo_root, detect_candidates)
            write_candidates_json(candidates, args.output)
            print(
                f"glossary-bootstrap: {len(candidates)} novel candidates written to {args.output}."
            )
        except Exception as exc:  # noqa: BLE001
            print(f"glossary-bootstrap: FATAL — {exc}", file=sys.stderr)
            return 1

        return 0

    # ----------------------------------------------------------------
    # Mode 2: --apply-decisions
    # ----------------------------------------------------------------
    if args.apply_decisions is not None:
        if not args.apply_decisions.exists():
            print(
                f"glossary-bootstrap: ERROR — decisions file not found: {args.apply_decisions}",
                file=sys.stderr,
            )
            return 1

        glossary_path = repo_root / "docs" / "glossary.md"
        blacklist_path = repo_root / "docs" / "glossary_blacklist.md"

        try:
            applied_g, applied_b, skipped = apply_decisions_from_file(
                decisions_path=args.apply_decisions,
                glossary_path=glossary_path,
                blacklist_path=blacklist_path,
                no_commit=args.no_commit,
                repo_root=repo_root,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"glossary-bootstrap: FATAL — {exc}", file=sys.stderr)
            return 1

        print(
            f"glossary-bootstrap: summary — "
            f"{len(applied_g)} glossary, {len(applied_b)} blacklist, "
            f"{len(skipped)} skipped."
        )
        return 0

    # ----------------------------------------------------------------
    # No subcommand: fail loud (the old silent-blacklist path is gone)
    # ----------------------------------------------------------------
    try:
        _dispatch_triage("", [], set(), set())  # always raises
    except RuntimeError as exc:
        print(f"glossary-bootstrap: ERROR — {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-19 [python-coder/TICKET-20260518-GlossaryBootstrap_OrchestrationFix]: Replaced
#   _dispatch_triage() body with fail-loud RuntimeError (no more silent blacklisting).
#   Added --list-candidates / --apply-decisions two-mode CLI to main().
#   No-subcommand path now calls _dispatch_triage() which raises.
#   New imports: apply_decisions_from_file, collect_candidates, write_candidates_json.
#   main() accepts optional argv list for testability.
# - 2026-05-18 19:45 [python-coder/EPIC-GlossaryAutomation/ticket-03]: Split (#EPIC-GlossaryAutomation/03)
#   I/O helpers into glossary_bootstrap_helpers.py to satisfy 400-line limit.
#   Main file now contains only TriageResult, _dispatch_triage, _load_detector,
#   run_bootstrap, and main().
# - 2026-05-18 19:10 [python-coder/EPIC-GlossaryAutomation/ticket-03]: Created (#EPIC-GlossaryAutomation/03)
#   module. Full-repo bootstrap entry point for the GlossaryAutomation system.
# ====================================================================
