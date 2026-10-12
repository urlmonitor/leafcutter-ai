#!/usr/bin/env python3
"""
MODULE: post_merge_notice
GOAL: Apply one settled post-merge run's verdict to the single open
    ``post-merge-red`` issue: raise it, update it, or close it. A notice for
    people, never the gate.
BUSINESS CONTEXT: TQ-600a-13-iii. The per-PR hold reads the run history
    (TQ-600a-13-vi), so this issue changes no verdict: when every write here
    fails the run's conclusion and the hold are exactly what they were. What a
    failed write costs is a lost notice, which is why a refused write, and an
    issue created without its label, end the job in failure and say so loudly.
ARCHITECTURE: A pure planner (``plan_writes``: verdict, open notices, commit
    range, clock in; ordered ``Write`` list out) and a thin applier
    (``apply_writes``) that sends each write through the one REST client
    (``_github_rest``). The text lives in ``_notice_render``; which run may
    write at all is decided by ``_run_history.select_verdict_run``, never here.
    A run with no verdict artifact takes its stage from its own conclusion
    (``_post_merge_stages.stage_from_conclusion``).
    Reads are exactly two: the workflow's run history and ONE page of open
    labelled issues (``per_page=100``, pull requests excluded, lowest number is
    canonical). CLI: ``apply --api-url --repo --repo-dir --run-id
    --verdict-file`` with the token in GITHUB_TOKEN; exit 0 on success and on a
    deliberate no-write, 1 when a write failed, 2 on unusable input.
    ``--lane timing`` (TQ-600a-13-xii) switches the one ``LaneSpec`` the whole job
    runs under: the timing workflow's run history, the ``post-merge-timing`` label
    and wording; ``--previous-verdict-file`` adds the lane-entrant section
    (``_notice_entrants``) to a red timing notice (the previous run is found by
    ``post_merge_previous_run``). Extension
    points: TQ-600a-13-iv reopens (it needs the closed notices, so its read
    joins ``read_notices``; its branch joins ``_plan_raise``), -v refines the
    did_not_complete wording in ``_notice_render._headline``. TQ-600a-13-xiii: a
    correctness-lane ``apply`` also writes the non-holding ``post-merge-flaky`` notice
    (``_flaky_notice``; from the verdict file's window alone, one more read of open
    notices labelled flaky, attempted whatever the red notice's writes did), names the
    ids a repeated pass-on-retry made red in the red description, and names a
    red-then-green-at-the-same-commit run's failures (``--previous-verdict-file``, which
    the correctness notice job now also passes) on the flaky notice. Lane entrants stay
    a timing-lane section. The verdict file is only read, never written.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):  # run as `python scripts/ci/post_merge_notice.py`: make `scripts.ci` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.ci import _notice_render as render  # noqa: E402
from scripts.ci._flaky_notice import FLAKY, FLAKY_LABEL, may_close, not_reproduced, plan_flaky_writes, repeated_lines, wants_write  # noqa: E402
from scripts.ci._flaky_window import load_tunables  # noqa: E402
from scripts.ci._github_rest import GitHubClient, GitHubError  # noqa: E402
from scripts.ci._notice_entrants import find_entrants, render_entrant_lines  # noqa: E402
from scripts.ci._notice_render import CORRECTNESS, LANES, LaneSpec  # noqa: E402
from scripts.ci._post_merge_stages import stage_from_conclusion  # noqa: E402
from scripts.ci._run_history import select_verdict_run, tested_main  # noqa: E402
from scripts.ci.post_merge_suite import build_verdict_file  # noqa: E402

logger = logging.getLogger("post_merge_notice")

LABEL = render.LABEL
EXIT_OK, EXIT_WRITE_FAILED, EXIT_BAD_INPUT = 0, 1, 2
REPO_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
VERDICT_ARTIFACT = "post-merge-verdict"
CANCELLED_CONCLUSIONS = frozenset({"cancelled", "timed_out"})
VERDICTS = frozenset({"green", "red", "did_not_complete"})


@dataclass(frozen=True)
class Write:
    """One request the applier will make: ``kind`` is create | comment | edit | close."""

    kind: str
    number: int | None
    body: dict


# --------------------------------------------------------------------------- pure planner
def plan_writes(
    verdict: dict,
    notices: list[dict],
    commit_range: render.CommitRange,
    now: str,
    lane: LaneSpec = CORRECTNESS,
    entrants: list[str] | None = None,
) -> list[Write]:
    """Return the ordered writes for this verdict given the open notices (ascending by number).

    ``entrants`` are the extra section lines of a RED notice, passed through to the description unchanged: the lane
    entrants of a timing notice, or the repeated pass-on-retry ids of a correctness notice (empty for every other notice).
    """
    if verdict["verdict"] == "green":
        return _plan_close(verdict, notices, lane)
    return _plan_raise(verdict, notices, commit_range, now, lane, entrants)


def _plan_close(verdict: dict, notices: list[dict], lane: LaneSpec) -> list[Write]:
    """Green: a comment linking the green run, then a close, for every open notice; none open means no write."""
    writes: list[Write] = []
    for notice in notices:
        writes.append(Write("comment", notice["number"], {"body": render.render_green_comment(verdict, lane)}))
        writes.append(Write("close", notice["number"], {"state": "closed", "state_reason": "completed"}))
    return writes


def _plan_raise(
    verdict: dict, notices: list[dict], commit_range: render.CommitRange, now: str, lane: LaneSpec, entrants: list[str] | None
) -> list[Write]:
    """Red or did-not-complete: create, or update the canonical notice and close the duplicates."""
    if not notices:
        state = render.build_state(verdict, commit_range, now, lane)
        body = {"title": lane.titles[verdict["verdict"]], "body": render.render_description(state, commit_range, lane, entrants), "labels": [lane.label]}
        return [Write("create", None, body)]
    canonical, duplicates = notices[0], notices[1:]
    writes = _plan_update(verdict, canonical, commit_range, now, lane, entrants)
    for duplicate in duplicates:
        writes.append(Write("comment", duplicate["number"], {"body": render.render_duplicate_comment(canonical["number"], lane)}))
        writes.append(Write("close", duplicate["number"], {"state": "closed", "state_reason": "duplicate"}))
    return writes


def _plan_update(
    verdict: dict, canonical: dict, commit_range: render.CommitRange, now: str, lane: LaneSpec, entrants: list[str] | None
) -> list[Write]:
    """Rewrite the canonical description and add one history comment, unless this exact state is already recorded.

    The comment goes first and the description last: the description's state block is what makes a
    re-apply a no-op, so it must only exist once the history comment does. "Exact" is the key
    (run_id, verdict, stage, failing set), so a corrected re-apply of the same run still updates.
    """
    previous = render.parse_state(canonical.get("body")) or {}
    recorded = (previous.get("run_id"), previous.get("verdict"), previous.get("stage"), previous.get("failing"))
    if recorded == (verdict["run_id"], verdict["verdict"], verdict.get("stage"), sorted(verdict.get("failing") or [])):
        return []
    since = previous.get("red_since")
    state = render.build_state(verdict, commit_range, since if isinstance(since, str) and since else now, lane)
    number = canonical["number"]
    return [
        Write("comment", number, {"body": render.render_history_comment(state, lane)}),
        Write("edit", number, {"body": render.render_description(state, commit_range, lane, entrants)}),
    ]


def last_green_anchor(runs: list[dict], before_run_number: int) -> str | None:
    """Return the head sha of the highest-numbered successful main run older than the verdict run."""
    green = [r for r in runs if tested_main(r) and r.get("conclusion") == "success" and r.get("run_number", 0) < before_run_number]
    if not green:
        return None
    return max(green, key=lambda r: r["run_number"]).get("head_sha")


# --------------------------------------------------------------------------- reads
def read_runs(client: GitHubClient, repo: str, lane: LaneSpec = CORRECTNESS) -> list[dict]:
    """Read one page of the lane's workflow run history on the main branch."""
    # No `status` filter, ever: `status=completed` hides the newer waiting run and so the displaced cancellation.
    query = {"branch": "main", "exclude_pull_requests": "true", "per_page": render.RUNS_PAGE_SIZE}
    payload = client.get(f"/repos/{repo}/actions/workflows/{lane.workflow}/runs", query)
    return list((payload or {}).get("workflow_runs") or [])


