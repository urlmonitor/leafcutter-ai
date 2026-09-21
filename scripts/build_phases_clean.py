"""
MODULE: build_phases_clean
GOAL: Remove stale, no-longer-templated artifacts from a target project's
    managed `.claude/` subdirectories during clean-mode builds.
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
    build_phases's private write/deploy helpers or shared module state — it
    only compares on-disk artifact names against a caller-supplied manifest
    and removes what is not named, so no late `import build_phases as _bp`
    is needed here.
"""

from __future__ import annotations

from pathlib import Path

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
) -> int:
    """Remove compiled artifacts in the target directory that have no matching source template.

    Scans the three managed artifact subdirectories (``agents/``, ``skills/``,
    ``hooks/``) inside ``<target_dir>/.claude/``. For each artifact found on
    disk, checks whether its name appears in the corresponding set in
    ``source_manifests``. Anything NOT in the manifest is considered stale and
    is removed.

    Only removes files/directories under the known managed subdirectories
    (``.claude/agents/``, ``.claude/skills/``, ``.claude/hooks/``). Files
    elsewhere in ``.claude/`` or the broader target directory are never touched.

    Args:
        target_dir: Root directory of the target project. The managed artifact
            subdirectories are resolved relative to ``<target_dir>/.claude/``.
        source_manifests: Mapping from artifact type to the set of expected
            artifact names. Accepted keys: ``"agents"``, ``"skills"``, ``"hooks"``.
            Each value is a set of file/directory **base names** (e.g.
            ``{"my-agent.md", "other-agent.md"}``). An absent key is treated
            the same as an empty set — all items of that type are considered
            stale.

    Returns:
        Count of artifacts removed (0 when nothing is stale).
    """
    import shutil as _shutil

    claude_dir = target_dir / ".claude"
    removed = 0

    for artifact_type, subdir_name in _MANAGED_ARTIFACT_DIRS.items():
        managed_dir = claude_dir / subdir_name
        if not managed_dir.exists():
            continue

        expected_names: set[str] = source_manifests.get(artifact_type, set())

        for item in sorted(managed_dir.iterdir()):
            if item.name not in expected_names:
                print(f"Removing stale artifact: {item}")
                if item.is_dir() and not item.is_symlink():
                    _shutil.rmtree(item)
                else:
                    item.unlink()
                removed += 1

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
# ===========================================================================
