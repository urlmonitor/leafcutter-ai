"""
epic_ac_store.py — AC YAML store lookups and target_epic stamping.

MODULE: epic_ac_store
GOAL: Read AC records out of the YAML store (title lookup, path lookup,
      target_epic lookup) and write the ``target_epic`` back-reference into the
      ACs an epic includes, using targeted line-level edits that preserve
      comments and field ordering.
BUSINESS CONTEXT: Implements ACD-1200d (target_epic stamping). Extracted from
      goal_to_epic.py so that file can meet the 400-line check_file_size limit.
ARCHITECTURE: Read/write layer over the AC YAML store. Imports only
      epic_runtime (shared logger); no other sibling dependency, so it sits
      just above the foundation layer. Deployed flat beside goal_to_epic.py in
      <output_root>/scripts/ac_store/ (see AC_STORE_DEPLOY_MAP in
      scripts/build_phases.py).

AC coverage owned by this module:
    ACD-1200d-1:   stamp_target_epic() writes target_epic via a targeted
                   line-level edit (never yaml.dump), and is idempotent — the
                   same value is a no-op with no file rewrite.
    ACD-1200d-1-i: a differing existing target_epic triggers a per-AC
                   overwrite/skip prompt rather than a silent overwrite.
    ACD-1200d-2:   exclusion guard — only ACs named in included_ids are ever
                   modified.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from epic_runtime import get_logger

# ---------------------------------------------------------------------------
# AC lookup helpers
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


def _find_ac_yaml_path(ac_id: str, store_root: Path) -> Path | None:
    """Find the YAML file for the given AC id in the store.

    Scans *store_root* recursively for a YAML file whose top-level ``id``
    field matches *ac_id*. Returns None if not found.

    Args:
        ac_id: The AC identifier to look up.
        store_root: Root directory of the AC YAML store.

    Returns:
        Path to the matching YAML file, or None if not found.
    """
    for yaml_path in sorted(store_root.rglob("*.yaml")):
        try:
            with open(yaml_path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except (yaml.YAMLError, OSError):
            continue
        else:
            if isinstance(data, dict) and data.get("id") == ac_id:
                return yaml_path
    return None


def _read_target_epic_from_file(yaml_path: Path) -> str | None:
    """Read the target_epic field from an AC YAML file.

    Args:
        yaml_path: Path to the AC YAML file.

    Returns:
        The target_epic value as a string, or None if not set.
    """
    try:
        with open(yaml_path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except (yaml.YAMLError, OSError):
        return None
    else:
        if isinstance(data, dict):
            return data.get("target_epic")
        return None


def _write_target_epic_field(yaml_path: Path, epic_name: str) -> None:
    """Write the target_epic field into an AC YAML file using targeted line-level update.

    This function uses a targeted field update approach (not yaml.dump) to
    preserve all other fields, comments, and field ordering in the YAML file.

    Strategy:
    - If the file already contains a ``target_epic:`` line, replace it.
    - Otherwise, append ``target_epic: <epic_name>`` as a new line.

    Args:
        yaml_path: Path to the AC YAML file to update.
        epic_name: The epic name to write as the target_epic value.
    """
    try:
        content = yaml_path.read_text(encoding="utf-8")
    except OSError as exc:
        get_logger().warning(
            "Cannot read %s for targeted field update: %s", yaml_path, exc
        )
        raise

    target_epic_line = f"target_epic: {epic_name}\n"
    target_epic_pattern = re.compile(r"^target_epic:.*$", re.MULTILINE)

    if target_epic_pattern.search(content):
        # Replace the existing target_epic line with the new value
        updated = target_epic_pattern.sub(f"target_epic: {epic_name}", content)
    else:
        # Append as a new line at the end of the file
        updated = content.rstrip("\n") + "\n" + target_epic_line

    try:
        yaml_path.write_text(updated, encoding="utf-8")
    except OSError as exc:
        get_logger().warning(
            "Cannot write targeted field update to %s: %s", yaml_path, exc
        )
        raise


# ---------------------------------------------------------------------------
# target_epic stamping (ACD-1200d)
# ---------------------------------------------------------------------------


def _resolve_target_epic_conflict(
    ac_id: str,
    existing_target_epic: str,
    epic_name: str,
) -> bool:
    """Prompt the user about an AC that already belongs to a different epic.

    Implements the ACD-1200d-1-i conflict prompt. Any answer other than an
    exact ``yes`` (case-insensitive, whitespace-stripped) retains the original
    value, so an accidental keystroke never silently re-homes an AC.

    Args:
        ac_id: The AC being stamped, named in the prompt.
        existing_target_epic: The target_epic value already on disk.
        epic_name: The epic name the caller wants to write instead.

    Returns:
        bool: True when the user answered "yes" and the overwrite should
        proceed; False to leave the existing value untouched.
    """
    prompt = (
        f"{ac_id} already belongs to {existing_target_epic}. "
        f"Overwrite with {epic_name}? (yes / skip): "
    )
    answer = input(prompt).strip().lower()
    return answer == "yes"


def stamp_target_epic(
    included_ids: list[str],
    epic_name: str,
    store_root: Path,
) -> None:
    """Stamp all included AC YAML files with the target_epic field.

    For each AC ID in *included_ids*:
    - Reads the current YAML from disk.
    - If ``target_epic`` is absent: writes ``target_epic: <epic_name>`` using
      a targeted field update (not full yaml.dump).
    - If ``target_epic`` matches *epic_name*: skips the file (idempotent no-op).
    - If ``target_epic`` differs from *epic_name*: prompts the user per-AC
      with "ACD-xxx already belongs to EPIC-OldName. Overwrite with
      EPIC-NewName? (yes / skip)" and routes on the answer.

    ACs whose IDs do NOT appear in *included_ids* are never touched (exclusion
    guard — ACD-1200d-2). ACs not found in the store are silently skipped.

    Args:
        included_ids: Ordered list of AC IDs to stamp. Only these IDs are
                      eligible for modification.
        epic_name: The EPIC folder name to write as the target_epic value
                   (case-exact — e.g. "EPIC-ValidateApiInputs").
        store_root: Root directory of the AC YAML store.

    Returns:
        None. All effects are on-disk writes to the AC YAML files.

    Raises:
        OSError: Propagated if a YAML file cannot be read or written after
                 the conflict resolution decision has been made.
    """
    for ac_id in included_ids:
        yaml_path = _find_ac_yaml_path(ac_id, store_root)
        if yaml_path is None:
            # AC not found in store — silently skip (may be outside the store)
            get_logger().warning(
                "AC %r not found in store %s — skipping stamp", ac_id, store_root
            )
            continue

        existing_target_epic = _read_target_epic_from_file(yaml_path)

        if existing_target_epic is None:
            # No existing target_epic — write unconditionally
            _write_target_epic_field(yaml_path, epic_name)

        elif existing_target_epic == epic_name:
            # Idempotent re-run — same value already present, no-op
            continue

        elif _resolve_target_epic_conflict(ac_id, existing_target_epic, epic_name):
            # Conflict: existing target_epic differs and the user chose to overwrite.
            # "skip" or any other input → retain original value (no write).
            _write_target_epic_field(yaml_path, epic_name)


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-05 10:35 [EPIC-GoalToEpic/04]: target_epic stamping. (#EPIC-GoalToEpic/04)
  Implements ACD-1200d-1: stamp_target_epic(included_ids, epic_name, store_root)
  writes target_epic field to each included AC YAML via targeted line-level edit
  (not yaml.dump) to preserve comments and field ordering. Idempotent: same
  value is a no-op (no file rewrite). Case-exact match to epic_name. Implements
  ACD-1200d-1-i: conflict detection when existing target_epic differs — per-AC
  prompt "ACD-xxx already belongs to EPIC-OldName. Overwrite with EPIC-NewName?
  (yes / skip)" routes on user answer. Implements ACD-1200d-2: exclusion guard
  — only ACs in included_ids are ever touched; all other AC files remain unread
  and unmodified. Helper functions: _find_ac_yaml_path(), _read_target_epic_from_file(),
  _write_target_epic_field() (regex-based targeted replace or append).
- 2026-09-14 12:00 [goal-to-epic-decompose]: Moved here from
  scripts/goal_to_epic.py, which exceeded the 400-line check_file_size limit.
  _get_ac_title, _find_ac_yaml_path, _read_target_epic_from_file and
  _write_target_epic_field moved verbatim. Two edits, both behaviour-preserving:
  (1) the deferred `import logging; logging.getLogger(__name__)` calls became
  epic_runtime.get_logger() so records keep the pre-split logger name
  "goal_to_epic"; (2) stamp_target_epic's inline conflict prompt was extracted
  into _resolve_target_epic_conflict() and the trailing `else:` became an
  `elif <helper>` — the prompt text, the exact-"yes" comparison, and the
  retain-on-anything-else default are all unchanged, so ACD-1200d-1-i behaves
  identically. (#TICKETLESS reason=file-size-decomposition-refactor)
====================================================================
"""
