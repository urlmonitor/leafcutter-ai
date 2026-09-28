"""
MODULE: build_reconciliation_helpers
GOAL: ADR-041 Section 3 run-time reconciliation between the removal set and
    the claim set, and the end-of-run blocked-conflicts gate that follows
    from it -- the two main()-level checks BP-1500g-1 added around
    build_ownership's ownership predicate.
BUSINESS CONTEXT: build.py is grandfathered over the check-file-size ratchet,
    and build_main_helpers.py (BP-100n-4's decomposition of build.py's
    main()) sits close enough to the plain 400-content-line limit that
    adding these two main()-level checks in place would have pushed it over.
    Giving them their own module -- rather than growing either existing
    file -- is the sanctioned remedy, and mirrors how build_ownership.py
    and build_phases_clean.py already carry the rest of BP-1500g-1's logic
    out of their own oversized homes.
ARCHITECTURE: Two functions, both pure with respect to the filesystem except
    for printing:

    ``run_adr041_reconciliation`` recomputes the effective shim strategy
    (``build_shim_probe.resolve_effective_shim_strategy``, never the
    declared config value -- the declared value can differ from what the
    platform actually supports, and reconciling against the wrong side of
    that gap is exactly the failure ADR-041 exists to close) and the claim
    set for this run (empty under ``--no-shims``: no shim will be created,
    so nothing is claimed). It derives this run's actual removal candidates
    via ``build_ownership.compute_removal_candidates`` and refuses the build
    with exit code 1 when any path is scheduled for both removal and claim
    (``build_ownership.paths_scheduled_for_both_removal_and_claim``) --
    the two tables silently disagreeing is exactly KI-BP-009. Returns the
    effective strategy alongside the exit code so the caller can forward it
    to ``_cleanup_stale_paths`` without recomputing it.

    ``check_blocked_conflicts`` is the run's final backstop: a non-empty
    *blocked_conflicts* list (accumulated by ``_cleanup_stale_paths`` and the
    shim-install step, each appending a path whose content the build could
    not attribute to itself) fails the run with exit code 1 rather than
    reporting success over content it left untouched (BP-1500g-1-ii).

    Both are called from ``build.py``'s ``main()`` via thin wrappers in
    ``build_main_helpers.py`` (BP-100n-4's own decomposition pattern), not
    directly, keeping ``build_main_helpers.py`` the single place ``main()``
    reaches into for its per-step helpers.
"""

from __future__ import annotations

from pathlib import Path

from build_colors import error as _error
from build_ownership import (
    assemble_claim_set,
    compute_removal_candidates,
    format_reconciliation_refusal,
    paths_scheduled_for_both_removal_and_claim,
)
from build_shim_probe import resolve_effective_shim_strategy


def run_adr041_reconciliation(
    target_root: Path,
    output_root: Path,
    config: dict,
    no_shims: bool,
    shim_map: dict,
    file_shims: dict,
    pre_consolidation_paths: list[str],
) -> tuple[int | None, str]:
    """Refuse the build when the removal and claim sets contradict each other.

    Args:
        target_root: Root of the target project.
        output_root: The consolidated output directory.
        config: Build configuration dict (reads ``shim_strategy``).
        no_shims: True when ``--no-shims`` was passed.
        shim_map: build_helpers' symlink shim declarations.
        file_shims: build_helpers' file shim declarations.
        pre_consolidation_paths: build_ownership._PRE_CONSOLIDATION_PATHS.

    Returns:
        ``(exit_code, effective_strategy)``. ``exit_code`` is 1 when a
        reconciliation conflict was found (the build must halt), else None.
        ``effective_strategy`` is always returned so the caller can forward
        it to ``_cleanup_stale_paths`` without recomputing it.
    """
    shim_strategy = config.get("shim_strategy", "auto")
    eff_strategy = resolve_effective_shim_strategy(shim_strategy, target_root)
    claim_set = set() if no_shims else assemble_claim_set(shim_map, file_shims)
    removal_candidates = compute_removal_candidates(
        target_root, output_root, eff_strategy, pre_consolidation_paths, claim_set
    )
    conflicts = paths_scheduled_for_both_removal_and_claim(removal_candidates, claim_set)
    if conflicts:
        _error(format_reconciliation_refusal(conflicts))
        return 1, eff_strategy
    return None, eff_strategy


def check_blocked_conflicts(blocked_conflicts: list[str], dry_run: bool) -> int | None:
    """Fail the run when adopter-owned or unattributable content was left untouched.

    Args:
        blocked_conflicts: Relative paths accumulated across the run by the
            stale-cleanup and shim-install steps.
        dry_run: Never fails a dry run (nothing was actually left in place
            that a real run would have needed to touch).

    Returns:
        1 when the run must fail, else None.
    """
    if not blocked_conflicts or dry_run:
        return None
    _error(
        "Build cannot complete cleanly: the following path(s) hold "
        "content this build did not produce and were left untouched "
        f"rather than removed or overwritten: {sorted(set(blocked_conflicts))}. "
        "This is not a successful build — resolve the conflict (move "
        "your content to a location the build does not claim, or "
        "confirm it is safe and remove it yourself) and re-run."
    )
    return 1


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-09-21 [python-coder/merge origin/main into fast-lane/bp-1500g-1]:
#   New module. Carries the ADR-041 Section 3 reconciliation check and the
#   BP-1500g-1-ii end-of-run blocked-conflicts gate out of build.py's
#   main(), which on origin/main is now BP-100n-4's decomposed form
#   (build_main_helpers.py). Neither check existed on origin/main before
#   this merge; both are pure carry-forward of this branch's own BP-1500g-1
#   work, re-homed so build_main_helpers.py does not cross the
#   check-file-size ratchet. (#BP-1500g-1/merge-origin-main)
# ===========================================================================
