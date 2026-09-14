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
    the first place. Its callers are ``build.py``'s ``_cleanup_stale_paths``,
    this module's own ``run_migration_report``, and ``build_helpers.py``'s
    ``install_shims``.

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
    that name -- with no test edit required. ``compute_removal_candidates``
    is the small helper ``build.py``'s ``main()`` uses to turn the removal
    table into the *actually-scheduled-this-run* subset reconciliation is
    checked against (raw table membership would false-trigger on every
    ordinary build, since most ``_PRE_CONSOLIDATION_PATHS`` entries are
    always co-claimed).

    ``run_migration_report`` (the ``--migrate`` report) moved here from
    ``build.py`` in the same pass that shed the headroom this module exists
    to hold -- see this module's own DECISION HISTORY for the full account,
    rather than repeating it once per file it touched. It takes its claim
    set as a plain ``claim_set: set[str]`` parameter, the same one
    ``assemble_claim_set`` (below) produces: ``build_helpers`` already
    imports ``resolve_shim_ownership_veto`` from this module, so importing
    ``build_helpers.shim_map``/``file_shims`` back in here would be
    circular -- ``assemble_claim_set`` takes them as plain parameters
    instead, and ``build.py`` computes the claim set once (from
    ``build_helpers``'s two tables) and passes it to both
    ``run_migration_report`` and ``compute_removal_candidates``.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from build_colors import warn as _warn

# Hardcoded "build_phases", not __name__: _load_clean_ledger/_save_clean_ledger
# moved here from build_phases.py (headroom pass, ADR-041 review) but must
# keep logging through the SAME logger identity build_phases.py's own
# ``logging.getLogger(__name__)`` produced, unchanged in behaviour.
_clean_ledger_log = logging.getLogger("build_phases")

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


def resolve_removal_verdict(
    full: Path,
    output_root: Path,
    strategy: str = "auto",
    is_claimed: bool = False,
) -> str | None:
    """Resolve *full*'s ownership verdict for a removal decision, or None
    when it should be skipped silently.

    Shared preamble for build.py's ``_cleanup_stale_paths`` and
    ``_run_migration_report``: a path that does not exist at all, or that
    is already a symlink resolving into *output_root* (our own,
    already-correct shim), is never a removal candidate and both callers
    skip it identically. Anything else is handed to ``owns_installed_path``
    for its full verdict — EXCEPT one further case, below.

    Under ``shim_strategy: "copy"``, a co-claimed canonical path (one a
    shim table will also reclaim this run, per *is_claimed*) is never a
    removal candidate at all, regardless of what ``owns_installed_path``
    would say about it. This is not the same carve-out
    ``resolve_shim_ownership_veto`` makes on the claim side: it is not
    "copy strategy is always safe", it is "this removal step has no way to
    tell a stale pre-consolidation leftover apart from the build's own
    current copy-strategy output by content alone" — the same
    container-vs-item conflation ADR-041 §1 rejects for the old
    is-symlink signal, now showing up on the removal side under copy
    strategy instead. A real, non-empty directory at a co-claimed path is
    exactly what a correct copy-strategy build looks like after its first
    run; ``owns_installed_path`` cannot distinguish that from a genuine
    orphan, so this function does not try. Ownership of what is
    individually INSIDE that container (ADR-041 §2: never the container as
    a whole) is decided at item granularity by ``install_shims``' own
    non-destructive copy-merge instead — see that function's directory-shim
    loop. A removal-only entry (not *is_claimed*, e.g.
    ``scripts/sync_platforms``) is unaffected by *strategy* and still gets
    the normal content-based verdict.

    Args:
        full: Absolute candidate path for removal.
        output_root: The consolidated output directory; a symlink resolving
            here is always our own, already-correct shim.
        strategy: The configured ``shim_strategy`` (``"symlink"``,
            ``"copy"``, or ``"auto"``). Defaults to ``"auto"`` for callers
            that have no strategy-specific behaviour to preserve.
        is_claimed: Whether *full*'s relative path also appears in a claim
            table (``shim_map`` or ``file_shims``) — i.e. whether some shim
            step will also try to (re)claim it this run.

    Returns:
        None when *full* should be skipped (absent, already a correct shim
        into *output_root*, or a co-claimed copy-strategy container);
        otherwise the ``owns_installed_path`` verdict string.
    """
    if not full.exists() and not full.is_symlink():
        return None
    if full.is_symlink():
        link_target = full.resolve()
        if str(link_target).startswith(str(output_root.resolve())):
            # Already the correct shim into our own output root — nothing
            # stale here, leave it silently alone.
            return None
    if strategy == "copy" and is_claimed:
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
    ``"copy"`` strategy this veto does not fire — NOT because "the
    canonical path is always a real, non-empty directory by design and so
    is never a conflict" (that claim is true of the CONTAINER and false of
    its CONTENTS, and treating a co-claimed container as a single unit is
    exactly the conflation ADR-041 §2 forbids). It does not fire because,
    for the directory-shim loop, the caller no longer removes anything
    before recreating the shim under copy strategy: ``_create_shim``'s
    copy branch is ``shutil.copytree(source, canonical,
    dirs_exist_ok=True)``, which merges the package's own current files in
    by name and never deletes a name it doesn't overwrite — so a genuinely
    adopter-owned item placed inside the container is never touched,
    regardless of whether this veto runs. Vetoing here (i.e. refusing to
    shim at all) would only reintroduce the false-permanent-failure defect
    (ADR-041 review defect 2a) this carve-out exists to avoid, for no
    additional safety. Item-level protection is enforced at the copy-merge
    itself, not by this container-level veto. For the file-shim loop a
    single file has no "contents" to conflate with its container in the
    first place, so the same reasoning is moot there — a copy-strategy
    file shim still fully overwrites its target, unchanged from before
    this decision record.

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


