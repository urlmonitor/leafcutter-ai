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
) -> None:
    """Print the LAST stdout line: the machine-readable outcome contract.

    Printed with print(), independent of logging configuration, so a caller can
    always read the verdict from stdout alone (ADR-042 §3). Both pointer counts
    are emitted on every run, zeros included, so their absence never has to be
    interpreted (§A6). Keys are additive: consumers read ``outcome`` and must not
    assert an exact key set.
    """
    print(json.dumps({
        "outcome": outcome,
        "examined": examined,
        "unreadable": unreadable,
        "empty_types": empty_types,
        "resolved_pointers": resolved_pointers,
        "unresolvable_pointers": unresolvable_pointers,
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
====================================================================
"""
