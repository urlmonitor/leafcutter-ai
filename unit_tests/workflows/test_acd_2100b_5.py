"""
MODULE: test_acd_2100b_5
GOAL: Behavioral tests for ACD-2100b-5 -- "The startup check reads the registry
    itself instead of asking an agent to read it" -- WORKFLOW-LEVEL half.

    This file covers the test_spec entries whose `target_dir` is
    `unit_tests/workflows/`: templates/workflows-js/plan-feature.js's Stage-0
    consumption of a pre-flight verdict. The companion SCRIPT-level tests
    (the pre-flight itself, run as a real subprocess) live in
    unit_tests/ac_driven_dev/test_acd_2100b_5.py.

SURFACE CHANGE (read before touching this file, or test_acd_2100b_1/2/3/4.py):
    ACD-2100b-5's own AC YAML (docs/acceptance-criteria/ac-driven-dev/
    ACD-2100-entry-point-unblocked/ACD-2100b-5.yaml) was amended in place on
    2026-09-07 after a prior build attempt on this exact ticket ran aground:
    the E2 engine (ADR-030) contextifies the workflow body with EXACTLY
    agent, parallel, pipeline, phase, log, args, workflow, budget -- no
    module loader, no filesystem primitive of any kind (canonical statement:
    unit_tests/_workflow_engine_harness.py docstring, "ENGINE FIDELITY"
    section). So "the check reads the registry itself" cannot be implemented
    INSIDE plan-feature.js's own sandboxed body -- the read must happen in a
    real script the plan-feature SKILL invokes BEFORE the workflow starts
    (the skill runs in the main agent loop, with real Bash/Read access), and
    the resulting verdict crosses into the workflow through `args` -- the
    ONLY injected global that carries caller-supplied data (it_requirements).

    A PRIOR version of this exact file existed under the PRE-amendment design
    (asserting the workflow itself could distinguish registry states with an
    empty `args={}` and a live git repository on `cwd` -- which is
    unimplementable under the sandboxed engine and was never a legitimate
    target). That file is superseded by this one (Source-of-Truth Discipline
    Rule 1: production_drift -- the AC's own surface moved out from under the
    prior test's assumptions; Rule 4 -- no production code has landed yet
    under either design, so there is nothing to split into a separate
    production-change commit).

CONTRACT THIS FILE PINS (mirrors unit_tests/ac_driven_dev/test_acd_2100b_5.py
    exactly -- see that file's module docstring for the full script-side
    contract):

    args key:  `args.workspace_setup_permission` -- the skill passes the
               pre-flight script's own stdout JSON through, VERBATIM, as this
               args value when it invokes the workflow. Shape (at minimum):
                 { "permits": bool, "outcome": <str>, ... }
               ABSENT (no such key in args at all) stands in for a caller
               that invokes the deployed workflow directly, e.g.
               `Workflow({scriptPath: '.leafcutter/workflows/plan-feature.js'})`,
               bypassing the skill's pre-flight entirely (it_requirements:
               "a real and currently-used invocation path").
    Guard:     the workflow must fail closed (halt before any authoring
               agent is dispatched) whenever `args.workspace_setup_permission`
               is absent, not an object, or has `permits !== true` --  and
               it must never make ANY agent() dispatch on the check's own
               behalf (no label resembling the old
               "resolve-workspace-setup-permission" dispatch, and no prompt
               that reads config/agent_registry.json).
    Next step: the pre-existing dispatch immediately after the removed gate
               -- label "resolve-worktree-setup-script-path" -- is the
               observable proof that the run proceeded PAST the check. This
               label is untouched by this AC (it belongs to the
               already-implemented ACD-2100a-1 resolution step) and remains
               the correct "did the run get past Stage 0's gate" probe.

HOW THE REAL SIDE EFFECT IS EXERCISED (Real-Artifact Behavioral Test
    Mandate): every test below drives the REAL, on-disk
    templates/workflows-js/plan-feature.js top-level body via a real Node
    subprocess -- never a hand-typed stand-in for its logic. The
    failure-angle test additionally sources its denying verdict from a REAL
    run of the REAL pre-flight script (scripts/worktree/
    check_workspace_setup_permission.py) against a REAL, on-disk registry, so
    the exact shape python-coder's script actually emits is what the
    workflow is tested against -- never a hand-typed guess at that shape.

WHY THIS CANNOT BE PROVEN BY A SOURCE SCAN: a test that greps for the absence
    of the old dispatch label passes on a fix that keeps a dispatching helper
    in the file for another caller while never calling it here, and fails on
    a correct fix that renames the label. The evidence has to be the RUN'S
    OWN DISPATCH RECORD, read back after actually executing the workflow.

TDD note: templates/workflows-js/plan-feature.js still dispatches an agent()
    call (label "resolve-workspace-setup-permission") to read the registry,
    and has no `args.workspace_setup_permission` handling at all. Every test
    below is expected to be RED until python-coder replaces that dispatch
    with the args-sourced, fail-closed guard described above.

TICKET: 12_TICKET-20260826-ACD-2100b-5.md
AC: ACD-2100b-5
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PLAN_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"
_PREFLIGHT_SCRIPT = (
    _WORKTREE_ROOT / "scripts" / "worktree" / "check_workspace_setup_permission.py"
)

_TIMEOUT = 40  # seconds; includes real git I/O and (for the real harness) real shell I/O.

# Labels this file cares about, taken verbatim from plan-feature.js's own
# agent() call sites around the Pre-Stage-0 Workspace-Setup Dispatch
# Permission Gate and the step immediately after it.
_REGISTRY_READ_LABEL = "resolve-workspace-setup-permission"
_NEXT_STEP_LABEL = "resolve-worktree-setup-script-path"

_DEFAULT_AGENT_ID = "worktree-agent"
_ARGS_VERDICT_KEY = "workspace_setup_permission"


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, check=True, capture_output=True, text=True
    )


def _make_registry_repo(tmp_path: Path, *, agents: list[dict] | None) -> Path:
    """Build a REAL git repository whose `.leafcutter/config/agent_registry.json`
    is a REAL, on-disk file produced by `json.dumps` -- never a hand-typed
    JSON literal (Fixture Authenticity Rule, 2h.2).
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
    registry_path.write_text(
        json.dumps({"agents": agents if agents is not None else []}),
        encoding="utf-8",
    )
    return repo_dir


