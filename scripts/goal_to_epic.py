#!/usr/bin/env python3
"""
goal_to_epic.py — Batch orchestrator: goal AC → EPIC folder of tickets.

MODULE: goal_to_epic
GOAL: Walk the AC tree from a goal-level AC, collect all leaf ACs, generate
      one ticket per leaf via generate_ticket_from_ac.py, and assemble the
      results into a numbered EPIC folder under tickets/00_inbox/epics/.
BUSINESS CONTEXT: Implements ACD-1200a (goal-to-epic pipeline). Enables
      /build-feature to accept a goal-level AC id and produce a fully
      populated EPIC folder without manual assembly.
ARCHITECTURE: Standalone CLI script. Delegates single-ticket generation to
      generate_ticket_from_ac.py (via subprocess). Tree traversal via
      traverse_ac_tree() from scan_ac_store.py. Assembles the EPIC folder
      with monotonically increasing numeric prefixes derived from traversal
      order.

Usage:
    python3 scripts/goal_to_epic.py --ac <ac_id> [--store-root <path>]
                                    [--inbox-dir <path>] [--dry-run]

Exit codes:
    0  EPIC folder created successfully (or --dry-run printed the plan).
    1  AC not found, zero-leaf condition, I/O error, or conflict.

ACD-1200a-1: traverse_ac_tree returns only leaf ACs.
ACD-1200a-1-i: L1-scoped traversal excludes sibling branches.
ACD-1200a-2: generate_ticket_from_ac.py called once per leaf.
ACD-1200a-3: EPIC folder assembled with numeric prefixes.
ACD-1200a-3-i: Zero-leaf condition exits non-zero, no files written.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_STORE_ROOT = "docs/acceptance-criteria"
_DEFAULT_INBOX_DIR = "tickets/00_inbox"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ZeroLeafError(ValueError):
    """Raised when the target AC tree has no leaf-level ACs beneath it.

    This condition means the goal AC has only composite L1 children and none
    have been decomposed to L2/L3 leaves. The caller must decompose the L1s
    before running goal_to_epic.
    """


class EpicFolderConflictError(FileExistsError):
    """Raised when the EPIC folder already exists and would be overwritten."""


# ---------------------------------------------------------------------------
# Worktree root detection
# ---------------------------------------------------------------------------


def _find_worktree_root(start: Path) -> Path:
    """Walk up from *start* until a directory containing a .git file/dir is found.

    Args:
        start: Starting path for the upward search (typically the script location).

    Returns:
        The worktree root path.

    Raises:
        FileNotFoundError: When no .git marker is found before the filesystem root.
    """
    current = start.resolve()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent
    raise FileNotFoundError(  # noqa: TRY003
        f"Could not locate worktree root from {start}"
    )


# ---------------------------------------------------------------------------
# PascalCase conversion
# ---------------------------------------------------------------------------


def _to_pascal_case(title: str) -> str:
    """Convert a human-readable title string to PascalCase.

    Splits on spaces, hyphens, and underscores. Capitalises the first
    character of each word and joins without separators.

    Args:
        title: The AC title string (e.g. "validate api inputs").

    Returns:
        PascalCase string (e.g. "ValidateApiInputs").
    """
    words = re.split(r"[\s\-_]+", title.strip())
    return "".join(word.capitalize() for word in words if word)


# ---------------------------------------------------------------------------
# AC title lookup
# ---------------------------------------------------------------------------


def _get_ac_title(ac_id: str, ac_store_root: Path) -> str:
    """Return the title of the AC with *ac_id*, or fall back to *ac_id* itself.

    Args:
        ac_id: The AC id to look up.
        ac_store_root: Root directory of the AC YAML store.

    Returns:
        The title string from the YAML, or *ac_id* as a fallback.
    """
    for yaml_path in sorted(ac_store_root.rglob("*.yaml")):
        try:
            with open(yaml_path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except (yaml.YAMLError, OSError):
            continue
        else:
            if isinstance(data, dict) and data.get("id") == ac_id:
                return data.get("title") or ac_id
    return ac_id


# ---------------------------------------------------------------------------
# Single-ticket generation (subprocess delegation)
# ---------------------------------------------------------------------------


def _call_generate_ticket_from_ac(
    ac_id: str,
    ac_root: Path,
    tickets_root: Path,
) -> str:
    """Invoke generate_ticket_from_ac.py for *ac_id* and return the ticket path.

    The function calls the script as a subprocess so that the ticket
    generation logic stays in its canonical home and is not duplicated here.
    The generated ticket path is read from the script's stdout line
    (``Written: <path>``).

    Args:
        ac_id: The leaf AC id to generate a ticket for.
        ac_root: Root directory of the AC YAML store.
        tickets_root: Root directory where tickets are written.

    Returns:
        Absolute path to the generated ticket file.

    Raises:
        subprocess.CalledProcessError: When the script exits non-zero.
        RuntimeError: When the script exits 0 but emits no ``Written:`` line.
    """
    script_path = Path(__file__).parent / "ac_store" / "generate_ticket_from_ac.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--ac",
            ac_id,
            "--ac-root",
            str(ac_root),
            "--tickets-root",
            str(tickets_root),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    for line in result.stdout.splitlines():
        if line.startswith("Written:"):
            return line[len("Written:"):].strip()
    raise RuntimeError(  # noqa: TRY003
        f"generate_ticket_from_ac.py exited 0 for AC {ac_id!r} "
        f"but emitted no 'Written:' line. stdout: {result.stdout!r}"
    )


# ---------------------------------------------------------------------------
# Batch ticket generation (ACD-1200a-2)
# ---------------------------------------------------------------------------


def generate_tickets_for_leaves(
    leaf_ids: list[str],
    ac_store_root: Path,
    tickets_root: Path,
) -> list[str]:
    """Generate one ticket per leaf AC and return the list of ticket paths.

    Calls :func:`_call_generate_ticket_from_ac` once per entry in *leaf_ids*,
    in order. The returned list preserves the same order as *leaf_ids*.

    Args:
        leaf_ids: Ordered list of leaf AC ids to generate tickets for.
        ac_store_root: Root directory of the AC YAML store.
        tickets_root: Root directory where individual tickets are written before
                      being assembled into the EPIC folder.

    Returns:
        Ordered list of absolute ticket file path strings — one per leaf AC.

    Raises:
        subprocess.CalledProcessError: Propagated from
            :func:`_call_generate_ticket_from_ac` when a leaf ticket cannot be
            generated.
    """
    ticket_paths: list[str] = []
    for leaf_id in leaf_ids:
        ticket_path = _call_generate_ticket_from_ac(leaf_id, ac_store_root, tickets_root)
        ticket_paths.append(ticket_path)
    return ticket_paths


# ---------------------------------------------------------------------------
# EPIC folder assembly (ACD-1200a-3)
# ---------------------------------------------------------------------------


def assemble_epic_folder(
    ticket_paths: list[Path | str],
    epic_name: str,
    inbox_dir: Path,
) -> Path:
    """Assemble ticket files into a numbered EPIC folder.

    Creates ``<inbox_dir>/epics/EPIC-<PascalCase>`` and places each ticket
    file inside it with a monotonically increasing numeric prefix
    (``01_<stem>.md``, ``02_<stem>.md``, ...). The order of the prefixes
    mirrors the order of *ticket_paths*.

    Raises :class:`ZeroLeafError` when *ticket_paths* is empty — this
    guard must fire before any filesystem writes (ACD-1200a-3-i).

    Raises :class:`EpicFolderConflictError` when the target EPIC folder
    already exists, to prevent silent overwrites.

    Args:
        ticket_paths: Ordered list of existing ticket file paths (strings or
                      Path objects). Must not be empty.
        epic_name: Human-readable name for the EPIC (e.g. "validate api inputs"
                   or "ValidateApiInputs"). PascalCase conversion is applied
                   automatically.
        inbox_dir: Absolute path to the tickets inbox root
                   (e.g. ``tickets/00_inbox``).

    Returns:
        Absolute path to the created EPIC folder.

    Raises:
        ZeroLeafError: When *ticket_paths* is empty.
        EpicFolderConflictError: When the EPIC folder already exists.
    """
    # Zero-leaf guard: must fire before ANY filesystem writes (ACD-1200a-3-i)
    if not ticket_paths:
        raise ZeroLeafError(  # noqa: TRY003
            "No leaf-level ACs found. Decompose the L1s into L2/L3 ACs first."
        )

    pascal = _to_pascal_case(epic_name)
    folder_name = f"EPIC-{pascal}"
    epics_dir = inbox_dir / "epics"
    epic_folder = epics_dir / folder_name

    if epic_folder.exists():
        raise EpicFolderConflictError(  # noqa: TRY003
            f"EPIC folder already exists and would conflict: {epic_folder}. "
            "Delete or rename the existing folder before re-running."
        )

    epic_folder.mkdir(parents=True, exist_ok=False)

    for index, raw_path in enumerate(ticket_paths, start=1):
        source = Path(raw_path)
        prefix = f"{index:02d}_"
        dest_name = prefix + source.name
        dest = epic_folder / dest_name
        shutil.copy2(str(source), str(dest))

    return epic_folder.resolve()


# ---------------------------------------------------------------------------
# Orchestration entry point
# ---------------------------------------------------------------------------


def run(
    ac_id: str,
    ac_store_root: Path,
    inbox_dir: Path,
    dry_run: bool = False,
) -> Path:
    """Full orchestration: traverse → generate tickets → assemble EPIC folder.

    1. Calls :func:`~scripts.ac_store.scan_ac_store.traverse_ac_tree` on
       *ac_id* to collect leaf AC ids.
    2. Raises :class:`ZeroLeafError` (via :func:`assemble_epic_folder`) when
       no leaves are found — exits non-zero at the CLI layer.
    3. Calls :func:`generate_tickets_for_leaves` once per leaf.
    4. Calls :func:`assemble_epic_folder` to build the numbered EPIC folder.

    Args:
        ac_id: The goal or L1 AC id to start traversal from.
        ac_store_root: Root directory of the AC YAML store.
        inbox_dir: Absolute path to the tickets inbox root.
        dry_run: When True, print the plan and return without writing files.

    Returns:
        Absolute path to the created EPIC folder (or a placeholder in dry-run).

    Raises:
        SystemExit: With code 1 on zero-leaf condition or other errors.
    """
    # Import traverse_ac_tree here to keep the top-level import surface small
    # and to allow this module to be imported even if scan_ac_store is not on
    # sys.path at module load time (e.g. in tests that patch the function).
    _scripts_dir = Path(__file__).parent / "ac_store"
    if str(_scripts_dir) not in sys.path:
        sys.path.insert(0, str(_scripts_dir))

    from scan_ac_store import traverse_ac_tree  # noqa: PLC0415

    leaf_ids = traverse_ac_tree(ac_id, ac_store_root)

    if not leaf_ids:
        print(
            f"No leaf-level ACs found beneath {ac_id}. "
            "Decompose the L1s into L2/L3 ACs first.",
            file=sys.stderr,
        )
        sys.exit(1)

    ac_title = _get_ac_title(ac_id, ac_store_root)
    epic_name = _to_pascal_case(ac_title)

    if dry_run:
        print(f"Dry-run: would create EPIC-{epic_name} with {len(leaf_ids)} ticket(s):")
        for leaf_id in leaf_ids:
            print(f"  {leaf_id}")
        # Return a placeholder path — no files written
        return (inbox_dir / "epics" / f"EPIC-{epic_name}").resolve()

    # Tickets root: write individual tickets to inbox before assembling
    tickets_root = inbox_dir

    try:
        ticket_paths = generate_tickets_for_leaves(leaf_ids, ac_store_root, tickets_root)
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: ticket generation failed: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        epic_folder = assemble_epic_folder(
            ticket_paths,
            epic_name,
            inbox_dir,
        )
    except (ZeroLeafError, EpicFolderConflictError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"EPIC folder created: {epic_folder}")
    return epic_folder


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Walk the AC tree from a goal AC, generate one ticket per leaf AC, "
            "and assemble the results into a numbered EPIC folder."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--ac",
        required=True,
        dest="ac_id",
        help="Goal or L1 AC id to start tree traversal from.",
    )
    parser.add_argument(
        "--store-root",
        dest="store_root",
        default=None,
        help=f"Root directory of the AC YAML store (default: {_DEFAULT_STORE_ROOT} relative to worktree).",
    )
    parser.add_argument(
        "--inbox-dir",
        dest="inbox_dir",
        default=None,
        help=f"Tickets inbox root directory (default: {_DEFAULT_INBOX_DIR} relative to worktree).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Print the plan without writing any files.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for goal_to_epic.py.

    Args:
        argv: Command-line arguments (default: sys.argv[1:]).

    Returns:
        Exit code: 0 on success, 1 on error.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        worktree = _find_worktree_root(Path(__file__))
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    ac_store_root = Path(args.store_root) if args.store_root else worktree / _DEFAULT_STORE_ROOT
    inbox_dir = Path(args.inbox_dir) if args.inbox_dir else worktree / _DEFAULT_INBOX_DIR

    if not ac_store_root.exists():
        print(f"ERROR: AC store root not found: {ac_store_root}", file=sys.stderr)
        return 1

    run(
        ac_id=args.ac_id,
        ac_store_root=ac_store_root,
        inbox_dir=inbox_dir,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-05 [EPIC-GoalToEpic/01]: Initial implementation.
  Implements ACD-1200a: tree traversal via traverse_ac_tree() from
  scan_ac_store.py, batch ticket generation via subprocess calls to
  generate_ticket_from_ac.py, and EPIC folder assembly with 01_/02_/...
  numeric prefixes. ZeroLeafError raised before any filesystem writes
  (ACD-1200a-3-i). EpicFolderConflictError raised when the target EPIC
  folder already exists. PascalCase conversion via _to_pascal_case().
====================================================================
"""
