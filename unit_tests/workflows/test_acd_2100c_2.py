"""
MODULE: test_acd_2100c_2
GOAL: Behavioral, RED-baseline tests for ACD-2100c-2 -- "A run that cannot
    reach a person waits with a durable record instead of proceeding or
    discarding."

BACKGROUND (ADR-024, docs/architecture/adrs/ADR-024-interactive-pause-resume.md;
    KI-ACD-005, docs/known-issues/ac-driven-dev.md): resolveGate() /
    pauseAtGate() (templates/workflows-js/plan-feature.js) already implement
    the headless-pause substrate -- an unattended invocation with no
    args.resume_answer never calls liveGateFn (ACD-2100c-1) and instead
    persists a pending-question record via a real, repository-anchored
    pause_store.py dispatch (ACD-2100a-4), verifies the write by reading it
    back, and returns { status: "paused_awaiting_input", ... } which every
    call site `return`s immediately (see e.g. the final-gate call site,
    ~line 3120: "Non-proceed outcomes: exit immediately."). This ticket's
    job is to prove that substrate holds under the SPECIFIC conditions
    ACD-2100c-2 names: cwd set to a git worktree, drafted work already
    sitting on disk, and the pause left both durable and non-destructive.

TEST STRATEGY: mirrors unit_tests/workflows/test_acd_2100a_4.py's own
    real-execution harness (a self-contained copy, per this directory's
    convention that E2 workflow scripts cannot be imported as modules): a
    REAL git repository ("the project") holding a REAL, verbatim copy of
    this repository's own scripts/pause_store.py under its untracked
    .leafcutter/scripts/ (matching production; ADR-001), and a REAL
    `git worktree add` of that repository as a sibling directory holding NO
    .leafcutter/ of its own -- verified absent before every run that depends
    on it. Driving templates/workflows-js/plan-feature.js's real, on-disk
    top-level body via a real Node child_process with `cwd` set to the
    worktree; every dispatch whose prompt embeds a `pause_store.py` command
    line is ACTUALLY EXECUTED (not mocked) against the real filesystem, and
    every other dispatch falls back to a generic stub -- the same one
    test_bo_2300_pause_resume.py's already-established tests rely on to
    drive a headless run all the way to *some* interactive gate. Because
    ACD-2100c-1 means liveGateFn is never invoked for any gate, the FIRST
    resolveGate() call the default flow reaches always pauses -- so these
    tests do not need to know in advance which of the five gates that is.

    PRE-FLIGHT PERMISSION VERDICT (ACD-2100b-5, landed 2026-09-07, AFTER
    ACD-2100a-4 and ACD-2100c-1 were signed off): the workspace-setup
    permission check is no longer resolved by an in-workflow agent()
    dispatch labelled "resolve-workspace-setup-permission" -- that label no
    longer exists. The workflow now consumes a pre-computed verdict passed
    in as `args.workspace_setup_permission` (`{permits: true, ...}`) and
    fails closed with a terminal `status: "error"` when it is absent. Every
    real-execution call below supplies `{"permits": true}` directly via
    `args` rather than mocking a now-removed label (verified empirically
    against this branch, HEAD: the older, label-based mock now halts every
    run at the very first step with "No workspace-setup permission
    pre-flight verdict was supplied in args").

    "Drafted work from the steps before the decision point" is modelled as a
    real file placed on disk inside the worktree BEFORE the run -- the
    uncommitted authoring output earlier stages would have produced. "No
    step after the decision point runs" is proven two ways: (1) the run's
    OWN captured dispatch record (never a source scan) must end at the
    pause-persist-verify call, with nothing dispatched afterward; (2) no
    file appears anywhere under the project except the pause record itself.

TICKET: 14_TICKET-20260826-ACD-2100c-2.md
AC: ACD-2100c-2
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PLAN_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"
_REAL_PAUSE_STORE_PY = _WORKTREE_ROOT / "scripts" / "pause_store.py"

_TIMEOUT = 40  # seconds; includes real `git worktree add` and real subprocess I/O.

_DRAFT_RELATIVE_PATH = "docs/acceptance-criteria/test-component/DRAFT-9999.yaml"
_DRAFT_CONTENT = (
    "id: DRAFT-9999\n"
    "origin_agent: business-analyst\n"
    "readiness: draft\n"
    "criteria: |\n"
    "  Given a drafted scenario\n"
    "  When the pipeline pauses\n"
    "  Then this file must not move\n"
)


# ---------------------------------------------------------------------------
# Fixture builders (self-contained copy of test_acd_2100a_4.py's conventions)
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, check=True, capture_output=True, text=True
    )


def _init_git_project(path: Path) -> None:
    path.mkdir(parents=True)
    _run(["git", "init", "-b", "main", str(path)])
    _run(["git", "-C", str(path), "config", "user.email", "test@example.com"])
    _run(["git", "-C", str(path), "config", "user.name", "Test"])
    (path / "README.md").write_text("seed\n", encoding="utf-8")
    _run(["git", "-C", str(path), "add", "README.md"])
    _run(["git", "-C", str(path), "commit", "-m", "seed"])


def _install_real_pause_store(project_dir: Path) -> Path:
    """Copy the REAL, verbatim scripts/pause_store.py into the fixture
    project's untracked `.leafcutter/scripts/` -- matching production, where
    `.leafcutter/` is build output that is never committed (ADR-001). A
    hand-authored stand-in would not exercise the real CLI's argument
    parsing, idempotency, or error-handling contract (2h.2 Fixture
    Authenticity Rule).
    """
    dest = project_dir / ".leafcutter" / "scripts" / "pause_store.py"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(_REAL_PAUSE_STORE_PY.read_bytes())
    return dest


def _make_worktree_fixture(tmp_path: Path) -> dict:
    """Build the Given: a REAL git repository ("the project") holding a REAL
    `.leafcutter/scripts/pause_store.py`, and a REAL git worktree of that
    repository, created as a sibling directory, holding NO `.leafcutter/` of
    its own.
    """
    project_dir = tmp_path / "project"
    _init_git_project(project_dir)
    _install_real_pause_store(project_dir)

    worktree_path = tmp_path / "ac-authoring-worktree"
    _run(
        [
            "git", "-C", str(project_dir), "worktree", "add",
            "-b", "ac-authoring/pause-c2-test", str(worktree_path), "main",
        ]
    )

    return {"project_dir": project_dir, "worktree_path": worktree_path}


def _assert_worktree_has_no_installed_leafcutter(worktree_path: Path) -> None:
    """If this fixture assertion is wrong, every assertion below would pass
    vacuously against unfixed, cwd-relative code (mirrors
    test_acd_2100a_3.py / test_acd_2100a_4.py's own warning).
    """
    assert not (worktree_path / ".leafcutter").exists(), (
        "Test construction error: the worktree fixture must hold NO installed "
        ".leafcutter/ support directory of its own. Found: "
        f"{sorted(p.name for p in worktree_path.iterdir())}"
    )


def _place_drafted_work(worktree_path: Path) -> Path:
    """Place a real, uncommitted 'drafted work' file on disk inside the
    worktree BEFORE the run -- the Given clause's 'drafted work from the
    steps before the decision point is present on disk'.
    """
    draft_path = worktree_path / _DRAFT_RELATIVE_PATH
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text(_DRAFT_CONTENT, encoding="utf-8")
    return draft_path


def _permitted_args(**extra) -> dict:
    """Args carrying the ACD-2100b-5 pre-flight permission verdict.

    Post-ACD-2100b-5 (landed 2026-09-07), plan-feature.js no longer resolves
    workspace-setup permission via an agent() dispatch at all -- it consumes
    a pre-computed verdict passed through `args.workspace_setup_permission`
    and fails closed (terminal `status: "error"`, no gate ever reached) when
    it is absent. This is not what this ticket's fix touches, so every test
    below supplies a permitting verdict directly to reach the first real
    decision point.
    """
    return {"workspace_setup_permission": {"permits": True}, **extra}


def _snapshot_files(root: Path) -> set:
    """Return the set of file paths (relative to `root`) present under it,
    excluding `.git`. Used to detect any file created as a side effect of
    the run -- 'no authoring output from a later step exists on disk'.
    """
    out = set()
    for p in root.rglob("*"):
        if p.is_file() and ".git" not in p.relative_to(root).parts:
            out.add(str(p.relative_to(root)))
    return out


# ---------------------------------------------------------------------------
# The real-execution harness (self-contained copy of
# test_acd_2100a_4.py's `_run_plan_feature_real` -- see that file's module
# docstring for why this real-executes ONLY pause_store.py dispatches and
# stubs everything else).
# ---------------------------------------------------------------------------

_SHIM_TEMPLATE = r"""
'use strict';

const { execSync } = require('child_process');

const __RUN_CWD__ = __RUN_CWD_JSON__;
const __labelResponses__ = __LABEL_RESPONSES_JSON__;
const __capturedCalls__ = [];

const _PAUSE_LINE_RE = /^.*pause_store\.py.*$/m;

async function agent(promptOrOpts, opts) {
  var label =
    (opts && opts.label) ||
    (typeof promptOrOpts === 'object' && promptOrOpts && promptOrOpts.label) ||
    null;

  var record = { label: label, prompt: promptOrOpts, opts: opts || null, real_result: null };
  var response;

  if (typeof promptOrOpts === 'string' && promptOrOpts.indexOf('pause_store.py') !== -1) {
    var m = promptOrOpts.match(_PAUSE_LINE_RE);
    var real = { command: null, cwd: __RUN_CWD__, output: '', exit_code: null, stderr: '' };
    if (m) {
      var cmd = m[0].trim().replace(/\{\{config\.output_root\}\}/g, '.leafcutter');
      real.command = cmd;
      try {
        var out = execSync(cmd, { cwd: __RUN_CWD__, encoding: 'utf8', timeout: 15000 });
        real.output = out;
        real.exit_code = 0;
      } catch (e) {
        real.output = (e.stdout || '').toString();
        real.stderr = (e.stderr || '').toString();
        real.exit_code = (e.status === null || e.status === undefined) ? 1 : e.status;
      }
    } else {
      real.stderr = 'harness: could not locate a pause_store.py command line in the prompt';
      real.exit_code = 1;
    }
    record.real_result = real;
    var parsed = null;
    try { parsed = JSON.parse((real.output || '').trim()); } catch (_pe) { parsed = null; }
    response = parsed;
  } else if (label !== null && Object.prototype.hasOwnProperty.call(__labelResponses__, label)) {
    response = __labelResponses__[label];
  } else {
    response = {
      status: 'ok', message: 'stub', passed: true, git_type: 'file',
      branch: 'feature-stub', exit_code: 0, output: '',
    };
  }

  __capturedCalls__.push(record);
  return response;
}

async function parallel(thunksArg) {
  var results = [];
  if (Array.isArray(thunksArg)) {
    for (var i = 0; i < thunksArg.length; i++) {
      var fn = thunksArg[i];
      if (typeof fn === 'function') {
        try { results.push(await fn()); } catch (_e) { results.push(null); }
      }
    }
  }
  return results;
}

async function pipeline(stepsArg) { return parallel(stepsArg); }

async function phase(name, fn) {
  if (typeof fn === 'function') { return fn(); }
}

function log(_msg) {}

function workflow() {
  throw new Error('workflow() cannot be called from within a running workflow.');
}

const budget = Object.freeze({ tokens_used: 0, tokens_limit: null });

const args = Object.assign({
  target_file: 'stub/target.py',
  root_cause: 'stub root cause for harness execution',
  location_hint: 'line 1',
  symptom: 'stub symptom',
  userInput: 'Add a small test feature for pause resolution',
  ac: 'BO-STUB-1',
}, __ARGS_JSON__);

(async function __body__() {
// BEGIN TARGET SCRIPT
__SCRIPT_BODY__
// END TARGET SCRIPT
})().then(function (result) {
  process.stdout.write(JSON.stringify({
    calls: __capturedCalls__,
    result: (typeof result === 'undefined' ? null : result),
  }));
}).catch(function (err) {
  process.stderr.write('harness: top-level error: ' + String(err) + '\n');
  process.stdout.write(JSON.stringify({
    calls: __capturedCalls__,
    result: null,
    error: String(err),
  }));
});
"""


def _strip_exports(source: str) -> str:
    """Minimal ESM `export` stripper (self-contained copy)."""
    lines = source.splitlines()
    out: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("export default "):
            out.append("/* export default stripped */")
        elif stripped.startswith("export {"):
            out.append("/* export block stripped */")
        elif stripped.startswith("export "):
            indent = len(line) - len(stripped)
            out.append(" " * indent + stripped[len("export "):])
        else:
            out.append(line)
    return "\n".join(out)


def _run_plan_feature_real(cwd: Path, label_responses: dict, args: dict) -> dict:
    """Drive the REAL templates/workflows-js/plan-feature.js top-level body,
    with every dispatch whose prompt embeds a `pause_store.py` command line
    ACTUALLY EXECUTED via a real Node child_process with `cwd` set to the
    given directory. Returns the parsed
    {calls: [...], result: ..., error?: ...} payload.
    """
    source = _PLAN_FEATURE_JS.read_text(encoding="utf-8")
    body = _strip_exports(source)

    shim = (
        _SHIM_TEMPLATE
        .replace("__RUN_CWD_JSON__", json.dumps(str(cwd)))
        .replace("__LABEL_RESPONSES_JSON__", json.dumps(label_responses))
        .replace("__ARGS_JSON__", json.dumps(args))
        .replace("__SCRIPT_BODY__", body)
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".js", prefix="acd_2100c2_", delete=False, encoding="utf-8"
    ) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write(shim)

    try:
        proc = subprocess.run(
            ["node", str(tmp_path)], capture_output=True, text=True, timeout=_TIMEOUT
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    stdout = proc.stdout or ""
    if not stdout.strip():
        raise AssertionError(
            "harness produced no stdout at all.\n"
            f"returncode={proc.returncode}\nstderr={proc.stderr[:2000]!r}"
        )
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"harness produced non-JSON stdout: {exc}\n"
            f"stdout={stdout[:2000]!r}\nstderr={proc.stderr[:2000]!r}"
        ) from exc

    payload["_stderr"] = proc.stderr
    payload["_returncode"] = proc.returncode
    return payload


def _real_calls(payload: dict) -> list:
    """All captured calls whose prompt was real-executed (a pause_store.py dispatch)."""
    return [c for c in payload.get("calls", []) if c.get("real_result") is not None]


def _parsed_real_result(call: dict):
    rr = call.get("real_result") or {}
    try:
        return json.loads((rr.get("output") or "").strip())
    except (ValueError, TypeError):
        return None


def _write_shaped_calls(payload: dict) -> list:
    """Real-executed calls whose stdout parsed to write_record()'s own output
    shape (presence of the "ok" key)."""
    out = []
    for c in _real_calls(payload):
        parsed = _parsed_real_result(c)
        if isinstance(parsed, dict) and "ok" in parsed:
            out.append((c, parsed))
    return out


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_unattended_run_from_a_worktree_pauses_with_a_record_on_disk():
    # covers: ACD-2100c-2
    # angle: criterion
    """AC: reaching a decision point with no channel to a person, from a real
    git worktree, with drafted work already on disk, leaves a durable record
    naming the run and the decision point, and the run reports it is waiting.
    """
    with tempfile.TemporaryDirectory(prefix="acd2100c2_criterion_") as tmp:
        fixture = _make_worktree_fixture(Path(tmp))
        _assert_worktree_has_no_installed_leafcutter(fixture["worktree_path"])
        _place_drafted_work(fixture["worktree_path"])

        run_id = "acd2100c2-criterion-run"
        payload = _run_plan_feature_real(
            fixture["worktree_path"],
            label_responses={},
            args=_permitted_args(run_id=run_id),
        )
        assert not payload.get("error"), (
            f"Unattended run must not crash. error={payload.get('error')} "
            f"stderr={payload.get('_stderr', '')[:2000]}"
        )

        writes = _write_shaped_calls(payload)
        assert writes, (
            "Expected at least one write-shaped (pause_store.py write) real "
            f"execution when the headless run reaches a decision point. "
            f"calls={payload.get('calls')}"
        )
        _, write_response = writes[0]
        assert write_response.get("ok") is True, (
            f"The pause-store write must succeed. Got: {write_response}. "
            f"real_result={writes[0][0]['real_result']}"
        )

        record_path = fixture["project_dir"] / ".leafcutter" / "paused_runs" / f"{run_id}.json"
        assert record_path.exists(), (
            "AC: no record naming the run and the decision point is present "
            f"on disk at {record_path} after the process exited."
        )
        on_disk = json.loads(record_path.read_text(encoding="utf-8"))
        assert on_disk.get("run_id") == run_id, f"Record must name the run. Got: {on_disk}"
        assert on_disk.get("gate_id"), f"Record must name the decision point. Got: {on_disk}"

        result = payload.get("result")
        assert isinstance(result, dict) and result.get("status") == "paused_awaiting_input", (
            f"The run must report that it is waiting for an answer. Got result={result!r}"
        )


def test_no_step_after_the_decision_point_runs_when_no_person_can_answer():
    # covers: ACD-2100c-2
    # angle: reachability
    """AC: the run's own record of the steps it executed ends at the decision
    point -- no later step appears, and no authoring output from a later step
    exists on disk. Driven through the REAL plan-feature.js entry point; the
    pause outcome is CONSUMED in control flow (checked against the terminal
    result), not merely computed and discarded.
    """
    with tempfile.TemporaryDirectory(prefix="acd2100c2_reachability_") as tmp:
        fixture = _make_worktree_fixture(Path(tmp))
        _assert_worktree_has_no_installed_leafcutter(fixture["worktree_path"])
        _place_drafted_work(fixture["worktree_path"])

        project_files_before = _snapshot_files(fixture["project_dir"])
        worktree_files_before = _snapshot_files(fixture["worktree_path"])

        run_id = "acd2100c2-reachability-run"
        payload = _run_plan_feature_real(
            fixture["worktree_path"],
            label_responses={},
            args=_permitted_args(run_id=run_id),
        )
        assert not payload.get("error"), f"Run must not crash. error={payload.get('error')}"

        writes = _write_shaped_calls(payload)
        assert writes, f"Expected a real pause-store write. calls={payload.get('calls')}"
        assert writes[0][1].get("ok") is True, f"Expected the write to succeed. Got: {writes[0][1]}"

        # The run's OWN dispatch record -- never a source scan -- must end at
        # the pause-persist-verify call. Every gate call site in
        # plan-feature.js `return`s immediately on a non-proceed resolveGate()
        # outcome (e.g. the final-gate site's "Non-proceed outcomes: exit
        # immediately."); if any later step ran, a call after
        # pause-persist-verify would appear here.
        labels = [c.get("label") for c in payload.get("calls", [])]
        assert "pause-persist-verify" in labels, (
            f"Expected a pause-persist-verify dispatch as the last step of the "
            f"pause. Labels: {labels}"
        )
        verify_index = labels.index("pause-persist-verify")
        assert verify_index == len(labels) - 1, (
            "A dispatch was made AFTER pause-persist-verify -- a later step ran "
            f"even though no person could answer. Labels: {labels}"
        )

        result = payload.get("result")
        assert isinstance(result, dict) and result.get("status") == "paused_awaiting_input", (
            f"The pause outcome must be consumed in control flow (the run's own "
            f"terminal result), not merely computed and discarded. Got: {result!r}"
        )

        # No authoring output from a later step exists on disk: the only new
        # file anywhere under the project is the pause record itself.
        project_files_after = _snapshot_files(fixture["project_dir"])
        new_project_files = project_files_after - project_files_before
        unexpected = {f for f in new_project_files if not f.startswith(".leafcutter/paused_runs/")}
        assert not unexpected, (
            f"Unexpected new file(s) on disk after the pause -- authoring output "
            f"from a later step must not exist: {unexpected}"
        )

        worktree_files_after = _snapshot_files(fixture["worktree_path"])
        assert worktree_files_after == worktree_files_before, (
            "No file inside the worktree changed as a side effect of the pause "
            f"itself. before={worktree_files_before} after={worktree_files_after}"
        )


def test_drafted_work_is_byte_identical_after_the_pause():
    # covers: ACD-2100c-2
    # angle: real_artifact
    """AC: the drafted work is still present on disk unchanged. Compares the
    REAL fixture file's bytes, read from disk before the run, against the
    same file's bytes read from disk after the process exits.
    """
    with tempfile.TemporaryDirectory(prefix="acd2100c2_real_artifact_") as tmp:
        fixture = _make_worktree_fixture(Path(tmp))
        _assert_worktree_has_no_installed_leafcutter(fixture["worktree_path"])
        draft_path = _place_drafted_work(fixture["worktree_path"])
        bytes_before = draft_path.read_bytes()

        run_id = "acd2100c2-real-artifact-run"
        payload = _run_plan_feature_real(
            fixture["worktree_path"],
            label_responses={},
            args=_permitted_args(run_id=run_id),
        )
        assert not payload.get("error"), f"Run must not crash. error={payload.get('error')}"

        writes = _write_shaped_calls(payload)
        assert writes and writes[0][1].get("ok") is True, (
            f"Expected the pause-store write to succeed before the byte-identical "
            f"check is meaningful. calls={payload.get('calls')}"
        )

        assert draft_path.exists(), (
            f"The drafted work file must still exist on disk after the pause: {draft_path}"
        )
        bytes_after = draft_path.read_bytes()
        assert bytes_after == bytes_before, (
            "The pause must not normalise, rewrite or relocate anything the "
            "earlier steps produced -- the drafted work must be byte-identical. "
            f"before={bytes_before!r} after={bytes_after!r}"
        )


def test_pause_written_from_the_worktree_is_readable_from_the_project_root():
    # covers: ACD-2100c-2
    # angle: seam
    """AC: a second fresh process started with the project root as its
    working directory lists the run as waiting. Pipes the REAL producer's
    output (a pause record written by the plan-feature.js process started
    inside the worktree) into the REAL consumer (a second, independent
    `pause_store.py read` process started from a DIFFERENT working directory
    -- the project root).
    """
    with tempfile.TemporaryDirectory(prefix="acd2100c2_seam_") as tmp:
        fixture = _make_worktree_fixture(Path(tmp))
        _assert_worktree_has_no_installed_leafcutter(fixture["worktree_path"])
        _place_drafted_work(fixture["worktree_path"])

        run_id = "acd2100c2-seam-run"
        payload = _run_plan_feature_real(
            fixture["worktree_path"],
            label_responses={},
            args=_permitted_args(run_id=run_id),
        )
        assert not payload.get("error"), f"Producer run must not crash. error={payload.get('error')}"
        writes = _write_shaped_calls(payload)
        assert writes and writes[0][1].get("ok") is True, (
            f"Producer (worktree) must perform a real, successful pause_store.py "
            f"write before the seam can be tested. calls={payload.get('calls')}"
        )

        installed_pause_store = fixture["project_dir"] / ".leafcutter" / "scripts" / "pause_store.py"
        assert installed_pause_store.exists(), (
            f"Test construction error: {installed_pause_store} must exist."
        )

        # Consumer: a SECOND, independent, fresh process -- not plan-feature.js
        # again -- started with the PROJECT ROOT (not the worktree) as its
        # working directory, reading the record through the real CLI's own
        # git-derived default store-dir resolution.
        read_proc = subprocess.run(
            ["python3", str(installed_pause_store), "read", "--run-id", run_id],
            cwd=str(fixture["project_dir"]),
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert read_proc.returncode == 0, (
            f"The consumer read must exit 0. stdout={read_proc.stdout!r} "
            f"stderr={read_proc.stderr!r}"
        )
        read_response = json.loads(read_proc.stdout.strip())
        assert read_response.get("exists") is True, (
            "AC: a second fresh process started from the project root must find "
            f"the record the worktree-started process wrote. Got: {read_response}"
        )
        found_record = read_response.get("record") or {}
        assert found_record.get("run_id") == run_id, (
            f"The record found by the second process must be the SAME record "
            f"the first process wrote (run_id mismatch). Got: {found_record}"
        )
        assert found_record.get("status") == "paused_awaiting_input", (
            "AC: a reader started somewhere else must list the run as waiting. "
            f"Got: {found_record}"
        )