def _real_preflight_verdict(repo_dir: Path, agent_id: str = _DEFAULT_AGENT_ID) -> dict:
    """Run the REAL pre-flight script (not a hand-typed stand-in for its
    output shape) against `repo_dir` and return its parsed verdict.

    Fails LOUD (never skips) if the script does not exist yet. A skip here
    would let this file's own failure-angle test go green-by-absence (a skip
    is not a failure) while the script itself is still covered as red by
    unit_tests/ac_driven_dev/test_acd_2100b_5.py -- the "one-red-rule"
    (project memory: XFAIL/skip must never quietly stand in for red, or the
    TDD gate is vacuous). This helper's job is only to source a REAL denying
    verdict once the script exists; until then, this workflow-level test
    must itself show red.
    """
    if not _PREFLIGHT_SCRIPT.is_file():
        raise AssertionError(
            f"Pre-flight script does not exist yet at {_PREFLIGHT_SCRIPT}. "
            "AC ACD-2100b-5 requires scripts/worktree/"
            "check_workspace_setup_permission.py to exist as a real, "
            "executable pre-flight (see unit_tests/ac_driven_dev/"
            "test_acd_2100b_5.py for the script-level coverage)."
        )
    proc = subprocess.run(
        [sys.executable, str(_PREFLIGHT_SCRIPT), "--agent-id", agent_id],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
    )
    if not proc.stdout.strip():
        raise AssertionError(
            "Pre-flight script produced no stdout.\n"
            f"returncode={proc.returncode}\nstderr={proc.stderr[:2000]!r}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"Pre-flight script produced non-JSON stdout: {exc}\n"
            f"stdout={proc.stdout[:2000]!r}"
        ) from exc


