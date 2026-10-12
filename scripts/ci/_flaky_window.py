"""
MODULE: _flaky_window
GOAL: Count, per correctness-lane test, in how many of the last ``flaky_window_runs``
    settled main runs it passed only on retry, from the runs' RECORDED verdict
    artifacts, and name the tests that reach ``flaky_red_threshold``.
BUSINESS CONTEXT: TQ-600a-13-xiii. A shared-layout guard catches a corruption that
    presents nondeterministically, so a test that passes on retry may be that
    corruption. One such run stays green but is tracked; the same test doing it
    again inside the window makes the run red. The count comes from earlier runs'
    verdict artifacts, never from the ``post-merge-flaky`` notice, so a notice that
    was never written, hand-edited or closed cannot change a verdict.
ARCHITECTURE: ``flaky_fields`` is pure (current ids, history, tunables, lane in; the
    three verdict fields out). ``read_history`` is the only I/O: ONE run-history page,
    then per earlier settled run (at most window-1) one artifact list and one
    artifact zip download through ``GitHubClient`` -- at most ``1 + 2 * (window - 1)``
    requests, never the issues API. "Settled" is ``_run_history.select_verdict_run``'s
    rule, applied repeatedly, so a superseded cancellation never fills a slot. An entry
    that cannot be read is ``None`` and counts as zero occurrences, but is not counted
    in ``window_runs_read``, so a short history is visible. The numbers come from
    ``post_merge_tunables.json``, never from a literal here.
"""

from __future__ import annotations

import io
import json
import logging
import re
import zipfile
from pathlib import Path
from typing import NamedTuple

from scripts.ci._github_rest import GitHubClient, GitHubError
from scripts.ci._notice_render import CORRECTNESS
from scripts.ci._run_history import select_verdict_run

logger = logging.getLogger("post_merge_suite")

TUNABLES_FILE = Path(__file__).with_name("post_merge_tunables.json")
REPO_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
VERDICT_ARTIFACT = "post-merge-verdict"
VERDICT_MEMBER = "post-merge-verdict.json"
MAX_MEMBER_BYTES = 5 * 1024 * 1024


def load_tunables(path: Path = TUNABLES_FILE) -> dict:
    """Read the tunables file; ``TypeError`` when it is not a JSON object, ``OSError`` when unreadable."""
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        logger.warning("cannot read the tunables %s: %s", path, exc)
        raise
    if not isinstance(parsed, dict):
        message = f"{path.name} is not a JSON object"
        raise TypeError(message)
    return parsed


# --------------------------------------------------------------------------- pure counting
def _retried_ids(entry: dict | None) -> set[str]:
    """The ids an earlier verdict says passed on retry (each counts once per run); none for an unreadable entry."""
    return set((entry or {}).get("passed_on_retry") or [])


def flaky_fields(current_ids: list[str], history: list[dict | None] | None, tunables: dict, *, escalate: bool) -> tuple[dict, int, list[str]]:
    """Return ``(pass_on_retry_window, window_runs_read, repeated_pass_on_retry)`` for the current run.

    ``history`` is the earlier runs' parsed verdict files, newest first, ``None`` for an unreadable one; only
    the first ``flaky_window_runs - 1`` are used. ``escalate`` False (the timing lane, a run that did not
    complete) leaves the repeated list empty.
    """
    used = list(history or [])[: max(0, int(tunables["flaky_window_runs"]) - 1)]
    window: dict[str, int] = {}
    for ids in [set(current_ids), *(_retried_ids(entry) for entry in used)]:
        for node_id in ids:
            window[node_id] = window.get(node_id, 0) + 1
    threshold = int(tunables["flaky_red_threshold"])
    repeated = sorted(i for i in set(current_ids) if window[i] >= threshold) if escalate else []
    return window, 1 + sum(entry is not None for entry in used), repeated


