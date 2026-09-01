"""
MODULE: test_acd_2100b_1
GOAL: Behavioral tests for ACD-2100b-1 -- "A registry the startup check cannot
    read is reported as unreadable and names what it tried to read."

INCIDENT BEING REGRESSION-TESTED (KI-ACD-009, false verdict / Mechanism M8
    inverted): templates/workflows-js/plan-feature.js's Pre-Stage-0
    Workspace-Setup Dispatch Permission Gate (around line 2020) reads
    `config/agent_registry.json` via `buildRepoAnchoredReadCommand()`, then
    does:

        if (registryParsed && typeof registryParsed.output === "string") {
          const registryJson = JSON.parse(registryParsed.output);
          ...
        }
        // on ANY parse failure (including an EMPTY stdout caused by the read
        // command itself failing with exit_code != 0 -- e.g. no file at the
        // resolved location, or permission refused) permitsShell stays false
        // and the run falls into the SAME halt message used for a
        // successfully-read registry that genuinely denies the agent:
        //
        //   "...that agent's registered charter (config/agent_registry.json)
        //    does not permit running repository-mutating shell commands...
        //    Fix ... config/agent_registry.json's permits_shell field..."

    The read command's own `exit_code` is never inspected, so "the registry
    could not be read" (an I/O fact) and "the registry was read and denies
    this agent" (a permission fact) collapse into one indistinguishable
    report -- and that report actively asserts a permission verdict the check
    never established, and points the reader at `permits_shell`, a setting
    that has nothing to do with an absent file or a denied read.

WHY A SINGLE ABSENT-REGISTRY FIXTURE CANNOT PROVE THE WHOLE AC: the Then
    clause requires the reason to DISTINGUISH "no file at that location" from
    "permission refused" -- two remedies, two reasons. A fixture that only
    ever exercises "no file" can pass a fix that hardcodes one canned reason
    string for every unreadable-registry case, which is the same defect one
    level down (KI-ACD-009's own diagnosis: "collapsing them recreates the
    defect"). This file therefore builds TWO independently-unreadable
    registries -- one absent entirely, one present on disk but with read
    permission withheld from the process -- and asserts their reports differ.

HOW THE REAL SIDE EFFECT IS EXERCISED (Real-Artifact Behavioral Test
    Mandate): mirrors unit_tests/workflows/test_acd_2100a_1.py's and
    test_acd_2100a_3.py's own harness (`_run_plan_feature_real`), which is
    intentionally NOT the shared `_workflow_engine_harness.py` mock -- that
    mock stubs every agent() call with a canned response and never actually
    runs a shell command, so it cannot tell us whether a REAL absent file or a
    REAL permission-denied read produces the reported behavior. This file's
    harness ACTUALLY EXECUTES every "Run the following command
    ...:\\n<cmd>\\nReturn JSON: ..." dispatch via a real Node child_process,
    against a real git repository and a real, on-disk (or deliberately
    absent/unreadable) registry file.

TDD note: templates/workflows-js/plan-feature.js does not yet distinguish an
    unreadable registry from a successfully-read, permission-denying one, nor
    does it distinguish "absent" from "permission refused" within that. All
    four tests below are expected to be RED until python-coder implements
    that distinction (inspecting the read command's own exit_code /
    diagnostic rather than only its stdout).

TICKET: 07_TICKET-20260826-ACD-2100b-1.md
AC: ACD-2100b-1
"""

from __future__ import annotations

import json
import os
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
_MIS_ASSIGNMENT_LABEL = "workspace-setup-mis-assignment"
_SETUP_RELATED_LABELS = ("resolve-worktree-setup-script-path", "worktree-setup")

# Reason-vocabulary markers used to prove the two unreadable-registry causes
# produce genuinely DIFFERENT reasons, not one canned string reused for both
# (the "collapsing them recreates the defect" hazard the ticket names).
_ABSENT_REASON_MARKERS = (
    "no such file",
    "not found",
    "does not exist",
    "no file exists",
    "missing",
    "could not resolve",
)
_PERMISSION_REASON_MARKERS = (
    "permission denied",
    "not readable",
    "access denied",
    "denied",
    "could not open",
)

# Vocabulary this report must never contain -- a statement about agent
# permission, or a pointer at a permission setting (AC-3 / AC-4).
_FORBIDDEN_PERMISSION_VERDICT_MARKERS = (
    "permit",  # covers permit/permits/permitted/does not permit
    "permits_shell",
)


def _is_root() -> bool:
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, check=True, capture_output=True, text=True
    )