def _strip_exports(source: str) -> str:
    """Minimal ESM `export` stripper (self-contained copy; see sibling files
    test_acd_2100b_1.py / test_acd_2100a_3.py for the same convention).
    """
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


# ---------------------------------------------------------------------------
# Shared shim boilerplate (parallel/pipeline/phase/log/workflow/budget/args),
# self-contained copies of the equivalent harness scaffolding in
# test_acd_2100b_1.py / test_acd_2100a_3.py.
# ---------------------------------------------------------------------------

_SHIM_BOILERPLATE = r"""
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

# Blocked variant: EVERY agent() call is recorded (so we can still see what
# the run attempted) and then IMMEDIATELY throws a simulated transport
# error -- the literal Given "no agent can be dispatched -- every dispatch
# attempt fails immediately with a transport error". Nothing is ever
# actually executed via child_process in this variant.
_BLOCKED_SHIM_TEMPLATE = (
    r"""
'use strict';

const __capturedCalls__ = [];

async function agent(promptOrOpts, opts) {
  __capturedCalls__.push({ prompt: promptOrOpts, opts: opts || null });
  throw new Error(
    'TRANSPORT_ERROR: dispatch unavailable (simulated for ACD-2100b-5 test)'
  );
}
"""
    + _SHIM_BOILERPLATE
)

# Real-dispatch variant: agent() ACTUALLY EXECUTES every "Run the following
# command ...:\n<cmd>\n" dispatch via a real Node child_process against the
# given real `cwd`, and returns canned `label_responses` for labels present
# in that map -- a self-contained copy of the harness used throughout
# test_acd_2100b_1.py / test_acd_2100a_3.py.
_REAL_SHIM_TEMPLATE = (
    r"""
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
"""
    + _SHIM_BOILERPLATE
)


def _run_shim(shim_source: str, prefix: str) -> dict:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".js", prefix=prefix, delete=False, encoding="utf-8"
    ) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write(shim_source)

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


def _run_plan_feature_blocked(args: dict) -> dict:
    """Drive the REAL plan-feature.js top-level body with dispatch made
    completely impossible: every agent() call is recorded and then
    immediately throws a simulated transport error.
    """
    source = _PLAN_FEATURE_JS.read_text(encoding="utf-8")
    body = _strip_exports(source)
    shim = (
        _BLOCKED_SHIM_TEMPLATE
        .replace("__ARGS_JSON__", json.dumps(args))
        .replace("__SCRIPT_BODY__", body)
    )
    return _run_shim(shim, "acd_2100b5_blocked_")


def _run_plan_feature_real(cwd: Path, label_responses: dict, args: dict) -> dict:
    """Drive the REAL plan-feature.js top-level body with dispatch AVAILABLE:
    every "Run the following command ...:\\n<cmd>\\n" dispatch is ACTUALLY
    EXECUTED via a real Node child_process against `cwd`.
    """
    source = _PLAN_FEATURE_JS.read_text(encoding="utf-8")
    body = _strip_exports(source)
    shim = (
        _REAL_SHIM_TEMPLATE
        .replace("__RUN_CWD_JSON__", json.dumps(str(cwd)))
        .replace("__LABEL_RESPONSES_JSON__", json.dumps(label_responses))
        .replace("__ARGS_JSON__", json.dumps(args))
        .replace("__SCRIPT_BODY__", body)
    )
    return _run_shim(shim, "acd_2100b5_real_")


def _calls_with_label(payload: dict, label: str) -> list:
    calls = payload.get("calls", [])
    return [
        c for c in calls
        if isinstance(c.get("opts"), dict) and c["opts"].get("label") == label
    ]


def _prompts_mentioning_registry(payload: dict) -> list:
    """Every captured call whose prompt text references the registry file --
    the second half of AC-3's observability requirement: "none whose prompt
    reads the registry", independent of what label (if any) the call carries.
    """
    hits = []
    for call in payload.get("calls", []):
        prompt = call.get("prompt")
        text = prompt if isinstance(prompt, str) else json.dumps(prompt)
        if "agent_registry.json" in text:
            hits.append(call)
    return hits


def _report_text(payload: dict) -> str:
    """Everything a human operator could plausibly read after this run: the
    final structured result's message (if any), any top-level error, plus
    stderr.
    """
    parts: list[str] = []
    result = payload.get("result")
    if isinstance(result, dict):
        parts.append(json.dumps(result))
    if payload.get("error"):
        parts.append(str(payload.get("error")))
    parts.append(payload.get("_stderr") or "")
    return "\n".join(parts)


_PERMITTED_VERDICT = {"permits": True, "outcome": "granted"}


class TestStartupCheckConsumesPreflightVerdictFromArgs(unittest.TestCase):

    def test_run_reaches_and_passes_the_startup_check_with_every_dispatch_attempt_failing(self):
        # covers: ACD-2100b-5
        # angle: criterion
        """AC-1/AC-2: with every dispatch attempt failing immediately with a
        transport error, and the permitted verdict the pre-flight would have
        produced supplied via args, the check must complete with the
        permitted verdict and the run must proceed to the NEXT real step (a
        dispatch attempt for resolving the worktree-setup script path) --
        not halt at the permission check itself.
        """
        args = {_ARGS_VERDICT_KEY: dict(_PERMITTED_VERDICT)}
        payload = _run_plan_feature_blocked(args=args)

        registry_dispatch_calls = _calls_with_label(payload, _REGISTRY_READ_LABEL)
        self.assertFalse(
            registry_dispatch_calls,
            "The check attempted a dispatch to read the registry "
            f"(label={_REGISTRY_READ_LABEL!r}) even though a pre-flight "
            f"verdict was already supplied via args. calls={payload.get('calls')}",
        )

        next_step_calls = _calls_with_label(payload, _NEXT_STEP_LABEL)
        self.assertTrue(
            next_step_calls,
            "The run never attempted the step after the permission check "
            f"({_NEXT_STEP_LABEL!r} was never dispatched) -- the check's "
            "permitted verdict (supplied via args) was not consumed in "
            f"control flow. calls={payload.get('calls')}",
        )

    def test_no_dispatch_is_made_on_the_checks_behalf_during_a_run(self):
        # covers: ACD-2100b-5
        # angle: reachability
        """AC-3: driving the REAL workflow (via a real Node subprocess, with
        dispatch AVAILABLE this time) and reading back the run's OWN dispatch
        record afterwards -- not scanning the source -- shows no call
        attributable to the permission check's former registry-read dispatch
        (neither by label nor by prompt content), while the run still
        demonstrably reaches (and its verdict is CONSUMED by) the next real
        step.
        """
        with tempfile.TemporaryDirectory(prefix="acd2100b5_reachability_") as tmp:
            repo_dir = _make_registry_repo(
                Path(tmp),
                agents=[{"id": _DEFAULT_AGENT_ID, "permits_shell": True}],
            )
            args = {_ARGS_VERDICT_KEY: dict(_PERMITTED_VERDICT)}
            payload = _run_plan_feature_real(repo_dir, label_responses={}, args=args)

            registry_dispatch_calls = _calls_with_label(payload, _REGISTRY_READ_LABEL)
            self.assertFalse(
                registry_dispatch_calls,
                "The run's own dispatch record contains a call attributable "
                f"to the permission check (label={_REGISTRY_READ_LABEL!r}), "
                "but the check must be a local read, never a dispatch. "
                f"calls={payload.get('calls')}",
            )

            registry_prompt_calls = _prompts_mentioning_registry(payload)
            self.assertFalse(
                registry_prompt_calls,
                "The run's own dispatch record contains a call whose prompt "
                "mentions agent_registry.json -- no dispatch may be made on "
                f"the check's behalf, under any label. calls={payload.get('calls')}",
            )

            next_step_calls = _calls_with_label(payload, _NEXT_STEP_LABEL)
            self.assertTrue(
                next_step_calls,
                "The run never reached the step after the permission check "
                f"-- its verdict was never consumed to advance control flow. "
                f"calls={payload.get('calls')}",
            )

    def test_withheld_permission_still_halts_the_run(self):
        # covers: ACD-2100b-5
        # angle: failure
        """AC-2: the run still stops at the check before any authoring agent
        is dispatched, even with dispatch impossible, when the pre-flight
        verdict supplied via args is a real DENYING verdict produced by the
        real pre-flight script against a registry that withholds permission
        (the workspace-setup agent is not listed at all). The local read is
        not a bypass: a fix that unconditionally reports permitted (or
        defaults to permitted whenever the caller-supplied verdict looks
        unfamiliar) must fail this test.
        """
        with tempfile.TemporaryDirectory(prefix="acd2100b5_denying_registry_") as tmp:
            repo_dir = _make_registry_repo(
                Path(tmp),
                agents=[{"id": "some-other-agent", "permits_shell": True}],
            )
            denying_verdict = _real_preflight_verdict(repo_dir)

        self.assertIsNot(
            denying_verdict.get("permits"),
            True,
            "Test construction error: the real pre-flight did not deny a "
            f"registry that does not list '{_DEFAULT_AGENT_ID}' at all. "
            f"verdict={denying_verdict!r}",
        )

        args = {_ARGS_VERDICT_KEY: denying_verdict}
        payload = _run_plan_feature_blocked(args=args)

        next_step_calls = _calls_with_label(payload, _NEXT_STEP_LABEL)
        self.assertFalse(
            next_step_calls,
            "The run proceeded past the permission check "
            f"({_NEXT_STEP_LABEL!r} was dispatched) even though the "
            "pre-flight verdict supplied via args denies the agent -- "
            f"the local read must not be a bypass. calls={payload.get('calls')}",
        )

        result = payload.get("result")
        self.assertIsInstance(
            result,
            dict,
            "The run did not return a structured error result when the "
            f"pre-flight verdict denies permission. payload={payload!r}",
        )
        self.assertEqual(
            result.get("status"),
            "error",
            f"Expected status='error' when permission is withheld. result={result!r}",
        )

    def test_direct_workflow_invocation_with_no_preflight_verdict_halts(self):
        # covers: ACD-2100b-5
        # angle: failure
        """AC-2/AC-4 (fail-closed extension): a caller that invokes the
        workflow directly -- e.g. Workflow({scriptPath:
        '.leafcutter/workflows/plan-feature.js'}) -- supplies NO
        `args.workspace_setup_permission` at all. Moving the check out of the
        workflow body and into the skill's pre-flight must not leave this
        path unguarded: the run must halt before any authoring agent is
        dispatched, and the report must name the MISSING pre-flight -- never
        assert a permission cause the run never established (that would
        misdirect an operator into editing a registry entry that was never
        even consulted).
        """
        with tempfile.TemporaryDirectory(prefix="acd2100b5_direct_invocation_") as tmp:
            repo_dir = _make_registry_repo(
                Path(tmp),
                agents=[{"id": _DEFAULT_AGENT_ID, "permits_shell": True}],
            )
            # No `workspace_setup_permission` key in args at all -- standing
            # in for a caller that bypasses the skill's pre-flight entirely.
            payload = _run_plan_feature_real(repo_dir, label_responses={}, args={})

        next_step_calls = _calls_with_label(payload, _NEXT_STEP_LABEL)
        self.assertFalse(
            next_step_calls,
            "The run proceeded past the permission check "
            f"({_NEXT_STEP_LABEL!r} was dispatched) even though NO "
            "pre-flight verdict was supplied via args at all -- a direct "
            "workflow invocation must not be able to bypass the check. "
            f"calls={payload.get('calls')}",
        )

        registry_dispatch_calls = _calls_with_label(payload, _REGISTRY_READ_LABEL)
        self.assertFalse(
            registry_dispatch_calls,
            "With no pre-flight verdict supplied, the workflow fell back to "
            "dispatching an agent to read the registry itself -- this AC "
            "requires the workflow to halt on the missing verdict, never to "
            f"recover by dispatching. calls={payload.get('calls')}",
        )

        report = _report_text(payload).lower()
        self.assertIn(
            "pre-flight",
            report,
            "The halt report does not name the missing pre-flight at all -- "
            "it must not assert a permission cause the run never "
            f"established. report={report!r}",
        )
        forbidden_permission_claims = ("permits_shell", "does not permit", "is not permitted")
        self.assertFalse(
            any(marker in report for marker in forbidden_permission_claims),
            "The halt report asserts a permission verdict "
            f"({[m for m in forbidden_permission_claims if m in report]!r}) "
            "even though no pre-flight verdict ever reached the workflow -- "
            f"no permission fact was ever established. report={report!r}",
        )

    def test_harness_default_still_permits_pre_existing_plan_feature_callers_to_proceed(self):
        # covers: ACD-2100b-5
        # angle: criterion
        """Regression guard for the shared `_workflow_engine_harness.py`:
        dozens of OTHER tests drive plan-feature.js via
        `run_workflow_under_e2()` for reasons unrelated to this AC (triage,
        the Product-Truth phase, orphan recovery, etc.) without knowing
        anything about the new args-sourced permission gate. If removing the
        old dispatch-based gate (which the harness used to satisfy via a
        script-specific `label_responses` default -- see
        `_default_label_responses_for_script()`'s "BO-1500f-1" note) is not
        paired with an equivalent ARGS-shaped default for every caller of
        plan-feature.js, every one of those pre-existing tests silently
        starts failing at Stage 0 the moment this AC lands. This test proves
        the harness supplies a safe default without a caller having to know
        about `args.workspace_setup_permission` explicitly -- mirroring the
        exact hardening pattern the harness module's own docstring already
        documents for this same script.
        """
        unit_tests_dir = _WORKTREE_ROOT / "unit_tests"
        if str(unit_tests_dir) not in sys.path:
            sys.path.insert(0, str(unit_tests_dir))
        from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

        # Deliberately supplies NO `args` override at all -- exactly how
        # every pre-existing, unrelated caller of plan-feature.js already
        # calls this harness today.
        result = run_workflow_under_e2(_PLAN_FEATURE_JS)

        registry_dispatch_calls = [
            c for c in result.agent_calls if c.label == _REGISTRY_READ_LABEL
        ]
        self.assertFalse(
            registry_dispatch_calls,
            "The harness's default run dispatched a call for "
            f"{_REGISTRY_READ_LABEL!r} -- this AC removes that dispatch "
            "entirely; the harness must no longer need to stub it.",
        )

        next_step_calls = [c for c in result.agent_calls if c.label == _NEXT_STEP_LABEL]
        self.assertTrue(
            next_step_calls,
            "A caller of run_workflow_under_e2(plan-feature.js) that "
            "supplies no `args` override at all never got past Stage 0's "
            f"permission gate ({_NEXT_STEP_LABEL!r} was never dispatched). "
            "The harness must supply a safe, real, registry-backed default "
            "for args.workspace_setup_permission so every PRE-EXISTING "
            "caller of this script is unaffected by this AC -- see this "
            "harness's own docstring precedent for "
            "_default_label_responses_for_script()'s 'BO-1500f-1' note, "
            "which solved the equivalent problem for the dispatch-based gate "
            f"this AC removes. dispatch_count={result.dispatch_count} "
            f"error={result.error!r}",
        )


if __name__ == "__main__":
    unittest.main()
