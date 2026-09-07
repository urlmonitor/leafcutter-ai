"""
MODULE: test_acd_2100a_4
GOAL: Behavioral tests for ACD-2100a-4 -- "A pause record written from inside
    a worktree is found again by the run that resumes."

INCIDENT BEING REGRESSION-TESTED: templates/workflows-js/plan-feature.js's
    three pause-store dispatch sites (resolveGate's read at ~line 1552,
    pauseAtGate's write at ~line 1625, and pauseAtGate's read-back verify at
    ~line 1642) all build their command with the raw, build-time
    `{{config.output_root}}/scripts/pause_store.py` placeholder -- resolved
    by the DISPATCHING AGENT's own process working directory, never anchored
    to the repository being operated on (the same class of defect ACD-2100a-1
    / ACD-2100a-3 already fixed for the registry read and the worktree-setup
    script). A run started with cwd set to a linked git worktree of the
    project holds no `.leafcutter/` of its own (ADR-001: untracked build
    output), so from inside a worktree:
      - the write silently resolves nowhere reachable (script-not-found) or,
        if it happens to resolve, writes UNDER the worktree rather than the
        project's own store;
      - a resuming run started from the project root can never find a record
        that was never written where it looks.

    pause_store.py's OWN default project-root detection
    (`git rev-parse --show-toplevel`) does not fix this on its own even if the
    script path itself were resolved correctly: run from inside a worktree,
    `--show-toplevel` reports the WORKTREE's own directory, not the shared
    repository root every worktree of the project shares (see
    `_buildRepoRootResolutionSnippet`'s own rationale, ~line 1693 of
    plan-feature.js, for `--git-common-dir` vs `--show-toplevel`). So the fix
    must anchor the read, the write, and the read-back verify all through the
    SAME repository-anchored resolution already established for the other two
    sites -- and files_touched on this ticket names ONLY plan-feature.js, so
    the fix is expected to pass an explicit, repository-anchored
    `--store-dir` to every pause_store.py invocation rather than relying on
    that script's own cwd-derived default.

WHY A BARE, EMPTY WORKTREE CANNOT PROVE THIS (mirrors test_acd_2100a_3.py's
    own rationale): if the fixture worktree happened to carry its own
    `.leafcutter/` of its own, or if the record's on-disk location were never
    independently checked, every assertion below would be unfalsifiable. This
    file builds a REAL git repository ("the project") holding a REAL, VERBATIM
    copy of this repository's own `scripts/pause_store.py` under its
    untracked `.leafcutter/scripts/` (matching production: build output, never
    committed), and a REAL `git worktree add` of that repository as a sibling
    directory holding NO `.leafcutter/` of its own -- verified absent before
    every run that depends on it.

HOW THE REAL SIDE EFFECT IS EXERCISED (Real-Artifact Behavioral Test Mandate):
    This file's harness (`_run_plan_feature_real`) mirrors
    test_acd_2100a_3.py's own harness convention (a self-contained copy, not a
    shared import) but ACTUALLY EXECUTES every dispatch whose prompt embeds a
    `pause_store.py` command line via a real Node child_process with a real,
    controlled `cwd` -- proving the read, the write, and the read-back verify
    all reach the real, on-disk pause-store CLI and the real filesystem, not a
    canned mock. Every other dispatch (stage triage, worktree-setup, gate
    prompts) uses the SAME generic stub `_workflow_engine_harness.py` and
    test_bo_2300_pause_resume.py already rely on to drive a headless run all
    the way to an interactive gate -- this file does not re-implement that
    control-flow proof, only the pause-store I/O seam ACD-2100a-4 is about.

TDD note: templates/workflows-js/plan-feature.js does not yet resolve any of
    the three pause-store sites through a repository-anchored path. Every test
    below is expected to be RED until python-coder extends the shared
    resolution mechanism (buildRepoAnchoredResolutionCommand /
    _buildRepoRootResolutionSnippet, per ACD-2100a-1's it_requirements) to the
    pause-store read, write, and verify dispatches, and passes an explicit
    repository-anchored `--store-dir` so a writer in a worktree and a reader
    at the project root address the same on-disk location.

TICKET: 05_TICKET-20260826-ACD-2100a-4.md
AC: ACD-2100a-4
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PLAN_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"
_REAL_PAUSE_STORE_PY = _WORKTREE_ROOT / "scripts" / "pause_store.py"
_REAL_REGISTRY_PATH = _WORKTREE_ROOT / "config" / "agent_registry.json"

_TIMEOUT = 40  # seconds; includes real `git worktree add` and real subprocess I/O.


# ---------------------------------------------------------------------------
# Fixture builders
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
    hand-authored stand-in would not exercise the real CLI's argument parsing,
    idempotency, or error-handling contract (2h.2 Fixture Authenticity Rule).
    """
    dest = project_dir / ".leafcutter" / "scripts" / "pause_store.py"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(_REAL_PAUSE_STORE_PY.read_bytes())
    return dest


