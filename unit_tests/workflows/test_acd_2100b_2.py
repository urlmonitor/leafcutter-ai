"""
MODULE: test_acd_2100b_2
GOAL: Behavioral tests for ACD-2100b-2 -- "A registry whose contents cannot be
    understood is reported as unusable and not as a permission verdict."

INCIDENT BEING REGRESSION-TESTED (KI-ACD-009, outcome 2 of 4): the Pre-Stage-0
    Workspace-Setup Dispatch Permission Gate in templates/workflows-js/plan-feature.js
    reads `config/agent_registry.json` and, when the read command's own
    exit_code is 0 (the file WAS opened and read successfully), does:

        } else if (registryParsed && typeof registryParsed.output === "string") {
          const registryJson = JSON.parse(registryParsed.output);
          ...
        }
        ...
        } catch (_parseErr) {
          permitsShell = false; // fail closed on any parse error
        }

    A truncated/malformed file makes `JSON.parse` throw. That throw IS caught
    (so it does not crash the process), but the catch does nothing except set
    `permitsShell = false` -- it records no reason, and `registryUnreadable`
    (the ACD-2100b-1 unreadable-registry flag) is never set for this cause
    either, because the read command itself exited 0. Control falls straight
    into the `if (!permitsShell)` branch below, which renders the SAME
    permission-mis-assignment report used for a registry that was read fine
    and genuinely denies the agent shell access:

        "...that agent's registered charter (config/agent_registry.json)
         does not permit running repository-mutating shell commands...
         Fix ... config/agent_registry.json's permits_shell field..."

    That is a false permission verdict about a file the check never actually
    interpreted, and it collapses "the contents are corrupt" into the same
    bucket as "this specific agent is denied" -- the exact
    false-green-mechanisms M8 ("a check asserting a failure cause it did not
    establish") this AC exists to close.

WHY A SINGLE TRUNCATION FIXTURE CANNOT PROVE THE WHOLE AC: AC-4 requires the
    report to state WHERE in the contents interpretation failed, not merely
    THAT it failed. A fixture that only ever truncates at one fixed offset
    could pass a fix that hardcodes one canned "position" string regardless
    of where the real cut actually was -- the same "collapse distinct causes
    into one shared message" defect one level down. This file therefore
    truncates the SAME real, serializer-produced registry JSON at two
    different, independently-computed offsets and requires the reported
    position to track each cut individually (see `_position_stated_correctly`).

FIXTURE AUTHENTICITY (docs/reference/fixture-policy.md, this AC's own
    doc_links, and the test_spec's `real_artifact` angle on
    test_uninterpretable_report_states_where_interpretation_failed): the
    malformed registry content is produced by `json.dumps(..., indent=2)` --
    the SAME serializer that would write a real agent_registry.json -- and
    then sliced with plain Python string slicing to simulate a partial write
    / interrupted build-time copy. It is never a hand-typed broken literal.

HOW THE REAL SIDE EFFECT IS EXERCISED (Real-Artifact Behavioral Test
    Mandate): mirrors unit_tests/workflows/test_acd_2100b_1.py's
    `_run_plan_feature_real` harness (itself a self-contained copy of
    test_acd_2100a_1.py's / test_acd_2100a_3.py's own harness, per those
    files' convention of not depending on _workflow_engine_harness.py's
    private internals). It ACTUALLY EXECUTES every
    "Run the following command ...:\\n<cmd>\\nReturn JSON: ..." agent()
    dispatch via a real Node child_process, against a real git repository and
    a real, on-disk (truncated) registry file -- never a mocked agent() that
    stubs the answer without running the shell command.

TDD note: templates/workflows-js/plan-feature.js does not yet distinguish "the
    registry was read but its contents could not be interpreted" from "the
    registry denies this agent shell access" -- both currently render the
    SAME permission-mis-assignment report. All five tests below are expected
    to be RED until python-coder adds that distinction (catching the
    JSON.parse failure by type, logging it at WARNING, and reporting a
    position-bearing, permission-verdict-free "could not be interpreted"
    outcome instead of falling through to the permission-verdict branch).

TICKET: 08_TICKET-20260826-ACD-2100b-2.md
AC: ACD-2100b-2
"""

from __future__ import annotations

import json
import re
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

