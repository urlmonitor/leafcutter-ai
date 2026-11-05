#!/usr/bin/env python3
"""
MODULE: post_merge_fix_proof
GOAL: The selection and the judgement of the fix proof: run, against a pull
    request's head, exactly the correctness-lane tests that failed in the current
    red post-merge run (the whole lane for a did-not-complete run), and say whether
    every one of them passed and which red run that proved against.
BUSINESS CONTEXT: TQ-600a-13-xvi. A pull request that declares a fix (TQ-600a-13-viii)
    is exempt from the hold only on evidence, because a declaration is something any
    pull request can write about itself. This module is the evidence's harness. It is
    DEFAULT-BRANCH code: the workflow runs under ``pull_request_target`` from a
    checkout with no ``ref``, so a pull request cannot edit the selection or the
    judgement it is measured by. The residual (test code runs inside the pytest
    process and could forge its own pass) is stated in the AC; the harness defends
    against a careless or goal-seeking edit of the harness or its config.
ARCHITECTURE: Three workflow-step subcommands plus one internal one.
    ``prepare`` (job `Prepare fix proof`, ``actions: read`` + ``issues: read``): reads
    the description from GITHUB_EVENT_PATH in Python (never echoed), calls
    ``_hold_exempt.match_declaration`` with the open ``post-merge-red`` numbers, reads
    the newest settled correctness run (``_run_history``) and classifies it; emits
    ``candidate`` / ``red_run_id`` / ``whole_lane`` only for a declared fix of a red or
    did-not-complete run. ``verify`` (same job, after ``actions/download-artifact`` of
    that run's ``post-merge-verdict``): takes the failing ids from the ARTIFACT, never
    from the notice, checks the artifact belongs to that run and that every id is a safe
    pytest node id (they become argv), and emits ``run_proof`` / ``red_run_id`` /
    ``whole_lane`` / ``failing_ids``. More than ``MAX_IDS`` ids fall back to the whole
    lane (a stronger proof that keeps the id list inside an environment variable).
    ``prove`` (job `Post-merge fix proof`, no permissions, no secrets): runs a fresh
    interpreter (``_child``) whose working directory and ``sys.path`` start at the head,
    with MAIN's ``-c pytest.ini`` whose ``-p`` plugins are imported from main's tree
    before the head is on the path (and removed from ``addopts``, so the head cannot
    supply them), MAIN's lane-report plugin loaded by file path with xfail/xpass
    recorded distinctly (``xfailed`` is never ``passed``), the
    lane selection ``manual and not timing_ratio`` and ``-p no:cacheprovider``, then
    judges the report: every wanted id ``passed`` (whole lane: no failure and
    ``_post_merge_stages.report_stage`` clean, no xfailed or xpassed test, and EVERY id
    of the baseline lane among the head's results: the red verdict's ``collected_ids``
    when ``verify`` handed over a usable list of at most ``MAX_IDS`` safe ids, else the
    ids of a collect-only of main's own lane read back through a file; an empty or
    missing baseline is an error), exit status 0, no collection error, a
    non-empty selection. Exit 5, an empty selection and a collection error are failures.
    ``prove`` prints ``proving against red run N`` first and the outcome last. The
    ``_child`` process imports nothing from ``scripts.ci``: the head's own ``scripts``
    package must be the one its tests import. Nothing here writes to the hosting service.
    TQ-600a-13-xxv: ``verify`` also reads the artifact's ``live_database`` object (``_fix_proof_live.live_part``) and emits
    ``live_proof`` / ``live_whole`` / ``live_ids`` / ``run_correctness``. Two more subcommands run in the same job only
    when ``live_proof`` is true: ``start-live`` (the lane's three databases, started by main's script because service
    containers cannot be conditional) and ``prove-live`` (reachability first, then the live ids or the whole live folder
    under the live lane's ``-m`` override, judged by ``judge_live``: a skip is never a pass; a database that never
    answers is NOT PROVEN). Both fail the one job named `Post-merge fix proof`.
"""

