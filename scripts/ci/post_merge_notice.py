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
    Reads are exactly two: the workflow's run history and ONE page of open
    labelled issues (``per_page=100``, pull requests excluded, lowest number is
    canonical). CLI: ``apply --api-url --repo --repo-dir --run-id
    --verdict-file`` with the token in GITHUB_TOKEN; exit 0 on success and on a
    deliberate no-write, 1 when a write failed, 2 on unusable input. Extension
    points: TQ-600a-13-iv reopens (it needs the closed notices, so its read
    joins ``read_notices``; its branch joins ``_plan_raise``), -v refines the
    did_not_complete wording in ``_notice_render._headline``, -xiii adds its
    section to the description via the same renderer. The verdict file is only
    read, never written.
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
from scripts.ci._github_rest import GitHubClient, GitHubError  # noqa: E402
from scripts.ci._run_history import select_verdict_run, tested_main  # noqa: E402
from scripts.ci.post_merge_suite import build_verdict_file  # noqa: E402

logger = logging.getLogger("post_merge_notice")

LABEL = render.LABEL
SUITE_WORKFLOW = "post-merge-suite.yml"
LANE = "correctness"
EXIT_OK, EXIT_WRITE_FAILED, EXIT_BAD_INPUT = 0, 1, 2
REPO_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
VERDICT_ARTIFACT = "post-merge-verdict"
VERDICTS = frozenset({"green", "red", "did_not_complete"})
TITLES = {"red": "Post-merge suite is red", "did_not_complete": "Post-merge suite did not complete"}


@dataclass(frozen=True)
class Write:
    """One request the applier will make: ``kind`` is create | comment | edit | close."""

    kind: str
    number: int | None
    body: dict


# --------------------------------------------------------------------------- pure planner
def plan_writes(verdict: dict, notices: list[dict], commit_range: render.CommitRange, now: str) -> list[Write]:
    """Return the ordered writes for this verdict given the open notices (ascending by number)."""
    if verdict["verdict"] == "green":
        return _plan_close(verdict, notices)
    return _plan_raise(verdict, notices, commit_range, now)


def _plan_close(verdict: dict, notices: list[dict]) -> list[Write]:
    """Green: a comment linking the green run, then a close, for every open notice; none open means no write."""
    writes: list[Write] = []
    for notice in notices:
        writes.append(Write("comment", notice["number"], {"body": render.render_green_comment(verdict)}))
        writes.append(Write("close", notice["number"], {"state": "closed", "state_reason": "completed"}))
    return writes


def _plan_raise(verdict: dict, notices: list[dict], commit_range: render.CommitRange, now: str) -> list[Write]:
    """Red or did-not-complete: create, or update the canonical notice and close the duplicates."""
    if not notices:
        state = render.build_state(verdict, commit_range, now)
        body = {"title": TITLES[verdict["verdict"]], "body": render.render_description(state, commit_range), "labels": [LABEL]}
        return [Write("create", None, body)]
    canonical, duplicates = notices[0], notices[1:]
    writes = _plan_update(verdict, canonical, commit_range, now)
    for duplicate in duplicates:
        writes.append(Write("comment", duplicate["number"], {"body": render.render_duplicate_comment(canonical["number"])}))
        writes.append(Write("close", duplicate["number"], {"state": "closed", "state_reason": "duplicate"}))
    return writes


def _plan_update(verdict: dict, canonical: dict, commit_range: render.CommitRange, now: str) -> list[Write]:
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
    state = render.build_state(verdict, commit_range, since if isinstance(since, str) and since else now)
    number = canonical["number"]
    return [
        Write("comment", number, {"body": render.render_history_comment(state)}),
        Write("edit", number, {"body": render.render_description(state, commit_range)}),
    ]


def last_green_anchor(runs: list[dict], before_run_number: int) -> str | None:
    """Return the head sha of the highest-numbered successful main run older than the verdict run."""
    green = [r for r in runs if tested_main(r) and r.get("conclusion") == "success" and r.get("run_number", 0) < before_run_number]
    if not green:
        return None
    return max(green, key=lambda r: r["run_number"]).get("head_sha")


