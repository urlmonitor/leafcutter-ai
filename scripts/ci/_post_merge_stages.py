"""
MODULE: _post_merge_stages
GOAL: Name the stage at which a post-merge correctness-lane run stopped, from
    the first-run report and from what the hosting service says about the run
    and retry jobs. Pure and stdlib-only.
BUSINESS CONTEXT: TQ-600a-13-v. A run that broke before it tested anything must
    never read as a run with no failures: green is a positive finding, and every
    input this module does not recognise ends as a did-not-complete stage, never
    as "no stage".
ARCHITECTURE: ``lane_stage`` is the only entry point the verdict builder calls.
    It first decides from the dependency results (cancelled, setup failure,
    unreadable report, failed retry), then from the content of a readable report
    (collection errors, aborted session, empty selection, truncated session,
    inconsistent exit status, nothing passed, mostly skipped). A collection error is
    a stage of its own and is never counted as a failing test.
    ``stage_from_conclusion`` is the fallback for a run that left no artifact at
    all (cancelled, timed out, could not start): the run's own conclusion is
    the only evidence there is.
"""

from __future__ import annotations

STAGE_SETUP = "setup"
STAGE_COLLECTION = "collection"
STAGE_EMPTY_SELECTION = "empty_selection"
STAGE_RETRY_FAILED = "retry_failed"
STAGE_CANCELLED = "cancelled_or_timed_out"
STAGE_STARTUP_FAILURE = "startup_failure"
STAGE_UNREADABLE = "result_unreadable"
STAGE_UNKNOWN = "unknown"
STAGE_ABORTED = "pytest_aborted"
STAGE_TRUNCATED = "truncated"
STAGE_INCONSISTENT_EXIT = "exit_status_without_failures"
STAGE_NOTHING_PASSED = "nothing_passed"
STAGE_MOSTLY_SKIPPED = "mostly_skipped"

ABORTED_EXIT_STATUSES = frozenset({2, 3, 4})
FAILED_STATES = frozenset({"failed", "error"})
REPORT_OK, REPORT_ABSENT, REPORT_UNREADABLE = "ok", "absent", "unreadable"
JOB_RESULTS = frozenset({"success", "failure", "cancelled", "skipped"})  # the values `needs.<job>.result` can take


def normalize_job_result(value: str | None) -> str:
    """Return a job result the runner can produce, or ``unknown`` for a missing, empty or unrecognised one."""
    return value if value in JOB_RESULTS else STAGE_UNKNOWN

# The runner cannot tell a cancellation from a timeout (a job past ``timeout-minutes`` reports
# ``cancelled``), so both are one stage rather than a guess.
_CONCLUSION_STAGES = {"cancelled": STAGE_CANCELLED, "timed_out": STAGE_CANCELLED, "startup_failure": STAGE_STARTUP_FAILURE}


def stage_from_conclusion(conclusion: str | None) -> str:
    """Return the stage a run with no artifact is given, from its own conclusion; unknown otherwise."""
    return _CONCLUSION_STAGES.get(conclusion or "", STAGE_UNKNOWN)


def _missing_report_stage(first_state: str, run_result: str) -> str:
    """Return the stage of a run whose first-run report cannot be used."""
    if first_state == REPORT_UNREADABLE:
        return STAGE_UNREADABLE
    if run_result == "failure":
        return STAGE_SETUP
    if run_result == "success":
        return STAGE_UNREADABLE
    return STAGE_UNKNOWN


def _dependency_stage(first: dict | None, run_result: str, retry_result: str, first_state: str) -> str | None:
    """Return the stage the dependency results alone decide, or None when the report must be read."""
    if "cancelled" in (run_result, retry_result):
        return STAGE_CANCELLED
    if first is None:
        return _missing_report_stage(first_state, run_result)
    if run_result not in ("", "success"):
        return STAGE_UNKNOWN
    return None


def report_stage(first: dict) -> str | None:
    """Return why a readable first-run report is not a finished lane, or None when it is.

    Rules, in order: a collection error (wins over an aborted session, the cause is what a reader
    needs); pytest aborted (exit status 2 interrupted, 3 internal error, 4 usage error); nothing
    collected; fewer tests reported than were selected (pytest.exit or a crash cut the session
    short); exit status 1 although no test failed; no test passed and none failed (all skipped; a
    one-test lane whose only test fails is red, or green when the retry passes it); more than half of
    the tests skipped (a missing prerequisite hollowed the lane out).
    """
    results = first.get("results", {})
    statuses = list(results.values())
    if first.get("collection_errors"):
        return STAGE_COLLECTION
    if first.get("exitstatus") in ABORTED_EXIT_STATUSES:
        return STAGE_ABORTED
    if not results:
        return STAGE_EMPTY_SELECTION
    if first.get("ran", len(results)) < first.get("expected", 0):
        return STAGE_TRUNCATED
    if first.get("exitstatus") == 1 and not any(s in FAILED_STATES for s in statuses):
        return STAGE_INCONSISTENT_EXIT
    if "passed" not in statuses and not any(s in FAILED_STATES for s in statuses):
        return STAGE_NOTHING_PASSED  # a failure is a finding (red, or green if the retry passes it), not an empty lane
    if statuses.count("skipped") * 2 > len(statuses):
        return STAGE_MOSTLY_SKIPPED
    return None


def _retry_stage(first: dict, retry: dict | None, retry_result: str) -> str | None:
    """Return the stage of a retry that did not confirm the first-run failures, or None."""
    if not any(status in FAILED_STATES for status in first.get("results", {}).values()):
        return None
    if retry_result == STAGE_UNKNOWN:  # the caller could not read the retry job's result
        return STAGE_UNKNOWN
    if retry_result == "failure":
        return STAGE_RETRY_FAILED
    if retry_result == "success" and retry is None:
        return STAGE_UNREADABLE
    return None


def lane_stage(
    first: dict | None,
    retry: dict | None = None,
    *,
    run_result: str = "",
    retry_result: str = "",
    first_state: str = REPORT_ABSENT,
) -> str | None:
    """Return the stage at which the run stopped, or None when it ran to completion.

    ``run_result`` / ``retry_result`` are the ``needs.<job>.result`` values (success | failure |
    cancelled | skipped), "" when unknown. ``first_state`` says whether a missing ``first`` was
    absent or present but unreadable (corrupt, truncated).
    """
    early = _dependency_stage(first, run_result, retry_result, first_state)
    if early or first is None:
        return early
    return report_stage(first) or _retry_stage(first, retry, retry_result)
