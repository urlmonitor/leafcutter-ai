"""
Repair for work-item identifiers held by more than one lifecycle folder.

MODULE: repair_work_item_duplicates
GOAL: Provide a single importable entry point,
    ``repair_work_item_duplicates(tickets_root, lifecycle_config_path) ->
    RepairReport``, that reduces every "TICKET-*.md" basename held by two
    lifecycle folders down to the one copy whose declared ``status:`` is the
    later, correct state, relocates that survivor into the lifecycle folder
    its own declared state actually permits (per
    ``tickets/ticket_lifecycle.json``), records the resolution and reason on
    the survivor file itself, folds in any content the deleted copy alone
    held, and deletes the losing copy.
BUSINESS CONTEXT: GE-122a-2 ("one work item cannot exist as two copies free
    to disagree about its state") is the detection half; this module
    (GE-122e-2) is the repair half. See
    docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122e-2.yaml
    (including its 2026-08-18 amendment) for the binding survivor rule: the
    survivor is computed from ticket_lifecycle.json's allowed-status-per-
    folder mapping, never assumed to be "the completed folder" or "the
    non-inbox copy". This repair is a deletion and therefore irreversible
    from the store's own perspective -- the content-preservation and
    resolution-recording behaviour this module delegates to
    ``_work_item_repair_io`` exists because two copies of one work item may
    have drifted, each holding something the other lacks.
ARCHITECTURE: Thin orchestrator over two sibling modules (split out to keep
    every new file in this directory under the project's 400-line-per-new-
    file limit, following the check_identifier_uniqueness.py /
    _uniqueness_scanners.py / _work_items_scanner.py precedent already
    established here):
      - _work_item_repair_types.py: the Resolution / RepairReport dataclasses
        (re-exported here for the public contract).
      - _work_item_repair_planning.py: reads ticket_lifecycle.json, walks the
        lifecycle folders to group claimants by basename, and decides which
        claimant survives, which is deleted, and which folder the survivor
        ends up in.
      - _work_item_repair_io.py: every read, write, move, and delete this
        repair performs, including merging the losing copy's unique body
        content into the survivor and recording the resolution + reason on
        the survivor's own text.
    This module can be loaded three different ways -- as a script, as a
    subprocess target from the deployed layout, and via
    ``importlib.util.spec_from_file_location`` from a test file that never
    adds this directory to ``sys.path`` -- so the sibling imports are made
    robust by inserting this file's own directory into ``sys.path`` before
    importing, matching check_identifier_uniqueness.py's own approach.
    No dependency on the sibling DETECTION module
    (check_identifier_uniqueness.py / _work_items_scanner.py): this module
    re-derives the lifecycle folder list and each claimant's declared status
    directly from ``tickets_root`` and ``lifecycle_config_path``, the same
    two inputs its own public contract takes.
    SCOPE IS DELIBERATELY NARROW: a basename claimed by more than two
    lifecycle folders is reported at WARNING and skipped rather than guessed
    at -- the criteria this module satisfies name exactly five two-way
    duplicates, and guessing a three-way resolution is exactly the kind of
    silent scope expansion this AC's own it_requirements forbid.

DOC_LINKS:
  - docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122e-2.yaml
  - tickets/ticket_lifecycle.json
  - templates/scripts/commit_guardian/_work_items_scanner.py

DECISION HISTORY:
  - 2026-08-18 [python-coder/GE-122e-2]: Created. Satisfies the CONTRACT
    UNDER TEST fixed by unit_tests/commit_guardian/test_ge_122e_2.py before
    this module existed.
  - 2026-08-18 [python-coder/GE-122e-2 file-size split]: Split the survivor-
    selection planning and the ticket-text I/O into sibling modules
    (_work_item_repair_planning.py, _work_item_repair_io.py,
    _work_item_repair_types.py) to stay under the check-file-size 400-line
    limit for new files; the initial single-file draft was 608 lines.
"""

from __future__ import annotations