def assemble_claim_set(
    shim_map: list[tuple[str, str]], file_shims: list[tuple[str, str]]
) -> set[str]:
    """The full claim set: every canonical path either claim table will
    (re)claim this run.

    ADR-041 Decision §3 requires the reconciliation to be assembled from
    ALL of the claim tables named in its Context §4 --
    ``build_helpers.shim_map`` (directories) and ``build_helpers.file_shims``
    (files). Takes both as plain parameters rather than importing them from
    ``build_helpers`` directly: ``build_helpers`` already imports
    ``resolve_shim_ownership_veto`` from this module, so importing back from
    ``build_helpers`` here would be circular. ``build.py`` calls this with
    ``build_helpers.shim_map`` and ``build_helpers.file_shims``.

    Args:
        shim_map: The directory-shim claim table.
        file_shims: The file-shim claim table.

    Returns:
        The union of every canonical (target-root-relative) path named in
        either table.
    """
    return {c for c, _ in shim_map} | {c for c, _ in file_shims}


def compute_removal_candidates(
    target_root: Path,
    output_root: Path,
    strategy: str,
    removal_paths: list[str],
    claim_set: set[str],
) -> set[str]:
    """The subset of *removal_paths* this run would ACTUALLY remove.

    ADR-041 §3's reconciliation must be checked against real run data, not
    a table's raw membership: most ``_PRE_CONSOLIDATION_PATHS`` entries are
    always present in a claim table too (co-claimed containers), so
    intersecting the two tables directly would refuse every ordinary build.
    A path only belongs in the removal set when its recomputed verdict this
    run is ``"package_produced"`` -- an already-correct shim, or anything
    else not actually scheduled for removal, resolves to something else (or
    ``None``) and is excluded. Callers pass the result to
    ``paths_scheduled_for_both_removal_and_claim`` alongside the claim set.

    Args:
        target_root: Root of the target project.
        output_root: The consolidated output directory.
        strategy: The configured ``shim_strategy``, forwarded to
            ``resolve_removal_verdict``.
        removal_paths: Candidate paths to test (``_PRE_CONSOLIDATION_PATHS``).
        claim_set: The full claim set, so each candidate's *is_claimed*
            flag can be resolved for ``resolve_removal_verdict``.

    Returns:
        The subset of *removal_paths* whose verdict this run is
        ``"package_produced"``.
    """
    return {
        rel_path
        for rel_path in removal_paths
        if resolve_removal_verdict(
            target_root / rel_path, output_root, strategy, rel_path in claim_set
        )
        == "package_produced"
    }


