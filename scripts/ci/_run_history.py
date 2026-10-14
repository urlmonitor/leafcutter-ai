"""
MODULE: _run_history
GOAL: The ONE rule that decides which run of ``post-merge-suite.yml`` carries
    the main-branch verdict, given a page of workflow runs as the REST API
    serves them. Every consumer of the run history imports it; none re-implements it.
BUSINESS CONTEXT: TQ-600a-13-ii. The post-merge run is coalesced (one in
    progress, one waiting, a newer waiting run replaces an older one, which ends
    ``cancelled``). A run cancelled that way tested nothing and carries no
    verdict; a lone cancellation with no newer run is a real did-not-complete.
    A run of the same workflow file on a pull-request branch must never be read
    as a verdict on main.
ARCHITECTURE: Pure and stdlib-only (the hold job installs nothing and this
    module must import without pytest, PyYAML or any dev dependency). Input is
    the ``workflow_runs`` list; order comes from ``run_number`` and never from
    list position. Output is a ``Selection``: ``kind`` (settled | never_run |
    no_settled_in_page), the chosen ``run`` dict (or None) and ``skipped``, the
    newer runs passed over, each ``{"id", "reason"}`` with reason one of
    superseded_cancellation | not_completed | not_main. ``classify_run``
    (TQ-600a-13-v) says whether a settled run is green, red or did_not_complete
    from its conclusion and its jobs list. TQ-600a-13-xv extends this module with
    verdict-change detection; keep this the single settled-run rule.
"""

from __future__ import annotations

from dataclasses import dataclass, field

MAIN_EVENTS = frozenset({"push", "schedule", "workflow_dispatch"})
MAIN_BRANCH = "main"

KIND_SETTLED = "settled"
KIND_NEVER_RUN = "never_run"
KIND_NO_SETTLED = "no_settled_in_page"

REASON_SUPERSEDED = "superseded_cancellation"
REASON_NOT_COMPLETED = "not_completed"
REASON_NOT_MAIN = "not_main"

VERDICT_GREEN = "green"
VERDICT_RED = "red"
VERDICT_DID_NOT_COMPLETE = "did_not_complete"
RED_STEP = "Verdict: red"


@dataclass(frozen=True)
class Selection:
    """The outcome of reading one page of runs: the verdict run (if any) and what was passed over."""

    kind: str
    run: dict | None = None
    skipped: list = field(default_factory=list)


def tested_main(run: dict) -> bool:
    """Return True when the run tested the main branch (event and head branch both qualify)."""
    return run.get("event") in MAIN_EVENTS and run.get("head_branch") == MAIN_BRANCH


def select_verdict_run(runs: list[dict]) -> Selection:
    """Pick the newest settled main-branch run from a page of runs, newest first by ``run_number``."""
    ordered = sorted(runs, key=lambda r: r.get("run_number", 0), reverse=True)
    main_numbers = [r.get("run_number", 0) for r in ordered if tested_main(r)]
    skipped: list[dict] = []
    for run in ordered:
        reason = _skip_reason(run, main_numbers)
        if reason is None:
            return Selection(KIND_SETTLED, run, skipped)
        skipped.append({"id": run.get("id"), "reason": reason})
    return Selection(KIND_NO_SETTLED if main_numbers else KIND_NEVER_RUN, None, skipped)


def _red_step_failed(jobs: list[dict] | None) -> bool:
    """Return True when some job's step named exactly ``Verdict: red`` concluded failure."""
    for job in jobs or []:
        for step in job.get("steps") or []:
            if step.get("name") == RED_STEP and step.get("conclusion") == "failure":
                return True
    return False


def classify_run(run: dict, jobs: list[dict] | None) -> str:
    """Classify a settled run as ``green``, ``red`` or ``did_not_complete``.

    Green is a positive finding: only the conclusion ``success``. Red needs the conclusion ``failure``
    AND the verdict job's ``Verdict: red`` step to have failed. Every other ending (cancelled, timed
    out, could not start, a failed setup, the ``Verdict: did not complete`` step, no verdict job at
    all, an unknown conclusion) did not complete. ``jobs`` is the ``jobs`` list of
    ``GET /actions/runs/{id}/jobs?filter=latest``; it is only consulted for a failure.
    """
    conclusion = run.get("conclusion")
    if conclusion == "success":
        return VERDICT_GREEN
    if conclusion == "failure" and _red_step_failed(jobs):
        return VERDICT_RED
    return VERDICT_DID_NOT_COMPLETE


def verdict_changed(runs: list[dict], triggering_run_id: int) -> bool | None:
    """Say whether the triggering run's verdict differs from the previous settled run's (TQ-600a-13-xv).

    None when the triggering run is unknown or not settled (superseded, unfinished, not a main run), or when
    there is no previous settled run: nothing is then re-evaluated. Otherwise True exactly when one of the two is
    green (conclusion ``success``) and the other is not; red, did-not-complete, timed out and cancelled are all
    "held", so held followed by held is False. Uses ``_skip_reason``, the one settled-run rule.
    """
    trigger = next((r for r in runs if r.get("id") == triggering_run_id), None)
    if trigger is None:
        return None
    main_numbers = [r.get("run_number", 0) for r in runs if tested_main(r)]
    if _skip_reason(trigger, main_numbers) is not None:
        return None
    number = trigger.get("run_number", 0)
    older = sorted((r for r in runs if r.get("run_number", 0) < number), key=lambda r: r.get("run_number", 0), reverse=True)
    previous = next((r for r in older if _skip_reason(r, main_numbers) is None), None)
    if previous is None:
        return None
    return (trigger.get("conclusion") == "success") != (previous.get("conclusion") == "success")


def _skip_reason(run: dict, main_numbers: list[int]) -> str | None:
    """Return why this run carries no verdict, or None when it is settled."""
    if not tested_main(run):
        return REASON_NOT_MAIN
    if run.get("status") != "completed":
        return REASON_NOT_COMPLETED
    if run.get("conclusion") == "cancelled" and any(n > run.get("run_number", 0) for n in main_numbers):
        return REASON_SUPERSEDED
    return None
