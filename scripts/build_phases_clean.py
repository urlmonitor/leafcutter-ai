"""
MODULE: build_phases_clean
GOAL: Remove stale, no-longer-templated artifacts from a target project's
    managed `.claude/` subdirectories during clean-mode builds, but only
    artifacts this build has positive, recomputed evidence it once produced
    itself (BP-1500g-1 / ADR-041).
BUSINESS CONTEXT: build_phases.py is grandfathered many times over the
    400-content-line check-file-size limit, and the GE-127b-1 ratchet refuses
    any change that leaves an already-oversized file longer than it was.
    Carrying this small, self-contained clean-mode phase out here restores
    headroom with no behaviour change, exactly as build_phases_knowledge.py
    and build_phases_product_truth.py did for their own phase groups.
ARCHITECTURE: One public function, ``clean_stale_artifacts``, plus the
    ``_MANAGED_ARTIFACT_DIRS`` constant it reads, re-exported from
    build_phases.py so every existing caller keeps working unchanged. Unlike
    the other extracted sibling modules, this one has no dependency on
    build_phases's private write/deploy helpers or shared module state for
    the artifact-scan itself, so no late `import build_phases as _bp` is
    needed for that part. It DOES need a logger identity for a real removal
    failure (an OSError from ``unlink``/``rmtree``, which must be logged and
    re-raised per the project's error-handling policy, never swallowed) --
    that late `import build_phases as _bp` inside the function body reaches
    `_bp._log`, matching every other sibling module extracted by the same
    BP-size split, rather than declaring a second logger under a different
    name for the one call site that needs it.

    The on-disk provenance ledger (``_CLEAN_LEDGER_FILENAME`` /
    ``_load_clean_ledger`` / ``_save_clean_ledger``) lives in
    build_ownership.py, imported here directly (no circularity: build_ownership
    does not import this module). An item is removed only when BOTH (1) its
    name is absent from the CURRENT source manifest for its artifact type,
    AND (2) its name was PREVIOUSLY recorded in an earlier ``--clean`` run's
    manifest -- an item the ledger has never seen is kept and reported with a
    WARNING (ADR-041 Consequences/Negative), never silently removed just
    because a name is unrecognised today. This is what let KI-BP-009 survive
    months of green builds undetected.
"""

from __future__ import annotations

from pathlib import Path

from build_ownership import _CLEAN_LEDGER_FILENAME, _load_clean_ledger, _save_clean_ledger

#: Artifact subdirectories managed by build.py that are eligible for clean-mode
#: removal. Only files/directories within these subdirectories are ever removed
#: by clean_stale_artifacts(). Paths outside this list are never touched.
_MANAGED_ARTIFACT_DIRS = {
    "agents": "agents",
    "skills": "skills",
    "hooks": "hooks",
    "workflows": "workflows",
}


