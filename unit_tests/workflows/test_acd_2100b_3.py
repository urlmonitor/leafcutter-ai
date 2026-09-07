"""
MODULE: test_acd_2100b_3
GOAL: Behavioral tests for ACD-2100b-3 -- "An agent missing from the registry
    and an agent denied permission produce different reports."

INCIDENT BEING FIXED (KI-ACD-009, outcome 3 of 4): the Pre-Stage-0
    Workspace-Setup Dispatch Permission Gate in templates/workflows-js/plan-feature.js
    resolves the workspace-setup agent's permission with:

        const entries = (registryJson && Array.isArray(registryJson.agents)) ? registryJson.agents : [];
        const match = entries.find((e) => e && e.id === workspaceSetupAgentId);
        permitsShell = !!(match && match.permits_shell === true);
        ...
        if (!permitsShell) {
          await agent(
            "...that agent's registered charter (config/agent_registry.json) " +
            "does not permit running repository-mutating shell commands. ... " +
            "Fix ... config/agent_registry.json's permits_shell field ...",
            ...
          );
        }

    `entries.find(...)` returns `undefined` both when the agent's entry is
    genuinely absent from the registry AND when it exists with
    `permits_shell: false` -- both collapse to the SAME `permitsShell = false`
    path and the SAME `!permitsShell` report, which asserts a permission cause
    ("Fix ... permits_shell field") that was never established when the agent
    was never even listed. That is false-green-mechanisms M8 one layer down
    from ACD-2100b-2: "the entry is absent" and "the entry is present and
    denies" are two distinct facts about the registry's contents, and only the
    second may be reported as a permission problem.

TDD note: templates/workflows-js/plan-feature.js does not yet distinguish
    these two outcomes -- both currently render the SAME
    permission-mis-assignment report, including its "permits_shell field"
    permission-setting pointer. All tests below are expected to be RED until
    python-coder makes `entries.find(...)` distinguish "entry present and
    denied" from "entry absent" (per this ticket's Delivers-To contract to
    python-coder: a three-state, absence-representable lookup) and renders a
    distinct, permission-setting-free report for the absence case.

FIXTURE AUTHENTICITY (docs/reference/fixture-policy.md): both registries are
    produced by `json.dumps(..., indent=2)` -- the SAME serializer that would
    write a real agent_registry.json -- never a hand-typed literal.

HOW THE REAL SIDE EFFECT IS EXERCISED (Real-Artifact Behavioral Test
    Mandate): mirrors unit_tests/workflows/test_acd_2100b_2.py's
    `_run_plan_feature_real` harness (itself a self-contained copy of
    test_acd_2100a_1.py's / test_acd_2100a_3.py's / test_acd_2100b_1.py's own
    harness, per those files' convention of not depending on
    _workflow_engine_harness.py's private internals). It ACTUALLY EXECUTES
    every "Run the following command ...:\\n<cmd>\\nReturn JSON: ..." agent()
    dispatch via a real Node child_process, against a real git repository and
    a real, on-disk agent registry file -- never a mocked agent() that stubs
    the answer without running the shell command.

TICKET: 09_TICKET-20260826-ACD-2100b-3.md
AC: ACD-2100b-3
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
_REGISTRY_READ_LABEL = "resolve-workspace-setup-permission"
_SETUP_RELATED_LABELS = ("resolve-worktree-setup-script-path", "worktree-setup")

# A distinctive, low-collision probe id for the workspace-setup agent this
# check resolves -- passed via args.workspace_setup_agent so the report is
# proven to name the VALUE THE CHECK RESOLVED rather than a hardcoded literal
# such as the real default "worktree-agent" (Implementation Notes: "taken
# from the value the check actually resolved rather than a literal in the
# message").
_PROBE_AGENT_ID = "zqm7_probe_worktree_agent_44xk"

# The REAL serializer's output (json.dumps, indent=2 -- same serializer a
# real agent_registry.json write would use) for a registry whose `agents`
# array is present and non-empty but does NOT list _PROBE_AGENT_ID at all.
_ABSENT_AGENT_REGISTRY_JSON = json.dumps(
    {"agents": [{"id": "unrelated-other-agent-9f2q", "permits_shell": True}]},
    indent=2,
)

# The REAL serializer's output for a registry that DOES list _PROBE_AGENT_ID,
# but explicitly withholds shell/repository-command permission from it.
_DENIED_AGENT_REGISTRY_JSON = json.dumps(
    {"agents": [{"id": _PROBE_AGENT_ID, "permits_shell": False}]},
    indent=2,
)

# Wording the absence report must contain (AC-1): it must state that the
# agent was not found in the registry.
_NOT_FOUND_PHRASES = (
    "not found in the registry",
    "not listed in the registry",
    "is not in the registry",
    "not present in the registry",
)

# Wording the denial report must contain (AC-2): it must state the agent IS
# listed, and is not permitted to run repository commands.
_LISTED_PHRASES = (
    "is listed",
    "listed in the registry",
    "found in the registry",
)
_NOT_PERMITTED_PHRASES = (
    "does not permit",
    "not permitted",
    "denies",
    "denied",
)

# A pointer at a specific permission SETTING the reader could change (AC-4)
# -- the schema field that governs shell/repository-command permission.
_PERMISSION_SETTING_MARKERS = ("permits_shell",)


def _make_repo_fixture(tmp_path: Path, *, registry_content: str) -> Path:
    """Build the Given: a REAL git repository ("the project") whose agent
    registry holds `registry_content` verbatim -- either the absent-agent or
    the denied-agent registry, both produced by the real JSON serializer.

    Layout:
        tmp_path/project/                                    <- real git repo
          .leafcutter/config/agent_registry.json
    """
    repo_dir = tmp_path / "project"
    repo_dir.mkdir(parents=True)
    subprocess.run(["git", "init", "-b", "main", str(repo_dir)], check=True, capture_output=True, text=True)
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

    registry_path = repo_dir / ".leafcutter" / "config" / "agent_registry.json"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(registry_content, encoding="utf-8")

    return repo_dir


# ---------------------------------------------------------------------------
# The real-execution harness (self-contained copy of the equivalent harness in
# test_acd_2100a_1.py / test_acd_2100a_3.py / test_acd_2100b_1.py /
# test_acd_2100b_2.py, per those files' own convention of not depending on
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
        mode="w", suffix=".js", prefix="acd_2100b3_", delete=False, encoding="utf-8"
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


def _combined_report_text(payload: dict) -> str:
    """Everything a human operator could plausibly read after this run: the
    final structured result's message, PLUS the text of every agent() prompt
    dispatched as a reporting/halt step (mirrors test_acd_2100b_1.py's /
    test_acd_2100b_2.py's own convention -- the buggy code also prints a
    message via a separate dispatched agent() call in addition to the
    returned result).
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


