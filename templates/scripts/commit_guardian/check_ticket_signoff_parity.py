"""
MODULE: check_ticket_signoff_parity.py
GOAL: Pre-commit guard that validates parity between a ticket's YAML frontmatter
    ``agents:`` map and its ``## Sign-offs`` checklist, preventing the two
    representations from drifting out of sync.
BUSINESS CONTEXT: The sync invariant (spec §4.4) requires that the frontmatter
    ``agents`` map and the ``## Sign-offs`` checklist contain the same agent set
    with the same status at all times. Agents update both surfaces in one atomic
    edit (signoff skill §2), but a hard guard at commit time is the last defence
    against partial writes or manual edits that only touch one surface. Done
    tickets (frontmatter ``status: done``, or a legacy ``done/`` path) have an
    additional invariant: no ``needed`` or ``failed`` entries are permitted.
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
    1 - Violations found and --enforce is active, OR any violation in a
        ``/done/`` path, OR a ``status: done`` ticket with a needed/failed
        agent (other violations on such a ticket stay warn-only)

Usage:
    python scripts/commit_guardian/check_ticket_signoff_parity.py [--enforce] [file ...]
"""

import argparse
import subprocess
import sys
from pathlib import Path

# Fix import path when running as a script (not as a module).
# check_documentation.py uses the same pattern — without this, `scripts.commit_guardian`
# is not importable when run via `python scripts/commit_guardian/check_ticket_signoff_parity.py`.
from _resolve_root import find_project_root

project_root = find_project_root()

