#!/usr/bin/env python3
"""
cross_reference_audit.py — Cross-reference AC store against existing tickets.

Scans existing tickets and finds ones whose acceptance criteria match AC criteria
so that `implemented_by` can be backfilled for ACs that were already implemented
before the AC-driven flow existed.

Usage:
    python3 scripts/ac_store/cross_reference_audit.py [options]

Options:
    --ac-root PATH              Root directory of the AC store (default:
                                docs/acceptance-criteria/ relative to worktree root).
    --tickets-root PATH         Root directory of tickets (default: tickets/ relative
                                to worktree root).
    --apply                     Write backfill to AC YAML files (default: read-only).
    --json                      Output matches as JSON in addition to human-readable.
    --min-confidence {high,medium}
                                Minimum confidence level to report (default: medium).

Exit codes:
    0  Success (even when no matches found — empty is valid).
    1  One or more AC YAML or ticket files could not be read or parsed.

# AC-1: Audit finds exact-criteria matches (confidence: high)
# AC-2: Audit finds keyword matches at medium confidence
# AC-3: No false positives for unrelated tickets
# AC-4: --apply writes implemented_by for high-confidence matches only
# AC-5: Report is written to debugging/logs/
# AC-6: --apply is idempotent for already-linked ACs
"""

from __future__ import annotations

import argparse
import difflib
import json
import logging
import sys
from datetime import date
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_STOP_WORDS: frozenset[str] = frozenset(
    {"the", "a", "an", "is", "are", "when", "then", "given", "and", "or", "not"}
)

_PASS1_SIMILARITY_THRESHOLD: float = 0.90
_PASS2_MIN_KEYWORD_OVERLAP: int = 2

_DEFAULT_AC_ROOT: str = "docs/acceptance-criteria"
_DEFAULT_TICKETS_ROOT: str = "tickets"
_DEFAULT_LOGS_DIR: str = "debugging/logs"

# Lifecycle folders whose tickets are considered "done" even without status: done
_DONE_FOLDER_MARKERS: frozenset[str] = frozenset({"99_done"})

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
    stream=sys.stderr,
)
_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

MatchRecord = dict[str, Any]


# ---------------------------------------------------------------------------
# Worktree root detection
# ---------------------------------------------------------------------------

def _detect_worktree_root() -> Path:
    """Walk up from this file to find the worktree root (directory with tickets/)."""
    candidate = Path(__file__).resolve().parent
    for _ in range(6):
        if (candidate / "tickets").exists() or (candidate / "docs").exists():
            return candidate
        candidate = candidate.parent
    return Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# AC store helpers
# ---------------------------------------------------------------------------

