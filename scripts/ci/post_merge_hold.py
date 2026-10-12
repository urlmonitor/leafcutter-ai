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
ARCHITECTURE: ``evaluate(client, repo, *, now=None)`` returns the verdict object
    (``state``, ``run``, ``workflow_state``, ``notice``, ``reason``, ``cause``).
    Reads, at most four and never growing with the repository: (1) the
    workflow's ``state``; (2) one page of its main-branch runs in ALL statuses,
    interpreted only by ``_run_history.select_verdict_run`` (never
    ``status=completed``, which would hold every pull request through a merge
    burst); held path only: (3) the run's jobs (``classify_run`` tells red from
    did-not-complete) and (4) one page of ``post-merge-red`` issues, pull
    requests excluded. Only ``post-merge-suite.yml`` is read: the timing lane
    never holds. A failed read is ``could_not_read``, which holds (fail closed).
    Numbers (page size, staleness bound) come from ``post_merge_tunables.json``.
    ``evaluate_pull_request(client, repo, pr_number, *, now=None, head_sha=None)``
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
    -xiv owns the stale/disabled/never_run wording (``_reason_*`` helpers,
    ``_hold_comment.HELD_HEADLINES``).
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from functools import partial
from pathlib import Path

if __package__ in (None, ""):  # run as `python scripts/ci/post_merge_hold.py`: make `scripts.ci` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.ci._github_rest import GitHubClient, GitHubError  # noqa: E402
from scripts.ci._hold_comment import EventError, read_event, render_comment, sync_comment  # noqa: E402, F401 -- render_comment is this module's public API
from scripts.ci._hold_exempt import Claim, apply_claim, match_declaration, read_body  # noqa: E402, F401 -- match_declaration is this module's public API (the proof workflow calls the same function)
from scripts.ci._hold_publish import GREEN_STATES, conclusion_for, publish  # noqa: E402, F401 -- conclusion_for is this module's public API
from scripts.ci._notice_render import LABEL, parse_state  # noqa: E402
from scripts.ci._run_history import (  # noqa: E402
    KIND_NEVER_RUN,
    KIND_SETTLED,
    VERDICT_RED,
    classify_run,
    select_verdict_run,
)

logger = logging.getLogger("post_merge_hold")

SUITE_WORKFLOW = "post-merge-suite.yml"
TUNABLES_FILE = Path(__file__).with_name("post_merge_tunables.json")
NOTICE_PAGE_SIZE = 30
ACTIVE = "active"
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


def read_workflow_state(client: GitHubClient, repo: str) -> str | None:
    """Read (1): the suite workflow's ``state`` (``active`` | ``deleted`` | ``disabled_*``)."""
    payload = client.get(f"/repos/{repo}/actions/workflows/{SUITE_WORKFLOW}")
    state = payload.get("state") if isinstance(payload, dict) else None
    return state if isinstance(state, str) else None


def read_runs(client: GitHubClient, repo: str, page_size: int) -> list[dict]:
    """Read (2): one page of the suite's main-branch runs. No ``status`` filter, ever."""
    query = {"branch": "main", "exclude_pull_requests": "true", "per_page": page_size}
    payload = client.get(f"/repos/{repo}/actions/workflows/{SUITE_WORKFLOW}/runs", query)
    runs = payload.get("workflow_runs") if isinstance(payload, dict) else None
    return [run for run in runs or [] if isinstance(run, dict)]


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


def find_notice(items: list[dict], run_id: int) -> dict | None:
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
    what = "the tests failed" if kind == VERDICT_RED else "the run did not complete"
    line = f"Post-merge suite is not green: run {run.get('html_url')} concluded {run.get('conclusion')}; {what}."
    if notice:
        line += f" Notice: {notice['html_url']}"
    return line


def _held_verdict(client: GitHubClient, repo: str, run: dict, workflow_state: str, claim: Claim | None = None) -> dict:
    """The held path: classify the run from its jobs, then link the notice that describes it (reads 3 and 4).

    After both reads succeed, a ``claim`` (the pull request's description, head and number) may turn the verdict into
    ``exempt`` (TQ-600a-13-viii, ``_hold_exempt.apply_claim``); a failed notice read is passed on so the output states it.
    """
    try:
        kind = classify_run(run, read_jobs(client, repo, run["id"]))
    except GitHubError as exc:  # still held, and the output still names the run
        logger.warning("post-merge hold: could not read the jobs of run %s, holding: %s", run.get("id"), exc)
        reason = f"Post-merge suite status could not be read: run {run.get('html_url')} concluded {run.get('conclusion')} but its jobs could not be read ({exc})."
        return _verdict("could_not_read", reason, run=run, workflow_state=workflow_state, cause=str(exc))
    issues, issues_error = None, None
    try:
        issues = read_notice_issues(client, repo)
    except GitHubError as exc:  # the notice is for people: failing to read it never changes the verdict
        logger.warning("could not read the %s notice; holding without a link: %s", LABEL, exc)
        issues_error = str(exc)
    notice = find_notice(issues, run["id"]) if issues is not None else None
    verdict = _verdict(kind, _reason_held(kind, run, notice), run=run, workflow_state=workflow_state, notice=notice, cause=str(run.get("conclusion")))
    return verdict if claim is None else apply_claim(client, repo, verdict, issues, issues_error, claim)


