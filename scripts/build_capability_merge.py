"""
MODULE: build_capability_merge
GOAL: Per-item merge of package-shipped items into a real, existing
    directory shim container that BP-1500g-1's ownership veto correctly
    refuses to replace wholesale -- so BP-1500g-2's coexistence guarantee
    ("every capability the package currently ships is present AND
    reachable by name, out of the SAME run in which the adopter's own
    content survived") holds without ever making the container itself the
    unit of the decision (ADR-041 §2).
BUSINESS CONTEXT: Before this module existed, install_shims' directory-shim
    loop treated a real, non-empty (adopter-owned or unattributable)
    canonical directory as an all-or-nothing veto: skip the WHOLE shim,
    leave every package item unreachable, and record a "blocked" conflict.
    That is precisely the "cheapest repair" BP-1500g-2's own notes name and
    exist to forbid: the adopter's content survives, nobody is told, and
    the package's own capabilities quietly never arrive. This module
    replaces that skip with the item-granular merge ADR-041 §2 already
    prescribes for removal decisions, applied here to the mirror-image
    write decision: only a name this run cannot attribute to itself is
    left alone; every other shipped name is copied in individually, and a
    genuine name collision (BP-1500g-2-i) is reported rather than silently
    resolved either way -- never overwritten, emptied, moved, or removed.
ARCHITECTURE: ``resolve_veto_or_merge`` is ``install_shims``' (build_helpers.py)
    single new call site, replacing its previous direct call to
    ``build_ownership.resolve_shim_ownership_veto`` in the directory-shim
    loop only (the file-shim loop is unaffected: a single file has no
    "items" to merge, and BP-1500g-2/-2-i are both about "capabilities" --
    skill directories -- not single-file shims like
    ``.pre-commit-config.yaml``). When the veto does not fire, behaviour is
    byte-identical to before (returns None, caller proceeds with its normal
    replace-and-shim path). When it fires for a real DIRECTORY, this module
    merges package items in instead of the caller simply appending the
    veto's "blocked" result.

    ``merge_capability_items`` is the merge itself, built on two pure
    predicates from ``build_ownership``: ``owns_installed_path`` (applied
    per ITEM inside the container, never to the container as a whole) and
    ``detect_capability_collisions`` (BP-1500g-2-i's own named contract --
    a plain set intersection over the shipped names and the names this run
    cannot attribute to itself).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from build_ownership import (
    detect_capability_collisions,
    owns_installed_path,
    resolve_shim_ownership_veto,
)


def _item_names(directory: Path) -> set[str]:
    """Immediate child names of *directory* (files and sub-directories alike).

    Args:
        directory: Absolute path to inspect.

    Returns:
        The (possibly empty) set of immediate child names, or an empty set
        when *directory* is not a real, readable directory.
    """
    if not directory.is_dir():
        return set()
    return {child.name for child in directory.iterdir()}


def _adopter_owned_item_names(canonical_path: Path) -> set[str]:
    """Names inside *canonical_path* this run cannot attribute to itself.

    Applies ``owns_installed_path`` to each IMMEDIATE CHILD individually --
    never to *canonical_path* as a whole (ADR-041 §2) -- so a genuinely
    empty leftover child is still treated as safe to overwrite, exactly as
    it would be if it sat at the top level.

    Args:
        canonical_path: The real, existing directory to inspect.

    Returns:
        The set of child names whose own verdict is not
        ``"package_produced"``.
    """
    return {
        name
        for name in _item_names(canonical_path)
        if owns_installed_path(canonical_path / name) != "package_produced"
    }


def _copy_item(source: Path, target: Path) -> None:
    """Copy one shipped item (file or directory) into place, verbatim.

    Args:
        source: The package's own current item, e.g.
            ``<output_root>/skills/<name>``.
        target: Where to place it inside the real, existing container.
    """
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def report_capability_collision(name: str) -> None:
    """Print BP-1500g-2-i's prescribed collision line for *name*.

    The EXACT line format ``unit_tests/portability/_bp1500g1_harness.
    parse_stated_collision_winner`` parses back -- any drift here silently
    breaks that parser, which is the observability half of this AC's own
    contract. Printed via plain ``print()``, never through build_colors'
    ``warn()``/``info()``, whose prefixes fall outside this line's own
    anchored, line-start-to-line-end format. This module's own policy: the
    adopter's version always wins a contested name (BP-1500g-2-i's first
    Then clause is unconditional -- "not overwritten, not emptied, not
    moved and not removed" -- and the AC does not require the package's
    version to win instead), so every caller of this function reports
    ``"adopter"``.

    Args:
        name: The contested capability name.
    """
    print(f"collision: {name} -- resolves to adopter")


def merge_capability_items(
    canonical_path: Path,
    source_path: Path,
    canonical_rel: str,
    output_rel: str,
    dry_run: bool,
) -> dict[str, str]:
    """Item-granular merge of *source_path*'s children into *canonical_path*.

    Called INSTEAD OF skipping the whole container when
    ``resolve_shim_ownership_veto`` would otherwise fire for a real,
    existing directory: every shipped name that does not collide with a
    name this run cannot attribute to itself
    (``build_ownership.detect_capability_collisions``) is copied in
    individually, by name, so it becomes reachable through the SAME
    discoverable path the adopter's own content already occupies --
    without ever removing, emptying, or replacing the container, or
    anything inside it that this call does not itself write.

    A colliding name is reported (BP-1500g-2-i) via
    ``report_capability_collision`` and left completely untouched: this
    function never overwrites an existing, non-package-produced item under
    any circumstance.

    Args:
        canonical_path: The real, existing directory to merge into (e.g.
            ``<target_root>/.claude/skills``).
        source_path: The package's own current output for this container
            (e.g. ``<output_root>/skills``).
        canonical_rel: *canonical_path*'s target-root-relative string, used
            only in the returned/printed method description.
        output_rel: *source_path*'s output-root-relative string, carried
            through unchanged into the returned result dict so its shape
            matches every other ``install_shims`` entry.
        dry_run: When True, reports intent but writes nothing.

    Returns:
        A ``{"canonical", "target", "method"}`` result dict matching every
        other ``install_shims`` entry's shape -- never one whose
        ``"method"`` starts with ``"blocked"``, since a successful
        item-level merge is not the run-ending backstop condition
        BP-1500g-1-ii governs.
    """
    shipped_names = _item_names(source_path)
    adopter_names = _adopter_owned_item_names(canonical_path)
    collisions = detect_capability_collisions(shipped_names, adopter_names)

    installed: list[str] = []
    for name in sorted(shipped_names - collisions):
        if not dry_run:
            _copy_item(source_path / name, canonical_path / name)
        installed.append(name)

    for name in sorted(collisions):
        report_capability_collision(name)

    if installed or collisions:
        label = "would merge" if dry_run else "merged"
        collision_note = (
            f"; {len(collisions)} contested name(s) left untouched" if collisions else ""
        )
        print(
            f"  {canonical_rel}: {label} {len(installed)} package item(s) "
            f"into the existing directory (adopter content left in place)"
            f"{collision_note}: {', '.join(installed) if installed else '(none)'}"
        )

    return {
        "canonical": canonical_rel,
        "target": output_rel,
        "method": f"merged ({len(installed)} item(s), {len(collisions)} collision(s))",
    }


def resolve_veto_or_merge(
    canonical_path: Path,
    source_path: Path,
    strategy: str,
    canonical_rel: str,
    output_rel: str,
    dry_run: bool,
) -> dict[str, str] | None:
    """install_shims' single call site: veto, merge, or proceed.

    Replaces a direct call to ``build_ownership.resolve_shim_ownership_veto``
    in the directory-shim loop only (the file-shim loop is unaffected -- see
    this module's own docstring). When the veto does not fire, behaviour is
    byte-identical to before (returns None; the caller proceeds with its
    normal replace-and-shim path). When it fires for a real DIRECTORY, this
    merges package items in individually instead of skipping the whole
    container. For anything else the veto fires on (a plain file occupying
    a directory shim's canonical path -- not expected in practice, since
    every ``shim_map`` entry names a directory), the original "blocked"
    veto result is returned unchanged: merging has no meaning for a
    non-directory, and this function invents no new behaviour for it.

    Args:
        canonical_path: The shim target path to classify.
        source_path: The package's own current output for this container.
        strategy: The configured ``shim_strategy``.
        canonical_rel: *canonical_path*'s target-root-relative string.
        output_rel: *source_path*'s output-root-relative string.
        dry_run: Forwarded to ``merge_capability_items``.

    Returns:
        None when the caller should proceed with its normal shim
        replacement; otherwise the result dict to append and skip ahead.
    """
    veto = resolve_shim_ownership_veto(canonical_path, strategy, canonical_rel, output_rel)
    if veto is None:
        return None
    if canonical_path.is_dir() and not canonical_path.is_symlink():
        return merge_capability_items(canonical_path, source_path, canonical_rel, output_rel, dry_run)
    return veto


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-23 [python-coder/BP-1500g-2, BP-1500g-2-i]: New module. See its
#   own docstring for the full design account. Item-granular merge
#   (ADR-041 §2) replaces install_shims' previous all-or-nothing container
#   veto for a real, existing directory: every shipped item this run can
#   attribute to itself is copied in by name; a name this run cannot
#   attribute to itself is left completely alone; a name claimed by BOTH
#   sides is reported (never silently resolved either way) via the
#   prescribed `collision: <name> -- resolves to <adopter|package>` line
#   and the adopter's version is preserved unconditionally (this module
#   always reports "adopter" -- see report_capability_collision's own
#   docstring for why that satisfies BP-1500g-2-i without picking a winner
#   the AC itself declines to pick).
#
#   KNOWN, DELIBERATE CONSEQUENCE FOR BP-1500g-1-ii's EXISTING TESTS: both
#   unit_tests/portability/test_bp_1500g_1_ii.py and
#   unit_tests/build_guards/test_bp_1500g_1_ii.py construct their trigger
#   scenario via `_bp1500g1_harness.plant_capability_at_discoverable_
#   location` -- a real `.claude/skills` directory holding ONLY the
#   adopter's own, uniquely-named item, colliding with nothing the package
#   ships. Before this change, that scenario reached BP-1500g-1's
#   container-level veto with no merge fallback, so the run genuinely could
#   not proceed without either overwriting the adopter's directory or
#   leaving every package skill unreachable -- BP-1500g-1-ii's own
#   "cannot proceed without taking adopter content" backstop condition, and
#   its tests assert the resulting non-zero exit. After this change, the
#   SAME scenario merges cleanly (no colliding name), so the build now
#   completes with exit 0 and every package skill reachable -- which is
#   exactly BP-1500g-2's own explicit requirement for this identical
#   fixture (see unit_tests/portability/test_bp_1500g_2.py's own decision
#   history: "assert result.returncode == 0 ... it is BP-1500g-1-ii's
#   honest-but-blocked outcome, not the single ordinary successful run this
#   AC's Given clause describes"). This is not an oversight: BP-1500g-1-ii's
#   OWN it_requirements say a build refusing this exact ordinary,
#   non-colliding tree is "a defect signal, not the feature working" ("THIS
#   IS A BACKSTOP AND MUST NOT BECOME THE PRIMARY MECHANISM. If this AC's
#   condition is reached routinely on ordinary adopter trees, BP-1500g-1
#   has not been implemented and the build has merely become loud instead
#   of destructive."). The fixture those two test files use no longer
#   represents an unavoidable block once item-level merge exists -- flagged
#   here for test-writer/ticket-supervisor to re-target BP-1500g-1-ii's
#   tests at a scenario the merge genuinely cannot resolve (e.g. every
#   shipped name colliding, or a canonical directory that cannot be
#   enumerated at all), never resolved by weakening this AC's own tests.
#   (#BP-1500g-2)
# ====================================================================
