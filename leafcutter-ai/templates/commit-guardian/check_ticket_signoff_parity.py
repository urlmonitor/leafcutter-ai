"""
MODULE: check_ticket_signoff_parity.py
GOAL: Pre-commit guard that validates parity between a ticket's YAML frontmatter
    ``agents:`` map and its ``## Sign-offs`` checklist, preventing the two
    representations from drifting out of sync.
BUSINESS CONTEXT: The sync invariant (spec §4.4) requires that the frontmatter
    ``agents`` map and the ``## Sign-offs`` checklist contain the same agent set
    with the same status at all times. Agents update both surfaces in one atomic
    edit (signoff skill §2), but a hard guard at commit time is the last defence
    against partial writes or manual edits that only touch one surface. Tickets
    in ``done/`` have an additional invariant: no ``needed`` or ``failed`` entries
    are permitted, because done means every phase passed.
ARCHITECTURE: Pre-commit passes changed ticket paths as positional argv. The
    script iterates over each path, parses the YAML frontmatter and the
    ``## Sign-offs`` markdown section, and runs five parity checks. Violations
    are printed to stderr in ``<path>: <message>`` format. The script exits 0
    (warn-only default) or 1 (``--enforce`` mode). A parse failure on any single
    ticket emits a warning and continues to the next ticket — the pre-commit run
    is never aborted by a malformed file. Registered via
    ``scripts/commit_guardian/run_hook.py`` in ``.pre-commit-config.yaml``.

Exit Codes:
    0 - All files pass, or violations found in warn-only mode (default)
    1 - Violations found and --enforce flag is active, OR violations found
        in a file whose path contains a ``/done/`` segment (auto-enforced
        regardless of --enforce flag)

Usage:
    python scripts/commit_guardian/check_ticket_signoff_parity.py [--enforce] [file ...]
"""

import argparse
import sys
from pathlib import Path

# Fix import path when running as a script (not as a module).
# check_documentation.py uses the same pattern — without this, `scripts.commit_guardian`
# is not importable when run via `python scripts/commit_guardian/check_ticket_signoff_parity.py`.
_current_dir = Path(__file__).resolve().parent
_project_root = _current_dir.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from scripts.commit_guardian._signoff_parity_checks import (  # noqa: E402
    VALID_STATUSES,
    _build_signoffs_map,
    _check_done_folder,
    _check_enum_membership,
    _check_orphans,
    _check_parity,
    _check_unchecked_tasks,
    _classify_signoff_line,
    _expected_signoff_repr,
    _extract_agent_status,
    _parse_frontmatter,
    _parse_impl_tasks_section,
    _parse_signoffs_section,
    load_agent_registry,
    load_components_registry,
    validate_ticket_components,
    validate_ticket_files_touched_shape,
    validate_ticket_required_fields,
    validate_ticket_status_enum,
    validate_ticket_type_enum,
)

# Re-export everything so that importlib-based test shims (unit_tests/commit_guardian/
# _signoff_parity_helpers.py) continue to access all names via this module without
# any changes to the test code.
__all__ = [
    "VALID_STATUSES",
    "_build_signoffs_map",
    "_check_done_folder",
    "_check_enum_membership",
    "_check_orphans",
    "_check_parity",
    "_check_unchecked_tasks",
    "_classify_signoff_line",
    "_expected_signoff_repr",
    "_extract_agent_status",
    "_parse_frontmatter",
    "_parse_impl_tasks_section",
    "_parse_signoffs_section",
    "load_agent_registry",
    "load_components_registry",
    "validate_ticket_components",
    "validate_ticket_files_touched_shape",
    "validate_ticket_required_fields",
    "validate_ticket_status_enum",
    "validate_ticket_type_enum",
    "_validate_ticket_content",
    "_validate_ticket",
    "main",
]


# ---------------------------------------------------------------------------
# Per-file validation
# ---------------------------------------------------------------------------


def _validate_ticket_content(content: str, ticket_path: str, valid_components: set[str]) -> list[str]:
    """Run parity checks on a string of ticket content.

    Args:
        content: The text content of the ticket.
        ticket_path: Path to the ticket file (used for folder invariant checks).
        valid_components: Set of valid component IDs.

    Returns:
        List of violation strings.
    """
    try:
        fm = _parse_frontmatter(content)
    except Exception as exc:
        return [f"frontmatter parse error: {exc}"]

    if fm is None:
        return ["could not parse YAML frontmatter (missing or malformed)"]

    violations: list[str] = []
    violations.extend(validate_ticket_required_fields(fm))
    violations.extend(validate_ticket_type_enum(fm))
    violations.extend(validate_ticket_status_enum(fm))
    violations.extend(validate_ticket_components(fm, valid_components))
    violations.extend(validate_ticket_files_touched_shape(fm))

    agents = fm.get("agents")
    if agents is None:
        return []  # optional field — skip cleanly

    if not isinstance(agents, dict):
        return ["'agents' must be a YAML map of agent-name -> status"]

    signoff_lines = _parse_signoffs_section(content)
    signoffs, _unrecognised = _build_signoffs_map(signoff_lines)

    violations.extend(_check_enum_membership(agents))
    violations.extend(_check_parity(agents, signoffs))
    violations.extend(_check_orphans(agents, signoffs))
    violations.extend(_check_done_folder(ticket_path, agents))

    # Check #6: signed-off agents with requires_ticket_section: true must have no unchecked tasks.
    _proj_root = Path(__file__).resolve().parent.parent.parent
    _agent_registry = load_agent_registry(_proj_root)
    _impl_tasks = _parse_impl_tasks_section(content)
    violations.extend(_check_unchecked_tasks(agents, _impl_tasks, _agent_registry, ticket_path))

    return violations