from __future__ import annotations

import argparse
import configparser
import importlib
import importlib.util
import json
import logging
import os
import re
import shlex
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

logger = logging.getLogger("post_merge_fix_proof")

LANE_SELECTION = "manual and not timing_ratio"  # identical to post-merge-suite.yml's correctness selection
WHOLE_LANE_TARGETS = ("tests/", "unit_tests/")
PLUGIN_FILE = Path(__file__).with_name("_lane_report_plugin.py")
MAX_IDS = 200
IDS_FILE = "collected-ids.json"  # next to the lane report: the ids a collect-only session selected
ISSUE_PAGE = 100
REPO_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
SAFE_ID = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./-]*\.py(?:::[\x20-\x7e]+)?")
EXIT_OK, EXIT_FAILED, EXIT_BAD_INPUT = 0, 1, 2
MASKED_STATES = frozenset({"xfailed", "xpassed"})  # a failure turned into one of these, or an unexpected pass: neither is a pass here
SHRUNK_ADVICE = "a branch behind main or a deleted test needs a merge from main or the break-glass route"
SOURCE_ROOT_ENV_VAR = "LEAFCUTTER_SHARED_LAYOUT_SOURCE_ROOT"  # read by the shared-layout producer and plugin (main's code)


class ProofInputError(RuntimeError):
    """An input of the proof (environment, artifact, id list) is missing or unsafe; nothing is proved."""


def _digits(text: str | None, what: str) -> str:
    """``text`` when it is a plain decimal run id, else ProofInputError."""
    if not (text and text.isascii() and text.isdigit()):
        message = f"{what} is missing or not a run id"
        raise ProofInputError(message)
    return text


def _safe_ids(values: object) -> list[str]:
    """The distinct node ids of ``values`` in order; every one must be a safe pytest node id (they become argv)."""
    if not isinstance(values, list):
        message = "the failing list is not a list"
        raise ProofInputError(message)
    ids: list[str] = []
    for value in values:
        if not isinstance(value, str) or not SAFE_ID.fullmatch(value) or ".." in value.split("::", 1)[0].split("/"):
            message = "a failing id is not a safe pytest node id; refusing all of them"
            raise ProofInputError(message)
        if value not in ids:
            ids.append(value)
    return ids


def verify(candidate: str, red_run_id: str, whole_lane: bool, verdict: dict | None) -> dict[str, str]:
    """The ``verify`` step's outputs from the downloaded verdict artifact (``None`` when no artifact was needed)."""
    if candidate != "true":
        return {"run_proof": "false"}
    red = _digits(red_run_id, "the red run id")
    if not isinstance(verdict, dict) or verdict.get("run_id") != int(red):
        message = f"the downloaded verdict is not the verdict of run {red}"
        raise ProofInputError(message)
    from scripts.ci._fix_proof_live import ended_in_live_stage, live_outputs  # noqa: PLC0415 -- after _put_root_on_path

    whole_lane = whole_lane and not ended_in_live_stage(verdict)  # a live-lane ending says nothing about the correctness lane
    try:
        ids = [] if whole_lane else _safe_ids(verdict.get("failing"))
    except ProofInputError as exc:  # an id that is not a safe node id never reaches argv; the whole lane proves more, and cannot deadlock the repair
        logger.warning("fix proof: %s; falling back to the whole lane", exc)
        ids = []
    whole = whole_lane or not ids or len(ids) > MAX_IDS
    return {
        "run_proof": "true",
        "red_run_id": red,
        "whole_lane": "true" if whole else "false",
        "failing_ids": "" if whole else "\n".join(ids),
        "collected_ids": "\n".join(_lane_ids(verdict)) if whole else "",
        **live_outputs(verdict, _safe_ids, MAX_IDS),  # TQ-600a-13-xxv: live_proof / live_whole / live_ids / run_correctness, from the artifact's live_database object
    }


