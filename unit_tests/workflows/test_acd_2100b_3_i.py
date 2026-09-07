"""
MODULE: test_acd_2100b_3_i
GOAL: Behavioral tests for ACD-2100b-3-i -- "A registry that holds no agent
    entries is reported as unusable rather than as a missing agent."

INCIDENT BEING FIXED (KI-ACD-009 pattern, refining ACD-2100b-3's own
    four-state resolver one step further): `_resolveWorkspaceSetupAgentEntryState()`
    in templates/workflows-js/plan-feature.js already distinguishes a fourth,
    representable state -- "no_entries_collection", set whenever
    `registryJson.agents` is not an array at all:

        function _resolveWorkspaceSetupAgentEntryState(registryJson, agentId) {
          if (!registryJson || !Array.isArray(registryJson.agents)) {
            return { state: "no_entries_collection" };
          }
          ...
        }

    But the CALLER does not yet give that state its own report. The halt
    below only ever branches on `.state === "denied"` for the "listed but
    denied" report; every other state -- including "absent" AND
    "no_entries_collection" -- falls through to the SAME `notFoundMessage`,
    which asserts the agent "was not found in the registry":

        const agentIsListedAndDenied =
          !!workspaceSetupAgentEntryState && workspaceSetupAgentEntryState.state === "denied";
        if (agentIsListedAndDenied) { ... }
        // falls through here for BOTH "absent" and "no_entries_collection":
        const notFoundMessage = "... but that agent was not found in the registry ...";

    A registry whose `agents` field holds a single value (e.g. a string or a
    number) instead of a list IS "no_entries_collection" -- the registry
    parses cleanly (valid JSON) but does not carry the collection of agent
    entries the check expects. Reporting it as "the agent was not found in
    the registry" asserts an absence verdict this check never established:
    the check never got as far as looking for the agent's id inside a
    collection, because there was no collection to search. This is
    false-green-mechanisms M8 one layer further down from ACD-2100b-3: "the
    entries collection itself is not present" is a THIRD distinct fact about
    the registry's contents, not a synonym for "absent" nor for "denied".

TDD note: templates/workflows-js/plan-feature.js does not yet give
    "no_entries_collection" its own report -- it currently renders the SAME
    "was not found in the registry" notFoundMessage as a genuinely absent
    entry. All tests below are expected to be RED until python-coder adds a
    THIRD halt branch (alongside "denied" and "absent"/not-found) for
    `workspaceSetupAgentEntryState.state === "no_entries_collection"` that
    states the registry could not be used and what was found where the agent
    entries were expected, asserts neither absence nor denial, and still
    fails closed without ever raising an unhandled failure.

FIXTURE AUTHENTICITY (docs/reference/fixture-policy.md): the registry is
    produced by `json.dumps(..., indent=2)` -- the SAME serializer that would
    write a real agent_registry.json -- never a hand-typed literal.

HOW THE REAL SIDE EFFECT IS EXERCISED (Real-Artifact Behavioral Test
    Mandate): mirrors unit_tests/workflows/test_acd_2100b_3.py's
    `_run_plan_feature_real` harness (itself a self-contained copy of
    test_acd_2100a_1.py's / test_acd_2100a_3.py's / test_acd_2100b_1.py's /
    test_acd_2100b_2.py's own harness, per those files' convention of not
    depending on _workflow_engine_harness.py's private internals). It
    ACTUALLY EXECUTES every "Run the following command ...:\\n<cmd>\\nReturn
    JSON: ..." agent() dispatch via a real Node child_process, against a real
    git repository and a real, on-disk agent registry file -- never a mocked
    agent() that stubs the answer without running the shell command.

TICKET: 10_TICKET-20260826-ACD-2100b-3-i.md
AC: ACD-2100b-3-i
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
# check resolves -- passed via args.workspace_setup_agent so any report is
# proven to name the VALUE THE CHECK RESOLVED rather than a hardcoded literal.
_PROBE_AGENT_ID = "zqm7_probe_worktree_agent_44xk"

# A distinctive numeric value standing where the `agents` LIST belongs. This
# is deliberately NOT a string, so a naive `typeof` check and a naive
# stringified-value check both have something unambiguous to find.
_MALFORMED_AGENTS_VALUE = 42891

# The REAL serializer's output (json.dumps, indent=2 -- same serializer a
# real agent_registry.json write would use) for a registry that parses
# cleanly as JSON but holds a single value -- not a list -- where the agent
# entries collection belongs.
_NO_ENTRIES_COLLECTION_REGISTRY_JSON = json.dumps(
    {"agents": _MALFORMED_AGENTS_VALUE},
    indent=2,
)

# Phrases the report must contain (AC-1): a statement that the registry
# itself could not be used.
_COULD_NOT_BE_USED_PHRASES = (
    "could not be used",
    "cannot be used",
    "could not be interpreted",
    "is not a list",
    "is not an array",
    "not a list of agent entries",
    "no entries collection",
    "no agent entries",
)

# A marker proving the report states WHAT was found where the agent entries
# were expected (AC-1) -- either the literal malformed value or its type.
_WHAT_WAS_FOUND_MARKERS = (str(_MALFORMED_AGENTS_VALUE), "number")

# Phrases that would wrongly assert this outcome as "the agent is absent"
# (AC-2) -- the exact defect this record removes. Reused verbatim from
# ACD-2100b-3's own vocabulary so a fix that merely swaps a word does not
# accidentally dodge this net.
_ABSENCE_PHRASES = (
    "not found in the registry",
    "not listed in the registry",
    "is not in the registry",
    "not present in the registry",
)

# Phrases/markers that would wrongly assert this outcome as "the agent is
# denied permission" (AC-3).
_DENIAL_PHRASES = ("is not permitted", "denies", "denied")
_PERMISSION_SETTING_MARKERS = ("permits_shell",)

# Signatures of an UNHANDLED failure (top-level .catch(), an uncaught JS
# exception's stack trace) as opposed to a recorded, returned report.
_UNHANDLED_FAILURE_MARKERS = (
    "harness: top-level error",
    "referenceerror",
    "typeerror",
    "uncaught",
)


def _make_repo_fixture(tmp_path: Path, *, registry_content: str) -> Path:
    """Build the Given: a REAL git repository ("the project") whose agent
    registry holds `registry_content` verbatim -- the no-entries-collection
    registry, produced by the real JSON serializer.

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
# test_acd_2100b_2.py / test_acd_2100b_3.py, per those files' own convention
# of not depending on _workflow_engine_harness.py's private internals).
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
        mode="w", suffix=".js", prefix="acd_2100b3i_", delete=False, encoding="utf-8"
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
    test_acd_2100b_2.py's / test_acd_2100b_3.py's own convention -- the
    checked code also prints a message via a separate dispatched agent()
    call in addition to the returned result).
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