# --------------------------------------------------------------------------- reading earlier verdicts
def _parse_verdict_zip(data: bytes) -> dict | None:
    """Return the verdict object inside a ``post-merge-verdict`` artifact zip, or None when it is not one."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if archive.getinfo(VERDICT_MEMBER).file_size > MAX_MEMBER_BYTES:
                return None
            parsed = json.loads(archive.read(VERDICT_MEMBER))
    except (zipfile.BadZipFile, KeyError, ValueError, RecursionError, OSError) as exc:
        logger.warning("an earlier verdict artifact is unreadable: %s", exc)
        return None
    ids = parsed.get("passed_on_retry") if isinstance(parsed, dict) else None
    if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
        logger.warning("an earlier verdict artifact has no usable passed_on_retry list")
        return None
    return parsed


def _read_one(client: GitHubClient, repo: str, run_id: int) -> dict | None:
    """Fetch and parse one earlier run's verdict artifact: one list request, one download; None when unreadable."""
    try:
        payload = client.get(f"/repos/{repo}/actions/runs/{run_id}/artifacts", {"per_page": 100})
        found = [a for a in (payload or {}).get("artifacts") or [] if a.get("name") == VERDICT_ARTIFACT and not a.get("expired")]
        if not found:
            logger.warning("run %s has no unexpired %s artifact; counting it as zero", run_id, VERDICT_ARTIFACT)
            return None
        newest = max(found, key=lambda a: str(a.get("created_at") or ""))  # a re-run leaves several: the latest attempt wins
        data = client.get_bytes(f"/repos/{repo}/actions/artifacts/{newest['id']}/zip")
    except (GitHubError, KeyError, TypeError) as exc:
        logger.warning("cannot read the verdict of run %s; counting it as zero: %s", run_id, exc)
        return None
    return _parse_verdict_zip(data)


def earlier_settled_runs(runs: list[dict], run_id: int, how_many: int) -> list[dict]:
    """The newest ``how_many`` settled main runs numbered below run ``run_id``, newest first.

    The run itself stays in the pool as a not-yet-settled newer main run, so the one settled-run rule still
    sees that it displaced an older cancelled run (which carries no verdict) and passes over it.
    """
    current = next((r for r in runs if r.get("id") == run_id), None)
    if current is None:
        logger.warning("run %s is not in the run history page; no earlier run can be named", run_id)
        return []
    marker = {**current, "status": "in_progress"}
    pool = [r for r in runs if r.get("run_number", 0) < current.get("run_number", 0)]
    chosen: list[dict] = []
    while len(chosen) < how_many:
        picked = select_verdict_run([*pool, marker]).run
        if picked is None or picked is marker:
            break
        chosen.append(picked)
        pool = [r for r in pool if r.get("run_number", 0) < picked.get("run_number", 0)]
    return chosen


class HistoryRead(NamedTuple):
    """What a history read produced: the entries (newest first, ``None`` = unreadable) and how many settled earlier
    runs the run-history page held (capped at ``window - 1``); ``available`` is None when the page could not be read."""

    entries: list
    available: int | None


def read_history(client: GitHubClient, repo: str, run_id: int, tunables: dict, lane=CORRECTNESS) -> HistoryRead:
    """Read the earlier settled runs' verdicts of ``lane`` (newest first); at most ``1 + 2 * (window - 1)`` requests.

    An unreadable run history leaves the entries empty (a window of one run, ``available`` None): the verdict is
    still written.
    """
    if not REPO_RE.fullmatch(repo):
        logger.warning("refusing repository name %r; the pass-on-retry window covers this run only", repo)
        return HistoryRead([], None)
    query = {"branch": "main", "exclude_pull_requests": "true", "per_page": int(tunables["run_history_page"])}
    try:
        payload = client.get(f"/repos/{repo}/actions/workflows/{lane.workflow}/runs", query)
    except GitHubError as exc:
        logger.warning("cannot read the run history; the pass-on-retry window covers this run only: %s", exc)
        return HistoryRead([], None)
    runs = list((payload or {}).get("workflow_runs") or [])
    earlier = earlier_settled_runs(runs, run_id, max(0, int(tunables["flaky_window_runs"]) - 1))
    return HistoryRead([_read_one(client, repo, int(run["id"])) for run in earlier], len(earlier))


def short_history(read: HistoryRead | None, tunables: dict, runs_read: int) -> bool:
    """True when history was asked for, a full window of settled runs existed (or could not be listed), and less was read.

    A repository's first runs (fewer settled earlier runs than ``window - 1``) are not short: there was nothing more to read.
    """
    window = int(tunables["flaky_window_runs"])
    if read is None or runs_read >= window:
        return False
    return read.available is None or read.available >= window - 1
