"""
MODULE: build_ownership
GOAL: Recomputed, run-time ownership attribution for the build's
    removal/claim decisions -- the single predicate every path that could
    plausibly hold adopter content must be checked against before the build
    touches it.
BUSINESS CONTEXT: Extracted from build.py and build_helpers.py so that
    BP-1500g-1 / ADR-041's decision -- ownership of an installed path is
    decided by recomputed attribution at item granularity, and the removal
    set and claim set are reconciled against each other every run -- has one
    home, instead of being scattered across the two build modules it was
    added to. Both modules were already over the check-file-size ratchet
    (an already-oversized file may be worked on, but must not end up longer
    than it stood at HEAD) before this AC; giving this distinct, cohesive
    concept its own module is what lets them shrink back under it rather
    than growing further. See
    docs/architecture/adrs/ADR-041-recomputed-attribution-at-item-granularity.md
    for the full decision record; it is not restated here.
ARCHITECTURE: Standalone module, no shared state.

    ``owns_installed_path`` is the ONE ownership predicate
    (``package_produced`` / ``adopter_owned`` / ``unattributable``) every
    removal/claim decision in the build must consult rather than deriving an
    independent rule -- two rules that happen to agree today is the same
    defect as the two independently-maintained tables
    (``_PRE_CONSOLIDATION_PATHS`` / ``shim_map``) that caused KI-BP-009 in
    the first place. Its callers are ``build.py``'s
    ``_cleanup_stale_paths`` and ``_run_migration_report``, and
    ``build_helpers.py``'s ``install_shims`` -- all three stay in their
    original modules and import from here; only the predicate moved.

    ``resolve_removal_verdict`` and ``resolve_shim_ownership_veto`` are each
    call site's own previously-duplicated preamble (the same handful of
    lines were copy-pasted once per loop when BP-1500g-1's ownership check
    was added), deduplicated here as pure functions rather than left
    duplicated. Neither changes any caller-visible behaviour; each caller's
    loop body is unchanged in shape, only the duplicated preamble is shared.

    ``paths_scheduled_for_both_removal_and_claim`` is the separate run-time
    reconciliation invariant BP-1500g-1 also requires: given a removal set
    and a claim set, surface their intersection as a contradiction rather
    than letting the two silently disagree, as they did in KI-BP-009.
    ``build.py`` imports it directly (``from build_ownership import
    paths_scheduled_for_both_removal_and_claim``) so ``build.
    paths_scheduled_for_both_removal_and_claim`` keeps resolving for
    existing callers -- including
    ``unit_tests/build_guards/test_bp_1500g_1.py``, which references it by
    that name -- with no test edit required.
"""

from __future__ import annotations

from pathlib import Path

from build_colors import warn as _warn

# The "removal set" table (ADR-041 Context §4): pre-consolidation output
# paths build.py's `_cleanup_stale_paths` and `_run_migration_report` treat
# as removal candidates, subject to the `owns_installed_path` verdict above.
# Used exclusively by those two functions (both still defined in build.py,
# which imports this constant so `build._PRE_CONSOLIDATION_PATHS` keeps
# resolving for existing callers, including
# unit_tests/build_guards/test_bp_1500g_1.py).
_PRE_CONSOLIDATION_PATHS = [
    ".claude/agents",
    ".claude/skills",
    ".claude/commands",
    ".claude/hooks",
    ".claude/settings.json",
    ".pre-commit-config.yaml",
    ".gemini",
    "scripts/commit_guardian",
    "scripts/doc_compliance",
    "scripts/feedback",
    "scripts/sync_platforms",
]


def owns_installed_path(path: Path) -> str:
    """Recomputed ownership verdict for *path*, evaluated fresh on every run.

    Returns one of:
      - ``"package_produced"``: nothing exists there, OR it is a symlink
        (removing a symlink never destroys the content it points to, so any
        symlink is always safe for the build to replace), OR it is a real,
        EMPTY directory / zero-byte file (nothing would be lost).
      - ``"adopter_owned"``: a real (non-symlink) file or directory holding
        content the build did not just verify is empty.
      - ``"unattributable"``: the path could not be inspected (e.g. a broken
        symlink or a permission error) — treated as a veto, the same as
        ``"adopter_owned"``, per BP-1500g-1's "non-attribution is keep" rule.

    This is the ONE ownership predicate BP-1500g-1 establishes. Every
    removal/claim decision in the build (``build._cleanup_stale_paths``,
    ``install_shims`` in build_helpers.py, ``build._run_migration_report``)
    must consult this same function rather than deriving an independent
    rule — two rules that happen to agree today is the same defect as the
    two independently-maintained tables (``_PRE_CONSOLIDATION_PATHS`` /
    ``shim_map``) that caused KI-BP-009 in the first place.

    Ownership is decided from content, never from a maintained name list:
    a real, non-empty path is ``adopter_owned`` regardless of what it is
    called, so a name that did not exist when this function was written is
    still correctly protected (BP-1500g-1's "no hardcoded name" requirement).

    Args:
        path: Absolute path to classify.

    Returns:
        ``"package_produced"``, ``"adopter_owned"``, or ``"unattributable"``.
    """
    try:
        if not path.exists() and not path.is_symlink():
            return "package_produced"
        if path.is_symlink():
            # Unlinking a symlink never touches the content it resolves to,
            # so any symlink — whatever it points at — is always safe to
            # replace.
            return "package_produced"
        if path.is_dir():
            return "package_produced" if not any(path.iterdir()) else "adopter_owned"
        return "package_produced" if path.stat().st_size == 0 else "adopter_owned"
    except OSError as exc:
        _warn(f"Could not determine ownership of {path}: {exc} — treating as unattributable (keep).")
        return "unattributable"