def _run_no_entries_collection(tmp_root: Path) -> dict:
    repo_dir = _make_repo_fixture(
        tmp_root, registry_content=_NO_ENTRIES_COLLECTION_REGISTRY_JSON
    )
    return _run_plan_feature_real(
        repo_dir, label_responses={}, args={"workspace_setup_agent": _PROBE_AGENT_ID}
    )


class TestNoEntriesCollectionReport(unittest.TestCase):

    def test_registry_without_an_entries_collection_reports_could_not_be_used(self):
        # covers: ACD-2100b-3-i
        # angle: criterion
        """AC-1: a registry that parses cleanly (valid JSON) but holds a
        single value where the agent entries collection belongs must produce
        a report stating the registry could not be used, and naming what was
        found in that position (its value or its type) so an operator can
        tell a wrong file from a structurally changed one.
        """
        with tempfile.TemporaryDirectory(prefix="acd2100b3i_") as tmp:
            payload = _run_no_entries_collection(Path(tmp))
            report = _combined_report_text(payload)
            report_lower = report.lower()

            self.assertTrue(
                any(phrase in report_lower for phrase in _COULD_NOT_BE_USED_PHRASES),
                "The no-entries-collection report does not state that the "
                f"registry could not be used. report={report!r}",
            )
            self.assertTrue(
                any(marker in report for marker in _WHAT_WAS_FOUND_MARKERS),
                "The no-entries-collection report does not state what was "
                "found where the agent entries were expected (expected the "
                f"malformed value {_MALFORMED_AGENTS_VALUE!r} or its type "
                f"'number' to appear). report={report!r}",
            )

    def test_no_entries_collection_report_asserts_neither_absence_nor_denial(self):
        # covers: ACD-2100b-3-i
        # angle: criterion
        """AC-2/AC-3: that same report must contain no statement that any
        agent is absent from the registry, and no statement that any agent
        lacks permission -- the two false verdicts this outcome currently
        produces (it falls through to the same "not found in the registry"
        message an absent entry gets).
        """
        with tempfile.TemporaryDirectory(prefix="acd2100b3i_") as tmp:
            payload = _run_no_entries_collection(Path(tmp))
            report_lower = _combined_report_text(payload).lower()

            for phrase in _ABSENCE_PHRASES:
                self.assertNotIn(
                    phrase, report_lower,
                    "The no-entries-collection report wrongly asserts the "
                    f"agent is absent from the registry ({phrase!r} found). "
                    f"report={report_lower!r}",
                )
            for phrase in _DENIAL_PHRASES:
                self.assertNotIn(
                    phrase, report_lower,
                    "The no-entries-collection report wrongly asserts the "
                    f"agent lacks permission ({phrase!r} found). "
                    f"report={report_lower!r}",
                )
            for marker in _PERMISSION_SETTING_MARKERS:
                self.assertNotIn(
                    marker, report_lower,
                    f"The no-entries-collection report names a permission "
                    f"setting ({marker!r}) that does not apply -- no "
                    f"permission fact was ever established. "
                    f"report={report_lower!r}",
                )

    def test_no_entries_collection_does_not_raise_an_unhandled_failure(self):
        # covers: ACD-2100b-3-i
        # angle: failure
        """The run's recorded outcome must be the report rather than an
        unhandled failure, and no unhandled-failure trace may appear in the
        captured output -- a fail-closed halt and an unhandled crash both
        stop the run, so the report is the only observable difference, and
        the guard must catch the interpretation gap by type rather than
        letting it propagate.
        """
        with tempfile.TemporaryDirectory(prefix="acd2100b3i_") as tmp:
            payload = _run_no_entries_collection(Path(tmp))

            self.assertNotIn(
                "error", payload,
                "The harness's top-level .catch() fired -- an UNHANDLED "
                f"failure escaped the check rather than a recorded halt. "
                f"payload={payload!r}",
            )
            self.assertEqual(
                payload.get("_returncode"), 0,
                "The Node process exited non-zero -- an unhandled failure, "
                f"not a recorded, returned report. payload={payload!r}",
            )
            stderr_lower = (payload.get("_stderr") or "").lower()
            for marker in _UNHANDLED_FAILURE_MARKERS:
                self.assertNotIn(
                    marker, stderr_lower,
                    f"An unhandled-failure signature ({marker!r}) appeared "
                    f"in stderr. stderr={payload.get('_stderr')!r}",
                )

            result = payload.get("result")
            self.assertIsInstance(
                result, dict,
                f"Expected a structured, recorded halt result -- got: {result!r}",
            )
            self.assertNotEqual(
                (result or {}).get("status"), "ok",
                f"The run did not stop for a registry with no entries "
                f"collection. result={result!r}",
            )

    def test_outcome_is_produced_through_the_workflow_entry_point(self):
        # covers: ACD-2100b-3-i
        # angle: reachability
        """The report is produced by driving the REAL workflow (via a real
        Node subprocess executing plan-feature.js's own top-level body, not
        by calling the registry-state resolver directly), and the run stops
        at the check -- no downstream worktree-setup step is ever dispatched
        -- with the recorded outcome CONSUMED (returned) rather than merely
        computed and discarded.
        """
        with tempfile.TemporaryDirectory(prefix="acd2100b3i_") as tmp:
            payload = _run_no_entries_collection(Path(tmp))

            registry_read_calls = _calls_with_label(payload, _REGISTRY_READ_LABEL)
            self.assertTrue(
                registry_read_calls,
                "The startup check's own registry-read dispatch never ran "
                f"-- cannot prove the check executed at all. "
                f"calls={payload.get('calls')}",
            )
            downstream_calls = _calls_with_any_label(payload, _SETUP_RELATED_LABELS)
            self.assertFalse(
                downstream_calls,
                "A step after the no-entries-collection check ran "
                f"(labels={_SETUP_RELATED_LABELS}), but the run must stop "
                f"at the check. calls={payload.get('calls')}",
            )
            result = payload.get("result")
            self.assertIsInstance(
                result, dict,
                f"The caller observes no structured halt result at all "
                f"(result={result!r}) -- the halt must be CONSUMED in "
                "control flow (returned), not merely computed and discarded.",
            )
            self.assertNotEqual(
                (result or {}).get("status"), "ok",
                f"The run's own observable result does not reflect a halt. "
                f"result={result!r}",
            )


if __name__ == "__main__":
    unittest.main()
