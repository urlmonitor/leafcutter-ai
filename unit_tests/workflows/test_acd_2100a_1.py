"""
MODULE: test_acd_2100a_1
GOAL: Behavioral tests for ACD-2100a-1 -- "The worktree step runs the copy of
    the setup script that belongs to the repository being worked on."

INCIDENT BEING REGRESSION-TESTED (KI-ACD-004): templates/workflows-js/
    plan-feature.js line ~1800 dispatches the "worktree-setup" agent() call
    with the instruction:

        python {{config.output_root}}/scripts/setup_ticket_worktree.py create-ac-worktree

    `{{config.output_root}}` is a BUILD-TIME placeholder that resolves to the
    bare relative name ".leafcutter" (see config/skills_config.default.json).
    Because the string is never anchored to an absolute, repository-rooted
    location, the sub-agent that actually runs the command resolves it against
    WHATEVER its own process working directory happens to be. In the
    self-hosting dev layout (ADR-001) that selects the DEPLOYED build-output
    copy sitting in the untracked workspace parent -- not the copy that
    belongs to the repository the run is supposed to operate on.

WHY A SINGLE FIXTURE COPY CANNOT PROVE THIS (see the AC's own test_rationale):
    A test that places only one copy of setup_ticket_worktree.py on disk
    cannot fail -- whichever path is resolved, the same file runs. This file
    therefore builds TWO physically distinct, externally-observable copies
    (each stamped with a different `source_copy` marker in its own stdout)
    and drives the REAL plan-feature.js workflow body against them.

HOW THE REAL SIDE EFFECT IS EXERCISED (Real-Artifact Behavioral Test Mandate):
    The standard `_workflow_engine_harness.py` mock stubs every agent() call
    with a static canned response -- it never actually runs a shell command,
    so it cannot tell us WHICH physical script file executes or whether a
    real `git worktree add` landed on disk. This file therefore uses its own
    small harness (`_run_plan_feature_real`) whose agent() mock, for any
    dispatch matching this file's pre-existing "Run the following command
    ...:\\n<cmd>\\nReturn JSON: ..." convention (already used by
    detect-current-branch, resolve-workspace-setup-permission, and
    worktree-setup), ACTUALLY EXECUTES that command via a real Node
    child_process, with a real controlled `cwd`, against a real temporary
    filesystem fixture. This is a genuine round-trip: the real
    setup_ticket_worktree.py stub this file writes to disk is the thing that
    runs, and the real git worktree it creates is the thing this file reads
    back and asserts on -- not a mocked call-args inspection.

TDD note: templates/workflows-js/plan-feature.js does not yet resolve this
    script location to an absolute, repository-anchored path. All three tests
    below are expected to be RED until python-coder implements the shared
    resolution named in ACD-2100a-1's it_requirements (also consumed by the
    sibling sites ACD-2100a-3 and ACD-2100a-4).

TICKET: 01_TICKET-20260826-ACD-2100a-1.md
AC: ACD-2100a-1
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

_TIMEOUT = 40  # seconds; includes real `git worktree add` I/O.
_PERMISSION_LABEL = "resolve-workspace-setup-permission"
_SETUP_LABEL = "worktree-setup"

_CMD_LINE_RE = re.compile(r"Run the following command[^\n]*:\n([^\n]+)\n")


# ---------------------------------------------------------------------------
# Fixture script bodies -- the two OBSERVABLY DIFFERENT copies of
# setup_ticket_worktree.py the Given clause requires.
# ---------------------------------------------------------------------------

_IN_REPO_STUB = textwrap.dedent(
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
        # This copy is physically installed at <repo_root>/.leafcutter/scripts/,
        # so its own file location anchors the repository it belongs to.
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

_PARENT_STUB = textwrap.dedent(
    """\
    import json
    import sys


    def main() -> int:
        if len(sys.argv) < 2 or sys.argv[1] != "create-ac-worktree":
            print(json.dumps({"error": "unsupported subcommand"}), file=sys.stderr)
            return 1
        slug = sys.argv[2] if len(sys.argv) > 2 else "session"
        # This copy is the untracked-parent BUILD OUTPUT -- it must never be the
        # one that runs. It performs no real git operation and reports a bogus
        # location, so a wrong-copy execution is unmistakable in the output.
        print(json.dumps({
            "worktree_path": f"/nonexistent/parent-worktree-{slug}",
            "ac_store_path": "/nonexistent/parent-ac-store",
            "source_copy": "parent",
        }))
        return 0


    if __name__ == "__main__":
        sys.exit(main())
    """
)


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, check=True, capture_output=True, text=True
    )


def _make_fixture(tmp_path: Path, *, with_repo_copy: bool) -> dict:
    """Build the Given: two candidate install locations, one of which is a real
    git repository ("the repository the run will operate on") and the other of
    which is the untracked parent directory itself (NOT a repository).

    Layout:
        tmp_path/                              <- untracked parent (not a repo)
          .leafcutter/scripts/setup_ticket_worktree.py   <- the WRONG copy
          target-repo/                          <- a real git repo, branch "main"
            .leafcutter/scripts/setup_ticket_worktree.py <- the RIGHT copy
                                                              (only when
                                                              with_repo_copy)
    """
    parent_dir = tmp_path
    repo_dir = parent_dir / "target-repo"
    repo_dir.mkdir(parents=True)

    _run(["git", "init", "-b", "main", str(repo_dir)])
    _run(["git", "-C", str(repo_dir), "config", "user.email", "test@example.com"])
    _run(["git", "-C", str(repo_dir), "config", "user.name", "Test"])
    (repo_dir / "README.md").write_text("seed\n", encoding="utf-8")
    _run(["git", "-C", str(repo_dir), "add", "README.md"])
    _run(["git", "-C", str(repo_dir), "commit", "-m", "seed"])

    parent_scripts = parent_dir / ".leafcutter" / "scripts"
    parent_scripts.mkdir(parents=True)
    (parent_scripts / "setup_ticket_worktree.py").write_text(
        _PARENT_STUB, encoding="utf-8"
    )

    if with_repo_copy:
        repo_scripts = repo_dir / ".leafcutter" / "scripts"
        repo_scripts.mkdir(parents=True)
        (repo_scripts / "setup_ticket_worktree.py").write_text(
            _IN_REPO_STUB, encoding="utf-8"
        )

    return {"parent_dir": parent_dir, "repo_dir": repo_dir}


def _permission_label_response() -> dict:
    """Real, registry-backed 'permitted' verdict for the pre-Stage-0 gate this
    workflow dispatches unconditionally -- out of scope for THIS AC (that is
    ACD-2100a-3's registry-read call site), so it is supplied directly rather
    than exercised through the same cwd-relative bug.
    """
    registry = json.loads(_REAL_REGISTRY_PATH.read_text(encoding="utf-8"))
    return {"output": json.dumps(registry), "exit_code": 0}


# ---------------------------------------------------------------------------
# The real-execution harness.
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
    """Minimal ESM `export` stripper (self-contained copy of the equivalent
    helper in _workflow_engine_harness.py, so this file does not depend on
    that module's private internals)."""
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
        mode="w", suffix=".js", prefix="acd_2100a1_", delete=False, encoding="utf-8"
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


def _setup_calls(payload: dict) -> list:
    calls = payload.get("calls", [])
    return [
        c for c in calls
        if isinstance(c.get("opts"), dict) and c["opts"].get("label") == _SETUP_LABEL
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_worktree_step_runs_the_in_repo_copy_from_an_untracked_cwd():
    # covers: ACD-2100a-1
    """AC-1/AC-3: two distinguishable copies of the setup step exist on disk --
    one inside the target repository, one in the untracked parent -- and, driven
    from the untracked parent's own working directory, the marker emitted by the
    IN-REPOSITORY copy (not the parent copy) appears in the captured output.
    """
    with tempfile.TemporaryDirectory(prefix="acd2100a1_criterion_") as tmp:
        fixture = _make_fixture(Path(tmp), with_repo_copy=True)
        payload = _run_plan_feature_real(
            fixture["parent_dir"],
            label_responses={_PERMISSION_LABEL: _permission_label_response()},
            args={},
        )
        setup_calls = _setup_calls(payload)
        assert setup_calls, (
            f"No '{_SETUP_LABEL}' agent() dispatch was captured. "
            f"calls={payload.get('calls')}"
        )

        real = setup_calls[0].get("real_result")
        assert real is not None, (
            "The worktree-setup prompt did not match the executable "
            f"shell-command pattern this file relies on: {setup_calls[0].get('prompt')!r}"
        )
        assert real.get("exit_code") == 0, f"setup step failed to run: {real}"

        try:
            out_payload = json.loads(real.get("output", ""))
        except json.JSONDecodeError:
            raise AssertionError(
                f"worktree-setup did not emit JSON on stdout: {real}"
            ) from None

        assert out_payload.get("source_copy") == "in-repo", (
            "The PARENT copy of setup_ticket_worktree.py executed instead of the "
            "copy that belongs to the repository being operated on. "
            f"Resolved output: {out_payload}"
        )


def test_worktree_step_invocation_is_reached_from_the_workflow_entry_point():
    # covers: ACD-2100a-1
    """AC-4/AC-5: driving the real workflow entry point (not importing a helper)
    produces the authoring worktree on disk under the target repository with the
    expected ac-authoring/* branch checked out, and the run's own recorded
    command string names an absolute location inside that repository rather
    than a location relative to the working directory.
    """
    with tempfile.TemporaryDirectory(prefix="acd2100a1_reach_") as tmp:
        fixture = _make_fixture(Path(tmp), with_repo_copy=True)
        payload = _run_plan_feature_real(
            fixture["parent_dir"],
            label_responses={_PERMISSION_LABEL: _permission_label_response()},
            args={},
        )
        setup_calls = _setup_calls(payload)
        assert setup_calls, (
            f"No '{_SETUP_LABEL}' agent() dispatch was captured. "
            f"calls={payload.get('calls')}"
        )

        prompt = setup_calls[0].get("prompt")
        assert isinstance(prompt, str), f"Expected a string prompt, got: {prompt!r}"
        m = _CMD_LINE_RE.search(prompt)
        assert m is not None, (
            f"Could not find a shell command line in the dispatched prompt: {prompt!r}"
        )
        command_line = m.group(1)

        repo_dir_str = str(fixture["repo_dir"])
        assert repo_dir_str in command_line, (
            "The run's own record of the command it issued must name an absolute "
            f"location inside the target repository ({repo_dir_str!r}); "
            f"got: {command_line!r}"
        )
        assert "{{config.output_root}}" not in command_line, (
            "The recorded command string still carries an unresolved cwd-relative "
            f"placeholder instead of an absolute, repository-anchored path: "
            f"{command_line!r}"
        )
        assert not command_line.strip().startswith(
            f"python {'.leafcutter'}"
        ), (
            "The recorded command string is still a bare cwd-relative path "
            f"(not anchored absolute inside the repository): {command_line!r}"
        )

        real = setup_calls[0].get("real_result")
        assert real is not None, f"worktree-setup prompt did not execute: {setup_calls[0]}"
        assert real.get("exit_code") == 0, f"setup step failed to run: {real}"
        out_payload = json.loads(real.get("output", "{}"))

        worktree_path = Path(out_payload["worktree_path"])
        assert worktree_path.is_dir(), (
            f"Expected the authoring worktree to exist on disk at {worktree_path}, "
            "but it does not."
        )

        branch_result = subprocess.run(
            ["git", "-C", str(worktree_path), "branch", "--show-current"],
            capture_output=True, text=True, check=False,
        )
        branch = branch_result.stdout.strip()
        assert branch.startswith("ac-authoring/"), (
            "Expected the authoring worktree to have an ac-authoring/* branch "
            f"checked out; got branch={branch!r} (stderr={branch_result.stderr!r})"
        )


def test_wrong_copy_execution_is_observable_and_blocks():
    # covers: ACD-2100a-1
    """AC-3 (negative form): with ONLY the untracked-parent copy present and no
    copy inside the target repository, the step fails and names the location it
    could not resolve -- it must NOT silently fall back to running the parent
    copy.
    """
    with tempfile.TemporaryDirectory(prefix="acd2100a1_failure_") as tmp:
        fixture = _make_fixture(Path(tmp), with_repo_copy=False)
        payload = _run_plan_feature_real(
            fixture["parent_dir"],
            label_responses={_PERMISSION_LABEL: _permission_label_response()},
            args={},
        )
        setup_calls = _setup_calls(payload)
        assert setup_calls, (
            f"No '{_SETUP_LABEL}' agent() dispatch was captured. "
            f"calls={payload.get('calls')}"
        )

        real = setup_calls[0].get("real_result")
        assert real is not None, (
            f"worktree-setup prompt did not match the executable pattern: "
            f"{setup_calls[0].get('prompt')!r}"
        )

        ran_parent_copy = False
        if real.get("exit_code") == 0:
            try:
                out_payload = json.loads(real.get("output", ""))
                ran_parent_copy = out_payload.get("source_copy") == "parent"
            except json.JSONDecodeError:
                ran_parent_copy = False

        assert not ran_parent_copy, (
            "The step silently fell back to the untracked-parent copy when no "
            "copy existed inside the target repository, instead of failing and "
            f"naming the unresolved location. Output: {real}"
        )
        assert real.get("exit_code") != 0, (
            "With no copy of the setup step inside the target repository, the "
            f"step must fail (non-zero exit), not silently succeed. Got: {real}"
        )

        diagnostic = (real.get("stderr") or "") + (real.get("output") or "")
        assert str(fixture["repo_dir"]) in diagnostic, (
            "The failure diagnostic (the run's own record) must name the "
            "repository-anchored location it could not resolve, so a wrong-copy "
            f"execution is diagnosable after the fact. Got stderr={real.get('stderr')!r} "
            f"output={real.get('output')!r}"
        )
