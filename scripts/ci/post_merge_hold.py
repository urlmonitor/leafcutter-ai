#!/usr/bin/env python3
"""
MODULE: post_merge_hold
GOAL: The verdict of the per-PR check `Post-merge suite status`: a pull request
    to main is held while the latest settled run of ``post-merge-suite.yml`` on
    main is not green, has no fresh verdict, or its workflow is not active.
BUSINESS CONTEXT: TQ-600a-13-vi. The expensive tests left the per-PR path to
    remove their cost from it, so this check reads the run history and runs
    nothing: no test session, no build, no checkout or execution of pull-request
    code. The verdict is the run history's alone; the ``post-merge-red`` issue is
    a notice for people, read here for content only, so closing it, duplicating
    it or never writing it moves nothing. Every evaluation is a fresh read; no
    verdict is stored between evaluations.
ARCHITECTURE: ``evaluate(client, repo, *, now=None, claim=None, sleep=time.sleep)`` returns the verdict
    object (``state``, ``run``, ``workflow_state``, ``notice``, ``reason``, ``cause``).
    FAIL CLOSED (TQ-600a-13-ix, helpers in ``_hold_reads``): only reads (1) and (2) decide ``could_not_read``;
    each is retried once for 429/5xx/timeout/connection failure, never for 401/403/404, and a body that is
    not an object with a string ``state`` / a ``workflow_runs`` list is ``could_not_read`` ("unexpected
    shape"), never ``disabled`` or ``never_run``. Its reason begins "Post-merge run history could not be
    read" and names the cause; no other state says that. Reads (3) and (4) never do: jobs that cannot be
    read give ``did_not_complete`` with ``stage`` ``unknown``; a notice, proof, comment or exemption-record
    failure is a note appended to the reason, never a change of state or exit code. Nothing branches on
    the head repository, so a fork is judged exactly like the repository itself. The client's timeout
    (``POST_MERGE_HOLD_TIMEOUT_SECONDS``, default 10 s) and the retry delay
    (``POST_MERGE_HOLD_RETRY_DELAY_SECONDS``) come from the environment.
    Reads, at most four and never growing with the repository: (1) the
    workflow's ``state``; (2) one page of its main-branch runs in ALL statuses,
    interpreted only by ``_run_history.select_verdict_run`` (never
    ``status=completed``, which would hold every pull request through a merge
    burst); held path only: (3) the run's jobs (``classify_run`` tells red from
    did-not-complete) and (4) one page of ``post-merge-red`` issues, pull
    requests excluded. Only ``post-merge-suite.yml`` is read: the timing lane
    never holds. A failed read is ``could_not_read``, which holds (fail closed).
    Numbers (page size, staleness bound) come from ``post_merge_tunables.json``.
    ``evaluate_pull_request(client, repo, pr_number, *, now=None, head_sha=None, body=None, sleep=time.sleep)``
    is ``evaluate`` followed by the pull request's one comment
    (``_hold_comment.sync_comment``, TQ-600a-13-vii) and returns the verdict
    unchanged; ``render_comment`` (re-exported) is the pure body renderer. The
    comment is written after the verdict and never changes it or the exit code.
    CLI: GITHUB_API_URL, GITHUB_TOKEN, GITHUB_REPOSITORY and GITHUB_EVENT_PATH
    from the environment; the reason is printed; exit 0 only on ``pass`` or ``exempt``. ``main``
    reads exactly three values from the event file, in Python: the pull request
    number (``pull_request.number``, a positive int, else exit 2 and nothing is
    judged or written), ``pull_request.head.sha`` (used only when 40 lowercase
    hex characters, else the comment says the head commit is unknown) and
    ``pull_request.body`` (the description, read only to look for a declaration
    of a fix, TQ-600a-13-viii; never echoed, never in a URL or a shell; null is
    no declaration). No other event text is read, and none of it may reach a shell.
    APP PUBLICATION (TQ-600a-13-vi): ``main(["--publish"])`` hands the same evaluation to
    ``_hold_publish.publish``, which creates the check run `Post-merge suite status` as the
    hold App (in progress, before the verdict) and completes it after; ``main()`` with no
    argv is unchanged and publishes nothing. ``conclusion_for(verdict)`` (re-exported) is
    ``success`` only for ``pass`` or ``exempt``.
    TRUST: the workflow runs under ``pull_request_target`` with the default
    branch's copy of this file, sparse-checked-out with no ``ref``, so a pull
    request that edits this module has no effect on its own verdict.
    PERMISSIONS: ``pull-requests: write`` writes the comment (-vii).
    ``issues: write`` records an exemption on the notice (TQ-600a-13-viii).
    EXEMPTION (TQ-600a-13-viii, all logic in ``_hold_exempt``): ``main`` reads
    ``pull_request.body`` from the event in Python (never printed, never to a
    shell); only when ``state`` is red or did_not_complete after the reads succeed
    (``_held_verdict``) does ``_hold_exempt.apply_claim`` turn the verdict into
    ``state="exempt"`` (a declared fix of an open notice AND a passing proof on the
    head); ``match_declaration`` (re-exported) is the pure matcher the proof
    workflow shares. The verdict's run summary also carries ``updated_at``.
    -xiv: the wording of all six held states lives in ``_hold_wording`` (six distinct headlines, each
    saying the cause is not the pull request and how to restore a verdict); the comment headlines are
    ``_hold_comment.HELD_HEADLINES``. ``_verdict_inputs`` refuses to run (``_hold_config``: state
    ``could_not_read`` under the headline "Post-merge hold configuration is invalid", naming the file, both keys
    and both values) when the staleness bound is not a finite number above the heartbeat bound.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from functools import partial
from pathlib import Path

if __package__ in (None, ""):  # run as `python scripts/ci/post_merge_hold.py`: make `scripts.ci` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.ci._github_rest import GitHubClient, GitHubError, WritePolicy  # noqa: E402
from scripts.ci._hold_comment import EventError, read_event, render_comment, sync_comment  # noqa: E402, F401 -- render_comment is this module's public API
from scripts.ci._hold_exempt import Claim, apply_claim, match_declaration, read_body  # noqa: E402, F401 -- match_declaration is this module's public API (the proof workflow calls the same function)
from scripts.ci._hold_publish import GREEN_STATES, conclusion_for, publish  # noqa: E402, F401 -- conclusion_for is this module's public API
from scripts.ci._hold_reads import base_delay_seconds, cause_of, read_with_retry, shape_error, timeout_seconds  # noqa: E402
from scripts.ci._hold_config import TunablesError, check_staleness_bounds  # noqa: E402
from scripts.ci._hold_wording import (  # noqa: E402
    UNREADABLE_HEADLINE,  # noqa: F401 -- kept importable from here since -ix
    config_invalid_reason,
    could_not_read_reason,
    disabled_reason,
    held_reason,
    never_run_reason,
    no_settled_reason,
    stale_reason,
)
from scripts.ci._notice_render import LABEL, parse_state  # noqa: E402
from scripts.ci._run_history import (  # noqa: E402
    KIND_NEVER_RUN,
    KIND_SETTLED,
    VERDICT_DID_NOT_COMPLETE,
    VERDICT_RED,
    Selection,
    classify_run,
    select_verdict_run,
)

logger = logging.getLogger("post_merge_hold")

SUITE_WORKFLOW = "post-merge-suite.yml"
TUNABLES_FILE = Path(__file__).with_name("post_merge_tunables.json")
NOTICE_PAGE_SIZE = 30
ACTIVE = "active"
CONTENT_ERRORS = (GitHubError, AttributeError, KeyError, TypeError, ValueError)  # a content read that failed or came back malformed
EXIT_OK, EXIT_HELD, EXIT_BAD_INPUT = 0, 1, 2
PUBLISH_FLAG = "--publish"
REPO_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


# --------------------------------------------------------------------------- reads
def load_tunables() -> dict:
    """Read the family's tunables file (page size, staleness bound); OSError/ValueError when unusable."""
    parsed = json.loads(TUNABLES_FILE.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        message = f"{TUNABLES_FILE.name} is not a JSON object"
        raise TypeError(message)
    return parsed


def read_workflow_state(client: GitHubClient, repo: str) -> str:
    """Read (1): the suite workflow's ``state`` (``active`` | ``deleted`` | ``disabled_*``); GitHubError when the body has no string ``state``."""
    payload = client.get(f"/repos/{repo}/actions/workflows/{SUITE_WORKFLOW}")
    state = payload.get("state") if isinstance(payload, dict) else None
    if not isinstance(state, str):
        message = "the workflow answer is not an object with a string state"
        raise shape_error(message)
    return state


def read_runs(client: GitHubClient, repo: str, page_size: int) -> list[dict]:
    """Read (2): one page of the suite's main-branch runs. No ``status`` filter, ever.

    GitHubError when the body is not an object with a ``workflow_runs`` list of objects; an empty list is a readable history.
    """
    query = {"branch": "main", "exclude_pull_requests": "true", "per_page": page_size}
    payload = client.get(f"/repos/{repo}/actions/workflows/{SUITE_WORKFLOW}/runs", query)
    runs = payload.get("workflow_runs") if isinstance(payload, dict) else None
    if not isinstance(runs, list) or not all(isinstance(run, dict) for run in runs):
        message = "the run history answer is not an object with a workflow_runs list of objects"
        raise shape_error(message)
    return runs


def read_jobs(client: GitHubClient, repo: str, run_id: int) -> list[dict]:
    """Read (3), held path: the jobs of the run's latest attempt."""
    payload = client.get(f"/repos/{repo}/actions/runs/{run_id}/jobs", {"filter": "latest"})
    jobs = payload.get("jobs") if isinstance(payload, dict) else None
    return [job for job in jobs or [] if isinstance(job, dict)]


def read_notice_issues(client: GitHubClient, repo: str) -> list[dict]:
    """Read (4), held path: one page of ``post-merge-red`` issues (pull requests included: the API lists them)."""
    query = {"labels": LABEL, "state": "all", "sort": "updated", "direction": "desc", "per_page": NOTICE_PAGE_SIZE}
    items = client.get(f"/repos/{repo}/issues", query)
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def find_notice(items: list[dict], run_id: object) -> dict | None:
    """The issue (no pull request) among ``items`` whose state block describes ``run_id`` (content only)."""
    for item in items:
        if item.get("pull_request"):
            continue
        block = parse_state(item.get("body"))
        if block is not None and block.get("run_id") == run_id:
            return {"number": item.get("number"), "html_url": item.get("html_url"), "state": item.get("state"), "state_block": block}
    return None


def read_notice(client: GitHubClient, repo: str, run_id: int) -> dict | None:
    """Read (4), held path: the ``post-merge-red`` issue whose state block describes ``run_id`` (content only)."""
    return find_notice(read_notice_issues(client, repo), run_id)


# --------------------------------------------------------------------------- verdict
def _verdict(state: str, reason: str, *, run: dict | None = None, workflow_state: str | None = None, notice: dict | None = None, cause: str | None = None) -> dict:
    """Assemble the verdict object (delivers_to of TQ-600a-13-vi)."""
    summary = None
    if run is not None:
        summary = {key: run.get(key) for key in ("id", "html_url", "conclusion", "run_started_at", "updated_at", "head_sha")}
    return {"state": state, "run": summary, "workflow_state": workflow_state, "notice": notice, "reason": reason, "cause": cause}


def _parse_time(text: object) -> datetime | None:
    """Parse an ISO-8601 timestamp as the API serves it (``...Z``) into an aware UTC datetime."""
    if not isinstance(text, str):
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        logger.warning("Post-merge suite status: unparseable run_started_at %r (%s); holding", text, exc)
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _reason_held(kind: str, run: dict, notice: dict | None) -> str:
    """The output line for a held run: its link and conclusion, red or did-not-complete, and the notice."""
    line = held_reason(kind == VERDICT_RED, run)
    if notice:
        line += f" Notice: {notice['html_url']}"
    return line


def _classify(client: GitHubClient, repo: str, run: dict) -> tuple[str, str | None]:
    """``(kind, cause)``: the run classified from its jobs; when they cannot be read or used, ``did_not_complete`` and the cause.

    A defect in the content (a malformed job element) is held the same way: the run is already known not green, so it
    never reads as an unreadable run history.
    """
    try:
        return classify_run(run, read_jobs(client, repo, run["id"])), None
    except CONTENT_ERRORS as exc:  # still held, and the output still names the run
        cause = cause_of(exc)
        logger.warning("post-merge hold: could not read the jobs of run %s (%s), holding as did_not_complete", run.get("id"), cause)
        return VERDICT_DID_NOT_COMPLETE, cause


def _notice_for(client: GitHubClient, repo: str, run_id: object) -> tuple[list[dict] | None, dict | None, str | None]:
    """``(issues, notice, error)``: the notice issues and the one describing ``run_id``; ``(None, None, cause)`` when unusable.

    The notice is for people: failing to read it, or a malformed body in it, never changes the verdict.
    """
    try:
        issues = read_notice_issues(client, repo)
        return issues, find_notice(issues, run_id), None
    except CONTENT_ERRORS as exc:
        cause = cause_of(exc)
        logger.warning("could not read the %s notice (%s); holding without a link", LABEL, cause)
        return None, None, cause


def _held_verdict(client: GitHubClient, repo: str, run: dict, workflow_state: str, claim: Claim | None = None) -> dict:
    """The held path: classify the run from its jobs, then link the notice that describes it (reads 3 and 4).

    After both reads succeed, a ``claim`` (the pull request's description, head and number) may turn the verdict into
    ``exempt`` (TQ-600a-13-viii, ``_hold_exempt.apply_claim``). Neither read decides ``could_not_read`` (TQ-600a-13-ix):
    jobs that cannot be read leave the run ``did_not_complete`` with stage ``unknown`` (the tests cannot be shown to have
    run), and a notice that cannot be read is noted in the output; both still hold, and the exemption route stays open.
    """
    kind, jobs_cause = _classify(client, repo, run)
    issues, notice, issues_error = _notice_for(client, repo, run.get("id"))
    reason = _reason_held(kind, run, notice)
    if jobs_cause is not None:
        reason += f" The tests cannot be shown to have run (stage: unknown): the jobs of the run could not be read ({jobs_cause})."
    if issues_error is not None:
        reason += f" Note: the {LABEL} notice could not be read ({issues_error})."
    verdict = _verdict(kind, reason, run=run, workflow_state=workflow_state, notice=notice, cause=jobs_cause or str(run.get("conclusion")))
    if jobs_cause is not None:
        verdict["stage"] = "unknown"
    return verdict if claim is None else apply_claim(client, repo, verdict, issues, issues_error, claim)


def _settled_verdict(run: dict, workflow_state: str, now: datetime, staleness_hours: float) -> dict:
    """A settled green run passes when fresh and is stale otherwise."""
    started = _parse_time(run.get("run_started_at"))
    if started is None:
        return _verdict("could_not_read", could_not_read_reason(f"run {run.get('html_url')} has no usable start time"), run=run, workflow_state=workflow_state, cause="no run_started_at")
    age = now - started
    if age > timedelta(hours=staleness_hours):
        reason = stale_reason(run, age.total_seconds() / 3600, staleness_hours)
        return _verdict("stale", reason, run=run, workflow_state=workflow_state, cause="stale")
    return _verdict("pass", f"Post-merge suite is green: run {run.get('html_url')} concluded success.", run=run, workflow_state=workflow_state)


def _verdict_reads(client: GitHubClient, repo: str, page_size: int, sleep: Callable[[float], object]) -> tuple[str, list[dict] | None]:
    """The two verdict reads, each with its one bounded retry: ``(workflow state, runs)``; runs is None unless the workflow is active.

    Raises GitHubError when either read fails (after the retry, for a transient failure) or answers in the wrong shape.
    """
    delay = base_delay_seconds()
    workflow_state = read_with_retry(lambda: read_workflow_state(client, repo), sleep, delay)
    if workflow_state != ACTIVE:
        return workflow_state, None
    return workflow_state, read_with_retry(lambda: read_runs(client, repo, page_size), sleep, delay)


def _could_not_read(exc: BaseException) -> dict:
    """The verdict for a verdict read that failed: its own headline, the cause named, logged at WARNING. Never a pass."""
    cause = cause_of(exc)
    logger.warning("post-merge hold: the run history could not be read (%s), holding", cause)
    return _verdict("could_not_read", could_not_read_reason(cause), cause=cause)


def _verdict_inputs(client: GitHubClient, repo: str, sleep: Callable[[float], object]) -> tuple[dict, str, Selection | None]:
    """``(tunables, workflow state, selection)``; the selection is None unless the workflow is active.

    Everything that can make the RUN HISTORY unreadable is here and only here: the tunables, the two reads and the
    selection of the verdict run. Raises GitHubError/OSError/ValueError/TypeError/KeyError; ``_evaluate`` turns those
    (and nothing raised later, on the content path) into ``could_not_read``.
    """
    tunables = load_tunables()
    check_staleness_bounds(tunables)  # fail closed: the bound must outlast the heartbeat (TunablesError)
    workflow_state, runs = _verdict_reads(client, repo, int(tunables["run_history_page"]), sleep)
    return tunables, workflow_state, None if runs is None else select_verdict_run(runs)


def _evaluate(client: GitHubClient, repo: str, now: datetime, claim: Claim | None, sleep: Callable[[float], object]) -> dict:
    """Read and decide; a failed verdict read is ``could_not_read``. A defect on the content path propagates (never that headline)."""
    try:
        tunables, workflow_state, selection = _verdict_inputs(client, repo, sleep)
    except TunablesError as exc:  # before the generic handler: it is a ValueError with its own headline
        logger.warning("post-merge hold: invalid tunables (%s), holding", exc)
        return _verdict("could_not_read", config_invalid_reason(str(exc)), cause="invalid tunables")
    except (GitHubError, OSError, ValueError, TypeError, KeyError) as exc:
        return _could_not_read(exc)
    if selection is None:
        return _verdict("disabled", disabled_reason(workflow_state), workflow_state=workflow_state, cause=str(workflow_state))
    if selection.run is None:
        if selection.kind == KIND_NEVER_RUN:
            return _verdict("never_run", never_run_reason(), workflow_state=workflow_state, cause=selection.kind)
        reason = no_settled_reason(int(tunables["run_history_page"]))
        return _verdict("stale", reason, workflow_state=workflow_state, cause=selection.kind)
    run = selection.run
    if selection.kind != KIND_SETTLED or run.get("conclusion") != "success":
        return _held_verdict(client, repo, run, workflow_state, claim)
    return _settled_verdict(run, workflow_state, now, float(tunables["staleness_hours"]))


def evaluate(client: GitHubClient, repo: str, *, now: datetime | None = None, claim: Claim | None = None, sleep: Callable[[float], object] = time.sleep) -> dict:
    """Return the hold verdict for a pull request to main from a fresh read of the run history.

    ``now`` is an aware UTC clock (default: the real one). A failed verdict read gives ``could_not_read``.
    ``claim`` (the pull request's description, head and number) is evaluated for an exemption only on the held path.
    ``sleep`` is the pause before the one retry of a transient failed verdict read (injectable).
    """
    return _evaluate(client, repo, now or datetime.now(timezone.utc), claim, sleep)


def evaluate_pull_request(client: GitHubClient, repo: str, pr_number: int, *, now: datetime | None = None, head_sha: str | None = None, body: str | None = None, sleep: Callable[[float], object] = time.sleep) -> dict:
    """``evaluate``, then keep the pull request's one comment in step with the verdict; the verdict's state is never changed by it.

    ``head_sha`` is the pull request's validated head commit (None: the comment says it is unknown). ``body`` is its
    description (None: no declaration). A comment that cannot be listed or written is logged at WARNING and noted at the
    end of the returned reason; the state, the exit code and the comment already published are unaffected.
    """
    clock = now or datetime.now(timezone.utc)
    verdict = evaluate(client, repo, now=clock, claim=None if body is None else Claim(body, head_sha, pr_number), sleep=sleep)
    cause = sync_comment(client, repo, pr_number, verdict, clock, head_sha)  # logs its own failure; any other exception is a defect and raises (exit 1: still held)
    if cause is None:
        return verdict
    return {**verdict, "reason": f"{verdict['reason']} Note: the pull request comment could not be written ({cause})."}


# --------------------------------------------------------------------------- CLI
def _read_jwt() -> str:
    """The App's signed JWT, read once from the first line of stdin (the step pipes it; it is never in the environment)."""
    try:
        return sys.stdin.readline().strip()
    except (OSError, ValueError) as exc:
        logger.warning("post-merge hold: could not read the App token from stdin: %s", exc)
        return ""


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: print the reason, exit 0 only when the verdict is ``pass``.

    ``argv`` is only ever checked for ``--publish`` (App publication); a call with no argv never publishes.
    """
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s", stream=sys.stderr)
    api_url, token, repo = (os.environ.get(name, "") for name in ("GITHUB_API_URL", "GITHUB_TOKEN", "GITHUB_REPOSITORY"))
    if not (api_url and token and REPO_RE.fullmatch(repo)):
        print("Post-merge suite status could not be read: GITHUB_API_URL, GITHUB_TOKEN or GITHUB_REPOSITORY is missing or malformed.")
        return EXIT_BAD_INPUT
    try:
        pr_number, head_sha = read_event(os.environ.get("GITHUB_EVENT_PATH"))
    except EventError as exc:  # fail closed: nothing is judged, nothing is commented
        print(f"Post-merge suite status could not be read: {exc}")
        return EXIT_BAD_INPUT
    try:
        client = GitHubClient(api_url, token, timeout=timeout_seconds(), policy=WritePolicy(repo=repo, notice_comments=True, pr_comment=pr_number))
    except GitHubError as exc:
        print(f"Post-merge suite status could not be read: {exc}")
        return EXIT_BAD_INPUT
    evaluate_with_body = partial(evaluate_pull_request, body=read_body(os.environ.get("GITHUB_EVENT_PATH")))  # the description: read here, never printed
    if PUBLISH_FLAG in (argv or []):
        return publish(client, api_url, repo, pr_number, head_sha, evaluate_with_body, jwt=_read_jwt())
    verdict = evaluate_with_body(client, repo, pr_number, head_sha=head_sha)
    print(verdict["reason"])
    return EXIT_OK if verdict["state"] in GREEN_STATES else EXIT_HELD  # the publish path's rule: pass and exempt are green


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
