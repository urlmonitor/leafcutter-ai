"""
MODULE: unit_tests/build_guards/test_bp_1500g_1.py
GOAL: Failing test-first stubs for AC BP-1500g-1 -- the boundary, seam, and
    failure-mode angles of "your own work in your own project survives every
    build" (KI-BP-009), as distinct from the primary real-artifact
    reproduction in unit_tests/portability/test_bp_1500g_1.py.
AC: docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500g-1.yaml

MEASURED OVERLAP (re-verified against origin/main 1cce5b48a on 2026-09-08,
per this AC's it_requirements): EIGHT of the eleven `_PRE_CONSOLIDATION_PATHS`
entries in scripts/build.py are also canonical `shim_map` paths in
scripts/build_helpers.py -- `.claude/agents`, `.claude/skills`,
`.claude/commands`, `.claude/hooks`, `.gemini`, `scripts/commit_guardian`,
`scripts/doc_compliance`, `scripts/feedback`. The one-entry-fix control below
computes this intersection LIVE from the two real tables rather than
hardcoding it, so a ninth co-claimed path added later is covered
automatically.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_PORTABILITY_DIR = _THIS_DIR.parent / "portability"
_WORKTREE_ROOT = _THIS_DIR.parents[1]
_SCRIPTS_DIR = _WORKTREE_ROOT / "scripts"

for _p in (_PORTABILITY_DIR, _SCRIPTS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from _bp1500g1_harness import (  # noqa: E402
    fresh_scratch_adopter,
    new_marker_bytes,
    plant_capability_at_discoverable_location,
    replace_shim_with_real_directory,
    run_build,
)

import build as _build  # noqa: E402 -- after sys.path setup
import build_helpers as _build_helpers  # noqa: E402 -- after sys.path setup


def _live_co_claimed_paths() -> list[str]:
    """The LIVE intersection of `_PRE_CONSOLIDATION_PATHS` and `shim_map`'s
    canonical paths, computed from the two real tables -- never hardcoded,
    per this AC's own "measured overlap" it_requirement."""
    shim_canonical = {canonical for canonical, _output in _build_helpers.shim_map}
    return sorted(set(_build._PRE_CONSOLIDATION_PATHS) & shim_canonical)


