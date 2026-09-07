"""
MODULE: repair_epic_member_pr_phase
GOAL: One-time repair script for epic-member tickets that carry
    ``pull-request: needed`` in their frontmatter ``agents:`` map even though
    the build driver never dispatches a per-ticket pull-request phase for a
    ticket that lives inside an epic (one epic-level PR covers the whole
    branch). Flips the value to ``not_needed`` and removes the orphaned
    ``## Sign-offs`` row so the completion write no longer refuses to mark
    the ticket done.
BUSINESS CONTEXT: 332 tickets under ``tickets/00_inbox/epics/`` were
    generated with a ``pull-request`` phase entry that can never be signed
    off inside an epic drive, so every one of them halts a drive at the
    finish line. Writing ``not_needed`` records "explicitly excluded from
    this ticket" (matching the driver's real behavior); writing
    ``signed_off`` would record a phantom sign-off for a phase that never
    ran, corrupting the very evidence the completion gate reads.
ARCHITECTURE: Walks ``--tickets-dir`` (default ``<repo>/tickets``)
    recursively for ``*.md`` files. For each file, parses only the YAML
    frontmatter block to decide applicability (epic-member path segment +
    ``pull-request: needed`` + non-``done`` status), then performs a
    targeted, non-round-tripping text edit — a first-occurrence line
    substitution for the ``agents:`` entry, plus a first-occurrence line
    deletion for the ``## Sign-offs`` row when that section exists — so
    every other byte of the file is left untouched. A ticket with no
    ``## Sign-offs`` section at all is repaired by the frontmatter flip
    alone (there is no row to remove and none is invented); a ticket whose
    ``## Sign-offs`` section exists but lacks the expected row is refused
    rather than guessed at. Reports five mutually exclusive counts
    (``examined``, ``changed``, ``skipped_done``, ``skipped_not_applicable``,
    ``refused``) and exits non-zero iff any file was refused.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_EPIC_PATH_SEGMENT = "00_inbox/epics/"
_STATUS_DONE = "done"
_TARGET_AGENT = "pull-request"
_TARGET_STATUS_NEEDED = "needed"
_TARGET_STATUS_REPAIRED = "not_needed"

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_AGENT_LINE_RE = re.compile(
    rf"(?m)^(?P<indent>[ \t]*){_TARGET_AGENT}:[ \t]*{_TARGET_STATUS_NEEDED}[ \t]*$"
)
_SIGNOFF_LINE_RE = re.compile(rf"(?m)^- \[ \] {_TARGET_AGENT}[ \t]*$\n?")
_SIGNOFFS_HEADER_RE = re.compile(r"(?m)^## Sign-offs[ \t]*$")

_COUNT_LABELS = (
    "examined",
    "changed",
    "skipped_done",
    "skipped_not_applicable",
    "refused",
)


class _Counts:
    """Mutable tally of the five mutually exclusive per-file outcomes."""

    def __init__(self) -> None:
        """Initialize every counter to zero."""
        self.examined = 0
        self.changed = 0
        self.skipped_done = 0
        self.skipped_not_applicable = 0
        self.refused = 0

    def report_lines(self) -> list[str]:
        """Render the five counts as ``<label>: <int>`` lines, in fixed order.

        Returns:
            One string per label in ``_COUNT_LABELS`` order.
        """
        return [f"{label}: {getattr(self, label)}" for label in _COUNT_LABELS]


def _parse_frontmatter(text: str) -> dict:
    """Extract and parse a ticket's YAML frontmatter block.

    Args:
        text: The full ticket file content.

    Returns:
        The parsed frontmatter as a dict.

    Raises:
        ValueError: The frontmatter delimiters are missing, or the enclosed
            YAML does not parse to a mapping.
    """
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        raise ValueError("no YAML frontmatter block found (missing '---' delimiters)")
    raw = match.group(1)
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML frontmatter: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("frontmatter did not parse to a mapping")
    return data


def _is_epic_member_path(path: Path) -> bool:
    """Check whether a ticket path contains the epic-member path segment.

    Args:
        path: The ticket file path.

    Returns:
        True iff the POSIX-normalised path contains ``00_inbox/epics/``.
    """
    return _EPIC_PATH_SEGMENT in path.as_posix()


def _is_repair_candidate(frontmatter: dict, path: Path) -> bool:
    """Decide whether a ticket is a repair candidate.

    A candidate is an epic-member ticket (per path) whose frontmatter
    ``agents:`` map has ``pull-request: needed``.

    Args:
        frontmatter: The parsed frontmatter dict.
        path: The ticket file path.

    Returns:
        True iff the ticket qualifies for repair.
    """
    if not _is_epic_member_path(path):
        return False
    agents = frontmatter.get("agents")
    if not isinstance(agents, dict):
        return False
    return agents.get(_TARGET_AGENT) == _TARGET_STATUS_NEEDED


def _repair_text(original_text: str) -> str | None:
    """Apply the targeted edit(s) to ticket text, leaving all else untouched.

    Always performs a first-occurrence substitution of the
    ``pull-request: needed`` agents-map line to ``pull-request: not_needed``
    (preserving the line's original indentation) — that match is required to
    occur exactly once, as evidence the file is genuinely the shape this
    repair understands.

    The ``## Sign-offs`` row is then handled by shape:
      - A ``## Sign-offs`` section exists and has a matching
        ``- [ ] pull-request`` row: the row (including its newline) is
        removed. Exactly one match is required.
      - No ``## Sign-offs`` section exists in the file at all: there is
        nothing to remove and nothing to author — the frontmatter flip alone
        is the complete repair for this shape (an older ticket template with
        no Sign-offs checklist).
      - A ``## Sign-offs`` section exists but has no matching row: this is a
        shape the repair cannot safely account for, so it refuses rather
        than guessing.

    This is pure text surgery on the original bytes — never a parse-and-redump
    of the YAML or the markdown — so every other byte is preserved exactly,
    and no ``## Sign-offs`` section is ever invented.

    Args:
        original_text: The full, unmodified ticket file content.

    Returns:
        The repaired text, or None if the file does not match one of the two
        safe shapes above (the caller must treat this as a refusal, not a
        partial edit).
    """
    updated, n_agent = _AGENT_LINE_RE.subn(
        lambda m: f"{m.group('indent')}{_TARGET_AGENT}: {_TARGET_STATUS_REPAIRED}",
        original_text,
        count=1,
    )
    if n_agent != 1:
        return None

    updated, n_signoff = _SIGNOFF_LINE_RE.subn("", updated, count=1)
    if n_signoff == 1:
        return updated

    if _SIGNOFFS_HEADER_RE.search(updated) is None:
        # No ## Sign-offs section at all: nothing to remove, nothing to
        # author. The frontmatter flip alone is the complete repair.
        return updated

    # A ## Sign-offs section exists but the expected row is absent — a shape
    # this repair cannot account for. Refuse rather than guess.
    return None


def _read_ticket_text(path: Path) -> str:
    """Read a ticket file as UTF-8 text.

    Args:
        path: The ticket file path.

    Returns:
        The file's full text content.

    Raises:
        OSError: The file could not be read.
    """
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not read %s: %s", path, exc)
        raise


def _write_ticket_text(path: Path, text: str) -> None:
    """Write repaired text back to a ticket file.

    Args:
        path: The ticket file path.
        text: The repaired content to write.

    Raises:
        OSError: The file could not be written.
    """
    try:
        path.write_text(text, encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not write %s: %s", path, exc)
        raise


def _process_file(path: Path, *, dry_run: bool, counts: _Counts) -> None:
    """Classify and (unless dry-run) repair a single ticket file.

    Updates ``counts`` in exactly one of ``changed``, ``skipped_done``,
    ``skipped_not_applicable``, or ``refused``, and prints an operator-facing
    line describing what happened (or would happen, under ``--dry-run``).

    Args:
        path: The ticket file path to examine.
        dry_run: When True, never writes to disk.
        counts: The running tally to update.
    """
    try:
        original_text = _read_ticket_text(path)
    except OSError as exc:
        print(f"REFUSED {path}: could not read file: {exc}", file=sys.stderr)
        counts.refused += 1
        return

    try:
        frontmatter = _parse_frontmatter(original_text)
    except ValueError as exc:
        logger.warning("Unparseable frontmatter in %s: %s", path, exc)
        print(f"REFUSED {path}: {exc}", file=sys.stderr)
        counts.refused += 1
        return

    if not _is_repair_candidate(frontmatter, path):
        counts.skipped_not_applicable += 1
        return

    if frontmatter.get("status") == _STATUS_DONE:
        counts.skipped_done += 1
        return

    repaired_text = _repair_text(original_text)
    if repaired_text is None:
        logger.warning(
            "Candidate ticket %s did not contain the expected 'pull-request: needed' "
            "agents-map line and/or '- [ ] pull-request' Sign-offs row in the exact "
            "shape this repair edits; refusing rather than guessing.",
            path,
        )
        print(
            f"REFUSED {path}: candidate did not match the expected line shapes "
            "for a safe surgical edit",
            file=sys.stderr,
        )
        counts.refused += 1
        return

    if dry_run:
        print(f"[dry-run] WOULD CHANGE {path}: pull-request needed -> not_needed")
    else:
        try:
            _write_ticket_text(path, repaired_text)
        except OSError as exc:
            print(f"REFUSED {path}: could not write file: {exc}", file=sys.stderr)
            counts.refused += 1
            return
        print(f"CHANGED {path}: pull-request needed -> not_needed")
    counts.changed += 1


def _iter_ticket_files(tickets_dir: Path) -> list[Path]:
    """List every ``*.md`` file under a tickets directory, recursively.

    Args:
        tickets_dir: The root directory to walk.

    Returns:
        A sorted list of matching file paths (empty if none, or the
        directory does not exist).

    Raises:
        OSError: The directory could not be walked.
    """
    try:
        return sorted(tickets_dir.rglob("*.md"))
    except OSError as exc:
        logger.warning("Failed to walk %s: %s", tickets_dir, exc)
        raise


def _build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for this repair script.

    Returns:
        A configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Repair epic-member tickets whose 'pull-request' agents-map entry "
            "is stuck at 'needed' by flipping it to 'not_needed' and removing "
            "the orphaned '## Sign-offs' row."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Report what would change without writing any file.",
    )
    parser.add_argument(
        "--tickets-dir",
        type=Path,
        default=None,
        help="Root directory to walk recursively for *.md tickets (default: <repo>/tickets).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point: walk, classify, repair, and report.

    Args:
        argv: Optional argument vector override (defaults to ``sys.argv[1:]``).

    Returns:
        0 when no ticket was refused; non-zero when at least one was.
    """
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    tickets_dir = args.tickets_dir
    if tickets_dir is None:
        tickets_dir = Path(__file__).resolve().parent.parent / "tickets"

    counts = _Counts()
    try:
        ticket_files = _iter_ticket_files(tickets_dir)
    except OSError as exc:
        print(f"REFUSED (directory walk): could not walk {tickets_dir}: {exc}", file=sys.stderr)
        return 1

    for path in ticket_files:
        counts.examined += 1
        _process_file(path, dry_run=args.dry_run, counts=counts)

    for line in counts.report_lines():
        print(line)

    return 1 if counts.refused > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