def _run_absent(tmp_root: Path) -> dict:
    repo_dir = _make_repo_fixture(tmp_root, registry_content=_ABSENT_AGENT_REGISTRY_JSON)
    return _run_plan_feature_real(
        repo_dir, label_responses={}, args={"workspace_setup_agent": _PROBE_AGENT_ID}
    )


def _run_denied(tmp_root: Path) -> dict:
    repo_dir = _make_repo_fixture(tmp_root, registry_content=_DENIED_AGENT_REGISTRY_JSON)
    return _run_plan_feature_real(
        repo_dir, label_responses={}, args={"workspace_setup_agent": _PROBE_AGENT_ID}
    )


class TestAbsentVsDeniedAgentReports(unittest.TestCase):

    def test_absent_agent_and_denied_agent_produce_different_reports(self):
        # covers: ACD-2100b-3
        # angle: criterion
        """AC-3: two runs that differ only in their registry -- the first
        registry does not list the workspace-setup agent at all, the second
        lists that same agent and withholds repository-command permission --
        produce reports that differ from each other.
        """
        with tempfile.TemporaryDirectory(prefix="acd2100b3_absent_") as tmp_absent:
            payload_absent = _run_absent(Path(tmp_absent))
            report_absent = _combined_report_text(payload_absent).lower()

        with tempfile.TemporaryDirectory(prefix="acd2100b3_denied_") as tmp_denied:
            payload_denied = _run_denied(Path(tmp_denied))
            report_denied = _combined_report_text(payload_denied).lower()

        self.assertNotEqual(
            report_absent, report_denied,
            "The absent-agent report is identical to the denied-agent "
            "report -- 'the agent is not in the registry' and 'the agent is "
            "in the registry but denied' must produce distinguishable "
            f"reports. report={report_absent!r}",
        )

    def test_absent_agent_report_names_the_agent_and_says_it_was_not_found(self):
        # covers: ACD-2100b-3
        # angle: criterion
        """AC-1: the first run's report names the agent id the check
        resolved (taken from args.workspace_setup_agent, not a hardcoded
        literal) and states that agent was not found in the registry, and it
        must not name a permission setting -- the entry does not exist, so
        there is no permission fact to report.
        """
        with tempfile.TemporaryDirectory(prefix="acd2100b3_absent_") as tmp:
            payload = _run_absent(Path(tmp))
            report = _combined_report_text(payload)
            report_lower = report.lower()

            self.assertIn(
                _PROBE_AGENT_ID, report,
                "The absent-agent report does not name the agent id the "
                f"check actually resolved. report={report!r}",
            )
            self.assertTrue(
                any(phrase in report_lower for phrase in _NOT_FOUND_PHRASES),
                "The absent-agent report does not state that the agent was "
                f"not found in the registry. report={report!r}",
            )
            for marker in _PERMISSION_SETTING_MARKERS:
                self.assertNotIn(
                    marker, report_lower,
                    f"The absent-agent report names a permission setting "
                    f"({marker!r}) that does not apply -- the agent's entry "
                    f"does not exist, so no permission fact was established. "
                    f"report={report!r}",
                )

            result = payload.get("result")
            self.assertIsInstance(
                result, dict,
                f"Expected a structured halt result, got: {result!r}",
            )
            self.assertNotEqual(
                (result or {}).get("status"), "ok",
                f"The run did not stop for an agent absent from the registry. result={result!r}",
            )

    def test_only_the_denied_report_names_the_permission_setting(self):
        # covers: ACD-2100b-3
        # angle: criterion
        """AC-2/AC-4: the second run's report states the agent is listed and
        is not permitted to run repository commands, and names the
        permission setting the operator can change (permits_shell); the
        first run's report names no permission setting. Asserted as a pair
        against both fixtures in one test, because either half alone would
        pass a fix that renders one shared message for both outcomes.
        """
        with tempfile.TemporaryDirectory(prefix="acd2100b3_absent_") as tmp_absent:
            payload_absent = _run_absent(Path(tmp_absent))
            report_absent = _combined_report_text(payload_absent).lower()

        with tempfile.TemporaryDirectory(prefix="acd2100b3_denied_") as tmp_denied:
            payload_denied = _run_denied(Path(tmp_denied))
            report_denied_raw = _combined_report_text(payload_denied)
            report_denied = report_denied_raw.lower()

        self.assertIn(
            _PROBE_AGENT_ID, report_denied_raw,
            "The denied-agent report does not name the agent id the check "
            f"actually resolved. report={report_denied_raw!r}",
        )
        self.assertTrue(
            any(phrase in report_denied for phrase in _LISTED_PHRASES),
            "The denied-agent report does not state that the agent is "
            f"listed in the registry. report={report_denied_raw!r}",
        )
        self.assertTrue(
            any(phrase in report_denied for phrase in _NOT_PERMITTED_PHRASES),
            "The denied-agent report does not state that the agent is not "
            f"permitted to run repository commands. report={report_denied_raw!r}",
        )
        for marker in _PERMISSION_SETTING_MARKERS:
            self.assertIn(
                marker, report_denied,
                f"The denied-agent report does not name the permission "
                f"setting ({marker!r}) the operator would change. "
                f"report={report_denied_raw!r}",
            )
            self.assertNotIn(
                marker, report_absent,
                f"The absent-agent report names a permission setting "
                f"({marker!r}) even though its entry does not exist in the "
                f"registry -- only the denial outcome may name it. "
                f"report_absent={report_absent!r}",
            )

    def test_both_outcomes_are_reached_through_the_workflow_entry_point(self):
        # covers: ACD-2100b-3
        # angle: reachability
        """Both reports are produced by driving the REAL workflow (via a real
        Node subprocess executing plan-feature.js's own top-level body, not
        by calling the registry lookup directly) with the two registries,
        and the recorded, CONSUMED (returned) outcome reflects each halt. In
        both cases no downstream worktree-setup step is ever dispatched.
        """
        with tempfile.TemporaryDirectory(prefix="acd2100b3_absent_") as tmp_absent:
            payload_absent = _run_absent(Path(tmp_absent))

            registry_read_calls = _calls_with_label(payload_absent, _REGISTRY_READ_LABEL)
            self.assertTrue(
                registry_read_calls,
                "The startup check's own registry-read dispatch never ran "
                f"for the absent-agent case -- cannot prove the check "
                f"executed at all. calls={payload_absent.get('calls')}",
            )
            downstream_absent = _calls_with_any_label(payload_absent, _SETUP_RELATED_LABELS)
            self.assertFalse(
                downstream_absent,
                "A step after the absent-agent check ran "
                f"(labels={_SETUP_RELATED_LABELS}), but the run must stop "
                f"at the check. calls={payload_absent.get('calls')}",
            )
            result_absent = payload_absent.get("result")
            self.assertIsInstance(
                result_absent, dict,
                f"The caller observes no structured halt result at all for "
                f"the absent-agent run (result={result_absent!r}) -- the "
                "halt must be CONSUMED in control flow (returned), not "
                "merely computed and discarded.",
            )
            self.assertNotEqual(
                (result_absent or {}).get("status"), "ok",
                f"The absent-agent run's own observable result does not "
                f"reflect a halt. result={result_absent!r}",
            )

        with tempfile.TemporaryDirectory(prefix="acd2100b3_denied_") as tmp_denied:
            payload_denied = _run_denied(Path(tmp_denied))

            registry_read_calls = _calls_with_label(payload_denied, _REGISTRY_READ_LABEL)
            self.assertTrue(
                registry_read_calls,
                "The startup check's own registry-read dispatch never ran "
                f"for the denied-agent case -- cannot prove the check "
                f"executed at all. calls={payload_denied.get('calls')}",
            )
            downstream_denied = _calls_with_any_label(payload_denied, _SETUP_RELATED_LABELS)
            self.assertFalse(
                downstream_denied,
                "A step after the denied-agent check ran "
                f"(labels={_SETUP_RELATED_LABELS}), but the run must stop "
                f"at the check. calls={payload_denied.get('calls')}",
            )
            result_denied = payload_denied.get("result")
            self.assertIsInstance(
                result_denied, dict,
                f"The caller observes no structured halt result at all for "
                f"the denied-agent run (result={result_denied!r}) -- the "
                "halt must be CONSUMED in control flow (returned), not "
                "merely computed and discarded.",
            )
            self.assertNotEqual(
                (result_denied or {}).get("status"), "ok",
                f"The denied-agent run's own observable result does not "
                f"reflect a halt. result={result_denied!r}",
            )

        # The two CONSUMED, returned results themselves must differ -- not
        # merely the side-channel agent() prompt text -- since it is the
        # returned result the real caller actually observes and branches on.
        self.assertNotEqual(
            json.dumps(result_absent, sort_keys=True),
            json.dumps(result_denied, sort_keys=True),
            "The absent-agent and denied-agent runs' own returned results "
            f"are identical. result_absent={result_absent!r} "
            f"result_denied={result_denied!r}",
        )


if __name__ == "__main__":
    unittest.main()
