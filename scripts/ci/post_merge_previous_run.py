#!/usr/bin/env python3
"""
MODULE: post_merge_previous_run
GOAL: Print the id of the settled timing-lane run that came immediately before a
    given timing run, so the follow-up workflow can fetch that run's verdict
    artifact. Prints nothing when there is no such run.
BUSINESS CONTEXT: TQ-600a-13-xii. The ``post-merge-timing`` notice names tests
    that newly entered the lane by comparing two consecutive timing verdicts. The
    notice job has only the triggering run's id, so it asks the run history for
    the one before it. No previous run is the normal first-run case, never an
    error: the notice then names no entrant.
ARCHITECTURE: One read of the timing workflow's run history (``post_merge_notice.read_runs``
    with the timing ``LaneSpec``), then ``_run_history.select_verdict_run`` over the
    runs numbered below the triggering one: the ONE settled-run rule, so a cancelled
    run superseded by a newer one, an unfinished run and a run that did not test
    main are all passed over. CLI: ``--api-url --repo --run-id`` with the token in
    GITHUB_TOKEN, plus ``--lane`` (default ``timing``, so the timing workflow is
    unchanged; ``correctness`` serves the flaky notice's not-reproduced reds,
    TQ-600a-13-xiii); the id (or an empty line) goes to stdout, and exit is 0 whenever
    the history was read (the step must not fail the job over a missing predecessor),
    2 on unusable input or an unreadable history.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as `python scripts/ci/post_merge_previous_run.py`: make `scripts.ci` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.ci._github_rest import GitHubClient, GitHubError  # noqa: E402
from scripts.ci._notice_render import LANES, TIMING  # noqa: E402
from scripts.ci._run_history import select_verdict_run  # noqa: E402
from scripts.ci.post_merge_notice import REPO_RE, read_runs  # noqa: E402

logger = logging.getLogger("post_merge_previous_run")

EXIT_OK, EXIT_BAD_INPUT = 0, 2


def previous_settled_run(runs: list[dict], run_id: int) -> dict | None:
    """Return the newest settled main-branch run numbered below run ``run_id``, or None."""
    current = next((r for r in runs if r.get("id") == run_id), None)
    if current is None:
        logger.warning("run %s is not in the timing run history; no previous run can be named", run_id)
        return None
    older = [r for r in runs if r.get("run_number", 0) < current.get("run_number", 0)]
    # The triggering run stays in the list as a not-yet-settled newer main run, so the one settled-run rule
    # still sees that it displaced an older cancelled run (which then carries no verdict) and passes over it.
    return select_verdict_run([*older, {**current, "status": "in_progress"}]).run


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: print the previous settled timing run id (or an empty line)."""
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s", stream=sys.stderr)
    parser = argparse.ArgumentParser(description="Print the id of the settled timing run before a given one.")
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--run-id", required=True, type=int)
    parser.add_argument("--lane", choices=sorted(LANES), default=TIMING.name, help="whose run history to read (default: timing, TQ-600a-13-xii)")
    opts = parser.parse_args(sys.argv[1:] if argv is None else argv)
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token or not REPO_RE.fullmatch(opts.repo):
        logger.warning("GITHUB_TOKEN is not set or the repository name %r is refused", opts.repo)
        return EXIT_BAD_INPUT
    try:
        runs = read_runs(GitHubClient(opts.api_url, token), opts.repo, LANES[opts.lane])
    except GitHubError as exc:
        logger.warning("cannot read the %s run history: %s", opts.lane, exc)
        return EXIT_BAD_INPUT
    previous = previous_settled_run(runs, opts.run_id)
    sys.stdout.write(f"{previous['id']}\n" if previous else "\n")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
