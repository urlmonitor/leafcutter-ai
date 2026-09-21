"""
MODULE: product_truth_bounds
GOAL: Declare a reviewable size for the fields of each thing the record holds --
    a journey, an example dataset, a screen -- measure every artifact against
    it, and decide from the record alone whether each bound still warns or
    now blocks (UXP-700e-1, UXP-700e-1-ii).
BUSINESS CONTEXT: A record nobody can read in one sitting stops being reviewed,
    and an unreviewed record is where drift hides. No size limit existed in any
    artifact shape (measured 2026-09-07). A bound introduced today would fail
    the store on the day it lands -- a 120-character description cap fails all
    14 journeys -- so every bound arrives behind a shape version: an artifact
    declaring that version is held to it, one predating it is warned about
    (UXP-700e-1-i). The warning period ends when, and only when, nothing in the
    record is still on an older shape version. That decision is read from the
    artifacts every run: there is no date after which a bound tightens and no
    flag that can tighten it, so the rollout cannot be declared finished before
    the backfill is.
    Each bound also states how many artifacts it measured, so a bound that
    measured nothing is told apart from one nothing exceeded (UXP-700b-2's
    convention).
ARCHITECTURE: Pure, stateless leaf module: BOUNDS is the one declaration, and
    check_bounds() mutates the shared errors / warnings lists like every other
    check. tightening_holdouts() is the single rule both the per-run
    enforcement and the checker's --tighten request go through, so the two
    cannot disagree.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

#: Enforcement states a bound can be in. Derived per run, never stored.
ENFORCEMENT_WARNING_PERIOD = "warning-period"
ENFORCEMENT_BLOCKING = "blocking"

#: What each population's artifacts are called in a finding.
_KIND = {"flows": "journey", "mock-data": "dataset", "mockups": "screen"}


def _length(field: str) -> Callable[[dict], int | None]:
    return lambda artifact: len(artifact[field]) if isinstance(artifact.get(field), (str, list)) else None


def _largest_entity_records(artifact: dict) -> int | None:
    entities = artifact.get("entities")
    if not isinstance(entities, dict) or not entities:
        return None
    return max(len(entity.get("records") or []) for entity in entities.values())


@dataclass(frozen=True)
class Bound:
    """One declared size bound on one field of one artifact type."""

    name: str
    population: str
    field: str
    unit: str
    limit: int
    effective_shape_version: int
    measure: Callable[[dict], int | None]


#: Every declared bound. The description bound is the one the measurement
#: motivated. The others are set above today's largest value (18 steps, 10
#: records per entity, a 527-character screen summary), so they cap further
#: growth without adding a finding on the day they land.
BOUNDS: tuple[Bound, ...] = (
    Bound("journey-description-length", "flows", "summary", "characters", 120, 2, _length("summary")),
    Bound("journey-step-count", "flows", "steps", "items", 20, 2, _length("steps")),
    Bound("dataset-records-per-entity", "mock-data", "entities.*.records", "items", 50, 2, _largest_entity_records),
    Bound("screen-description-length", "mockups", "summary", "characters", 600, 2, _length("summary")),
)


def bound_named(name: str) -> Bound | None:
    """Return the declared bound called *name*, or None."""
    return next((bound for bound in BOUNDS if bound.name == name), None)


def tightening_holdouts(bound: Bound, artifacts: dict) -> list[str]:
    """Return the artifacts still on a shape version older than *bound*'s, sorted.

    An artifact declaring no shape_version counts as older. An empty result is
    the one condition under which the bound may block every artifact; nothing
    else -- no date, no flag -- is consulted.
    """
    return sorted(
        artifact_id for artifact_id, artifact in artifacts.items()
        if not isinstance(artifact.get("shape_version"), int)
        or artifact["shape_version"] < bound.effective_shape_version
    )


def check_bounds(populations: dict[str, dict], errors: list[str], warnings: list[str],
                 bounds: tuple[Bound, ...] = BOUNDS) -> dict[str, dict]:
    """Measure every artifact against every bound and report what exceeds one.

    Within a bound nothing is reported. Over it, an artifact declaring the
    bound's shape version or later is an error; one declaring an older version,
    or none, is a warning -- unless the bound has left its warning period, which
    by construction means no such artifact exists.

    Args:
        populations: ``{population name -> {artifact id -> artifact}}``.
        errors: Shared error list.
        warnings: Shared warning list.
        bounds: The bounds to apply; defaults to every declared bound.

    Returns:
        ``{bound name -> {measured, exceeded, enforcement, holdouts}}``, where
        *holdouts* lists the artifacts keeping the bound in its warning period.
    """
    report: dict[str, dict] = {}
    for bound in bounds:
        artifacts = populations.get(bound.population) or {}
        holdouts = tightening_holdouts(bound, artifacts)
        measured = exceeded = 0
        for artifact_id in sorted(artifacts):
            artifact = artifacts[artifact_id]
            size = bound.measure(artifact)
            if size is None:
                continue
            measured += 1
            if size <= bound.limit:
                continue
            exceeded += 1
            _report_exceeding(bound, artifact_id, artifact, size, errors, warnings)
        report[bound.name] = {
            "measured": measured, "exceeded": exceeded, "holdouts": holdouts,
            "enforcement": ENFORCEMENT_WARNING_PERIOD if holdouts else ENFORCEMENT_BLOCKING,
        }
    return report


def _report_exceeding(bound: Bound, artifact_id: str, artifact: dict, size: int,
                      errors: list[str], warnings: list[str]) -> None:
    """File one over-bound artifact as an error or a warning by its shape_version."""
    kind = _KIND.get(bound.population, "artifact")
    head = (f"[shape] {artifact_id}: {bound.field} is {size} {bound.unit}, over the "
            f"{bound.limit}-{bound.unit.rstrip('s')} bound '{bound.name}'")
    version = artifact.get("shape_version")
    if not isinstance(version, int):
        warnings.append(f"{head}, but the {kind} declares no shape_version — it needs a shape_version "
                        f"before the bound can be applied to it")
    elif version < bound.effective_shape_version:
        warnings.append(f"{head}, but the {kind} declares shape_version {version}, which predates the bound "
                        f"(effective at shape_version {bound.effective_shape_version}) — not blocked")
    else:
        errors.append(f"{head} this {kind} is held to at shape_version {version}")


def tighten_refusal(bound_name: str, report: dict[str, dict]) -> str | None:
    """Return why *bound_name* cannot be tightened, or None when it can.

    Args:
        bound_name: The bound a caller asked to hold as blocking.
        report: This run's check_bounds() result.
    """
    entry = report.get(bound_name)
    if entry is None:
        return f"no declared bound is named '{bound_name}' (declared: {', '.join(b.name for b in BOUNDS)})"
    if entry["holdouts"]:
        return (f"bound '{bound_name}' cannot be tightened: {len(entry['holdouts'])} artifact(s) still on a shape "
                f"version older than the one it took effect in: {', '.join(entry['holdouts'])}")
    return None


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-14 [python-coder]: UXP-700e-1 / UXP-700e-1-ii -- new module. The
  single description bound UXP-700e-1-i hard-coded in product_truth_checks.py
  becomes one entry in BOUNDS, alongside a bound for each artifact type the AC
  names. Every bound reports how many artifacts it measured. Tightening is not a
  stored state: a bound blocks every artifact exactly when tightening_holdouts()
  is empty, recomputed from the artifacts each run, and --tighten is a request
  that is refused, naming the holdouts, while it is not. Considered and
  rejected: a `tightened: true` flag in a config file (a hand edit would end the
  warning period with the backfill unfinished) and a sunset date (a date passes
  whether or not anyone backfilled). (#EPIC-TruthfulProjectRecord/38, /40)
====================================================================
"""