def _make_repo_fixture(
    tmp_path: Path,
    *,
    registry_present: bool,
    registry_permission_denied: bool = False,
) -> Path:
    """Build the Given: a REAL git repository ("the project") in which the
    agent registry the startup check resolves to either does not exist at
    all, or exists but cannot be opened for reading.

    Layout:
        tmp_path/project/                                    <- real git repo
          .leafcutter/config/agent_registry.json              <- present iff
                                                                   registry_present
    """
    repo_dir = tmp_path / "project"
    repo_dir.mkdir(parents=True)
    _run(["git", "init", "-b", "main", str(repo_dir)])
    _run(["git", "-C", str(repo_dir), "config", "user.email", "test@example.com"])
    _run(["git", "-C", str(repo_dir), "config", "user.name", "Test"])
    (repo_dir / "README.md").write_text("seed\n", encoding="utf-8")
    _run(["git", "-C", str(repo_dir), "add", "README.md"])
    _run(["git", "-C", str(repo_dir), "commit", "-m", "seed"])

    if registry_present:
        registry_path = repo_dir / ".leafcutter" / "config" / "agent_registry.json"
        registry_path.parent.mkdir(parents=True)
        registry_path.write_text(
            json.dumps({"agents": [{"id": "worktree-agent", "permits_shell": True}]}),
            encoding="utf-8",
        )
        if registry_permission_denied:
            registry_path.chmod(0o000)

    return repo_dir


def _resolved_registry_location(repo_dir: Path) -> str:
    return str(repo_dir / ".leafcutter" / "config" / "agent_registry.json")


# ---------------------------------------------------------------------------
# The real-execution harness (self-contained copy of the equivalent harness in
# test_acd_2100a_1.py / test_acd_2100a_3.py, per those files' own convention
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
        mode="w", suffix=".js", prefix="acd_2100b1_", delete=False, encoding="utf-8"
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
    dispatched as a reporting/halt step. The AC's own test_rationale notes
    the buggy code "also prints a message" via a separate dispatched agent()
    call in addition to the returned result, so checking only one surface
    would let a forbidden phrase hide in the other.
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


def _registry_read_reason(payload: dict) -> str:
    """The read command's own real stderr/stdout for the registry-read
    dispatch -- the ground truth for what actually failed and why, captured
    from the REAL executed shell command (not the workflow's own report).
    """
    reads = _calls_with_label(payload, _REGISTRY_READ_LABEL)
    if not reads:
        return ""
    real = reads[0].get("real_result") or {}
    return f"{real.get('stderr', '')}\n{real.get('output', '')}"


