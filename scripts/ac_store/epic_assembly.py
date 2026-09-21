"""
epic_assembly.py — EPIC folder assembly and single-location write enforcement.

MODULE: epic_assembly
GOAL: Copy the generated ticket files into a numbered ``EPIC-<PascalCase>``
      folder, then make that folder the ONLY place each ticket exists — delete
      the loose inbox-root copies and repoint every ``implemented_by``
      back-reference in the AC store at the epic-folder path.
BUSINESS CONTEXT: Implements ACD-1200a-3 (numbered EPIC folder), ACD-1200a-3-i
      (zero-leaf guard fires before any write), ACD-1200a-9 (single-location
      write; implemented_by names the epic-folder path) and ACD-1200a-9-i
      (basename collision overwrites in place with a WARNING, never a renamed
      sibling or a second copy). Extracted from goal_to_epic.py so that file
      can meet the 400-line check_file_size limit.
ARCHITECTURE: Filesystem writes plus targeted line-level YAML edits. Imports
      epic_errors (ZeroLeafError), epic_naming (_to_pascal_case) and
      epic_runtime (shared logger). Deployed flat beside goal_to_epic.py in
      <output_root>/scripts/ac_store/ (see AC_STORE_DEPLOY_MAP in
      scripts/build_phases.py).

AC coverage owned by this module:
    ACD-1200a-3:   EPIC folder assembled with monotonic numeric prefixes.
    ACD-1200a-3-i: zero-leaf condition raises before ANY filesystem write.
    ACD-1200a-9:   each ticket is written only inside the epic folder; no loose
                   inbox-root copy survives; implemented_by names the
                   epic-folder path (with prefix).
    ACD-1200a-9-i: a basename collision inside the epic folder overwrites in
                   place and emits a WARNING; no renamed sibling is minted.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from epic_errors import ZeroLeafError
from epic_naming import _to_pascal_case
from epic_runtime import get_logger

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

    When the target EPIC folder already exists (e.g. from a prior partial run),
    file writes continue inside it.  If an individual destination file already
    exists with the same basename, it is overwritten in place and a WARNING is
    emitted (ACD-1200a-9-i).  No renamed sibling or second copy is ever created.

    Args:
        ticket_paths: Ordered list of existing ticket file paths (strings or
                      Path objects). Must not be empty.
        epic_name: Human-readable name for the EPIC (e.g. ``"validate api inputs"``
                   or ``"ValidateApiInputs"``).  PascalCase conversion is applied
                   automatically and is idempotent — passing an already-PascalCase
                   string returns it unchanged (n_location_rule: 1).
        inbox_dir: Absolute path to the tickets inbox root
                   (e.g. ``tickets/00_inbox``).

    Returns:
        Absolute path to the created EPIC folder.

    Raises:
        ZeroLeafError: When *ticket_paths* is empty.
    """
    _log = get_logger()

    # Zero-leaf guard: must fire before ANY filesystem writes (ACD-1200a-3-i)
    if not ticket_paths:
        raise ZeroLeafError(  # noqa: TRY003
            "No leaf-level ACs found. Decompose the L1s into L2/L3 ACs first."
        )

    pascal = _to_pascal_case(epic_name)
    folder_name = f"EPIC-{pascal}"
    epics_dir = inbox_dir / "epics"
    epic_folder = epics_dir / folder_name

    try:
        epic_folder.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        _log.warning("Cannot create EPIC folder %s: %s", epic_folder, exc)
        raise

    for index, raw_path in enumerate(ticket_paths, start=1):
        source = Path(raw_path)
        prefix = f"{index:02d}_"
        dest_name = prefix + source.name
        dest = epic_folder / dest_name

        if dest.exists():
            _log.warning(
                "Basename collision in EPIC folder: %s already exists — "
                "overwriting in place (ACD-1200a-9-i). No second copy created.",
                dest,
            )

        try:
            shutil.copy2(str(source), str(dest))
        except OSError as exc:
            _log.warning(
                "Cannot write ticket file %s to epic folder: %s", dest, exc
            )
            raise

    return epic_folder.resolve()


# ---------------------------------------------------------------------------
# Single-location write helpers (ACD-1200a-9)
# ---------------------------------------------------------------------------