def _make_plain_project_fixture(tmp_path: Path) -> Path:
    """A single real git repository with a real, installed pause_store.py --
    no worktree indirection. Used only where the AC does not require the
    worktree distinction (the failure-biconditional and reachability tests
    still use the worktree fixture below, since a plain project would resolve
    correctly even under the unfixed, cwd-relative code and so could not be
    RED before the fix).
    """
    project_dir = tmp_path / "project"
    _init_git_project(project_dir)
    _install_real_pause_store(project_dir)
    return project_dir


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
            "-b", "ac-authoring/pause-test", str(worktree_path), "main",
        ]
    )

    return {"project_dir": project_dir, "worktree_path": worktree_path}


def _assert_worktree_has_no_installed_leafcutter(worktree_path: Path) -> None:
    """The second Given is the whole test (mirrors test_acd_2100a_3.py's own
    warning): if this fixture assertion is wrong, every assertion below would
    pass vacuously against unfixed, cwd-relative code.
    """
    assert not (worktree_path / ".leafcutter").exists(), (
        "Test construction error: the worktree fixture must hold NO installed "
        ".leafcutter/ support directory of its own. If it did, the existing "
        "cwd-relative pause_store.py dispatch would accidentally resolve and "
        "every assertion below would pass against unfixed code. Found: "
        f"{sorted(p.name for p in worktree_path.iterdir())}"
    )


def _load_real_registry() -> dict:
    """Read the REAL config/agent_registry.json from disk (not a fixture),
    mirroring test_bo_2300_pause_resume.py's identically-named helper, so the
    workspace-setup-permission gate is fed a real, current registry payload
    rather than a hand-authored stand-in.
    """
    return json.loads(_REAL_REGISTRY_PATH.read_text(encoding="utf-8"))


def _permission_label_response() -> dict:
    """The `{output, exit_code}` shape resolve-workspace-setup-permission
    expects (see plan-feature.js ~line 1965 onward). Supplied directly rather
    than via real execution: the workspace-setup-permission gate is not what
    this ticket's fix touches, and stubbing it lets every test below focus its
    real execution on the pause-store seam alone.
    """
    return {"output": json.dumps(_load_real_registry()), "exit_code": 0}


def _build_valid_resume_answer(record: dict) -> dict:
    """Build a resume_answer that will pass validateAnswerShape() for
    whatever gate/question type the headless run actually paused on, without
    hardcoding a specific gate id (discovered dynamically from the record a
    prior real run actually wrote).
    """
    question = record.get("question") or {}
    qtype = question.get("type", "single_choice")
    gate_id = record["gate_id"]
    if qtype == "priority_choice":
        return {"gate_id": gate_id, "type": qtype, "priority": "medium"}
    if qtype == "free_text":
        return {"gate_id": gate_id, "type": qtype, "text": "resumed via ACD-2100a-4 test"}
    options = question.get("options") or ["approve"]
    action = "cancel" if "cancel" in options else options[0]
    return {"gate_id": gate_id, "type": qtype, "action": action}


# ---------------------------------------------------------------------------
# The real-execution harness (self-contained copy, per test_acd_2100a_3.py's
# own convention of not depending on _workflow_engine_harness.py's private
# internals). Unlike that file's harness -- which real-executes EVERY
# "Run the following command...:\n<cmd>\n" dispatch -- this harness real-
# executes ONLY dispatches whose prompt embeds a `pause_store.py` command
# line, and falls back to the SAME generic stub `_workflow_engine_harness.py`
# uses for everything else, so a headless run reaches an interactive gate the
# same way test_bo_2300_pause_resume.py's already-established tests do,
# without this file also having to drive real worktree creation or real
# authoring-agent dispatches end to end.
# ---------------------------------------------------------------------------