class TestUnreadableRegistryReport(unittest.TestCase):

    def test_absent_registry_is_reported_as_unreadable_with_the_location_tried(self):
        # covers: ACD-2100b-1
        # angle: criterion
        """AC-1/AC-2: no file exists at the resolved registry location; the run
        stops and its report contains that location and states the read
        failed because nothing is there.
        """
        with tempfile.TemporaryDirectory(prefix="acd2100b1_absent_") as tmp:
            repo_dir = _make_repo_fixture(Path(tmp), registry_present=False)
            payload = _run_plan_feature_real(repo_dir, label_responses={}, args={})

            report = _combined_report_text(payload)

            location = _resolved_registry_location(repo_dir)
            self.assertIn(
                location, report,
                "The report does not name the exact location that was tried "
                f"({location!r}). report={report!r}",
            )

            self.assertTrue(
                any(
                    phrase in report.lower()
                    for phrase in ("could not be read", "cannot be read", "unreadable")
                ),
                "The report does not state that the registry could not be "
                f"read. report={report!r}",
            )

            result = payload.get("result")
            self.assertIsInstance(
                result, dict,
                f"Expected a structured halt result, got: {result!r}",
            )
            self.assertNotEqual(
                (result or {}).get("status"), "ok",
                f"The run did not stop for an unreadable registry. result={result!r}",
            )

    def test_unreadable_registry_report_contains_no_permission_verdict(self):
        # covers: ACD-2100b-1
        # angle: criterion
        """AC-3/AC-4: the same report (absent-registry case) contains no
        statement about any agent being permitted or not permitted to run
        repository commands, and does not name a permission setting --
        asserted as an absence, because the buggy code also prints a message.
        """
        with tempfile.TemporaryDirectory(prefix="acd2100b1_no_verdict_") as tmp:
            repo_dir = _make_repo_fixture(Path(tmp), registry_present=False)
            payload = _run_plan_feature_real(repo_dir, label_responses={}, args={})

            report = _combined_report_text(payload).lower()

            for marker in _FORBIDDEN_PERMISSION_VERDICT_MARKERS:
                self.assertNotIn(
                    marker, report,
                    "The report on an unreadable registry contains a "
                    f"permission-verdict marker ({marker!r}), but AC-3/AC-4 "
                    "require it to contain no statement about agent "
                    f"permission and no pointer at a permission setting. "
                    f"report={report!r}",
                )

    def test_permission_refused_registry_reports_a_different_reason_than_absent(self):
        # covers: ACD-2100b-1
        # angle: boundary
        """AC-2: a registry file present but with read permission withheld
        from the process produces a report naming the location and a reason
        distinct from the nothing-is-there reason.
        """
        if _is_root():
            self.skipTest(
                "Running as root -- file permission bits do not deny reads, "
                "so this boundary cannot be constructed."
            )

        with tempfile.TemporaryDirectory(prefix="acd2100b1_absent_cmp_") as tmp_absent:
            repo_dir_absent = _make_repo_fixture(
                Path(tmp_absent), registry_present=False
            )
            payload_absent = _run_plan_feature_real(
                repo_dir_absent, label_responses={}, args={}
            )
            report_absent = _combined_report_text(payload_absent).lower()

        with tempfile.TemporaryDirectory(prefix="acd2100b1_denied_") as tmp_denied:
            repo_dir_denied = _make_repo_fixture(
                Path(tmp_denied),
                registry_present=True,
                registry_permission_denied=True,
            )
            try:
                payload_denied = _run_plan_feature_real(
                    repo_dir_denied, label_responses={}, args={}
                )
            finally:
                # Restore read permission so TemporaryDirectory cleanup (and
                # any later inspection) is never blocked by our own fixture.
                registry_path = (
                    repo_dir_denied / ".leafcutter" / "config" / "agent_registry.json"
                )
                registry_path.chmod(0o644)

            report_denied = _combined_report_text(payload_denied).lower()

            location_denied = _resolved_registry_location(repo_dir_denied)
            self.assertIn(
                location_denied, _combined_report_text(payload_denied),
                "The report for a permission-refused registry does not name "
                f"the location that was tried ({location_denied!r}). "
                f"report={report_denied!r}",
            )

            reason_denied = _registry_read_reason(payload_denied).lower()
            self.assertTrue(
                any(marker in reason_denied for marker in _PERMISSION_REASON_MARKERS),
                "The real, executed registry-read command for the "
                "permission-refused fixture did not actually fail for a "
                f"permission reason -- test construction error. reason={reason_denied!r}",
            )

            self.assertNotEqual(
                report_absent, report_denied,
                "The report for a permission-refused registry is identical "
                "to the report for an absent registry -- the two distinct "
                "failure causes must produce distinguishable reasons.",
            )

            self.assertFalse(
                any(marker in report_denied for marker in _ABSENT_REASON_MARKERS),
                "The permission-refused report reuses the nothing-is-there "
                f"vocabulary instead of stating its own distinct reason. "
                f"report={report_denied!r}",
            )
            self.assertFalse(
                any(marker in report_absent for marker in _PERMISSION_REASON_MARKERS),
                "The absent-registry report reuses permission-refused "
                f"vocabulary instead of stating its own distinct reason. "
                f"report={report_absent!r}",
            )

    def test_unreadable_registry_halts_the_run_at_the_check(self):
        # covers: ACD-2100b-1
        # angle: reachability
        """Driving the REAL workflow (via a real Node subprocess, not by
        importing a helper) with the registry unreadable stops the run at the
        check -- no step after the check runs -- and the halt is what the
        caller observes (the returned result, not a value merely computed
        and discarded).
        """
        with tempfile.TemporaryDirectory(prefix="acd2100b1_halt_") as tmp:
            repo_dir = _make_repo_fixture(Path(tmp), registry_present=False)
            payload = _run_plan_feature_real(repo_dir, label_responses={}, args={})

            registry_read_calls = _calls_with_label(payload, _REGISTRY_READ_LABEL)
            self.assertTrue(
                registry_read_calls,
                "The startup check's own registry-read dispatch never ran -- "
                f"cannot prove the check executed at all. calls={payload.get('calls')}",
            )

            downstream_calls = _calls_with_any_label(payload, _SETUP_RELATED_LABELS)
            self.assertFalse(
                downstream_calls,
                "A step after the unreadable-registry check ran "
                f"(labels={_SETUP_RELATED_LABELS}), but the run must stop at "
                f"the check. calls={payload.get('calls')}",
            )

            result = payload.get("result")
            self.assertIsInstance(
                result, dict,
                "The caller observes no structured halt result at all "
                f"(result={result!r}) -- the halt must be CONSUMED in "
                "control flow (returned), not merely computed and discarded.",
            )
            self.assertNotEqual(
                (result or {}).get("status"), "ok",
                f"The run's own observable result does not reflect a halt. result={result!r}",
            )

            # Halting alone is NOT sufficient proof for this AC: the existing
            # (buggy) code already halts on any registry problem -- it fails
            # closed today, just with the wrong diagnosis (KI-ACD-009). What
            # the CALLER must observe is the corrected unreadable-registry
            # report, not merely a halt of some kind, or this test would pass
            # unchanged before python-coder's fix.
            result_text = json.dumps(result or {}).lower()
            self.assertTrue(
                any(
                    phrase in result_text
                    for phrase in ("could not be read", "cannot be read", "unreadable")
                ),
                "The halted run's own observable result does not state that "
                f"the registry could not be read. result={result!r}",
            )
            for marker in _FORBIDDEN_PERMISSION_VERDICT_MARKERS:
                self.assertNotIn(
                    marker, result_text,
                    "The halted run's own observable result contains a "
                    f"permission-verdict marker ({marker!r}). result={result!r}",
                )


if __name__ == "__main__":
    unittest.main()