def format_reconciliation_refusal(conflicts: set[str]) -> str:
    """The ADR-041 §3 refusal message for main() to pass to ``_error``.

    Kept as a plain string-returning function (rather than main() building
    the f-string inline) so the message text lives beside the invariant it
    describes. Callers are expected to ``return 1`` immediately after
    printing it -- this function has no control-flow effect of its own.

    Args:
        conflicts: The non-empty result of
            ``paths_scheduled_for_both_removal_and_claim``.

    Returns:
        The formatted refusal message, naming every conflicting path.
    """
    return (
        "Build refuses to proceed: the following path(s) are scheduled "
        "for BOTH removal (this run's stale-cleanup pass) AND reclaim "
        "(a shim table will recreate them) in the SAME run — exactly "
        "the contradiction that caused KI-BP-009. ADR-041 §3 requires "
        "the build to refuse rather than resolve this silently: "
        f"{sorted(conflicts)}. Investigate why the path(s) named above "
        "ended up in this state before re-running."
    )


def run_migration_report(
    target_root: Path, output_root: Path, strategy: str, claim_set: set[str]
) -> int:
    """Scan for stale pre-consolidation files and print a migration report.

    Moved here from ``build.py`` (see this module's DECISION HISTORY) --
    ``build.py``'s ``--migrate`` flag calls this unchanged in behaviour.

    Checks known pre-consolidation output paths. A path already shimmed
    correctly (symlink into the output root) is not stale. Of the
    remainder, only paths whose ownership verdict (``owns_installed_path``)
    is ``"package_produced"`` (a foreign symlink, or a real empty
    directory/file) are suggested for removal via an ``rm``/``rm -rf``
    instruction — the fifth enforcement point ADR-041 governs. A path
    holding content the build cannot attribute to itself is listed
    separately as PROTECTED and is never named in a removal instruction:
    a migration report must not instruct the adopter to delete their own
    content by hand. Under ``shim_strategy: "copy"`` a co-claimed path is
    never considered stale at all (see ``resolve_removal_verdict``) so it is
    silently omitted from both lists, the same as an already-correct symlink.

    Args:
        target_root: Root of the target project.
        output_root: The consolidated output directory.
        strategy: The configured ``shim_strategy``.
        claim_set: The full claim set (see module docstring for why this is
            a parameter rather than an internal import).

    Returns:
        0 always (report-only, no deletions).
    """
    print(f"\nMigration report for: {target_root}")
    print(f"Output root: {output_root}\n")

    stale: list[str] = []
    protected: list[str] = []
    for rel_path in _PRE_CONSOLIDATION_PATHS:
        full = target_root / rel_path
        verdict = resolve_removal_verdict(full, output_root, strategy, rel_path in claim_set)
        if verdict is None:
            continue
        if verdict == "package_produced":
            stale.append(rel_path)
        else:
            protected.append(rel_path)

    if not stale and not protected:
        print("No stale pre-consolidation files found. Migration complete.")
        return 0

    if stale:
        print(f"Found {len(stale)} stale pre-consolidation path(s):\n")
        for p in stale:
            full = target_root / p
            kind = "directory" if full.is_dir() else "file"
            print(f"  STALE: {p} ({kind})")

        print("\nTo remove stale files, run:")
        for p in stale:
            full = target_root / p
            if full.is_dir():
                print(f"  rm -rf {p}")
            else:
                print(f"  rm {p}")
    else:
        print("No stale pre-consolidation files are safe to remove automatically.")

    if protected:
        print(
            f"\n{len(protected)} path(s) hold content this build did not "
            "produce and will NOT be suggested for removal:\n"
        )
        for p in protected:
            print(f"  PROTECTED: {p} (adopter-owned or unattributable content)")

    # Hardcoded "build.py", not Path(__file__).name -- this function now
    # lives in build_ownership.py, but the printed instruction must name
    # the CLI entry point the adopter actually runs, unchanged from the
    # original build.py-resident behaviour.
    print(f"\nThen re-run: python build.py --target-dir {target_root}")
    return 0


#: BP-1500g-1-i: filename of the ledger clean_stale_artifacts() (build_phases.py)
#: maintains under output_root, recording — per artifact type — the UNION of
#: every name ever seen in a real ``source_manifests`` at clean-mode time.
#: Never shrinks. This is the "provenance record" it_requirements calls for:
#: an item absent from the CURRENT manifest is only removed when it was
#: PREVIOUSLY, genuinely package-produced (recorded here in an earlier
#: --clean run) — never merely because its name is unrecognised today. An
#: unrecognised name the ledger has never seen is adopter-owned or
#: unattributable by definition and is always kept. Moved here from
#: build_phases.py (headroom pass, ADR-041 review) alongside the two
#: functions that read/write it, unchanged in behaviour.
_CLEAN_LEDGER_FILENAME = ".clean_deploy_ledger.json"