def _lane_ids(verdict: dict) -> list[str]:
    """The red run's lane (``collected_ids``) as a baseline, when it is usable and small; else ``[]`` (the prove step then asks main).

    Job outputs are size-limited, so a lane of more than MAX_IDS ids, or one with an id that is not a safe node id, is not handed over.
    """
    try:
        lane = _safe_ids(verdict.get("collected_ids"))
    except ProofInputError as exc:
        logger.warning("fix proof: the verdict's lane is not usable as a baseline (%s); main's own lane will be", exc)
        return []
    return lane if len(lane) <= MAX_IDS else []


def judge_live(report: dict | None, wanted: list[str] | None, baseline: list[str] | None = None) -> list[str]:
    """The live-database judge (TQ-600a-13-xxv): why the proof failed, an empty list is a pass; any skip is a problem line."""
    from scripts.ci._fix_proof_live import judge_live as judge_live_tests  # noqa: PLC0415 -- after _put_root_on_path

    return judge_live_tests(report, wanted, baseline)


def judge(report: dict | None, wanted: list[str] | None, baseline: list[str] | None = None) -> list[str]:
    """Why the proof failed (an empty list is a pass). ``wanted`` None is the whole lane.

    A readable report, exit status 0, no collection error, a non-empty selection that ran in full; then every wanted
    id passed, or (whole lane) no failure, no xfailed or xpassed test, ``report_stage`` finds the lane finished and
    every id of ``baseline`` (the lane as main has it) is among the head's results: identity, not count, so a deleted
    test cannot be offset by an added one.
    """
    if report is None:
        return ["no readable lane report: pytest did not finish a session"]
    from scripts.ci._fix_proof_live import missing_baseline, session_problems  # noqa: PLC0415 -- after _put_root_on_path
    from scripts.ci._post_merge_stages import FAILED_STATES, report_stage  # noqa: PLC0415 -- stdlib-only, but kept out of the _child process

    results = report.get("results") or {}
    problems = session_problems(report)
    if wanted is None:
        problems += [f"{results[i]}: {i}" for i in sorted(results) if results[i] in FAILED_STATES | MASKED_STATES]
        stage = report_stage(report) if results else None
        problems += [f"the lane did not finish cleanly ({stage})"] if stage else []
        problems += missing_baseline(results, baseline, "lane", f"; {SHRUNK_ADVICE}")
    else:
        problems += [f"not passed ({results.get(i, 'not run')}): {i}" for i in wanted if results.get(i) != "passed"]
    return problems


def _emit(outputs: dict[str, str]) -> None:
    """Append the step outputs to GITHUB_OUTPUT (a multi-line value as a heredoc with a random delimiter)."""
    target = os.environ.get("GITHUB_OUTPUT")
    if not target:
        message = "GITHUB_OUTPUT is not set"
        raise ProofInputError(message)
    lines = []
    for key, value in outputs.items():
        delimiter = f"EOF_{uuid.uuid4().hex}"
        lines.append(f"{key}<<{delimiter}\n{value}\n{delimiter}\n" if "\n" in value else f"{key}={value}\n")
    try:
        with open(target, "a", encoding="utf-8") as handle:
            handle.writelines(lines)
    except OSError as exc:
        logger.warning("cannot write the step outputs %s: %s", target, exc)
        raise


def _read_json(path: Path, kind: type = dict):
    """A JSON value of type ``kind`` (object by default) from ``path``; None (logged) when absent, unreadable or another type."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        logger.warning("cannot read %s: %s", path, exc)
        return None
    return data if isinstance(data, kind) else None


class _IdCollector:
    """A collect-only session's plugin: writes the node ids of the tests it selected to ``path`` (JSON list)."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def pytest_collection_finish(self, session) -> None:
        """Write the selected ids; an unwritable file is an error, never an empty baseline."""
        try:
            self.path.write_text(json.dumps([item.nodeid for item in session.items]), encoding="utf-8")
        except OSError as exc:
            logger.warning("cannot write the collected ids %s: %s", self.path, exc)
            raise