def _build_loose_to_epic_map(
    ticket_paths: list[str],
    epic_folder: Path,
) -> dict[str, str]:
    """Build a mapping from loose inbox ticket paths to their epic-folder counterparts.

    Mirrors the numeric-prefix logic in :func:`assemble_epic_folder` so that
    after assembly the caller can update ``implemented_by`` and delete the loose
    copies without re-scanning the filesystem.

    Args:
        ticket_paths: Ordered list of ticket paths as written into the loose inbox
                      root (output of :func:`generate_tickets_for_leaves`).
        epic_folder: Absolute path to the assembled EPIC folder.

    Returns:
        Dict mapping each loose ticket path string → the corresponding
        epic-folder path string (absolute), in the same order as *ticket_paths*.
    """
    mapping: dict[str, str] = {}
    for index, raw_path in enumerate(ticket_paths, start=1):
        source = Path(raw_path)
        prefix = f"{index:02d}_"
        dest_name = prefix + source.name
        dest = epic_folder / dest_name
        mapping[raw_path] = str(dest.resolve())
    return mapping


def _remove_loose_inbox_tickets(
    ticket_paths: list[str],
    inbox_dir: Path,
) -> None:
    """Delete loose ticket files from the inbox root after they have been assembled.

    Only deletes files that are direct children of *inbox_dir* (i.e. at the
    inbox root level, not inside any subdirectory). Files that are already
    inside a subfolder — including the epic folder — are never touched.

    Missing files are silently skipped (they may have already been removed by
    a previous run).

    Args:
        ticket_paths: List of ticket file path strings to remove.
        inbox_dir: The tickets inbox root (e.g. ``tickets/00_inbox``). Only
                   files whose resolved parent equals *inbox_dir*.resolve() are
                   eligible for deletion.
    """
    _log = get_logger()
    resolved_inbox = inbox_dir.resolve()

    for raw_path in ticket_paths:
        path = Path(raw_path).resolve()
        if path.parent != resolved_inbox:
            # Not a direct child of inbox root — skip (already in a subfolder)
            continue
        if not path.exists():
            continue
        try:
            path.unlink()
        except OSError as exc:
            _log.warning(
                "Could not remove loose ticket %s: %s", path, exc
            )


def _read_ac_record(yaml_path: Path) -> tuple[str, dict] | None:
    """Read an AC YAML file and return its raw text alongside the parsed mapping.

    Args:
        yaml_path: Path to the candidate AC YAML file.

    Returns:
        tuple[str, dict] | None: The file's text and the parsed top-level
        mapping, or None when the file cannot be read, cannot be parsed, or
        does not parse to a mapping. Read and parse failures are logged at
        WARNING; a non-mapping document is not an error and is not logged.
    """
    _log = get_logger()
    try:
        content = yaml_path.read_text(encoding="utf-8")
    except OSError as exc:
        _log.warning("Cannot read %s for implemented_by update: %s", yaml_path, exc)
        return None

    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        _log.warning("YAML parse error in %s: %s", yaml_path, exc)
        return None

    if not isinstance(data, dict):
        return None
    return content, data


def _swapped_implemented_by(
    implemented_by: list[str],
    old_path: str,
    new_path: str,
) -> list[str]:
    """Return *implemented_by* with *old_path* replaced by *new_path*, deduplicated.

    Pure function — no I/O, so no try/except per Error Handling Policy Rule 4.
    Entries other than *old_path* are preserved in order and are never
    deduplicated against each other; only repeated *old_path* entries collapse
    onto a single *new_path*.

    Args:
        implemented_by: The AC's current implemented_by list.
        old_path: The entry to replace (the loose inbox path).
        new_path: The replacement entry (the epic-folder path).

    Returns:
        list[str]: The updated list.
    """
    updated: list[str] = []
    for entry in implemented_by:
        if entry == old_path:
            if new_path not in updated:
                updated.append(new_path)
        else:
            updated.append(entry)
    return updated


def _splice_implemented_by_block(content: str, new_value_yaml: str) -> str:
    """Replace the ``implemented_by:`` block in *content* with *new_value_yaml*.

    A targeted line-level splice that rewrites only the ``implemented_by:``
    key and the dash-prefixed item lines directly beneath it, leaving every
    other line — including comments and field ordering — byte-identical. Only
    the first ``implemented_by:`` block is replaced.

    Pure function — no I/O, so no try/except per Error Handling Policy Rule 4.

    Args:
        content: The full current text of the AC YAML file.
        new_value_yaml: The rendered replacement block (``implemented_by:``
            plus its items), without a trailing newline.

    Returns:
        str: The updated file text.
    """
    lines = content.splitlines(keepends=True)
    result_lines: list[str] = []
    i = 0
    replaced = False
    while i < len(lines):
        line = lines[i]
        if not replaced and line.startswith("implemented_by:"):
            result_lines.append(new_value_yaml + "\n")
            i += 1
            while i < len(lines) and (
                lines[i].startswith("- ")
                or lines[i].startswith("  - ")
                or lines[i].strip() == "-"
            ):
                i += 1
            replaced = True
        else:
            result_lines.append(line)
            i += 1

    return "".join(result_lines)


