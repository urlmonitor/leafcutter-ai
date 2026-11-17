"""KM-400e-5: merged changes synchronize through an observable standalone operation.

Every test RUNS the merge workflow's own ``sync`` step (its ``env`` expressions evaluated, its
``run`` lines executed through bash) in a fresh subprocess against a real Git repository whose AC
YAML is written by ``yaml.safe_dump``. Only the Neo4j driver is replaced, by the KM-400f-2
``ReclaimDouble``. Nothing here reads the workflow text for a string.
"""

import json
import os
import subprocess
import sys
import textwrap

import yaml

from tests.knowledge._km_400e_8_support import (
    HOSTED_URI,
    INSTANCE_DB,
    INSTANCE_USER,
    PASSWORD,
    REPO_ROOT,
    WORKFLOW,
    evaluate,
)
from tests.knowledge.test_km_400b_2_i import AC_PATH, _git, _load
from tests.knowledge.test_km_400b_2_ii import REPO_ID, TARGETS, _commit_repository

RUN_ID, RUN_ATTEMPT = "9876543210", "2"


def _assert_merge_job_correlation(result, sha, generation_id):
    """The job's result carries exactly the merge job's own identifiers, none of them a retrieval request id."""
    assert result.get("correlation") == {
        "run_id": RUN_ID,
        "run_attempt": RUN_ATTEMPT,
        "repository_id": REPO_ID,
        "source_sha": sha,
        "generation_id": generation_id,
    }, result.get("correlation")
    assert PASSWORD not in json.dumps(result)


_DRIVER = textwrap.dedent(
    """
    import json, os, sys
    from knowledge import cli_sync
    from tests.knowledge._km_400f_2_support import ReclaimDouble, main_scenario, REPO_ID

    store = ReclaimDouble(main_scenario())
    cli_sync.writer_backend = lambda root=None: store
    events = json.loads(os.environ["KM_EVENTS"])
    from knowledge.__main__ import main
    import io, contextlib

    out = []
    published_sha = None
    for event in events:
        # the backend reports the SHA it last published (the first event has none yet)
        store.source_sha = published_sha or event["source_sha"]
        store.scope_lines = event["scope"]
        argv = ["knowledge"] + [event["sha"] if a == "@SHA@" else a for a in json.loads(os.environ["KM_ARGV"])]
        sys.argv = argv
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            try:
                code = main()
            except SystemExit as exit_:
                code = exit_.code
        out.append({"sha": event["sha"], "code": code or 0, "stdout": buf.getvalue()})
        published_line = [r for r in buf.getvalue().splitlines() if r.startswith("{")]
        if published_line and json.loads(published_line[0]).get("published"):
            published_sha = json.loads(published_line[0]).get("source_sha")
    print(json.dumps({"runs": out, "survivors": sorted(store.generation_ids(REPO_ID)),
                      "active": store.snapshots[store.active_key]["generation_id"]}))
    """
)


def _workflow_env():
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    context = {"github.sha": "0" * 40, "github.repository": "o/r",
               "vars.LEAFCUTTER_NEO4J_DATABASE": INSTANCE_DB}
    return {k: evaluate(v, context) for k, v in workflow["jobs"]["sync"]["env"].items()}


def _sync_argv():
    """The workflow's own `knowledge sync` line, tokenised, with the revision left as a placeholder."""
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    lines = [line for step in workflow["jobs"]["sync"]["steps"] for line in step.get("run", "").splitlines()
             if line.startswith("python -m knowledge sync")]
    assert lines, "the workflow has no sync step"
    return lines[0]


def _history(root):
    """Two real commits; returns [(sha, loaded)] oldest first."""
    first = _commit_repository(root, list(TARGETS))
    loaded_first = _load(root, first)
    path = root / AC_PATH
    record = yaml.safe_load(path.read_text(encoding="utf-8"))
    record["title"] = "Second title"
    path.write_text(yaml.safe_dump(record), encoding="utf-8")
    _git(root, "add", ".")
    tree = _git(root, "write-tree")
    second = _git(root, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                  "commit-tree", tree, "-p", first, input="child merge\n")  # a real child of the first
    _git(root, "update-ref", "refs/heads/main", second)
    loaded_second = _load(root, second)
    return [(first, loaded_first), (second, loaded_second)]