def _put_root_on_path() -> None:
    """Make ``scripts.ci`` importable when run as ``python scripts/ci/post_merge_fix_proof.py`` (main's tree)."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _decide(client, repo: str, body: str | None) -> tuple[dict[str, str], str]:
    """Reads and decision of the ``prepare`` step: (outputs, one-line reason)."""
    from scripts.ci._github_rest import GitHubError  # noqa: PLC0415 -- after _put_root_on_path
    from scripts.ci._hold_exempt import match_declaration, open_notice_numbers  # noqa: PLC0415
    from scripts.ci._notice_render import LABEL  # noqa: PLC0415
    from scripts.ci._run_history import KIND_SETTLED, VERDICT_DID_NOT_COMPLETE, VERDICT_GREEN, classify_run, select_verdict_run  # noqa: PLC0415
    from scripts.ci.post_merge_hold import load_tunables, read_jobs, read_runs  # noqa: PLC0415

    no_proof = {"candidate": "false"}
    items = client.get(f"/repos/{repo}/issues", {"labels": LABEL, "state": "open", "per_page": ISSUE_PAGE})
    numbers = open_notice_numbers([item for item in items if isinstance(item, dict)] if isinstance(items, list) else [])
    declared = match_declaration(body, repo, numbers)
    if declared is None:
        return no_proof, "no fix of an open post-merge-red notice is declared; no proof"
    try:
        runs = read_runs(client, repo, int(load_tunables()["run_history_page"]))
    except GitHubError as exc:  # TQ-600a-13-ix: a failed or wrong-shape read is no basis for a proof
        logger.warning("fix proof: the run history could not be read (%s); no proof", exc)
        return no_proof, "the run history could not be read; no proof"
    selection = select_verdict_run(runs)
    run = selection.run
    if selection.kind != KIND_SETTLED or run is None or not isinstance(run.get("id"), int):
        return no_proof, "the suite has no settled run to prove against; no proof"
    kind = VERDICT_GREEN if run.get("conclusion") == "success" else classify_run(run, read_jobs(client, repo, run["id"]))
    if kind == VERDICT_GREEN:
        return no_proof, "the newest settled run is green; no proof"
    outputs = {"candidate": "true", "red_run_id": str(run["id"]), "whole_lane": "true" if kind == VERDICT_DID_NOT_COMPLETE else "false"}
    return outputs, f"a fix of #{declared} is declared; the newest settled run {run['id']} is {kind}"


def cmd_prepare(_args: argparse.Namespace) -> int:
    """``prepare``: decide whether a proof is wanted and against which red run."""
    from scripts.ci._github_rest import GitHubClient  # noqa: PLC0415
    from scripts.ci._hold_exempt import read_body  # noqa: PLC0415

    api_url, token, repo = (os.environ.get(name, "") for name in ("GITHUB_API_URL", "GITHUB_TOKEN", "GITHUB_REPOSITORY"))
    if not (api_url and token and REPO_RE.fullmatch(repo)):
        message = "GITHUB_API_URL, GITHUB_TOKEN or GITHUB_REPOSITORY is missing or malformed"
        raise ProofInputError(message)
    outputs, reason = _decide(GitHubClient(api_url, token), repo, read_body(os.environ.get("GITHUB_EVENT_PATH")))  # the description: never printed
    print(f"fix proof: {reason}")
    _emit(outputs)
    return EXIT_OK


def cmd_verify(args: argparse.Namespace) -> int:
    """``verify``: take the failing ids from the downloaded verdict artifact and publish the job's outputs."""
    candidate = os.environ.get("CANDIDATE", "")
    verdict = _read_json(Path(args.verdict)) if candidate == "true" else None
    outputs = verify(candidate, os.environ.get("RED_RUN_ID", ""), os.environ.get("WHOLE_LANE") == "true", verdict)
    print(f"fix proof: run_proof={outputs['run_proof']}")
    _emit(outputs)
    return EXIT_OK