def _load_clean_ledger(ledger_path: Path) -> dict[str, set[str]]:
    """Load the clean-mode provenance ledger, tolerating absence/corruption."""
    if not ledger_path.exists():
        return {}
    try:
        raw = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _clean_ledger_log.warning(
            "Could not read clean-mode ledger %s: %s — treating as empty.", ledger_path, exc
        )
        return {}
    return {k: set(v) for k, v in raw.items()} if isinstance(raw, dict) else {}


def _save_clean_ledger(ledger_path: Path, ledger: dict[str, set[str]]) -> None:
    """Persist the clean-mode provenance ledger (never shrinks its entries)."""
    try:
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        serialisable = {k: sorted(v) for k, v in ledger.items()}
        ledger_path.write_text(
            json.dumps(serialisable, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except OSError as exc:
        _clean_ledger_log.warning("Could not write clean-mode ledger %s: %s", ledger_path, exc)


def _relative_symlink_target(canonical: Path, source: Path) -> str:
    """Return the symlink target to record for ``canonical`` -> ``source``.

    Moved here from ``build_helpers.py`` (headroom pass, ADR-041 review --
    see this module's DECISION HISTORY) alongside its two callers below,
    unchanged in behaviour.

    Computed relative to ``canonical``'s own parent directory (ADR-004 /
    ADR-016) — not the process's working directory — so a rebuild from any
    cwd, and a relocation/copy of the whole tree, still resolves. Falls back
    to an absolute target when no relative path can be expressed (e.g. the
    canonical location and the output root sit on different drives/mounts
    with no common ancestor); the caller still completes in that case.

    Args:
        canonical: Absolute path where the shim link will be created.
        source: Absolute path inside the output root the link must resolve to.

    Returns:
        The string to pass to ``Path.symlink_to()`` — a relative path when
        one can be expressed, otherwise the absolute ``source`` path.
    """
    try:
        return os.path.relpath(str(source), str(canonical.parent))
    except ValueError:
        return str(source)


def _create_shim(canonical: Path, source: Path, strategy: str) -> str:
    """Create a directory shim (symlink or copy) at canonical pointing to source.

    Moved here from ``build_helpers.py`` (headroom pass, ADR-041 review).

    Args:
        canonical: Absolute path where the shim is created (e.g. `.claude/agents`).
        source: Absolute path inside the output root the shim must resolve to.
        strategy: ``"symlink"``, ``"copy"``, or ``"auto"`` (see ``install_shims``).

    Returns:
        The method used: ``"symlink"``, ``"copy"``, or ``"copy (symlink failed)"``.
    """
    import shutil

    if strategy == "copy":
        shutil.copytree(source, canonical, dirs_exist_ok=True)
        return "copy"

    target = _relative_symlink_target(canonical, source)
    try:
        canonical.symlink_to(target, target_is_directory=True)
    except (OSError, PermissionError):
        if strategy == "symlink":
            raise
        shutil.copytree(source, canonical, dirs_exist_ok=True)
        return "copy (symlink failed)"
    else:
        return "symlink"


def _create_file_shim(canonical: Path, source: Path, strategy: str) -> str:
    """Create a file shim (symlink or copy) at canonical pointing to source.

    Moved here from ``build_helpers.py`` (headroom pass, ADR-041 review).

    Args:
        canonical: Absolute path where the shim is created (e.g. `.gemini`).
        source: Absolute path inside the output root the shim must resolve to.
        strategy: ``"symlink"``, ``"copy"``, or ``"auto"`` (see ``install_shims``).

    Returns:
        The method used: ``"symlink"``, ``"copy"``, or ``"copy (symlink failed)"``.
    """
    import shutil

    if strategy == "copy":
        shutil.copy2(source, canonical)
        return "copy"

    target = _relative_symlink_target(canonical, source)
    try:
        canonical.symlink_to(target)
    except (OSError, PermissionError):
        if strategy == "symlink":
            raise
        shutil.copy2(source, canonical)
        return "copy (symlink failed)"
    else:
        return "symlink"


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
# - 2026-09-14 [python-coder/ADR-041 review-defects pass, CONSOLIDATED --
#   this is the canonical account for build.py, build_helpers.py, and
#   build_phases.py too; each carries only a short pointer back here rather
#   than repeating this narrative four times]: Fixed three divergences from
#   ADR-041 found reviewing this AC's own implementation, then shed the
#   resulting file-size-ratchet overage back into this module (its intended
#   destination -- see the GOAL/BUSINESS CONTEXT above).
#   DEFECT 1 (dead reconciliation invariant): paths_scheduled_for_both_
#   removal_and_claim was correct but never called from real control flow.
#   Wired it into build.py's main() via the new compute_removal_candidates
#   (below): the removal set is the subset of _PRE_CONSOLIDATION_PATHS
#   whose recomputed verdict THIS run is actually "package_produced" (not
#   raw table membership, which false-triggers on every ordinary build,
#   since most entries are always co-claimed); a non-empty intersection
#   with the claim set refuses the build before any removal/shim action.
#   Promoted build_helpers.py's file_shims from a function-local variable
#   to module scope (ADR-041 Decision §3 names this explicitly) and added
#   assemble_claim_set() (this module) to combine it with build_helpers'
#   shim_map into the claim set build.py passes around.
#   DEFECT 2a (copy-strategy false failure): resolve_removal_verdict gained
#   strategy/is_claimed parameters -- under shim_strategy "copy", a
#   co-claimed path is never a removal candidate at all, since content
#   alone cannot distinguish a stale leftover from the build's own current
#   copy-strategy output. Fixes a false permanent build failure on every
#   build after the first.
#   DEFECT 2b (copy-strategy data loss, the serious half): install_shims'
#   directory-shim loop no longer shutil.rmtree()s the canonical directory
#   before recreating it under copy strategy -- confirmed as a real,
#   present destruction of genuinely adopter-owned content placed inside a
#   co-claimed container, not merely hypothetical. _create_shim's copy
#   branch (shutil.copytree(source, canonical, dirs_exist_ok=True)) merges
#   the package's own files in by name without deleting anything it
#   doesn't overwrite, so no pre-removal is needed at all under copy
#   strategy; symlink strategy's pre-removal is unchanged.
#   resolve_shim_ownership_veto's docstring was corrected to stop claiming
#   copy-strategy directories are "always safe by design" (true of the
#   container, false of its contents, the exact conflation ADR-041 §2
#   forbids) -- the real reason the veto can skip is the pre-removal fix
#   above, so the merge itself is non-destructive.
#   DEFECT 3 (silent keep): build_phases.py's clean_stale_artifacts printed
#   nothing for a kept-but-unattributable item (bare `continue`), unlike
#   the adjacent removal branch's own print. Now prints a WARNING naming
#   the item -- ADR-041 Consequences/Negative requires this be visible, not
#   merely spared, since silence here is exactly what let KI-BP-009 survive
#   months of green builds undetected.
#   HEADROOM PASS: the above fixes pushed build.py/build_helpers.py/
#   build_phases.py over the file-size ratchet's HEAD baseline. Moved
#   run_migration_report, compute_removal_candidates,
#   format_reconciliation_refusal, assemble_claim_set,
#   _relative_symlink_target/_create_shim/_create_file_shim, and
#   _CLEAN_LEDGER_FILENAME/_load_clean_ledger/_save_clean_ledger here --
#   all belong with the ownership predicates and provenance records they
#   serve, not in build.py's CLI-orchestration file, build_helpers.py's
#   shim-install file, or build_phases.py's phase-dispatch file -- and
#   shrank each of the other three files' own decision-history entries and
#   in-place explanatory comments to short pointers back to this one,
#   moving the substance of what they explained into function/module
#   docstrings (free under the ratchet's own docstring-stripping rule)
#   rather than deleting it. The moved ledger helpers keep logging through
#   ``logging.getLogger("build_phases")`` (hardcoded, not ``__name__``) so
#   their observable behaviour is byte-identical to before the move.
#   Verified via the four originally-RED tests (all green) plus the full
#   unit_tests/build_guards/ suite (152 passed, 4 subtests passed, no
#   regressions) under AC_ENFORCE_STRICT=1, both before and after the
#   headroom pass. (#BP-1500g-1/adr-041-review)
# ====================================================================