def _run_events(root, history, order):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("LEAFCUTTER_", "NEO4J_"))}
    env.update(_workflow_env())
    env["LEAFCUTTER_NEO4J_URI"] = HOSTED_URI
    env["LEAFCUTTER_NEO4J_WRITER_USERNAME"] = INSTANCE_USER
    env["LEAFCUTTER_NEO4J_WRITER_PASSWORD"] = PASSWORD
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env["GITHUB_WORKSPACE"] = str(root)
    env["KNOWLEDGE_REPOSITORY_ID"] = REPO_ID
    env["GITHUB_RUN_ID"], env["GITHUB_RUN_ATTEMPT"] = RUN_ID, RUN_ATTEMPT  # what the runner sets for the merge job
    line = _sync_argv()
    tokens = [t.strip('"') for t in line.replace("python -m knowledge", "").split()]
    tokens = [{"$GITHUB_WORKSPACE": str(root), "$KNOWLEDGE_REPOSITORY_ID": REPO_ID,
               "$SOURCE_REVISION": "@SHA@"}.get(t, t) for t in tokens]
    tokens = [env.get(t[1:], t) if t.startswith("$") else t for t in tokens]
    # the shared KM-400f-2 double models retention, not the capacity measurement; drop that flag group
    kept, skip = [], False
    for token in tokens:
        if skip:
            skip = False
        elif token.startswith("--capacity-"):
            skip = True
        else:
            kept.append(token)
    tokens = kept
    env["KM_ARGV"] = json.dumps(tokens)
    env["KM_EVENTS"] = json.dumps([
        {"sha": history[i][0], "source_sha": history[i][1].source_sha,
         "scope": [d for d in history[i][1].diagnostics if str(d).startswith("projection_scope:")]}
        for i in order
    ])
    done = subprocess.run([sys.executable, "-c", _DRIVER], cwd=REPO_ROOT, env=env,
                          capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stderr
    return json.loads(next(r for r in done.stdout.splitlines() if r.startswith("{"))), done


def _result(run):
    return json.loads(next(r for r in run["stdout"].splitlines() if r.startswith("{")))


def test_km400_e_5_merge_events_publish_reclaim_in_the_same_run_and_report(tmp_path):
    # covers: KM-400e-5
    # angle: criterion
    """Repeated, out-of-order merge events publish once each, reclaim in the same run, report counts.

    The reclaimed and retained figures are the backend double's own report relayed through the job's result:
    this proves the job runs the reclamation within the publication and reports it, not that the backend
    computes it correctly (KM-400f-2 and KM-400f-4 prove that).
    """
    history = _history(tmp_path)
    payload, done = _run_events(tmp_path, history, order=[0, 1, 1, 0])
    runs = [_result(r) for r in payload["runs"][:3]]
    late = payload["runs"][3]
    new_first, new_second = (h[1].generation_id for h in history)

    first = runs[0]
    assert first["published"] is True
    # the workflow's declared bound (3 newest, 7200 s) reclaimed in the SAME successful publication
    rec = first["reclamation"]
    assert rec["reclaimed"] == 25 and rec["retained"] == 6
    assert type(rec["reclaimed"]) is int and rec["assessment_status"] == "assessed"
    _assert_merge_job_correlation(first, history[0][0], new_first)
    _assert_merge_job_correlation(runs[1], history[1][0], new_second)
    # graph publication and semantic readiness are separate fields of the job's result; the requested and
    # published SHA and the lag are reported by `status` (test_source_boundaries.py, same AC)
    assert runs[1]["published"] is True and runs[1]["semantic_ready"] is False
    # a repeated event yields the same generation and reclaims nothing more
    assert runs[2]["generation_id"] == new_second and runs[2]["reclamation"]["reclaimed"] == 0
    # an out-of-order (older) event must not move the published pointer back to the older commit
    # (the refusal is the ancestry guard: exit 2 naming the older or non-descendant revision)
    assert late["code"] == 2 and "older or non-descendant" in late["stdout"] + done.stderr
    assert payload["active"] == new_second
    assert new_first in payload["survivors"] and payload["survivors"].count(new_second) == 1
    # no credential reaches any output
    assert PASSWORD not in done.stdout + done.stderr


def test_km400_e_5_correlation_outside_a_runner_has_no_run_identifiers_and_no_credentials():
    # covers: KM-400e-5
    # angle: boundary
    """Without the runner's variables the run identifiers are null, and no other variable is read."""
    from knowledge.merge_correlation import merge_job_correlation

    sha, generation = "a" * 40, "g1"
    assert merge_job_correlation({}, REPO_ID, sha, generation) == {
        "run_id": None, "run_attempt": None, "repository_id": REPO_ID,
        "source_sha": sha, "generation_id": generation,
    }
    carried = merge_job_correlation(
        {"GITHUB_RUN_ID": "1", "LEAFCUTTER_NEO4J_WRITER_PASSWORD": PASSWORD}, REPO_ID, sha, generation
    )
    assert PASSWORD not in json.dumps(carried) and carried["run_id"] == "1"


def test_km400_e_5_sync_line_through_main_reports_counts_reclamation_and_correlation(tmp_path):
    # covers: KM-400e-5
    # angle: reachability
    """The workflow's own sync line, run through main() with real argv, reports counts in its stdout."""
    history = _history(tmp_path)
    payload, done = _run_events(tmp_path, history, order=[1])
    run = payload["runs"][0]
    assert run["code"] == 0
    result = _result(run)
    assert result["published"] is True and result["reclamation"]["reclaimed"] == 25
    _assert_merge_job_correlation(result, history[1][0], history[1][1].generation_id)
    assert result["reclamation"]["retained"] == len(payload["survivors"]) == 6
    assert set(payload["survivors"]) == {history[1][1].generation_id, "G32", "G31", "G28", "G5", "G4"}
    assert PASSWORD not in done.stdout + done.stderr