def _settled_verdict(run: dict, workflow_state: str, now: datetime, staleness_hours: float) -> dict:
    """A settled green run passes when fresh and is stale otherwise."""
    started = _parse_time(run.get("run_started_at"))
    if started is None:
        return _verdict("could_not_read", f"Post-merge suite status could not be read: run {run.get('html_url')} has no usable start time.", run=run, workflow_state=workflow_state, cause="no run_started_at")
    age = now - started
    if age > timedelta(hours=staleness_hours):
        reason = f"Post-merge suite has no fresh verdict: the latest run {run.get('html_url')} started {age.total_seconds() / 3600:.0f} h ago (limit {staleness_hours:g} h)."
        return _verdict("stale", reason, run=run, workflow_state=workflow_state, cause="stale")
    return _verdict("pass", f"Post-merge suite is green: run {run.get('html_url')} concluded success.", run=run, workflow_state=workflow_state)


def _evaluate(client: GitHubClient, repo: str, now: datetime, claim: Claim | None = None) -> dict:
    """Read and decide; raises GitHubError/OSError/ValueError when a read fails (``evaluate`` turns that into a hold)."""
    tunables = load_tunables()
    workflow_state = read_workflow_state(client, repo)
    if workflow_state != ACTIVE:
        return _verdict("disabled", f"Post-merge suite workflow is not active (state: {workflow_state}).", workflow_state=workflow_state, cause=str(workflow_state))
    selection = select_verdict_run(read_runs(client, repo, int(tunables["run_history_page"])))
    if selection.run is None:
        if selection.kind == KIND_NEVER_RUN:
            return _verdict("never_run", "Post-merge suite has never run on main.", workflow_state=workflow_state, cause=selection.kind)
        reason = "Post-merge suite has no settled run in its latest runs on main."
        return _verdict("stale", reason, workflow_state=workflow_state, cause=selection.kind)
    run = selection.run
    if selection.kind != KIND_SETTLED or run.get("conclusion") != "success":
        return _held_verdict(client, repo, run, workflow_state, claim)
    return _settled_verdict(run, workflow_state, now, float(tunables["staleness_hours"]))


def evaluate(client: GitHubClient, repo: str, *, now: datetime | None = None, claim: Claim | None = None) -> dict:
    """Return the hold verdict for a pull request to main from a fresh read of the run history.

    ``now`` is an aware UTC clock (default: the real one). A failed read gives ``could_not_read``.
    ``claim`` (the pull request's description, head and number) is evaluated for an exemption only on the held path.
    """
    clock = now or datetime.now(timezone.utc)
    try:
        return _evaluate(client, repo, clock, claim)
    except (GitHubError, OSError, ValueError, TypeError, KeyError) as exc:
        logger.warning("post-merge hold: a read failed, holding: %s", exc)
        return _verdict("could_not_read", f"Post-merge suite status could not be read: {exc}", cause=str(exc))


def evaluate_pull_request(client: GitHubClient, repo: str, pr_number: int, *, now: datetime | None = None, head_sha: str | None = None, body: str | None = None) -> dict:
    """``evaluate``, then keep the pull request's one comment in step with the verdict, and return the verdict unchanged.

    ``head_sha`` is the pull request's validated head commit (None: the comment says it is unknown). ``body`` is its
    description (None: no declaration). A comment that cannot be listed or written is logged and never changes the verdict.
    """
    clock = now or datetime.now(timezone.utc)
    verdict = evaluate(client, repo, now=clock, claim=None if body is None else Claim(body, head_sha, pr_number))
    try:
        sync_comment(client, repo, pr_number, verdict, clock, head_sha)
    except GitHubError as exc:  # the comment is for people; any other exception is a defect and raises (a raise exits 1: still held)
        logger.warning("post-merge hold: the comment on #%s could not be kept in step: %s", pr_number, exc)
    return verdict


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
        client = GitHubClient(api_url, token)
    except GitHubError as exc:
        print(f"Post-merge suite status could not be read: {exc}")
        return EXIT_BAD_INPUT
    try:
        pr_number, head_sha = read_event(os.environ.get("GITHUB_EVENT_PATH"))
    except EventError as exc:  # fail closed: nothing is judged, nothing is commented
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
