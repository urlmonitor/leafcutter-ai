"""
MODULE: _fix_proof_live
GOAL: The live-database half of the post-merge fix proof that needs no session of its own:
    which live tests the red run's verdict asks to prove, how a head's live-lane report is
    judged, and how the proof starts the lane's three disposable databases.
BUSINESS CONTEXT: TQ-600a-13-xxv. The live-database tests skip without a database, so a proof
    that started none would "pass" every failing live test by skipping it and release the
    repository-wide hold with nothing proven. Here a skip, for any reason, is never a pass; the
    judgement imports ``_live_lane.classify_live_results`` instead of restating it.
ARCHITECTURE: Pure except ``start_databases`` (``docker run`` subprocesses) and the two workflow steps
    ``start_live`` / ``prove_live`` (the ``start-live`` / ``prove-live`` subcommands) with ``main_lane_ids``
    (the baseline collect-only both proofs use); those take ``post_merge_fix_proof`` itself as their first argument
    (its session runner and error type; importing it by name would load a second copy when it runs as a script).
    ``live_part`` is
    called by ``post_merge_fix_proof.verify`` and reads ONLY the artifact's ``live_database``
    object (never the notice, never the pull request). ``judge_live`` mirrors ``judge``: an empty
    list is a pass. Imported after ``post_merge_fix_proof`` has put the default branch's root on
    ``sys.path``; the ``_child`` process never imports it.
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path

from scripts.ci import _live_lane as live
from scripts.ci._post_merge_stages import STAGE_LIVE_STARTUP, STAGE_LIVE_UNREACHABLE

logger = logging.getLogger("post_merge_fix_proof")

LIVE_TARGETS = ("tests/knowledge_live/",)  # the live lane's one pinned input: the folder, collected fresh
MAX_SHOWN = 20
START_ATTEMPT_PAUSE = 2.0


def ended_in_live_stage(verdict: dict) -> bool:
    """True when the run's combined stage is one of the live lane's: the correctness lane itself did not fail to complete.

    The combined verdict ranks the correctness lane's own stage first, so a live stage there means the correctness lane
    completed (red or green) and only the live lane did not.
    """
    return verdict.get("stage") in (STAGE_LIVE_STARTUP, STAGE_LIVE_UNREACHABLE)


def correctness_lane_green(verdict: dict) -> bool:
    """True when the correctness lane's OWN verdict is green, whatever the live lane did.

    The combined ``verdict`` cannot say it (a red live lane makes it red). The lane's own fields can: no failing test, no
    repeated pass-on-retry (the other way the lane turns red with an empty ``failing``), and no stage of its own (the
    combined stage is either empty or a live stage when the correctness lane completed).
    """
    clean = not verdict.get("failing") and not verdict.get("repeated_pass_on_retry")
    return clean and (verdict.get("stage") is None or ended_in_live_stage(verdict))


def live_part(verdict: dict, safe_ids, max_ids: int) -> dict[str, str]:
    """The ``verify`` outputs for the live part of a red run: ``live_proof`` / ``live_whole`` / ``live_ids``.

    A red live lane proves its ``failing`` ids; a did-not-complete one (empty ``failing``) proves the whole live folder; a
    green or absent one starts no live part. ``safe_ids`` (the caller's validator) refuses an id that could become an
    option: the whole folder is the stronger proof and replaces them.
    """
    lane = verdict.get("live_database")
    lane_fields: dict = lane if isinstance(lane, dict) else {}
    state = lane_fields.get("verdict")
    if state not in ("red", "did_not_complete"):
        return {"live_proof": "false", "live_whole": "false", "live_ids": ""}
    ids: list[str] = []
    if state == "red":
        try:
            ids = safe_ids(lane_fields.get("failing"))
        except RuntimeError as exc:  # ProofInputError: the whole folder proves more and cannot deadlock the repair
            logger.warning("fix proof: %s; falling back to the whole live folder", exc)
    whole = state == "did_not_complete" or not ids or len(ids) > max_ids
    return {"live_proof": "true", "live_whole": "true" if whole else "false", "live_ids": "" if whole else "\n".join(ids)}


def live_outputs(verdict: dict, safe_ids, max_ids: int) -> dict[str, str]:
    """The live half of the ``verify`` outputs: ``live_part`` plus ``run_correctness``.

    ``run_correctness`` is false when a live part exists and the correctness lane's OWN verdict is green: it has nothing to prove.
    """
    part = live_part(verdict, safe_ids, max_ids)
    only_live = part["live_proof"] == "true" and correctness_lane_green(verdict)
    return {"run_correctness": "false" if only_live else "true", **part}


def judge_live(report: dict | None, wanted: list[str] | None, baseline: list[str] | None = None) -> list[str]:
    """Why the live proof failed (an empty list is a pass). ``wanted`` None is the whole live folder.

    Every wanted live test must have ``passed``; a skip, whatever its reason, is a problem line naming the test.
    The whole folder judges every result the same way (an xfailed or xpassed test is not a pass either) and additionally
    needs a pass and every id of ``baseline`` (the folder as main has it) among the head's results.
    """
    if report is None:
        return ["no readable lane report: pytest did not finish a session"]
    results = report.get("results") or {}
    sorted_out = live.classify_live_results(report)
    reasons = {s["id"]: s["reason"] for s in sorted_out["skipped"]}
    problems = session_problems(report)
    for node_id in wanted if wanted is not None else sorted(results):
        status = results.get(node_id)
        if status == "passed":
            continue
        if node_id in sorted_out["unreachable_skips"]:
            problems.append(f"skipped (no database was reachable): {node_id}")
        elif node_id in reasons:
            problems.append(f"skipped ({reasons[node_id]}): {node_id}")
        else:
            problems.append(f"not passed ({status or 'not run'}): {node_id}")
    if wanted is None:
        problems += ["no live test passed"] if results and not sorted_out["passed"] else []
        problems += missing_baseline(results, baseline, "live folder")
    return problems


def session_problems(report: dict) -> list[str]:
    """The lane-independent problems of a readable lane report: collection errors, a non-zero exit, an empty or cut-short session."""
    results = report.get("results") or {}
    problems = []
    if report.get("collection_errors"):
        problems.append(f"{len(report['collection_errors'])} collection error(s)")
    if report.get("exitstatus") != 0:
        problems.append(f"pytest exited with status {report.get('exitstatus')}")
    if not results:
        problems.append("nothing was selected or run")
    if report.get("ran", len(results)) < report.get("expected", 0):
        problems.append("the session was cut short")
    return problems


def missing_baseline(results: dict, baseline: list[str] | None, label: str, advice: str = "") -> list[str]:
    """One problem line when the head's ``label`` lacks baseline ids (identity, not count); ``[]`` when none is missing."""
    missing = [i for i in baseline or [] if i not in results]
    if not missing:
        return []
    shown = ", ".join(missing[:MAX_SHOWN])
    return [f"head {label} is missing {len(missing)} of {len(baseline or [])} baseline tests (first {min(len(missing), MAX_SHOWN)}: {shown}){advice}"]


def docker_commands() -> list[list[str]]:
    """The ``docker run`` command of each of the lane's three instances, from the one definition (``_live_lane.INSTANCES``)."""
    memory = [
        "-e", f"NEO4J_server_memory_heap_initial__size={live.MEMORY['heap_initial']}",
        "-e", f"NEO4J_server_memory_heap_max__size={live.MEMORY['heap_max']}",
        "-e", f"NEO4J_server_memory_pagecache_size={live.MEMORY['pagecache']}",
    ]  # fmt: skip
    return [
        ["docker", "run", "-d", "--name", str(i["name"]),"-p", f"{i['port']}:7687", "-e", f"NEO4J_AUTH={i['auth']}", *memory, str(i["image"])]
        for i in live.INSTANCES
    ]


def start_databases(limit: float) -> bool:
    """Start the three instances and wait up to ``limit`` seconds for each to hold a connection; False when any never does."""
    try:
        for command in docker_commands():
            subprocess.run(command, check=True, capture_output=True, text=True)  # noqa: S603
    except (OSError, subprocess.CalledProcessError) as exc:
        logger.warning("cannot start the live databases: %s", exc)
        return False
    deadline = time.monotonic() + limit
    for instance in live.INSTANCES:
        address = f"127.0.0.1:{instance['port']}"
        while not live.check_database(address, 0.0)["reachable"]:
            if time.monotonic() >= deadline:
                logger.warning("the live database at %s never became healthy", address)
                return False
            time.sleep(START_ATTEMPT_PAUSE)
    return True


def main_lane_ids(proof, args, wanted_targets: tuple[str, ...] | None = None, selection: str | None = None) -> list[str]:
    """Collect-only of MAIN's lane (the correctness lane, or the live folder), in main's tree under main's ini and plugins; the ids it selected.

    ``proof`` is ``post_merge_fix_proof``; the defaults are its whole-lane targets and selection. The ids come back through
    a file in the session's scratch directory (never argv or env). A collection error leaves a partial list, which is used
    and logged as partial; no report, or an empty lane, is an error (the baseline is never silently skipped).
    """
    main_tree = Path(args.ini).resolve().parent
    targets = [t for t in wanted_targets or proof.WHOLE_LANE_TARGETS if (main_tree / t).is_dir()]
    _status, report = proof._run_session(args, targets, tree=main_tree, collect_only=True, selection=selection or proof.LANE_SELECTION) if targets else (proof.EXIT_BAD_INPUT, None)  # noqa: SLF001
    if report is None:
        message = "main's lane could not be collected, so there is no baseline to hold the head's lane to"
        raise proof.ProofInputError(message)
    if report.get("collection_errors"):
        logger.warning("main's lane baseline is partial: %d collection error(s)", len(report["collection_errors"]))
        print("baseline is partial: main's own collection had errors; using what it collected")
    ids = report.get("collected_ids")
    if not isinstance(ids, list) or not ids:
        message = "main's correctness lane collected no tests, so there is no baseline to hold the head's lane to"
        raise proof.ProofInputError(message)
    return [i for i in ids if isinstance(i, str)]


def _startup_limit(proof) -> float:
    """The live lane's start-up limit from the environment; a malformed value is a ``proof.ProofInputError`` that names the variable."""
    try:
        return live.startup_limit(os.environ)
    except ValueError as exc:
        raise proof.ProofInputError(str(exc)) from exc


def start_live(proof, _args) -> int:
    """``start-live``: start the lane's three disposable databases (same definition as the live lane's services).

    ``proof`` is ``post_merge_fix_proof`` (the toolbox of the running module). A ``LIVE_DB_ADDRESS`` other than the lane's
    default means the database is supplied from outside (a stand-in in the unit layer): nothing is started and the next
    step's reachability check judges it.
    """
    address = os.environ.get("LIVE_DB_ADDRESS", live.DEFAULT_ADDRESS)
    if address != live.DEFAULT_ADDRESS:
        print(f"live database at {address} is supplied from outside; starting none")
        return proof.EXIT_OK
    if not start_databases(_startup_limit(proof)):
        print("the live databases did not become healthy: the live tests are not proven")
        return proof.EXIT_FAILED
    print("the three live databases are up")
    return proof.EXIT_OK


def prove_live(proof, args) -> int:
    """``prove-live``: execute the red run's live tests (or the whole live folder) against the head, under the live lane's selection.

    The database must be reachable (a probe, then a held first connection) before any test runs; when it never is, nothing
    runs and the proof is NOT PROVEN (a non-zero exit, so the job named ``Post-merge fix proof`` is not success). The
    judgement is ``judge_live``: a skip, for any reason, is not a pass.
    """
    red = proof._digits(os.environ.get("RED_RUN_ID"), "RED_RUN_ID")  # noqa: SLF001 -- the running module's own helpers
    wanted = None if os.environ.get("LIVE_WHOLE") == "true" else proof._safe_ids([line.strip() for line in os.environ.get("LIVE_IDS", "").splitlines() if line.strip()])  # noqa: SLF001
    what = "the whole live-database folder" if wanted is None else f"{len(wanted)} failing live-database test(s)"
    print(f"proving against red run {red}: {what}, selection '{live.SELECTION}'")
    reach = live.check_database(os.environ.get("LIVE_DB_ADDRESS", live.DEFAULT_ADDRESS), _startup_limit(proof))
    if not reach["reachable"]:
        print(f"fix proof NOT PROVEN against red run {red}: the live database is not reachable ({reach['detail']}); no live test was run")
        return proof.EXIT_FAILED
    if wanted is not None and not wanted:
        message = "no failing live id to prove and not a whole-folder proof"
        raise proof.ProofInputError(message)
    baseline = main_lane_ids(proof, args, LIVE_TARGETS, live.SELECTION) if wanted is None else []
    status, report = proof._run_session(args, list(LIVE_TARGETS) if wanted is None else wanted, selection=live.SELECTION)  # noqa: SLF001
    problems = judge_live(report, wanted, baseline)
    print(f"pytest session exited with status {status}")
    return proof.conclude(problems, red, "NOT PROVEN", what)
