"""
MODULE: test_acd_2100b_4
GOAL: Behavioral tests for ACD-2100b-4 -- "Every unresolved outcome of the
    startup check still stops the run before any authoring work begins."

WHAT THIS RECORD GUARDS (KI-ACD-009 / the BO-1500f-1 fail-closed gate): the
    Pre-Stage-0 Workspace-Setup Dispatch Permission Gate in
    templates/workflows-js/plan-feature.js can meet FOUR distinguishable
    unresolved conditions -- a registry it cannot read (ACD-2100b-1), a
    registry it cannot interpret (ACD-2100b-2), a readable registry that does
    not list the workspace-setup agent (ACD-2100b-3), and a readable registry
    that lists that agent but withholds repository-command permission
    (ACD-2100b-3). Each sibling ticket already proved its own report is
    accurate. THIS record proves something different and orthogonal: that
    EVERY ONE of the four conditions still halts -- no authoring agent is
    ever dispatched, no authoring worktree or branch is ever created on
    disk, and none of the four halted runs reports itself as having
    succeeded.

WHY THIS IS A SEPARATE GUARD FROM THE THREE REPORTING RECORDS (test_rationale,
    ACD-2100b-4.yaml): the realistic way this L1 regresses is not a bad
    message -- it is somebody deciding that because three of the four causes
    are not really permission problems, three of the four should be
    downgraded to warnings. That would silently let an authoring agent run
    with an unresolved permission verdict, reintroducing the exact hazard the
    BO-1500f-1 gate was built to close. A guard asserted once, behaviourally,
    across all four conditions in the same place catches that regression
    regardless of which condition's branch was weakened; four independent
    per-sibling tests would not, because a change that weakens ALL FOUR
    identically still passes each sibling's own narrower assertions.

WHY THE ABSENCE OF DISPATCH AND OF A WORKTREE ARE OBSERVED BEHAVIOURALLY, NOT
    BY READING THE SOURCE (it_requirements, ACD-2100b-4.yaml; CLAUDE.md "Gate
    / Workflow ACs -- Verify Behaviorally, Not by Grep"): confirming that a
    `return` statement follows the check in the source text proves nothing
    about whether the check is actually reached at runtime, or about whether
    some other code path independently creates a worktree. This file drives
    the REAL workflow entry point and inspects (a) the run's own record of
    what it dispatched (`payload["calls"]`) for an authoring-agent dispatch,
    and (b) the real git repository on disk, before and after the process
    exits, for a new worktree or branch.

FIXTURE AUTHENTICITY (docs/reference/fixture-policy.md): every registry
    fixture below is produced by `json.dumps(..., indent=2)` -- the SAME
    serializer that would write a real agent_registry.json -- and the
    uninterpretable fixture is a plain string slice of that same serialized
    output (an interrupted write), never a hand-typed broken literal.

HOW THE REAL SIDE EFFECT IS EXERCISED (Real-Artifact Behavioral Test
    Mandate): this file's harness (`_run_plan_feature_real`) is a
    self-contained copy of the harness already used by
    test_acd_2100b_1.py / test_acd_2100b_2.py / test_acd_2100b_3.py (per
    those files' own convention of not depending on
    _workflow_engine_harness.py's private internals). It ACTUALLY EXECUTES
    every "Run the following command ...:\\n<cmd>\\nReturn JSON: ..." agent()
    dispatch via a real Node child_process, against a REAL git repository on
    disk -- never a mocked agent() that stubs the answer without running the
    shell command. The worktree/branch check inspects that same real git
    repository with real `git worktree list` / `git branch --list` calls
    before and after the run.

TDD note: templates/workflows-js/plan-feature.js's four halt branches
    (lines ~2291-2422) already exist from ACD-2100b-1/-2/-3/-3-i. This ticket
    is the REGRESSION GUARD -- see the module docstring above for why it is a
    distinct behaviour rather than a restatement of the three sibling
    reporting tests. If any of the four conditions below is ever weakened to
    a warning, or made to fall through to the worktree-setup dispatch, or
    made to report `status: "ok"`, this file's tests turn red.

TICKET: 11_TICKET-20260826-ACD-2100b-4.md
AC: ACD-2100b-4
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PLAN_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"

_TIMEOUT = 40  # seconds; includes real git I/O.

# The startup check's own registry-read dispatch -- its presence proves the
# check was actually reached (all four conditions read the registry first).
_REGISTRY_READ_LABEL = "resolve-workspace-setup-permission"

# The two labels that only ever fire AFTER the permission gate resolves a
# permitted verdict. Neither may appear in any of the four halted runs.
_SCRIPT_RESOLVE_LABEL = "resolve-worktree-setup-script-path"
_WORKTREE_SETUP_LABEL = "worktree-setup"
_DOWNSTREAM_LABELS = (_SCRIPT_RESOLVE_LABEL, _WORKTREE_SETUP_LABEL)

# A distinctive, low-collision probe id for the workspace-setup agent this
# check resolves -- passed via args.workspace_setup_agent so "no authoring
# agent dispatched" is proven against the VALUE THE CHECK RESOLVED rather
# than a hardcoded literal such as the real default "worktree-agent".
_PROBE_AGENT_ID = "vh3k_probe_authoring_agent_29rp"

# --- The four registry fixtures, one per Given condition -------------------
#
# Each is the REAL serializer's output (json.dumps, indent=2 -- the same
# serializer a real agent_registry.json write would use), never a hand-typed
# literal (docs/reference/fixture-policy.md).

_FULL_REGISTRY_JSON = json.dumps(
    {"agents": [{"id": _PROBE_AGENT_ID, "permits_shell": True}]}, indent=2
)
# Condition 2: readable, but its contents cannot be interpreted -- a plain
# string slice of the real serialized output (simulating an interrupted
# write), never a hand-typed broken literal.
_UNINTERPRETABLE_REGISTRY_JSON = _FULL_REGISTRY_JSON[: len(_FULL_REGISTRY_JSON) // 2]

# Condition 3: readable and interpretable, but does not list the probe agent.
_AGENT_ABSENT_REGISTRY_JSON = json.dumps(
    {"agents": [{"id": "unrelated-other-agent-8h2z", "permits_shell": True}]},
    indent=2,
)

# Condition 4: readable and interpretable, lists the probe agent, but
# withholds repository-command permission.
_AGENT_DENIED_REGISTRY_JSON = json.dumps(
    {"agents": [{"id": _PROBE_AGENT_ID, "permits_shell": False}]}, indent=2
)

# name -> registry_content ("None" means: no file at all, i.e. unreadable).
_CONDITIONS: tuple[tuple[str, str | None], ...] = (
    ("unreadable", None),
    ("uninterpretable", _UNINTERPRETABLE_REGISTRY_JSON),
    ("agent_absent", _AGENT_ABSENT_REGISTRY_JSON),
    ("agent_denied", _AGENT_DENIED_REGISTRY_JSON),
)


def _make_repo_fixture(tmp_path: Path, *, registry_content: str | None) -> Path:
    """Build the Given: a REAL git repository ("the project") whose agent
    registry either does not exist at all (`registry_content is None`) or
    holds `registry_content` verbatim.

    Layout:
        tmp_path/project/                                    <- real git repo
          .leafcutter/config/agent_registry.json               <- iff registry_content is not None
    """
    repo_dir = tmp_path / "project"
    repo_dir.mkdir(parents=True)
    subprocess.run(
        ["git", "init", "-b", "main", str(repo_dir)],
        check=True, capture_output=True, text=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_dir), "config", "user.email", "test@example.com"],
        check=True, capture_output=True, text=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_dir), "config", "user.name", "Test"],
        check=True, capture_output=True, text=True,
    )
    (repo_dir / "README.md").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo_dir), "add", "README.md"], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(repo_dir), "commit", "-m", "seed"], check=True, capture_output=True, text=True)

    if registry_content is not None:
        registry_path = repo_dir / ".leafcutter" / "config" / "agent_registry.json"
        registry_path.parent.mkdir(parents=True)
        registry_path.write_text(registry_content, encoding="utf-8")

    return repo_dir


# ---------------------------------------------------------------------------
# The real-execution harness (self-contained copy of the equivalent harness in
# test_acd_2100b_1.py / test_acd_2100b_2.py / test_acd_2100b_3.py, per those
# files' own convention of not depending on _workflow_engine_harness.py's
# private internals).
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
        mode="w", suffix=".js", prefix="acd_2100b4_", delete=False, encoding="utf-8"
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


def _calls_with_agent_type(payload: dict, agent_type: str) -> list:
    calls = payload.get("calls", [])
    return [
        c for c in calls
        if isinstance(c.get("opts"), dict) and c["opts"].get("agentType") == agent_type
    ]


def _combined_report_text(payload: dict) -> str:
    """Everything a human operator could plausibly read after this run: the
    final structured result's message, PLUS the text of every agent() prompt
    dispatched as a reporting/halt step (mirrors test_acd_2100b_1.py's /
    test_acd_2100b_2.py's / test_acd_2100b_3.py's own convention).
    """
    parts: list[str] = []
    result = payload.get("result")
    if isinstance(result, dict):
        parts.append(json.dumps(result))
    for call in payload.get("calls", []):
        prompt = call.get("prompt")
        if isinstance(prompt, str):
            parts.append(prompt)
        elif isinstance(prompt, dict):
            parts.append(json.dumps(prompt))
    parts.append(payload.get("_stderr") or "")
    return "\n".join(parts)


def _git_worktree_snapshot(repo_dir: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_dir), "worktree", "list", "--porcelain"],
        check=True, capture_output=True, text=True,
    )
    return result.stdout


def _git_branch_snapshot(repo_dir: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_dir), "branch", "--list", "--all"],
        check=True, capture_output=True, text=True,
    )
    return result.stdout


def _fs_snapshot(tmp_root: Path) -> list:
    """A relative-path listing of everything under `tmp_root` on disk --
    used to prove no NEW directory or file (an authoring worktree, in
    particular) appears as a side effect of the run.
    """
    return sorted(
        p.relative_to(tmp_root).as_posix() for p in tmp_root.rglob("*")
    )


def _run_condition(tmp_root: Path, registry_content: str | None) -> dict:
    """Build the Given for one of the four conditions, run the REAL workflow
    entry point against it, and capture the run's own dispatch record PLUS
    the real git repository's worktree/branch/filesystem state before and
    after the run exits.
    """
    repo_dir = _make_repo_fixture(tmp_root, registry_content=registry_content)

    worktree_before = _git_worktree_snapshot(repo_dir)
    branch_before = _git_branch_snapshot(repo_dir)
    tree_before = _fs_snapshot(tmp_root)

    payload = _run_plan_feature_real(
        repo_dir, label_responses={}, args={"workspace_setup_agent": _PROBE_AGENT_ID}
    )

    worktree_after = _git_worktree_snapshot(repo_dir)
    branch_after = _git_branch_snapshot(repo_dir)
    tree_after = _fs_snapshot(tmp_root)

    return {
        "payload": payload,
        "repo_dir": repo_dir,
        "worktree_before": worktree_before,
        "worktree_after": worktree_after,
        "branch_before": branch_before,
        "branch_after": branch_after,
        "tree_before": tree_before,
        "tree_after": tree_after,
    }


# Phrases that would state the RUN itself succeeded -- distinct from
# incidental use of the word "success"/"successfully" describing a
# sub-step (e.g. "the registry was read successfully"), which the
# uninterpretable-registry report legitimately contains.
_RUN_SUCCEEDED_PHRASES = (
    "run completed successfully",
    "workflow succeeded",
    "workflow completed successfully",
    "plan-feature completed",
    "run succeeded",
)


class TestFourStartupCheckConditionsAlwaysHalt(unittest.TestCase):

    def test_all_four_startup_check_conditions_stop_the_run_at_the_check(self):
        # covers: ACD-2100b-4
        # angle: criterion
        """AC-1: driving the real workflow entry point with each of the four
        Given conditions in turn, every run stops at the startup check -- the
        check's own registry-read dispatch runs (proving the check was
        reached), no step after the check runs, and the run's own returned
        result reflects a halt.
        """
        for name, registry_content in _CONDITIONS:
            with self.subTest(condition=name):
                with tempfile.TemporaryDirectory(prefix=f"acd2100b4_{name}_") as tmp:
                    outcome = _run_condition(Path(tmp), registry_content)
                    payload = outcome["payload"]

                    registry_read_calls = _calls_with_label(payload, _REGISTRY_READ_LABEL)
                    self.assertTrue(
                        registry_read_calls,
                        f"[{name}] the startup check's own registry-read dispatch never "
                        f"ran -- cannot prove the check executed at all. "
                        f"calls={payload.get('calls')}",
                    )

                    downstream_calls = _calls_with_any_label(payload, _DOWNSTREAM_LABELS)
                    self.assertFalse(
                        downstream_calls,
                        f"[{name}] a step after the startup check ran "
                        f"(labels={_DOWNSTREAM_LABELS}), but the run must stop at the "
                        f"check. calls={payload.get('calls')}",
                    )

                    result = payload.get("result")
                    self.assertIsInstance(
                        result, dict,
                        f"[{name}] expected a structured halt result, got: {result!r}",
                    )
                    self.assertNotEqual(
                        (result or {}).get("status"), "ok",
                        f"[{name}] the run did not stop at the check. result={result!r}",
                    )

    def test_no_authoring_agent_is_dispatched_in_any_halted_run(self):
        # covers: ACD-2100b-4
        # angle: reachability
        """AC-2: for each of the four runs, the run's OWN record of what it
        dispatched (observed from `payload["calls"]`, not inferred from the
        workflow source) contains no dispatch to the authoring/workspace-
        setup agent -- neither by its resolved agentType nor by the
        worktree-setup label it would have been dispatched under.
        """
        for name, registry_content in _CONDITIONS:
            with self.subTest(condition=name):
                with tempfile.TemporaryDirectory(prefix=f"acd2100b4_{name}_") as tmp:
                    outcome = _run_condition(Path(tmp), registry_content)
                    payload = outcome["payload"]

                    authoring_agent_calls = _calls_with_agent_type(payload, _PROBE_AGENT_ID)
                    self.assertFalse(
                        authoring_agent_calls,
                        f"[{name}] the run's own dispatch record contains a call to the "
                        f"authoring agent ({_PROBE_AGENT_ID!r}), but this condition must "
                        f"halt before any authoring agent is dispatched. "
                        f"calls={payload.get('calls')}",
                    )

                    worktree_setup_calls = _calls_with_label(payload, _WORKTREE_SETUP_LABEL)
                    self.assertFalse(
                        worktree_setup_calls,
                        f"[{name}] the run's own dispatch record contains a "
                        f"'{_WORKTREE_SETUP_LABEL}' dispatch, which is reserved for the "
                        f"authoring worktree bootstrap. calls={payload.get('calls')}",
                    )

    def test_no_authoring_worktree_or_branch_exists_after_any_halted_run(self):
        # covers: ACD-2100b-4
        # angle: failure
        """AC-3: after each of the four real processes exits, the real git
        repository on disk holds no NEW worktree and no NEW branch, and no
        new directory or file appears anywhere under the project's parent
        directory -- observed from the filesystem itself, not from the
        workflow's own report.
        """
        for name, registry_content in _CONDITIONS:
            with self.subTest(condition=name):
                with tempfile.TemporaryDirectory(prefix=f"acd2100b4_{name}_") as tmp:
                    outcome = _run_condition(Path(tmp), registry_content)

                    self.assertEqual(
                        outcome["worktree_before"], outcome["worktree_after"],
                        f"[{name}] `git worktree list` differs before vs. after the run "
                        f"-- a worktree was created even though the run must halt before "
                        f"any authoring worktree is bootstrapped.\n"
                        f"before={outcome['worktree_before']!r}\n"
                        f"after={outcome['worktree_after']!r}",
                    )
                    self.assertEqual(
                        outcome["branch_before"], outcome["branch_after"],
                        f"[{name}] `git branch --list --all` differs before vs. after the "
                        f"run -- a branch was created even though the run must halt "
                        f"before any authoring branch is created.\n"
                        f"before={outcome['branch_before']!r}\n"
                        f"after={outcome['branch_after']!r}",
                    )
                    self.assertEqual(
                        outcome["tree_before"], outcome["tree_after"],
                        f"[{name}] the filesystem under the project's parent directory "
                        f"differs before vs. after the run -- something was created on "
                        f"disk even though this condition must halt before any "
                        f"authoring workspace setup step runs.\n"
                        f"before={outcome['tree_before']!r}\n"
                        f"after={outcome['tree_after']!r}",
                    )
                    for entry in outcome["tree_after"]:
                        self.assertNotIn(
                            "ac-authoring", entry,
                            f"[{name}] an 'ac-authoring' path component appears on disk "
                            f"after the run ({entry!r}), but this condition must halt "
                            f"before any authoring worktree/branch is created.",
                        )

    def test_no_halted_run_reports_itself_as_having_succeeded(self):
        # covers: ACD-2100b-4
        # angle: criterion
        """AC-4: each of the four runs' own returned result records an
        outcome that says the run did not proceed -- its `status` field is
        never the success value the real success path uses ("ok"), and no
        run's combined report claims the run itself (as opposed to a
        sub-step within it) completed or succeeded.
        """
        for name, registry_content in _CONDITIONS:
            with self.subTest(condition=name):
                with tempfile.TemporaryDirectory(prefix=f"acd2100b4_{name}_") as tmp:
                    outcome = _run_condition(Path(tmp), registry_content)
                    payload = outcome["payload"]
                    result = payload.get("result")

                    self.assertIsInstance(
                        result, dict,
                        f"[{name}] expected a structured, CONSUMED (returned) halt "
                        f"result, got: {result!r}",
                    )
                    self.assertNotEqual(
                        (result or {}).get("status"), "ok",
                        f"[{name}] the halted run's own returned result reports the "
                        f"success status. result={result!r}",
                    )

                    report_lower = _combined_report_text(payload).lower()
                    for phrase in _RUN_SUCCEEDED_PHRASES:
                        self.assertNotIn(
                            phrase, report_lower,
                            f"[{name}] the halted run's report claims the run itself "
                            f"succeeded ({phrase!r} found). report={report_lower!r}",
                        )


if __name__ == "__main__":
    unittest.main()