def read_notices(client: GitHubClient, repo: str, lane: LaneSpec = CORRECTNESS) -> list[dict]:
    """Read the lane's open notice issues in one page, pull requests excluded, ascending by number."""
    query = {"labels": lane.label, "state": "open", "sort": "created", "direction": "asc", "per_page": 100}
    items = client.get(f"/repos/{repo}/issues", query) or []
    issues = [item for item in items if isinstance(item, dict) and not item.get("pull_request")]
    return sorted(issues, key=lambda item: item["number"])


def verdict_from_run(run: dict, repo: str, lane: LaneSpec = CORRECTNESS) -> dict:
    """Build the verdict for a run whose artifact is absent, from the run record's own conclusion."""
    if run.get("conclusion") == "success":
        return {"verdict": "green", "lane": lane.name, "stage": None, "failing": [], "run_id": run["id"], "run_url": run["html_url"], "head_sha": run["head_sha"]}
    env = {"GITHUB_SHA": run["head_sha"], "GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": run["event"], "GITHUB_RUN_ID": str(run["id"]), "GITHUB_REPOSITORY": repo}
    verdict = build_verdict_file(None, None, env, lane=lane.name)
    verdict["stage"] = stage_from_conclusion(run.get("conclusion"))  # the run's own conclusion is all there is
    verdict["run_url"] = run["html_url"]
    return verdict


