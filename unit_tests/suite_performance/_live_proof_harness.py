"""Test infrastructure for TQ-600a-13-xxv (the fix proof of a live-database red run). Not a test: underscore-named.

Builds on ``_proof_harness`` (the two-source ``ProofRun`` executor, the served history and notice) and ``_live_lane_harness``
(the stand-in database, the real ``verdict`` producer). ``driven_live`` is ``_proof_harness.driven`` plus: a live folder in
BOTH the default-branch tree and the head tree (each live test writes a witness line when it really runs), the red run's
verdict artifact written by the REAL ``verdict`` entry point over seeded lane reports, and the stand-in database address
substituted into the workflow (``LIVE_DB_ADDRESS``).

ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds this), on top of ``_live_lane_harness``:

* ``post_merge_fix_proof.verify`` reads ``live_database`` from the downloaded verdict: ``failing`` are the live ids to prove; a
  ``did_not_complete`` live lane (empty ``failing``) means the WHOLE live folder; a green live lane starts no live part. The
  live part's inputs travel as job outputs / env exactly as the correctness ones do.
* The job ``Post-merge fix proof`` runs the live part (its own step(s), whose names contain ``live``) only when the red run's
  live lane was red or did not complete, against the database at ``LIVE_DB_ADDRESS`` (an ``env:`` key of that job or its
  steps), under the live lane's own marker override (so ``manual`` live tests execute), and its failure fails the job.
* ``post_merge_fix_proof.judge_live(report, wanted, baseline=None) -> list[str]`` is the live judge: an empty list is a pass;
  ``wanted`` None is the whole live folder. A wanted live test is a pass only if it ``passed``; any skip, whatever its reason
  (recognised no-database reasons included), is a problem line naming the id. It reuses ``post_merge_suite``'s live classification.
* The proof prints ``not proven`` when the database never became healthy, and runs no live test then.
"""

from __future__ import annotations

import json
import tempfile
from contextlib import contextmanager
from pathlib import Path

from ._live_lane_harness import OTHER_REASON, live_report, live_test, nid, point_at, report, verdict_cli
from ._notice_fakes import REPO, SERVER
from ._proof_harness import (
    HEAD_SHA,
    PR_NUMBER,
    PREPARE,
    PROVE,
    RED_HEAD,
    WORKFLOW,
    Proof,
    ProofRun,
    _write,
    serve_history,
    stage_head,
    stage_main,
)
from ._workflow_jobs import REPO_ROOT, find_job, load_workflow

LANE_MARKER = "POST_MERGE_LIVE_LANE"  # set to "1" only for a live-lane pytest session (TQ-600a-13-xxvii)
LIVE_FAILS, LIVE_RECLAIM, LIVE_CAPACITY = nid("publication_fails_until_fixed"), nid("reclaim_ok"), nid("capacity_ok")
LIVE_NAMES = ("publication_fails_until_fixed", "reclaim_ok", "capacity_ok")
CORR_A = "tests/test_lane.py::test_a_always_passes"
FAILS_WITNESS = ["publication_fails_until_fixed"]


def live_sources(variant: str) -> dict:
    """The live folder of a tree. ``fixed`` all pass; ``broken`` the fix-me test fails; ``skipping`` it skips; ``missing`` lacks one test.

    ``lane_marker`` passes only when its session carries the live lane's marker (TQ-600a-13-xxvii).
    """
    fails = {
        "fixed": "assert True",
        "broken": "assert False",
        "skipping": f"pytest.skip({OTHER_REASON!r})",
        "missing": "assert True",
        "lane_marker": f"assert os.environ.get({LANE_MARKER!r}) == '1'",
    }[variant]
    sources = {
        "publication_fails_until_fixed": live_test("publication_fails_until_fixed", fails, marks=("manual",)),
        "reclaim_ok": live_test("reclaim_ok"),
        "capacity_ok": live_test("capacity_ok"),
    }
    if variant == "missing":
        del sources["capacity_ok"]
    return sources


def _put_live(tree: Path, variant: str) -> None:
    for name, source in live_sources(variant).items():
        _write(tree / "tests" / "knowledge_live" / f"test_{name}.py", source)


