#!/usr/bin/env python3
"""
MODULE: post_merge_reeval
GOAL: When the post-merge verdict changes, run again the latest hold evaluation of
    every open pull request targeting main, so each gets a verdict from the new run
    history without anyone pushing. Name every pull request that could not be re-run.
BUSINESS CONTEXT: TQ-600a-13-xv. The hold is evaluated on pull request events, so a
    pull request evaluated before the verdict changed keeps its earlier result: a stale
    pass while main is red, a stale hold after main is green again. This job closes
    both. It runs after the triggering run settled (a ``workflow_run`` job), so the
    re-evaluation reads the new history. A fix-proof completion (TQ-600a-13-xvi)
    re-runs only the hold of the proof's head commit, and only when the proof run
    was a ``pull_request_target`` run of this repository (a same-named run from a
    pull request branch or a fork re-runs nothing).
ARCHITECTURE: Stdlib only, through the one REST client (``_github_rest``). Two phases:
    READ (the suite history, ``_run_history.verdict_changed``, the open pull request
    list, the latest ``pull_request_target`` hold run per head SHA) then ACT (one
    ``POST /actions/runs/{id}/rerun`` per completed hold run no older than 30 days).
    Any read failure ends the job non-zero before the first re-run. The only write is
    that re-run request, on a run of ``post-merge-hold.yml``. A hold run that is in
    progress is skipped silently (it reads the new history itself); one that cannot be
    re-run is named in the ``unrerunnable`` output, one line
    ``unrerunnable=<JSON list of {pr, head_sha, reason}>`` appended to ``--output-file``
    (``GITHUB_OUTPUT``) and printed. ``reason`` is ``older_than_30_days`` |
    ``rerun_refused_<status>`` | ``no_hold_run`` | ``rerun_disabled``. Hotfix 2026-10-12: re-runs are opt-in. The
    GITHUB_TOKEN re-run POST is accepted live but the re-run ends in ``startup_failure``, so a request is made only when
    env ``REEVAL_RERUN_ENABLED`` is exactly ``true`` (the workflow passes repo variable ``POST_MERGE_REEVAL_RERUN``);
    otherwise every read is still done, no POST is made, and each hold that would have been re-run is named
    ``rerun_disabled``. A fix-proof completion also reads ``GET /actions/runs/{id}/jobs`` and re-runs only when the job
    ``Post-merge fix proof`` concluded success or failure (skipped or absent: nothing, output ``[]``). CLI: ``--api-url --repo --event-path
    --output-file``, the token in GITHUB_TOKEN; exit 0 once a decision is reached, 2 on
    unusable input or an unreadable history or pull request list.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple

if __package__ in (None, ""):  # run as `python scripts/ci/post_merge_reeval.py`: make `scripts.ci` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.ci._github_rest import GitHubClient, GitHubError, WritePolicy  # noqa: E402
from scripts.ci._hold_comment import MAX_PAGES, next_link, valid_sha  # noqa: E402
from scripts.ci._run_history import verdict_changed  # noqa: E402
from scripts.ci.post_merge_notice import REPO_RE, read_runs  # noqa: E402

logger = logging.getLogger("post_merge_reeval")

EXIT_OK, EXIT_BAD_INPUT = 0, 2
SUITE_NAME, PROOF_NAME = "Post-merge suite", "Post-merge fix proof"
HOLD_WORKFLOW = "post-merge-hold.yml"
HOLD_EVENT = "pull_request_target"
RERUN_WINDOW = timedelta(days=30)
PAGE_SIZE, HOLD_RUNS_PAGE = 100, 5

ACTION_RERUN, ACTION_SKIP, ACTION_NAME = "rerun", "skip", "name"
REASON_DISABLED = "rerun_disabled"
PROOF_JOB = "Post-merge fix proof"  # the proof workflow's `prove` job; skipped when no fix is declared
PROOF_RAN = ("success", "failure")  # a conclusion that means the proof actually ran
RERUN_FLAG, RERUN_ON = "REEVAL_RERUN_ENABLED", "true"


def _entry(pr: int | None, head_sha: str, reason: str) -> dict:
    """One ``unrerunnable`` item."""
    return {"pr": pr, "head_sha": head_sha, "reason": reason}


# --------------------------------------------------------------------------- reads
class Trigger(NamedTuple):
    """The facts of the ``workflow_run`` event the decision uses."""

    name: str
    run_id: int | None
    head_sha: str | None
    event: str
    head_repository: str


def read_trigger(path: str) -> Trigger:
    """Return the ``Trigger`` of the ``workflow_run`` event file; ``ValueError`` when it is unreadable or malformed."""
    try:
        event = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        message = f"cannot read the event file {path}: {exc}"
        raise ValueError(message) from exc
    run = event.get("workflow_run") if isinstance(event, dict) else None
    if not isinstance(run, dict):
        message = f"event file {path} has no workflow_run"
        raise ValueError(message)  # noqa: TRY004 -- the documented contract of this reader is ValueError for any malformed input
    run_id, repository = run.get("id"), run.get("head_repository")
    full_name = repository.get("full_name") if isinstance(repository, dict) else None
    return Trigger(
        str(run.get("name") or ""),
        run_id if isinstance(run_id, int) and not isinstance(run_id, bool) else None,
        valid_sha(run.get("head_sha")),
        str(run.get("event") or ""),
        full_name if isinstance(full_name, str) else "",
    )


def list_open_pull_requests(client: GitHubClient, repo: str) -> list[dict]:
    """Every open pull request with base ``main``, following ``Link: rel="next"`` on the API's own origin only.

    Raises ``GitHubError`` when a page cannot be read, is not a list, or a ``next`` link leaves the origin or repeats.
    """
    path, query, seen, found = f"/repos/{repo}/pulls", {"state": "open", "base": "main", "per_page": PAGE_SIZE}, set(), []
    for _ in range(MAX_PAGES):
        payload, headers = client.get_with_headers(path, query)
        if not isinstance(payload, list):
            message = "the pull request list is not a JSON array"
            raise GitHubError(message, kind="shape")
        found += [p for p in payload if isinstance(p, dict)]
        target = next_link(headers.get("link"))
        if target is None:
            return found
        path, query = client.same_origin_path(target), None
        if path is None or path in seen:
            message = "the pull request list's next link leaves the API origin or repeats"
            raise GitHubError(message, kind="shape")
        seen.add(path)
    message = f"the pull request list runs past {MAX_PAGES} pages"
    raise GitHubError(message, kind="shape")


def latest_hold_run(client: GitHubClient, repo: str, head_sha: str) -> dict | None:
    """The ``pull_request_target`` run of the hold workflow for ``head_sha`` with the highest ``run_number``, or None."""
    query = {"head_sha": head_sha, "event": HOLD_EVENT, "per_page": HOLD_RUNS_PAGE}
    payload = client.get(f"/repos/{repo}/actions/workflows/{HOLD_WORKFLOW}/runs", query)
    runs = (payload or {}).get("workflow_runs") if isinstance(payload, dict) or payload is None else None
    if not isinstance(runs, list):
        message = "the hold run list is not the expected shape"
        raise GitHubError(message, kind="shape")
    usable = [r for r in runs if isinstance(r, dict) and r.get("event") == HOLD_EVENT and isinstance(r.get("run_number"), int) and isinstance(r.get("id"), int)]
    return max(usable, key=lambda r: r["run_number"]) if usable else None


def _pull_request_targets(client: GitHubClient, repo: str) -> list[tuple[int | None, str, dict | None]]:
    """``(pr, head sha, latest hold run)`` for every open pull request on main; all reads happen here, before any re-run."""
    targets: list[tuple[int | None, str, dict | None]] = []
    for pull in list_open_pull_requests(client, repo):
        number, sha = pull.get("number"), valid_sha((pull.get("head") or {}).get("sha"))
        if not isinstance(number, int) or isinstance(number, bool) or sha is None:
            logger.warning("skipping a pull request with no usable number or head sha: %r", number)
            continue
        targets.append((number, sha, latest_hold_run(client, repo, sha)))
    return targets


# --------------------------------------------------------------------------- decision
def _created(run: dict) -> datetime | None:
    """The run's ``created_at`` as an aware datetime, or None when absent or unparseable."""
    text = run.get("created_at")
    if not isinstance(text, str):
        return None
    try:
        stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def classify_hold(run: dict | None, now: datetime) -> tuple[str, str | None]:
    """``(action, reason)`` for a pull request's latest hold run: rerun, skip (in progress) or name (with the reason)."""
    if run is None:
        return ACTION_NAME, "no_hold_run"
    if run.get("status") != "completed":
        return ACTION_SKIP, None
    created = _created(run)
    if created is not None and now - created > RERUN_WINDOW:
        return ACTION_NAME, "older_than_30_days"
    return ACTION_RERUN, None