def _lane_command(args: argparse.Namespace, report: Path, targets: list[str], tree: Path, *, collect_only: bool = False, selection: str = LANE_SELECTION) -> list[str]:
    """The child interpreter's command line: this very file (main's), a fresh process, ``tree`` first on its path.

    ``Path.resolve`` touches the file system (symlinks); the caller (``_run_session``) wraps this in its OSError handling.
    ``selection`` is the ``-m`` expression: the correctness lane's, or the live lane's whole-folder override.
    """
    own = ["--head", str(tree.resolve()), "--ini", str(Path(args.ini).resolve()), "--report", str(report), "--selection", selection]
    return [sys.executable, str(Path(__file__).resolve()), "_child", *own, *(["--collect-only"] if collect_only else []), "--", *targets]


def _run_session(args: argparse.Namespace, targets: list[str], *, tree: Path | None = None, collect_only: bool = False, selection: str = LANE_SELECTION) -> tuple[int, dict | None]:
    """Run the child session over ``targets`` in ``tree`` (default: the head); ``(its exit status, its lane report or None)``.

    A live-selection session (run by ``prove_live`` only after its database check) carries the live lane's marker (TQ-600a-13-xxvii).
    """
    from scripts.ci import _live_lane as live  # noqa: PLC0415 -- after _put_root_on_path

    where = tree or Path(args.head)
    env = live.lane_environ(os.environ) if selection == live.SELECTION else None
    try:
        with tempfile.TemporaryDirectory(prefix="fix-proof-") as scratch:
            report_path = Path(scratch) / "lane-report.json"
            command = _lane_command(args, report_path, targets, where, collect_only=collect_only, selection=selection)
            completed = subprocess.run(command, cwd=where, env=env, check=False)  # noqa: S603
            report = _read_json(report_path)
            if report is not None and collect_only:  # the selected ids travel in a file next to the report, never in argv or env
                report["collected_ids"] = _read_json(report_path.with_name(IDS_FILE), list) or []
            return completed.returncode, report
    except OSError as exc:
        logger.warning("cannot run the pytest session in %s: %s", where, exc)
        raise


def baseline_ids(verdict_ids: list[str], main_collected) -> list[str]:
    """The ids a whole-lane proof must find in the head's results: the red verdict's lane, else main's own lane's.

    ``main_collected`` is called (a collect-only of main's lane) only when the verdict gave no usable list.
    """
    return verdict_ids if verdict_ids else main_collected()


def cmd_prove(args: argparse.Namespace) -> int:
    """``prove``: execute the selection against the head and exit non-zero unless every selected id passed."""
    red = _digits(os.environ.get("RED_RUN_ID"), "RED_RUN_ID")
    if os.environ.get("RUN_CORRECTNESS") == "false":  # TQ-600a-13-xxv: the red run's correctness lane had nothing to prove; only live tests did
        print(f"proving against red run {red}: no correctness-lane test failed there, so nothing to prove in this step")
        return EXIT_OK
    whole = os.environ.get("WHOLE_LANE") == "true"
    wanted = None if whole else _safe_ids([line.strip() for line in os.environ.get("FAILING_IDS", "").splitlines() if line.strip()])
    if wanted is not None and not wanted:
        message = "no failing id to prove and not a whole-lane proof"
        raise ProofInputError(message)
    what = "the whole correctness lane" if wanted is None else f"{len(wanted)} failing test(s)"
    print(f"proving against red run {red}: {what}, selection '{LANE_SELECTION}'")
    baseline: list[str] = []
    if wanted is None:  # only a whole-lane proof is held to the lane's identity
        verdict_lane = _lane_ids({"collected_ids": [line.strip() for line in os.environ.get("COLLECTED_IDS", "").splitlines() if line.strip()]})
        baseline = baseline_ids(verdict_lane, lambda: _toolbox("main_lane_ids", args))
        print(f"baseline: the head lane must contain all of the {len(baseline)} tests of {'the red run' if verdict_lane else 'main'}'s lane")
    status, report = _run_session(args, list(WHOLE_LANE_TARGETS) if wanted is None else wanted)
    problems = judge(report, wanted, baseline)
    print(f"pytest session exited with status {status}")
    return conclude(problems, red, "FAILED", what)


