#!/usr/bin/env python3
"""
MODULE: _gtfa_phases
GOAL: Resolve which phase agents the build drive will NOT dispatch for a
    ticket at a given location, from the location-keyed declaration in
    ``config/phase_deferral.yaml`` (TKT-600b-1).
BUSINESS CONTEXT: An epic member's own pull-request phase is superseded by the
    one epic-level PR, so the drive never dispatches it — but a generated
    ticket that still records ``pull-request: needed`` makes the record and the
    drive disagree about what will run, and the ticket can never reach done.
    The declaration is the single place both sides read, so neither side
    carries a literal phase name in its logic.
ARCHITECTURE: A missing or malformed declaration REFUSES generation rather than
    falling back to a built-in phase set — that is the whole constraint
    TKT-600b-1 exists to hold, and it is why the two error types below are
    distinct exception classes rather than a bare ValueError: ``main()`` has to
    tell "the declaration is missing or broken" apart from "the AC is
    malformed" and from "a CLI argument is absent". Silence about the ticket's
    final location also refuses, because defaulting to ``standalone`` on
    silence would classify every epic member as standalone and silently restore
    the exact defect the mechanism removes.
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path

import yaml

# See the "Sibling wiring" note in generate_ticket_from_ac.py for why the
# sibling package prefix is derived from __name__ rather than hard-coded.
_PKG = __name__.rpartition(".")[0]
_gtfa_seams = importlib.import_module(f"{_PKG}._gtfa_seams" if _PKG else "_gtfa_seams")
_gtfa_constants = importlib.import_module(
    f"{_PKG}._gtfa_constants" if _PKG else "_gtfa_constants"
)

logger = logging.getLogger(_gtfa_seams.logger_name())

_DEFAULT_PHASE_DEFERRAL = _gtfa_constants._DEFAULT_PHASE_DEFERRAL


# ---------------------------------------------------------------------------
# Phase-deferral declaration (TKT-600b-1)
# ---------------------------------------------------------------------------


class PhaseDeferralDeclarationError(Exception):
    """Raised when the location-keyed phase-deferral declaration cannot be
    loaded or is malformed.

    Deliberately a distinct exception type (not a bare ValueError/OSError) so
    that a caller — chiefly ``main()`` — can tell "the declaration is missing
    or broken" apart from a malformed AC record or a missing CLI argument
    (TKT-600b-1-i's "distinguishable in kind" requirement). A missing
    declaration must refuse generation rather than silently fall back to a
    built-in default (TKT-600b-1).
    """


class UnresolvedDestinationError(Exception):
    """Raised when the phase-deferral declaration is location-dependent (it
    defers a different phase set for at least two location kinds) but no
    ``resolved_destination`` was supplied, so the phase record cannot be
    soundly computed without guessing the ticket's final location
    (TKT-600b-1-i).
    """


def _default_phase_deferral_path() -> Path:
    """Resolve the default location of config/phase_deferral.yaml.

    Mirrors the fallback pattern already used for the guardrail-gates config:
    resolves relative to the discovered worktree root when possible, and
    falls back to a path relative to the current working directory when no
    ``.git`` marker can be found.

    Returns:
        Absolute (or best-effort relative) path to config/phase_deferral.yaml.
    """
    try:
        repo_root = _gtfa_seams.find_worktree_root(Path(__file__))
    except FileNotFoundError:
        return Path(_DEFAULT_PHASE_DEFERRAL)
    return repo_root / _DEFAULT_PHASE_DEFERRAL


def _load_phase_deferral(path: Path) -> dict[str, list[str]]:
    """Load the location-keyed phase-deferral declaration (TKT-600b-1).

    Args:
        path: Path to the declaration YAML (e.g. config/phase_deferral.yaml).

    Returns:
        Mapping of location kind (e.g. ``"epic_member"``, ``"standalone"``)
        to the list of phase-agent names deferred (not dispatched by the
        drive) at that location.

    Raises:
        PhaseDeferralDeclarationError: When the file cannot be read/parsed,
            or does not contain a YAML mapping. Deliberately never caught and
            defaulted internally — a missing declaration must refuse
            generation rather than silently substitute a built-in phase set
            (TKT-600b-1's "must refuse rather than default" constraint).
    """
    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except (OSError, yaml.YAMLError) as exc:
        raise PhaseDeferralDeclarationError(
            f"could not load phase deferral declaration at {path}: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise PhaseDeferralDeclarationError(  # noqa: TRY003
            f"phase deferral declaration at {path} must be a YAML mapping, "
            f"got {type(data).__name__}"
        )
    return data


def _location_kind_for_destination(resolved_destination: str) -> str:
    """Classify a resolved ticket destination into a phase_deferral.yaml key.

    Args:
        resolved_destination: Repo-relative path the ticket will finally
            occupy.

    Returns:
        ``"epic_member"`` when the path contains an ``"epics"`` path segment
        (i.e. the ticket lives under ``tickets/**/epics/EPIC-*/``); otherwise
        ``"standalone"``.
    """
    return "epic_member" if "epics" in Path(resolved_destination).parts else "standalone"


def _deferral_for_declared_kind(
    declaration: dict[str, list[str]],
    location_kind: str,
    resolved_destination: "str | None",
    path: Path,
) -> set[str]:
    """Resolve the deferred set for an explicitly DECLARED location kind.

    This is the path a caller takes when it knows what it is building but not
    where the file will finally sit — /build-ac generating a loose ticket knows
    it is standalone without knowing a folder. It is deliberately a declaration
    and NOT a default: defaulting to "standalone" when nobody says would
    classify every epic member as standalone (no caller passes a destination
    today), silently restoring the exact `pull-request: needed` defect TKT-600b
    exists to remove. A caller must state its case; silence still refuses.

    Args:
        declaration: The parsed phase-deferral declaration.
        location_kind: The caller's declared location kind.
        resolved_destination: The caller's destination, when it also gave one.
        path: Declaration path, for error messages.

    Returns:
        Set of phase-agent names deferred for this location kind.

    Raises:
        UnresolvedDestinationError: When *location_kind* is not a key of the
            declaration, or when a *resolved_destination* was ALSO supplied and
            classifies as a different kind.
    """
    if location_kind not in declaration:
        raise UnresolvedDestinationError(
            f"unknown location kind {location_kind!r}; the declaration at "
            f"{path} names {sorted(declaration)}"
        )
    if resolved_destination is not None:
        derived = _location_kind_for_destination(resolved_destination)
        if derived != location_kind:
            # Both were supplied and they disagree. The generator can see
            # the contradiction, so it must not silently pick a winner.
            raise UnresolvedDestinationError(
                f"contradictory location: --location-kind says "
                f"{location_kind!r} but --resolved-destination "
                f"{resolved_destination!r} classifies as {derived!r}"
            )
    return set(declaration.get(location_kind, []) or [])


def _resolve_deferred_phases(
    resolved_destination: "str | None",
    phase_deferral_path: "Path | str | None",
    location_kind: "str | None" = None,
) -> set[str]:
    """Resolve the set of phase agents deferred for one generation call.

    Loads the location-keyed deferral declaration and returns the phase set
    that applies to *resolved_destination*. When the declaration defers the
    SAME set (including an empty set) for every location kind it names, the
    location does not actually matter for this call, and the single common
    set is returned even when *resolved_destination* is ``None`` — this is
    TKT-600b-1-i's "a generation whose declared deferral set is empty for
    every location has nothing to resolve and must not be blocked"
    exemption, generalised to "identical for every location" rather than
    hard-coded to "empty".

    Args:
        resolved_destination: The ticket's final repo-relative location, or
            ``None`` when unresolved.
        phase_deferral_path: Path to the declaration YAML, or ``None`` to use
            :func:`_default_phase_deferral_path`.
        location_kind: An explicitly declared location kind, or ``None``.

    Returns:
        Set of phase-agent names deferred for this call.

    Raises:
        PhaseDeferralDeclarationError: propagated from :func:`_load_phase_deferral`.
        UnresolvedDestinationError: the declaration defers a different phase
            set per location (location-dependent) and *resolved_destination*
            is ``None``.
    """
    path = (
        Path(phase_deferral_path)
        if phase_deferral_path is not None
        else _default_phase_deferral_path()
    )
    declaration = _load_phase_deferral(path)
    location_sets = [frozenset(v or []) for v in declaration.values()]

    if location_kind is not None:
        return _deferral_for_declared_kind(
            declaration, location_kind, resolved_destination, path
        )

    if resolved_destination is not None:
        derived_kind = _location_kind_for_destination(resolved_destination)
        return set(declaration.get(derived_kind, []) or [])

    if len(set(location_sets)) > 1:
        affected = sorted(set().union(*location_sets))
        raise UnresolvedDestinationError(
            "the ticket's final location is unresolved and the phase "
            "deferral declaration is location-dependent; the phase(s) "
            f"whose status could not be determined: {affected}"
        )

    # Every declared location defers the same (possibly empty) set — there is
    # nothing location-specific to resolve, so proceed without a destination.
    return set(location_sets[0]) if location_sets else set()