def request_rerun(client: GitHubClient, repo: str, run_id: int) -> str | None:
    """Ask for ``run_id`` to be run again; None on success, ``rerun_refused_<status>`` when the service refused."""
    try:
        client.post(f"/repos/{repo}/actions/runs/{run_id}/rerun", {})
    except GitHubError as exc:
        logger.warning("re-run of hold run %s refused: %s", run_id, exc)
        return f"rerun_refused_{exc.status}"
    return None


def reevaluate(client: GitHubClient, repo: str, targets: list[tuple[int | None, str, dict | None]], now: datetime, *, rerun_enabled: bool = False) -> list[dict]:
    """Re-run each target's completed hold run; return the entries that could not be re-run.

    With ``rerun_enabled`` False no request is made: each hold that would have been re-run is named ``rerun_disabled``.
    """
    named: list[dict] = []
    for pr, sha, run in targets:
        action, reason = classify_hold(run, now)
        if action == ACTION_RERUN and run is not None:
            reason = request_rerun(client, repo, run["id"]) if rerun_enabled else REASON_DISABLED
        if reason:
            named.append(_entry(pr, sha, reason))
    return named


def _proof_trusted(trigger: Trigger, repo: str) -> bool:
    """True only for a ``pull_request_target`` proof run of THIS repository with a usable head sha.

    A same-named workflow run from a pull request branch (event ``pull_request``) or from a fork must cause no re-run.
    """
    if trigger.event != HOLD_EVENT or trigger.head_repository != repo:
        logger.warning("ignoring a %s run of event %r from repository %r: only %s runs of %s re-run a hold", trigger.name, trigger.event, trigger.head_repository, HOLD_EVENT, repo)
        return False
    if trigger.head_sha is None:
        logger.warning("the %s event carries no usable head sha; nothing to re-run", trigger.name)
        return False
    return True


