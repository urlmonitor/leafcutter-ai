"""
MODULE: _done_proof_automation_gate
GOAL: BO-2900a-3's THIRD reachability condition -- "no automation runs the
    unit as a program" -- plus the shared shape of the
    ``no_entry_point_reaches_code`` refusal verdict, including the
    ``clearing_actions`` field BO-2900a-3.yaml's own
    ``config_schema_fragment.no_way_in_verdict`` and this AC's "Delivers To"
    Agent Contract both require.
BUSINESS CONTEXT: ``_apply_reachability_gate`` (done_proof.py) refuses a unit
    with ``refusal_cause: "no_entry_point_reaches_code"`` only when ALL
    THREE of the AC's enumerated conditions hold: (1) the unit defines no
    ``main()`` of its own, (2) no other project module genuinely imports it,
    and (3) no automation script runs it as a program. Conditions (1) and
    (2) are established by ``_find_no_entry_point_unit`` /
    ``_is_imported_elsewhere`` in done_proof.py itself; this module answers
    condition (3) by delegating to the shared BO-2900b-1/BO-2900b-3
    automation-invocation seam (``collected_invocations`` from
    ``scripts/commit_guardian/_reachability_inventory``, the SAME seam
    ``_apply_reachability_gate`` already reaches for BO-2900d-1's
    ``is_exempt`` -- this module never opens a second import path to that
    package; the caller passes the already-imported function in). A unit
    that IS run as a program by a real automation script does not satisfy
    condition (3), so the refusal must not fire for it at all -- the
    verdict passes through unchanged, exactly like the pre-existing "no
    no-way-in unit found" and "unit is exempted" outcomes.

    ``build_no_entry_point_refusal`` centralises the refusal dict's shape so
    the ``clearing_actions`` field (the two ways the verdict flips: give the
    unit an entry point, or record an exemption) is defined in exactly one
    place rather than risking two call sites drifting apart on its wording.
ARCHITECTURE: A fourth sibling extraction out of done_proof.py, alongside
    _done_proof_phase_helpers.py and _done_proof_entry_point_gate.py, for
    the same file-size-ratchet reason -- done_proof.py has zero content-line
    headroom against its own HEAD length (BO-2900a-1's precedent). Follows
    _done_proof_entry_point_gate.py's own documented circular-import
    convention: done_proof.py imports this module's public functions at TOP
    LEVEL, so this module's own need for done_proof.py symbols
    (``_is_excluded_path``, ``_is_within``) is satisfied by a LOCAL
    ``from done_proof import ...`` inside the one function that needs them,
    never at this module's own top level. Added to build_ac_store's
    deploy_map in scripts/build_phases_ac_store.py in the same change, so
    the deployed check_done_proof hook (which imports done_proof, which
    imports this module) does not crash with ModuleNotFoundError.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable, Iterable

# The two named ways BO-2900a-3.yaml's config_schema_fragment.no_way_in_verdict
# says the no_entry_point_reaches_code refusal is cleared. Defined once here
# so the refusal dict and any future consumer (e.g. BO-2900e-1's message
# composer) read the identical wording.
CLEARING_ACTIONS: tuple[str, ...] = (
    "give the unit an entry point",
    "record an exemption",
)


def _automation_script_candidates(project_root: Path, test_root: Path) -> list[Path]:
    """Return the project-scoped set of ``.py`` files eligible to be scanned
    as automation scripts.

    Mirrors ``_is_imported_elsewhere``'s own ``project_root.rglob("*.py")``
    convention in done_proof.py: every project ``.py`` file EXCEPT those
    under an excluded scan directory (node_modules, .git, __pycache__, ...)
    or inside *test_root* (test-support code is not automation). No further
    narrowing is applied -- an ordinary project directory outside the test
    tree must never be excluded from this scan, or a real automation script
    living there would be silently invisible to condition (3).

    Args:
        project_root: Root directory bounding the scan.
        test_root: The project's test tree, excluded from the scan.

    Returns:
        Candidate automation-script paths. Empty when *project_root* cannot
        be scanned (fails closed to "no automation found" at the caller).
    """
    from done_proof import _is_excluded_path, _is_within

    try:
        candidates = list(project_root.rglob("*.py"))
    except OSError:
        return []
    return [
        candidate
        for candidate in candidates
        if not _is_excluded_path(candidate) and not _is_within(candidate, test_root)
    ]


def _resolve_candidate_path(candidate: str, project_root: Path) -> str | None:
    """Resolve *candidate* to a normalised, absolute path string, or ``None``.

    *candidate* is treated as relative to *project_root* when it is not
    already absolute, then resolved (``Path.resolve()``) and passed through
    ``os.path.normcase`` so drive-letter case and path-separator style
    (``/`` vs ``\\``) can never cause a false mismatch when comparing two
    resolved paths on Windows. Wrapped in its own ``try/except`` so one
    malformed literal (a *candidate* string that cannot be turned into a
    real filesystem path at all) can never crash the reachability gate --
    the caller treats ``None`` as "does not resolve, does not match" and
    simply skips that candidate rather than passing it through as a match.

    Args:
        candidate: A unit path or an invocation's ``surface`` string, either
            already absolute or relative to *project_root*.
        project_root: Root directory a relative *candidate* is resolved
            against.

    Returns:
        The normalised, absolute path string, or ``None`` when *candidate*
        cannot be resolved to a path.
    """
    try:
        candidate_path = Path(candidate)
        candidate_absolute = (
            candidate_path if candidate_path.is_absolute() else project_root / candidate_path
        )
        return os.path.normcase(str(candidate_absolute.resolve()))
    except (OSError, ValueError) as exc:
        print(
            f"WARNING: _done_proof_automation_gate: cannot resolve path "
            f"candidate {candidate!r}, skipping: {exc}",
            file=sys.stderr,
        )
        return None


def unit_is_invoked_by_automation(
    unit: str,
    project_root: Path,
    test_root: Path,
    collected_invocations: Callable[[Iterable[Path]], list] | None,
) -> bool:
    """True iff some automation script runs *unit* as a program.

    Established from EXECUTED invocations only -- the real, AST-based
    ``collected_invocations()`` scan over the derived automation-script set,
    never a text match of *unit*'s name or path (mirroring condition (2)'s
    own AST-only requirement). *unit* and each invocation's ``surface`` are
    independently resolved to a normalised, absolute path via
    :func:`_resolve_candidate_path` (a non-absolute ``surface`` is treated
    as relative to *project_root*, exactly like *unit* itself) and then
    compared via exact string equality -- no globs, prefixes, or basename
    matching, so a same-basename file at a different path never matches.

    Args:
        unit: The no-way-in candidate's path, as returned by
            ``_find_no_entry_point_unit`` (relative to *project_root* when
            possible, absolute otherwise).
        project_root: Root directory bounding the automation-script scan,
            and the base a non-absolute *unit* or invocation ``surface`` is
            resolved against.
        test_root: The project's test tree, excluded from the scan.
        collected_invocations: The real ``collected_invocations`` function
            already imported by the caller from the shared
            ``_reachability_inventory`` seam, or ``None`` when that seam is
            unavailable (fails closed to ``False`` -- an unreadable seam
            must never itself grant a pass).

    Returns:
        ``True`` iff a collected invocation's resolved ``surface`` exactly
        equals *unit*'s own resolved path.
    """
    if collected_invocations is None:
        return False
    unit_resolved = _resolve_candidate_path(unit, project_root)
    if unit_resolved is None:
        return False
    scripts = _automation_script_candidates(project_root, test_root)
    if not scripts:
        return False
    invocations = collected_invocations(scripts)
    for invocation in invocations:
        surface_resolved = _resolve_candidate_path(invocation.surface, project_root)
        if surface_resolved is not None and surface_resolved == unit_resolved:
            return True
    return False


def build_no_entry_point_refusal(verdict: dict, *, ac_id: str, unit: str) -> dict:
    """Build the ``no_entry_point_reaches_code`` refusal verdict for *unit*.

    Single source of this refusal's shape, including ``clearing_actions``
    (BO-2900a-3.yaml's ``config_schema_fragment.no_way_in_verdict`` and this
    AC's "Delivers To" Agent Contract) so ``check_done_proof.py`` and
    BO-2900e-1's message composer read a stable, complete verdict.

    Args:
        verdict: The eligibility verdict computed so far (used only to carry
            forward its ``passing_tests``/``failing_tests``/``dangling_tags``).
        ac_id: The AC identifier being evaluated (for the refusal message).
        unit: The no-way-in unit's path, as returned by
            ``_find_no_entry_point_unit``.

    Returns:
        An ``eligible: False`` verdict carrying ``refusal_cause``, ``unit``,
        and ``clearing_actions``.
    """
    return {
        "eligible": False,
        "reason": (
            f"no way of running the product reaches {unit} (refusal_cause: "
            f"no_entry_point_reaches_code) for {ac_id}"
        ),
        "refusal_cause": "no_entry_point_reaches_code",
        "unit": unit,
        "clearing_actions": list(CLEARING_ACTIONS),
        "passing_tests": verdict.get("passing_tests", []),
        "failing_tests": verdict.get("failing_tests", []),
        "dangling_tags": verdict.get("dangling_tags", []),
    }


# DECISION HISTORY
# ================================================================================
# - 2026-09-27 [python-coder/BO-2900a-3 rework]: Created this FOURTH sibling
#   module out of done_proof.py (alongside _done_proof_phase_helpers.py and
#   _done_proof_entry_point_gate.py) to answer condition (3) ("no automation
#   runs that unit as a program") against the now-merged BO-2900b-1/
#   BO-2900b-3 collected_invocations() seam, and to centralise the
#   no_entry_point_reaches_code refusal's shape so clearing_actions is
#   defined once. done_proof.py had ZERO content-line headroom against its
#   own HEAD length (measured via _file_size_ratchet.count_content_lines
#   before this change: current == HEAD == 1307), so this logic could not be
#   grown in place; collapsing _apply_reachability_gate's own 12-line
#   literal return dict into a single call to build_no_entry_point_refusal()
#   bought back the headroom the new automation-check call site needed, net
#   negative overall. Added to build_ac_store's deploy_map in
#   scripts/build_phases_ac_store.py in the same change. (#BO-2900a-3)
# - 2026-09-27 [python-coder/BO-2900a-3 rework round 3, pr-reviewer 21:57
#   blocker]: unit_is_invoked_by_automation previously compared an ABSOLUTE,
#   OS-native-separator unit_absolute against invocation.surface's VERBATIM
#   literal via bare ==, so a project-relative, forward-slash-authored
#   surface (the style this repo's own automation favours) never matched --
#   the unit was wrongly refused despite real automation running it.
#   Extracted _resolve_candidate_path(): both unit and each invocation
#   surface are now independently treated as project_root-relative when not
#   already absolute, resolved via Path.resolve(), and compared through
#   os.path.normcase() so drive-letter case and separator style can never
#   cause a mismatch on Windows -- still exact resolved-path equality, never
#   basename or prefix matching (test_relative_literal_naming_a_different_
#   same_basename_file_does_not_clear_the_refusal stays green). A malformed
#   surface literal that cannot resolve to a path is caught in
#   _resolve_candidate_path's own try/except and treated as "does not
#   match" rather than crashing the gate. (#BO-2900a-3)
# ================================================================================
