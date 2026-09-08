"""
MODULE: test_acd_2100c_1
GOAL: Behavioral, RED-baseline tests for ACD-2100c-1 -- "Every decision the
    route records as the user's is put to the user and to no agent."

BACKGROUND (KI-ACD-005, docs/known-issues/ac-driven-dev.md; ADR-024
    docs/architecture/adrs/ADR-024-interactive-pause-resume.md): the E2 engine
    has no `prompt()` primitive, so every one of plan-feature.js's five
    human-decision points is modelled today as a LIVE `agent()` dispatch to
    `status-checker`, asking it to relay a question to a human and return an
    answer:

      1. resolve-orphans-choice  (line ~841)  -- stranded drafts from a prior run.
      2. covered-route-gate      (line ~1913) -- request already covered by an AC.
      3. pt-gate-<stage>         (line ~2067) -- approve a drafted product-truth artifact.
      4. gate-<stage>            (line ~2361) -- approve a mid-pipeline authoring stage.
      5. final-gate              (line ~2458) -- final approval.

    Four of the five (everything but resolve-orphans-choice) are already
    wrapped in the ADR-024 `resolveGate()` / `pauseAtGate()` substrate, which
    checks `args.resume_answer` first and, when the live gate dispatch cannot
    produce a genuine (non-refusal) decision, pauses and persists a
    resumable record. The DEFECT this AC targets is narrower than "no
    substrate exists": `resolveGate()` still ATTEMPTS the live dispatch
    before falling back to pause -- that attempt's whole purpose is to
    obtain a human answer from an agent, which is exactly what the AC
    forbids ("no dispatch whose purpose was to obtain an answer to any of
    the five"). `resolveOrphanedDrafts()` (site 1) does not even have the
    pause/resume substrate: it dispatches "resolve-orphans-choice" directly
    and treats whatever comes back as the final word -- no pause path at
    all today.

    Verified empirically against this branch, HEAD, via ad-hoc harness runs
    before writing these assertions (see the specific `label_responses`
    shapes below, each confirmed to reach the named gate and, in the
    "answered directly" variant, to observably let the run proceed past it
    without any `args.resume_answer` ever being supplied):
      - Headless (no gate-label answer, verify-ok override): all four
        resolveGate() sites already resolve to a clean
        `{"status": "paused_awaiting_input", "gate_id": <id>}` -- but WITHOUT
        the actual question content (no "question" key at all) and WITHOUT
        ever having skipped the live dispatch (the gate-answer label is
        still present in the dispatch record). resolve-orphans-choice has no
        such state at all and instead returns `{"status": "error", ...}`.
      - Answered directly at the gate-answer label (never via
        `args.resume_answer`): all five currently let the run keep going
        (covered-route-gate resolves to `status: "ok"`; gate-po and
        pt-gate-mockdata dispatch "branch-check" trying to commit;
        resolve-orphans-choice drives the ENTIRE rest of the pipeline all
        the way to final-gate; final-gate dispatches "apply-approval").
      - A synthetic SIXTH gate id, driven directly against the real
        `resolveGate()` extracted from this file's own source (never a
        hand-typed stand-in), makes the exact same live dispatch attempt as
        every one of the five hardcoded sites -- proving the guard, as it
        stands today, is NOT on the class; a new call site inherits nothing.

FIX DIRECTION (per KI-ACD-005 and this AC's own it_requirements): "Gates
    must not be answered by an agent. Either surface them to the real user,
    or persist a pause record and exit with a status that says 'awaiting
    input'." In this sandboxed E2 body the ONLY channel that reaches the
    person running the route -- the caller (the /plan-feature skill, running
    in the human's own interactive session) -- is the workflow's OWN
    terminal return value; there is no other I/O surface available to it.
    So "the question is put on the channel that reaches the person" is
    operationalised here as: the run's terminal payload, at each decision
    point, carries the actual question content (a `question` object with a
    non-empty `prompt`, a declared `type`, and a non-empty `options` list --
    the exact shape `pauseAtGate()` already builds internally today, just
    never returns) -- not merely a bare `gate_id`/`status` pair that a
    caller would have to separately look up.

TEST STRATEGY: drive the REAL, on-disk plan-feature.js via
    run_workflow_under_e2() (the real workflow-runner entry point; see
    `_workflow_engine_harness.py`'s own "reachability" convention, used
    throughout unit_tests/workflows/) for the criterion and reachability
    angles (tests 1-3). The boundary angle (test 4) additionally extracts
    the REAL `resolveGate()`/`pauseAtGate()` machinery verbatim from the
    on-disk source (brace-counted extraction, mirroring
    unit_tests/workflows/test_tkt_600b_4.py's own `_extract_function`
    convention) and drives it directly with a gate id that is NOT one of
    the five hardcoded sites, to prove the fix lives in the shared
    mechanism itself rather than in five per-site edits.

TICKET: 13_TICKET-20260826-ACD-2100c-1.md
AC: ACD-2100c-1
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# unit_tests/ must be on sys.path so _workflow_engine_harness is importable
# from this sub-package (unit_tests/workflows/), mirroring every other file
# in this directory (test_bo_2300_pause_resume.py, test_acd_2100b_5.py, ...).
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PLAN_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"

_TIMEOUT = 30  # seconds; all agent() calls are synchronous mocks.

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

# Makes resolveGate()'s / pauseAtGate()'s own persist-verification read-back
# succeed, so a headless run resolves to the CLEAN `paused_awaiting_input`
# state rather than `pause_persist_failed` (a harness artifact: the mocked
# "pause-persist"/"pause-persist-verify" agent calls cannot really write a
# file, so without this override every pause looks like a verify failure --
# see test_bo_2300_pause_resume.py's own `_pause_record()` helper, which
# reads the SAME real record shape this override supplies).
_PERSIST_VERIFY_OK = {
    "pause-persist-verify": {"exists": True, "stale": False, "record": {"run_id": "default-run"}},
}

_PT_CLASSIFY_MOCKDATA_ONLY = {
    "needs_mock_data": True,
    "needs_mockup": False,
    "needs_flow": False,
    "outcome": "mock-data-only",
    "component": "test-component",
    "entities": [],
}

_PT_STORE_PRESENT = {"output": "present", "exit_code": 0}

_TRIAGE_COVERED = {"route": "covered", "existing_acs": ["FOO-1"], "rationale": "already covered"}
_TRIAGE_STRATEGIC = {"route": "strategic", "existing_acs": [], "rationale": "net-new strategic ask"}

_ORPHAN_GIT_STATUS = {
    "output": "?? docs/acceptance-criteria/ac-driven-dev/ACD-9999.yaml\n",
    "exit_code": 0,
}
_ORPHAN_FILE_CONTENT = {
    "content": "id: ACD-9999\norigin_agent: business-analyst\nreadiness: draft\n",
}

# One entry per decision point named in the AC's own criteria. `gate_id` is
# the CURRENT gate-answer label (the one whose PURPOSE is "obtain an
# answer" and which this AC requires be dispatched never again).
# `label_responses` drives the run to that gate WITHOUT ever answering the
# gate itself (the "channel open, no real answer yet" baseline used by
# tests 1 and 2). `direct_answer_label_responses` additionally answers the
# gate-answer label directly -- never via `args.resume_answer` -- with a
# decisive-looking reply, used by test 3 to prove that answering the
# soon-to-be-removed dispatch must NOT count as an answer having "arrived
# on the channel".
SCENARIOS = [
    {
        "key": "orphan_resolution",
        "description": "deciding what to do with stranded drafts from an earlier run",
        "gate_id": "resolve-orphans-choice",
        "label_responses": {
            "scan-orphans-git-status": _ORPHAN_GIT_STATUS,
            "scan-orphans-read-file": _ORPHAN_FILE_CONTENT,
        },
        "direct_answer_label_responses": {
            "scan-orphans-git-status": _ORPHAN_GIT_STATUS,
            "scan-orphans-read-file": _ORPHAN_FILE_CONTENT,
            "resolve-orphans-choice": {"choice": "discard"},
        },
        # Empirically: answering "discard" directly drives the ENTIRE rest of
        # the pipeline all the way to final-gate -- the strongest available
        # proof that the orphan decision was not actually gated on a real
        # channel answer.
        "advance_markers": ["final-gate"],
    },
    {
        "key": "covered_route",
        "description": "choosing how to proceed when the request looks already covered",
        "gate_id": "covered-route-gate",
        "label_responses": {"stage-0-triage": _TRIAGE_COVERED},
        "direct_answer_label_responses": {
            "stage-0-triage": _TRIAGE_COVERED,
            "covered-route-gate": {"choice": "cancel", "rationale": "existing ACs suffice"},
        },
        # Answering "cancel" directly returns a clean `status: "ok"` with no
        # further dispatch at all -- there is no "next" label to check for
        # absence, so this scenario is asserted via the terminal status
        # instead (see test 3's special-case branch below).
        "advance_markers": None,
    },
    {
        "key": "product_truth_gate",
        "description": "approving a drafted product-truth artifact",
        "gate_id": "pt-gate-mockdata",
        "label_responses": {
            "pt-classify": _PT_CLASSIFY_MOCKDATA_ONLY,
            "pt-store-check": _PT_STORE_PRESENT,
        },
        "direct_answer_label_responses": {
            "pt-classify": _PT_CLASSIFY_MOCKDATA_ONLY,
            "pt-store-check": _PT_STORE_PRESENT,
            "pt-gate-mockdata": {"action": "approve"},
        },
        # Empirically: an "approve" answer dispatches "branch-check" trying
        # to commit the drafted artifact.
        "advance_markers": ["branch-check"],
    },
    {
        "key": "mid_pipeline_gate",
        "description": "approving the mid-pipeline authoring stage",
        "gate_id": "gate-po",
        "label_responses": {"stage-0-triage": _TRIAGE_STRATEGIC},
        "direct_answer_label_responses": {
            "stage-0-triage": _TRIAGE_STRATEGIC,
            "gate-po": {"action": "approve"},
        },
        # Empirically: an "approve" answer dispatches "branch-check" trying
        # to commit the product-owner's stage output.
        "advance_markers": ["branch-check"],
    },
    {
        "key": "final_gate",
        "description": "giving final approval",
        "gate_id": "final-gate",
        "label_responses": {},
        "direct_answer_label_responses": {"final-gate": {"action": "approve", "priority": "high"}},
        # Empirically: an "approve" answer dispatches "apply-approval".
        "advance_markers": ["apply-approval"],
    },
]

_ALL_GATE_IDS = [scenario["gate_id"] for scenario in SCENARIOS]


# ---------------------------------------------------------------------------
# Tests 1-3: drive the REAL plan-feature.js via the real workflow-runner
# entry point (run_workflow_under_e2), one scenario per decision point.
# ---------------------------------------------------------------------------


class TestFiveDecisionPointsAreOnTheUserChannel(unittest.TestCase):

    def test_each_of_the_five_decision_points_is_put_on_the_user_channel(self):
        # covers: ACD-2100c-1
        # angle: criterion
        """AC: "the question is put on the channel that reaches the person
        running the route." In this sandboxed E2 body the run's own terminal
        return value is the ONLY channel back to its caller (the
        /plan-feature skill, running in the human's own session) -- so the
        question itself (not merely a bare gate_id) must be observable there.

        RED today: every one of the five decision points' terminal payload,
        when reached without any live-gate answer, carries no `question`
        object at all (verified empirically: `{"status":
        "paused_awaiting_input", "run_id": ..., "gate_id": ...}` for the four
        resolveGate() sites; `{"status": "error", ...}` with no gate_id at
        all for resolve-orphans-choice).
        """
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario["key"]):
                label_responses = dict(scenario["label_responses"])
                label_responses.update(_PERSIST_VERIFY_OK)
                result = run_workflow_under_e2(
                    _PLAN_FEATURE_JS, timeout=_TIMEOUT, label_responses=label_responses
                )
                self.assertEqual(result.error, "", f"Harness error: {result.error}")

                terminal = result.result
                self.assertIsInstance(
                    terminal,
                    dict,
                    f"[{scenario['key']}] Reaching the '{scenario['gate_id']}' decision "
                    f"point must return a structured payload naming the question -- "
                    f"got {terminal!r}. Dispatched labels: "
                    f"{[c.label for c in result.agent_calls]}",
                )
                self.assertEqual(
                    terminal.get("gate_id"),
                    scenario["gate_id"],
                    f"[{scenario['key']}] Terminal payload does not name the decision "
                    f"point it is awaiting an answer for. terminal={terminal!r}",
                )
                self.assertEqual(
                    terminal.get("status"),
                    "paused_awaiting_input",
                    f"[{scenario['key']}] Reaching '{scenario['description']}' without a "
                    f"real channel answer must leave the run awaiting input, never "
                    f"resolve as though a decision had been made. terminal={terminal!r}",
                )

                question = terminal.get("question")
                self.assertIsInstance(
                    question,
                    dict,
                    f"[{scenario['key']}] Terminal payload for '{scenario['gate_id']}' "
                    f"carries no 'question' object. The run's only channel back to the "
                    f"person running the route IS this returned payload -- it must name "
                    f"what is being asked, not merely that something is pending. "
                    f"terminal={terminal!r}",
                )
                prompt = question.get("prompt") if isinstance(question, dict) else None
                self.assertTrue(
                    isinstance(prompt, str) and prompt.strip(),
                    f"[{scenario['key']}] question.prompt must be a non-empty string a "
                    f"human could actually read and answer. question={question!r}",
                )
                options = question.get("options") if isinstance(question, dict) else None
                self.assertTrue(
                    isinstance(options, list) and len(options) >= 1,
                    f"[{scenario['key']}] question.options must be a non-empty list of "
                    f"choices. question={question!r}",
                )
                qtype = question.get("type") if isinstance(question, dict) else None
                self.assertIn(
                    qtype,
                    ("single_choice", "priority_choice", "free_text"),
                    f"[{scenario['key']}] question.type must declare one of the answer "
                    f"shapes ADR-024 validates. question={question!r}",
                )

    def test_no_dispatch_is_made_to_obtain_an_answer_to_any_of_the_five(self):
        # covers: ACD-2100c-1
        # angle: reachability
        """AC: "the run's own record of every dispatch it made contains no
        dispatch whose purpose was to obtain an answer to any of the five."

        Read from the RUN'S OWN DISPATCH RECORD (`result.agent_calls`,
        captured by driving the real, on-disk plan-feature.js through the
        real workflow-runner entry point, `run_workflow_under_e2`) -- never
        from the workflow source. A source-scan for the absence of a label
        string would pass on a fix that keeps the dispatching helper defined
        but merely stops invoking it from one call site while another still
        calls it; only the run's OWN record proves nothing was actually
        dispatched.

        RED today: every scenario's dispatch record contains a call whose
        label IS that scenario's `gate_id` -- the exact live-gate-answer
        dispatch this AC forbids (verified empirically for all five).
        """
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario["key"]):
                result = run_workflow_under_e2(
                    _PLAN_FEATURE_JS, timeout=_TIMEOUT, label_responses=scenario["label_responses"]
                )
                self.assertEqual(result.error, "", f"Harness error: {result.error}")

                labels = [c.label for c in result.agent_calls]
                for gate_id in _ALL_GATE_IDS:
                    self.assertNotIn(
                        gate_id,
                        labels,
                        f"[{scenario['key']}] The run's own dispatch record contains a "
                        f"call labelled '{gate_id}' while reaching "
                        f"'{scenario['gate_id']}' ({scenario['description']}) -- no "
                        f"dispatch anywhere in this run may exist whose purpose is to "
                        f"obtain an answer to any of the five. Dispatched labels: {labels}",
                    )

    def test_run_does_not_advance_past_a_decision_point_before_an_answer_arrives(self):
        # covers: ACD-2100c-1
        # angle: criterion
        """AC: "the run does not move past any of the five until an answer
        has arrived on that channel." The channel is `args.resume_answer`
        (the ADR-024 resume mechanism); a reply to the (soon-to-be-removed)
        gate-answer dispatch itself is NOT an answer having "arrived on the
        channel" -- it is the very agent-mediated relay this AC eliminates.

        Answers the CURRENT gate-answer label directly, with NO
        `args.resume_answer` ever supplied, and asserts the run does not
        visibly keep going as though a real decision had been made.

        RED today: every scenario's dispatch record shows the run advancing
        (verified empirically: covered-route-gate resolves to a clean
        `status: "ok"`; the other four dispatch a concrete "next step" label
        that only fires once a decision has been applied).
        """
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario["key"]):
                result = run_workflow_under_e2(
                    _PLAN_FEATURE_JS,
                    timeout=_TIMEOUT,
                    label_responses=scenario["direct_answer_label_responses"],
                )
                self.assertEqual(result.error, "", f"Harness error: {result.error}")
                labels = [c.label for c in result.agent_calls]

                if scenario["advance_markers"] is None:
                    # covered-route-gate: a direct "cancel" reply resolves the
                    # whole run immediately with no further dispatch to check
                    # for absence -- the terminal status itself is the tell.
                    terminal = result.result
                    self.assertIsInstance(terminal, dict, f"[{scenario['key']}] terminal={terminal!r}")
                    self.assertNotEqual(
                        terminal.get("status"),
                        "ok",
                        f"[{scenario['key']}] The '{scenario['gate_id']}' decision "
                        f"resolved as though a real decision had arrived on the "
                        f"channel, but no args.resume_answer was ever supplied -- only "
                        f"a direct reply to the gate-answer dispatch itself. "
                        f"terminal={terminal!r} labels={labels}",
                    )
                else:
                    for marker in scenario["advance_markers"]:
                        self.assertNotIn(
                            marker,
                            labels,
                            f"[{scenario['key']}] The run advanced past the "
                            f"'{scenario['gate_id']}' decision point (dispatched "
                            f"'{marker}') even though no answer ever arrived via "
                            f"args.resume_answer -- only a direct reply to the "
                            f"gate-answer dispatch itself. labels={labels}",
                        )


# ---------------------------------------------------------------------------
# Test 4: the guard must be on the CLASS, not on a list of five.
# ---------------------------------------------------------------------------
#
# Extracts the REAL resolveGate()/pauseAtGate() machinery verbatim from the
# on-disk plan-feature.js (brace-counted, never a hand-typed stand-in --
# Fixture Authenticity Rule 2h.2), and drives it directly with a gate id
# that is NOT one of the five hardcoded call sites, exactly the way a future
# sixth call site would: by calling resolveGate() the ordinary way, with its
# own liveGateFn that -- like every one of today's five sites -- dispatches
# an agent() to try to obtain the answer. If the fix lives in the class
# (resolveGate() itself no longer ever invoking that dispatch, for ANY gate
# id), this liveGateFn's own dispatch must never fire, with no per-site
# opt-out required by the new caller. If the fix were instead five per-site
# patches, this synthetic sixth caller would inherit nothing, and the
# dispatch would still fire -- exactly as it does today.


def _extract_function(source: str, name: str) -> str:
    """Extract a top-level `function <name>(...) { ... }` (or `async
    function <name>(...) { ... }`) by brace-counting.

    Mirrors the identically-named helper in
    unit_tests/workflows/test_tkt_600b_4.py -- a self-contained copy, per
    this directory's own convention (E2 workflow scripts cannot be imported
    as modules, so every file that needs a piece of one extracts it fresh).
    """
    for marker in (f"async function {name}(", f"function {name}("):
        idx = source.find(marker)
        if idx != -1:
            start = idx
            break
    else:
        raise AssertionError(f"could not find function {name} in plan-feature.js")
    brace = source.index("{", start)
    depth = 0
    i = brace
    while i < len(source):
        ch = source[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source[start : i + 1]
        i += 1
    raise AssertionError(f"could not extract function {name}: unbalanced braces")


def _extract_const_array(source: str, name: str) -> str:
    """Extract a top-level `const <name> = [ ... ];` by bracket-counting."""
    marker = f"const {name} = ["
    start = source.index(marker)
    open_idx = source.index("[", start)
    depth = 0
    i = open_idx
    while i < len(source):
        ch = source[i]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                if end < len(source) and source[end] == ";":
                    end += 1
                return source[start:end]
        i += 1
    raise AssertionError(f"could not extract const array {name}: unbalanced brackets")


def _assemble_gate_machinery_source() -> str:
    """Read the REAL, on-disk plan-feature.js and extract the exact,
    verbatim source of every function resolveGate()/pauseAtGate() transitively
    call, in dependency order.
    """
    source = _PLAN_FEATURE_JS.read_text(encoding="utf-8")
    pieces = [
        _extract_function(source, "parseAgentJson"),
        _extract_function(source, "validateAnswerShape"),
        _extract_function(source, "applyAnswerByType"),
        _extract_const_array(source, "AGENT_REFUSAL_MARKERS"),
        _extract_function(source, "isAgentRefusal"),
        _extract_function(source, "_buildRepoRootResolutionSnippet"),
        _extract_function(source, "buildPauseStoreCommand"),
        _extract_function(source, "pauseAtGate"),
        _extract_function(source, "resolveGate"),
    ]
    return "\n\n".join(pieces)


_SIXTH_GATE_ID = "a-newly-added-decision-gate"


def _run_resolve_gate_with_sixth_gate_id() -> dict:
    """Build and run a standalone Node driver: the REAL resolveGate()
    machinery (extracted verbatim above) plus a mock `agent()`/`log()`, then
    call resolveGate() directly with `_SIXTH_GATE_ID` -- a gate id that
    exists in NO call site in plan-feature.js today -- using a liveGateFn
    that dispatches an agent() exactly the way every one of the five
    hardcoded sites' own liveGateFn does.

    Returns: {"calls": [...], "result": <resolveGate's return value>}
    """
    machinery = _assemble_gate_machinery_source()
    driver = (
        "'use strict';\n"
        "const __capturedCalls__ = [];\n"
        "async function agent(promptOrOpts, opts) {\n"
        "  var label = opts && opts.label;\n"
        "  __capturedCalls__.push({ prompt: promptOrOpts, opts: opts || null });\n"
        f"  if (label === {json.dumps(_SIXTH_GATE_ID)}) {{\n"
        "    // Simulates a live status-checker relay actually succeeding with\n"
        "    // a well-formed, non-refusal answer -- proving that even a SUCCESSFUL\n"
        "    // live reply must never be reachable for a gate id resolveGate() has\n"
        "    // never seen before.\n"
        "    return { action: 'approve' };\n"
        "  }\n"
        "  if (label === 'pause-persist-verify') {\n"
        "    return { exists: true, stale: false, record: { run_id: 'test-run-sixth' } };\n"
        "  }\n"
        "  return { status: 'ok' };\n"
        "}\n"
        "function log(msg) {}\n\n"
        + machinery
        + "\n\n"
        "(async function () {\n"
        "  const result = await resolveGate(\n"
        f"    {json.dumps(_SIXTH_GATE_ID)},\n"
        "    async () => {\n"
        "      const raw = await agent(\n"
        "        'Ask the user something new for a hypothetical sixth decision point.',\n"
        f"        {{ agentType: 'status-checker', label: {json.dumps(_SIXTH_GATE_ID)} }}\n"
        "      );\n"
        "      return (raw && typeof raw.action === 'string') ? raw : null;\n"
        "    },\n"
        "    {},\n"
        "    { info: 'context for a newly added decision point' },\n"
        "    { type: 'single_choice', options: ['approve', 'cancel'] },\n"
        "    'test-run-sixth'\n"
        "  );\n"
        "  process.stdout.write(JSON.stringify({ calls: __capturedCalls__, result: result }));\n"
        "})();\n"
    )

    with tempfile.NamedTemporaryFile(
        "w", suffix=".js", prefix="acd2100c1_sixth_gate_", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(driver)
        path = Path(fh.name)

    try:
        proc = subprocess.run(
            ["node", str(path)], capture_output=True, text=True, timeout=_TIMEOUT
        )
    finally:
        path.unlink(missing_ok=True)

    if not proc.stdout.strip():
        raise AssertionError(
            "sixth-gate driver produced no stdout at all.\n"
            f"returncode={proc.returncode}\nstderr={proc.stderr[:2000]!r}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"sixth-gate driver produced non-JSON stdout: {exc}\n"
            f"stdout={proc.stdout[:2000]!r}\nstderr={proc.stderr[:2000]!r}"
        ) from exc


class TestSixthDecisionPointInheritsTheRule(unittest.TestCase):

    def test_a_newly_added_human_decision_point_inherits_the_rule(self):
        # covers: ACD-2100c-1
        # angle: boundary
        """AC: "A sixth human-decision point introduced into the run is put
        on the user channel and produces no dispatch, without any per-site
        registration -- the guard is on the class, not on a list of five."

        Drives the REAL resolveGate()/pauseAtGate() machinery (extracted
        verbatim from the on-disk plan-feature.js) directly with a gate id
        that exists in no call site today, via a liveGateFn that dispatches
        an agent() to try to obtain the answer -- exactly the pattern every
        one of the five hardcoded sites uses. If the fix is class-wide, this
        dispatch must never fire for ANY gate id, with nothing new required
        of the caller.

        RED today (verified empirically): resolveGate() calls the supplied
        liveGateFn unconditionally, the mocked agent() dispatch fires and
        succeeds, and resolveGate() returns that live answer verbatim
        (`{"action": "approve"}`) -- proving today's guard, such as it is,
        does not generalize past the five sites it happens to be wired into.
        """
        payload = _run_resolve_gate_with_sixth_gate_id()

        sixth_gate_calls = [
            c for c in payload.get("calls", [])
            if isinstance(c.get("opts"), dict) and c["opts"].get("label") == _SIXTH_GATE_ID
        ]
        self.assertEqual(
            sixth_gate_calls,
            [],
            f"resolveGate() dispatched an agent() call whose purpose was to obtain "
            f"an answer for a decision point it has never seen before "
            f"({_SIXTH_GATE_ID!r}) -- the guard must be on resolveGate() itself, "
            f"not on a list of five known gate ids. calls={payload.get('calls')}",
        )

        result = payload.get("result")
        self.assertIsInstance(
            result,
            dict,
            f"A newly added decision point must still be put on the user channel "
            f"(a structured, question-carrying payload), not silently dropped. "
            f"result={result!r}",
        )
        self.assertEqual(
            result.get("gate_id"),
            _SIXTH_GATE_ID,
            f"Terminal payload does not name the new decision point. result={result!r}",
        )
        self.assertEqual(
            result.get("status"),
            "paused_awaiting_input",
            f"A newly added decision point must await a real channel answer, "
            f"never resolve as though the (removed) live dispatch had answered "
            f"it. result={result!r}",
        )
        question = result.get("question") if isinstance(result, dict) else None
        self.assertIsInstance(
            question,
            dict,
            f"The new decision point's question must be present in the terminal "
            f"payload -- the only channel back to the person running the route. "
            f"result={result!r}",
        )
        self.assertTrue(
            isinstance(question.get("prompt"), str) and question.get("prompt").strip(),
            f"question.prompt must be a non-empty string. question={question!r}",
        )


if __name__ == "__main__":
    unittest.main()
