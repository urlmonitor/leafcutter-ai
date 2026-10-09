#!/usr/bin/env python3
"""
MODULE: post_merge_suite
GOAL: Execute the correctness lane (the excluded ``manual`` tests minus the
    timing lane), re-execute ONLY its first-run failures once, classify the
    result per test, and turn it into the run's verdict and exit status.
BUSINESS CONTEXT: TQ-600a-13-ii / -i. Tests the default run no longer collects
    must still run somewhere that fails something. A single failure is weak
    evidence, so exactly the failures are re-executed once on a fresh machine;
    but a failure that vanishes on retry may be the very shared-layout
    corruption these tests guard, so a fail-then-pass is NAMED
    (``passed_on_retry``), never folded into an ordinary pass.
ARCHITECTURE: All decision logic lives here; ``post-merge-suite.yml`` is a thin
    caller of the CLI below. In-process API (injected runner, used by the unit
    tests): ``run_with_retry`` / ``classify`` / ``exit_status``. CLI, one
    subcommand per workflow step: ``run`` (first execution; exits 0 whenever it
    produced a readable report, test failures are data), ``retry`` (re-executes
    exactly the handed-over ids under the SAME ``-m`` selection, in another job),
    ``verdict`` (reads both reports, writes ``post-merge-verdict.json``; ``--lane timing``
    labels it for ``post-merge-timing.yml``, which reuses every other subcommand as is),
    ``exit-status`` (the named ``Verdict:`` steps fail through it). The verdict
    comes from per-test reports written by ``_lane_report_plugin``, never from
    pytest exit statuses. Which stage a run stopped at is decided by
    ``_post_merge_stages`` from the report AND from the ``needs.run.result`` /
    ``needs.retry.result`` values the verdict step receives as ``RUN_RESULT`` /
    ``RETRY_RESULT``. Stdlib-only. TQ-600a-13-xiii adds the pass-on-retry
    history window at the marked extension point in ``build_verdict_file``.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as `python scripts/ci/post_merge_suite.py`: make `scripts.ci` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.ci._post_merge_stages import (  # noqa: E402
    FAILED_STATES,
    REPORT_ABSENT,
    REPORT_OK,
    REPORT_UNREADABLE,
    lane_stage,
    normalize_job_result,
)

logger = logging.getLogger("post_merge_suite")

SCHEMA_VERSION = 2
LANE = "correctness"
LANES = (LANE, "timing")
PLUGIN_ARGS = ["-p", "scripts.ci._lane_report_plugin"]
FIRST_REPORT = "first-run-report/first-run-report.json"
RETRY_REPORT = "retry-report/retry-report.json"


class LaneReportError(RuntimeError):
    """The lane produced no readable per-test report, so no verdict can be derived from it."""


# --------------------------------------------------------------------------- pure classification
def _failed_ids(report: dict) -> list[str]:
    """Return the sorted node ids a per-test report marks as failed."""
    return sorted(node_id for node_id, status in report.items() if status in FAILED_STATES)


def classify(first: dict, retry: dict | None) -> dict:
    """Classify a first-run report and a retry report into a verdict dict.

    A first-run failure absent from the retry report, or not ``passed`` in it,
    counts as failed on both executions: it can never read as passed-on-retry.
    """
    retried = retry or {}
    first_failures = _failed_ids(first)
    passed_on_retry = [i for i in first_failures if retried.get(i) == "passed"]
    failing = [i for i in first_failures if i not in passed_on_retry]
    return {
        "verdict": "red" if failing else "green",
        "collected": len(first),
        "first_run_failures": first_failures,
        "failing": failing,
        "passed_on_retry": passed_on_retry,
    }


def run_with_retry(runner) -> dict:
    """Run the lane once; re-run exactly the failed ids once; return the verdict dict.

    ``runner(None)`` runs the whole lane, ``runner(ids)`` runs exactly those ids.
    """
    first = runner(None)
    failures = _failed_ids(first)
    retry = runner(failures) if failures else None
    return classify(first, retry)


def exit_status(verdict: dict) -> int:
    """Return 0 exactly when the verdict is green."""
    return 0 if verdict["verdict"] == "green" else 1


# --------------------------------------------------------------------------- reports and the verdict file
def load_report(path: Path) -> tuple[dict | None, str]:
    """Read a lane report file; return (report, state), state one of ok | absent | unreadable.

    ``unreadable`` is a file that exists but is corrupt, truncated or not a lane report: a different
    ending from a file that was never written.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("lane report %s not found", path)
        return None, REPORT_ABSENT
    except (OSError, ValueError) as exc:
        logger.warning("lane report %s is unreadable: %s", path, exc)
        return None, REPORT_UNREADABLE
    if not isinstance(data, dict) or not isinstance(data.get("results"), dict):
        logger.warning("lane report %s has no results object", path)
        return None, REPORT_UNREADABLE
    return data, REPORT_OK


