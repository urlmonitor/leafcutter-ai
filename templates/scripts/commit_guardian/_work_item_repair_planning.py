"""
Survivor-selection planning for the work-item duplicate repair.

MODULE: _work_item_repair_planning
GOAL: Read ``tickets/ticket_lifecycle.json``, walk the declared lifecycle
    folders to group "TICKET-*.md" claimants by basename, and decide -- for
    one contested basename -- which claimant survives, which is deleted, and
    which lifecycle folder the survivor ends up in. Split out of
    repair_work_item_duplicates.py to keep every new file in this directory
    under the project's 400-line-per-new-file limit.
BUSINESS CONTEXT: GE-122e-2's own it_requirements forbid a rule of thumb like
    "the completed folder wins" or "the non-inbox copy wins" -- the survivor
    must be computed from ticket_lifecycle.json's own data. This module
    computes it from one additional signal already present in that config: a
    folder whose ``when_tickets_move_out`` field contains the word "never" is
    a TERMINAL, permanent archive (99_done, 99_rejected), as opposed to an
    active, still-in-flight folder (00_inbox, 01_todo). A declared status
    permitted ONLY in a terminal folder is treated as later/more-final than
    one permitted only in non-terminal folders. This is what correctly moves
    the discriminating BP-1200a-1-ii shape -- whose "done"-declaring copy
    sits in 01_todo, a folder that does not permit "done" -- to 99_done
    instead of leaving it in place because "01_todo isn't the inbox".
ARCHITECTURE: Pure data + pure filesystem walk; the one I/O boundary
    (reading each candidate ticket's text) is delegated to
    ``_work_item_repair_io.read_text``, which already fails open with a
    WARNING per CLAUDE.md Rules 1-4, so this module performs no try/except of
    its own.

DOC_LINKS:
  - docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122e-2.yaml
  - tickets/ticket_lifecycle.json

DECISION HISTORY:
  - 2026-08-18 [python-coder/GE-122e-2]: Extracted from
    repair_work_item_duplicates.py to keep every new file in this directory
    under the check-file-size 400-line limit for new files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from _work_item_repair_io import read_status, read_text  # type: ignore[import]  # noqa: E402

_HOOK_PREFIX = "[repair_work_item_duplicates]"

Claimant = tuple[Path, "str | None", str]


# ---------------------------------------------------------------------------
# Lifecycle config
# ---------------------------------------------------------------------------


def load_lifecycle_folders(lifecycle_config_path: Path) -> list[dict]:
    """Read the lifecycle folder list from ``tickets/ticket_lifecycle.json``.

    Args:
        lifecycle_config_path: Path to the lifecycle config file.

    Returns:
        List of folder descriptors (``name``, ``allowed_statuses``,
        ``terminal``), in the config's own declared order, or an empty list
        if the config is missing, unreadable, or unparsable (fail-open:
        nothing to walk rather than a crash).
    """
    try:
        content = lifecycle_config_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"{_HOOK_PREFIX} WARNING: cannot read {lifecycle_config_path}: {exc}", file=sys.stderr)
        return []

    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        print(f"{_HOOK_PREFIX} WARNING: cannot parse {lifecycle_config_path}: {exc}", file=sys.stderr)
        return []

    folders = []
    for entry in data.get("folders", []):
        path = entry.get("path")
        if not path:
            continue
        when_moves_out = str(entry.get("when_tickets_move_out", "")).lower()
        folders.append(
            {
                "name": Path(path).name,
                "allowed_statuses": list(entry.get("allowed_statuses", [])),
                "terminal": "never" in when_moves_out,
            }
        )
    return folders


def terminal_statuses(folders: list[dict]) -> set[str]:
    """Return every status permitted by at least one terminal (archive) folder.

    Args:
        folders: Folder descriptors from ``load_lifecycle_folders``.

    Returns:
        Set of status strings permitted only by "when_tickets_move_out":
        "Never" folders -- the later/more-final states.
    """
    statuses: set[str] = set()
    for folder in folders:
        if folder["terminal"]:
            statuses.update(folder["allowed_statuses"])
    return statuses


def folders_allowing(status: str | None, folders: list[dict]) -> list[dict]:
    """Return every folder descriptor that permits *status*, in config order.

    Args:
        status: A declared status string, or None.
        folders: Folder descriptors from ``load_lifecycle_folders``.

    Returns:
        The matching folder descriptors, config-order preserved.
    """
    if status is None:
        return []
    return [folder for folder in folders if status in folder["allowed_statuses"]]


# ---------------------------------------------------------------------------
# Claim collection
# ---------------------------------------------------------------------------


def collect_claims(tickets_root: Path, folders: list[dict]) -> dict[str, list[Claimant]]:
    """Walk every declared lifecycle folder and group files by basename.

    Non-recursive per folder, matching the sibling detection scanner
    (_work_items_scanner.py), so an epic's own sub-tickets and Master_Plan.md
    are never visited.

    Args:
        tickets_root: The ``tickets/`` directory to walk.
        folders: Folder descriptors from ``load_lifecycle_folders``.

    Returns:
        Mapping of claimed basename to its list of (path, declared_status,
        folder_name) claimant tuples.
    """
    claims: dict[str, list[Claimant]] = {}
    for folder in folders:
        folder_path = tickets_root / folder["name"]
        if not folder_path.is_dir():
            continue
        for ticket_path in sorted(folder_path.glob("TICKET-*.md")):
            text = read_text(ticket_path)
            status = read_status(text) if text is not None else None
            claims.setdefault(ticket_path.name, []).append((ticket_path, status, folder["name"]))
    return claims


# ---------------------------------------------------------------------------
# Survivor selection
# ---------------------------------------------------------------------------


def choose_winner(claimants: list[Claimant], terminal: set[str]) -> tuple[Claimant, Claimant]:
    """Pick the surviving claimant and the losing claimant for one pair.

    A claimant whose declared status is permitted only in a terminal
    (permanent-archive) folder wins over one whose status is not -- computed
    from ticket_lifecycle.json's own "when_tickets_move_out" data, never from
    an assumption about which folder looks "more final". Ties (both or
    neither terminal) are broken by path string, purely for determinism.

    Args:
        claimants: Exactly two (path, declared_status, folder_name) tuples.
        terminal: Statuses permitted by at least one terminal folder.

    Returns:
        (winner, loser) tuple, each a (path, declared_status, folder_name).
    """

    def sort_key(claimant: Claimant) -> tuple[int, str]:
        _path, status, _folder = claimant
        is_terminal = status in terminal
        return (0 if is_terminal else 1, str(claimant[0]))

    ranked = sorted(claimants, key=sort_key)
    return ranked[0], ranked[1]


def destination_folder(winner_status: str | None, winner_folder: str, folders: list[dict]) -> str:
    """Compute the lifecycle folder the winner's declared status permits.

    Args:
        winner_status: The winning claimant's declared status.
        winner_folder: The winning claimant's current folder name.
        folders: Folder descriptors from ``load_lifecycle_folders``.

    Returns:
        The winner's current folder if it already permits its own declared
        status; otherwise the first (config-order) folder that does; or the
        current folder unchanged if no folder permits it at all (fail-open).
    """
    allowed = folders_allowing(winner_status, folders)
    if not allowed:
        return winner_folder
    allowed_names = [folder["name"] for folder in allowed]
    return winner_folder if winner_folder in allowed_names else allowed_names[0]


def describe_resolution(
    winner_status: str | None,
    winner_folder: str,
    loser_status: str | None,
    loser_folder: str,
    target_folder: str,
    terminal: set[str],
) -> tuple[str, str]:
    """Build the human-readable resolution label and reason for one pair.

    Args:
        winner_status: The surviving copy's declared status.
        winner_folder: The surviving copy's original folder.
        loser_status: The deleted copy's declared status.
        loser_folder: The deleted copy's folder.
        target_folder: The folder the survivor ends up in.
        terminal: Statuses permitted by at least one terminal folder.

    Returns:
        (resolution, reason) tuple of non-empty strings.
    """
    resolution = (
        f"kept the '{winner_status}' copy (previously held by {winner_folder}) "
        f"and removed the '{loser_status}' copy (held by {loser_folder})"
    )
    if winner_status in terminal and loser_status not in terminal:
        reason = (
            f"tickets/ticket_lifecycle.json permits status '{winner_status}' only in a terminal, "
            f"permanent archive folder ({target_folder}), while status '{loser_status}' is only "
            f"permitted in non-terminal, still-in-flight folders, so the '{winner_status}' "
            "declaration records the later, completed state."
        )
    else:
        reason = (
            "tickets/ticket_lifecycle.json does not mark either declared state as uniquely "
            f"terminal, so the copy previously held by {winner_folder} was kept and relocated to "
            f"{target_folder}, the folder its own declared status permits."
        )
    return resolution, reason
