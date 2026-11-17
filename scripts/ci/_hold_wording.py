"""
MODULE: _hold_wording
GOAL: The output wording of the hold `Post-merge suite status` for every held state, so that
    the headlines (red, did_not_complete, stale, disabled, never_run, could_not_read, and the
    invalid-configuration variant of could_not_read) are pairwise different and each says the
    cause is not the pull request and how to restore a verdict.
BUSINESS CONTEXT: TQ-600a-13-xiv. A held pull request author must be able to tell from the
    output alone whether to fix their change (only for a red run), wait, or ask someone to act
    on the post-merge workflow, and what that action is.
ARCHITECTURE: Pure string builders, no I/O. Every reason is ``<headline>: <detail>. <NOT_THE_PR>
    To restore a verdict: <action>.`` The headline is the text before the first ``:``, ``(``,
    ``.`` or ``;``. ``RESTORE_ACTIONS`` is the single source of the action per state: the
    reasons here and the pull request comment (``_hold_comment``) both read it. ``could_not_read``
    keeps the -ix headline ``UNREADABLE_HEADLINE`` (``post_merge_hold`` imports it from here) and
    appends the two sentences after its cause; ``config_invalid_reason`` is its own headline for a
    refused tunables file, still in state ``could_not_read``. This module owns only the words; the
    verdicts are ``post_merge_hold``'s.
"""

from __future__ import annotations

UNREADABLE_HEADLINE = "Post-merge run history could not be read"  # shared with no other state
CONFIG_HEADLINE = "Post-merge hold configuration is invalid"
NOT_THE_PR = "This is not caused by this pull request."
TUNABLES_PATH = "scripts/ci/post_merge_tunables.json"
DISPATCH = "dispatch the post-merge correctness workflow on main"
RESTORE_ACTIONS = {
    "red": "fix main so the suite is green again, or declare the fix in a pull request with a passing fix proof (Fixes #<notice>)",
    "did_not_complete": "re-run the post-merge suite on main until it completes",
    "stale": DISPATCH,
    "disabled": "re-enable the post-merge correctness workflow",
    "never_run": "wait for the first run to complete, or dispatch it",
    "could_not_read": "re-run this check once the read succeeds",
    "config_invalid": f"edit {TUNABLES_PATH} so that staleness_hours is greater than heartbeat_max_hours",
}


def restore_sentence(key: str) -> str:
    """The closing sentence for ``key``: how a verdict is restored."""
    return f"To restore a verdict: {RESTORE_ACTIONS[key]}."


def held_reason(kind_is_red: bool, run: dict) -> str:
    """The output line for a held run: red (the tests failed) or did-not-complete, with the run's link and conclusion."""
    link, conclusion = run.get("html_url"), run.get("conclusion")
    if kind_is_red:
        return f"Post-merge suite is not green: run {link} concluded {conclusion}; the tests failed. {NOT_THE_PR} {restore_sentence('red')}"
    return f"Post-merge suite run did not finish: run {link} concluded {conclusion}; the run did not complete. {NOT_THE_PR} {restore_sentence('did_not_complete')}"


def stale_reason(run: dict, age_hours: float, limit_hours: float) -> str:
    """Stale: the latest settled run's own start time and its age (one decimal, so it never reads equal to the limit) against the bound."""
    return (
        f"Post-merge verdict is stale: the latest run {run.get('html_url')} started {run.get('run_started_at')} "
        f"({age_hours:.1f} h ago, limit {limit_hours:g} h). {NOT_THE_PR} {restore_sentence('stale')}"
    )


def no_settled_reason(page: int) -> str:
    """Stale because none of the most recent ``page`` runs has settled."""
    return f"Post-merge verdict is stale: no settled run among the most recent {page} runs on main. {NOT_THE_PR} {restore_sentence('stale')}"


def disabled_reason(workflow_state: str) -> str:
    """Disabled: the state the workflow reported, verbatim."""
    return f"Post-merge suite workflow is disabled and not active (state: {workflow_state}). {NOT_THE_PR} {restore_sentence('disabled')}"


def never_run_reason() -> str:
    """Never run: nothing has settled, so there is no verdict."""
    return f"Post-merge suite has never run on main: no post-merge run has ever completed, so there is no verdict. {NOT_THE_PR} {restore_sentence('never_run')}"


def could_not_read_reason(cause: str) -> str:
    """Could not read: the -ix headline, the cause, then the two sentences every held state carries."""
    return f"{UNREADABLE_HEADLINE}: {cause}. {NOT_THE_PR} {restore_sentence('could_not_read')}"


def config_invalid_reason(detail: str) -> str:
    """A refused tunables file: its own headline, the file, both keys and both values (in ``detail``), and the edit that restores it."""
    return f"{CONFIG_HEADLINE}: {detail}. {NOT_THE_PR} {restore_sentence('config_invalid')}"