def conclude(problems: list[str], red: str, failure_word: str, what: str) -> int:
    """Print the proof's outcome against red run ``red`` and return the exit status (non-zero when any problem)."""
    if problems:
        print(f"fix proof {failure_word} against red run {red}:")
        for problem in problems[:50]:
            print(f"  - {problem}")
        return EXIT_FAILED
    print(f"fix proof PASSED against red run {red}: {what} passed on the head")
    return EXIT_OK


def _toolbox(name: str, *args):
    """Call ``name`` of ``_fix_proof_live`` (``start_live``, ``prove_live``, ``main_lane_ids``) with this module as its first argument."""
    from scripts.ci import _fix_proof_live  # noqa: PLC0415 -- after _put_root_on_path

    return getattr(_fix_proof_live, name)(sys.modules[__name__], *args)


def ini_plugins(addopts: str) -> tuple[list[str], str]:
    """Split an ``addopts`` string into (the module names of its ``-p`` plugins, the remaining options as one string).

    ``-p no:<name>`` stays among the remaining options: it names no module to load.
    """
    tokens, names, rest, i = shlex.split(addopts), [], [], 0
    while i < len(tokens):
        token = tokens[i]
        if token == "-p" and i + 1 < len(tokens):
            name, i = tokens[i + 1], i + 2
        elif token.startswith("-p") and len(token) > 2:
            name, i = token[2:], i + 1
        else:
            rest.append(token)
            i += 1
            continue
        if name.startswith("no:"):
            rest += ["-p", name]
        else:
            names.append(name)
    return names, shlex.join(rest)


def _distinct_status(report) -> str:
    """The proof's own per-test status: unlike the post-merge run's, an xfail and an xpass are told apart from skip and pass."""
    wasxfail = hasattr(report, "wasxfail")
    if report.failed:
        return "failed"
    if getattr(report, "outcome", None) == "xfailed":  # pytest_ac_enforcement's mask: neither failed nor skipped
        return "xfailed"
    if report.skipped:
        return "xfailed" if wasxfail else "skipped"
    return "xpassed" if wasxfail else "passed"


def _load_lane_plugin():
    """MAIN's report plugin, loaded by file path as a private copy whose status mapping is the proof's own (the post-merge run's is untouched)."""
    spec = importlib.util.spec_from_file_location("_fix_proof_lane_report", PLUGIN_FILE)
    plugin = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plugin)
    plugin._status = _distinct_status
    plugin._RANK = {"passed": 0, "xpassed": 1, "skipped": 2, "xfailed": 3, "failed": 4}
    return plugin


def _load_main_plugins(ini: str, head: str, own_dir: str) -> tuple[list, str]:
    """Import the plugins MAIN's ini names from main's tree, then give the head the front of ``sys.path``.

    ``(plugin modules, the ini's addopts without them)``. The modules are imported while main's root is first, so their
    own top-level ``scripts.*`` imports are main's; the ``scripts`` modules are then dropped from ``sys.modules`` so the
    head's tests import the head's code. RESIDUAL: an import a plugin makes lazily, at run time, resolves to the head.
    """
    parser = configparser.ConfigParser(interpolation=None)
    try:
        with open(ini, encoding="utf-8") as handle:
            parser.read_file(handle)
    except OSError as exc:
        logger.warning("cannot read main's pytest.ini %s: %s", ini, exc)
        raise
    names, addopts = ini_plugins(parser.get("pytest", "addopts", fallback=""))
    main_root = os.path.realpath(Path(ini).parent)
    others = [p for p in sys.path if os.path.realpath(p or ".") not in (own_dir, main_root)]
    sys.path[:] = [main_root, *others]
    modules = [importlib.import_module(name) for name in names]
    for loaded in [n for n in sys.modules if n == "scripts" or n.startswith("scripts.")]:
        del sys.modules[loaded]
    sys.path[:] = [head, *others]
    return modules, addopts