def resolve_removal_verdict(full: Path, output_root: Path) -> str | None:
    """Resolve *full*'s ownership verdict for a removal decision, or None
    when it should be skipped silently.

    Shared preamble for build.py's ``_cleanup_stale_paths`` and
    ``_run_migration_report``: a path that does not exist at all, or that
    is already a symlink resolving into *output_root* (our own,
    already-correct shim), is never a removal candidate and both callers
    skip it identically. Anything else is handed to ``owns_installed_path``
    for its full verdict.

    Args:
        full: Absolute candidate path for removal.
        output_root: The consolidated output directory; a symlink resolving
            here is always our own, already-correct shim.

    Returns:
        None when *full* should be skipped (absent, or already a correct
        shim into *output_root*); otherwise the ``owns_installed_path``
        verdict string.
    """
    if not full.exists() and not full.is_symlink():
        return None
    if full.is_symlink():
        link_target = full.resolve()
        if str(link_target).startswith(str(output_root.resolve())):
            # Already the correct shim into our own output root — nothing
            # stale here, leave it silently alone.
            return None
    return owns_installed_path(full)


def resolve_shim_ownership_veto(
    canonical_path: Path,
    strategy: str,
    canonical_rel: str,
    output_rel: str,
    kind: str | None = None,
) -> dict[str, str] | None:
    """Ownership veto for one canonical shim target, or None to proceed.

    Shared by ``install_shims``' directory-shim and file-shim loops
    (identical logic, previously duplicated once per loop). Under the
    ``"copy"`` strategy the canonical path is always a real, non-empty
    directory by design (that is where the package's own copied files
    live) — the veto only applies when the build is about to replace the
    path with a symlink, the scenario the container-conflict defect
    (KI-BP-009) actually occurs in.

    Args:
        canonical_path: The shim target path to classify.
        strategy: The configured ``shim_strategy`` (``"symlink"``,
            ``"copy"``, or ``"auto"``).
        canonical_rel: The canonical path's relative-to-target-root string,
            used in the result dict and the warning text.
        output_rel: The corresponding output-root-relative path, used in
            the result dict.
        kind: The noun to name in the warning text ("directory" or "file").
            When None, it is derived from ``canonical_path.is_dir()`` — the
            directory-shim loop's original behaviour. The file-shim loop
            passes ``"file"`` explicitly, matching its original hardcoded
            text even in the edge case where the conflicting path happens
            to be a directory.

    Returns:
        A ``{"canonical", "target", "method"}`` result dict (with
        ``method`` set to ``"blocked (<verdict>)"``) when the veto fires;
        otherwise None.
    """
    if strategy == "copy":
        return None
    verdict = owns_installed_path(canonical_path)
    if verdict == "package_produced":
        return None
    effective_kind = kind if kind is not None else ("directory" if canonical_path.is_dir() else "file")
    _warn(
        f"cannot install shim at {canonical_rel}: a real, "
        f"non-empty {effective_kind} already exists there holding content this build did "
        f"not produce ({verdict}). Leaving it in place and "
        "not creating this shim."
    )
    return {
        "canonical": canonical_rel,
        "target": output_rel,
        "method": f"blocked ({verdict})",
    }


def paths_scheduled_for_both_removal_and_claim(
    removal_set: set[str], claim_set: set[str]
) -> set[str]:
    """Return the paths present in BOTH *removal_set* and *claim_set*.

    The run-time reconciliation invariant BP-1500g-1 requires: a path the
    build would both remove (stale cleanup) and re-claim (shim install) in
    the same run is a contradiction the build can detect from its own data,
    without any knowledge of the adopter's project. A non-empty result means
    the two tables disagree about who owns the same path — exactly the
    condition that produced KI-BP-009. Pure function: no I/O, so any
    exception is a caller bug and must propagate rather than being caught
    here.

    Args:
        removal_set: Paths scheduled for removal this run.
        claim_set: Paths scheduled to be claimed (shimmed) this run.

    Returns:
        The (possibly empty) intersection of the two sets.
    """
    return set(removal_set) & set(claim_set)


# DECISION HISTORY
# ================================================================================
# - 2026-09-14 [python-coder]: Created this module, extracting BP-1500g-1's
#   ownership predicate (owns_installed_path, moved from build_helpers.py),
#   its removal-set table (_PRE_CONSOLIDATION_PATHS, moved from build.py),
#   and the reconciliation invariant (paths_scheduled_for_both_removal_and_claim,
#   moved from build.py) so that both build.py and build_helpers.py -- already
#   over the check-file-size ratchet before this change -- could shrink back
#   under it (ADR-041). Also added two small dedup helpers,
#   resolve_removal_verdict() and resolve_shim_ownership_veto(), covering
#   preamble logic that had been duplicated once per call site when the
#   ownership check was added: build.py's _cleanup_stale_paths and
#   _run_migration_report share the former; build_helpers.py's install_shims
#   (both its directory-shim and file-shim loops) shares the latter. All four
#   original call sites stay defined in their original modules and import
#   from here; this is a pure move plus deduplication, not a redesign.
#   Verified via a real `build.py --target-dir` run into a scratch directory
#   (exit 0) and `unit_tests/build_guards/` (152 passed, 4 subtests passed)
#   under AC_ENFORCE_STRICT=1. Nothing in the deployed layout imports this
#   module: build.py and build_helpers.py are the build tool itself, always
#   run from the source tree, never copied into a consumer install by any
#   build phase or deploy_map -- confirmed by grepping build_phases.py's
#   deploy maps and templates/ for both filenames, with no hits outside this
#   module's own siblings. No build-manifest / deploy-map entry was needed.
#   (#BP-1500g-1/extract)
# ====================================================================
