"""
MODULE: test_acd_2100a_3
GOAL: Behavioral tests for ACD-2100a-3 -- "The startup charter check finds the
    agent registry when the run starts inside a worktree."

INCIDENT BEING REGRESSION-TESTED (KI-ACD-009 cause 1): templates/workflows-js/
    plan-feature.js's Pre-Stage-0 Workspace-Setup Dispatch Permission Gate
    (around line 1885) dispatches:

        cat {{config.output_root}}/config/agent_registry.json

    `{{config.output_root}}` is a BUILD-TIME placeholder that resolves to the
    bare relative name ".leafcutter" (see config/skills_config.default.json).
    Because the string is never anchored to an absolute, repository-anchored
    location, the check resolves it against WHATEVER the dispatching agent's
    own process working directory happens to be. When a run is started with
    cwd set to a `git worktree` of the project -- e.g. the very AC-authoring
    worktree this route creates -- that worktree holds no `.leafcutter/` of
    its own (per ADR-001, `.leafcutter/` is untracked build output that only
    `install_shims` populates on the project's own checkout; `git worktree
    add` only ever checks out TRACKED content). The `cat` fails, the check
    fails CLOSED (a false "does not permit" verdict), and the run halts even
    though the project's own registry genuinely grants the permission.

WHY A BARE, EMPTY WORKTREE CANNOT PROVE THIS (see the AC's own test_rationale,
    "the second Given is the whole test"): if the fixture worktree happens to
    have its own `.leafcutter/config/agent_registry.json` (or if the fixture
    never places a registry ANYWHERE reachable), the Then clause is
    unfalsifiable -- either the buggy cwd-relative read accidentally resolves,
    or nothing could have resolved it either way. This file therefore builds a
    REAL git repository ("the project"), writes an UNTRACKED
    `.leafcutter/config/agent_registry.json` inside it (matching production:
    the registry is build output, never committed), and creates a REAL git
    worktree of that repository as a SIBLING directory holding no
    `.leafcutter/` of its own -- verified absent before every run below.

HOW THE REAL SIDE EFFECT IS EXERCISED (Real-Artifact Behavioral Test Mandate):
    Mirrors unit_tests/workflows/test_acd_2100a_1.py's own harness
    (`_run_plan_feature_real`), which is intentionally NOT the shared
    `_workflow_engine_harness.py` mock -- that mock stubs every agent() call
    with a canned response and never actually runs a shell command, so it
    cannot tell us whether the registry read reaches the project's real,
    on-disk `config/agent_registry.json` from inside a real worktree. This
    file's harness ACTUALLY EXECUTES every "Run the following command
    ...:\\n<cmd>\\nReturn JSON: ..." dispatch via a real Node child_process,
    with a real controlled `cwd` set to the real worktree this file creates on
    disk with real `git worktree add`.

TDD note: templates/workflows-js/plan-feature.js does not yet resolve the
    registry read to a location anchored on the project's repository rather
    than the caller's cwd. All three tests below are expected to be RED until
    python-coder extends the shared resolution named in ACD-2100a-1's
    it_requirements (buildRepoAnchoredResolutionCommand /
    resolveRepoAnchoredScriptPath) to reach the registry from inside a linked
    worktree that has no local `.leafcutter/` of its own.

TICKET: 04_TICKET-20260826-ACD-2100a-3.md
AC: ACD-2100a-3
"""

from __future__ import annotations

import json
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

_TIMEOUT = 40  # seconds; includes real `git worktree add` I/O.
_MIS_ASSIGNMENT_LABEL = "workspace-setup-mis-assignment"
_SETUP_RELATED_LABELS = ("resolve-worktree-setup-script-path", "worktree-setup")


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, check=True, capture_output=True, text=True
    )


def _make_worktree_fixture(tmp_path: Path, *, registry_bytes: bytes) -> dict:
    """Build the Given: a REAL git repository ("the project") holding an
    UNTRACKED `.leafcutter/config/agent_registry.json` (matching production --
    the registry is build output, never committed), and a REAL git worktree of
    that repository, created as a sibling directory, holding NO `.leafcutter/`
    of its own.

    Layout:
        tmp_path/
          project/                        <- "the project": a real git repo
            .leafcutter/config/agent_registry.json  <- the project's registry
                                                         (untracked -- git
                                                         worktree add will NOT
                                                         copy this into any
                                                         linked worktree)
          ac-authoring-worktree/          <- a REAL `git worktree add` of
                                              project/, on its own branch --
                                              holds no .leafcutter/ of its own
    """
    repo_dir = tmp_path / "project"
    repo_dir.mkdir(parents=True)
    _run(["git", "init", "-b", "main", str(repo_dir)])
    _run(["git", "-C", str(repo_dir), "config", "user.email", "test@example.com"])
    _run(["git", "-C", str(repo_dir), "config", "user.name", "Test"])
    (repo_dir / "README.md").write_text("seed\n", encoding="utf-8")
    _run(["git", "-C", str(repo_dir), "add", "README.md"])
    _run(["git", "-C", str(repo_dir), "commit", "-m", "seed"])

    registry_path = repo_dir / ".leafcutter" / "config" / "agent_registry.json"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_bytes(registry_bytes)
    # Deliberately NOT `git add`-ed: .leafcutter/ is untracked build output
    # (ADR-001). This is exactly what leaves a linked worktree of `repo_dir`
    # with no copy of its own.

    worktree_path = tmp_path / "ac-authoring-worktree"
    _run(
        [
            "git", "-C", str(repo_dir), "worktree", "add",
            "-b", "ac-authoring/test", str(worktree_path), "main",
        ]
    )

    return {"repo_dir": repo_dir, "worktree_path": worktree_path}