def _validate_ticket(ticket_path: str, valid_components: set[str] = frozenset()) -> list[str]:
    """Run all parity checks on a single ticket file.

    Failures during file reading or frontmatter parsing are surfaced as a
    single warning-style violation and do not propagate exceptions.

    Args:
        ticket_path: Path to the ticket file, as passed by pre-commit.
        valid_components: Set of valid component IDs.

    Returns:
        List of violation strings. Empty list means the ticket is valid
        (or has no ``agents:`` key, which is permitted during migration).
    """
    try:
        content = Path(ticket_path).read_text(encoding="utf-8")
    except OSError as exc:
        return [f"could not read file: {exc}"]

    return _validate_ticket_content(content, ticket_path, valid_components)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for this guard.

    Returns:
        Configured ArgumentParser ready for parsing.
    """
    parser = argparse.ArgumentParser(
        description="Validate parity between ticket frontmatter agents: and ## Sign-offs."
    )
    parser.add_argument(
        "--enforce",
        action="store_true",
        default=False,
        help="Exit 1 when violations are found (default: warn-only, exit 0).",
    )
    parser.add_argument(
        "filenames",
        nargs="*",
        help="Ticket file paths to check (passed by pre-commit).",
    )
    return parser


def main() -> int:
    """Entry point for the pre-commit hook.

    Returns:
        0 when all files pass, or violations found in warn-only mode.
        1 when ``--enforce`` is active and violations exist, OR when a
        violation is found in a ``/done/`` path (auto-enforced).
    """
    parser = _build_arg_parser()
    args = parser.parse_args()

    enforce = args.enforce
    all_violations: list[tuple[str, str, bool]] = []  # (path, message, file_enforce)

    project_root = Path(__file__).resolve().parent.parent.parent
    valid_components = load_components_registry(project_root)

    for ticket_path in args.filenames:
        # /done/ paths always enforce (done-folder invariant is non-negotiable).
        file_enforce = enforce or ("/done/" in ticket_path.replace("\\", "/").lower())

        try:
            violations = _validate_ticket(ticket_path, valid_components)
        except Exception as exc:
            # Crash-resilient: a completely unexpected error on one ticket
            # emits a warning and continues.
            print(
                f"WARNING: {ticket_path}: unexpected error during parity check: {exc}",
                file=sys.stderr,
            )
            continue

        for msg in violations:
            all_violations.append((ticket_path, msg, file_enforce))

    if all_violations:
        for path, msg, fe in all_violations:
            print(f"{path}: {msg}", file=sys.stderr)
        if any(fe for _, __, fe in all_violations):
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-15 15:10 [python-coder/file-size-fix]: Extracted parsing and parity-check
  helpers into _signoff_parity_checks.py to stay under the 400-line budget.
  All names re-exported from this module via explicit imports so the existing
  importlib-based test shim (_signoff_parity_helpers.py) continues to work
  without modification. No logic changes.
- 2026-05-15 12:00 [python-coder/T06]: Added check #6 — unchecked-tasks parity guard. New helpers:
  load_agent_registry() (fail-open registry reader, mirrors load_components_registry()),
  _parse_impl_tasks_section() (counts - [ ] items per ### <agent> subheading in
  ## Implementation Tasks), _check_unchecked_tasks() (emits warn-only for absent sections,
  hard violation for present sections with unchecked items). AGENT_REGISTRY_PATH constant
  added to config.py. Integrates via _validate_ticket_content() violations.extend() —
  no changes to main() required.
- 2026-05-12 12:48 [Hendrik/Claude]: Auto-enforce for done-folder paths added
  (TICKET-20260512-Signoff_Write_Loss_Halt). The done-folder invariant is
  non-negotiable — warn-only mode on done/ paths was precisely the gap that
  hid the silent sign-off loss bug. Changed main() to compute a per-file
  file_enforce flag (True when path contains /done/ or --enforce is set),
  and to use file_enforce when deciding whether to exit 1. Unit tests added
  in unit_tests/commit_guardian/test_signoff_parity_auto_enforce.py.
- 2026-05-12 00:00 [Hendrik/Claude]: Extended for TICKET-20260511 Deliverable 2 (Option A).
  Added _extract_agent_status() helper that accepts both the scalar form (``signed_off``)
  and the nested-map form (``{status: signed_off, grandfathered: true}``). Updated
  _check_enum_membership, _check_parity, and _check_done_folder to route through the
  helper so grandfathered entries are valid without breaking existing scalar-format tickets.
- 2026-05-08 17:30 [Hendrik/Claude]: Created for EPIC-AgentSupervisor ticket 04.
  Warn-only by default; flip to --enforce after ticket 11's grandfathering
  migration runs. Five parity checks: enum membership, frontmatter↔Sign-offs
  representation agreement, orphan Sign-offs entries, done-folder invariant,
  and not_needed entries absent from Sign-offs. Parse failures on individual
  tickets are contained so the pre-commit run is never aborted by a single
  malformed file.
====================================================================
"""