def _verdict_artifact_exists(client: GitHubClient, repo: str, run_id: int) -> bool:
    """Return True when the triggering run uploaded the verdict artifact (and it has not expired)."""
    payload = client.get(f"/repos/{repo}/actions/runs/{run_id}/artifacts", {"per_page": 100})
    artifacts = (payload or {}).get("artifacts") or []
    return any(a.get("name") == VERDICT_ARTIFACT and not a.get("expired") for a in artifacts)


def load_verdict(opts: argparse.Namespace, client: GitHubClient, run: dict, lane: LaneSpec = CORRECTNESS) -> dict:
    """Return the run's verdict; ``ValueError``/``GitHubError`` when it cannot be trusted.

    An absent file means did_not_complete from the run record, UNLESS the download step failed while
    the run did upload the artifact: that is a transient failure, and recording a wrong state would
    make every re-run a no-op on it.
    """
    path = Path(opts.verdict_file)
    if not path.exists():
        if opts.download_outcome == "failure" and run.get("conclusion") != "cancelled" and _verdict_artifact_exists(client, opts.repo, run["id"]):
            message = f"the verdict artifact download failed although run {run['id']} uploaded it; writing nothing, re-run this job"
            raise ValueError(message)
        logger.warning("no verdict artifact at %s; applying the %s verdict from run %s's own record", path, lane.label, run["id"])
        return verdict_from_run(run, opts.repo, lane)
    return read_verdict_file(path, run)


def read_verdict_file(path: Path, run: dict) -> dict:
    """Read and validate the verdict file against the run record. Raises ValueError if unusable."""
    try:
        verdict = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        message = f"cannot read verdict file {path}: {exc}"
        raise ValueError(message) from exc
    ok = isinstance(verdict, dict) and verdict.get("verdict") in VERDICTS and verdict.get("run_id") == run["id"]
    if not ok or not isinstance(verdict.get("run_url"), str) or not isinstance(verdict.get("head_sha"), str):
        message = f"verdict file {path} is not the verdict of run {run['id']}"
        raise ValueError(message)
    if verdict["verdict"] == "green" and run.get("conclusion") in CANCELLED_CONCLUSIONS:
        # Cancelled after run and retry finished clean: the verdict job (always()) wrote green, the run did not complete.
        logger.warning("verdict file says green but run %s concluded %s; applying it as did_not_complete", run["id"], run["conclusion"])
        return {**verdict, "verdict": "did_not_complete", "stage": stage_from_conclusion(run["conclusion"])}
    if (verdict["verdict"] == "green") != (run.get("conclusion") == "success"):
        message = f"verdict file says {verdict['verdict']} but run {run['id']} concluded {run.get('conclusion')}; a re-run left a stale artifact"
        raise ValueError(message)
    return verdict


# --------------------------------------------------------------------------- applier
def _label_names(issue: dict | None) -> set[str]:
    """Return the label names of an issue as the service reported them."""
    labels = (issue or {}).get("labels") or []
    return {item.get("name") if isinstance(item, dict) else item for item in labels}


def _send(client: GitHubClient, repo: str, write: Write, label: str = LABEL) -> None:
    """Perform one write; raise GitHubError when it fails, or when a created issue lacks the label."""
    base = f"/repos/{repo}/issues"
    if write.kind == "create":
        created = client.post(base, write.body)
        if label not in _label_names(created):
            logger.warning("%s: created issue came back with labels %s", label, sorted(map(str, _label_names(created))))
            _repair_unlabelled(client, repo, created, label)
    elif write.kind == "comment":
        client.post(f"{base}/{write.number}/comments", write.body)
    else:
        client.patch(f"{base}/{write.number}", write.body)


