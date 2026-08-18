"""
MODULE: test_bo2400f_review_and_delivery_guarantee
GOAL: RED behavioral tests for two coupled ACs that both govern the guard region
      between the green+coverage gate and the commit dispatch in
      templates/workflows-js/fast-lane-ship.js, plus the workflow's terminal
      payload.

ACs covered:
  - BO-2400f-11: the run submits its own working diff to the existing
    pr-reviewer agent BEFORE the commit dispatch. It blocks only on findings
    pr-reviewer itself classifies high-confidence; an unobtainable verdict is
    NEVER treated as a clean review. A review-blocked run releases its own
    claims (BO-2400f-10) but opens no PR.
  - BO-2400f-4-vi: a reported success ('ok') is reachable only when no known
    required check is unsatisfied. A known-unsatisfied check forces 'blocked'
    and the blocked outcome still names the pull request it opened.

=== Why these are RED today ===
fast-lane-ship.js's phase order is currently:
  Worktree -> Resolve -> Test Writer -> Coder -> Commit -> Pull Request
There is NO review phase between Coder and Commit, and there is no single
terminal-payload construction site that enforces "ok requires zero unsatisfied
required checks." Both are the gaps these tests pin down.

=== Verify Behaviorally, Not by Grep (root CLAUDE.md) ===
Every test in the BO-2400f-11 section EXECUTES the real workflow under
unit_tests/_workflow_engine_harness.py's run_workflow_under_e2() with the
review dispatch's return value stubbed via label_responses, then asserts on
the RECORDED, EXECUTED agent_calls (presence/absence/order) — never on
fast-lane-ship.js source text. A grep-only test would pass on dead code; this
lane already shipped exactly that phantom-done defect once
(fast-lane-build.js, 2026-07-22) and BO-2400f-11's own it_requirements
constraint explicitly bars grep-only coverage for this criterion.

The BO-2400f-4-vi section executes the real pure payload-construction
function via `node` (once python-coder extracts it) rather than the full
harness: the AC's own constraint requires the covering test to "construct a
run state with a known-unsatisfied required check" directly, and the
mechanism it gates (a known-unsatisfied required check, e.g. the changelog
check) has no agent dispatch anywhere in fast-lane-ship.js today — there is
nothing to stub via label_responses. This mirrors the established pattern in
unit_tests/workflows/test_bo_2700_defer_epic_pr.py, which extracts and
executes selectDispatchPhases() the same way.

=== Harness change made alongside these tests (additive, non-breaking) ===
unit_tests/_workflow_engine_harness.py's HarnessResult gained a `.result`
field: the workflow script's own top-level `return` value (the terminal
payload), JSON-round-tripped. Previously the harness discarded the resolved
value of the wrapped async IIFE entirely — only agent_calls and
contract_violations were observable. Both BO-2400f-11 (finding text in the
terminal message; "no verdict obtained" vs "zero findings" wording) and
BO-2400f-4-vi ("status" distinguishing ok/blocked) require terminal-payload
CONTENT, not just dispatch topology, so this was a real capability gap, not
a style preference. The change is purely additive (a new dict key); the two
existing harness consumers (test_bo_2300_pause_resume.py,
test_finalize_baseline_recovery.py) were re-run and are unaffected.

=== Assumed implementation contracts (for python-coder) ===
Neither the review phase nor the payload-builder function exists yet, so
these tests necessarily assume specific, minimal, documented names for the
seams they exercise. These are NOT load-bearing on their exact spelling in
the sense of "any name will do" — they are the concrete contract these tests
constrain python-coder to implement:

  1. A new agent() dispatch between the Coder and Commit phases, with
     opts.label == "fastlane-review" and opts.agentType == "pr-reviewer".
     Its returned verdict conforms to BO-2400f-11's config_schema_fragment:
       { verdict_obtained: bool, high_findings: [str],
         medium_findings: [str], low_suppressed_count: int, message: str }
     The commit dispatch (opts.agentType == "commit") must be unreachable
     whenever verdict_obtained is not exactly true, OR high_findings is
     non-empty.

  2. On the review-blocked path, the workflow's terminal `return` sets
     failing_phase: "review" (matching the existing failing_phase vocabulary
     already used for "worktree", "resolve", "test-writer", "python-coder",
     "commit", "pull-request") and embeds the literal text of every blocking
     finding in the payload (message or an equivalent field) — not a count.

  3. On an unobtainable verdict, the payload explicitly says a verdict was
     not obtained (e.g. contains "verdict" language) and must NOT contain
     language claiming zero/no findings were found (that would misreport an
     unread review as a clean one).

  4. A pure function `buildFastLaneDeliveryOutcome(prUrl, unsatisfiedRequiredChecks)`
     is the single construction site for the terminal delivery payload
     (BO-2400f-4-vi's "one construction site, not a convention" constraint).
     It returns { status: 'ok'|'blocked', pr_url, unsatisfied_required_checks,
     message }, with status 'ok' reachable only when unsatisfiedRequiredChecks
     is empty, and pr_url always carried through (including on the blocked
     path, so the operator can act on the already-opened PR rather than
     rebuild).

If python-coder's real implementation differs in these particulars but still
satisfies the AC criteria, these tests should be adjusted alongside the
implementation (Source-of-Truth Discipline Rule 1: a failing test here is a
question, not an answer) — but the underlying BEHAVIOR asserted (unreachable
commit dispatch on a high finding; failing_phase naming review; no
zero-findings language on an unread verdict; ok-status gated on an empty
unsatisfied-checks list; pr_url always carried) is what BO-2400f-11 and
BO-2400f-4-vi actually require, independent of naming.

=== Real-artifact behavioral mandate — not applicable here ===
fast-lane-ship.js is an E2 workflow script with no direct filesystem access
(ADR-024): every side effect (git diff, git commit, gh pr create) is
performed by an LLM agent dispatch the harness mocks, not by code this test
process can execute and read back. There is no in-process durable artifact
to round-trip. This mirrors the same scoping already documented in
test_bo_2300_pause_resume.py for the sibling pause/resume feature.

=== Fixture-authenticity mandate (BO-2500c) ===
No hand-typed copy of fast-lane-ship.js content is embedded as a fixture.
The BO-2400f-11 tests execute the REAL on-disk file via run_workflow_under_e2.
The BO-2400f-4-vi tests extract the REAL on-disk function text (once it
exists) via brace-counting, exactly as test_bo_2700_defer_epic_pr.py does for
selectDispatchPhases — never a hand-typed re-implementation.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# unit_tests/ must be on sys.path so _workflow_engine_harness is importable
# from this sub-package (unit_tests/workflows/), matching the existing
# convention in test_bo_2300_pause_resume.py.
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import HarnessResult, run_workflow_under_e2  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_FAST_LANE_SHIP_JS = _REPO_ROOT / "templates" / "workflows-js" / "fast-lane-ship.js"

_TIMEOUT = 20  # seconds; all agent() calls are synchronous mocks

# The assumed label/agentType contract for the not-yet-existing review
# dispatch. See "Assumed implementation contracts" in the module docstring.
_REVIEW_LABEL = "fastlane-review"


# ---------------------------------------------------------------------------
# Green baseline label_responses — enough to drive the run all the way to the
# Commit and Pull Request phases. Every key here matches a label already
# present in fast-lane-ship.js's existing agent() dispatches.
# ---------------------------------------------------------------------------

_GREEN_LABELS: dict = {
    "fastlane-worktree": {
        "worktree_path": "/tmp/fastlane-wt-bo2400f11",
        "branch": "fast-lane/bo-stub-1",
        "ac_store_path": "/tmp/fastlane-wt-bo2400f11/docs/acceptance-criteria",
        "created": True,
    },
    "resolve-connected": {
        "ac_ids": ["BO-STUB-1"],
        "message": "1 to build",
    },
    "claim-connected": {
        "claimed": ["BO-STUB-1"],
        "excluded_claimed": [],
        "target_refused": False,
    },
    "test-writer-connected": {
        "status": "ok",
        "tests_written": ["unit_tests/test_stub.py"],
        "gate_passed": True,
        "reason": None,
        "green_at_baseline": [],
        "message": "red baseline ok",
    },
    "coder-connected": {
        "status": "ok",
        "files_modified": ["scripts/stub_impl.py"],
        "green": True,
        "coverage_ok": True,
        "uncovered_ac_ids": [],
        "message": "implementation green",
    },
    # Added when BO-2400c-1-iii wired the prompt-caching layer into the lane.
    # The context-bundle gate runs before the Test Writer phase and fails
    # closed, so an unstubbed fixture halts there and never reaches the
    # behaviour these tests are about. The harness default reply carries no
    # `obtained` key — exactly the absent case the gate must reject — so the
    # stub has to be explicit and schema-conforming, as below.
    "fastlane-context-bundle": {
        "obtained": True,
        "bundle": (
            "ARCHITECTURE (stub)\n\nCONVENTIONS (stub)\n\nHIGH-LEVEL ACS (stub)"
            "\n\n<!-- CACHE_BREAKPOINT -->\n\nBATCH ACS (stub)\n\nPRIOR TESTS (stub)"
        ),
        "message": "bundle assembled",
    },
    # The changelog phase must be stubbed with a SCHEMA-CONFORMING positive
    # reply (status ok + entry_added true). An unstubbed label falls through to
    # the harness default, whose shape is {passed: true, ...}; the changelog
    # guard deliberately does not accept that, because a bare `passed: true`
    # carries no evidence an entry was actually written. Omitting this entry
    # would make every "green run reaches commit" assertion below fail on the
    # changelog halt instead — which is what happened when this fixture was
    # first written, and was briefly papered over by a `|| passed === true`
    # escape hatch in the workflow itself before being fixed here instead.
    "fastlane-changelog": {
        "status": "ok",
        "entry_added": True,
        "entry_path": "changelogs/2026-08-18-0000-stub-entry.md",
        "message": "entry emitted",
    },
    "fastlane-commit": {
        "status": "ok",
        "branch": "fast-lane/bo-stub-1",
        "message": "committed",
    },
    "fastlane-pr": {
        "status": "ok",
        "pr_url": "https://github.com/example/repo/pull/1",
        "message": "PR opened",
    },
}

_HIGH_FINDING_VERDICT = {
    "verdict_obtained": True,
    "high_findings": [
        "SQL injection risk: unsanitised input reaches cursor.execute() in fast_lane.py:88",
    ],
    "medium_findings": [],
    "low_suppressed_count": 0,
    "message": "1 high-confidence finding",
}

_HIGH_FINDING_VERDICT_TWO = {
    "verdict_obtained": True,
    "high_findings": [
        "SQL injection risk: unsanitised input reaches cursor.execute() in fast_lane.py:88",
        "Credential leaked in log line at worktree_agent.py:41",
    ],
    "medium_findings": ["Consider extracting a helper (fast_lane.py:120)"],
    "low_suppressed_count": 2,
    "message": "2 high-confidence findings",
}

_MEDIUM_LOW_ONLY_VERDICT = {
    "verdict_obtained": True,
    "high_findings": [],
    "medium_findings": [
        "Consider extracting a helper function for readability (fast_lane.py:120)",
    ],
    "low_suppressed_count": 3,
    "message": "0 high, 1 medium, 3 low (suppressed)",
}

# Absent/unusable verdict variants (BO-2400f-11 constraint #3: fail closed on
# ANY of these — a missing key, a null, or a schema-nonconforming reply).
_ABSENT_VERDICT_VARIANTS: list = [
    {},  # empty object — no keys at all
    None,  # bare null
    {"high_findings": []},  # missing verdict_obtained entirely
]


def _run(review_response, extra_labels: dict | None = None, args: dict | None = None) -> HarnessResult:
    """Run fast-lane-ship.js under the E2 harness with the green baseline plus
    a stubbed review-dispatch response (and any additional label overrides).
    """
    labels = dict(_GREEN_LABELS)
    if extra_labels:
        labels.update(extra_labels)
    labels[_REVIEW_LABEL] = review_response
    return run_workflow_under_e2(
        _FAST_LANE_SHIP_JS,
        timeout=_TIMEOUT,
        label_responses=labels,
        args=args or {"ac": "BO-STUB-1"},
    )


def _labels(result: HarnessResult) -> list:
    return [c.label for c in result.agent_calls]


def _agent_types(result: HarnessResult) -> list:
    return [c.agent_type for c in result.agent_calls]


def _review_calls(result: HarnessResult) -> list:
    return [c for c in result.agent_calls if c.label == _REVIEW_LABEL]


# ---------------------------------------------------------------------------
# BO-2400f-11 — review before commit; block only on high-confidence findings
# ---------------------------------------------------------------------------


def test_ac11_high_confidence_finding_prevents_commit_dispatch():
    # covers: BO-2400f-11
    """A high-confidence finding stopped everything downstream of review.

    With the review dispatch stubbed to return one high-confidence finding,
    the run must record NO commit dispatch and NO pull-request dispatch.

    RED today: fast-lane-ship.js has no review phase at all, so the
    high-finding stub is never consulted and the run sails straight through
    to commit + pull-request — exactly the load-bearing absence this test
    exists to catch (a dispatch-topology test that checks for a missing
    call, not merely a present one).
    """
    result = _run(_HIGH_FINDING_VERDICT)
    assert result.error == "", f"Harness error: {result.error}"

    agent_types = _agent_types(result)
    assert "commit" not in agent_types, (
        "A high-confidence finding must prevent the commit dispatch. "
        f"Got agent_types in order: {agent_types}. Labels: {_labels(result)}"
    )
    assert "pull-request" not in agent_types, (
        "A high-confidence finding must prevent the pull-request dispatch. "
        f"Got agent_types in order: {agent_types}. Labels: {_labels(result)}"
    )


def test_ac11_blocked_outcome_names_each_high_confidence_finding():
    # covers: BO-2400f-11
    """The reported outcome names each blocking finding verbatim, not a count.

    Reads the workflow's own terminal payload (HarnessResult.result — see
    module docstring for why the harness now captures this) and asserts the
    literal text of BOTH findings appears, and that the payload identifies
    "review" as the failing phase per BO-2400f-11's own constraint that this
    criterion does not relax BO-2400f-4-vi (a review-blocked run opened no
    PR, so its outcome is a halt naming review, never an 'ok' with a
    warning).
    """
    result = _run(_HIGH_FINDING_VERDICT_TWO)
    assert result.error == "", f"Harness error: {result.error}"

    payload = result.result
    assert payload is not None, (
        "Workflow returned no terminal payload the harness could capture. "
        f"Labels: {_labels(result)}"
    )
    dumped = json.dumps(payload)

    for finding in _HIGH_FINDING_VERDICT_TWO["high_findings"]:
        assert finding in dumped, (
            f"Blocking finding text must appear verbatim in the terminal payload. "
            f"Missing: {finding!r}. Got payload: {payload}"
        )

    assert payload.get("status") != "ok", (
        f"A review-blocked run must not report status 'ok'. Got: {payload}"
    )
    assert payload.get("failing_phase") == "review", (
        "A review-blocked run's terminal payload must name 'review' as the "
        f"failing_phase (BO-2400f-11's own note: never the 'PR opened but "
        f"blocked' outcome, which asserts a PR exists). Got: {payload}"
    )


def test_ac11_medium_and_low_only_verdict_permits_commit_and_pr():
    # covers: BO-2400f-11
    """Reviewer noise (medium/low only) does not halt an otherwise-green run.

    With only medium- and low-confidence findings, both the commit and
    pull-request dispatches must occur, status must be 'ok', and the
    non-blocking medium finding must still be carried into the terminal
    payload (not silently dropped) without altering the status.
    """
    result = _run(_MEDIUM_LOW_ONLY_VERDICT)
    assert result.error == "", f"Harness error: {result.error}"

    agent_types = _agent_types(result)
    assert "commit" in agent_types, (
        f"Medium/low-only findings must not block the commit dispatch. "
        f"Got: {agent_types}. Labels: {_labels(result)}"
    )
    assert "pull-request" in agent_types, (
        f"Medium/low-only findings must not block the pull-request dispatch. "
        f"Got: {agent_types}. Labels: {_labels(result)}"
    )

    payload = result.result
    assert payload is not None, f"Missing terminal payload. Labels: {_labels(result)}"
    assert payload.get("status") == "ok", (
        f"A medium/low-only review must not change status away from 'ok'. Got: {payload}"
    )
    dumped = json.dumps(payload)
    medium_text = _MEDIUM_LOW_ONLY_VERDICT["medium_findings"][0]
    assert medium_text in dumped, (
        "Non-blocking (medium) findings must be carried into the terminal "
        f"payload without stopping the run. Missing: {medium_text!r}. Got: {payload}"
    )


def test_ac11_absent_verdict_does_not_commit():
    # covers: BO-2400f-11
    """An unreadable verdict is never treated as a clean review.

    Covers empty object, bare null, and a payload missing verdict_obtained
    entirely — all three must take the not-committed branch and the terminal
    payload must say NO VERDICT was obtained, never "0 findings" / "no
    findings" (which would misreport an unread review as a clean pass).
    This is explicitly called out as the scenario most likely to be
    implemented as a silent pass.
    """
    for variant in _ABSENT_VERDICT_VARIANTS:
        result = _run(variant)
        assert result.error == "", f"Harness error for variant {variant!r}: {result.error}"

        agent_types = _agent_types(result)
        assert "commit" not in agent_types, (
            f"Unreadable verdict {variant!r} must not permit the commit dispatch. "
            f"Got: {agent_types}. Labels: {_labels(result)}"
        )
        assert "pull-request" not in agent_types, (
            f"Unreadable verdict {variant!r} must not permit the pull-request dispatch. "
            f"Got: {agent_types}. Labels: {_labels(result)}"
        )

        payload = result.result
        assert payload is not None, (
            f"Missing terminal payload for variant {variant!r}. Labels: {_labels(result)}"
        )
        message_blob = json.dumps(payload).lower()
        assert "verdict" in message_blob, (
            f"An unreadable verdict {variant!r} must report that NO VERDICT was "
            f"obtained (the word 'verdict' must appear). Got: {payload}"
        )
        for forbidden in ("0 findings", "no findings", "zero findings", "clean review"):
            assert forbidden not in message_blob, (
                f"An unreadable verdict {variant!r} must NEVER be reported as a "
                f"clean/zero-findings review — that is the exact 'no verdict "
                f"manufactured as clean' defect BO-2400f-11 exists to prevent. "
                f"Found forbidden phrase {forbidden!r} in payload: {payload}"
            )


def test_ac11_review_dispatch_precedes_commit_in_executed_call_order():
    # covers: BO-2400f-11
    """In a fully green run, the review dispatch is EXECUTED before commit.

    Asserted on the recorded, EXECUTED call order (agent_calls index
    positions) — not on source-text ordering. A review inserted after Commit
    in the source (or never actually awaited before the commit guard reads
    it) would not satisfy this even if the string 'pr-reviewer' appears
    somewhere earlier in the file.
    """
    result = _run(_MEDIUM_LOW_ONLY_VERDICT)
    assert result.error == "", f"Harness error: {result.error}"

    labels = _labels(result)
    assert _REVIEW_LABEL in labels, (
        f"Expected the review dispatch ({_REVIEW_LABEL!r}) to actually execute "
        f"in a fully green run. Got labels: {labels}"
    )
    assert "fastlane-commit" in labels, (
        f"Expected the commit dispatch to actually execute in a fully green run "
        f"with only medium/low findings. Got labels: {labels}"
    )

    review_idx = labels.index(_REVIEW_LABEL)
    commit_idx = labels.index("fastlane-commit")
    assert review_idx < commit_idx, (
        f"The review dispatch must be EXECUTED before the commit dispatch. "
        f"review at index {review_idx}, commit at index {commit_idx}. Full order: {labels}"
    )


def test_ac11_review_dispatch_targets_the_uncommitted_worktree_diff():
    # covers: BO-2400f-11
    """The reviewer is pointed at the run's real uncommitted diff.

    The captured prompt of the executed review dispatch must direct the
    reviewer at the working diff in the run's own worktree (references the
    worktree path and a diff operation) — not at a written summary, a
    files_modified list, or the coder's self-reported message as the thing
    to review.
    """
    result = _run(_MEDIUM_LOW_ONLY_VERDICT)
    assert result.error == "", f"Harness error: {result.error}"

    reviews = _review_calls(result)
    assert len(reviews) == 1, (
        f"Expected exactly one review dispatch in a fully green run. "
        f"Got {len(reviews)}. Labels: {_labels(result)}"
    )
    prompt = reviews[0].prompt
    assert isinstance(prompt, str) and prompt.strip(), (
        f"The review dispatch prompt must be a non-empty instruction string. "
        f"Got: {type(prompt).__name__}"
    )

    worktree_path = _GREEN_LABELS["fastlane-worktree"]["worktree_path"]
    assert worktree_path in prompt, (
        f"The review prompt must reference the run's own worktree path "
        f"({worktree_path!r}) so the reviewer reads the REAL uncommitted diff "
        f"from that location. Prompt: {prompt[:400]}"
    )
    assert "diff" in prompt.lower(), (
        "The review prompt must direct the reviewer at a diff operation "
        "(the working diff), not a narrative account of the change. "
        f"Prompt: {prompt[:400]}"
    )

    # Anti-phantom: the coder's SELF-REPORTED artifacts (its fabricated
    # files_modified entry and message) must not be what is handed over as
    # the thing to review — the diff itself must be the target.
    coder_reported_file = _GREEN_LABELS["coder-connected"]["files_modified"][0]
    assert coder_reported_file not in prompt, (
        f"The review prompt must not merely hand over the coder's "
        f"self-reported files_modified entry ({coder_reported_file!r}) as the "
        f"thing to review — it must point the reviewer at the real "
        f"uncommitted diff instead. Prompt: {prompt[:400]}"
    )


def test_ac11_review_blocked_run_releases_its_own_claims():
    # covers: BO-2400f-11
    """A review-blocked run still releases the ACs it claimed (BO-2400f-10).

    Without this, the connected set is stranded in_progress after a
    review-blocked run — no concurrent run and no retry can pick it up.
    Asserted on the actually-dispatched release invocation (the same
    `release --ac-ids ... --ac-root ...` command every other pre-commit halt
    branch already issues), not merely on the run halting.
    """
    result = _run(_HIGH_FINDING_VERDICT)
    assert result.error == "", f"Harness error: {result.error}"

    release_calls = [
        c
        for c in result.agent_calls
        if isinstance(c.prompt, str) and "release --ac-ids" in c.prompt
    ]
    assert release_calls, (
        "A review-blocked run must dispatch a release invocation "
        "('release --ac-ids ... --ac-root ...') for the ACs it claimed, "
        "exactly as every other pre-commit halt branch does (BO-2400f-10) — "
        "otherwise the connected set is stuck in_progress forever. "
        f"No matching prompt found. Labels: {_labels(result)}"
    )

    # The release must actually be reachable from the review-blocked branch,
    # i.e. it must occur AFTER the review dispatch executed.
    labels = _labels(result)
    assert _REVIEW_LABEL in labels, (
        f"Expected the review dispatch to execute before any release-on-review "
        f"path could be taken. Got labels: {labels}"
    )
    review_idx = labels.index(_REVIEW_LABEL)
    release_idx = next(
        i for i, c in enumerate(result.agent_calls)
        if isinstance(c.prompt, str) and "release --ac-ids" in c.prompt
    )
    assert release_idx > review_idx, (
        f"The release dispatch must follow the review dispatch that blocked "
        f"the run. review at index {review_idx}, release at index {release_idx}. "
        f"Full order: {labels}"
    )


# ---------------------------------------------------------------------------
# BO-2400f-4-vi — 'ok' is reachable only when no required check is known-
# unsatisfied; the invariant lives at ONE terminal-payload construction site.
# ---------------------------------------------------------------------------
#
# The mechanism this AC gates (a known-unsatisfied required check, e.g. the
# changelog-presence check) has no agent() dispatch anywhere in
# fast-lane-ship.js today, so there is nothing to stub via label_responses.
# The AC's own constraint requires the covering test to "construct a run
# state" directly — so these tests extract and execute the real pure
# function once python-coder writes it, exactly as
# test_bo_2700_defer_epic_pr.py does for selectDispatchPhases().


def _extract_function(source: str, name: str) -> str:
    """Extract a top-level `function <name>(...) { ... }` by brace-counting.

    Mirrors the identical helper in test_bo_2700_defer_epic_pr.py — kept as
    a local copy (not imported) per the instruction to touch no other test
    file, and because this is a small, self-contained, already-established
    repo pattern rather than shared production logic.
    """
    try:
        start = source.index(f"function {name}(")
    except ValueError as exc:
        raise AssertionError(
            f"fast-lane-ship.js does not define `function {name}(...)` yet. "
            f"This is the RED state for BO-2400f-4-vi: the single terminal-"
            f"payload construction site does not exist. See the "
            f"'Assumed implementation contracts' section of this test file's "
            f"module docstring for the required signature and return shape."
        ) from exc
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
    raise AssertionError(f"could not extract function {name} — unbalanced braces")


def _run_delivery_outcome(pr_url, unsatisfied_required_checks) -> dict:
    """Extract buildFastLaneDeliveryOutcome from the real on-disk source and
    execute it via node with the given arguments, returning the parsed JSON
    result.
    """
    source = _FAST_LANE_SHIP_JS.read_text(encoding="utf-8")
    func_src = _extract_function(source, "buildFastLaneDeliveryOutcome")

    driver = (
        func_src
        + "\nconsole.log(JSON.stringify(buildFastLaneDeliveryOutcome("
        + "JSON.parse(process.argv[2]), JSON.parse(process.argv[3]))));\n"
    )
    with tempfile.NamedTemporaryFile(
        "w", suffix=".mjs", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(driver)
        path = fh.name
    try:
        proc = subprocess.run(
            ["node", path, json.dumps(pr_url), json.dumps(unsatisfied_required_checks)],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )
    finally:
        Path(path).unlink(missing_ok=True)
    return json.loads(proc.stdout.strip())


class TestAc4viDeliveryOutcomeInvariant(unittest.TestCase):
    """Executes the real buildFastLaneDeliveryOutcome() function via node.

    RED today: the function does not exist. _extract_function() raises
    AssertionError naming the missing function — the intended red state.
    """

    def test_ac4vi_success_payload_requires_no_unsatisfied_required_check(self) -> None:
        # covers: BO-2400f-4-vi
        """The terminal payload reports 'ok' only when the unsatisfied-checks
        list is empty."""
        payload = _run_delivery_outcome(
            "https://github.com/example/repo/pull/1", []
        )
        self.assertEqual(
            payload.get("status"),
            "ok",
            f"status must be 'ok' when unsatisfied_required_checks is empty. Got: {payload}",
        )

    def test_ac4vi_known_failing_required_check_reports_blocked_not_ok(self) -> None:
        # covers: BO-2400f-4-vi
        """A known-unsatisfied required check forces 'blocked', names the
        check, and must NOT report 'ok' with a warning appended."""
        check_name = "changelog entry present"
        payload = _run_delivery_outcome(
            "https://github.com/example/repo/pull/1", [check_name]
        )
        self.assertNotEqual(
            payload.get("status"),
            "ok",
            f"status must not be 'ok' when a required check is known-unsatisfied "
            f"— an 'ok' payload with a warning bolted on is the exact failure "
            f"mode this AC exists to prevent. Got: {payload}",
        )
        self.assertEqual(
            payload.get("status"),
            "blocked",
            f"status must be exactly 'blocked' (distinguishable from an "
            f"unrelated halt — the work IS committed and the PR DOES exist). "
            f"Got: {payload}",
        )
        dumped = json.dumps(payload)
        self.assertIn(
            check_name,
            dumped,
            f"The blocked payload must name the specific unsatisfied check "
            f"({check_name!r}), not a bare 'blocked' with no detail. Got: {payload}",
        )

    def test_ac4vi_blocked_outcome_names_the_pull_request(self) -> None:
        # covers: BO-2400f-4-vi
        """The blocked outcome still carries the pull request it opened, so
        the operator's next action is to satisfy the named check — not to
        rebuild from scratch."""
        pr_url = "https://github.com/example/repo/pull/42"
        payload = _run_delivery_outcome(pr_url, ["changelog entry present"])
        self.assertEqual(
            payload.get("pr_url"),
            pr_url,
            f"A blocked outcome must still carry the pull request url it "
            f"opened (work is committed, PR exists — the fix is to satisfy "
            f"the named check, not to rebuild). Got: {payload}",
        )


if __name__ == "__main__":
    unittest.main()
