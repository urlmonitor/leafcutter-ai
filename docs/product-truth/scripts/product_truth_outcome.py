"""
MODULE: product_truth_outcome
GOAL: Decide and print the product-truth checker's run outcome -- the closed
    four-value vocabulary and the single JSON stdout line ADR-042 defines.
BUSINESS CONTEXT: A check that exits 0 cannot tell a caller whether it examined
    everything and found it sound, examined nothing, or examined only part of
    what it was given. ADR-042 answers that with one machine-readable line. This
    module is the one place its derivation and its printed shape live, so the
    rules a consumer depends on are read in one file rather than reconstructed
    from a 900-line checker. Split out of validate_product_truth.py, which was
    over its GE-127a-1 limit, when UXP-700c-1-i added a third input condition.
ARCHITECTURE: Pure functions and constants; nothing here reads the store.
    validate_product_truth imports and re-exports every name, so existing
    callers are unchanged.
"""
from __future__ import annotations

import json

from product_truth_checks import _ARTIFACT_TYPES

# The closed outcome vocabulary printed on the checker's final stdout line
# (ADR-042 §1). Consumers compare against exactly these four values.
_TOP_OUTCOME_SOUND = "checked-and-sound"
_TOP_OUTCOME_NOTHING = "nothing-examined"
_TOP_OUTCOME_DEGRADED = "degraded"
_TOP_OUTCOME_FAILED = "failed"


def record_check_executed(checks: list[dict], name: str, examined: int) -> None:
    """Append an executed-check entry recording how many records it examined.

    `checks` is the per-run bookkeeping list threaded through run_checks() (and
    built directly in unit tests). `examined` is the count of records this
    check actually inspected — the figure build_examined_total() sums across
    every executed entry.
    """
    checks.append({"name": name, "executed": True, "examined": examined})


def record_check_not_executed(
    checks: list[dict], name: str, reason: str, *, blocks: bool = False
) -> None:
    """Append a not-executed entry carrying a stated reason (GE-120, applied here).

    A check whose precondition is absent (e.g. the file it reads does not
    exist) must be visibly listed — never silently omitted, never left to
    crash the whole run — and must contribute exactly zero to any stated
    examined figure (see build_examined_total).

    *blocks* separates the two reasons a precondition can be missing, which
    the record cannot tell apart from the check's own point of view but which
    mean opposite things to a caller:

    * ``blocks=False`` — the input has simply not been AUTHORED yet. Expected
      of a young record; the run stays open and exits zero (UXP-700b-2-i).
    * ``blocks=True`` — the input was never INSTALLED, so the tooling itself
      is incomplete and no run against it can establish the record is sound.
      The run exits non-zero (UXP-700a-1-i).
    """
    checks.append({"name": name, "executed": False, "reason": reason, "blocks": blocks})


def build_examined_total(checks: list[dict]) -> int:
    """Sum the `examined` figure across executed checks only.

    Not-executed entries (record_check_not_executed) carry no `examined` key
    and are excluded from the sum, so an unexecuted check contributes nothing
    to any stated examined total — AC-2 of UXP-700b-2-i.
    """
    return sum(entry.get("examined", 0) for entry in checks if entry.get("executed"))


# Outcome sentinels returned by report_outcome(). Kept as named constants (not
# inlined) so main()'s branch on the "everything executed and sound" case can't
# accidentally match a degraded run by string coincidence.
_OUTCOME_SOUND = "checked-and-sound"
_OUTCOME_ERRORS = "checked-with-errors"
_OUTCOME_DEGRADED = "checked-with-unexecuted-checks"


def report_outcome(checks: list[dict], *, has_errors: bool = False) -> str:
    """Return the outcome sentinel for a completed check run.

    The checked-and-sound outcome is returned ONLY when every recorded check
    executed and there were no errors. If ANY check is listed as not executed,
    the outcome is never the checked-and-sound sentinel — even with zero
    errors — because part of the record was not actually checked (AC-3).
    """
    if any(not entry.get("executed", True) for entry in checks):
        return _OUTCOME_DEGRADED
    if has_errors:
        return _OUTCOME_ERRORS
    return _OUTCOME_SOUND


#: The record populations the checker reads, keyed by the name a check lists
#: in CHECK_READS. Built once per run from what that run actually loaded, so
#: no figure can outlive the run that produced it (UXP-700b-2).
POPULATIONS = ("flows", "mock-data", "mockups", "index", "acceptance-criteria")

#: For every check that runs unconditionally, the populations it reads. Its
#: stated figure is the sum of their sizes, so adding one record of a type it
#: reads raises that figure by exactly one and removing one lowers it by one
#: (UXP-700b-2). `eval` and `pointers` record their own finer figures -- eval
#: rows and pointers walked -- and are deliberately absent. A check added to
#: run_checks() without an entry here states no figure, which the tests for
#: UXP-700b-2 catch by name for the checks they know.
CHECK_READS: dict[str, tuple[str, ...]] = {
    "journey-shape": ("flows",),
    "example-data-shape": ("mock-data",),
    "screen-shape": ("mockups",),
    "example-data-refs": ("flows",),
    "index": ("index",),
    "impl-status": ("flows",),
    "product-truth-links": ("acceptance-criteria",),
    "derived-indexes": ("flows", "mock-data", "acceptance-criteria"),
    "screen-refs": ("flows",),
    "expansions": ("flows",),
    "shape-bounds": ("flows",),
    "artifact-paths": ("index",),
    "canonical-datasets": ("mock-data",),
    "truth-evidence": ("flows",),
}