# --------------------------------------------------------------------------- reads
def read_runs(client: GitHubClient, repo: str) -> list[dict]:
    """Read one page of the suite's run history on the main branch."""
    payload = client.get(f"/repos/{repo}/actions/workflows/{SUITE_WORKFLOW}/runs", {"branch": "main", "per_page": render.RUNS_PAGE_SIZE})
    return list((payload or {}).get("workflow_runs") or [])


def read_notices(client: GitHubClient, repo: str) -> list[dict]:
    """Read the open ``post-merge-red`` issues in one page, pull requests excluded, ascending by number."""
    query = {"labels": LABEL, "state": "open", "sort": "created", "direction": "asc", "per_page": 100}
    items = client.get(f"/repos/{repo}/issues", query) or []
    issues = [item for item in items if isinstance(item, dict) and not item.get("pull_request")]
    return sorted(issues, key=lambda item: item["number"])


def verdict_from_run(run: dict, repo: str) -> dict:
    """Build the verdict for a run whose artifact is absent, from the run record's own conclusion."""
    if run.get("conclusion") == "success":
        return {"verdict": "green", "lane": LANE, "stage": None, "failing": [], "run_id": run["id"], "run_url": run["html_url"], "head_sha": run["head_sha"]}
    env = {"GITHUB_SHA": run["head_sha"], "GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": run["event"], "GITHUB_RUN_ID": str(run["id"]), "GITHUB_REPOSITORY": repo}
    verdict = build_verdict_file(None, None, env)
    verdict["run_url"] = run["html_url"]
    return verdict


def _verdict_artifact_exists(client: GitHubClient, repo: str, run_id: int) -> bool:
    """Return True when the triggering run uploaded the verdict artifact (and it has not expired)."""
    payload = client.get(f"/repos/{repo}/actions/runs/{run_id}/artifacts", {"per_page": 100})
    artifacts = (payload or {}).get("artifacts") or []
    return any(a.get("name") == VERDICT_ARTIFACT and not a.get("expired") for a in artifacts)


def load_verdict(opts: argparse.Namespace, client: GitHubClient, run: dict) -> dict:
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
        logger.warning("no verdict artifact at %s; applying the %s verdict from run %s's own record", path, LABEL, run["id"])
        return verdict_from_run(run, opts.repo)
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
    if (verdict["verdict"] == "green") != (run.get("conclusion") == "success"):
        message = f"verdict file says {verdict['verdict']} but run {run['id']} concluded {run.get('conclusion')}; a re-run left a stale artifact"
        raise ValueError(message)
    return verdict


# --------------------------------------------------------------------------- applier
def _label_names(issue: dict | None) -> set[str]:
    """Return the label names of an issue as the service reported them."""
    labels = (issue or {}).get("labels") or []
    return {item.get("name") if isinstance(item, dict) else item for item in labels}


def _send(client: GitHubClient, repo: str, write: Write) -> None:
    """Perform one write; raise GitHubError when it fails, or when a created issue lacks the label."""
    base = f"/repos/{repo}/issues"
    if write.kind == "create":
        created = client.post(base, write.body)
        if LABEL not in _label_names(created):
            logger.warning("%s: created issue came back with labels %s", LABEL, sorted(map(str, _label_names(created))))
            _repair_unlabelled(client, repo, created)
    elif write.kind == "comment":
        client.post(f"{base}/{write.number}/comments", write.body)
    else:
        client.patch(f"{base}/{write.number}", write.body)


def _repair_unlabelled(client: GitHubClient, repo: str, created: dict | None) -> None:
    """An issue came back without the label: add it, or close the orphan and raise.

    An open issue without the label is invisible to every later run, which would then create another.
    Returns normally only when the label stuck.
    """
    number = (created or {}).get("number")
    if not isinstance(number, int):
        message = f"issue created without the {LABEL} label and the response names no issue number"
        raise GitHubError(message)
    base = f"/repos/{repo}/issues/{number}"
    try:
        added = client.post(f"{base}/labels", {"labels": [LABEL]})
    except GitHubError as exc:
        logger.warning("%s: adding the label to #%s failed: %s", LABEL, number, exc)
        added = None
    if LABEL in {item.get("name") if isinstance(item, dict) else item for item in added or []}:
        logger.warning("%s: issue #%s was created without its label; the label was added afterwards", LABEL, number)
        return
    _close_orphan(client, base, number)
    message = f"issue #{number} was created without the {LABEL} label and the label would not stick; the orphan was closed"
    raise GitHubError(message)