def read_report(path: Path) -> dict | None:
    """Read a lane report file; None when it is absent, unreadable or not a lane report."""
    return load_report(path)[0]


def _run_context(env: dict) -> dict:
    """Return the run-identifying fields of the verdict file from the runner's standard variables."""
    run_id = env.get("GITHUB_RUN_ID", "")
    server, repo = env.get("GITHUB_SERVER_URL", ""), env.get("GITHUB_REPOSITORY", "")
    return {
        "head_sha": env.get("GITHUB_SHA", ""),
        "ref": env.get("GITHUB_REF", ""),
        "event": env.get("GITHUB_EVENT_NAME", ""),
        "run_id": int(run_id) if run_id.isdigit() else 0,
        "run_url": f"{server}/{repo}/actions/runs/{run_id}",
    }


def build_verdict_file(
    first: dict | None,
    retry: dict | None,
    env: dict,
    *,
    run_result: str = "",
    retry_result: str = "",
    first_state: str = REPORT_ABSENT,
    lane: str = LANE,
) -> dict:
    """Build the ``post-merge-verdict.json`` object from the two reports (None = absent).

    ``run_result`` / ``retry_result`` are the dependency results of the verdict job and ``first_state``
    says whether a missing first-run report was absent or unreadable; see ``_post_merge_stages``.
    ``lane`` (``correctness`` | ``timing``, TQ-600a-13-xii) only labels the file: both lanes classify
    identically, and an empty lane of either kind is did_not_complete at stage ``empty_selection``.
    Green is only ever the absence of every did-not-complete stage AND of every failure.
    ``collection_errors`` is always present (``[]`` when none): they are never failing tests.
    """
    results = (first or {}).get("results", {})
    stage = lane_stage(first, retry, run_result=run_result, retry_result=retry_result, first_state=first_state)
    verdict = classify(results, (retry or {}).get("results"))
    if stage:
        verdict["verdict"] = "did_not_complete"
    # TQ-600a-13-xiii extension point: read earlier verdicts, fill the window and the escalation list.
    window = {node_id: 1 for node_id in verdict["passed_on_retry"]}
    errors = sorted((first or {}).get("collection_errors") or [])
    return {
        "collection_errors": errors,
        "schema_version": SCHEMA_VERSION,
        "lane": lane,
        "verdict": verdict["verdict"],
        "stage": stage,
        "collected": verdict["collected"],
        "skipped": list(results.values()).count("skipped"),
        "collected_ids": sorted(results),
        "first_run_failures": verdict["first_run_failures"],
        "failing": verdict["failing"],
        "passed_on_retry": verdict["passed_on_retry"],
        "repeated_pass_on_retry": [],
        "pass_on_retry_window": window,
        "window_runs_read": 1,
        "run_runner": (first or {}).get("runner"),
        "retry_runner": (retry or {}).get("runner"),
        **_run_context(env),
    }


# --------------------------------------------------------------------------- executing pytest
def execute_lane(command: list[str], report_path: Path, node_ids: list[str] | None = None) -> dict:
    """Run the lane's pytest command (plus exact node ids for a retry); return the per-test report.

    The command's own ``-m`` selection is kept for a retry: node ids alone would be
    deselected by pytest.ini's default ``-m`` and execute nothing.
    """
    try:
        report_path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("cannot clear stale report %s: %s", report_path, exc)
        raise
    argv = [*command, *PLUGIN_ARGS, "--lane-report", str(report_path)]
    if node_ids:
        argv += ["--", *node_ids]
    try:
        completed = subprocess.run(argv, check=False)
    except OSError as exc:
        logger.warning("cannot execute %s: %s", argv[0], exc)
        raise
    logger.info("pytest exited with status %s (informational: the verdict comes from the report)", completed.returncode)
    report = read_report(report_path)
    if report is None:
        detail = f"no readable lane report at {report_path}"
        raise LaneReportError(detail)
    return report


def _set_output(key: str, value: str) -> None:
    """Append ``key=value`` to the step's GITHUB_OUTPUT file when the runner provides one."""
    target = os.environ.get("GITHUB_OUTPUT")
    if not target:
        return
    try:
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(f"{key}={value}\n")
    except OSError as exc:
        logger.warning("cannot write step output %s: %s", key, exc)
        raise


