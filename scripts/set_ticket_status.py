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

Exit Codes:
    0 - Success (status updated or no-op same-status call)
    1 - Validation failure (invalid transition, parity check failed)
    2 - Internal error (file not found, frontmatter parse failure)

Usage:
    python scripts/set_ticket_status.py --ticket <path> --status <todo|in_progress|done> [--force]
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path


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
        required=True,
        help="Absolute or repo-relative path to the ticket markdown file.",
    )
    parser.add_argument(
        "--status",
        required=True,
        choices=sorted(VALID_STATUSES),
        help="Target status value to set.",
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
    return parser


def main() -> int:
    """Entry point for set_ticket_status.py.

    Returns:
        0 on success, 1 on validation failure, 2 on internal error.
    """
    parser = _build_arg_parser()
    args = parser.parse_args()

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
====================================================================
"""
