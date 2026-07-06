"""
MODULE: check_ac_limits
GOAL: Pre-commit hook that enforces acceptance-criteria count limits on staged
    ticket files — max 7 ACs per agent block, max 20 ACs per ticket total.
BUSINESS CONTEXT: Oversized tickets (>7 ACs for one agent or >20 total) are
    too large for safe atomic implementation. This hook detects bloated tickets
    at commit time so the IT PO can split them before they enter the
    implementation pipeline. Tickets with `ac_limit_override: true` in
    frontmatter are warned but not blocked. v1 tickets (no `## Agent Contracts`
    section) are skipped transparently. Structured JSON on stderr enables
    `precommit-autofix` to route the failure to the IT PO agent automatically.
ARCHITECTURE: Reads the staged diff via `git diff --cached` (or HOOK_TEST_DIFF
    env var for unit testing), extracts paths of staged `.md` ticket files,
    and for each file reads it from disk (not from the diff) to get its full
    content. Parses the YAML frontmatter for `ac_limit_override`, finds the
    `## Agent Contracts` section, iterates `### <agent-name>` subsections,
    counts `- [ ] AC-N:` lines per agent (excluding `<!-- scope: integration -->`
    lines from per-agent counts), and also tallies a ticket-level total.
    Exits non-zero with a structured JSON payload on stderr when limits are
    exceeded. v1-flat tickets (no `## Agent Contracts` section) are now
    subject to the 20-total cap; the per-agent cap (7) is not applied because
    there are no `### <agent>` subsections to parse.
DOC_LINKS:
  - tickets/00_inbox/epics/EPIC-ContractDrivenACs/02b_ac_count_hook.md

Exit Codes:
    0 - All staged ticket files pass, or no ticket files staged, or override active
    1 - One or more ticket files exceed AC limits

Usage:
    python scripts/commit_guardian/run_hook.py \\
        scripts/commit_guardian/hooks/check_ac_limits.py
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_ACS_PER_AGENT: int = 7
_MAX_ACS_TOTAL: int = 20

# Matches: ### any-agent-name (one or more header-2 subsections in Agent Contracts)
_AGENT_SECTION_RE = re.compile(r"^###\s+(.+)$", re.MULTILINE)

# Matches an unchecked AC line: `- [ ] AC-<digits>:`
_AC_LINE_RE = re.compile(r"^\s*-\s*\[\s*\]\s*AC-\d+:", re.MULTILINE)

# Integration-scope exclusion marker
_INTEGRATION_SCOPE_RE = re.compile(r"<!--\s*scope:\s*integration\s*-->", re.IGNORECASE)

# Ticket file filter: only .md files that look like ticket paths
_TICKET_PATH_RE = re.compile(r"tickets/.*\.md$", re.IGNORECASE)

# YAML frontmatter override flag
_FRONTMATTER_OVERRIDE_RE = re.compile(
    r"^ac_limit_override\s*:\s*true", re.MULTILINE | re.IGNORECASE
)

# Detects the ## Agent Contracts section start (h2 only)
_AGENT_CONTRACTS_H2_RE = re.compile(r"^##\s+Agent Contracts\s*$", re.MULTILINE)

# Detects any h2 section start (to find the end of Agent Contracts)
_H2_RE = re.compile(r"^##\s+\S", re.MULTILINE)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class AgentViolation:
    """A single per-agent AC limit violation."""

    agent: str
    count: int
    limit: int


@dataclass
class TicketResult:
    """Parsed AC counts and violations for one ticket file."""

    path: str
    skipped: bool = False
    override_active: bool = False
    per_agent: dict[str, int] = field(default_factory=dict)
    total_ac_count: int = 0
    violations: list[AgentViolation] = field(default_factory=list)
    total_violation: bool = False

    @property
    def has_violations(self) -> bool:
        """True iff any per-agent or total limit is exceeded."""
        return bool(self.violations) or self.total_violation


# ---------------------------------------------------------------------------
# Diff reading
# ---------------------------------------------------------------------------


def _get_staged_diff() -> str:
    """Return the staged diff as a string.

    Uses HOOK_TEST_DIFF env var when set (for unit testing only).
    Otherwise calls git diff --cached.

    Returns:
        The full text of the staged diff.
    """
    test_diff_path = os.environ.get("HOOK_TEST_DIFF")
    if test_diff_path:
        try:
            return Path(test_diff_path).read_text(encoding="utf-8")
        except OSError as exc:
            print(
                f"[check-ac-limits] ERROR: could not read HOOK_TEST_DIFF: {exc}",
                file=sys.stderr,
            )
            sys.exit(1)

    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(
            f"[check-ac-limits] ERROR: git diff --cached --name-only failed: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)
    else:
        return result.stdout


def _extract_staged_ticket_paths(diff_output: str) -> list[str]:
    """Extract ticket .md file paths from the diff output.

    When using HOOK_TEST_DIFF, the env var holds a plain newline-separated
    list of paths (not a patch). When using git output directly, it is also
    newline-separated (--name-only mode).

    Args:
        diff_output: Newline-separated list of changed file paths.

    Returns:
        List of relative paths that look like ticket .md files.
    """
    paths = []
    for line in diff_output.splitlines():
        stripped = line.strip()
        if stripped and _TICKET_PATH_RE.search(stripped):
            paths.append(stripped)
    return paths


# ---------------------------------------------------------------------------
# Frontmatter / AC parsing
# ---------------------------------------------------------------------------


def _has_override(content: str) -> bool:
    """Return True iff the ticket frontmatter contains ac_limit_override: true.

    Args:
        content: Full ticket file content.

    Returns:
        True if override is active.
    """
    # Only inspect within the frontmatter block (between the first pair of ---)
    parts = content.split("---", 2)
    if len(parts) < 3:
        return False
    frontmatter = parts[1]
    return bool(_FRONTMATTER_OVERRIDE_RE.search(frontmatter))


def _extract_agent_contracts_block(content: str) -> str | None:
    """Extract the text of the ## Agent Contracts section.

    Returns everything from '## Agent Contracts' up to (but not including)
    the next h2 section, or end of file.

    Args:
        content: Full ticket file content.

    Returns:
        The Agent Contracts block text, or None if the section is absent.
    """
    match = _AGENT_CONTRACTS_H2_RE.search(content)
    if not match:
        return None

    start = match.end()
    # Find the next h2 after the start position
    next_h2 = _H2_RE.search(content, start)
    if next_h2:
        return content[start:next_h2.start()]
    return content[start:]


def _count_acs_in_block(block: str) -> int:
    """Count total unchecked AC lines in a block, including integration-scoped ones.

    Args:
        block: A text block (e.g. an agent subsection).

    Returns:
        Total count of `- [ ] AC-N:` lines.
    """
    return len(_AC_LINE_RE.findall(block))


def _count_acs_per_agent(contracts_block: str) -> dict[str, int]:
    """Parse ### <agent-name> subsections and return per-agent non-integration AC counts.

    Integration ACs (those containing `<!-- scope: integration -->`) are excluded
    from the per-agent count.

    Args:
        contracts_block: Text of the ## Agent Contracts section.

    Returns:
        Mapping of agent_name -> AC count (integration ACs excluded).
    """
    agent_counts: dict[str, int] = {}

    # Find all ### headings and their positions
    agent_matches = list(_AGENT_SECTION_RE.finditer(contracts_block))
    if not agent_matches:
        return agent_counts

    for i, match in enumerate(agent_matches):
        agent_name = match.group(1).strip()
        subsection_start = match.end()
        subsection_end = (
            agent_matches[i + 1].start()
            if i + 1 < len(agent_matches)
            else len(contracts_block)
        )
        subsection_text = contracts_block[subsection_start:subsection_end]

        # Count non-integration ACs only
        count = 0
        for line in subsection_text.splitlines():
            if _AC_LINE_RE.match(line) and not _INTEGRATION_SCOPE_RE.search(line):
                count += 1

        agent_counts[agent_name] = count

    return agent_counts


def _count_total_acs(contracts_block: str) -> int:
    """Count total ACs across all agent blocks (including integration-scoped ones).

    Args:
        contracts_block: Text of the ## Agent Contracts section.

    Returns:
        Total count of all `- [ ] AC-N:` lines in the block.
    """
    return _count_acs_in_block(contracts_block)


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------


def _find_project_root() -> Path:
    """Walk up from this script's location to find the project root.

    Returns:
        Absolute path to the project root.
    """
    here = Path(__file__).resolve().parent
    for ancestor in [here, *here.parents]:
        if (ancestor / ".git").exists() or (ancestor / "CLAUDE.md").exists():
            return ancestor
    # Fallback: 3 levels up from hooks/
    return here.parent.parent.parent


def _analyse_ticket(path: str, project_root: Path) -> TicketResult:
    """Analyse a single ticket file for AC limit violations.

    Args:
        path: Relative path to the ticket file (relative to project_root).
        project_root: Absolute path to the project root.

    Returns:
        A TicketResult describing what was found.
    """
    result = TicketResult(path=path)

    ticket_path = project_root / path
    try:
        content = ticket_path.read_text(encoding="utf-8")
    except OSError as exc:
        # File cannot be read — skip with a warning (not a blocking error)
        print(
            f"[check-ac-limits] WARNING: could not read {path}: {exc}",
            file=sys.stderr,
        )
        result.skipped = True
        return result

    # Check override flag first
    if _has_override(content):
        result.override_active = True
        # Still parse ACs so we can emit a warning, but do not block
        contracts_block = _extract_agent_contracts_block(content)
        if contracts_block:
            result.per_agent = _count_acs_per_agent(contracts_block)
            result.total_ac_count = _count_total_acs(contracts_block)
        else:
            # v1-flat format with override: count full-body ACs for the warning
            result.total_ac_count = _count_acs_in_block(content)
        return result

    # Extract the ## Agent Contracts section (present on v2 tickets).
    contracts_block = _extract_agent_contracts_block(content)
    if contracts_block is None:
        # v1-flat format: no ## Agent Contracts section. Count all _AC_LINE_RE
        # matches across the full ticket body and apply the 20-total cap.
        # The per-agent cap (7) is NOT applied on this path — it requires
        # ### <agent> subsection structure.
        result.total_ac_count = _count_acs_in_block(content)
        if result.total_ac_count > _MAX_ACS_TOTAL:
            result.total_violation = True
        return result

    result.per_agent = _count_acs_per_agent(contracts_block)
    result.total_ac_count = _count_total_acs(contracts_block)

    # Check per-agent limits
    for agent_name, count in result.per_agent.items():
        if count > _MAX_ACS_PER_AGENT:
            result.violations.append(
                AgentViolation(agent=agent_name, count=count, limit=_MAX_ACS_PER_AGENT)
            )

    # Check total limit
    if result.total_ac_count > _MAX_ACS_TOTAL:
        result.total_violation = True

    return result


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _build_json_payload(results: list[TicketResult]) -> dict:
    """Build the structured JSON payload for precommit-autofix routing.

    Args:
        results: List of TicketResult objects with violations.

    Returns:
        A dict suitable for JSON serialisation.
    """
    violations = []
    for ticket_result in results:
        if not ticket_result.has_violations:
            continue
        entry: dict = {"ticket": ticket_result.path, "violations": []}
        for violation in ticket_result.violations:
            entry["violations"].append(
                {
                    "type": "per_agent",
                    "agent": violation.agent,
                    "count": violation.count,
                    "limit": violation.limit,
                }
            )
        if ticket_result.total_violation:
            entry["violations"].append(
                {
                    "type": "total",
                    "count": ticket_result.total_ac_count,
                    "limit": _MAX_ACS_TOTAL,
                }
            )
        violations.append(entry)

    return {
        "hook": "check_ac_limits",
        "fix_agent": "it-po",
        "violations": violations,
    }


def _print_human_error(results: list[TicketResult]) -> None:
    """Print a human-readable error block for blocking violations.

    Args:
        results: List of TicketResult objects with violations.
    """
    lines: list[str] = [
        "",
        "[check-ac-limits] BLOCKED — AC count limits exceeded",
        "",
    ]
    for ticket_result in results:
        if not ticket_result.has_violations:
            continue
        lines.append(f"  Ticket: {ticket_result.path}")
        for violation in ticket_result.violations:
            lines.append(
                f"    agent '{violation.agent}': {violation.count} ACs "
                f"(max {violation.limit}) — split the ticket"
            )
        if ticket_result.total_violation:
            lines.append(
                f"    total: {ticket_result.total_ac_count} ACs "
                f"(max {_MAX_ACS_TOTAL}) — this ticket is an epic in disguise"
            )
        lines.append("")

    lines.append("Fix: split the ticket so no agent block exceeds 7 ACs and total <= 20.")
    lines.append(
        "Escape hatch: add `ac_limit_override: true` to frontmatter only when "
        "splitting would create worse coupling (requires IT PO review)."
    )
    lines.append("")
    print("\n".join(lines), file=sys.stderr)


def _print_override_warning(results: list[TicketResult]) -> None:
    """Print a warning for tickets with ac_limit_override: true.

    Args:
        results: List of TicketResult objects where override is active.
    """
    for ticket_result in results:
        if not ticket_result.override_active:
            continue
        over_agent = [
            f"{a}: {c}" for a, c in ticket_result.per_agent.items()
            if c > _MAX_ACS_PER_AGENT
        ]
        over_total = ticket_result.total_ac_count > _MAX_ACS_TOTAL
        if not (over_agent or over_total):
            continue  # override present but no actual excess — no warning needed
        warn_parts = over_agent[:]
        if over_total:
            warn_parts.append(f"total: {ticket_result.total_ac_count}")
        print(
            f"[check-ac-limits] WARNING (override active): {ticket_result.path} "
            f"exceeds AC limits ({', '.join(warn_parts)}) but ac_limit_override: true "
            f"— commit not blocked.",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Run the AC limits pre-commit hook.

    Returns:
        0 if all staged tickets pass (or are overridden/skipped), 1 if blocked.
    """
    project_root = _find_project_root()

    diff_output = _get_staged_diff()
    ticket_paths = _extract_staged_ticket_paths(diff_output)

    if not ticket_paths:
        return 0

    results: list[TicketResult] = []
    for path in ticket_paths:
        ticket_result = _analyse_ticket(path, project_root)
        results.append(ticket_result)

    # Emit override warnings (non-blocking)
    _print_override_warning(results)

    # Check for blocking violations
    blocking = [r for r in results if r.has_violations and not r.override_active]
    if not blocking:
        return 0

    # BLOCKED — print human-readable error + structured JSON
    _print_human_error(blocking)
    payload = _build_json_payload(blocking)
    print(json.dumps(payload, indent=2), file=sys.stderr)

    return 1


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-04 [EPIC-ContractDrivenACs/02b]: Created check_ac_limits.py.
    Enforces max 7 ACs per agent block and max 20 total per ticket.
    Integration-scoped ACs excluded from per-agent counts.
    Structured JSON payload on stderr for precommit-autofix routing.
    ac_limit_override: true in frontmatter warns but does not block.
    v1 tickets (no ## Agent Contracts section) were originally skipped silently.
- 2026-07-06 [GE-114]: Fixed silent skip of 20-total AC cap for v1-flat tickets.
    When ## Agent Contracts is absent, _analyse_ticket now counts all _AC_LINE_RE
    matches across the full body and applies the 20-total cap. result.skipped=True
    is now reserved exclusively for the OSError (unreadable file) path.
    The per-agent cap (7) is NOT applied on the v1-flat path.
    The ac_limit_override: true branch also populates total_ac_count for flat
    tickets so the override warning can report the excess count.
====================================================================
"""