def _write_text(path: Path, text: str) -> None:
    """Write a text file, creating its directory."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError as exc:
        logger.warning("cannot write %s: %s", path, exc)
        raise


# --------------------------------------------------------------------------- CLI
def _split_command(argv: list[str]) -> tuple[list[str], list[str]]:
    """Split argv at the first ``--`` into (own options, the pytest command)."""
    if "--" not in argv:
        return argv, []
    index = argv.index("--")
    return argv[:index], argv[index + 1 :]


def _cmd_run(opts: argparse.Namespace, command: list[str]) -> int:
    """First execution: always exit 0 when a report exists; hand over the failure ids."""
    report = execute_lane(command, Path(opts.report))
    failures = _failed_ids(report["results"])
    _write_text(Path(opts.failures), "".join(f"{i}\n" for i in failures))
    _set_output("failure_count", str(len(failures)))
    logger.info("first execution: %d collected, %d failed", len(report["results"]), len(failures))
    return 0


def _read_failure_ids(path: Path) -> list[str]:
    """Read the handed-over failure list; refuse ids that could be read as pytest options."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        logger.warning("cannot read the failure list %s: %s", path, exc)
        raise
    ids = [line.strip() for line in lines if line.strip()]
    bad = [i for i in ids if i.startswith("-")]
    if bad:
        detail = f"refusing node ids that look like options: {bad}"
        raise LaneReportError(detail)
    return ids


def _cmd_retry(opts: argparse.Namespace, command: list[str]) -> int:
    """Second execution of exactly the handed-over ids; exit 0 when its report is readable."""
    ids = _read_failure_ids(Path(opts.failures))
    execute_lane(command, Path(opts.report), ids)
    return 0


def _cmd_verdict(opts: argparse.Namespace, _command: list[str]) -> int:
    """Classify both reports, write the verdict file, publish the verdict as a step output."""
    base = Path(opts.artifacts)
    first, first_state = load_report(base / FIRST_REPORT)
    retry, _retry_state = load_report(base / RETRY_REPORT)
    verdict_file = build_verdict_file(
        first,
        retry,
        dict(os.environ),
        run_result=normalize_job_result(os.environ.get("RUN_RESULT")),  # missing or odd means unknown, never green
        retry_result=normalize_job_result(os.environ.get("RETRY_RESULT")),
        first_state=first_state,
        lane=opts.lane,
    )
    _write_text(Path(opts.output), json.dumps(verdict_file, indent=2) + "\n")
    _set_output("verdict", verdict_file["verdict"])
    _append_summary(verdict_file)
    logger.info("verdict: %s (stage: %s)", verdict_file["verdict"], verdict_file["stage"])
    return 0


def _append_summary(verdict_file: dict) -> None:
    """Append one line per passed-on-retry id and per failing id to the step summary, when there is one.

    Makes a fail-then-pass visible on a green run. A summary that cannot be written is logged
    and dropped: nothing but the verdict may change this run's conclusion.
    """
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if not target:
        return
    lines = [f"- passed on retry: `{i}`\n" for i in verdict_file["passed_on_retry"]]
    lines += [f"- FAILING: `{i}`\n" for i in verdict_file["failing"]]
    try:
        with open(target, "a", encoding="utf-8") as handle:
            handle.writelines(lines)
    except OSError as exc:
        logger.warning("cannot write the step summary %s: %s", target, exc)


def _cmd_exit_status(opts: argparse.Namespace, _command: list[str]) -> int:
    """Exit with the verdict file's status: non-zero unless green."""
    try:
        verdict = json.loads(Path(opts.verdict_file).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("cannot read the verdict file %s: %s", opts.verdict_file, exc)
        raise
    return exit_status(verdict)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser: one subcommand per workflow step."""
    parser = argparse.ArgumentParser(description="Post-merge correctness-lane run, retry and verdict.")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="first execution; command after --")
    run.add_argument("--report", required=True)
    run.add_argument("--failures", required=True)
    retry = sub.add_parser("retry", help="re-execute the listed ids; command after --")
    retry.add_argument("--failures", required=True)
    retry.add_argument("--report", required=True)
    verdict = sub.add_parser("verdict", help="classify the reports and write the verdict file")
    verdict.add_argument("--artifacts", required=True)
    verdict.add_argument("--output", required=True)
    verdict.add_argument("--lane", choices=LANES, default=LANE, help="which lane's verdict file to write")
    status = sub.add_parser("exit-status", help="exit non-zero unless the verdict file is green")
    status.add_argument("--verdict-file", required=True)
    return parser


_HANDLERS = {"run": _cmd_run, "retry": _cmd_retry, "verdict": _cmd_verdict, "exit-status": _cmd_exit_status}


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; a missing report or unreadable input is an error exit, never a pass."""
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    own, command = _split_command(list(sys.argv[1:] if argv is None else argv))
    opts = build_parser().parse_args(own)
    if opts.command in ("run", "retry") and not command:
        logger.error("%s needs the pytest command after --", opts.command)
        return 2
    try:
        return _HANDLERS[opts.command](opts, command)
    except (LaneReportError, OSError):
        logger.exception("%s failed", opts.command)
        return 2


if __name__ == "__main__":
    sys.exit(main())