def _replace_implemented_by_entry(
    ac_store_root: Path,
    old_path: str,
    new_path: str,
) -> None:
    """Replace *old_path* with *new_path* in the ``implemented_by`` list of any AC YAML.

    Scans *ac_store_root* for AC YAML files that contain *old_path* in their
    ``implemented_by`` list and replaces it with *new_path* using a targeted
    line-level update that preserves all other YAML content.

    This is idempotent: if *new_path* is already present and *old_path* is not,
    the file is not rewritten.

    Args:
        ac_store_root: Root directory of the AC YAML store.
        old_path: The old ``implemented_by`` path to replace (loose inbox path).
        new_path: The replacement path (epic-folder path).
    """
    _log = get_logger()

    for yaml_path in sorted(ac_store_root.rglob("*.yaml")):
        record = _read_ac_record(yaml_path)
        if record is None:
            continue
        content, data = record

        implemented_by: list[str] = data.get("implemented_by") or []
        if not isinstance(implemented_by, list):
            continue
        if old_path not in implemented_by:
            continue

        # Build the updated list: replace old_path with new_path (dedup)
        updated = _swapped_implemented_by(implemented_by, old_path, new_path)

        # Targeted rewrite: replace the implemented_by block only
        new_value_yaml = yaml.dump(
            {"implemented_by": updated},
            default_flow_style=False,
            allow_unicode=True,
        ).strip()

        new_content = _splice_implemented_by_block(content, new_value_yaml)

        try:
            yaml_path.write_text(new_content, encoding="utf-8")
        except OSError as exc:
            _log.warning(
                "Cannot write updated implemented_by to %s: %s", yaml_path, exc
            )


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-22 [EPIC-GoalToEpicBugfixes/01]: Single-location write + correct implemented_by.
  Implements ACD-1200a-9: fixes dual-write bug where each generated ticket was
  written to tickets/00_inbox/<file>.md (loose) AND copied into the epic folder.
  Added _build_loose_to_epic_map(), _remove_loose_inbox_tickets(), and
  _replace_implemented_by_entry(). run() now calls these three helpers after
  assemble_epic_folder() succeeds: (1) builds the loose→epic path mapping,
  (2) updates implemented_by in each source AC YAML from the loose path to the
  epic-folder path (with numeric prefix), (3) removes the loose inbox copies.
- 2026-06-22 [EPIC-GoalToEpicBugfixes/02]: Basename collision resolution.
  Implements ACD-1200a-9-i: when a generated ticket's computed basename already
  exists at the epic-folder path, assemble_epic_folder() overwrites it in place
  rather than raising EpicFolderConflictError or minting a renamed sibling.
  A WARNING log line is emitted for each overwrite so the replacement is
  observable. The epic folder is now created with exist_ok=True so partial
  re-runs converge correctly. EpicFolderConflictError is no longer raised by
  assemble_epic_folder(); run() exception handler updated to catch OSError in
  its place. After the run exactly one ticket file with the computed basename
  exists at the epic-folder path, and implemented_by names that single path
  (consistent with ACD-1200a-9).
- 2026-09-14 12:00 [goal-to-epic-decompose]: Moved here from
  scripts/goal_to_epic.py, which exceeded the 400-line check_file_size limit.
  assemble_epic_folder, _build_loose_to_epic_map and _remove_loose_inbox_tickets
  moved verbatim. Two edits, both behaviour-preserving:
  (1) the deferred logging.getLogger(__name__) calls became
      epic_runtime.get_logger(). That matters more here than elsewhere:
      tests/test_goal_to_epic_basename_collision.py asserts the ACD-1200a-9-i
      collision WARNING via assertLogs("goal_to_epic", ...), so falling back to
      this module's own __name__ would have emitted the record under
      "epic_assembly" and broken that assertion;
  (2) _replace_implemented_by_entry was at cyclomatic 19 — over the threshold
      of 15, and the worst function in the pre-split file. Its body was divided
      into _read_ac_record() (read + parse + mapping guard),
      _swapped_implemented_by() (pure list rebuild) and
      _splice_implemented_by_block() (pure line splice), leaving the outer
      function a scan loop at 6. Every warning message, every `continue` and
      the yaml.dump call are unchanged, so the on-disk result is identical.
  (#TICKETLESS reason=file-size-decomposition-refactor)
====================================================================
"""