def _assert_worktree_has_no_installed_registry(worktree_path: Path) -> None:
    """The second Given is the whole test (per the AC's own test_rationale):
    if this fixture assertion is wrong, every assertion below would pass
    vacuously against unfixed, cwd-relative code.
    """
    assert not (worktree_path / ".leafcutter").exists(), (
        "Test construction error: the worktree fixture must hold NO installed "
        ".leafcutter/ support directory of its own. If it did, the existing "
        "cwd-relative `cat .leafcutter/config/agent_registry.json` read would "
        "accidentally resolve and every assertion below would pass against "
        "unfixed code -- the exact construction hazard this AC's test_rationale "
        f"warns about. Found: {sorted(p.name for p in worktree_path.iterdir())}"
    )


# ---------------------------------------------------------------------------
# The real-execution harness (self-contained copy of the equivalent harness in
# test_acd_2100a_1.py, per that file's own convention of not depending on
# _workflow_engine_harness.py's private internals).
# ---------------------------------------------------------------------------

_SHIM_TEMPLATE = r"""
'use strict';

const { execSync } = require('child_process');

const __RUN_CWD__ = __RUN_CWD_JSON__;
const __labelResponses__ = __LABEL_RESPONSES_JSON__;
const __capturedCalls__ = [];

const _CMD_RE = /Run the following command[^\n]*:\n([^\n]+)\n/;

async function agent(promptOrOpts, opts) {
  var label =
    (opts && opts.label) ||
    (typeof promptOrOpts === 'object' && promptOrOpts && promptOrOpts.label) ||
    null;

  var record = { prompt: promptOrOpts, opts: opts || null, real_result: null };
  var response;

  if (label !== null && Object.prototype.hasOwnProperty.call(__labelResponses__, label)) {
    response = __labelResponses__[label];
  } else if (typeof promptOrOpts === 'string') {
    var m = promptOrOpts.match(_CMD_RE);
    if (m) {
      // Mirrors template_compiler.inject_config's resolution of the ONE
      // build-time placeholder this file's fixture cares about (see
      // config/skills_config.default.json: "output_root": ".leafcutter").
      var cmd = m[1].replace(/\{\{config\.output_root\}\}/g, '.leafcutter');
      var real = { output: '', exit_code: 0, stderr: '' };
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
      response = { status: 'ok', message: 'stub', passed: true, exit_code: 0, output: '' };
    }
  } else {
    response = { status: 'ok', message: 'stub', passed: true, exit_code: 0, output: '' };
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
  userInput: 'stub user input',
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
    with every "Run the following command ...:\\n<cmd>\\n" agent() dispatch
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
        mode="w", suffix=".js", prefix="acd_2100a3_", delete=False, encoding="utf-8"
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_registry_read_succeeds_from_a_worktree_with_no_installed_support_files():
    # covers: ACD-2100a-3
    # angle: criterion
    """AC-1/AC-2/AC-3/AC-5: a real git worktree of a project, asserted first to
    hold no installed `.leafcutter/` support directory, is the process working
    directory; the project's own registry grants `permits_shell` to a
    deliberately non-default agent id, and the startup check must return a
    verdict DERIVED FROM THAT REGISTRY'S CONTENTS -- not from a hardcoded
    default -- so the run does not halt with the "does not permit" mis-
    assignment error.
    """
    with tempfile.TemporaryDirectory(prefix="acd2100a3_criterion_") as tmp:
        registry_bytes = json.dumps(
            {"agents": [{"id": "custom-worktree-agent", "permits_shell": True}]}
        ).encode("utf-8")
        fixture = _make_worktree_fixture(Path(tmp), registry_bytes=registry_bytes)
        _assert_worktree_has_no_installed_registry(fixture["worktree_path"])

        payload = _run_plan_feature_real(
            fixture["worktree_path"],
            label_responses={},
            args={"workspace_setup_agent": "custom-worktree-agent"},
        )

        mis_assignment_calls = _calls_with_label(payload, _MIS_ASSIGNMENT_LABEL)
        assert not mis_assignment_calls, (
            "The startup charter check reported the registry (or the agent's "
            "permission) as missing/denied when run from inside a worktree with "
            "no installed .leafcutter/ of its own, even though the project's own "
            "registry (reachable via the worktree's real git linkage to its "
            "parent repository) grants permits_shell=true to "
            "'custom-worktree-agent'. This proves the check is not reading the "
            f"project's registry. calls={payload.get('calls')}"
        )

        result = payload.get("result")
        if isinstance(result, dict):
            assert result.get("status") != "error" or "does not permit" not in (
                result.get("message") or ""
            ), (
                "The run halted with the workspace-setup permission-denied error "
                f"even though the project's registry grants it. result={result}"
            )

        setup_related = _calls_with_any_label(payload, _SETUP_RELATED_LABELS)
        assert setup_related, (
            "The run did not continue past the startup charter check to the next "
            "step (no resolve-worktree-setup-script-path / worktree-setup "
            f"dispatch was captured). calls={payload.get('calls')}"
        )


def test_startup_check_registry_read_is_reached_from_the_workflow_entry_point():
    # covers: ACD-2100a-3
    # angle: reachability
    """AC-4: driving the REAL plan-feature.js workflow body (via a real Node
    subprocess, not by importing a helper function) from inside a real
    worktree reaches the step after the startup charter check -- the check's
    verdict is CONSUMED in control flow (the workflow dispatches its next real
    step), not merely computed and discarded.
    """
    with tempfile.TemporaryDirectory(prefix="acd2100a3_reach_") as tmp:
        registry_bytes = json.dumps(
            {"agents": [{"id": "worktree-agent", "permits_shell": True}]}
        ).encode("utf-8")
        fixture = _make_worktree_fixture(Path(tmp), registry_bytes=registry_bytes)
        _assert_worktree_has_no_installed_registry(fixture["worktree_path"])

        payload = _run_plan_feature_real(
            fixture["worktree_path"], label_responses={}, args={}
        )

        setup_related = _calls_with_any_label(payload, _SETUP_RELATED_LABELS)
        assert setup_related, (
            "The workflow never reached the step after the startup charter "
            "check -- no dispatch for resolving or running the worktree-setup "
            "step was captured. The check's verdict must be CONSUMED in "
            "control flow (the run must proceed to dispatch the next real "
            "step), not merely computed and thrown away. "
            f"calls={payload.get('calls')}"
        )

        mis_assignment_calls = _calls_with_label(payload, _MIS_ASSIGNMENT_LABEL)
        assert not mis_assignment_calls, (
            "The run halted at the startup charter check instead of continuing "
            f"to the next step. calls={payload.get('calls')}"
        )


def test_registry_read_uses_the_real_on_disk_registry_file():
    # covers: ACD-2100a-3
    # angle: real_artifact
    """The registry fed to the check must be the project's own
    config/agent_registry.json read VERBATIM from disk -- this test copies
    THIS repository's actual, real file byte-for-byte into the fixture
    project's `.leafcutter/config/agent_registry.json` rather than hand-
    building a synthetic one, and asserts the computed verdict matches the
    real `permits_shell` value that file actually carries for
    'worktree-agent', the agent this route uses to create the authoring
    worktree.
    """
    real_registry_bytes = _REAL_REGISTRY_PATH.read_bytes()
    real_registry = json.loads(real_registry_bytes.decode("utf-8"))
    match = next(
        (e for e in real_registry.get("agents", []) if e.get("id") == "worktree-agent"),
        None,
    )
    assert match is not None, (
        "Test construction error: this repository's own "
        "config/agent_registry.json no longer registers a 'worktree-agent' "
        "entry -- update this test's expectations to match the current file."
    )
    assert match.get("permits_shell") is True, (
        "Test construction error: expected the real, on-disk "
        "config/agent_registry.json to currently grant permits_shell=true to "
        "'worktree-agent' so this test can distinguish a genuine registry read "
        "from the fail-closed default (permits_shell=false); the real file no "
        "longer does -- update this test."
    )

    with tempfile.TemporaryDirectory(prefix="acd2100a3_real_artifact_") as tmp:
        fixture = _make_worktree_fixture(
            Path(tmp), registry_bytes=real_registry_bytes
        )
        _assert_worktree_has_no_installed_registry(fixture["worktree_path"])

        payload = _run_plan_feature_real(
            fixture["worktree_path"], label_responses={}, args={}
        )

        mis_assignment_calls = _calls_with_label(payload, _MIS_ASSIGNMENT_LABEL)
        assert not mis_assignment_calls, (
            "The real, verbatim config/agent_registry.json from this repository "
            "grants permits_shell=true to 'worktree-agent', but the startup "
            "charter check denied it when run from inside a worktree holding no "
            f"installed copy of its own. calls={payload.get('calls')}"
        )

        setup_related = _calls_with_any_label(payload, _SETUP_RELATED_LABELS)
        assert setup_related, (
            "The run did not continue past the startup charter check to the "
            f"next step. calls={payload.get('calls')}"
        )
