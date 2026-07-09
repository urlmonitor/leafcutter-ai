"""
check_ticket_test_requirements.py — authoring guard for ticket Test Requirements.

Blocks code tickets that lack a populated ## Test Requirements section.
Non-code tickets (no coder agent needed) are always allowed through.

Implements BO-2000e-1 (authoring block for code tickets missing test requirements)
and BO-2000e-1-i (non-code tickets pass through unchanged).

Pre-commit hook: may be registered via create-hook or called from commit_guardian.json.
Pure library: the public API is check_ticket_has_test_requirements(content) → (bool, str).
"""
from __future__ import annotations

import re
import sys
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Agents that produce production code — tickets with any of these set to
# "needed" are treated as code tickets and must have populated Test Requirements.
CODER_AGENTS: frozenset[str] = frozenset(
    {"python-coder", "sql-coder", "frontend-coder"}
)

# ---------------------------------------------------------------------------
# Compiled regexes (module-level for reuse)
# ---------------------------------------------------------------------------

# Detects a coder agent in the YAML frontmatter agents: map with value "needed".
# Matches lines like "  python-coder: needed" (with arbitrary leading whitespace).
_CODER_NEEDED_RE = re.compile(
    r"^\s+(?:" + "|".join(re.escape(a) for a in sorted(CODER_AGENTS)) + r"):\s*needed\b",
    re.MULTILINE,
)

# Locates the fenced code block immediately following a ## Test Requirements heading.
# Captures the YAML content inside the backtick fence (group 1).
# Uses re.DOTALL so "." matches newlines across the block.
_TESTS_BLOCK_RE = re.compile(
    r"##\s+Test\s+Requirements\b.*?```(?:yaml)?\s*(.*?)```",
    re.DOTALL | re.IGNORECASE,
)

# Detects at least one test entry in the tests: array.
# Matches "  - name: <anything>" (with at least one non-whitespace char after "name:").
_TESTS_ENTRY_RE = re.compile(
    r"^\s*-\s+name:\s+\S+",
    re.MULTILINE,
)


# ---------------------------------------------------------------------------
# Pure helper functions (no I/O — no try/except per repo convention §Rule 4)
# ---------------------------------------------------------------------------


def _is_code_ticket(ticket_content: str) -> bool:
    """Return True if the ticket has at least one coder agent set to 'needed'."""
    return bool(_CODER_NEEDED_RE.search(ticket_content))


def _has_populated_test_requirements(ticket_content: str) -> bool:
    """
    Return True if the ticket has a ## Test Requirements section that contains
    at least one test entry (``- name: ...``) in the fenced YAML block.

    Treats the following as "not populated":
    - Absent ## Test Requirements section entirely.
    - Section present but no fenced code block follows it.
    - Fenced code block present but empty or contains only ``tests: []``.
    """
    match = _TESTS_BLOCK_RE.search(ticket_content)
    if match is None:
        return False
    yaml_block = match.group(1)
    if not yaml_block.strip():
        return False
    return bool(_TESTS_ENTRY_RE.search(yaml_block))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_ticket_has_test_requirements(
    ticket_content: str,
) -> tuple[bool, str]:
    """
    Check whether a ticket satisfies the Test Requirements guard.

    A code ticket (one with python-coder, sql-coder, or frontend-coder set to
    "needed") must have a ## Test Requirements section with at least one test
    entry in the ``tests:`` array.

    Non-code tickets pass through unconditionally (BO-2000e-1-i).

    Args:
        ticket_content: Full text of the ticket markdown file (including
                        YAML frontmatter and body sections).

    Returns:
        ``(True, "")`` when the ticket is valid — either a non-code ticket, or
        a code ticket with a populated ## Test Requirements section.

        ``(False, reason)`` when the ticket is invalid — a code ticket with
        an empty or absent ## Test Requirements section. ``reason`` is a
        human-readable string that names ``Test Requirements`` so the author
        knows exactly what to add.
    """
    if not _is_code_ticket(ticket_content):
        # Non-code ticket: the guard does not apply (BO-2000e-1-i).
        return True, ""

    if _has_populated_test_requirements(ticket_content):
        # Code ticket with at least one test entry: guard passes.
        return True, ""

    # Code ticket with absent or empty Test Requirements → block authoring.
    reason = (
        "Code ticket is missing a populated ## Test Requirements section. "
        "Add at least one test entry to the `tests:` array (under "
        "## Test Requirements) before authoring or dispatching the coder "
        "phase. (BO-2000e-1)"
    )
    return False, reason


# ---------------------------------------------------------------------------
# Pre-commit hook entrypoint
# ---------------------------------------------------------------------------


def main(ticket_files: Optional[list[str]] = None) -> int:
    """
    Pre-commit hook: check that every staged ticket file that is a code ticket
    has a populated ## Test Requirements section.

    Args:
        ticket_files: list of absolute or relative ticket file paths to check.
                      If ``None``, reads one path per line from stdin (the
                      standard pre-commit hook calling convention).

    Returns:
        0 if all tickets pass, 1 if any ticket fails the guard.
    """
    if ticket_files is None:
        ticket_files = [p.strip() for p in sys.stdin.readlines() if p.strip()]

    failures: list[tuple[str, str]] = []

    for path in ticket_files:
        try:
            with open(path, encoding="utf-8") as fh:
                content = fh.read()
        except OSError as exc:
            # Unreadable file: warn but do not block (not this hook's job).
            print(
                f"[check-ticket-test-requirements] WARNING: cannot read {path}: {exc}",
                file=sys.stderr,
            )
            continue

        ok, reason = check_ticket_has_test_requirements(content)
        if not ok:
            failures.append((path, reason))
            print(
                f"[check-ticket-test-requirements] BLOCKED: {path}",
                file=sys.stderr,
            )
            print(f"  Reason: {reason}", file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