def _repair_unlabelled(client: GitHubClient, repo: str, created: dict | None, label: str = LABEL) -> None:
    """An issue came back without the label: add it, or close the orphan and raise.

    An open issue without the label is invisible to every later run, which would then create another.
    Returns normally only when the label stuck.
    """
    number = (created or {}).get("number")
    if not isinstance(number, int):
        message = f"issue created without the {label} label and the response names no issue number"
        raise GitHubError(message)
    base = f"/repos/{repo}/issues/{number}"
    try:
        added = client.post(f"{base}/labels", {"labels": [label]})
    except GitHubError as exc:
        logger.warning("%s: adding the label to #%s failed: %s", label, number, exc)
        added = None
    if label in {item.get("name") if isinstance(item, dict) else item for item in added or []}:
        logger.warning("%s: issue #%s was created without its label; the label was added afterwards", label, number)
        return
    _close_orphan(client, base, number, label)
    message = f"issue #{number} was created without the {label} label and the label would not stick; the orphan was closed"
    raise GitHubError(message)


def _close_orphan(client: GitHubClient, base: str, number: int, label: str = LABEL) -> None:
    """Best effort: comment why, then close an unlabelled issue this job created."""
    reason = f"This issue was created without the {label} label and the label could not be added, so no later run could find it. Closed by the post-merge notice job; see its log."
    try:
        client.post(f"{base}/comments", {"body": reason})
        client.patch(base, {"state": "closed", "state_reason": "not_planned"})
    except GitHubError as exc:
        logger.warning("%s: could not close the unlabelled orphan #%s, close it by hand: %s", label, number, exc)


def apply_writes(client: GitHubClient, repo: str, writes: list[Write], label: str = LABEL) -> list[str]:
    """Perform the writes in order; return a description of each one NOT written.

    After a failure the remaining writes for the same issue are skipped (an edit must not mark a run
    as recorded when its history comment is missing), and every other issue is still attempted.
    """
    not_written: list[str] = []
    broken: set = set()
    for write in writes:
        name = f"{write.kind} #{write.number}" if write.number else write.kind
        if write.number in broken:
            not_written.append(f"{name} (skipped after an earlier failure on the same issue)")
            continue
        try:
            _send(client, repo, write, label)
        except GitHubError as exc:
            logger.warning("%s notice write failed: %s: %s", label, name, exc)
            not_written.append(name)
            broken.add(write.number)
            continue
        logger.info("%s notice: wrote %s", label, name)
    return not_written


# --------------------------------------------------------------------------- entry points
def _now() -> str:
    """Return the current UTC time as ISO-8601."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_previous_verdict(path: str | None) -> dict | None:
    """Read the previous settled run's verdict file; None when there is none or it is unusable.

    Never raises: an absent or corrupt previous artifact means "no entrants", not a failed notice.
    """
    if not path or not Path(path).is_file():
        return None
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("previous verdict file %s is unusable, naming no lane entrants: %s", path, exc)
        return None
    return data if isinstance(data, dict) else None


def _red_extra_lines(opts: argparse.Namespace, verdict: dict, lane: LaneSpec) -> list[str]:
    """The extra sections of a RED run's notice: the repeated pass-on-retry ids (correctness), the lane entrants (timing)."""
    if verdict["verdict"] != "red":
        return []
    if lane.name == CORRECTNESS.name:  # entrants are a timing-lane notion: the correctness lane's collected ids are not a lane membership
        return repeated_lines(verdict, load_tunables())
    return render_entrant_lines(find_entrants(verdict, read_previous_verdict(opts.previous_verdict_file), opts.repo_dir))


def _decide(opts: argparse.Namespace, client: GitHubClient) -> tuple[list[Write], str | None, dict | None]:
    """Read what the decision needs and return (red/timing notice writes, reason there are none, the verdict or None)."""
    lane = LANES[opts.lane]
    runs = read_runs(client, opts.repo, lane)
    selection = select_verdict_run(runs)
    run = selection.run
    if run is None or run.get("id") != opts.run_id:
        return [], f"run {opts.run_id} is not the settled main-branch verdict run; nothing to write", None
    verdict = load_verdict(opts, client, run, lane)
    verdict["run_url"] = run["html_url"]  # the link comes from the API, never from an artifact
    if verdict.get("lane", lane.name) != lane.name:
        return [], f"run {opts.run_id} is the {verdict['lane']} lane; it never writes the {lane.label} notice", None
    notices = read_notices(client, opts.repo, lane)
    commit_range = render.CommitRange(render.RANGE_NO_GREEN)
    if verdict["verdict"] != "green" and lane.lists_commits:
        anchor = last_green_anchor(runs, run["run_number"])
        page_full = len(runs) >= render.RUNS_PAGE_SIZE
        commit_range = render.collect_commits(opts.repo_dir, verdict["head_sha"], anchor, page_full)
    return plan_writes(verdict, notices, commit_range, _now(), lane, _red_extra_lines(opts, verdict, lane)), None, verdict