_SHIM_TEMPLATE = r"""
'use strict';

const { execSync } = require('child_process');

const __RUN_CWD__ = __RUN_CWD_JSON__;
const __labelResponses__ = __LABEL_RESPONSES_JSON__;
const __capturedCalls__ = [];

// Matches the single line carrying the pause_store.py invocation, whatever
// its exact prefix wording ("Run exactly:" / "Run the following command...:")
// or exact shell-fragment shape (a bare `python ...` call today; a
// REPO_ROOT-resolved one-liner once fixed) -- both are single-line by this
// file's own existing convention (see plan-feature.js's
// _buildRepoRootResolutionSnippet doc comment).
const _PAUSE_LINE_RE = /^.*pause_store\.py.*$/m;

async function agent(promptOrOpts, opts) {
  var label =
    (opts && opts.label) ||
    (typeof promptOrOpts === 'object' && promptOrOpts && promptOrOpts.label) ||
    null;

  var record = { prompt: promptOrOpts, opts: opts || null, real_result: null };
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
  userInput: 'Add a small test feature for pause-store resolution',
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
    """Minimal ESM `export` stripper (self-contained copy; see module docstring)."""
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
    ACTUALLY EXECUTED (not mocked) via a real Node child_process with `cwd`
    set to the given directory. Returns the parsed
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
        mode="w", suffix=".js", prefix="acd_2100a4_", delete=False, encoding="utf-8"
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
    """All captured calls whose prompt was real-executed (a pause_store.py
    dispatch), regardless of label.
    """
    return [c for c in payload.get("calls", []) if c.get("real_result") is not None]


def _parsed_real_result(call: dict):
    rr = call.get("real_result") or {}
    try:
        return json.loads((rr.get("output") or "").strip())
    except (ValueError, TypeError):
        return None


def _write_shaped_calls(payload: dict) -> list:
    """Real-executed calls whose stdout parsed to write_record()'s own output
    shape ({"ok": ..., "idempotent": ..., "path": ...} or
    {"ok": False, "error": ...}) -- identified structurally by the presence
    of the "ok" key, not by matching wording in the dispatching prompt, so
    this stays correct even if a future edit rewords the prompt text.
    """
    out = []
    for c in _real_calls(payload):
        parsed = _parsed_real_result(c)
        if isinstance(parsed, dict) and "ok" in parsed:
            out.append((c, parsed))
    return out


def _read_shaped_calls(payload: dict) -> list:
    """Real-executed calls whose stdout parsed to read_record()'s own output
    shape ({"exists": ..., "stale": ..., "record": ...}) -- identified
    structurally by the presence of the "exists" key.
    """
    out = []
    for c in _real_calls(payload):
        parsed = _parsed_real_result(c)
        if isinstance(parsed, dict) and "exists" in parsed:
            out.append((c, parsed))
    return out


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_pause_record_written_from_a_worktree_lands_in_the_project_store():
    # covers: ACD-2100a-4
    # angle: criterion
    """AC-1/AC-2: a run started with cwd set to a REAL git worktree that holds
    no installed `.leafcutter/` of its own (asserted first) must still land
    its pause record in the PROJECT's own store -- the shared repository root
    reachable via the worktree's real git linkage -- and must create no pause
    record anywhere UNDERNEATH the worktree directory the run started in.
    """
    with tempfile.TemporaryDirectory(prefix="acd2100a4_criterion_") as tmp:
        fixture = _make_worktree_fixture(Path(tmp))
        _assert_worktree_has_no_installed_leafcutter(fixture["worktree_path"])

        run_id = "acd2100a4-criterion-run"
        payload = _run_plan_feature_real(
            fixture["worktree_path"],
            label_responses={"resolve-workspace-setup-permission": _permission_label_response()},
            args={"run_id": run_id},
        )

        real_calls = _real_calls(payload)
        assert real_calls, (
            "Expected at least one real pause_store.py dispatch to be executed "
            f"when the headless run reaches an interactive gate. calls={payload.get('calls')}"
        )

        writes = _write_shaped_calls(payload)
        assert writes, (
            "Expected at least one write-shaped (pause_store.py write) real "
            f"execution whose stdout parsed as JSON. real results: "
            f"{[c.get('real_result') for c in real_calls]}"
        )
        _, write_response = writes[0]
        assert write_response.get("ok") is True, (
            "The pause-store write must report ok:true when run from inside a "
            "worktree of a project holding a real, reachable .leafcutter/ "
            f"(repository-anchored resolution). Got: {write_response}. "
            f"real_result={writes[0][0]['real_result']}"
        )

        project_store = fixture["project_dir"] / ".leafcutter" / "paused_runs" / f"{run_id}.json"
        assert project_store.exists(), (
            "AC-1: no pause record was found at the project's own store "
            f"location ({project_store}) after the process exited. "
            f"real results: {[c.get('real_result') for c in real_calls]}"
        )

        worktree_leftovers = list(fixture["worktree_path"].rglob("paused_runs"))
        assert not worktree_leftovers, (
            "AC-2: a pause-record location was created UNDERNEATH the "
            f"directory the run started in (the worktree): {worktree_leftovers}"
        )


def test_pause_record_is_found_by_a_second_process_started_elsewhere():
    # covers: ACD-2100a-4
    # angle: seam
    """AC-3: the REAL producer's real output (a pause record written by a
    process started inside a worktree) is piped into the REAL consumer (a
    second, fresh process's real pause-store read) started from a DIFFERENT
    working directory -- the project root -- and that second process must
    find the same record.
    """
    with tempfile.TemporaryDirectory(prefix="acd2100a4_seam_") as tmp:
        fixture = _make_worktree_fixture(Path(tmp))
        _assert_worktree_has_no_installed_leafcutter(fixture["worktree_path"])

        run_id = "acd2100a4-seam-run"
        permission = {"resolve-workspace-setup-permission": _permission_label_response()}

        # Process 1: real headless write from inside the worktree.
        payload1 = _run_plan_feature_real(
            fixture["worktree_path"], label_responses=permission, args={"run_id": run_id}
        )
        writes1 = _write_shaped_calls(payload1)
        assert writes1, (
            "Process 1 (worktree) must perform a real, JSON-parseable "
            f"pause_store.py write before the seam can be tested. "
            f"calls={payload1.get('calls')}"
        )
        _, write_response1 = writes1[0]
        assert write_response1.get("ok") is True, (
            f"Process 1's write must succeed. Got: {write_response1}"
        )

        project_store = fixture["project_dir"] / ".leafcutter" / "paused_runs" / f"{run_id}.json"
        assert project_store.exists(), (
            f"Test construction error: process 1 must have really written {project_store}."
        )
        on_disk_record = json.loads(project_store.read_text(encoding="utf-8"))
        gate_id = on_disk_record["gate_id"]
        answer = _build_valid_resume_answer(on_disk_record)

        # Process 2: a DIFFERENT, fresh process started with the PROJECT ROOT
        # (not the worktree) as its working directory.
        payload2 = _run_plan_feature_real(
            fixture["project_dir"],
            label_responses=permission,
            args={"run_id": run_id, "resume_answer": answer},
        )

        reads2 = _read_shaped_calls(payload2)
        assert reads2, (
            "Process 2 (project root) must dispatch a real, JSON-parseable "
            "pause-record read to consult the record process 1 wrote. "
            f"calls={payload2.get('calls')}"
        )
        _, read_response2 = reads2[0]
        assert read_response2.get("exists") is True, (
            "AC-3: the second process, started from a DIFFERENT working "
            "directory (the project root) than process 1 (a worktree), must "
            f"find the SAME record process 1 wrote. Got: {read_response2}"
        )
        found_record = read_response2.get("record") or {}
        assert found_record.get("gate_id") == gate_id, (
            "The record read back by process 2 must be the SAME record "
            f"process 1 wrote (gate_id mismatch). Got: {found_record}"
        )


def test_reported_write_failure_matches_what_is_on_disk():
    # covers: ACD-2100a-4
    # angle: failure
    """AC-4: the run that wrote the record reports the write as failed IF AND
    ONLY IF no record is present on disk afterward -- checked in both
    directions from a REAL, permission-manipulated store, run from inside a
    worktree so the assertion is meaningful under both the unfixed and the
    fixed resolution (see module docstring for why a plain, non-worktree
    project cannot distinguish the two).
    """
    with tempfile.TemporaryDirectory(prefix="acd2100a4_failure_") as tmp:
        fixture = _make_worktree_fixture(Path(tmp))
        _assert_worktree_has_no_installed_leafcutter(fixture["worktree_path"])
        permission = {"resolve-workspace-setup-permission": _permission_label_response()}
        leafcutter_dir = fixture["project_dir"] / ".leafcutter"
        original_mode = leafcutter_dir.stat().st_mode

        # --- Direction 1: unwritable store -> must NOT report success, and no
        # record may be present on disk.
        run_id_unwritable = "acd2100a4-failure-unwritable"
        try:
            leafcutter_dir.chmod(0o555)  # read + traverse, no write: mkdir() fails
            payload_unwritable = _run_plan_feature_real(
                fixture["worktree_path"], label_responses=permission,
                args={"run_id": run_id_unwritable},
            )
        finally:
            leafcutter_dir.chmod(original_mode)

        record_path_unwritable = (
            fixture["project_dir"] / ".leafcutter" / "paused_runs" / f"{run_id_unwritable}.json"
        )
        writes_unwritable = _write_shaped_calls(payload_unwritable)
        reported_ok_unwritable = bool(writes_unwritable) and writes_unwritable[0][1].get("ok") is True
        assert not reported_ok_unwritable, (
            "Direction 1 (unwritable store): the run must NOT report the "
            f"write as successful. writes={[w[1] for w in writes_unwritable]} "
            f"real_calls={[c.get('real_result') for c in payload_unwritable.get('calls', [])]}"
        )
        assert not record_path_unwritable.exists(), (
            f"Direction 1: no record should be present on disk. Found: {record_path_unwritable}"
        )

        # --- Direction 2: writable store -> must report success, and the
        # record IS present on disk.
        run_id_writable = "acd2100a4-failure-writable"
        payload_writable = _run_plan_feature_real(
            fixture["worktree_path"], label_responses=permission, args={"run_id": run_id_writable}
        )
        record_path_writable = (
            fixture["project_dir"] / ".leafcutter" / "paused_runs" / f"{run_id_writable}.json"
        )
        writes_writable = _write_shaped_calls(payload_writable)
        assert writes_writable, (
            "Direction 2 (writable store): expected a real, JSON-parseable "
            f"pause_store.py write response. calls={payload_writable.get('calls')}"
        )
        _, write_response_writable = writes_writable[0]
        assert write_response_writable.get("ok") is True, (
            "Direction 2: expected ok:true once the store is writable and "
            f"reachable via the repository-anchored resolution. Got: {write_response_writable}"
        )
        assert record_path_writable.exists(), (
            "Direction 2: a reported successful write must correspond to a "
            f"real record on disk. Missing: {record_path_writable}"
        )


def test_pause_write_is_reached_from_the_workflow_entry_point():
    # covers: ACD-2100a-4
    # angle: reachability
    """The pause record is produced by driving the REAL plan-feature.js
    workflow body (via a real Node subprocess, not by calling the pause-store
    helper directly) from inside a real worktree, and the pause outcome is
    CONSUMED in control flow -- returned as the workflow's own top-level
    result -- not merely computed and discarded.
    """
    with tempfile.TemporaryDirectory(prefix="acd2100a4_reach_") as tmp:
        fixture = _make_worktree_fixture(Path(tmp))
        _assert_worktree_has_no_installed_leafcutter(fixture["worktree_path"])
        permission = {"resolve-workspace-setup-permission": _permission_label_response()}
        run_id = "acd2100a4-reach-run"

        payload = _run_plan_feature_real(
            fixture["worktree_path"], label_responses=permission, args={"run_id": run_id}
        )

        writes = _write_shaped_calls(payload)
        assert writes, (
            "Driving the REAL templates/workflows-js/plan-feature.js top-level "
            "body (via a real Node subprocess, not by calling the pause-store "
            "helper directly) must reach a real, JSON-parseable pause_store.py "
            f"write dispatch when the run hits a headless interactive gate. "
            f"calls={payload.get('calls')}"
        )
        _, write_response = writes[0]
        assert write_response.get("ok") is True, (
            f"Expected the entry-point-driven write to succeed. Got: {write_response}"
        )

        record_path = fixture["project_dir"] / ".leafcutter" / "paused_runs" / f"{run_id}.json"
        assert record_path.exists(), (
            "The pause record must exist on disk as a consequence of driving "
            f"the workflow's real entry point. Missing: {record_path}"
        )
        on_disk = json.loads(record_path.read_text(encoding="utf-8"))
        assert on_disk.get("gate_id"), (
            f"Sanity: the record written must be a real pending-question record. Got: {on_disk}"
        )

        result = payload.get("result")
        assert isinstance(result, dict) and result.get("status") in (
            "paused_awaiting_input", "pause_persist_failed",
        ), (
            "The pause outcome must be CONSUMED in control flow -- returned "
            "as the workflow's own top-level result -- not merely computed "
            f"and discarded. Got result={result}"
        )