from _signoff_parity_checks import (  # noqa: E402
    VALID_STATUSES,
    _build_signoffs_map,
    _check_done_folder,
    _check_done_folder_prohibition,
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
    check_cross_layer_seam_answer,
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
    "_check_done_folder_prohibition",
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
    "check_cross_layer_seam_answer",
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


def _is_done_status(fm: dict | None) -> bool:
    """Return True when frontmatter ``status`` is the string ``done`` (BO-400c-5).

    A missing, non-string, or malformed status is treated as not done.
    """
    status = fm.get("status") if isinstance(fm, dict) else None
    return isinstance(status, str) and status.strip().lower() == "done"


# Prefix of the only violation main() blocks on outside --enforce / done/ paths.
_DONE_STATUS_PREFIX = "ticket has status: done but agent"


def _check_done_status(fm: dict, agents: dict, ticket_path: str) -> list[str]:
    """Report ``needed``/``failed`` agents on a ``status: done`` ticket (BO-400c-5).

    Legacy ``done/`` paths are skipped: ``_check_done_folder`` already reports them.
    main() treats these messages (and only these) as blocking on such tickets.
    """
    if not _is_done_status(fm) or "/done/" in ticket_path.replace("\\", "/").lower():
        return []
    return [
        f"{_DONE_STATUS_PREFIX} '{name}' still has status '{status}' "
        "(must be 'signed_off' or 'not_needed')"
        for name, raw in agents.items()
        if (status := _extract_agent_status(raw)) in ("needed", "failed")
    ]


def _validate_ticket_content(
    content: str,
    ticket_path: str,
    valid_components: set[str],
    *,
    old_path: str | None = None,
) -> list[str]:
    """Run parity checks on a string of ticket content.

    Args:
        content: The text content of the ticket.
        ticket_path: Path to the ticket file (used for folder invariant checks).
        valid_components: Set of valid component IDs.
        old_path: The pre-move (HEAD) path of the file, or ``None`` when the
            caller does not have rename information.  Forwarded to
            ``_check_done_folder_prohibition()`` so the move-based done-folder
            check can distinguish a genuine move from an in-place edit
            (BO-400c-3-i).

    Returns:
        List of violation strings.
    """
    try:
        fm = _parse_frontmatter(content)
    except Exception as exc:  # noqa: BLE001
        return [f"frontmatter parse error: {exc}"]

    if fm is None:
        return ["could not parse YAML frontmatter (missing or malformed)"]

    violations: list[str] = []
    violations.extend(validate_ticket_required_fields(fm))
    violations.extend(validate_ticket_type_enum(fm))
    violations.extend(validate_ticket_status_enum(fm))
    violations.extend(validate_ticket_components(fm, valid_components))
    violations.extend(validate_ticket_files_touched_shape(fm))

    # BP-1100g-5-i: cross_layer_seam_answer shortfall — a record-shape
    # observation over the ## Comments completion_manifest: block(s), run
    # regardless of whether the ticket has an `agents:` map.
    seam_shortfall = check_cross_layer_seam_answer(content, ticket_path)
    if seam_shortfall is not None:
        violations.append(
            f"cross_layer_seam_answer {seam_shortfall['kind']}: {seam_shortfall['detail']}"
        )

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
    violations.extend(_check_done_status(fm, agents, ticket_path))
    violations.extend(_check_done_folder_prohibition(ticket_path, old_path=old_path))

    # Check #6: signed-off agents with requires_ticket_section: true must have no unchecked tasks.
    _proj_root = find_project_root()
    _agent_registry = load_agent_registry(_proj_root)
    _impl_tasks = _parse_impl_tasks_section(content)
    violations.extend(_check_unchecked_tasks(agents, _impl_tasks, _agent_registry, ticket_path))

    return violations


def _validate_ticket(
    ticket_path: str,
    valid_components: set[str] = frozenset(),
    *,
    old_path: str | None = None,
) -> list[str]:
    """Run all parity checks on a single ticket file.

    Failures during file reading or frontmatter parsing are surfaced as a
    single warning-style violation and do not propagate exceptions.

    Args:
        ticket_path: Path to the ticket file, as passed by pre-commit.
        valid_components: Set of valid component IDs.
        old_path: The pre-move (HEAD) path of the file, or ``None`` when rename
            information is unavailable.  Forwarded to ``_validate_ticket_content``
            so the move-based done-folder prohibition (BO-400c-3-i) can
            distinguish a genuine move from an in-place edit.

    Returns:
        List of violation strings. Empty list means the ticket is valid
        (or has no ``agents:`` key, which is permitted during migration).
    """
    try:
        content = Path(ticket_path).read_text(encoding="utf-8")
    except OSError as exc:
        return [f"could not read file: {exc}"]

    return _validate_ticket_content(content, ticket_path, valid_components, old_path=old_path)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_rename_map() -> dict[str, str]:
    """Query git for staged renames and in-place edits; return new-path to old-path mapping.

    Used to detect whether a staged commit is moving a ticket into a done/
    folder, so the done-folder prohibition check (BO-400c-3) can distinguish a
    genuine move from an in-place edit of a file already residing at a done/
    path (BO-400c-3-i).

    For renamed files (R status): maps new_path -> old_path.
    For modified-in-place files (M status): maps path -> path (old_path == new_path),
    so that ``_check_done_folder_prohibition`` sees ``old_in_done`` and skips the
    false-positive prohibition for files that already resided at a done/ path.

    Fail-open: returns an empty dict when git is unavailable or the command
    fails, causing the prohibition to fall back to presence-based detection
    for backward compatibility.

    Returns:
        Dict mapping each staged file's new (staged) path to its old (HEAD)
        path.  Modified-in-place files have old_path == new_path.
        Files not in the R or M status categories are absent from the dict.
    """
    rename_map: dict[str, str] = {}
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-status", "--diff-filter=RM"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        print(
            f"WARNING: check-ticket-signoff-parity: git diff timed out: {exc}",
            file=sys.stderr,
        )
        return rename_map
    except OSError as exc:
        print(
            f"WARNING: check-ticket-signoff-parity: could not query git renames: {exc}",
            file=sys.stderr,
        )
        return rename_map
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].startswith("R"):
            # Rename: R<score>\t<old_path>\t<new_path> — map new_path -> old_path
            rename_map[parts[2]] = parts[1]
        elif len(parts) == 2 and parts[0] == "M":
            # Modified in place: M\t<path> — old_path == new_path (no move)
            rename_map[parts[1]] = parts[1]
    return rename_map


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
        1 when ``--enforce`` is active and violations exist, when a
        violation is found in a legacy ``/done/`` path, OR when a
        ``status: done`` ticket still has a needed/failed agent (BO-400c-5).
    """
    args = _build_arg_parser().parse_args()
    all_violations: list[tuple[str, str, bool]] = []  # (path, message, blocking)
    valid_components = load_components_registry(find_project_root())
    rename_map = _build_rename_map()

    for ticket_path in args.filenames:
        # --enforce and legacy done/ paths block on every violation.
        file_enforce = args.enforce or ("/done/" in ticket_path.replace("\\", "/").lower())
        old_path = rename_map.get(ticket_path)

        try:
            violations = _validate_ticket(ticket_path, valid_components, old_path=old_path)
        except Exception as exc:  # noqa: BLE001
            # Crash-resilient: a completely unexpected error on one ticket
            # emits a warning and continues.
            print(
                f"WARNING: {ticket_path}: unexpected error during parity check: {exc}",
                file=sys.stderr,
            )
            continue

        for msg in violations:
            # BO-400c-5: on a status: done ticket only the needed/failed rule blocks.
            blocking = file_enforce or msg.startswith(_DONE_STATUS_PREFIX)
            all_violations.append((ticket_path, msg, blocking))

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
- 2026-09-25 [python-coder/BO-400c-5]: status: done + needed/failed agent now
  blocks at any path (KI-CG-20260925: done/ moves retired by BO-400c-1, hook
  registered without --enforce). Only that rule blocks; other violations on done
  tickets stay warn-only (blocking all would hit 638/725 done tickets). Added
  _is_done_status, _check_done_status. Older entries condensed (line budget).
- 2026-08-31 [python-coder/BP-1100g-5-i]: Wired check_cross_layer_seam_answer()
  into _validate_ticket_content() (runs before the `agents:` check) and
  registered the hook id in commit_guardian.json hooks_manifest.
- 2026-07-14 [python-coder/BO-400c-3-callsite]: _build_rename_map() (fail-open)
  threads old_path to _check_done_folder_prohibition (BO-400c-3-i).
- 2026-05-15 [python-coder/file-size-fix, T06]: Helpers extracted to
  _signoff_parity_checks.py and re-exported; check #6 unchecked-tasks guard.
- 2026-05-12 [Hendrik/Claude]: Auto-enforce for done/ paths
  (TICKET-20260512-Signoff_Write_Loss_Halt); _extract_agent_status() accepts
  scalar and nested-map (grandfathered) statuses (TICKET-20260511).
- 2026-05-08 [Hendrik/Claude]: Created for EPIC-AgentSupervisor ticket 04:
  warn-only by default, five parity checks, per-ticket parse failures contained.
====================================================================
"""