# The REAL serializer's output for a two-agent registry -- built with the
# same json.dumps() a real agent_registry.json write would use, never a
# hand-typed literal (fixture-authenticity policy). Two distinct, deliberately
# mid-token truncation offsets are cut from this SAME content below so the
# "states where interpretation failed" test can prove the reported position
# tracks the real cut point rather than a hardcoded canned value. The second
# agent's id is a deliberately distinctive, low-collision token (rather than
# e.g. "second-agent") so that a truncation landing inside it produces a
# trailing fragment that cannot coincidentally match unrelated vocabulary
# already present in plan-feature.js's OTHER report strings (e.g. the literal
# schema field name "permits_shell", which appears in this AC's own
# forbidden-permission-verdict wording and would otherwise produce a false
# fragment match).
_FULL_REGISTRY_JSON = json.dumps(
    {
        "agents": [
            {"id": "worktree-agent", "permits_shell": True},
            {"id": "xk7q_distinctive_probe_marker_93fz", "permits_shell": False},
        ]
    },
    indent=2,
)
_CUT_A = 118  # mid distinctive-marker string-literal ("...xk7q_distinc|").
_CUT_B = 132  # mid distinctive-marker string-literal ("...probe_mar|"), same line as _CUT_A.

# Vocabulary this report must never contain -- a statement about agent
# permission, or a pointer at a permission setting (AC-3).
_FORBIDDEN_PERMISSION_VERDICT_MARKERS = (
    "permit",  # covers permit/permits/permitted/does not permit
    "permits_shell",
)

# The wording an UNREADABLE registry (ACD-2100b-1, already implemented)
# reports -- an UNINTERPRETABLE registry's report must differ from this
# (AC-2).
_UNREADABLE_PHRASES = ("could not be read", "cannot be read", "unreadable")

# The wording this AC requires for a registry that was read but whose
# contents could not be interpreted (AC-1).
_UNINTERPRETABLE_PHRASES = (
    "could not be interpreted",
    "cannot be interpreted",
    "could not interpret",
    "failed to interpret",
)