def _close_orphan(client: GitHubClient, base: str, number: int) -> None:
    """Best effort: comment why, then close an unlabelled issue this job created."""
    reason = f"This issue was created without the {LABEL} label and the label could not be added, so no later run could find it. Closed by the post-merge notice job; see its log."
    try:
        client.post(f"{base}/comments", {"body": reason})
        client.patch(base, {"state": "closed", "state_reason": "not_planned"})
    except GitHubError as exc:
        logger.warning("%s: could not close the unlabelled orphan #%s, close it by hand: %s", LABEL, number, exc)


def apply_writes(client: GitHubClient, repo: str, writes: list[Write]) -> list[str]:
    """Perform the writes in order; return a description of each one NOT written.

    After a failure the remaining writes for the same issue are skipped (an edit must not mark a run
    as recorded when its history comment is missing), and every other issue is still attempted.
    """
    not_written: list[str] = []
    broken: set = set()
    for write in writes:
        label = f"{write.kind} #{write.number}" if write.number else write.kind
        if write.number in broken:
            not_written.append(f"{label} (skipped after an earlier failure on the same issue)")
            continue
        try:
            _send(client, repo, write)
        except GitHubError as exc:
            logger.warning("%s notice write failed: %s: %s", LABEL, label, exc)
            not_written.append(label)
            broken.add(write.number)
            continue
        logger.info("%s notice: wrote %s", LABEL, label)
    return not_written


# --------------------------------------------------------------------------- entry points
def _now() -> str:
    """Return the current UTC time as ISO-8601."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _decide(opts: argparse.Namespace, client: GitHubClient) -> tuple[list[Write], str | None]:
    """Read what the decision needs and return (writes, reason there are none)."""
    runs = read_runs(client, opts.repo)
    selection = select_verdict_run(runs)
    run = selection.run
    if run is None or run.get("id") != opts.run_id:
        return [], f"run {opts.run_id} is not the settled main-branch verdict run; nothing to write"
    verdict = load_verdict(opts, client, run)
    verdict["run_url"] = run["html_url"]  # the link comes from the API, never from an artifact
    if verdict.get("lane", LANE) != LANE:
        return [], f"run {opts.run_id} is the {verdict['lane']} lane; it never writes the {LABEL} notice"
    notices = read_notices(client, opts.repo)
    commit_range = render.CommitRange(render.RANGE_NO_GREEN)
    if verdict["verdict"] != "green":
        anchor = last_green_anchor(runs, run["run_number"])
        page_full = len(runs) >= render.RUNS_PAGE_SIZE
        commit_range = render.collect_commits(opts.repo_dir, verdict["head_sha"], anchor, page_full)
    return plan_writes(verdict, notices, commit_range, _now()), None


def run_apply(opts: argparse.Namespace, token: str) -> int:
    """Decide and perform the writes for the triggering run; return the exit status."""
    if not REPO_RE.fullmatch(opts.repo):
        logger.warning("%s notice: refusing repository name %r", LABEL, opts.repo)
        return EXIT_BAD_INPUT
    try:
        client = GitHubClient(opts.api_url, token)
        writes, reason = _decide(opts, client)
    except (GitHubError, ValueError) as exc:
        logger.warning("%s notice: cannot decide what to write: %s", LABEL, exc)
        return EXIT_BAD_INPUT
    if reason:
        logger.info("%s notice: %s", LABEL, reason)
    if not writes:
        return EXIT_OK
    not_written = apply_writes(client, opts.repo, writes)
    if not_written:
        done = len(writes) - len(not_written)
        logger.warning("%s notice NOT fully written: %d of %d writes done; not written: %s", LABEL, done, len(writes), "; ".join(not_written))
        return EXIT_WRITE_FAILED
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description="Apply a post-merge run verdict to the post-merge-red notice.")
    sub = parser.add_subparsers(dest="command", required=True)
    apply = sub.add_parser("apply", help="apply the triggering run's verdict")
    apply.add_argument("--api-url", required=True)
    apply.add_argument("--repo", required=True)
    apply.add_argument("--repo-dir", required=True)
    apply.add_argument("--run-id", required=True, type=int)
    apply.add_argument("--verdict-file", required=True)
    apply.add_argument("--download-outcome", default="", help="outcome of the artifact download step (success | failure)")
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