def record_population_checks(checks: list[dict], sizes: dict[str, int]) -> None:
    """Record every CHECK_READS check as executed, examining the records it reads.

    Args:
        checks: The run's bookkeeping list.
        sizes: This run's size of each population in POPULATIONS.
    """
    for name, reads in CHECK_READS.items():
        record_check_executed(checks, name, sum(sizes[population] for population in reads))


def examined_by_check(checks: list[dict]) -> dict[str, int]:
    """Return {check name: records it read} for every check that executed.

    A check that did not execute read nothing and is listed as skipped
    instead, so it is left out here rather than reported as zero.
    """
    return {entry["name"]: entry["examined"] for entry in checks if entry.get("executed")}


def _compute_empty_types(flows: dict, mocks: dict, mockups: dict) -> list[str]:
    """Return the artifact types for which zero records were read.

    Names exactly the types with a zero count -- a type holding at least one
    record is never included, even when other types are empty (UXP-700b-1,
    UXP-700b-1-ii).
    """
    counts = {"flows": len(flows), "mock-data": len(mocks), "mockups": len(mockups)}
    return sorted(name for name in _ARTIFACT_TYPES if counts[name] == 0)


def _top_level_outcome(
    examined: int, unreadable: list[str], has_errors: bool, empty_types: list[str],
    unresolvable_pointers: int = 0,
) -> str:
    """Return the run outcome, applying ADR-042's conditions in a fixed order.

    1. Any real error -> 'failed'. Never masked by anything below.
    2. Any unreadable journey -> 'degraded' (UXP-700b-1-i): the run completed
       fail-open but did not read everything it was given.
    3. Every artifact type empty with nothing examined -> 'nothing-examined'
       (UXP-700b-1): a run that looked at nothing is not a sound one.
    4. Any pointer the checker could not classify -> 'degraded' (UXP-700c-1-i,
       ADR-042 Amendment 1 §A2): it did not establish that the record is sound.
    5. Otherwise -> 'checked-and-sound'.

    PARTIAL emptiness deliberately does not withhold the clean pass. A record
    holding journeys but no screens or example data yet is young, not defective;
    which types are empty is still reported, in ``empty_types``. This resolves
    UXP-700b-1-i against UXP-700b-1-ii by user decision (KI-ACD-20260909-2130)
    and supersedes the partial-emptiness clause of ADR-042 §A2.

    ``unresolvable_pointers`` is an explicit argument, never inferred from the
    others, so the condition that decides it stays visible at the one call site
    that decides the outcome (ADR-042 §A2).
    """
    if has_errors:
        return _TOP_OUTCOME_FAILED
    if unreadable:
        return _TOP_OUTCOME_DEGRADED
    if examined == 0 and len(empty_types) == len(_ARTIFACT_TYPES):
        return _TOP_OUTCOME_NOTHING
    if unresolvable_pointers:
        return _TOP_OUTCOME_DEGRADED
    return _TOP_OUTCOME_SOUND


def _print_outcome_contract(
    outcome: str, examined: int, unreadable: list[str], empty_types: list[str],
    resolved_pointers: int = 0, unresolvable_pointers: int = 0,
    examined_by_check: dict[str, int] | None = None,
) -> None:
    """Print the LAST stdout line: the machine-readable outcome contract.

    Printed with print(), independent of logging configuration, so a caller can
    always read the verdict from stdout alone (ADR-042 §3). Both pointer counts
    are emitted on every run, zeros included, so their absence never has to be
    interpreted (§A6). ``examined_by_check`` states how many records each
    performed check read (UXP-700b-2). Keys are additive: consumers read ``outcome`` and must not
    assert an exact key set.
    """
    print(json.dumps({
        "outcome": outcome,
        "examined": examined,
        "unreadable": unreadable,
        "empty_types": empty_types,
        "resolved_pointers": resolved_pointers,
        "unresolvable_pointers": unresolvable_pointers,
        "examined_by_check": examined_by_check or {},
    }))


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-14 [python-coder]: UXP-700c-1-i -- extracted the outcome vocabulary,
  _compute_empty_types, _top_level_outcome and _print_outcome_contract from
  validate_product_truth.py so the unresolvable-pointer condition could be added
  without growing that file past its GE-127b-1 ratchet. _top_level_outcome gains
  the explicit unresolvable_pointers argument and demotes to 'degraded' after the
  nothing-examined check; the payload gains resolved_pointers and
  unresolvable_pointers, both always present (ADR-042 Amendment 1 §A2, §A6).
  (#EPIC-TruthfulProjectRecord/20)
- 2026-09-14 [python-coder]: UXP-700b-2 -- the check bookkeeping (record_check_*,
  build_examined_total, report_outcome) moved here from the validator, and
  CHECK_READS maps every unconditional check to the populations it reads so each
  can state how many records it read; the figures go on the JSON line as
  examined_by_check. (#EPIC-TruthfulProjectRecord/14)
====================================================================
"""