def test_bp_1500g_1_every_co_claimed_path_is_protected_not_only_the_skills_directory(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-1
    # angle: boundary
    """THE ONE-ENTRY-FIX CONTROL, and the entry that makes a
    `.claude/skills`-only repair fail. Parameterised over the measured live
    intersection of `_PRE_CONSOLIDATION_PATHS` and `shim_map` -- eight paths
    as of 1cce5b48a -- computed IN THE TEST BODY from the two live tables
    rather than hardcoded, so a ninth co-claimed path added next month is
    covered without anyone editing this test. Plant real adopter-owned
    content at each and assert it survives a no-flag build."""
    co_claimed = _live_co_claimed_paths()
    assert co_claimed, (
        "No co-claimed path found between _PRE_CONSOLIDATION_PATHS and "
        "shim_map -- fixture/premise broken (expected at least "
        ".claude/skills)."
    )

    target_root = fresh_scratch_adopter(tmp_path)
    planted: dict[str, tuple[Path, bytes]] = {}
    for rel in co_claimed:
        container = target_root / rel
        if not container.is_symlink():
            # Not every co-claimed entry is guaranteed to be a directory shim
            # after a fresh build (e.g. it could be file-shaped); skip any
            # that a fresh build did not actually establish as a symlink so
            # this test only exercises genuinely exercisable containers.
            continue
        real_dir = replace_shim_with_real_directory(target_root, rel)
        marker = real_dir / "ADOPTER_MARKER.txt"
        content = new_marker_bytes(rel)
        marker.write_bytes(content)
        planted[rel] = (marker, content)

    assert planted, (
        "No co-claimed path was a symlink after a fresh build -- fixture "
        "premise broken."
    )

    result = run_build(target_root)

    failed = [
        rel
        for rel, (marker, content) in planted.items()
        if not (marker.is_file() and marker.read_bytes() == content)
    ]
    assert not failed, (
        f"The following co-claimed paths did NOT survive a no-flag build: "
        f"{failed}. A `.claude/skills`-only repair leaves every other "
        f"co-claimed path exposed to the same defect.\nstdout:\n{result.stdout}"
    )


def test_bp_1500g_1_the_build_refuses_to_both_remove_and_claim_the_same_path() -> None:
    # covers: BP-1500g-1
    # angle: seam
    """THE RUN-TIME RECONCILIATION INVARIANT, asserted directly at the seam,
    independent of any filesystem. CONTRACT THIS FIXES AS THE EXPLICIT
    TARGET FOR python-coder -- does not exist today, confirmed by `grep -n
    reconcil scripts/build.py` returning nothing:

        build.paths_scheduled_for_both_removal_and_claim(
            removal_set: set[str], claim_set: set[str],
        ) -> set[str]

    Returns the (possibly empty) intersection -- the set of paths the build
    would both remove and re-claim in the same run. Given a removal set and
    a claim set that intersect, the build must be able to surface the
    contradiction (this helper returns the non-empty intersection) rather
    than silently letting `_cleanup_stale_paths` and `_install_shims`
    disagree, as they do today. Given disjoint sets, it returns empty and
    the build proceeds. This is the entry that stays meaningful when
    `_PRE_CONSOLIDATION_PATHS` grows -- it does not depend on any specific
    path name."""
    removal_set = {".claude/skills", ".claude/agents", ".pre-commit-config.yaml"}
    claim_set = {".claude/skills", ".claude/commands"}

    conflict = _build.paths_scheduled_for_both_removal_and_claim(removal_set, claim_set)

    assert conflict == {".claude/skills"}, (
        f"Expected the single co-claimed path to be surfaced as a "
        f"contradiction; got {conflict!r}. The build must detect a path "
        "scheduled for both removal and re-claim from its own data, "
        "without any knowledge of the adopter's project."
    )

    disjoint_conflict = _build.paths_scheduled_for_both_removal_and_claim(
        {".pre-commit-config.yaml"}, {".claude/commands"}
    )
    assert disjoint_conflict == set(), (
        "Disjoint removal and claim sets must not be reported as a "
        "conflict -- a false positive here would block every ordinary "
        "build."
    )


def test_bp_1500g_1_ownership_is_not_decided_by_a_hardcoded_name_anywhere_in_the_removal_path(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-1
    # angle: failure
    """THE NO-MAINTAINED-LIST CONTROL, in the shape BP-1500b-2 and
    BP-1500b-4 use on their own sides. Plant adopter content whose directory
    name contains a uuid4 hex minted inside this test body, inside a
    co-claimed container. It must survive. A protected-names constant
    cannot hold a name that did not exist when it was written, so an
    allowlist repair -- KI-BP-009's own smaller fallback -- passes every
    other entry in this contract and fails here."""
    target_root = fresh_scratch_adopter(tmp_path)
    unique_name = f"adopter-{uuid.uuid4().hex}"
    planted = plant_capability_at_discoverable_location(target_root, name=unique_name)

    result = run_build(target_root)

    assert planted["skill_md"].is_file() and planted["skill_md"].read_bytes() == planted[
        "content"
    ], (
        f"Adopter content under a name minted at test time ({unique_name}) "
        "did not survive -- ownership must not be decided by a hardcoded "
        f"or pre-registered name.\nstdout:\n{result.stdout}"
    )


def test_bp_1500g_1_the_migration_report_never_instructs_the_adopter_to_delete_their_own_content(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-1
    # angle: criterion
    """THE FIFTH ENFORCEMENT POINT. Run the migration report (`--migrate`)
    over a tree holding adopter-owned content at a co-claimed path and
    assert the printed remediation does not name that path in an `rm`/
    `rm -rf` instruction. Guards the surviving-advice failure: four repaired
    code paths and one page of prose still telling the adopter to do it by
    hand. `_run_migration_report` in scripts/build.py iterates the same
    `_PRE_CONSOLIDATION_PATHS` constant and prints `rm -rf <path>` for any
    entry it considers stale -- confirmed present, and not named in
    KI-BP-009 prior to this AC's enrichment."""
    target_root = fresh_scratch_adopter(tmp_path)
    plant_capability_at_discoverable_location(target_root)

    result = run_build(target_root, "--migrate")

    assert result.returncode == 0, (
        f"--migrate did not exit 0.\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "rm -rf .claude/skills" not in combined, (
        "The migration report instructs the adopter to `rm -rf` their own "
        f".claude/skills directory.\n{combined}"
    )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-08 [test-writer/fast-lane BP-1500g-1 build set]: Initial RED
#   stubs for the boundary/seam/failure angles. `paths_scheduled_for_both_
#   removal_and_claim` does not exist on scripts/build.py today (confirmed
#   by grep for "reconcil" and "scheduled_for_both" -- no hits), so the seam
#   test is RED via AttributeError. The other three exercise the same
#   confirmed `_cleanup_stale_paths` / `_run_migration_report` defects as
#   the portability file's primary reproduction.
# ====================================================================