def red_live_reports() -> dict:
    """Seeded lane reports of a run whose live lane is red: the fix-me live test failed on both executions."""
    return {
        "first": report({CORR_A: "passed"}),
        "live_first": live_report({LIVE_FAILS: "failed", LIVE_RECLAIM: "passed", LIVE_CAPACITY: "passed"}),
        "live_retry": live_report({LIVE_FAILS: "failed"}, runner="live-retry-machine"),
    }


def startup_live_reports() -> dict:
    """Seeded inputs of a run whose live lane did not complete: its job failed and left no report."""
    return {"first": report({CORR_A: "passed"}), "results": {"LIVE_RUN_RESULT": "failure"}}


def correctness_only_reports() -> dict:
    """A red run whose failing tests are all correctness-lane tests and whose live lane is green."""
    from ._proof_harness import X_ID, Y_ID  # noqa: PLC0415 -- the two correctness tests that fail until fixed

    return {
        "first": report({CORR_A: "passed", X_ID: "failed", Y_ID: "failed"}),
        "retry": report({X_ID: "failed", Y_ID: "failed"}),
        "live_first": live_report({LIVE_RECLAIM: "passed"}),
    }


@contextmanager
def driven_live(svc, address: str, *, kind: str = "red", reports: dict | None = None, head_live: str = "fixed", head: dict | None = None):
    """Execute ``Prepare fix proof`` then ``Post-merge fix proof`` of the real workflow over a live-database red run; yield a :class:`Proof`."""
    if not WORKFLOW.is_file():
        message = f"not implemented: {WORKFLOW.relative_to(REPO_ROOT)}"
        raise AssertionError(message)
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        newest = serve_history(svc, kind)
        state, event = base / "state", base / "event.json"
        state.mkdir()
        payload = {"action": "opened", "number": PR_NUMBER, "repository": {"full_name": REPO},
                   "pull_request": {"number": PR_NUMBER, "body": "Fixes #12", "head": {"sha": HEAD_SHA, "ref": "fix/branch"}, "base": {"ref": "main"}}}
        _write(event, json.dumps(payload))
        env = {"GITHUB_EVENT_PATH": str(event), "GITHUB_EVENT_NAME": "pull_request_target", "LANE_STATE_DIR": str(state),
               "LIVE_STATE_DIR": str(state), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": ""}
        main_tree, head_tree = stage_main(base / "main"), stage_head(base / "head", other_ok=True, **(head or {}))
        _put_live(main_tree, "fixed")
        _put_live(head_tree, head_live)
        run = ProofRun(WORKFLOW, main_tree, head_tree, base / "scratch", env, svc.url)
        point_at(run, address)
        seeded = dict(reports or red_live_reports())
        results = seeded.pop("results", None)
        produced = verdict_cli(
            base / "verdict",
            results=results,
            env={"GITHUB_RUN_ID": str(newest["id"]), "GITHUB_SHA": RED_HEAD, "GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": "push", "GITHUB_REPOSITORY": REPO, "GITHUB_SERVER_URL": SERVER},
            **seeded,
        )
        if produced.file is None:
            message = f"the real `verdict` entry point wrote no file: {produced.proc.stderr[-800:]}"
            raise AssertionError(message)
        run.artifacts.upload("post-merge-verdict", [("post-merge-verdict.json", produced.path)])
        doc = load_workflow(WORKFLOW)
        prepare_id = find_job(doc, PREPARE)[0]
        prepare = run.execute_job(PREPARE)
        prove = run.execute_job(PROVE, needs={prepare_id: prepare})
        yield Proof(run, prepare, prove, newest, state)


def live_ran(proof: Proof) -> list:
    """The witness lines of the live tests that really executed (sorted)."""
    return [name for name in proof.ran() if name in LIVE_NAMES]


def live_step_outcomes(proof: Proof) -> dict:
    """Every step of either proof job whose name mentions ``live``, with its outcome."""
    return {name: outcome for job in (proof.prepare, proof.prove) for name, outcome in job.steps.items() if "live" in name.lower()}
