"""
MODULE: test_acd_2100a_5
GOAL: Behavioral tests for ACD-2100a-5 -- "A run reaches its first question to
    the user from any working directory." This is the ANTI-REGRESSION record
    for the whole class ACD-2100a-1 through ACD-2100a-4 each fixed one site
    of (KI-ACD-004 / KI-ACD-009): every startup-path dispatch that previously
    built its command from the raw, cwd-relative `{{config.output_root}}`
    placeholder now goes through the SAME shared
    `_buildRepoRootResolutionSnippet()` mechanism in templates/workflows-js/
    plan-feature.js. This file does not add a sixth per-site repair -- it
    drives the WHOLE startup path (Pre-Stage-0 permission gate, worktree
    setup, and the first interactive gate) from THREE different starting
    working directories against the SAME project and asserts all three reach
    the same point.

THE THIRD RUN IS THE SHARP ONE (per the AC's own test_rationale): the
    project-root case already works today (the trivial case). The worktree
    case is what ACD-2100a-3 / ACD-2100a-4 already fixed (KI-ACD-009 cause 1).
    The THIRD case -- a working directory that holds neither the project nor
    any installed copy of the route's support files -- is not solved by
    either of `_buildRepoRootResolutionSnippet()`'s two existing resolution
    strategies (`git rev-parse --git-common-dir` from cwd, or probing cwd's
    immediate child directories for the ADR-001 self-hosting layout): from a
    directory with no git ancestry and no child directory holding the
    project, BOTH strategies come up empty, the shared snippet prints its
    `REGISTRYREADFAIL reason=ENOREPO` diagnostic, and the Pre-Stage-0
    Workspace-Setup Dispatch Permission Gate halts the run with a
    "registry could not be read" error BEFORE any question is ever asked --
    exactly the outcome AC-2 forbids. There is nothing in that directory to
    resolve against, so a surviving cwd-relative assumption has nowhere to
    hide; this is the test the "single resolution, not five per-site
    repairs" it_requirement exists to protect.

WHY A BARE, DISCONNECTED THIRD DIRECTORY CANNOT BE FAKED (mirrors
    test_acd_2100a_3.py / test_acd_2100a_4.py's own "second Given is the
    whole test" warning): the unrelated directory is asserted, before every
    run that depends on it, to be (a) not itself inside any git repository
    (`git rev-parse --show-toplevel` fails there) and (b) freshly created
    with zero child directories, so neither of the shared snippet's two
    existing resolution strategies can accidentally succeed against it. If
    either assertion were wrong, every scenario-C assertion below would pass
    vacuously against unfixed code.

HOW THE REAL SIDE EFFECT IS EXERCISED (Real-Artifact Behavioral Test
    Mandate): mirrors test_acd_2100a_1.py / test_acd_2100a_3.py /
    test_acd_2100a_4.py's own convention of a small, self-contained harness
    (never the shared, fully-mocked `_workflow_engine_harness.py`, which
    takes no `cwd` parameter and never runs a real shell command). This
    file's harness ACTUALLY EXECUTES, via a real Node `child_process` with a
    real, controlled `cwd`: (1) every "Run the following command...:\\n<cmd>\\n"
    single-line dispatch (the Pre-Stage-0 registry read, the worktree-setup
    script-path resolution, the worktree-setup dispatch itself, and the
    branch-detect / orphan-scan / committed-stage-scan git calls), and (2)
    every dispatch whose prompt embeds a `pause_store.py` invocation (the
    pause-persist write and its read-back verify) -- against a REAL git
    project, a REAL git worktree of it, and a REAL git worktree stub script
    that performs a REAL `git worktree add` on disk. Only the ac-triage
    classification itself (`stage-0-triage`) is given a fixed, deterministic
    answer (`route: "covered"`) so all three runs are driven to the SAME
    named first question (`covered-route-gate`) rather than depending on
    whatever a live triage agent would have said -- this does not touch any
    of the resolution machinery under test, which is exercised for real on
    every other dispatch.

TDD note: `templates/workflows-js/plan-feature.js`'s shared
    `_buildRepoRootResolutionSnippet()` has exactly the two resolution
    strategies described above and no third one. `test_all_three_working_directories_...`
    and its two siblings are expected to be RED for the third
    (working-directory-disconnected-from-the-project) scenario until
    python-coder adds a resolution path that does not depend on any
    filesystem relationship between the process's cwd and the project (per
    the AC's own test_rationale: "there is nothing there to resolve against,
    so a surviving relative path has nowhere to hide"). The project-root and
    worktree scenarios are expected to already be GREEN today (ACD-2100a-1
    through ACD-2100a-4 already fixed them) -- this file protects them against
    regression while adding the harder, previously-unproven third case.

TICKET: 06_TICKET-20260826-ACD-2100a-5.md
AC: ACD-2100a-5
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PLAN_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"
_REAL_REGISTRY_PATH = _WORKTREE_ROOT / "config" / "agent_registry.json"
_REAL_PAUSE_STORE_PY = _WORKTREE_ROOT / "scripts" / "pause_store.py"

_TIMEOUT = 60  # seconds; includes real `git worktree add` and real subprocess I/O.

_HALT_LABELS = (
    "workspace-setup-registry-uninterpretable",
    "workspace-setup-registry-unreadable",
    "workspace-setup-mis-assignment",
    "workspace-setup-agent-not-found",
)
_SCRIPT_PATH_LABEL = "resolve-worktree-setup-script-path"
_WORKTREE_SETUP_LABEL = "worktree-setup"

_CMD_LINE_RE = re.compile(r"Run the following command[^\n]*:\n([^\n]+)\n")
_WORKTREE_SETUP_PATH_RE = re.compile(
    r'"(/[^"]*\.leafcutter/scripts/setup_ticket_worktree\.py)"'
)

# ---------------------------------------------------------------------------
# The in-repository worktree-setup stub -- a self-contained copy of
# test_acd_2100a_1.py's own `_IN_REPO_STUB` (that file's own convention of
# not depending on other test files' private internals). Its own file
# location (`Path(__file__).resolve().parents[2]`) anchors the repository it
# belongs to, so the AC-authoring worktree it creates lands under the
# CORRECT project regardless of the run's own starting cwd -- exactly what
# every scenario below needs once the shared resolution snippet has located
# this script's absolute, repository-anchored path.
# ---------------------------------------------------------------------------

_WORKTREE_SETUP_STUB = textwrap.dedent(
    """\
    import json
    import subprocess
    import sys
    from pathlib import Path


    def main() -> int:
        if len(sys.argv) < 2 or sys.argv[1] != "create-ac-worktree":
            print(json.dumps({"error": "unsupported subcommand"}), file=sys.stderr)
            return 1
        slug = sys.argv[2] if len(sys.argv) > 2 else "session"
        repo_root = Path(__file__).resolve().parents[2]
        worktree_path = repo_root.parent / f"ac-authoring-{slug}"
        branch = f"ac-authoring/{slug}"
        try:
            subprocess.run(
                [
                    "git", "-C", str(repo_root), "worktree", "add",
                    "-b", branch, str(worktree_path), "main",
                ],
                check=True, capture_output=True, text=True,
            )
        except subprocess.CalledProcessError as exc:
            print(
                json.dumps({"error": "worktree add failed", "detail": exc.stderr}),
                file=sys.stderr,
            )
            return 1
        print(json.dumps({
            "worktree_path": str(worktree_path),
            "ac_store_path": str(worktree_path / "docs" / "acceptance-criteria"),
            "source_copy": "in-repo",
        }))
        return 0


    if __name__ == "__main__":
        sys.exit(main())
    """
)


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


def _make_project(tmp_path: Path) -> Path:
    """Build "the project" the Given's three runs all target: a real git
    repository holding the REAL, verbatim registry from this repository
    (never a hand-authored stand-in -- 2h.2 Fixture Authenticity Rule), a
    REAL, verbatim copy of scripts/pause_store.py, and the simplified
    in-repo worktree-setup stub above.
    """
    project_dir = tmp_path / "project"
    _init_git_project(project_dir)

    registry_dest = project_dir / ".leafcutter" / "config" / "agent_registry.json"
    registry_dest.parent.mkdir(parents=True, exist_ok=True)
    registry_dest.write_bytes(_REAL_REGISTRY_PATH.read_bytes())

    pause_store_dest = project_dir / ".leafcutter" / "scripts" / "pause_store.py"
    pause_store_dest.parent.mkdir(parents=True, exist_ok=True)
    pause_store_dest.write_bytes(_REAL_PAUSE_STORE_PY.read_bytes())

    setup_dest = project_dir / ".leafcutter" / "scripts" / "setup_ticket_worktree.py"
    setup_dest.write_text(_WORKTREE_SETUP_STUB, encoding="utf-8")

    return project_dir


def _make_run_worktree(tmp_path: Path, project_dir: Path, branch: str) -> Path:
    """A REAL `git worktree add` of `project_dir`, used as the STARTING cwd
    for scenario B -- distinct from the AC-authoring worktree the workflow
    itself creates internally via `_WORKTREE_SETUP_STUB` above. Holds NO
    `.leafcutter/` of its own (asserted below), mirroring
    test_acd_2100a_3.py / test_acd_2100a_4.py's own fixture convention.
    """
    worktree_path = tmp_path / "run-worktree"
    _run(
        [
            "git", "-C", str(project_dir), "worktree", "add",
            "-b", branch, str(worktree_path), "main",
        ]
    )
    return worktree_path


def _assert_holds_no_leafcutter(path: Path) -> None:
    """The second Given is the whole test (mirrors test_acd_2100a_3.py's own
    warning): if this assertion is wrong, every scenario-B assertion below
    would pass vacuously against unfixed, cwd-relative code.
    """
    assert not (path / ".leafcutter").exists(), (
        f"Test construction error: {path} must hold NO installed .leafcutter/ "
        "support directory of its own, or the existing cwd-relative "
        f"resolution would accidentally succeed. Found: "
        f"{sorted(p.name for p in path.iterdir())}"
    )


def _make_unrelated_directory(tmp_path: Path) -> Path:
    """A working directory that holds NEITHER the project NOR any installed
    copy of the route's support files (the AC's third Given) -- a freshly
    created, empty directory with zero children (so the shared resolution
    snippet's child-probe fallback finds nothing either) that is not itself
    inside any git repository (asserted below).
    """
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir(parents=True)
    return unrelated


def _assert_not_inside_any_repository(path: Path) -> None:
    """The second Given for scenario C (mirrors _assert_holds_no_leafcutter's
    role for scenario B): if this directory turned out to be inside a git
    repository (e.g. because the OS temp root itself is tracked), the shared
    resolution snippet's FIRST strategy (`git rev-parse --git-common-dir`)
    could accidentally succeed and every scenario-C assertion below would be
    unfalsifiable.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=str(path), capture_output=True, text=True, check=False,
    )
    assert result.returncode != 0, (
        f"Test construction error: {path} is unexpectedly inside a git "
        f"repository ({result.stdout.strip()!r}); the unrelated-directory "
        "scenario requires a directory with no git ancestry at all."
    )
    assert not any(path.iterdir()), (
        f"Test construction error: {path} must be empty (no child "
        "directories), or the shared resolution snippet's ADR-001 "
        "child-probe fallback could accidentally succeed against it."
    )


