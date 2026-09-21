"""Classifier deciding whether a check's non-zero exit is an OBJECTION.

Extracted from ``test_ge_120e_2_i.py`` rather than grown in place. That file is
already over its size limit, and ``check-file-size`` (GE-127a-1/GE-127b-1)
refuses any edit that leaves an already-oversized file longer than it stood
before. Deleting the rationale below to buy the space was not an option — the
hook forbids exactly that, and the reasoning here is the substance of the
distinction, not decoration. Extraction is this branch's established answer to
that collision: move a cohesive unit out to a sibling instead of compressing it.

The unit is cohesive on its own terms. ``COULD_NOT_RUN_MARKERS`` and
``could_not_run`` answer one question that nothing else in the test file
answers, and the test file uses the predicate at exactly two call sites while
never touching the marker tuple directly.
"""

from __future__ import annotations

# Signals that a non-zero exit means "this check could not run here", NOT
# "this check inspected the change set and objected to something in it".
#
# This distinction is the whole point of GE-120a-1, and getting it wrong is
# what made this sweep accuse six checks of objecting to carried-in content
# when not one of them had inspected anything: two were handed no file
# argument and printed usage, two needed a product-truth store the second
# working copy does not carry, and two needed a fuller layout than the
# fixture provides. `exit != 0` is not an objection.
#
# The RESULT-line form is the epic's own machine-readable vocabulary
# (`check_outcome.OUTCOME_COULD_NOT_CHECK`) and is the form this should
# eventually rely on alone. The prose markers below are a documented
# INTERIM fallback for checks that have not adopted that vocabulary yet —
# adoption across the fleet is GE-120a-2/GE-120a-5's scope. Delete the
# fallback when it lands; do not grow it to paper over a real objection.
#
# `result: not_run` is the OTHER half of that machine-readable vocabulary
# (check_outcome.OUTCOME_NOT_RUN, added by UXP-700c-3-ii on 2026-09-09, two
# weeks after the marker list below was first written). run_hook.py emits it on
# the delegated check's behalf — `RESULT: not_run checker=<x> reason=<why>` —
# when the check's own process never started at all: the manifest switched it
# off, or its script could not be opened from the deployed layout. A check that
# never started inspected nothing, so by this AC's own Then-clause it "raises no
# objection"; and its report can name neither "the content it objected to" nor
# "the state that content came in from", which is the three-part shape this AC
# requires of a real objection. Counting it as one accuses a gate of rejecting
# work it was never even handed. It is still surfaced: could-not-run entries are
# named in the caller's assertion message, and the caller's `exercised` guard
# still fails a sweep that ran nothing.
COULD_NOT_RUN_MARKERS = (
    "could_not_check",
    "result: not_run",
    "usage:",
    "cannot read",
    "skipping",
    "no such file or directory",
    "modulenotfounderror",
    "importerror",
    "traceback (most recent call last)",
    "matches none of the",
)


def could_not_run(outcome) -> bool:
    """True when `outcome` shows the check never performed its inspection."""
    lowered = (outcome.output or "").lower()
    return any(marker in lowered for marker in COULD_NOT_RUN_MARKERS)
