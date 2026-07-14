"""
MODULE: set_ticket_status.py
GOAL: Exclusive mechanism for setting ticket frontmatter status field, replacing
    the fragile git-mv-to-done/ convention with a single deterministic script.
BUSINESS CONTEXT: BO-400 establishes ticket frontmatter status: as the single source
    of truth for ticket lifecycle. Every lifecycle decision (is it ready? is it done?
    is it in progress?) must derive from this field, not from folder position.
    This script is the only permitted way to update ticket status; LLM agents
    invoking git mv to move tickets to done/ subfolders must use this script instead.
ARCHITECTURE: Standalone CLI script. Reads the YAML frontmatter block (between
    the first and second --- delimiters), performs targeted line-replacement to
    update the status: field, and writes the file back. Uses targeted replacement
    (not yaml.dump round-trip) to preserve field order and exact formatting.
    After a successful write, stages the file via git add for the next commit.
    Validates transitions against an explicit allow-list. Checks agents: map parity
    before permitting done transitions (unless --force is set).
    Also exposes scan_epic_archive_readiness() as a library function, and a
    --scan-epic CLI mode, for callers that need to assess whether all tickets
    in an epic directory are done. The finalize-feature-archive-check skill
    (finalize-feature.js Step 5) invokes the --scan-epic mode as its
    authoritative pre-archive gate (BO-400c-2).

Exit Codes:
    0 - Success (status updated / no-op same-status call / epic all_clear)
    1 - Validation failure (invalid transition, parity check failed, or
        --scan-epic found tickets not yet done)
    2 - Internal error (file not found, frontmatter parse failure, or
        --scan-epic pointed at a directory that does not exist)

Usage:
    python scripts/set_ticket_status.py --ticket <path> --status <todo|in_progress|done> [--force]
    python scripts/set_ticket_status.py --scan-epic <epic_dir>
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import TypedDict


# ---------------------------------------------------------------------------
# Transition allow-lists (as data, not scattered conditionals)
# ---------------------------------------------------------------------------

# Transitions allowed without --force
ALLOWED_TRANSITIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("todo", "in_progress"),
        ("in_progress", "done"),
        ("in_progress", "todo"),
    }
)

# Additional transitions allowed only with --force
FORCE_ALLOWED_TRANSITIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("todo", "done"),
        ("done", "todo"),
        ("done", "in_progress"),
        ("inbox", "todo"),
        ("inbox", "in_progress"),
        ("inbox", "done"),
        ("blocked", "todo"),
        ("blocked", "in_progress"),
    }
)

# All valid status values
VALID_STATUSES: frozenset[str] = frozenset({"todo", "in_progress", "done", "blocked", "deferred", "inbox"})


# ---------------------------------------------------------------------------
# Frontmatter parsing (targeted, not YAML round-trip)
# ---------------------------------------------------------------------------


def _extract_frontmatter_block(content: str) -> tuple[str, str, str] | None:
    """Split ticket content into pre-YAML, YAML block, and post-YAML sections.

    Uses targeted delimiter detection rather than yaml.dump round-trip to
    preserve field order and exact formatting.

    Args:
        content: Full text content of the ticket file.

    Returns:
        A tuple of (pre_yaml, yaml_block, post_yaml) where pre_yaml is the
        leading '---' line, yaml_block is the content between delimiters, and
        post_yaml is everything from the closing '---' onward.
        Returns None if no frontmatter block is detected.
    """
    if not content.startswith("---"):
        return None
    end_idx = content.find("\n---", 3)
    if end_idx == -1:
        return None
    pre_yaml = content[: 4]  # "---\n"
    yaml_block = content[4 : end_idx + 1]  # YAML content (includes trailing newline)
    post_yaml = content[end_idx + 1:]  # "---\n..." onward
    return (pre_yaml, yaml_block, post_yaml)


def _get_current_status(yaml_block: str) -> str | None:
    """Extract the current status value from the YAML block.

    Args:
        yaml_block: The raw YAML content between frontmatter delimiters.

    Returns:
        The status string if found, or None if the status: field is absent.
    """
    match = re.search(r"^status:\s*(.+)$", yaml_block, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None


def _get_needed_agents(yaml_block: str) -> list[str]:
    """Extract agent names that have status 'needed' from the agents: map.

    Args:
        yaml_block: The raw YAML content between frontmatter delimiters.

    Returns:
        List of agent names with 'needed' status.
    """
    needed: list[str] = []
    in_agents = False
    for line in yaml_block.splitlines():
        if re.match(r"^agents:\s*$", line):
            in_agents = True
            continue
        if in_agents:
            # Stop at the next top-level (unindented) key
            if line and not line[0].isspace() and not line.startswith("  "):
                if ":" in line:
                    break
            # Match "  agent-name: needed" pattern
            m = re.match(r"^\s+([a-zA-Z0-9_-]+):\s+needed\s*$", line)
            if m:
                needed.append(m.group(1))
    return needed


def _replace_status_line(yaml_block: str, new_status: str) -> str:
    """Replace the status: field value in the YAML block.

    Uses targeted regex replacement to preserve field order and formatting.
    If no status: field exists, inserts one after the title: line (or at
    the start of the block if title: is absent).

    Args:
        yaml_block: The raw YAML content between frontmatter delimiters.
        new_status: The new status value to set.

    Returns:
        The updated YAML block with the status: field replaced or inserted.
    """
    if re.search(r"^status:\s*.+$", yaml_block, re.MULTILINE):
        return re.sub(r"^(status:\s*)(.+)$", rf"\g<1>{new_status}", yaml_block, flags=re.MULTILINE)

    # Insert status: after title: if present
    if re.search(r"^title:", yaml_block, re.MULTILINE):
        return re.sub(
            r"^(title:.+\n)",
            rf"\g<1>status: {new_status}\n",
            yaml_block,
            count=1,
            flags=re.MULTILINE,
        )

    # Fallback: prepend
    return f"status: {new_status}\n{yaml_block}"


# ---------------------------------------------------------------------------
# Git staging
# ---------------------------------------------------------------------------


def _stage_file(ticket_path: Path) -> None:
    """Stage the ticket file via git add.

    Handles the case where the file is not tracked by git gracefully.

    Args:
        ticket_path: Absolute path to the ticket file to stage.
    """
    try:
        result = subprocess.run(
            ["git", "add", str(ticket_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            # Not a hard failure — file may not be in a git repo (e.g. CI, tests)
            print(
                f"Warning: git add failed (not git-tracked?): {result.stderr.strip()}",
                file=sys.stderr,
            )
    except FileNotFoundError:
        print("Warning: git not available — file not staged", file=sys.stderr)
    except OSError as exc:
        print(f"Warning: git add error: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Epic archive-readiness scanner
# ---------------------------------------------------------------------------

# Files that are never tickets and must be excluded from the readiness count.
_NON_TICKET_FILES: frozenset[str] = frozenset({"Master_Plan.md", "README.md"})

# Frontmatter statuses that count as "done enough" to archive an epic.
_ARCHIVE_OK_STATUSES: frozenset[str] = frozenset({"done", "deferred"})


class MissingTicket(TypedDict):
    """One non-done ticket surfaced by scan_epic_archive_readiness."""

    path: str
    current_status: str | None


class ArchiveReadiness(TypedDict):
    """Structured result of an epic archive-readiness scan."""

    all_clear: bool
    ok_count: int
    missing_count: int
    missing_tickets: list[MissingTicket]


def scan_epic_archive_readiness(epic_dir: str) -> ArchiveReadiness:
    """Scan an epic directory for tickets that have not reached status: done.

    Scans ``.md`` files at the epic root and inside a ``done/`` subfolder
    (legacy layout where tickets were previously moved via git mv). Excludes
    ``Master_Plan.md`` and ``README.md`` from the count. Status is read from
    YAML frontmatter, not inferred from folder position (BO-400a-3 principle).
    A ticket counts as ready when its status is ``done`` or ``deferred``.

    Backward-compat: a legacy ticket that lives under the ``done/`` subfolder
    and has no ``status:`` field is treated as ``done`` (the only reason it
    would have been moved there under the old convention) — per the
    finalize-feature-archive-check skill §4.

    An empty-but-existing epic directory returns ``all_clear: True`` (nothing
    blocks archival) — this is the deliberate skill §4 contract. A directory
    that does not exist is an operator error (e.g. a mistyped path), NOT a
    ready state, so it raises ``FileNotFoundError`` rather than reporting a
    false all-clear.

    Args:
        epic_dir: Absolute or relative path to the epic directory.

    Returns:
        An :class:`ArchiveReadiness` mapping with keys ``all_clear``,
        ``ok_count``, ``missing_count``, and ``missing_tickets`` (one
        :class:`MissingTicket` per non-done ticket).

    Raises:
        FileNotFoundError: When ``epic_dir`` does not exist or is not a
            directory. Prevents a mistyped path from being reported as
            ready-to-archive.
    """
    epic_path = Path(epic_dir)
    if not epic_path.is_dir():
        raise FileNotFoundError(epic_dir)

    ok_tickets: list[str] = []
    missing_tickets: list[MissingTicket] = []

    root_candidates = list(epic_path.glob("*.md"))
    done_subdir = epic_path / "done"
    done_candidates = list(done_subdir.glob("*.md")) if done_subdir.is_dir() else []

    for md_file in [*root_candidates, *done_candidates]:
        if md_file.name in _NON_TICKET_FILES:
            continue
        try:
            content = md_file.read_text(encoding="utf-8")
        except OSError as exc:
            # A file we cannot read must not be silently dropped when gating
            # archival — count it as not-done so all_clear stays honest.
            print(f"Warning: cannot read {md_file}: {exc}", file=sys.stderr)
            missing_tickets.append({"path": str(md_file), "current_status": "(read error)"})
            continue
        parts = _extract_frontmatter_block(content)
        status: str | None = None
        if parts is not None:
            _, yaml_block, _ = parts
            status = _get_current_status(yaml_block)
        # Legacy backward-compat: a done/ ticket with no status: is treated as done.
        if status is None and md_file in done_candidates:
            status = "done"
        if status in _ARCHIVE_OK_STATUSES:
            ok_tickets.append(str(md_file))
        else:
            missing_tickets.append({"path": str(md_file), "current_status": status})

    return {
        "all_clear": len(missing_tickets) == 0,
        "ok_count": len(ok_tickets),
        "missing_count": len(missing_tickets),
        "missing_tickets": missing_tickets,
    }


def _run_scan_epic(epic_dir: str) -> int:
    """CLI entry point for --scan-epic: print the readiness JSON to stdout.

    This is the wired call path that the finalize-feature-archive-check skill
    (finalize-feature.js Step 5) invokes to assess an epic before archival.

    Args:
        epic_dir: Path to the epic directory to scan.

    Returns:
        0 when the epic is all-clear, 1 when tickets remain not-done, 2 when
        the directory does not exist.
    """
    try:
        result = scan_epic_archive_readiness(epic_dir)
    except FileNotFoundError as exc:
        print(f"Error: epic directory does not exist: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result["all_clear"] else 1


# ---------------------------------------------------------------------------
# Core transition logic
# ---------------------------------------------------------------------------


def set_ticket_status(
    ticket_path: Path,
    new_status: str,
    force: bool = False,
) -> int:
    """Perform the status transition for a single ticket file.

    Args:
        ticket_path: Absolute or relative path to the ticket markdown file.
        new_status: Target status value (one of VALID_STATUSES).
        force: When True, bypasses parity check and allows force-allowed transitions.

    Returns:
        Exit code: 0 on success (including no-op), 1 on validation failure,
        2 on internal error.
    """
    # --- Read ---
    try:
        content = ticket_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Error: cannot read ticket file: {exc}", file=sys.stderr)
        return 2

    # --- Parse frontmatter ---
    parts = _extract_frontmatter_block(content)
    if parts is None:
        print("Error: ticket file has no YAML frontmatter block (missing --- delimiters)", file=sys.stderr)
        return 2

    pre_yaml, yaml_block, post_yaml = parts
    current_status = _get_current_status(yaml_block)
    absent_note = ""

    if current_status is None:
        absent_note = " (absent, treated as todo)"
        current_status = "todo"

    # --- No-op check (same-status is always allowed) ---
    if current_status == new_status:
        print(f"status: {current_status} -> {new_status} (no change)")
        return 0

    # --- Transition validation ---
    transition = (current_status, new_status)

    if new_status == "done" and not force:
        # Parity check: ensure no agents have 'needed' status
        needed_agents = _get_needed_agents(yaml_block)
        if needed_agents:
            agents_str = ", ".join(needed_agents)
            print(f"Cannot set done - agents with status 'needed': {agents_str}")
            return 1

    if transition not in ALLOWED_TRANSITIONS:
        if force and transition in FORCE_ALLOWED_TRANSITIONS:
            # Force-allowed transition
            pass
        elif force:
            # Force flag set but transition is not even in the force-allowed list
            print(
                f"Invalid transition: {current_status} -> {new_status} "
                f"(not permitted even with --force)"
            )
            return 1
        else:
            print(
                f"Invalid transition: {current_status} -> {new_status} "
                f"(use --force to override)"
            )
            return 1

    # --- Write ---
    updated_yaml = _replace_status_line(yaml_block, new_status)
    new_content = pre_yaml + updated_yaml + post_yaml

    try:
        ticket_path.write_text(new_content, encoding="utf-8")
    except OSError as exc:
        print(f"Error: cannot write ticket file: {exc}", file=sys.stderr)
        return 2

    # --- Stage ---
    _stage_file(ticket_path)

    # --- Report ---
    force_note = " (forced, parity check skipped)" if force and new_status == "done" else ""
    print(f"status: {current_status}{absent_note} -> {new_status}{force_note}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for set_ticket_status.py.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Set the status: field in a ticket's YAML frontmatter. "
            "Validates transitions against an allow-list and checks agents: parity "
            "before permitting done transitions. Stages the file via git add on success."
        )
    )
    parser.add_argument(
        "--ticket",
        required=False,
        help="Absolute or repo-relative path to the ticket markdown file. "
        "Required unless --scan-epic is given.",
    )
    parser.add_argument(
        "--status",
        required=False,
        choices=sorted(VALID_STATUSES),
        help="Target status value to set. Required unless --scan-epic is given.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help=(
            "Bypass transition allow-list and parity checks. "
            "Required for transitions like done -> in_progress or todo -> done."
        ),
    )
    parser.add_argument(
        "--scan-epic",
        metavar="EPIC_DIR",
        default=None,
        help=(
            "Scan an epic directory for archive readiness and print the result "
            "as JSON. Exits 0 when all_clear, 1 when tickets remain not-done, "
            "2 when the directory does not exist. Ignores --ticket/--status."
        ),
    )
    return parser


def main() -> int:
    """Entry point for set_ticket_status.py.

    Returns:
        0 on success, 1 on validation failure, 2 on internal error.
    """
    parser = _build_arg_parser()
    args = parser.parse_args()

    if args.scan_epic is not None:
        return _run_scan_epic(args.scan_epic)

    if not args.ticket or not args.status:
        parser.error("--ticket and --status are required unless --scan-epic is given")

    ticket_path = Path(args.ticket).resolve()
    if not ticket_path.exists():
        print(f"Error: ticket file not found: {ticket_path}", file=sys.stderr)
        return 2

    return set_ticket_status(ticket_path, args.status, force=args.force)


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-05 12:30 [python-coder/BO-400]: Created as the exclusive mechanism for
  setting ticket frontmatter status fields. Replaces the git-mv-to-done/ convention
  per BO-400b spec. Uses targeted regex replacement (not yaml.dump round-trip) to
  preserve field order and formatting. Allow-list data structure (ALLOWED_TRANSITIONS
  / FORCE_ALLOWED_TRANSITIONS) chosen over scattered conditionals for maintainability.
  Parity check reads agents: from frontmatter YAML only (not ## Sign-offs body section),
  consistent with how check_ticket_signoff_parity.py operates.
- 2026-07-14 [code-review remediation/BO-400c-2]: Hardened scan_epic_archive_readiness
  and wired it into the finalize/archive surface (review findings H-1, H-2).
  H-1: a non-existent epic_dir now raises FileNotFoundError instead of returning
  a false {all_clear: True} — a mistyped path is an operator error, not a ready
  state. An existing-but-empty directory still returns all_clear: True per the
  finalize-feature-archive-check skill §4 contract. H-2: added the --scan-epic
  CLI mode (_run_scan_epic) so the skill (finalize-feature.js Step 5) invokes
  this one authoritative implementation instead of an ad-hoc find+parse; the
  skill body was updated to call it. Aligned the scanner's semantics with the
  skill's documented §2/§4 contract: README.md excluded alongside Master_Plan.md,
  status: deferred counts as ready, and a legacy done/ ticket with no status:
  field is treated as done. Return type tightened to the ArchiveReadiness
  TypedDict (review finding L-3).
====================================================================
"""