def run_child(args: argparse.Namespace, targets: list[str]) -> int:
    """``_child``: one pytest session over the head, under main's ini, main's plugins and main's report plugin.

    A fresh interpreter: the script's own directory (main's ``scripts/ci``) leaves ``sys.path`` and the head takes the
    front, as with ``python -m pytest`` run in the head, so the head's tests import the head's code. Every plugin of the
    session (the ini's ``-p`` entries and the lane report) is main's, loaded by this process before the head is on the
    path; the ini's own ``-p`` entries are removed from ``addopts`` so pytest cannot resolve them to the head.
    """
    import pytest  # noqa: PLC0415 -- only the child session needs it

    head, own_dir = os.path.realpath(args.head), os.path.realpath(Path(__file__).parent)
    os.environ[SOURCE_ROOT_ENV_VAR] = head  # main's shared-layout code builds from the code under test; set before it is imported
    try:
        os.chdir(head)
        modules, addopts = _load_main_plugins(args.ini, head, own_dir)
        plugins = [*modules, _load_lane_plugin(), *([_IdCollector(Path(args.report).with_name(IDS_FILE))] if args.collect_only else [])]
    except (OSError, ImportError, AttributeError, configparser.Error, ValueError) as exc:
        logger.warning("cannot prepare the head's pytest session: %s", exc)
        return EXIT_BAD_INPUT
    argv = ["-c", args.ini, "-o", f"addopts={addopts}", "--rootdir", head, "-m", args.selection, "-p", "no:cacheprovider", "--lane-report", args.report, *(["--collect-only"] if args.collect_only else []), "--", *targets]
    return int(pytest.main(argv, plugins=plugins))


def build_parser() -> argparse.ArgumentParser:
    """One subcommand per workflow step (``_child`` is internal to ``prove``)."""
    parser = argparse.ArgumentParser(description="Post-merge fix proof: prepare, verify, prove.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare", help="decide whether a proof runs, against which red run")
    verify_cmd = sub.add_parser("verify", help="take the failing ids from the verdict artifact")
    verify_cmd.add_argument("--verdict", required=True)
    sub.add_parser("start-live", help="start the live lane's three disposable databases")
    for name in ("prove", "prove-live", "_child"):
        step = sub.add_parser(name, help=argparse.SUPPRESS if name == "_child" else "run the selection against the head")
        step.add_argument("--head", required=True)
        step.add_argument("--ini", required=True)
        if name == "_child":
            step.add_argument("--report", required=True)
            step.add_argument("--collect-only", action="store_true")
            step.add_argument("--selection", default=LANE_SELECTION)
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; any unusable input is a non-zero exit, never a pass."""
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s", stream=sys.stderr)
    arguments = list(sys.argv[1:] if argv is None else argv)
    own, targets = (arguments[: arguments.index("--")], arguments[arguments.index("--") + 1 :]) if "--" in arguments else (arguments, [])
    opts = build_parser().parse_args(own)
    if opts.command == "_child":
        return run_child(opts, targets)
    try:
        _put_root_on_path()
        steps = {"prepare": cmd_prepare, "verify": cmd_verify, "prove": cmd_prove, "start-live": lambda o: _toolbox("start_live", o), "prove-live": lambda o: _toolbox("prove_live", o)}
        return steps[opts.command](opts)
    except ProofInputError as exc:
        logger.warning("fix proof: %s", exc)
        print(f"fix proof could not run: {exc}")
        return EXIT_BAD_INPUT
    except (OSError, ValueError, KeyError) as exc:  # GitHubError is a RuntimeError: caught below with the rest of the read failures
        logger.warning("fix proof: %s", exc)
        return EXIT_BAD_INPUT
    except RuntimeError as exc:
        logger.warning("fix proof: a read failed: %s", exc)
        return EXIT_BAD_INPUT


if __name__ == "__main__":
    sys.exit(main())