def proof_ran(client: GitHubClient, repo: str, run_id: int | None) -> bool:
    """True when the proof run's ``Post-merge fix proof`` job concluded success or failure (read-only); skipped or absent is False.

    Raises ``GitHubError`` when the jobs cannot be read or are not the expected shape.
    """
    if run_id is None:
        return False
    payload = client.get(f"/repos/{repo}/actions/runs/{run_id}/jobs", {"per_page": PAGE_SIZE})
    jobs = payload.get("jobs") if isinstance(payload, dict) else None
    if not isinstance(jobs, list):
        message = "the proof run's job list is not the expected shape"
        raise GitHubError(message, kind="shape")
    return any(isinstance(j, dict) and j.get("name") == PROOF_JOB and j.get("conclusion") in PROOF_RAN for j in jobs)


def decide(client: GitHubClient, opts: argparse.Namespace, trigger: Trigger) -> list[dict]:
    """Read what the trigger needs and perform the re-runs; return the named pull requests.

    ``opts.rerun_enabled`` (False when absent) gates every re-run request; reads are always done.
    Raises ``GitHubError`` on an unreadable history, pull request list, job list or hold run list, before any re-run.
    """
    now = datetime.now(timezone.utc)
    enabled = bool(getattr(opts, "rerun_enabled", False))
    if trigger.name == PROOF_NAME:
        if not _proof_trusted(trigger, opts.repo) or trigger.head_sha is None:
            return []
        if not proof_ran(client, opts.repo, trigger.run_id):
            logger.info("the %s job did not run in proof run %s; nothing was proved, nothing is re-run", PROOF_JOB, trigger.run_id)
            return []
        return reevaluate(client, opts.repo, [(None, trigger.head_sha, latest_hold_run(client, opts.repo, trigger.head_sha))], now, rerun_enabled=enabled)
    if trigger.name != SUITE_NAME:
        logger.info("workflow %r is not one this job re-evaluates for; nothing to do", trigger.name)
        return []
    run_id = trigger.run_id
    if verdict_changed(read_runs(client, opts.repo), run_id if run_id is not None else -1) is not True:
        logger.info("the verdict did not change at run %s (or it is not settled); nothing is re-evaluated", run_id)
        return []
    return reevaluate(client, opts.repo, _pull_request_targets(client, opts.repo), now, rerun_enabled=enabled)


# --------------------------------------------------------------------------- entry point
def emit(named: list[dict], output_file: str) -> bool:
    """Print the ``unrerunnable`` JSON and append its one output line; False when the file cannot be written."""
    text = json.dumps(named, separators=(",", ":"))
    print(text)  # noqa: T201 -- the output is part of the job log
    try:
        with Path(output_file).open("a", encoding="utf-8") as handle:
            handle.write(f"unrerunnable={text}\n")
    except OSError as exc:
        logger.warning("cannot write the output file %s: %s", output_file, exc)
        return False
    return True


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description="Re-run the latest hold evaluation of every open pull request when the post-merge verdict changed.")
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--event-path", required=True, help="the workflow_run event file (GITHUB_EVENT_PATH)")
    parser.add_argument("--output-file", required=True, help="GITHUB_OUTPUT: receives the one unrerunnable= line")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; the token comes from GITHUB_TOKEN."""
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    opts = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    opts.rerun_enabled = os.environ.get(RERUN_FLAG, "") == RERUN_ON
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token or not REPO_RE.fullmatch(opts.repo):
        logger.warning("GITHUB_TOKEN is not set or the repository name %r is refused; nothing re-run", opts.repo)
        return EXIT_BAD_INPUT
    try:
        named = decide(GitHubClient(opts.api_url, token, policy=WritePolicy(repo=opts.repo, rerun_hold=True)), opts, read_trigger(opts.event_path))
    except (GitHubError, ValueError) as exc:
        logger.warning("cannot decide what to re-run: %s", exc)
        return EXIT_BAD_INPUT
    return EXIT_OK if emit(named, opts.output_file) else EXIT_BAD_INPUT


if __name__ == "__main__":
    sys.exit(main())