def _load_ac_yamls(ac_root: Path) -> list[dict[str, Any]]:
    """Load all AC YAML files from the AC store directory tree.

    Returns a list of dicts with at least: id, title, criteria, component,
    work_status, implemented_by. Skips files that cannot be parsed.
    """
    acs: list[dict[str, Any]] = []
    if not ac_root.exists():
        _log.warning("AC root does not exist: %s", ac_root)
        return acs

    for yaml_path in sorted(ac_root.rglob("*.yaml")):
        try:
            with open(yaml_path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
            if not isinstance(data, dict):
                _log.warning("Skipping non-dict YAML: %s", yaml_path)
                continue
            data["_path"] = str(yaml_path)
            acs.append(data)
        except yaml.YAMLError as exc:
            _log.warning("YAML parse error in %s: %s", yaml_path, exc)
        except OSError as exc:
            _log.warning("Cannot read %s: %s", yaml_path, exc)
    return acs


def _filter_todo_acs(acs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return only ACs with work_status: todo and implemented_by: []."""
    result = []
    for ac in acs:
        work_status = ac.get("work_status", "todo")
        implemented_by = ac.get("implemented_by", [])
        if work_status == "todo" and not implemented_by:
            result.append(ac)
    return result


# ---------------------------------------------------------------------------
# Ticket helpers
# ---------------------------------------------------------------------------

def _is_done_ticket(ticket_path: Path, ticket_text: str) -> bool:
    """Return True if the ticket is 'done' by folder name or frontmatter status."""
    # Check if any parent folder name is a done-marker
    for part in ticket_path.parts:
        if part in _DONE_FOLDER_MARKERS:
            return True
    # Parse frontmatter for status: done
    if ticket_text.startswith("---"):
        end = ticket_text.find("\n---", 3)
        if end != -1:
            fm_text = ticket_text[3:end]
            try:
                fm = yaml.safe_load(fm_text)
                if isinstance(fm, dict) and fm.get("status") == "done":
                    return True
            except yaml.YAMLError:
                pass
    return False


def _extract_ticket_frontmatter(ticket_text: str) -> dict[str, Any]:
    """Extract YAML frontmatter from a ticket file."""
    if ticket_text.startswith("---"):
        end = ticket_text.find("\n---", 3)
        if end != -1:
            try:
                fm = yaml.safe_load(ticket_text[3:end])
                return fm if isinstance(fm, dict) else {}
            except yaml.YAMLError:
                pass
    return {}


def _extract_acceptance_criteria_section(ticket_text: str) -> str:
    """Extract text of the ## Acceptance Criteria section from a ticket body."""
    # Find the section header
    marker = "## Acceptance Criteria"
    idx = ticket_text.find(marker)
    if idx == -1:
        return ""
    # Extract until the next ## section or end of file
    start = idx + len(marker)
    next_section = ticket_text.find("\n## ", start)
    if next_section != -1:
        return ticket_text[start:next_section].strip()
    return ticket_text[start:].strip()


def _load_done_tickets(tickets_root: Path) -> list[dict[str, Any]]:
    """Load all done tickets from the tickets root directory.

    Returns a list of dicts with: path, title, components, ac_section.
    Skips files that cannot be read.
    """
    tickets: list[dict[str, Any]] = []
    if not tickets_root.exists():
        _log.warning("Tickets root does not exist: %s", tickets_root)
        return tickets

    for md_path in sorted(tickets_root.rglob("*.md")):
        try:
            ticket_text = md_path.read_text(encoding="utf-8")
        except OSError as exc:
            _log.warning("Cannot read ticket %s: %s", md_path, exc)
            continue

        if not _is_done_ticket(md_path, ticket_text):
            continue

        fm = _extract_ticket_frontmatter(ticket_text)
        title = fm.get("title", md_path.stem)
        components = fm.get("components", [])
        if isinstance(components, str):
            components = [components]
        ac_section = _extract_acceptance_criteria_section(ticket_text)

        tickets.append(
            {
                "path": str(md_path),
                "title": title,
                "components": components,
                "ac_section": ac_section,
            }
        )
    return tickets


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def _pass1_similarity(ac_criteria: str, ticket_ac_section: str) -> float:
    """Compute similarity ratio between AC criteria text and ticket AC section."""
    if not ac_criteria or not ticket_ac_section:
        return 0.0
    sm = difflib.SequenceMatcher(None, ac_criteria, ticket_ac_section, autojunk=False)
    return sm.ratio()


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase words, filtering stop words."""
    words = []
    for word in text.lower().split():
        # Strip punctuation
        clean = "".join(ch for ch in word if ch.isalnum())
        if clean and clean not in _STOP_WORDS:
            words.append(clean)
    return words


def _pass2_keyword_overlap(
    ac_title: str,
    ticket_title: str,
    ac_component: str | None,
    ticket_components: list[str],
) -> tuple[bool, str]:
    """Check keyword overlap and component match for medium-confidence matching.

    Returns (matched, reason_string).
    """
    ac_tokens = set(_tokenize(ac_title))
    ticket_tokens = set(_tokenize(ticket_title))
    overlap = ac_tokens & ticket_tokens

    has_component_match = False
    if ac_component and ticket_components:
        # Normalize for comparison
        ac_comp_lower = ac_component.lower().replace("-", "").replace("_", "")
        for tc in ticket_components:
            tc_lower = tc.lower().replace("-", "").replace("_", "")
            if ac_comp_lower == tc_lower or ac_comp_lower in tc_lower or tc_lower in ac_comp_lower:
                has_component_match = True
                break

    if len(overlap) >= _PASS2_MIN_KEYWORD_OVERLAP and has_component_match:
        reason = (
            f"title keyword overlap ({len(overlap)}/{len(ac_tokens)}) "
            f"+ component match ({ac_component})"
        )
        return True, reason
    return False, ""


def _find_matches(
    acs: list[dict[str, Any]],
    tickets: list[dict[str, Any]],
) -> list[MatchRecord]:
    """Run two-pass matching and return deduplicated match records."""
    matches: list[MatchRecord] = []

    for ac in acs:
        ac_id = ac.get("id", "UNKNOWN")
        ac_title = str(ac.get("title", ""))
        ac_criteria = str(ac.get("criteria", ""))
        # component may be a string, list, or dict (various AC YAML schemas)
        ac_component_raw = ac.get("component", ac.get("components", None))
        if isinstance(ac_component_raw, list):
            ac_component: str | None = ac_component_raw[0] if ac_component_raw else None
        elif isinstance(ac_component_raw, dict):
            # Some ACs encode component as a dict with an 'id' or 'name' key
            ac_component = str(
                ac_component_raw.get("id", ac_component_raw.get("name", ""))
            ) or None
        elif ac_component_raw is None:
            ac_component = None
        else:
            ac_component = str(ac_component_raw)

        best_match: MatchRecord | None = None

        for ticket in tickets:
            ticket_path = ticket["path"]
            ticket_title = str(ticket["title"])
            ticket_components = ticket["components"]
            ticket_ac_section = ticket["ac_section"]

            # Pass 1 — exact criteria similarity
            similarity = _pass1_similarity(ac_criteria, ticket_ac_section)
            if similarity >= _PASS1_SIMILARITY_THRESHOLD:
                record: MatchRecord = {
                    "ac_id": ac_id,
                    "ticket_path": ticket_path,
                    "confidence": "high",
                    "reason": f"AC criteria text similarity ({similarity:.0%})",
                    "_ac": ac,
                }
                # High confidence wins — track best
                if best_match is None or best_match["confidence"] == "medium":
                    best_match = record
                continue

            # Pass 2 — keyword + component match
            matched, reason = _pass2_keyword_overlap(
                ac_title, ticket_title, ac_component, ticket_components
            )
            if matched:
                record = {
                    "ac_id": ac_id,
                    "ticket_path": ticket_path,
                    "confidence": "medium",
                    "reason": reason,
                    "_ac": ac,
                }
                # Only record medium if no high match exists yet
                if best_match is None:
                    best_match = record

        if best_match is not None:
            matches.append(best_match)

    return matches


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _print_match(match: MatchRecord) -> None:
    """Print a single match in human-readable format."""
    ac_id = match["ac_id"]
    ticket_path = match["ticket_path"]
    confidence = match["confidence"]
    reason = match["reason"]

    ac_title = match.get("_ac", {}).get("title", "")
    ticket_name = Path(ticket_path).name

    print(f"\nMATCH (confidence: {confidence}):")
    print(f"  AC:     {ac_id} — \"{ac_title}\"")
    print(f"  Ticket: {ticket_name}")
    print(f"          {ticket_path}")
    print(f"  Reason: {reason}")


def _write_report(
    matches: list[MatchRecord],
    logs_dir: Path,
) -> Path:
    """Write the JSON report to debugging/logs/ and return the file path."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().strftime("%Y%m%d")
    report_path = logs_dir / f"ac_cross_reference_audit_{today}.json"

    report = {
        "run_date": date.today().isoformat(),
        "matches": [
            {
                "ac_id": m["ac_id"],
                "ticket_path": m["ticket_path"],
                "confidence": m["confidence"],
                "reason": m["reason"],
            }
            for m in matches
        ],
    }

    try:
        with open(report_path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False)
        _log.info("Report written to %s", report_path)
    except OSError as exc:
        _log.error("Cannot write report to %s: %s", report_path, exc)
        sys.exit(1)

    return report_path


# ---------------------------------------------------------------------------
# Apply logic
# ---------------------------------------------------------------------------

def _apply_backfill(matches: list[MatchRecord]) -> int:
    """Write implemented_by for high-confidence matches.

    Returns the number of ACs modified.
    """
    modified = 0
    for match in matches:
        if match["confidence"] != "high":
            continue

        ac = match.get("_ac", {})
        ac_path_str = ac.get("_path")
        if not ac_path_str:
            _log.warning("No _path for AC %s — skipping apply", match["ac_id"])
            continue

        ac_path = Path(ac_path_str)
        ticket_path = match["ticket_path"]

        # Re-read the AC YAML fresh to avoid stale state
        try:
            with open(ac_path, encoding="utf-8") as fh:
                ac_data = yaml.safe_load(fh)
        except (OSError, yaml.YAMLError) as exc:
            _log.warning("Cannot re-read AC %s for apply: %s", ac_path, exc)
            continue

        if not isinstance(ac_data, dict):
            _log.warning("AC file %s is not a dict — skipping apply", ac_path)
            continue

        implemented_by = ac_data.get("implemented_by", [])
        if not isinstance(implemented_by, list):
            implemented_by = []

        # Idempotency check — AC-6
        if ticket_path in implemented_by:
            _log.info(
                "no-op (already linked): %s already has %s in implemented_by",
                match["ac_id"],
                ticket_path,
            )
            continue

        implemented_by.append(ticket_path)
        ac_data["implemented_by"] = implemented_by
        ac_data["work_status"] = "done"

        try:
            with open(ac_path, "w", encoding="utf-8") as fh:
                yaml.dump(
                    ac_data,
                    fh,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                )
            _log.info(
                "Applied: %s ← %s (work_status: done)", match["ac_id"], ticket_path
            )
            modified += 1
        except OSError as exc:
            _log.error("Cannot write AC %s: %s", ac_path, exc)

    return modified


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Cross-reference AC store against existing tickets for backfill.",
    )
    parser.add_argument(
        "--ac-root",
        default=None,
        help=f"Root directory of the AC store (default: {_DEFAULT_AC_ROOT})",
    )
    parser.add_argument(
        "--tickets-root",
        default=None,
        help=f"Root directory of tickets (default: {_DEFAULT_TICKETS_ROOT})",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Write backfill to AC YAML files (default: read-only)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        dest="output_json",
        help="Also print matches as JSON to stdout",
    )
    parser.add_argument(
        "--min-confidence",
        choices=["high", "medium"],
        default="medium",
        help="Minimum confidence level to report (default: medium)",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    worktree_root = _detect_worktree_root()

    ac_root = Path(args.ac_root) if args.ac_root else worktree_root / _DEFAULT_AC_ROOT
    tickets_root = (
        Path(args.tickets_root)
        if args.tickets_root
        else worktree_root / _DEFAULT_TICKETS_ROOT
    )
    logs_dir = worktree_root / _DEFAULT_LOGS_DIR

    _log.info("AC root: %s", ac_root)
    _log.info("Tickets root: %s", tickets_root)

    # Load data
    all_acs = _load_ac_yamls(ac_root)
    _log.info("Loaded %d AC YAML files", len(all_acs))

    todo_acs = _filter_todo_acs(all_acs)
    _log.info("Filtered to %d todo ACs with empty implemented_by", len(todo_acs))

    done_tickets = _load_done_tickets(tickets_root)
    _log.info("Loaded %d done tickets", len(done_tickets))

    # Run matching
    matches = _find_matches(todo_acs, done_tickets)

    # Filter by minimum confidence
    if args.min_confidence == "high":
        matches = [m for m in matches if m["confidence"] == "high"]

    # Print human-readable output
    if not matches:
        print("No matches found.")
    else:
        print(f"\nFound {len(matches)} match(es):")
        for match in matches:
            _print_match(match)

    # Write report — AC-5
    report_path = _write_report(matches, logs_dir)

    # JSON output flag
    if args.output_json:
        report = {
            "run_date": date.today().isoformat(),
            "matches": [
                {
                    "ac_id": m["ac_id"],
                    "ticket_path": m["ticket_path"],
                    "confidence": m["confidence"],
                    "reason": m["reason"],
                }
                for m in matches
            ],
        }
        print("\n--- JSON Output ---")
        print(json.dumps(report, indent=2))

    # Apply backfill — AC-4, AC-6
    if args.apply:
        high_count = sum(1 for m in matches if m["confidence"] == "high")
        print(
            f"\n--apply: processing {high_count} high-confidence match(es) "
            f"(medium-confidence matches are skipped)."
        )
        modified = _apply_backfill(matches)
        print(f"Applied {modified} AC backfill(s).")

    print(f"\nReport: {report_path}")


if __name__ == "__main__":
    main()
