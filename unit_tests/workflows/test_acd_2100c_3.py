"""
MODULE: test_acd_2100c_3
GOAL: Behavioral, RED-baseline tests for ACD-2100c-3 -- "A paused run picks up
    at the decision it was waiting on when the answer arrives."

BACKGROUND (ADR-024, docs/architecture/adrs/ADR-024-interactive-pause-resume.md;
    architect-review comment on this ticket, 2026-09-08): resolveGate()
    already checks args.resume_answer BEFORE ever calling liveGateFn, so the
    resume-answer-before-live-gate path (AC-1/AC-3) is real production
    behaviour today. What this ticket's own architect review flags as
    genuinely UNIMPLEMENTED is AC-4: nothing in resolveGate() / pauseAtGate()
    / applyAnswerByType() ever clears the durable pause record once a resumed
    run moves past the gate, and scripts/pause_store.py has only `write` and
    `read` subcommands -- no `clear`/`delete`. A record left behind makes the
    run look permanently paused to any later reader.

    Reading the pipeline body directly (templates/workflows-js/plan-feature.js,
    the default "technical" route -- reached whenever ac-triage's stub/real
    response carries no recognised `route`) also surfaces a SECOND, related
    gap this ticket's own Implementation Notes name explicitly: "The steps
    before the decision point must not re-execute on resume. Re-running them
    is observable as duplicated or rewritten drafted work and is the failure
    this record exists to prevent." The it-po authoring dispatch
    (`stage-itpo-author`) is the only step before the final-gate decision on
    that route, and it is NOT gated behind `committedStageKeys` (the
    crash-resume skip only fires for a stage already visible in `git log`,
    and the it-po stage is not committed until AFTER the final gate approves)
    -- so today it is unconditionally re-dispatched on every resume attempt,
    independent of whether the answer applies cleanly. test_
    resume_in_a_new_process_continues_from_the_decision_point below asserts
    this does NOT happen, per this ticket's own Implementation Notes, and is
    expected to be RED against the current implementation.

TEST STRATEGY: self-contained real-execution harness (per this directory's
    convention that E2 workflow scripts cannot be imported as modules --
    mirrors test_acd_2100a_4.py and test_acd_2100c_2.py): a REAL git
    repository ("the project") holding a REAL, verbatim copy of this
    repository's own scripts/pause_store.py under its untracked
    .leafcutter/scripts/ (matching production; ADR-001), and a REAL
    `git worktree add` of that repository as a sibling directory holding NO
    .leafcutter/ of its own. Driving templates/workflows-js/plan-feature.js's
    real, on-disk top-level body via a real Node child_process with `cwd` set
    to the worktree -- TWICE per test, as two independent Node subprocess
    invocations (the "new process" the AC names) -- with every dispatch whose
    prompt embeds a `pause_store.py` command line ACTUALLY EXECUTED (not
    mocked) against the real filesystem, and every other dispatch falling
    back to a generic stub. Because ACD-2100c-1 means liveGateFn is never
    invoked for any gate, and the default (unmocked) ac-triage response
    carries no `route` field, the default "technical" pipeline (single
    it-po stage, `final-gate`) is what every test below reaches and pauses
    at -- so every test can assume `gate_id == "final-gate"` without
    depending on which of the five gates a different route would reach.

TICKET: 15_TICKET-20260826-ACD-2100c-3.md
AC: ACD-2100c-3
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from unit_tests._plan_feature_harness_defaults import worktree_setup_default_responses
_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PLAN_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"
_REAL_PAUSE_STORE_PY = _WORKTREE_ROOT / "scripts" / "pause_store.py"

_TIMEOUT = 40  # seconds; includes real `git worktree add` and real subprocess I/O.

_DRAFT_RELATIVE_PATH = "docs/acceptance-criteria/test-component/DRAFT-8888.yaml"
_DRAFT_CONTENT = (
    "id: DRAFT-8888\n"
    "origin_agent: business-analyst\n"
    "readiness: draft\n"
    "criteria: |\n"
    "  Given a drafted scenario\n"
    "  When the pipeline pauses and is later resumed\n"
    "  Then this file must carry forward byte-identical\n"
)


# ---------------------------------------------------------------------------
# Fixture builders (self-contained copy of test_acd_2100c_2.py's conventions)
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
            "-b", "ac-authoring/pause-c3-test", str(worktree_path), "main",
        ]
    )

    return {"project_dir": project_dir, "worktree_path": worktree_path}


def _assert_worktree_has_no_installed_leafcutter(worktree_path: Path) -> None:
    """If this fixture assertion is wrong, every assertion below would pass
    vacuously against unfixed, cwd-relative code (mirrors
    test_acd_2100a_3.py / test_acd_2100a_4.py / test_acd_2100c_2.py's own
    warning).
    """
    assert not (worktree_path / ".leafcutter").exists(), (
        "Test construction error: the worktree fixture must hold NO installed "
        ".leafcutter/ support directory of its own. Found: "
        f"{sorted(p.name for p in worktree_path.iterdir())}"
    )


def _place_drafted_work(worktree_path: Path) -> Path:
    """Place a real, uncommitted 'drafted work' file on disk inside the
    worktree BEFORE the run -- the work already present when the run pauses.
    """
    draft_path = worktree_path / _DRAFT_RELATIVE_PATH
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text(_DRAFT_CONTENT, encoding="utf-8")
    return draft_path


def _permitted_args(**extra) -> dict:
    """Args carrying the ACD-2100b-5 pre-flight permission verdict.

    plan-feature.js consumes a pre-computed verdict via
    `args.workspace_setup_permission` and fails closed (terminal
    `status: "error"`, no gate ever reached) when it is absent. Every test
    below supplies a permitting verdict directly to reach the real decision
    point.
    """
    return {"workspace_setup_permission": {"permits": True}, **extra}


# ---------------------------------------------------------------------------
# The real-execution harness (self-contained copy of
# test_acd_2100c_2.py's `_run_plan_feature_real` -- see that file's module
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
    as a brand-new Node child_process each call -- this IS the "new process"
    the AC names. Every dispatch whose prompt embeds a `pause_store.py`
    command line is ACTUALLY EXECUTED via a real Node child_process with
    `cwd` set to the given directory. Returns the parsed
    {calls: [...], result: ..., error?: ...} payload.

    This is also this ticket's resolved reachability entry point (see the
    module docstring's TEST STRATEGY and this file's
    reachability-angle test): a real subprocess executing the actual,
    on-disk production script's top-level body -- the E2 workflow-dispatch
    contract (ADR-030) -- never an import of an inner function.

    `label_responses` is merged UNDER `worktree_setup_default_responses()`
    (BO-1500a-5-i) so a caller that never overrides 'worktree-setup' /
    'resolve-worktree-setup-script-path' still gets a real, confirming
    reply for both and reaches the pause-store dispatches this file tests,
    instead of halting fail-closed at Pre-Stage-0. A caller-supplied entry
    for either label still wins (dict merge order below).
    """
    source = _PLAN_FEATURE_JS.read_text(encoding="utf-8")
    body = _strip_exports(source)

    shim = (
        _SHIM_TEMPLATE
        .replace("__RUN_CWD_JSON__", json.dumps(str(cwd)))
        .replace("__LABEL_RESPONSES_JSON__", json.dumps({**worktree_setup_default_responses(), **label_responses}))
        .replace("__ARGS_JSON__", json.dumps(args))
        .replace("__SCRIPT_BODY__", body)
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".js", prefix="acd_2100c3_", delete=False, encoding="utf-8"
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


def _labels(payload: dict) -> list:
    return [c.get("label") for c in payload.get("calls", [])]


def _pause_record_path(project_dir: Path, run_id: str) -> Path:
    return project_dir / ".leafcutter" / "paused_runs" / f"{run_id}.json"


def _write_pause_record_via_real_process(
    pause_store_path: Path, project_dir: Path, run_id: str, record: dict
) -> None:
    """Seed a durable pause record via the REAL `pause_store.py write` CLI --
    never a hand-typed JSON file on disk (2h.2 Fixture Authenticity Rule).
    `--store-dir` is passed explicitly so the write lands at exactly the path
    `buildPauseStoreCommand()` derives in production (project root's
    `.leafcutter/paused_runs/`, resolved there via `git rev-parse
    --git-common-dir` from inside the linked worktree) -- the same location
    `_pause_record_path()` / `_read_via_fresh_process()` above already use.
    """
    store_dir = project_dir / ".leafcutter" / "paused_runs"
    proc = subprocess.run(
        [
            "python3", str(pause_store_path),
            "--store-dir", str(store_dir),
            "write", "--run-id", run_id, "--record", json.dumps(record),
        ],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0, (
        f"Test construction error: seeding the pause record must succeed. "
        f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )


def _read_via_fresh_process(pause_store_path: Path, project_dir: Path, run_id: str) -> dict:
    """Consumer: a fresh, independent `pause_store.py read` process -- never
    plan-feature.js again -- started from the project root. Real reader
    piped the real writer's own on-disk output (seam angle: producer and
    consumer are both the real, on-disk artifacts, never mocked).
    """
    proc = subprocess.run(
        ["python3", str(pause_store_path), "read", "--run-id", run_id],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0, (
        f"The consumer read must exit 0. stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    return json.loads(proc.stdout.strip())


def _pause_headless(worktree_path: Path, project_dir: Path, run_id: str) -> tuple:
    """Run the real production entry point headless (no resume_answer) and
    confirm it pauses with a verified, on-disk record. Returns
    (payload, gate_id).
    """
    payload = _run_plan_feature_real(
        worktree_path, label_responses={}, args=_permitted_args(run_id=run_id)
    )
    assert not payload.get("error"), (
        f"Unattended run must not crash. error={payload.get('error')} "
        f"stderr={payload.get('_stderr', '')[:2000]}"
    )
    writes = _write_shaped_calls(payload)
    assert writes, (
        "Expected a real pause_store.py write when the headless run reaches "
        f"a decision point. calls={payload.get('calls')}"
    )
    assert writes[0][1].get("ok") is True, f"The pause-store write must succeed. Got: {writes[0][1]}"

    record_path = _pause_record_path(project_dir, run_id)
    assert record_path.exists(), f"No pause record on disk at {record_path} after the process exited."
    on_disk = json.loads(record_path.read_text(encoding="utf-8"))
    assert on_disk.get("run_id") == run_id
    gate_id = on_disk.get("gate_id")
    assert gate_id, f"Record must name the decision point. Got: {on_disk}"

    result = payload.get("result")
    assert isinstance(result, dict) and result.get("status") == "paused_awaiting_input", (
        f"The run must report that it is waiting for an answer. Got result={result!r}"
    )
    return payload, gate_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_resume_in_a_new_process_continues_from_the_decision_point():
    # covers: ACD-2100c-3
    # angle: criterion
    """AC-1: a run paused at a decision point, with the process no longer
    running, is started again in a NEW process supplying the answer, and
    continues from that decision point rather than repeating the steps
    before it -- observed from the RESUMED run's own record of the steps it
    ran (this file's default technical route's only step before the
    final-gate decision is the `stage-itpo-author` dispatch).

    Implementation Notes (this ticket): "The steps before the decision point
    must not re-execute on resume. Re-running them is observable as
    duplicated or rewritten drafted work and is the failure this record
    exists to prevent." Reading plan-feature.js directly: the it-po
    authoring dispatch is not gated behind the crash-resume
    `committedStageKeys` check (that stage is not committed to git until
    AFTER the final gate approves), so today it is unconditionally
    re-dispatched on resume -- this assertion is expected to be RED.
    """
    with tempfile.TemporaryDirectory(prefix="acd2100c3_criterion_") as tmp:
        fixture = _make_worktree_fixture(Path(tmp))
        _assert_worktree_has_no_installed_leafcutter(fixture["worktree_path"])

        run_id = "acd2100c3-criterion-run"
        payload1, gate_id = _pause_headless(fixture["worktree_path"], fixture["project_dir"], run_id)
        labels1 = _labels(payload1)
        assert labels1.count("stage-itpo-author") == 1, (
            f"Sanity: the it-po author step must run exactly once before pausing. Labels: {labels1}"
        )

        # Run 2: a brand-new process (a fresh Node child_process invocation --
        # NOT the same process as run 1) supplying the answer for the decision
        # point the first run paused at.
        resume_answer = {
            "gate_id": gate_id,
            "type": "single_choice",
            "action": "approve",
            "channel": "person",
        }
        payload2 = _run_plan_feature_real(
            fixture["worktree_path"],
            label_responses={},
            args=_permitted_args(run_id=run_id, resume_answer=resume_answer),
        )
        assert not payload2.get("error"), f"Resumed run must not crash. error={payload2.get('error')}"
        labels2 = _labels(payload2)

        # AC-1: the resumed run engaged the durable record (continues from the
        # decision point) rather than starting over with no memory of the pause.
        assert "read-pause-record" in labels2, (
            f"Resumed run's own record of steps must show it consulted the durable "
            f"pause record. Labels: {labels2}"
        )

        # AC-1: the steps BEFORE the decision point must not re-execute -- observed
        # from the RESUMED run's own dispatch record, never a source scan.
        assert labels2.count("stage-itpo-author") == 0, (
            "The it-po authoring step -- the step before the final-gate decision on "
            "this route -- was re-dispatched by the resumed run. AC-1 requires the "
            "resumed run to continue from the decision point, not repeat the steps "
            f"before it. Resumed run's own labels: {labels2}"
        )

        # The resumed run must actually move past the decision point.
        result2 = payload2.get("result")
        assert isinstance(result2, dict) and result2.get("status") != "paused_awaiting_input", (
            f"The resumed run must continue past the decision point. Got: {result2!r}"
        )


def test_drafted_work_carried_forward_is_the_work_that_was_present_at_pause():
    # covers: ACD-2100c-3
    # angle: real_artifact
    """AC-2: the drafted artifacts are compared byte-for-byte between the
    moment of pause and the moment the resumed run moves past the gate; the
    resumed run must carry the same bytes forward unchanged.
    """
    with tempfile.TemporaryDirectory(prefix="acd2100c3_real_artifact_") as tmp:
        fixture = _make_worktree_fixture(Path(tmp))
        _assert_worktree_has_no_installed_leafcutter(fixture["worktree_path"])
        draft_path = _place_drafted_work(fixture["worktree_path"])

        run_id = "acd2100c3-real-artifact-run"
        _payload1, gate_id = _pause_headless(fixture["worktree_path"], fixture["project_dir"], run_id)

        # Snapshot at the moment of pause.
        bytes_at_pause = draft_path.read_bytes()

        resume_answer = {"gate_id": gate_id, "type": "single_choice", "action": "approve"}
        payload2 = _run_plan_feature_real(
            fixture["worktree_path"],
            label_responses={},
            args=_permitted_args(run_id=run_id, resume_answer=resume_answer),
        )
        assert not payload2.get("error"), f"Resumed run must not crash. error={payload2.get('error')}"

        assert draft_path.exists(), (
            f"The drafted work file must still exist on disk after the resumed run "
            f"moves past the gate: {draft_path}"
        )
        bytes_after_resume = draft_path.read_bytes()
        assert bytes_after_resume == bytes_at_pause, (
            "AC-2: the drafted work present when the run paused must be the work the "
            "resumed run carries forward unchanged. "
            f"before={bytes_at_pause!r} after={bytes_after_resume!r}"
        )


def test_supplied_answer_is_the_one_applied_to_that_decision():
    # covers: ACD-2100c-3
    # angle: criterion
    """AC-3: two resumes of equivalent paused runs, supplying different valid
    answers, take different observable branches -- proving the SUPPLIED
    answer is applied, not a default.
    """
    with tempfile.TemporaryDirectory(prefix="acd2100c3_answer_") as tmp:
        fixture = _make_worktree_fixture(Path(tmp))
        _assert_worktree_has_no_installed_leafcutter(fixture["worktree_path"])

        run_id_approve = "acd2100c3-answer-approve-run"
        run_id_cancel = "acd2100c3-answer-cancel-run"

        _p1a, gate_id_a = _pause_headless(fixture["worktree_path"], fixture["project_dir"], run_id_approve)
        _p1b, gate_id_b = _pause_headless(fixture["worktree_path"], fixture["project_dir"], run_id_cancel)
        assert gate_id_a == gate_id_b, (
            "Test construction error: both paused runs must be equivalent (same "
            f"gate). Got {gate_id_a!r} and {gate_id_b!r}."
        )

        approve_answer = {
            "gate_id": gate_id_a,
            "type": "single_choice",
            "action": "approve",
            "channel": "person",
        }
        cancel_answer = {
            "gate_id": gate_id_b,
            "type": "single_choice",
            "action": "cancel",
            "channel": "person",
        }

        payload_approve = _run_plan_feature_real(
            fixture["worktree_path"],
            label_responses={},
            args=_permitted_args(run_id=run_id_approve, resume_answer=approve_answer),
        )
        payload_cancel = _run_plan_feature_real(
            fixture["worktree_path"],
            label_responses={},
            args=_permitted_args(run_id=run_id_cancel, resume_answer=cancel_answer),
        )
        assert not payload_approve.get("error"), f"Approve resume must not crash: {payload_approve.get('error')}"
        assert not payload_cancel.get("error"), f"Cancel resume must not crash: {payload_cancel.get('error')}"

        result_approve = payload_approve.get("result") or {}
        result_cancel = payload_cancel.get("result") or {}

        assert result_approve.get("status") != result_cancel.get("status"), (
            "AC-3: supplying different valid answers to equivalent paused runs must "
            f"take different observable branches. Got the SAME status on both: "
            f"approve={result_approve!r} cancel={result_cancel!r}"
        )
        assert result_cancel.get("status") == "cancelled", (
            f"The cancel answer must be the one applied to the cancel run. Got: {result_cancel!r}"
        )
        assert result_approve.get("status") != "cancelled", (
            f"The approve answer must NOT be treated as a cancel. Got: {result_approve!r}"
        )

        labels_approve = _labels(payload_approve)
        labels_cancel = _labels(payload_cancel)
        assert "apply-approval" in labels_approve, (
            f"The approve branch must dispatch apply-approval. Labels: {labels_approve}"
        )
        assert "apply-approval" not in labels_cancel, (
            f"The cancel branch must NOT dispatch apply-approval. Labels: {labels_cancel}"
        )


def test_no_waiting_record_remains_after_the_resumed_run_passes_the_gate():
    # covers: ACD-2100c-3
    # angle: seam
    """AC-4: after the resumed run moves past the decision point, a fresh
    process that reads the run's waiting record must not find it -- the
    real writer's record consumed and cleared, read back by the real reader.

    Pipes the REAL producer (plan-feature.js's real pause_store.py write,
    executed via the harness's real child_process exec) into the REAL
    consumer (an independent `python3 pause_store.py read` process, started
    fresh, never plan-feature.js again). Per this ticket's own architect
    review, nothing in resolveGate()/pauseAtGate()/applyAnswerByType() clears
    the record and pause_store.py has no clear/delete subcommand -- expected
    to be RED.
    """
    with tempfile.TemporaryDirectory(prefix="acd2100c3_seam_") as tmp:
        fixture = _make_worktree_fixture(Path(tmp))
        _assert_worktree_has_no_installed_leafcutter(fixture["worktree_path"])

        run_id = "acd2100c3-seam-run"
        _payload1, gate_id = _pause_headless(fixture["worktree_path"], fixture["project_dir"], run_id)

        resume_answer = {
            "gate_id": gate_id,
            "type": "single_choice",
            "action": "approve",
            "channel": "person",
        }
        payload2 = _run_plan_feature_real(
            fixture["worktree_path"],
            label_responses={},
            args=_permitted_args(run_id=run_id, resume_answer=resume_answer),
        )
        assert not payload2.get("error"), f"Resumed run must not crash. error={payload2.get('error')}"
        labels2 = _labels(payload2)
        assert "apply-approval" in labels2, (
            f"Test construction error: the resumed run must actually move past the "
            f"gate before the 'record cleared' assertion is meaningful. Labels: {labels2}"
        )
        result2 = payload2.get("result") or {}
        assert result2.get("status") != "paused_awaiting_input", (
            f"Test construction error: run must not still be paused. Got: {result2!r}"
        )

        installed_pause_store = fixture["project_dir"] / ".leafcutter" / "scripts" / "pause_store.py"
        assert installed_pause_store.exists(), f"Test construction error: {installed_pause_store} must exist."

        read_response = _read_via_fresh_process(installed_pause_store, fixture["project_dir"], run_id)
        assert read_response.get("exists") is False, (
            "AC-4: once the resumed run has moved past the decision point, no record "
            "of it waiting must remain on disk -- a fresh reader process must not "
            f"find it. Got: {read_response}"
        )


def test_acd_2100c_3_reachable_from_entry_point():
    # covers: ACD-2100c-3
    # angle: reachability
    """REQUIRED reachability test. No test_spec named an entry point for this
    AC, so it is resolved here (Step 1 of the Reachability Entry-Point
    Resolution procedure): templates/workflows-js/plan-feature.js is an
    E2 workflow-dispatch script (ADR-030) with no CLI wrapper and no live
    `claude` engine invocation available in this test environment -- so the
    resolved entry point is a real Node subprocess executing the actual,
    on-disk production script's top-level body (the same convention already
    established by unit_tests/_workflow_engine_harness.py and
    test_acd_2100c_2.py for this exact class of unit). This is NOT an import
    of any inner function: two independent subprocess invocations of the
    real file are dispatched, and the new pause -> resume behaviour is
    asserted to actually occur AND to be consumed in control flow (the run's
    own terminal result), never merely computed and discarded.
    """
    with tempfile.TemporaryDirectory(prefix="acd2100c3_reachability_") as tmp:
        fixture = _make_worktree_fixture(Path(tmp))
        _assert_worktree_has_no_installed_leafcutter(fixture["worktree_path"])

        run_id = "acd2100c3-reachability-run"
        payload1, gate_id = _pause_headless(fixture["worktree_path"], fixture["project_dir"], run_id)
        assert payload1["result"]["status"] == "paused_awaiting_input", (
            "Reachability sanity: the first (headless) real subprocess invocation "
            f"of the production entry point must report the paused status. Got: {payload1.get('result')}"
        )

        resume_answer = {
            "gate_id": gate_id,
            "type": "single_choice",
            "action": "approve",
            "channel": "person",
        }
        payload2 = _run_plan_feature_real(
            fixture["worktree_path"],
            label_responses={},
            args=_permitted_args(run_id=run_id, resume_answer=resume_answer),
        )
        assert not payload2.get("error"), (
            f"Second real subprocess invocation of the production entry point must "
            f"not crash. error={payload2.get('error')}"
        )

        result2 = payload2.get("result")
        assert isinstance(result2, dict), (
            f"The second real invocation must produce a terminal payload dict, not "
            f"{type(result2)}."
        )
        assert result2.get("status") != "paused_awaiting_input", (
            "The behaviour driven through the REAL production entry point (a second "
            "independent Node subprocess dispatch of the actual on-disk "
            "plan-feature.js body, supplying the answer for the decision the first "
            "invocation paused at) must actually occur -- the run must be observed, "
            f"via its own terminal result, to have moved past the gate. Got: {result2!r}"
        )
        assert "apply-approval" in _labels(payload2), (
            "The paused-then-resumed outcome must be CONSUMED in control flow (the "
            "apply-approval dispatch that only fires once the gate resolves), not "
            f"merely computed and discarded. Labels: {_labels(payload2)}"
        )


def test_h2_duplicate_ac_ids_when_multistage_route_resumes_at_final_gate():
    # covers: ACD-2100c-3
    # angle: criterion
    """Regression for pr-reviewer finding H-2 (this ticket's 2026-09-08 14:01
    comment): `resolveGate()`'s resume branch attaches the ORIGINAL, pre-pause
    `all_acs` context snapshot to `decision._resumedContext.all_acs`
    (plan-feature.js ~3216-3223), and the final-gate handler pushes it
    straight into `allAcsWritten` (~3220-3222). But in THIS fresh process,
    `allAcsWritten` already contains that same already-committed stage's AC
    ids, independently re-derived from `git log` via the pre-existing
    crash-resume mechanism (`committedStageKeys`, ~2850-2937, pushed at
    ~2911) a few dozen lines earlier in the SAME `for (const step of
    pipeline)` loop. Every already-committed stage's AC id is therefore
    counted twice -- corrupting the `apply-approval` dispatch prompt, the
    terminal success message's "N AC(s) approved" count, and the terminal
    `acs_approved` array.

    None of the four pre-existing tests in this file can reach this: they all
    drive the default "technical" route, whose pipeline is the single-stage
    `[{stage: "itpo", gate: "final"}]` -- there is no earlier committed stage
    to duplicate against, so the bug cannot manifest under any of them. This
    test forces the "behavioral" route (ba -> itpo) via the `stage-0-triage`
    stub -- the smallest route with an earlier stage to duplicate against --
    and constructs the "paused at the final gate after an earlier stage
    already committed" state directly: a REAL pause record (written via the
    actual `pause_store.py` CLI, never hand-typed on disk) at gate_id
    "final-gate" whose `context.all_acs` is exactly what a genuine pre-pause
    run would have accumulated (the "ba" stage's AC plus the "itpo" stage's
    own AC). This is the fast, single-subprocess way to reach the same state
    a slower real pause -> resume(mid-gate) -> resume(final-gate) chain would
    reach; every dispatch label used to build it (`stage-0-triage`,
    `scan-committed-stages`, `resume-log`, `branch-check`,
    `commit-stage-output`) is controlled the same stub-injection way this
    file's other four tests already control every non-pause_store.py
    dispatch -- only the pause-record read/write/clear commands are real.

    Expected to be RED against current production code: `acs_approved` will
    contain the "ba" stage's AC id twice.
    """
    with tempfile.TemporaryDirectory(prefix="acd2100c3_h2_dup_") as tmp:
        fixture = _make_worktree_fixture(Path(tmp))
        _assert_worktree_has_no_installed_leafcutter(fixture["worktree_path"])
        pause_store_path = fixture["project_dir"] / ".leafcutter" / "scripts" / "pause_store.py"

        run_id = "acd2100c3-h2-dup-run"
        ba_ac_id = "H2DUP-BA-1"
        itpo_ac_id = "H2DUP-ITPO-1"

        # Seed the durable record a genuine pre-pause run would have left: the
        # "ba" stage already committed (its AC is already inside
        # context.all_acs), and this run paused at the FINAL gate while
        # authoring "itpo".
        _write_pause_record_via_real_process(
            pause_store_path, fixture["project_dir"], run_id,
            {
                "run_id": run_id,
                "gate_id": "final-gate",
                "question": {
                    "type": "priority_choice",
                    "gate_id": "final-gate",
                    "options": ["approve", "edit", "defer", "cancel"],
                    "prompt": "final gate",
                },
                "context": {
                    "stage": "final",
                    "acs": [itpo_ac_id],
                    "all_acs": [ba_ac_id, itpo_ac_id],
                },
                "status": "paused_awaiting_input",
            },
        )

        label_responses = {
            # Force the multi-stage "behavioral" route (ba -> itpo) -- the
            # smallest route with an earlier stage to duplicate against.
            "stage-0-triage": {
                "route": "behavioral",
                "existing_acs": [],
                "parent_l1_id": "H2DUP-L1",
                "rationale": "forced for H-2 regression test",
            },
            # The "ba" stage already committed in a PRIOR process. This fresh
            # process's own crash-resume reconstruction (real production
            # code, ~2850-2937) recovers its AC id from `git log` output
            # shaped exactly as the real `scanCommittedStages()` parser
            # expects -- only the underlying `git log` execution itself is
            # stubbed, matching this file's existing convention of stubbing
            # every non-pause_store.py dispatch.
            "scan-committed-stages": {
                "output": "abc1234 plan-feature(BA): test-component\n",
                "exit_code": 0,
            },
            "resume-log": {
                "output": (
                    "plan-feature(BA): test-component\n\n"
                    f"AC IDs: {ba_ac_id}\n"
                    f"run-id: {run_id}\n"
                    "mid-pipeline commit\n"
                ),
                "exit_code": 0,
            },
            # commitStageOutput()'s internal branch-check + commit dispatch --
            # forced to succeed so the run reaches its real "approve" success
            # path and returns a real `acs_approved` terminal field (rather
            # than aborting early with a commit error, which would make the
            # duplication this test targets unobservable).
            "branch-check": {"output": "ac-authoring/h2-dup-test", "exit_code": 0},
            "commit-stage-output": {"status": "ok", "message": "committed successfully"},
        }

        payload = _run_plan_feature_real(
            fixture["worktree_path"],
            label_responses=label_responses,
            args=_permitted_args(
                run_id=run_id,
                resume_answer={
                    "gate_id": "final-gate",
                    "type": "priority_choice",
                    "priority": "medium",
                    "channel": "person",
                },
            ),
        )
        assert not payload.get("error"), (
            f"Resumed multi-stage run must not crash. error={payload.get('error')} "
            f"stderr={payload.get('_stderr', '')[:2000]}"
        )

        result = payload.get("result") or {}
        assert result.get("status") == "ok", (
            f"Test construction error: the resumed run must reach the real "
            f"'approve' success path so `acs_approved` is populated. Got: {result!r}"
        )
        acs_approved = result.get("acs_approved")
        assert isinstance(acs_approved, list), f"Expected a list. Got: {acs_approved!r}"

        # H-2: the "ba" stage's AC id was reconstructed once from git log
        # (crash-resume) and must NOT ALSO be re-pushed from the persisted
        # `_resumedContext.all_acs` snapshot -- it must appear exactly once
        # in the run's own terminal record of what was approved.
        assert acs_approved.count(ba_ac_id) == 1, (
            f"AC {ba_ac_id!r} (the already-committed 'ba' stage) must appear "
            f"exactly once in the resumed run's own acs_approved record -- it "
            f"was double-counted (once via the real git-log crash-resume "
            f"reconstruction, once via the redundant `_resumedContext.all_acs` "
            f"re-push). Got acs_approved={acs_approved!r}"
        )
        assert len(acs_approved) == len(set(acs_approved)), (
            f"acs_approved must contain no duplicate AC ids at all. Got: {acs_approved!r}"
        )

        # The user-facing terminal count must match the real number of
        # distinct ACs approved, not an inflated double-counted total.
        expected_message_count = len(set(acs_approved))
        assert f"{expected_message_count} AC(s) approved" in (result.get("message") or ""), (
            f"Terminal message must report the true distinct AC count "
            f"({expected_message_count}), not an inflated double-counted one. "
            f"Got message={result.get('message')!r}"
        )

        # The apply-approval dispatch must name each AC exactly once too -- a
        # duplicate there means the same AC would be presented twice in the
        # prompt that updates readiness/priority on the real AC YAML files.
        approval_calls = [c for c in payload.get("calls", []) if c.get("label") == "apply-approval"]
        assert approval_calls, "Test construction error: apply-approval must have been dispatched."
        approval_prompt = approval_calls[0].get("prompt") or ""
        assert approval_prompt.count(ba_ac_id) == 1, (
            f"The apply-approval dispatch must name {ba_ac_id!r} exactly once, not "
            f"duplicate it. Prompt: {approval_prompt!r}"
        )


def test_h1_itpo_author_skipped_when_resume_answer_targets_an_earlier_gate():
    # covers: ACD-2100c-3-i
    # angle: seam
    """Regression for pr-reviewer finding H-1 (this ticket's 2026-09-08 comment
    on ACD-2100c-3-i): `isResuming` (plan-feature.js ~3031) is computed as
    `!!(args && args.resume_answer)` -- true for every pipeline step still
    remaining in the `for (const step of pipeline)` loop for the rest of THIS
    process invocation, not only for the step the run actually paused at.

    architect-review's justification ("this step's own gate is necessarily the
    one decision point the run could actually be paused at") holds ONLY for
    the FIRST uncommitted step a resumed invocation reaches. It is false for
    every step after it: on a multi-stage route, a successful mid-pipeline
    resume lets the SAME process continue past the approved gate into the
    NEXT step's own iteration of the pipeline loop, with `args.resume_answer`
    untouched (still naming the gate the run resumed AT, not the one it is now
    at). `_resumeAnswerForThisStep` and `_resumeAction` are correctly null for
    that next step (its own `stepGateId` does not match the stale
    `resume_answer.gate_id`), but `isResuming` never checks `gate_id` at all
    -- so it stays true, `skipAuthorOnResume` wrongly evaluates true, and that
    next step's own authoring dispatch is skipped, even though nothing ever
    authored it.

    This test forces the "behavioral" route (ba -> itpo) -- the smallest
    route with a step AFTER the one the run pauses at -- via the
    `stage-0-triage` stub (mirrors the neighbouring H-2 test's route-forcing
    convention in this file). Unlike the H-2 test, this one does NOT seed a
    synthetic pre-existing pause record: it drives an actual pause at the
    real FIRST gate ("gate-ba") via a genuine headless run, then resumes in a
    second, independent process supplying the answer that gate was waiting
    on. That resumed process's own pipeline loop then advances, in the SAME
    invocation, into the "itpo" step -- the step this defect skips.

    Per the ticket's dispatch mandate: assert on the run's own recorded
    dispatch list (the harness's captured `labels`), never on internal
    variables reached into directly -- this mirrors every other assertion in
    this file's `test_resume_in_a_new_process_continues_from_the_decision_point`
    and `test_h2_duplicate_ac_ids_when_multistage_route_resumes_at_final_gate`.

    Expected to be RED against current production code: `stage-itpo-author`
    is ABSENT from the resumed run's own labels.
    """
    with tempfile.TemporaryDirectory(prefix="acd2100c3i_h1_") as tmp:
        fixture = _make_worktree_fixture(Path(tmp))
        _assert_worktree_has_no_installed_leafcutter(fixture["worktree_path"])

        run_id = "acd2100c3i-h1-run"
        behavioral_triage_stub = {
            "route": "behavioral",
            "existing_acs": [],
            "parent_l1_id": "H1SKIP-L1",
            "rationale": "forced for H-1 regression test",
        }

        # Run 1 (headless): force the "behavioral" route (ba -> itpo) and let
        # the run pause at the FIRST, non-final gate ("gate-ba") -- never
        # supplying a resume_answer.
        payload1 = _run_plan_feature_real(
            fixture["worktree_path"],
            label_responses={"stage-0-triage": behavioral_triage_stub},
            args=_permitted_args(run_id=run_id),
        )
        assert not payload1.get("error"), (
            f"Headless run must not crash. error={payload1.get('error')} "
            f"stderr={payload1.get('_stderr', '')[:2000]}"
        )
        labels1 = _labels(payload1)
        assert labels1.count("stage-ba-author") == 1, (
            f"Sanity: the 'ba' stage's own author step must run exactly once "
            f"before the run pauses at its gate. Labels: {labels1}"
        )
        assert "stage-itpo-author" not in labels1, (
            "Sanity: 'itpo' is the step AFTER the gate this run pauses at in "
            f"run 1 -- it must not have run yet. Labels: {labels1}"
        )
        result1 = payload1.get("result")
        assert isinstance(result1, dict) and result1.get("status") == "paused_awaiting_input", (
            f"Sanity: the headless run must pause. Got: {result1!r}"
        )
        gate_id = result1.get("gate_id")
        assert gate_id == "gate-ba", (
            "Test construction error: the 'behavioral' route's first gate must "
            "be the non-final 'gate-ba' -- this test needs a real step AFTER "
            f"the resumed decision point to exist. Got: {gate_id!r}"
        )

        record_path = _pause_record_path(fixture["project_dir"], run_id)
        assert record_path.exists(), f"No pause record on disk at {record_path} after run 1."

        # Run 2: a brand-new, independent process resumes, naming the SAME
        # gate run 1 paused at ("gate-ba") and approving it. "behavioral" has
        # a SECOND stage ("itpo") after "ba", so approving this gate does NOT
        # end the pipeline -- the SAME process's `for` loop advances into the
        # "itpo" step's own iteration, with `args.resume_answer` unchanged
        # from what was supplied for "gate-ba".
        resume_answer = {
            "gate_id": gate_id,
            "type": "single_choice",
            "action": "approve",
            "channel": "person",
        }
        label_responses = {
            "stage-0-triage": behavioral_triage_stub,
            # commitStageOutput()'s internal branch-check + commit dispatch,
            # forced to succeed so the run actually commits the "ba" stage and
            # the for-loop genuinely advances into the "itpo" step -- without
            # this, an early commit error would return before the "itpo" step
            # is ever reached, making the assertion below vacuous.
            "branch-check": {"output": "ac-authoring/h1-skip-test", "exit_code": 0},
            "commit-stage-output": {"status": "ok", "message": "committed successfully"},
        }
        payload2 = _run_plan_feature_real(
            fixture["worktree_path"],
            label_responses=label_responses,
            args=_permitted_args(run_id=run_id, resume_answer=resume_answer),
        )
        assert not payload2.get("error"), (
            f"Resumed multi-stage run must not crash. error={payload2.get('error')} "
            f"stderr={payload2.get('_stderr', '')[:2000]}"
        )
        labels2 = _labels(payload2)

        # Sanity: the run really did move past the "ba" gate it resumed AT
        # (it must not be re-authored) -- otherwise the itpo-author assertion
        # below would be vacuous (the run would never reach the "itpo" step
        # at all).
        assert labels2.count("stage-ba-author") == 0, (
            "Test construction error / AC-1 regression: the 'ba' stage the run "
            f"resumed AT must not be re-authored. Labels: {labels2}"
        )

        # H-1: the resumed run's OWN dispatch record must show the 'itpo'
        # step's authoring agent actually ran -- it is the step AFTER the one
        # this run resumed at, was never authored by run 1 (asserted above),
        # and is never gated behind `committedStageKeys` (that stage is not
        # committed to git until AFTER the final gate approves). Skipping it
        # leaves the "itpo" stage treated as already-authored when nothing
        # authored it.
        assert labels2.count("stage-itpo-author") == 1, (
            "H-1 (pr-reviewer, 2026-09-08): the it-po authoring dispatch for "
            "the step AFTER the one this run resumed at was skipped. "
            "`isResuming` in plan-feature.js (~line 3031) is computed as "
            "`!!(args && args.resume_answer)` with no gate_id check, so it "
            "stays true for every step remaining in the pipeline once ANY "
            "resume_answer is present -- not only the step the run actually "
            "paused at. This makes the 'itpo' stage look already-authored "
            f"when nothing authored it. Resumed run's own labels: {labels2}"
        )