def _make_repo_fixture(
    tmp_path: Path,
    *,
    registry_present: bool = True,
    registry_content: str | None = None,
) -> Path:
    """Build the Given: a REAL git repository ("the project") in which the
    agent registry the startup check resolves to either does not exist, or
    exists and can be opened and read but holds `registry_content` verbatim
    (a truncated, real-serializer-produced JSON string when constructing the
    uninterpretable-registry case).

    Layout:
        tmp_path/project/                                    <- real git repo
          .leafcutter/config/agent_registry.json              <- present iff
                                                                   registry_present
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

    if registry_present:
        registry_path = repo_dir / ".leafcutter" / "config" / "agent_registry.json"
        registry_path.parent.mkdir(parents=True)
        content = registry_content if registry_content is not None else _FULL_REGISTRY_JSON
        registry_path.write_text(content, encoding="utf-8")

    return repo_dir


# ---------------------------------------------------------------------------
# The real-execution harness (self-contained copy of the equivalent harness in
# test_acd_2100a_1.py / test_acd_2100a_3.py / test_acd_2100b_1.py, per those
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
        mode="w", suffix=".js", prefix="acd_2100b2_", delete=False, encoding="utf-8"
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
    dispatched as a reporting/halt step (mirrors test_acd_2100b_1.py's own
    convention -- the buggy code also prints a message via a separate
    dispatched agent() call in addition to the returned result).
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


_OFFSET_PATTERN = re.compile(
    r"(?:position|offset|character|char|index|byte|col(?:umn)?)\D{0,15}(\d{1,6})",
    re.IGNORECASE,
)
_LINE_PATTERN = re.compile(r"line\D{0,10}(\d{1,4})", re.IGNORECASE)


def _position_stated_correctly(report: str, content: str, cut: int) -> bool:
    """True iff `report` names a position that corresponds to where `content`
    was actually cut at `cut` -- accepting any of the three forms
    ACD-2100b-2's implementation notes explicitly allow: a byte/character
    offset near the real cut point, a line number matching the truncated
    content's own line count, or the literal trailing fragment at which
    interpretation stopped. This intentionally does NOT require one specific
    encoding -- only that whichever encoding is used genuinely tracks the
    real, on-disk cut point rather than a canned constant.
    """
    truncated = content[:cut]
    expected_line = truncated.count("\n") + 1

    for match in _OFFSET_PATTERN.finditer(report):
        if abs(int(match.group(1)) - cut) <= 5:
            return True

    for match in _LINE_PATTERN.finditer(report):
        if int(match.group(1)) == expected_line:
            return True

    for frag_len in (10, 15, 20):
        if len(truncated) >= frag_len:
            fragment = truncated[-frag_len:].strip()
            if fragment and fragment in report:
                return True

    return False


class TestUninterpretableRegistryReport(unittest.TestCase):

    def test_truncated_registry_is_reported_as_uninterpretable(self):
        # covers: ACD-2100b-2
        # angle: criterion
        """AC-1: a registry produced by truncating the real serializer's
        output part-way through is read successfully (the file exists and is
        readable) but its contents cannot be interpreted as a registry; the
        run stops and reports that the file was read but could not be
        interpreted.
        """
        with tempfile.TemporaryDirectory(prefix="acd2100b2_truncated_") as tmp:
            repo_dir = _make_repo_fixture(
                Path(tmp), registry_content=_FULL_REGISTRY_JSON[:_CUT_A]
            )
            payload = _run_plan_feature_real(repo_dir, label_responses={}, args={})

            report = _combined_report_text(payload).lower()

            self.assertTrue(
                any(phrase in report for phrase in _UNINTERPRETABLE_PHRASES),
                "The report for a registry that was read but whose contents "
                "could not be parsed does not state that the file was read "
                f"but could not be interpreted. report={report!r}",
            )

            result = payload.get("result")
            self.assertIsInstance(
                result, dict,
                f"Expected a structured halt result, got: {result!r}",
            )
            self.assertNotEqual(
                (result or {}).get("status"), "ok",
                f"The run did not stop for an uninterpretable registry. result={result!r}",
            )

    def test_uninterpretable_report_differs_from_the_unreadable_report(self):
        # covers: ACD-2100b-2
        # angle: criterion
        """AC-2/AC-3: two runs -- one with the registry entirely absent (the
        ACD-2100b-1 unreadable-registry outcome), one with it present but
        truncated (this AC's uninterpretable-registry outcome) -- produce
        reports that differ from each other in wording, and NEITHER contains
        a statement about whether any agent is permitted to run repository
        commands.
        """
        with tempfile.TemporaryDirectory(prefix="acd2100b2_absent_") as tmp_absent:
            repo_dir_absent = _make_repo_fixture(Path(tmp_absent), registry_present=False)
            payload_absent = _run_plan_feature_real(repo_dir_absent, label_responses={}, args={})
            report_absent = _combined_report_text(payload_absent).lower()

        with tempfile.TemporaryDirectory(prefix="acd2100b2_truncated_") as tmp_truncated:
            repo_dir_truncated = _make_repo_fixture(
                Path(tmp_truncated), registry_content=_FULL_REGISTRY_JSON[:_CUT_A]
            )
            payload_truncated = _run_plan_feature_real(
                repo_dir_truncated, label_responses={}, args={}
            )
            report_truncated = _combined_report_text(payload_truncated).lower()

        self.assertNotEqual(
            report_absent, report_truncated,
            "The uninterpretable-registry report is identical to the "
            "unreadable-registry report -- the two distinct outcomes must "
            "produce distinguishable reports.",
        )

        # The absent-registry (unreadable) report must not have regressed
        # into stating "could not be interpreted" -- that would just move the
        # collapse the other direction.
        self.assertFalse(
            any(phrase in report_absent for phrase in _UNINTERPRETABLE_PHRASES),
            f"The unreadable-registry report now uses the uninterpretable "
            f"wording -- the two outcomes have collapsed. report={report_absent!r}",
        )
        # And the truncated (uninterpretable) report must not simply reuse
        # the unreadable-registry's own wording either.
        self.assertFalse(
            any(phrase in report_truncated for phrase in _UNREADABLE_PHRASES),
            "The uninterpretable-registry report reuses the unreadable-"
            f"registry's wording instead of stating its own distinct "
            f"outcome. report={report_truncated!r}",
        )

        for marker in _FORBIDDEN_PERMISSION_VERDICT_MARKERS:
            self.assertNotIn(
                marker, report_absent,
                f"The unreadable-registry report contains a permission-"
                f"verdict marker ({marker!r}). report={report_absent!r}",
            )
            self.assertNotIn(
                marker, report_truncated,
                f"The uninterpretable-registry report contains a permission-"
                f"verdict marker ({marker!r}), but AC-3 requires it to "
                f"contain no statement about agent permission. "
                f"report={report_truncated!r}",
            )

    def test_uninterpretable_report_states_where_interpretation_failed(self):
        # covers: ACD-2100b-2
        # angle: real_artifact
        """AC-4: the report names a position within the contents, and that
        position corresponds to where the REAL serializer's output was cut --
        proved by truncating the same real JSON at two different,
        independently-computed offsets and requiring each run's reported
        position to track its own cut point (not a single hardcoded value
        that happens to satisfy one of them).
        """
        for cut in (_CUT_A, _CUT_B):
            with self.subTest(cut=cut):
                with tempfile.TemporaryDirectory(prefix="acd2100b2_position_") as tmp:
                    repo_dir = _make_repo_fixture(
                        Path(tmp), registry_content=_FULL_REGISTRY_JSON[:cut]
                    )
                    payload = _run_plan_feature_real(repo_dir, label_responses={}, args={})
                    report = _combined_report_text(payload)

                    self.assertTrue(
                        _position_stated_correctly(report, _FULL_REGISTRY_JSON, cut),
                        "The report does not name a position (offset, line, "
                        "or trailing fragment) that corresponds to where the "
                        f"real serializer's output was actually cut (cut={cut}). "
                        f"report={report!r}",
                    )

    def test_uninterpretable_registry_does_not_end_the_run_with_an_unhandled_failure(self):
        # covers: ACD-2100b-2
        # angle: failure
        """Implementation notes: the interpretation failure must be caught by
        type and logged at WARNING or higher before the halt -- it must not
        propagate as an unhandled failure. Both an unhandled crash and a
        recorded halt stop the run, so the run's own recorded outcome must
        actually BE the interpretation report (not a raw uncaught exception,
        and not the old permission-verdict message either) -- that is the
        only thing that tells the two apart.
        """
        with tempfile.TemporaryDirectory(prefix="acd2100b2_unhandled_") as tmp:
            repo_dir = _make_repo_fixture(
                Path(tmp), registry_content=_FULL_REGISTRY_JSON[:_CUT_A]
            )
            payload = _run_plan_feature_real(repo_dir, label_responses={}, args={})

            self.assertNotIn(
                "harness: top-level error", payload.get("_stderr") or "",
                "JSON.parse's failure on the truncated registry propagated "
                "as an unhandled top-level failure instead of being caught "
                f"and reported. stderr={payload.get('_stderr')!r}",
            )
            self.assertNotIn(
                "error", payload,
                "The harness recorded a top-level uncaught error for the "
                f"truncated-registry run: {payload.get('error')!r}",
            )

            result = payload.get("result")
            self.assertIsInstance(
                result, dict,
                f"The run's recorded outcome is not a structured halt result "
                f"(result={result!r}) -- an unhandled failure produces no "
                "usable result either.",
            )
            result_text = json.dumps(result or {}).lower()
            self.assertTrue(
                any(phrase in result_text for phrase in _UNINTERPRETABLE_PHRASES),
                "The run's recorded outcome is not the interpretation report "
                f"-- it must state that the registry was read but could not "
                f"be interpreted. result={result!r}",
            )
            for marker in _FORBIDDEN_PERMISSION_VERDICT_MARKERS:
                self.assertNotIn(
                    marker, result_text,
                    f"The run's recorded outcome contains a permission-"
                    f"verdict marker ({marker!r}) instead of the "
                    f"interpretation report. result={result!r}",
                )

    def test_acd_2100b_2_reachable_from_entry_point(self):
        # covers: ACD-2100b-2
        # angle: reachability
        """Driving the REAL workflow (via a real Node subprocess executing
        plan-feature.js's own top-level body, not by importing a helper
        function) with a truncated, on-disk registry produces the
        uninterpretable-registry report as the run's own CONSUMED,
        returned result -- and the run stops at the check: no downstream
        worktree-setup step is ever dispatched.
        """
        with tempfile.TemporaryDirectory(prefix="acd2100b2_reach_") as tmp:
            repo_dir = _make_repo_fixture(
                Path(tmp), registry_content=_FULL_REGISTRY_JSON[:_CUT_A]
            )
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
                "A step after the uninterpretable-registry check ran "
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

            result_text = json.dumps(result or {}).lower()
            self.assertTrue(
                any(phrase in result_text for phrase in _UNINTERPRETABLE_PHRASES),
                "The halted run's own observable, returned result does not "
                "state that the registry was read but could not be "
                f"interpreted. result={result!r}",
            )
            for marker in _FORBIDDEN_PERMISSION_VERDICT_MARKERS:
                self.assertNotIn(
                    marker, result_text,
                    "The halted run's own observable result contains a "
                    f"permission-verdict marker ({marker!r}). result={result!r}",
                )


if __name__ == "__main__":
    unittest.main()