# ---------------------------------------------------------------------------
# The real-execution harness (self-contained copy of the equivalent harness
# in test_acd_2100a_1.py / test_acd_2100a_3.py / test_acd_2100a_4.py, per
# those files' own convention of not depending on
# _workflow_engine_harness.py's private internals -- that shared harness
# takes no `cwd` parameter and never runs a real shell command, so it cannot
# prove anything about THIS AC). Combines test_acd_2100a_1.py /
# test_acd_2100a_3.py's generic "Run the following command...:\n<cmd>\n"
# real-execution with test_acd_2100a_4.py's pause_store.py-line
# real-execution, since this AC's Then clauses span every one of those
# dispatch sites at once.
# ---------------------------------------------------------------------------

_SHIM_TEMPLATE = r"""
'use strict';

const { execSync } = require('child_process');

const __RUN_CWD__ = __RUN_CWD_JSON__;
const __labelResponses__ = __LABEL_RESPONSES_JSON__;
const __capturedCalls__ = [];

const _CMD_RE = /Run the following command[^\n]*:\n([^\n]+)\n/;
const _PAUSE_LINE_RE = /^.*pause_store\.py.*$/m;

async function agent(promptOrOpts, opts) {
  var label =
    (opts && opts.label) ||
    (typeof promptOrOpts === 'object' && promptOrOpts && promptOrOpts.label) ||
    null;

  var record = { prompt: promptOrOpts, opts: opts || null, real_result: null };
  var response;

  if (label !== null && Object.prototype.hasOwnProperty.call(__labelResponses__, label)) {
    // Caller-supplied override (e.g. the deterministic "stage-0-triage"
    // answer this file forces) always wins over real execution.
    response = __labelResponses__[label];
  } else if (typeof promptOrOpts === 'string' && promptOrOpts.indexOf('pause_store.py') !== -1) {
    var pm = promptOrOpts.match(_PAUSE_LINE_RE);
    var preal = { command: null, output: '', exit_code: null, stderr: '' };
    if (pm) {
      var pcmd = pm[0].trim().replace(/\{\{config\.output_root\}\}/g, '.leafcutter');
      preal.command = pcmd;
      try {
        var pout = execSync(pcmd, { cwd: __RUN_CWD__, encoding: 'utf8', timeout: 15000 });
        preal.output = pout;
        preal.exit_code = 0;
      } catch (pe) {
        preal.output = (pe.stdout || '').toString();
        preal.stderr = (pe.stderr || '').toString();
        preal.exit_code = (pe.status === null || pe.status === undefined) ? 1 : pe.status;
      }
    } else {
      preal.stderr = 'harness: could not locate a pause_store.py command line in the prompt';
      preal.exit_code = 1;
    }
    record.real_result = preal;
    var pparsed = null;
    try { pparsed = JSON.parse((preal.output || '').trim()); } catch (_pe) { pparsed = null; }
    response = pparsed;
  } else if (typeof promptOrOpts === 'string') {
    var m = promptOrOpts.match(_CMD_RE);
    if (m) {
      // Mirrors template_compiler.inject_config's resolution of the ONE
      // build-time placeholder this file's fixture cares about (see
      // config/skills_config.default.json: "output_root": ".leafcutter").
      var cmd = m[1].replace(/\{\{config\.output_root\}\}/g, '.leafcutter');
      var real = { command: cmd, output: '', exit_code: 0, stderr: '' };
      try {
        var out = execSync(cmd, { cwd: __RUN_CWD__, encoding: 'utf8', timeout: 15000 });
        real.output = out;
      } catch (e) {
        real.output = (e.stdout || '').toString();
        real.stderr = (e.stderr || '').toString();
        real.exit_code = (e.status === null || e.status === undefined) ? 1 : e.status;
      }
      record.real_result = real;
      response = { output: real.output, exit_code: real.exit_code, stderr: real.stderr };
    } else {
      response = { status: 'ok', message: 'stub', passed: true, git_type: 'file', branch: 'feature-stub', exit_code: 0, output: '' };
    }
  } else {
    response = { status: 'ok', message: 'stub', passed: true, git_type: 'file', branch: 'feature-stub', exit_code: 0, output: '' };
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
  userInput: 'Add a small test feature for startup-path resolution',
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
    with cwd set to the given directory, and every dispatch matching this
    harness's real-execution patterns ACTUALLY EXECUTED (not mocked) via a
    real Node child_process. Returns the parsed
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
        mode="w", suffix=".js", prefix="acd_2100a5_", delete=False, encoding="utf-8"
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


def _calls_with_label(payload: dict, label: str) -> list:
    calls = payload.get("calls", [])
    return [
        c for c in calls
        if isinstance(c.get("opts"), dict) and c["opts"].get("label") == label
    ]


def _calls_with_any_label(payload: dict, labels: tuple) -> list:
    calls = payload.get("calls", [])
    return [
        c for c in calls
        if isinstance(c.get("opts"), dict) and c["opts"].get("label") in labels
    ]


_TRIAGE_COVERED_RESPONSE = {
    "route": "covered",
    "existing_acs": ["ACD-STUB-1"],
    "parent_l1_id": None,
    "rationale": "stub triage forcing the covered-route-gate as the first question",
}


def _label_responses_forcing_first_question() -> dict:
    """Forces ac-triage's classification to 'covered' so every scenario is
    driven to the SAME named first question (the 'covered-route-gate'
    resolveGate() call at plan-feature.js ~line 2492) rather than depending
    on what a live triage agent would have said. This override does not
    touch any of the resolution machinery under test (the registry read,
    the worktree-setup script-path resolution, the worktree-setup dispatch,
    or the pause-store read/write/verify), which are all real-executed on
    every scenario below.
    """
    return {"stage-0-triage": _TRIAGE_COVERED_RESPONSE}


def _collect_resolved_absolute_paths(payload: dict, project_dir: Path) -> list[str]:
    """Collect every absolute, repository-anchored path the run's OWN
    OBSERVED BEHAVIOUR reveals it resolved before the first question --
    never from reading the workflow source (per the AC's own reachability
    Then clause). Three independent, structurally-identified observation
    points:

      1. The 'resolve-worktree-setup-script-path' dispatch's REAL stdout on
         success is the literal resolved absolute path (buildRepoAnchored-
         ResolutionCommand()'s snippet ends with `echo "$SCRIPT"`).
      2. The 'worktree-setup' dispatch's own PROMPT TEXT embeds the resolved
         absolute script path literally (a static JS string built from the
         resolution above, not a shell variable) -- extracted the same way
         test_acd_2100a_1.py's AC-4/AC-5 test already does.
      3. Every real-executed pause_store.py write response whose parsed
         JSON carries a "path" key (write_record()'s own success shape).
    """
    paths: list[str] = []

    for call in _calls_with_label(payload, _SCRIPT_PATH_LABEL):
        real = call.get("real_result")
        if real and real.get("exit_code") == 0:
            candidate = (real.get("output") or "").strip()
            if candidate:
                paths.append(candidate)

    for call in _calls_with_label(payload, _WORKTREE_SETUP_LABEL):
        prompt = call.get("prompt")
        if isinstance(prompt, str):
            m = _WORKTREE_SETUP_PATH_RE.search(prompt)
            if m:
                paths.append(m.group(1))

    for call in payload.get("calls", []):
        real = call.get("real_result")
        if not real:
            continue
        try:
            parsed = json.loads((real.get("output") or "").strip())
        except (ValueError, TypeError):
            continue
        if isinstance(parsed, dict) and isinstance(parsed.get("path"), str):
            paths.append(parsed["path"])

    return paths


def _drive_three_scenarios(tmp_path: Path, run_prefix: str) -> dict:
    """Drive the SAME project three times, once per Given cwd, and return
    {"root": payload, "worktree": payload, "unrelated": payload}.
    """
    project_dir = _make_project(tmp_path)
    run_worktree = _make_run_worktree(tmp_path, project_dir, f"{run_prefix}-worktree-branch")
    _assert_holds_no_leafcutter(run_worktree)
    unrelated_dir = _make_unrelated_directory(tmp_path)
    _assert_not_inside_any_repository(unrelated_dir)

    label_responses = _label_responses_forcing_first_question()

    payload_root = _run_plan_feature_real(
        project_dir, label_responses,
        {"run_id": f"{run_prefix}-root", "userInput": f"Add a feature --component {run_prefix}root"},
    )
    payload_worktree = _run_plan_feature_real(
        run_worktree, label_responses,
        {"run_id": f"{run_prefix}-worktree", "userInput": f"Add a feature --component {run_prefix}wt"},
    )
    payload_unrelated = _run_plan_feature_real(
        unrelated_dir, label_responses,
        {"run_id": f"{run_prefix}-unrelated", "userInput": f"Add a feature --component {run_prefix}unrel"},
    )

    return {
        "root": (payload_root, project_dir),
        "worktree": (payload_worktree, project_dir),
        "unrelated": (payload_unrelated, project_dir),
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_all_three_working_directories_reach_the_first_question():
    # covers: ACD-2100a-5
    # angle: criterion
    """AC-1: the same run, started three times against the same project --
    process cwd set to the project root, to a real git worktree of it, and
    to a directory holding neither the project nor any installed copy of
    the route's support files -- reaches the SAME point in all three cases:
    the first question the route puts to the user (the 'covered-route-gate'
    resolveGate() call resolving to status "paused_awaiting_input").
    """
    with tempfile.TemporaryDirectory(prefix="acd2100a5_criterion_") as tmp:
        scenarios = _drive_three_scenarios(Path(tmp), "acd2100a5crit")

        for name, (payload, _project_dir) in scenarios.items():
            result = payload.get("result")
            assert isinstance(result, dict) and result.get("status") == "paused_awaiting_input", (
                f"Scenario '{name}': expected the run to reach the first question "
                f"(status='paused_awaiting_input'), but result={result}. "
                f"calls={payload.get('calls')}"
            )
            assert result.get("gate_id") == "covered-route-gate", (
                f"Scenario '{name}': expected the first question to be the "
                f"'covered-route-gate' gate this test forced via stage-0-triage. "
                f"Got: {result}"
            )


def test_no_scenario_halts_before_the_first_question_on_a_missing_file_or_non_repository():
    # covers: ACD-2100a-5
    # angle: failure
    """AC-2: none of the three runs terminates before the first question by
    reporting a file it could not find or a directory that is not a
    repository. The assertion is on each run's OWN RECORDED OUTCOME (its
    terminal `result` and which halt-labelled agent() calls it dispatched),
    not on the mere absence of a raised exception.
    """
    with tempfile.TemporaryDirectory(prefix="acd2100a5_failure_") as tmp:
        scenarios = _drive_three_scenarios(Path(tmp), "acd2100a5fail")

        for name, (payload, _project_dir) in scenarios.items():
            halt_calls = _calls_with_any_label(payload, _HALT_LABELS)
            assert not halt_calls, (
                f"Scenario '{name}': the run halted before the first question "
                f"via one of {_HALT_LABELS} (a file-not-found / not-a-repository "
                f"outcome). calls={payload.get('calls')}"
            )

            result = payload.get("result")
            assert isinstance(result, dict) and result.get("status") != "error", (
                f"Scenario '{name}': the run's own recorded outcome is an error "
                f"reported before the first question was ever asked. result={result}"
            )


def test_every_resolved_support_file_path_observed_before_the_first_question_is_inside_the_project():
    # covers: ACD-2100a-5
    # angle: reachability
    """AC-3: for each of the three runs, every support-file location the
    process actually resolved before the first question -- collected from
    OBSERVED PROCESS BEHAVIOUR (the resolve-worktree-setup-script-path
    dispatch's real stdout, the worktree-setup dispatch's own dispatched
    command text, and every real pause_store.py write's own "path" field --
    never from reading templates/workflows-js/plan-feature.js's source) --
    resolves to a path inside the project the run was pointed at. A source
    scan for the literal string `.leafcutter` would pass on a dead code path
    and fail on a correct one built by concatenation; this test observes
    only what the process itself reported having resolved.
    """
    with tempfile.TemporaryDirectory(prefix="acd2100a5_reach_") as tmp:
        scenarios = _drive_three_scenarios(Path(tmp), "acd2100a5reach")

        # This Then clause is only meaningful where the run got far enough to
        # resolve and dispatch at least one support-file location -- a
        # scenario that halted with zero such resolutions (the exact failure
        # AC-1/AC-2 above already catch) would make this loop vacuously pass.
        # At least one scenario overall must have produced observable paths,
        # or this test itself is not exercising anything.
        any_paths_seen = False

        for name, (payload, project_dir) in scenarios.items():
            resolved_paths = _collect_resolved_absolute_paths(payload, project_dir)
            if resolved_paths:
                any_paths_seen = True
            for resolved in resolved_paths:
                assert resolved.startswith(str(project_dir)), (
                    f"Scenario '{name}': observed a resolved support-file "
                    f"location ({resolved!r}) that is NOT inside the project "
                    f"this run was pointed at ({project_dir}). "
                    f"All resolved paths observed: {resolved_paths}"
                )

        assert any_paths_seen, (
            "Test construction error: none of the three scenarios produced any "
            "observable resolved support-file path at all -- this test cannot "
            "distinguish correct resolution from a run that never got far "
            f"enough to resolve anything. scenarios={ {k: v[0].get('result') for k, v in scenarios.items()} }"
        )
