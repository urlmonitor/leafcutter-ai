"""
MODULE: test_acd_2100c_3_i
GOAL: Behavioral, RED-baseline tests for ACD-2100c-3-i -- "An answer naming a
    different decision than the one being waited on is not applied."

BACKGROUND (architect-review comment on this ticket, 2026-09-09): reading the
    pipeline loop directly (templates/workflows-js/plan-feature.js), the bug
    this ticket must fix is that `skipAuthorOnResume` (around line ~3015) is
    derived from a NAIVE STRING COMPARISON of `args.resume_answer.gate_id` to
    the CURRENT step's `stepGateId`, BEFORE `resolveGate()` ever consults the
    persisted pause record. `resolveGate()` itself (line ~1517) correctly
    falls back to `pauseAtGate()` -- and so correctly re-reports the SAME gate
    it is actually waiting on -- whenever `args.resume_answer.gate_id` names
    a decision other than the one it is resolving. But BEFORE resolveGate()
    is ever reached, `skipAuthorOnResume` has already decided (from that same
    naive per-step comparison) whether to skip the authoring dispatch that
    precedes the gate. On a MISMATCHED resume, `isResumingThisStep` is false
    for the step actually paused (its own stepGateId does not equal the wrong
    gate_id the answer supplied), so `skipAuthorOnResume` is also false --
    and the authoring agent for the step the run is ACTUALLY waiting on gets
    RE-DISPATCHED anyway, even though the supplied answer was never going to
    be (and per resolveGate() below, never is) applied to that decision. That
    violates the Implementation Notes' "subject binding must be checked
    before any part of the answer is acted on" and is the direct mechanism
    behind AC-4 (drafted work unchanged) failing.

    A second structural fact matters for how these tests are built:
    `pause_store.py write` (scripts/pause_store.py `write_record()`) is
    IDEMPOTENT keyed on `gate_id` alone -- if a record already exists on disk
    for this run_id with the same `gate_id`, the write is skipped entirely
    (byte-for-byte untouched on disk), regardless of what `context` the
    caller passed. This means the persisted PAUSE RECORD FILE itself cannot
    be used to observe the redispatch bug (its bytes are protected by that
    idempotency check either way) -- so AC-2/AC-3 ("record still on disk",
    "reports which decision it is waiting on") are expected to already hold
    under today's code; only the REDISPATCH itself, and its real-world
    consequence (new drafted content), are the observable defect. Tests
    below account for this deliberately: every test still asserts the
    persisted-record-level ACs the ticket names (they are legitimate
    regression coverage the ticket requires), but the tests that MUST be RED
    against today's code (AC-1's "no step ... executes" and AC-4's
    "byte-identical... nothing is discarded") key off (a) the dispatch LABEL
    count for the authoring step, and (b) a REAL on-disk file the harness's
    author-dispatch stub itself writes with a fresh nonce each time it is
    actually invoked -- so a redispatch is observable as different bytes on
    disk, exactly mirroring what a real (non-deterministic) authoring LLM
    call would produce in production.

TEST STRATEGY: self-contained real-execution harness (per this directory's
    convention that E2 workflow scripts cannot be imported as modules --
    mirrors test_acd_2100a_4.py, test_acd_2100c_2.py, and test_acd_2100c_3.py):
    a REAL git repository ("the project") holding a REAL, verbatim copy of
    this repository's own scripts/pause_store.py under its untracked
    .leafcutter/scripts/ (matching production; ADR-001), and a REAL
    `git worktree add` of that repository as a sibling directory holding NO
    .leafcutter/ of its own. Driving templates/workflows-js/plan-feature.js's
    real, on-disk top-level body via a real Node child_process with `cwd` set
    to the worktree -- TWICE (sometimes three times) per test, as independent
    Node subprocess invocations (the "new process" a resume always is) --
    with every dispatch whose prompt embeds a `pause_store.py` command line
    ACTUALLY EXECUTED (not mocked) against the real filesystem, every
    "stage-itpo-author" dispatch made to actually write a real, nonce-stamped
    file to disk (simulating a real authoring LLM's non-deterministic
    output), and every other dispatch falling back to a generic stub.
    Because ACD-2100c-1 means liveGateFn is never invoked for any gate, and
    the default (unmocked) ac-triage response carries no `route` field, the
    default "technical" pipeline (single it-po stage, `final-gate`) is what
    every test below reaches and pauses at -- so every test can assume
    `gate_id == "final-gate"` is the ONE decision point the run is actually
    waiting on, and "gate-ba" (a real gate id on a different, unused route)
    is a genuine, plausible "different decision point" name for the
    mismatched resume_answer to carry.

TICKET: 16_TICKET-20260826-ACD-2100c-3-i.md
AC: ACD-2100c-3-i
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

# The AC-1 "drafted work" real artifact: the shim below makes every
# "stage-itpo-author" dispatch actually WRITE this file with a fresh nonce,
# simulating a real (non-deterministic) authoring agent's output.
_DRAFT_RELATIVE_PATH = "docs/acceptance-criteria/test-component/DRAFT-8888.yaml"

# A real gate id used elsewhere in this same script's pipeline (the "ba"
# stage's mid-gate) -- a genuine "different decision point" name, distinct
# from "final-gate" (the only gate the default technical route ever reaches).
_A_DIFFERENT_DECISION_GATE_ID = "gate-ba"


# ---------------------------------------------------------------------------
# Fixture builders (self-contained copy of test_acd_2100c_3.py's conventions)
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
    hand-authored stand-in would not exercise the real CLI's idempotency or
    error-handling contract (2h.2 Fixture Authenticity Rule).
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
            "-b", "ac-authoring/pause-c3i-test", str(worktree_path), "main",
        ]
    )

    return {"project_dir": project_dir, "worktree_path": worktree_path}


def _assert_worktree_has_no_installed_leafcutter(worktree_path: Path) -> None:
    """If this fixture assertion is wrong, every assertion below would pass
    vacuously against unfixed, cwd-relative code (mirrors
    test_acd_2100a_3.py / test_acd_2100a_4.py / test_acd_2100c_2.py /
    test_acd_2100c_3.py's own warning).
    """
    assert not (worktree_path / ".leafcutter").exists(), (
        "Test construction error: the worktree fixture must hold NO installed "
        ".leafcutter/ support directory of its own. Found: "
        f"{sorted(p.name for p in worktree_path.iterdir())}"
    )


def _permitted_args(**extra) -> dict:
    """Args carrying the ACD-2100b-5 pre-flight permission verdict.

    plan-feature.js consumes a pre-computed verdict via
    `args.workspace_setup_permission` and fails closed (terminal
    `status: "error"`, no gate ever reached) when it is absent. Every test
    below supplies a permitting verdict directly to reach the real decision
    point.
    """
    return {"workspace_setup_permission": {"permits": True}, **extra}


def _draft_path(worktree_path: Path) -> Path:
    return worktree_path / _DRAFT_RELATIVE_PATH


# ---------------------------------------------------------------------------
# The real-execution harness (self-contained copy of
# test_acd_2100c_3.py's `_run_plan_feature_real` -- see that file's module
# docstring for why this real-executes ONLY pause_store.py dispatches and
# stubs everything else). EXTENDED here so that a "stage-itpo-author"
# dispatch also performs a REAL disk write of a fresh nonce -- simulating a
# real, non-deterministic authoring agent's output -- so a redispatch is
# observable as changed bytes on disk (AC-1 / AC-4's real artifact).
# ---------------------------------------------------------------------------

_SHIM_TEMPLATE = r"""
'use strict';

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const __RUN_CWD__ = __RUN_CWD_JSON__;
const __labelResponses__ = __LABEL_RESPONSES_JSON__;
const __capturedCalls__ = [];

const _PAUSE_LINE_RE = /^.*pause_store\.py.*$/m;
const _DRAFT_RELATIVE_PATH = __DRAFT_RELATIVE_PATH_JSON__;

async function agent(promptOrOpts, opts) {
  var label =
    (opts && opts.label) ||
    (typeof promptOrOpts === 'object' && promptOrOpts && promptOrOpts.label) ||
    null;

  var record = { label: label, prompt: promptOrOpts, opts: opts || null, real_result: null };
  var response;

  if (label === 'stage-itpo-author') {
    // Simulate a REAL (non-deterministic) authoring agent: every time this
    // dispatch actually happens, it writes fresh content to the drafted-work
    // file on disk. A redispatch is therefore observable as changed bytes.
    var draftAbsPath = path.join(__RUN_CWD__, _DRAFT_RELATIVE_PATH);
    fs.mkdirSync(path.dirname(draftAbsPath), { recursive: true });
    var nonce = 'drafted-at:' + Date.now() + ':' + Math.random() + '\n';
    fs.writeFileSync(draftAbsPath, nonce, 'utf8');
    response = { status: 'ok', acs_written: ['DRAFT-8888'] };
  } else if (typeof promptOrOpts === 'string' && promptOrOpts.indexOf('pause_store.py') !== -1) {
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
    a resume always is. Every dispatch whose prompt embeds a `pause_store.py`
    command line is ACTUALLY EXECUTED via a real Node child_process with
    `cwd` set to the given directory; every "stage-itpo-author" dispatch
    ACTUALLY WRITES a fresh-nonce file to disk. Returns the parsed
    {calls: [...], result: ..., error?: ...} payload.

    This is also this ticket's resolved reachability entry point (see the
    module docstring's TEST STRATEGY and this file's reachability-angle
    test): a real subprocess executing the actual, on-disk production
    script's top-level body -- the E2 workflow-dispatch contract (ADR-030)
    -- never an import of an inner function. Resolved identically to sibling
    ticket ACD-2100c-3's own test_acd_2100c_3.py (same script, no CLI
    wrapper, no live `claude` engine available in this test environment).

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
        .replace("__DRAFT_RELATIVE_PATH_JSON__", json.dumps(_DRAFT_RELATIVE_PATH))
        .replace("__SCRIPT_BODY__", body)
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".js", prefix="acd_2100c3i_", delete=False, encoding="utf-8"
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


def _write_shaped_calls(payload: dict) -> list:
    """Real-executed calls whose stdout parsed to write_record()'s own output
    shape (presence of the "ok" key)."""
    out = []
    for c in payload.get("calls", []):
        rr = c.get("real_result")
        if not rr:
            continue
        try:
            parsed = json.loads((rr.get("output") or "").strip())
        except (ValueError, TypeError):
            parsed = None
        if isinstance(parsed, dict) and "ok" in parsed:
            out.append((c, parsed))
    return out


def _labels(payload: dict) -> list:
    return [c.get("label") for c in payload.get("calls", [])]


def _pause_record_path(project_dir: Path, run_id: str) -> Path:
    return project_dir / ".leafcutter" / "paused_runs" / f"{run_id}.json"


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

    draft_path = _draft_path(worktree_path)
    assert draft_path.exists(), (
        f"Test construction error: the harness's 'stage-itpo-author' dispatch must have "
        f"written the drafted-work file before pausing. Missing: {draft_path}"
    )
    return payload, gate_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_answer_naming_a_different_decision_is_not_applied():
    # covers: ACD-2100c-3-i
    # angle: criterion
    """AC-1: a run paused at one decision point (`final-gate`, the default
    technical route's only gate) is resumed supplying a well-formed answer
    naming a DIFFERENT, real decision point (`gate-ba`). Neither branch of
    the decision it is actually waiting on is taken -- and, per the
    Implementation Notes ("the subject binding must be checked before any
    part of the answer is acted on"), no step is executed as a side effect
    of the mismatch either.

    Expected RED against current code: `skipAuthorOnResume` (~line 3015) is
    computed from a naive per-step comparison BEFORE resolveGate() ever
    checks the mismatch, so the authoring dispatch for the step actually
    being waited on is unconditionally re-run.
    """
    with tempfile.TemporaryDirectory(prefix="acd2100c3i_criterion_") as tmp:
        fixture = _make_worktree_fixture(Path(tmp))
        _assert_worktree_has_no_installed_leafcutter(fixture["worktree_path"])

        run_id = "acd2100c3i-criterion-run"
        payload1, gate_id = _pause_headless(fixture["worktree_path"], fixture["project_dir"], run_id)
        assert gate_id == "final-gate", f"Test construction error: expected final-gate. Got {gate_id!r}"

        mismatched_answer = {
            "gate_id": _A_DIFFERENT_DECISION_GATE_ID,
            "type": "single_choice",
            "action": "approve",
        }
        payload2 = _run_plan_feature_real(
            fixture["worktree_path"],
            label_responses={},
            args=_permitted_args(run_id=run_id, resume_answer=mismatched_answer),
        )
        assert not payload2.get("error"), f"Mismatched resume must not crash. error={payload2.get('error')}"
        labels2 = _labels(payload2)

        # AC-1: the decision the run is actually waiting on is untouched --
        # neither branch (approve nor any other) was taken.
        result2 = payload2.get("result")
        assert isinstance(result2, dict) and result2.get("status") == "paused_awaiting_input", (
            f"AC-1: the answer must not be applied to the decision being waited on -- the "
            f"run must remain paused. Got result={result2!r}"
        )
        assert "apply-approval" not in labels2, (
            f"AC-1: no branch of the waiting decision must be taken on a mismatch. Labels: {labels2}"
        )
        assert "clear-pause-record" not in labels2, (
            f"AC-1: nothing about the waiting decision may be acted on -- the pause record "
            f"must not even be cleared. Labels: {labels2}"
        )

        # AC-1 ("no step after it executes"), read together with the
        # Implementation Notes ("checked before any part of the answer is
        # acted on"): the authoring step for the decision actually being
        # waited on must not be re-dispatched just because SOME answer
        # arrived -- only a MATCHING answer may do that.
        assert labels2.count("stage-itpo-author") == 0, (
            "AC-1: a mismatched resume must not cause the step whose decision is being "
            "waited on to be re-executed. The current implementation computes "
            "skipAuthorOnResume from a naive per-step gate_id comparison BEFORE "
            "resolveGate() ever detects the mismatch, so the authoring dispatch runs "
            f"anyway. Labels from the mismatched-resume process: {labels2}"
        )


def test_run_remains_paused_with_its_record_intact_after_a_mismatch():
    # covers: ACD-2100c-3-i
    # angle: failure
    """AC-2: after the mismatched resume, the durable record is still present
    on disk and still names the original decision point ("final-gate"), read
    back by a FRESH, independent `pause_store.py read` process (never
    plan-feature.js again) -- and, because nothing was actually acted on, a
    SUBSEQUENT correct resume (a third real subprocess, supplying the RIGHT
    answer for "final-gate") must still succeed and recover the same
    originally-drafted AC ids. This is the "recovery from a mistyped resume
    must not be a full re-run" property the Implementation Notes require.

    Expected RED against current code for the same reason as AC-1's test:
    the mismatched resume still re-dispatches the authoring step, which is
    itself unwanted work having happened, even though the record on disk
    (protected by pause_store.py's own gate_id-keyed idempotency) survives.
    """
    with tempfile.TemporaryDirectory(prefix="acd2100c3i_failure_") as tmp:
        fixture = _make_worktree_fixture(Path(tmp))
        _assert_worktree_has_no_installed_leafcutter(fixture["worktree_path"])
        pause_store_path = fixture["project_dir"] / ".leafcutter" / "scripts" / "pause_store.py"

        run_id = "acd2100c3i-failure-run"
        _payload1, gate_id = _pause_headless(fixture["worktree_path"], fixture["project_dir"], run_id)
        assert gate_id == "final-gate"

        mismatched_answer = {
            "gate_id": _A_DIFFERENT_DECISION_GATE_ID,
            "type": "single_choice",
            "action": "approve",
        }
        payload2 = _run_plan_feature_real(
            fixture["worktree_path"],
            label_responses={},
            args=_permitted_args(run_id=run_id, resume_answer=mismatched_answer),
        )
        assert not payload2.get("error"), f"Mismatched resume must not crash. error={payload2.get('error')}"
        result2 = payload2.get("result") or {}
        assert result2.get("status") == "paused_awaiting_input", (
            f"Test construction error: run must still be paused after the mismatch. Got: {result2!r}"
        )

        # AC-2: a FRESH, independent reader process still finds the record,
        # still naming the ORIGINAL decision point.
        read_response = _read_via_fresh_process(pause_store_path, fixture["project_dir"], run_id)
        assert read_response.get("exists") is True, (
            f"AC-2: the run's record must still be on disk after a mismatched resume. "
            f"Got: {read_response}"
        )
        record = read_response.get("record") or {}
        assert record.get("gate_id") == "final-gate", (
            f"AC-2: the surviving record must still name the ORIGINAL decision point, not "
            f"the one the mismatched answer supplied. Got record={record!r}"
        )

        # The mismatch must not have caused unwanted work: the authoring step
        # for the decision being waited on must not have been re-dispatched.
        assert _labels(payload2).count("stage-itpo-author") == 0, (
            "AC-2 read together with the Implementation Notes ('the subject binding must "
            "be checked before any part of the answer is acted on'): an intact record is "
            "not enough on its own if the mismatch still caused the authoring step to "
            f"re-run. Labels: {_labels(payload2)}"
        )

        # Recovery: a THIRD, independent real subprocess supplying the RIGHT
        # answer for the decision actually being waited on must still work --
        # the mistyped resume must not have turned recovery into a full re-run.
        correct_answer = {
            "gate_id": "final-gate",
            "type": "priority_choice",
            "priority": "medium",
            "channel": "person",
        }
        payload3 = _run_plan_feature_real(
            fixture["worktree_path"],
            label_responses={},
            args=_permitted_args(run_id=run_id, resume_answer=correct_answer),
        )
        assert not payload3.get("error"), f"Recovery resume must not crash. error={payload3.get('error')}"
        result3 = payload3.get("result") or {}
        assert result3.get("status") != "paused_awaiting_input", (
            f"AC-2: the correct resume, after an earlier mismatch, must still move the run "
            f"past the decision point. Got: {result3!r}"
        )
        assert "apply-approval" in _labels(payload3), (
            f"AC-2: the correct resume must actually apply the approval. Labels: {_labels(payload3)}"
        )


def test_mismatch_report_names_the_decision_actually_being_waited_on():
    # covers: ACD-2100c-3-i
    # angle: criterion
    """AC-3: the mismatched resume's own terminal payload reports the
    decision point the run is ACTUALLY waiting on ("final-gate"), not the
    one the supplied answer named ("gate-ba") -- so an operator can correct
    their answer without inspecting the store by hand.
    """
    with tempfile.TemporaryDirectory(prefix="acd2100c3i_report_") as tmp:
        fixture = _make_worktree_fixture(Path(tmp))
        _assert_worktree_has_no_installed_leafcutter(fixture["worktree_path"])

        run_id = "acd2100c3i-report-run"
        _payload1, gate_id = _pause_headless(fixture["worktree_path"], fixture["project_dir"], run_id)
        assert gate_id == "final-gate"

        mismatched_answer = {
            "gate_id": _A_DIFFERENT_DECISION_GATE_ID,
            "type": "single_choice",
            "action": "approve",
        }
        payload2 = _run_plan_feature_real(
            fixture["worktree_path"],
            label_responses={},
            args=_permitted_args(run_id=run_id, resume_answer=mismatched_answer),
        )
        assert not payload2.get("error"), f"Mismatched resume must not crash. error={payload2.get('error')}"
        result2 = payload2.get("result") or {}

        assert result2.get("status") == "paused_awaiting_input"
        assert result2.get("gate_id") == "final-gate", (
            f"AC-3: the report must name the decision ACTUALLY being waited on. Got: {result2!r}"
        )
        assert result2.get("gate_id") != _A_DIFFERENT_DECISION_GATE_ID, (
            f"AC-3: the report must NOT echo the wrongly-supplied gate id. Got: {result2!r}"
        )
        question = result2.get("question") or {}
        assert question.get("gate_id") == "final-gate", (
            f"AC-3: the question descriptor in the report must also name the real decision "
            f"point. Got question={question!r}"
        )

        # Tie the "honest report" requirement to "nothing acted on yet" --
        # a report that names the right gate is not meaningful proof of AC-3
        # if the mismatch already silently re-ran the step before it.
        assert _labels(payload2).count("stage-itpo-author") == 0, (
            "AC-3: reporting the correct decision point is undermined if the mismatch "
            f"already caused the authoring step to re-run. Labels: {_labels(payload2)}"
        )


def test_mismatched_resume_discards_nothing():
    # covers: ACD-2100c-3-i
    # angle: real_artifact
    """AC-4: the drafted artifact on disk (written by the REAL
    "stage-itpo-author" dispatch -- this test's harness makes that dispatch
    actually write a fresh-nonce file, simulating a real, non-deterministic
    authoring LLM's output) is byte-identical before and after a mismatched
    resume whose supplied answer names a decision ("gate-ba") whose own
    choices include "cancel" -- a discarding choice for THAT (wrongly-named)
    decision. Reading the real, on-disk bytes both times (never a hand-typed
    literal) is exactly the real-artifact round trip: if the mismatch causes
    the authoring step to re-run, the file's bytes actually change (the
    nonce differs), directly observing the "drafted work is unchanged"
    requirement rather than merely asserting a dispatch count.

    Expected RED against current code: `skipAuthorOnResume` is computed from
    the naive per-step comparison before the mismatch is ever detected, so
    the authoring dispatch re-runs and overwrites the file with a new nonce.
    """
    with tempfile.TemporaryDirectory(prefix="acd2100c3i_real_artifact_") as tmp:
        fixture = _make_worktree_fixture(Path(tmp))
        _assert_worktree_has_no_installed_leafcutter(fixture["worktree_path"])

        run_id = "acd2100c3i-real-artifact-run"
        _payload1, gate_id = _pause_headless(fixture["worktree_path"], fixture["project_dir"], run_id)
        assert gate_id == "final-gate"

        draft_path = _draft_path(fixture["worktree_path"])
        bytes_at_pause = draft_path.read_bytes()
        assert bytes_at_pause, "Test construction error: the drafted-work file must be non-empty."

        # The supplied answer names a DIFFERENT decision ("gate-ba") whose
        # own real choices include "cancel" -- a discarding choice for that
        # (wrongly-named) decision. It must have zero effect here.
        mismatched_discard_answer = {
            "gate_id": _A_DIFFERENT_DECISION_GATE_ID,
            "type": "single_choice",
            "action": "cancel",
        }
        payload2 = _run_plan_feature_real(
            fixture["worktree_path"],
            label_responses={},
            args=_permitted_args(run_id=run_id, resume_answer=mismatched_discard_answer),
        )
        assert not payload2.get("error"), f"Mismatched resume must not crash. error={payload2.get('error')}"
        result2 = payload2.get("result") or {}
        assert result2.get("status") == "paused_awaiting_input", (
            f"Test construction error: run must remain paused. Got: {result2!r}"
        )
        # Sanity: the mismatched answer's own "cancel" choice must not have
        # been silently treated as applying to the real (final-gate) decision.
        assert result2.get("status") != "cancelled", (
            f"AC-4/AC-1: a discarding choice aimed at the WRONG decision must never be "
            f"treated as cancelling the real one. Got: {result2!r}"
        )

        assert draft_path.exists(), (
            f"The drafted work file must still exist on disk after the mismatched resume: {draft_path}"
        )
        bytes_after_mismatch = draft_path.read_bytes()
        assert bytes_after_mismatch == bytes_at_pause, (
            "AC-4: the drafted artifact present when the run paused must be byte-identical "
            "after a mismatched resume -- including one whose supplied answer names a "
            "decision whose choices include discarding. "
            f"before={bytes_at_pause!r} after={bytes_after_mismatch!r}"
        )


def test_acd_2100c_3_i_reachable_from_entry_point():
    # covers: ACD-2100c-3-i
    # angle: reachability
    """REQUIRED reachability test. No test_spec named an entry point for this
    AC, so it is resolved here per the Reachability Entry-Point Resolution
    procedure, Step 0: the request already carries no named entry point, and
    Step 1 resolves identically to sibling ticket ACD-2100c-3's own
    test_acd_2100c_3.py::test_acd_2100c_3_reachable_from_entry_point --
    templates/workflows-js/plan-feature.js is an E2 workflow-dispatch script
    (ADR-030) with no CLI wrapper and no live `claude` engine invocation
    available in this test environment, so the resolved entry point is a
    real Node subprocess executing the actual, on-disk production script's
    top-level body. This is NOT an import of any inner function: two
    independent subprocess invocations of the real file are dispatched, and
    the mismatched-resume behaviour is asserted to actually occur (the run
    stays paused, reporting the true decision) AND to be consumed in control
    flow (no downstream branch dispatch fires), never merely computed and
    discarded.

    completion_manifest.reachability_entry_point_answer (recorded on this
    ticket's sign-off): result: resolved, entry_point: "node <tmpfile
    embedding the real plan-feature.js top-level body> (real Node
    subprocess; no CLI wrapper exists for this E2 workflow script)".
    """
    with tempfile.TemporaryDirectory(prefix="acd2100c3i_reachability_") as tmp:
        fixture = _make_worktree_fixture(Path(tmp))
        _assert_worktree_has_no_installed_leafcutter(fixture["worktree_path"])

        run_id = "acd2100c3i-reachability-run"
        payload1, gate_id = _pause_headless(fixture["worktree_path"], fixture["project_dir"], run_id)
        assert payload1["result"]["status"] == "paused_awaiting_input", (
            "Reachability sanity: the first (headless) real subprocess invocation of the "
            f"production entry point must report the paused status. Got: {payload1.get('result')}"
        )
        assert gate_id == "final-gate"

        mismatched_answer = {
            "gate_id": _A_DIFFERENT_DECISION_GATE_ID,
            "type": "single_choice",
            "action": "approve",
        }
        payload2 = _run_plan_feature_real(
            fixture["worktree_path"],
            label_responses={},
            args=_permitted_args(run_id=run_id, resume_answer=mismatched_answer),
        )
        assert not payload2.get("error"), (
            f"Second real subprocess invocation of the production entry point must not "
            f"crash. error={payload2.get('error')}"
        )

        result2 = payload2.get("result")
        assert isinstance(result2, dict), (
            f"The second real invocation must produce a terminal payload dict, not {type(result2)}."
        )
        # Behaviour actually occurred: the run is observed, via its own terminal
        # result, to still be paused at the decision it was really waiting on.
        assert result2.get("status") == "paused_awaiting_input", (
            "The behaviour driven through the REAL production entry point (a second "
            "independent Node subprocess dispatch of the actual on-disk plan-feature.js "
            "body, supplying an answer that names a DIFFERENT decision point) must "
            "actually occur -- the run must be observed, via its own terminal result, to "
            f"remain paused at the decision it is really waiting on. Got: {result2!r}"
        )
        assert result2.get("gate_id") == "final-gate", (
            f"The terminal result must name the real decision point. Got: {result2!r}"
        )
        # Consumed in control flow: no downstream branch dispatch fired as a
        # side effect of the mismatch (merely computing and discarding a
        # decision would be invisible here; an actual dispatch would not be).
        labels2 = _labels(payload2)
        assert "apply-approval" not in labels2, (
            f"The mismatched answer must not have been consumed by any downstream branch. "
            f"Labels: {labels2}"
        )
        assert labels2.count("stage-itpo-author") == 0, (
            "The mismatched resume, driven through the real production entry point, must "
            f"not re-execute the step before the decision it is waiting on. Labels: {labels2}"
        )