import sys
from pathlib import Path

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from _work_item_repair_io import (  # type: ignore[import]  # noqa: E402
    compose_survivor_content,
    read_text,
    relocate_file,
    remove_file,
    write_survivor,
)
from _work_item_repair_planning import (  # type: ignore[import]  # noqa: E402
    Claimant,
    choose_winner,
    collect_claims,
    describe_resolution,
    destination_folder,
    load_lifecycle_folders,
    terminal_statuses,
)
from _work_item_repair_types import RepairReport, Resolution  # type: ignore[import]  # noqa: E402

__all__ = ["Resolution", "RepairReport", "repair_work_item_duplicates"]

_HOOK_PREFIX = "[repair_work_item_duplicates]"


def _repair_pair(
    basename: str,
    claimants: list[Claimant],
    tickets_root: Path,
    folders: list[dict],
    terminal: set[str],
    repo_root: Path,
) -> Resolution | None:
    """Repair one contested basename held by exactly two lifecycle folders.

    Args:
        basename: The contested "TICKET-*.md" basename.
        claimants: Exactly two (path, declared_status, folder_name) tuples.
        tickets_root: The ``tickets/`` directory.
        folders: Folder descriptors from ``load_lifecycle_folders``.
        terminal: Statuses permitted by at least one terminal folder.
        repo_root: Repository root for git operations.

    Returns:
        The Resolution recorded for this identifier, or None if it could not
        be repaired (a claimant's text could not be read).
    """
    winner, loser = choose_winner(claimants, terminal)
    winner_path, winner_status, winner_folder = winner
    loser_path, loser_status, loser_folder = loser

    winner_text = read_text(winner_path)
    loser_text = read_text(loser_path)
    if winner_text is None or loser_text is None:
        print(f"{_HOOK_PREFIX} WARNING: skipping {basename}: a claimant could not be read.", file=sys.stderr)
        return None

    target_folder = destination_folder(winner_status, winner_folder, folders)
    resolution, reason = describe_resolution(
        winner_status, winner_folder, loser_status, loser_folder, target_folder, terminal
    )
    merged_content = compose_survivor_content(winner_text, loser_text, resolution, reason)

    target_path = winner_path if target_folder == winner_folder else tickets_root / target_folder / basename
    if target_path != winner_path:
        relocate_file(winner_path, target_path, repo_root)
    write_survivor(target_path, merged_content)
    remove_file(loser_path, repo_root)

    return Resolution(
        identifier=basename,
        survivor_path=str(target_path),
        deleted_path=str(loser_path),
        resolution=resolution,
        reason=reason,
    )


def repair_work_item_duplicates(tickets_root: str | Path, lifecycle_config_path: str | Path) -> RepairReport:
    """Reduce every twice-held work-item identifier to its one correct copy.

    Idempotent: a basename no longer held by two or more lifecycle folders
    is not touched, so re-running this over an already-repaired collection
    returns an empty ``resolutions`` list and leaves every survivor
    byte-identical.

    Args:
        tickets_root: Path to the ``tickets/`` directory.
        lifecycle_config_path: Path to ``tickets/ticket_lifecycle.json``, the
            source of truth for lifecycle folders, their allowed statuses,
            and which of them are terminal (permanent-archive) folders.

    Returns:
        RepairReport listing one Resolution per identifier actually repaired
        in this call.
    """
    tickets_root = Path(tickets_root)
    lifecycle_config_path = Path(lifecycle_config_path)
    repo_root = tickets_root.parent

    folders = load_lifecycle_folders(lifecycle_config_path)
    if not folders:
        return RepairReport(resolutions=[])

    terminal = terminal_statuses(folders)
    claims = collect_claims(tickets_root, folders)

    resolutions: list[Resolution] = []
    for basename, claimants in sorted(claims.items()):
        if len(claimants) < 2:
            continue
        if len(claimants) > 2:
            print(
                f"{_HOOK_PREFIX} WARNING: {basename} is claimed by {len(claimants)} files; "
                "this repair only handles two-way duplicates (scope is the five named "
                "identifiers) -- skipping rather than guessing a resolution.",
                file=sys.stderr,
            )
            continue
        resolution = _repair_pair(basename, claimants, tickets_root, folders, terminal, repo_root)
        if resolution is not None:
            resolutions.append(resolution)

    return RepairReport(resolutions=resolutions)