def clean_stale_artifacts(
    target_dir: Path,
    source_manifests: dict[str, set[str]],
    dry_run: bool = False,
    output_root: Path | None = None,
) -> int:
    """Remove compiled artifacts in the target directory that have no matching source template.

    Scans the managed artifact subdirectories (``agents/``, ``skills/``,
    ``hooks/``, ``workflows``) inside ``<target_dir>/.claude/``. An item is
    removed only when BOTH: (1) its name is absent from the CURRENT
    ``source_manifests`` entry for its artifact type, AND (2) its name was
    PREVIOUSLY recorded in an earlier ``--clean`` run's manifest (the
    on-disk provenance ledger this function maintains under *output_root*).
    An item whose name the ledger has never seen is never removed — non-
    attribution is keep (BP-1500g-1): the build only removes what it has
    positive, recomputed evidence it once produced itself, never merely
    because a name is unrecognised today.

    Only removes files/directories under the known managed subdirectories.
    Files elsewhere in ``.claude/`` or the broader target directory are
    never touched.

    ADR-041 Consequences/Negative: a kept-but-unattributable item (name not
    in the current manifest AND not in the ledger) MUST be reported, not
    merely spared -- a bare ``continue`` here was silent, which is exactly
    what let KI-BP-009 survive months of green builds undetected, including
    on the very first ``--clean`` after an upgrade (ledger empty by
    construction, every unmatched item takes this path). Prints a WARNING
    naming the item instead.

    Args:
        target_dir: Root directory of the target project. The managed artifact
            subdirectories are resolved relative to ``<target_dir>/.claude/``.
        source_manifests: Mapping from artifact type to the set of expected
            artifact names. Accepted keys: ``"agents"``, ``"skills"``, ``"hooks"``.
            Each value is a set of file/directory **base names** (e.g.
            ``{"my-agent.md", "other-agent.md"}``). An absent key is treated
            the same as an empty set — all items of that type are considered
            unrecognised (and therefore never removed unless the ledger has
            seen them before).
        dry_run: When True, prints what would be removed (identically to a
            real run) but removes nothing and does not update the ledger.
        output_root: Directory the provenance ledger is stored under.
            Defaults to ``target_dir / ".leafcutter"`` when omitted.

    Returns:
        Count of artifacts removed (0 when nothing is stale), or that would
        be removed under ``dry_run``.
    """
    import shutil as _shutil

    import build_phases as _bp

    claude_dir = target_dir / ".claude"
    if output_root is None:
        output_root = target_dir / ".leafcutter"
    ledger_path = output_root / _CLEAN_LEDGER_FILENAME
    ledger = _load_clean_ledger(ledger_path)
    updated_ledger = {k: set(v) for k, v in ledger.items()}

    removed = 0

    for artifact_type, subdir_name in _MANAGED_ARTIFACT_DIRS.items():
        expected_names: set[str] = source_manifests.get(artifact_type, set())
        known_before: set[str] = ledger.get(artifact_type, set())
        updated_ledger[artifact_type] = updated_ledger.get(artifact_type, set()) | expected_names

        managed_dir = claude_dir / subdir_name
        if not managed_dir.exists():
            continue

        for item in sorted(managed_dir.iterdir()):
            if item.name in expected_names:
                continue
            if item.name not in known_before:
                print(f"WARNING: kept unattributable item (unrecorded, not removed): {item}")
                continue
            print(f"Removing stale artifact: {item}")
            removed += 1
            if dry_run:
                continue
            try:
                if item.is_dir() and not item.is_symlink():
                    _shutil.rmtree(item)
                else:
                    item.unlink()
            except OSError as exc:
                _bp._log.warning("Failed to remove stale artifact %s: %s", item, exc)
                raise

    if not dry_run:
        _save_clean_ledger(ledger_path, updated_ledger)

    if removed == 0:
        print("No stale artifacts found")

    return removed


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-09-14 [python-coder/bp-size-split]: Moved _MANAGED_ARTIFACT_DIRS and
#   clean_stale_artifacts verbatim from build_phases.py into this new sibling
#   module to bring build_phases.py under the 400-counted-line
#   check-file-size limit. Re-exported from build_phases.py so build.py and
#   every test import keeps working. (#refactor/build-phases-size-limit)
# - 2026-09-14 [python-coder/KI-BP-010]: Fixed _MANAGED_ARTIFACT_DIRS["workflows"]
#   (".claude/workflows" -> "workflows", joined onto claude_dir which is already
#   target_dir/".claude"; the old value built a never-existent
#   ".claude/.claude/workflows" so exists() skipped the sweep every clean run --
#   orphan survived pre-fix, removed=1 after; path-join only, promoting the sweep
#   onto the default build path stays BP-1500b-1's scope). Reapplied here after the
#   bp-size-split refactor moved this constant out from under the original fix
#   (#KI-BP-010, covered_by: BP-1500b-1).
# - 2026-09-21 [python-coder/merge origin/main into fast-lane/bp-1500g-1]:
#   Landed BP-1500g-1-i's on-disk provenance ledger, dry_run/output_root
#   params, and the ADR-041 Consequences/Negative kept-unattributable WARNING
#   into this module (the merge's own facade had already moved
#   clean_stale_artifacts here before BP-1500g-1-i's ledger work started on
#   fast-lane/bp-1500g-1). Ledger helpers imported from build_ownership.py,
#   where fast-lane/bp-1500g-1 had already relocated them. Also took
#   origin/main's ``_MANAGED_ARTIFACT_DIRS["workflows"]`` fix ("workflows",
#   not ".claude/workflows") over fast-lane/bp-1500g-1's stale pre-KI-BP-010
#   value -- that branch never touched this key, so origin/main's fix is not
#   a competing change, just one this branch had not yet merged in.
#   (#BP-1500g-1/merge-origin-main)
# ===========================================================================
