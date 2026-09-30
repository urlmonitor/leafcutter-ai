"""
epic_readiness.py — Read-only readiness classification of leaf ACs.

MODULE: epic_readiness
GOAL: Read the ``readiness`` field of every leaf AC in a generated set and
      split it into approved vs unapproved, so the caller can either take the
      all-approved fast path or hand the result to the interactive gate.
BUSINESS CONTEXT: Implements ACD-1200b-1 and ACD-1200b-1-i. Classification is
      deliberately separated from the gate (epic_readiness_gate) because it is
      strictly read-only and side-effect free: it never prints, never prompts
      and never writes, so it can be called from a dry run or a test without
      any stdin/stdout involvement. Extracted from goal_to_epic.py so that
      file can meet the 400-line check_file_size limit.
ARCHITECTURE: One O(n) store walk builds an AC id → path index; each leaf is
      then read from that index. Imports epic_runtime (shared logger) only,
      which keeps it below epic_readiness_gate in the dependency graph.
      Deployed flat beside goal_to_epic.py (see AC_STORE_DEPLOY_MAP in
      scripts/build_phases.py).

AC coverage owned by this module:
    ACD-1200b-1:   classify_readiness() reads the readiness field and splits
                   approved from unapproved; read-only, <500ms for 100 leaves.
    ACD-1200b-1-i: the all-approved fast path is detectable by an empty
                   ``unapproved`` list, and print_fast_path_message() is the
                   confirmation the caller prints on it.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from epic_runtime import get_logger

# ---------------------------------------------------------------------------
# Store indexing
# ---------------------------------------------------------------------------


def _index_store_by_ac_id(store_root: Path) -> dict[str, Path]:
    """Build an AC id → YAML path index for the whole store in one walk.

    Unreadable or unparseable files are skipped with a WARNING; a failure to
    walk the store at all is logged and yields whatever was indexed so far,
    matching the pre-split behaviour where classification degraded rather than
    aborting.

    Args:
        store_root: Root directory of the AC YAML store.

    Returns:
        dict[str, Path]: Mapping from each AC id found to its YAML file.
    """
    ac_index: dict[str, Path] = {}
    _log = get_logger()
    try:
        for yaml_path in store_root.rglob("*.yaml"):
            try:
                with open(yaml_path, encoding="utf-8") as fh:
                    data = yaml.safe_load(fh)
            except (yaml.YAMLError, OSError) as exc:
                _log.warning("Skipping unreadable YAML %s: %s", yaml_path, exc)
                continue
            else:
                if isinstance(data, dict) and "id" in data:
                    ac_index[data["id"]] = yaml_path
    except OSError as exc:
        _log.warning("Error scanning AC store %s: %s", store_root, exc)
    return ac_index


def _read_readiness(yaml_path: Path) -> str:
    """Read the ``readiness`` field from one AC YAML file.

    A read or parse failure here is deliberately NOT logged: the store walk in
    :func:`_index_store_by_ac_id` has already warned about any file it could
    not read, and warning twice for the same file would double-report.

    Args:
        yaml_path: Path to the AC YAML file.

    Returns:
        str: The readiness value, or ``"unknown"`` when the file cannot be
        read or parsed, does not parse to a mapping, or has no readiness field.
    """
    try:
        with open(yaml_path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except (yaml.YAMLError, OSError):
        return "unknown"
    if isinstance(data, dict):
        return data.get("readiness", "unknown")
    return "unknown"


# ---------------------------------------------------------------------------
# Classification (ACD-1200b-1)
# ---------------------------------------------------------------------------


def classify_readiness(
    leaf_ids: list[str],
    store_root: Path,
) -> dict:
    """Read the readiness field from each leaf AC YAML and classify into approved vs unapproved.

    This function is read-only: it never writes any files. It completes in
    <500ms for up to 100 leaf ACs (ACD-1200b-1).

    The all-approved fast-path is detectable by the caller by checking
    whether ``result["unapproved"]`` is empty (ACD-1200b-1-i). This function
    does not print or prompt — it returns a plain dict so the caller can decide.

    Args:
        leaf_ids: Ordered list of leaf AC IDs to classify.
        store_root: Root directory of the AC YAML store.

    Returns:
        A dict with two keys:
            ``approved``: list[str] — IDs where readiness == "approved".
            ``unapproved``: list[dict] — entries for IDs where readiness
                != "approved"; each entry has ``{"id": str, "readiness": str}``.
    """
    approved: list[str] = []
    unapproved: list[dict] = []

    # Build an index from AC id → YAML path for O(n) look-up.
    ac_index = _index_store_by_ac_id(store_root)

    for ac_id in leaf_ids:
        readiness = "unknown"
        if ac_id in ac_index:
            readiness = _read_readiness(ac_index[ac_id])

        if readiness == "approved":
            approved.append(ac_id)
        else:
            unapproved.append({"id": ac_id, "readiness": readiness})

    return {"approved": approved, "unapproved": unapproved}


def print_fast_path_message(n: int) -> None:
    """Print the all-approved fast-path confirmation message.

    Called when every leaf AC is already approved (ACD-1200b-1-i). The message
    confirms to the user that no prompt is needed and epic generation proceeds.

    Args:
        n: Total number of leaf ACs (all approved).
    """
    print(f"All {n} leaf ACs are approved. Generating epic...")


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-14 12:00 [goal-to-epic-decompose]: Extracted from
  scripts/goal_to_epic.py, which exceeded the 400-line check_file_size limit.
  print_fast_path_message moved verbatim. Two edits, both behaviour-preserving:
  (1) the deferred `import logging; logging.getLogger(__name__)` calls became
      epic_runtime.get_logger(), keeping the pre-split logger name
      "goal_to_epic";
  (2) classify_readiness was at cyclomatic 13. Its store walk became
      _index_store_by_ac_id() and its per-leaf read became _read_readiness(),
      dropping it to 4. The "unknown" default, the WARNING on an unreadable
      file during the walk, and the deliberately SILENT fallback when the
      per-leaf re-read fails are all preserved exactly — that asymmetry is
      original behaviour, not an oversight, and _read_readiness's docstring now
      records why.

  The interactive gate (readiness_gate_prompt, _route_answer,
  _gate_select_approved_ids, dispatch_it_po_v3 and friends) is NOT here — it
  lives in epic_readiness_gate.py. Splitting on the read-only/interactive seam
  was forced by the 400-line limit (the combined module came to 455) and is the
  natural cut: everything in this file is side-effect free apart from
  print_fast_path_message, so it can be called from a dry run or a test with no
  stdin involved at all.

  Pre-split history lives in goal_to_epic.py's DECISION HISTORY block (the
  2026-06-05 EPIC-GoalToEpic/02 entry).
  (#TICKETLESS reason=file-size-decomposition-refactor)
====================================================================
"""