def _flaky_writes(opts: argparse.Namespace, client: GitHubClient, verdict: dict) -> list[Write]:
    """The non-holding ``post-merge-flaky`` notice's writes for a correctness-lane verdict (TQ-600a-13-xiii).

    Reads no history: the verdict file carries the window. A verdict without one (a run with no artifact) says
    nothing about the window, so it writes nothing. The notices are read only when a write is possible.
    """
    if "pass_on_retry_window" not in verdict:
        return []
    previous = read_previous_verdict(opts.previous_verdict_file)
    candidates = not_reproduced(verdict, previous)
    size = int(load_tunables()["flaky_window_runs"])
    if not (wants_write(verdict, candidates) or may_close(verdict, size)):
        return []
    notices = read_notices(client, opts.repo, FLAKY)
    return [Write(*write) for write in plan_flaky_writes(verdict, notices, size, candidates, previous)]


def _perform(client: GitHubClient, repo: str, writes: list[Write], label: str) -> int:
    """Apply ``writes`` under ``label``; return ``EXIT_OK`` or ``EXIT_WRITE_FAILED``, logging what was not written."""
    if not writes:
        return EXIT_OK
    not_written = apply_writes(client, repo, writes, label)
    if not_written:
        done = len(writes) - len(not_written)
        logger.warning("%s notice NOT fully written: %d of %d writes done; not written: %s", label, done, len(writes), "; ".join(not_written))
        return EXIT_WRITE_FAILED
    return EXIT_OK


def _apply_flaky(opts: argparse.Namespace, client: GitHubClient, verdict: dict) -> int:
    """Decide and perform the flaky notice's writes; a failure here is its own exit status and touches nothing else."""
    try:
        writes = _flaky_writes(opts, client, verdict)
    except (GitHubError, ValueError, OSError, TypeError, KeyError) as exc:
        logger.warning("%s notice: cannot decide what to write: %s", FLAKY_LABEL, exc)
        return EXIT_WRITE_FAILED
    return _perform(client, opts.repo, writes, FLAKY_LABEL)


def run_apply(opts: argparse.Namespace, token: str) -> int:
    """Decide and perform the writes for the triggering run; return the exit status."""
    label = LANES[opts.lane].label
    if not REPO_RE.fullmatch(opts.repo):
        logger.warning("%s notice: refusing repository name %r", label, opts.repo)
        return EXIT_BAD_INPUT
    try:
        client = GitHubClient(opts.api_url, token)
        writes, reason, verdict = _decide(opts, client)
    except (GitHubError, ValueError, OSError, TypeError, KeyError) as exc:  # the last three: an unreadable or malformed tunables file
        logger.warning("%s notice: cannot decide what to write: %s", label, exc)
        return EXIT_BAD_INPUT
    if reason:
        logger.info("%s notice: %s", label, reason)
    status = _perform(client, opts.repo, writes, label)
    if verdict is not None and opts.lane == CORRECTNESS.name:  # the flaky notice is independent of the red one: attempted whatever happened above
        status = max(status, _apply_flaky(opts, client, verdict))
    return status


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description="Apply a post-merge run verdict to the lane's notice (post-merge-red / post-merge-timing).")
    sub = parser.add_subparsers(dest="command", required=True)
    apply = sub.add_parser("apply", help="apply the triggering run's verdict")
    apply.add_argument("--api-url", required=True)
    apply.add_argument("--repo", required=True)
    apply.add_argument("--repo-dir", required=True)
    apply.add_argument("--run-id", required=True, type=int)
    apply.add_argument("--verdict-file", required=True)
    apply.add_argument("--download-outcome", default="", help="outcome of the artifact download step (success | failure)")
    apply.add_argument("--lane", choices=sorted(LANES), default=CORRECTNESS.name, help="which lane's run history, label and wording to use")
    apply.add_argument("--previous-verdict-file", default=None, help="verdict file of the previous settled run of this lane, to name lane entrants")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; the token comes from GITHUB_TOKEN."""
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    opts = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        logger.warning("%s notice: GITHUB_TOKEN is not set; nothing can be written", LABEL)
        return EXIT_BAD_INPUT
    return run_apply(opts, token)


if __name__ == "__main__":
    sys.exit(main())
