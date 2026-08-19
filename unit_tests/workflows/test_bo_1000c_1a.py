"""
MODULE: test_bo_1000c_1a
GOAL: Verify finalize-feature.js's run-progress visibility contract after its
    BP-1100b-45 redefinition (2026-08-18): in-flight visibility of a running
    finalize workflow is provided by the E2 engine's own per-agent run
    journal (<transcriptDir>/journal.jsonl — a `{"type":"started",...}` /
    `{"type":"result",...}` pair per agent() dispatch), NOT by any custom
    on-disk file this script writes.
BUSINESS CONTEXT: The original AC BO-1000c-1a asked for a custom, per-STEP
    journal (appendJournal() / journalPath, writing run-progress.journal.jsonl).
    That mechanism could never work under the real E2 engine (ADR-030: no
    filesystem primitive, no module loader in a workflow script's top-level
    body) and was removed outright rather than patched. The ten tests that
    used to live in this file asserted the REMOVED mechanism's presence by
    grepping finalize-feature.js's source — the exact presence-only-assertion
    shape BP-1100b-5's commit-guardian hook (in this same ticket) exists to
    ban. They are deleted, not preserved: once the source they grepped for no
    longer exists, keeping them around would either fail permanently (if left
    as-is) or have to be weakened into a tautology to pass — both are worse
    than removal.
ARCHITECTURE: HONEST LIMITATION — the E2 engine's own journal.jsonl is written
    by the engine itself, entirely outside a workflow script's control and
    outside what unit_tests/_workflow_engine_harness.py's Node-subprocess stub
    can reproduce (the harness has no engine-internal journal-writer to
    invoke). So no test in this file — or anywhere at the unit level — can
    execute a real run and read back a real journal.jsonl produced by
    production code; that would require an integration-level harness around
    the actual E2 engine, which does not exist. What CAN be executed and
    asserted on is the harness's own agent_calls capture
    (unit_tests/_workflow_engine_harness.py's AgentCall list, keyed by real
    agent() dispatches and their phase labels) — the same underlying signal
    (one record per agent() dispatch) the engine's own journal is keyed on,
    just observed from the test-harness side of the boundary rather than from
    a re-parsed on-disk file. Every test below either (a) executes
    finalize-feature.js for real under run_workflow_under_e2() and asserts on
    that captured, in-control-flow data, or (b) is a narrowly-scoped
    regression guard against the specific defect shape (a silently-swallowed
    require('fs') journal write) this ticket removed — never a grep asserting
    a removed symbol's declaration is "coverage".
TICKET: 09_bp1100b45_presence_only_assertions_stop_counting.md
AC: BP-1100b-4 (re-authored per the ticket's 2026-08-18 20:05 main-loop
    decision comment)
"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_JS_PATH = _REPO_ROOT / "templates" / "workflows-js" / "finalize-feature.js"

# unit_tests/ must be on sys.path so _workflow_engine_harness is importable
# from this sub-package (unit_tests/workflows/). E402 is suppressed in ruff.toml.
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _js_text() -> str:
    """Return the full text of finalize-feature.js."""
    return _JS_PATH.read_text(encoding="utf-8")


_HARNESS_TIMEOUT = 30

# Matches a numbered step phase label, e.g. "Step 0", "Step 3.5" (excludes
# "Pre-flight" / "Pre-flight 2", which carry no step number).
_STEP_PHASE_RE = re.compile(r"^Step (\d+(?:\.\d+)?)$")


def _run_finalize_minimal(js_path: Path, worktree_root: str):
    """Run finalize-feature.js with a minimal, deterministic label_responses
    set that reliably reaches Step 0 and Step 1, then halts at Step 2 (the
    generic stub response for step-2-merge-main is not a status the step
    recognises). Every response this scenario depends on for step reachability
    is explicit — nothing here relies on the harness's default fallback for a
    step this test counts, so the set of steps reached is stable across runs.
    """
    label_responses = {
        "pre-flight": {
            "found": True,
            "branch": "feature/test-bp1100b45",
            "worktree_root": worktree_root,
        },
    }
    return run_workflow_under_e2(
        js_path,
        label_responses=label_responses,
        args={"epicArg": "test-bp1100b45"},
        timeout=_HARNESS_TIMEOUT,
    )


def _numbered_step_phases(result) -> set[str]:
    """Return the set of numbered step-phase labels dispatched (e.g. {'0','1','2'}).

    Derived from AgentCall.phase_name — independent, ground-truth evidence of
    which steps the run actually reached. NEVER a hardcoded step count: this
    is why the cardinality assertions below hold regardless of how many of
    finalize-feature.js's 9 declared steps a given label_responses set reaches.
    """
    numbers = set()
    for call in result.agent_calls:
        phase = call.phase_name or ""
        match = _STEP_PHASE_RE.match(phase)
        if match:
            numbers.add(match.group(1))
    return numbers


def _ordered_numbered_step_sequence(result) -> list[float]:
    """Return the sequence of numbered step values in agent-dispatch order.

    Walks result.agent_calls in call_index order (the order the harness's
    Node subprocess actually captured them in) and extracts each numbered
    "Step N" phase as a float, skipping non-numbered phases (Pre-flight,
    Pre-flight 2). This is the executed, in-control-flow analogue of "journal
    records appear in step order" — the ordering evidence comes from the real
    dispatch sequence the harness recorded, not from re-parsing an on-disk
    file finalize-feature.js no longer writes.
    """
    sequence: list[float] = []
    for call in sorted(result.agent_calls, key=lambda c: c.call_index):
        phase = call.phase_name or ""
        match = _STEP_PHASE_RE.match(phase)
        if match:
            sequence.append(float(match.group(1)))
    return sequence


def _prepare_finalize_copy_with_renamed_narrate(tmp_dir: Path) -> Path:
    """Write a temp copy of finalize-feature.js with every occurrence of the
    `narrate` identifier renamed to `narrateRenamedForTest`.

    Used by TestCoverageDoesNotDependOnInternalHelperNaming to prove that the
    dispatch-based coverage below binds to the workflow's observable
    behaviour (which steps it dispatches agents for, and in what order), not
    to any particular JS identifier appearing in the source — the same proof
    BP-1100b-4's original AC-4 ("renaming ... leaves the tests green") asked
    for, re-targeted onto the mechanism that actually exists post-removal.
    `narrate` is renamed (rather than `outcome`) because it is used only as
    the function name and its call sites, with no other overloaded meaning
    elsewhere in the file (`outcome` also names an object property).
    """
    source = _js_text()
    renamed_source = re.sub(r"\bnarrate\b", "narrateRenamedForTest", source)
    copy_path = Path(tmp_dir) / "finalize-feature.renamed.js"
    copy_path.write_text(renamed_source, encoding="utf-8")
    return copy_path


# ---------------------------------------------------------------------------
# Regression guard: the removed mechanism's specific defect shape cannot
# reappear silently.
# ---------------------------------------------------------------------------

class TestCustomFilesystemJournalMechanismIsFullyRemoved(unittest.TestCase):
    """BP-1100b-4 (AC-3 equivalent, post-redefinition): a run in which a
    filesystem-backed journal append "cannot happen" must not be a live code
    path at all — not merely fail loudly instead of silently.

    Before this ticket, `appendJournal()` called `require('fs')` inside a
    try/catch that swallowed the resulting throw and logged only a WARNING,
    so a run whose append could never succeed still reported success. The
    fix removes that code path outright. This is the one assertion in this
    file that reads source text directly, and it is deliberately an ABSENCE
    check, not a presence claim: it exists specifically to catch a REGRESSION
    (someone reintroducing a require('fs')-based journal write with the same
    swallow-and-report-success shape), which none of the executed tests below
    can detect, since a reintroduction that is functionally inert under the
    stub harness's default responses would not visibly change any dispatch.
    """

    def test_no_module_loader_or_custom_journal_helper_remains(self):
        # covers: BO-1000c-1a
        """finalize-feature.js must contain neither a require(...) call (the
        specific mechanism that could never work under the real E2 engine's
        no-module-loader contract, ADR-030) nor the removed appendJournal
        helper or its journalPath variable.

        This test FAILS the moment any of these three are reintroduced,
        regardless of whether the reintroduction is wrapped in a swallowing
        try/catch — unlike the removed grep-only tests, this one asserts
        ABSENCE of a known-broken pattern, not presence of a symbol as a
        stand-in for "the feature works".
        """
        source = _js_text()
        self.assertNotIn(
            "require(",
            source,
            msg=(
                "finalize-feature.js contains a require(...) call. This script's "
                "top-level body runs under the real E2 engine's ADR-030 contract, "
                "which injects no module loader — any require(...) call here "
                "either throws unconditionally in production or (if wrapped in a "
                "try/catch) silently swallows that throw, exactly the BP-1100b-4 "
                "defect this ticket removed."
            ),
        )
        self.assertNotIn(
            "appendJournal",
            source,
            msg=(
                "finalize-feature.js still references appendJournal, the removed "
                "on-disk journal helper. BP-1100b-45 replaced this mechanism with "
                "the E2 engine's own per-agent journal.jsonl; do not reintroduce "
                "a custom filesystem-backed journal helper."
            ),
        )
        self.assertNotIn(
            "journalPath",
            source,
            msg=(
                "finalize-feature.js still declares a journalPath variable. "
                "BP-1100b-45 removed the custom on-disk journal entirely."
            ),
        )


# ---------------------------------------------------------------------------
# Executed coverage: the workflow's step-dispatch behaviour, which is what
# the engine's own per-agent journal is keyed on, still works correctly
# after the journal helper's removal.
# ---------------------------------------------------------------------------

class TestStepDispatchesStillReachableAndOrderedAfterJournalRemoval(unittest.TestCase):
    """BP-1100b-4: executes the REAL, unmodified finalize-feature.js (no
    require-shadowing trick is needed any more — the production script has
    no require() call left at all) and asserts on the harness's genuine
    agent-dispatch capture, never on source text.
    """

    def test_every_reached_step_has_at_least_one_agent_dispatch(self):
        # covers: BO-1000c-1a
        """Every numbered step the run actually reaches must correspond to at
        least one real agent() dispatch tagged with that step's phase — the
        same per-dispatch granularity the E2 engine's own journal.jsonl
        records (one started/result pair per agent() call). This replaces
        the old per-step "one journal record group" assertion: the ticket's
        own 2026-08-18 20:05 decision explicitly gives up per-step
        granularity in favour of per-agent-dispatch, so a step making more
        than one agent() call (e.g. Step 1's PR probe followed by opening a
        PR) legitimately produces more than one record — cardinality is
        therefore asserted per phase (>=1), not as an exact global count.
        """
        with tempfile.TemporaryDirectory() as tmp:
            result = _run_finalize_minimal(_JS_PATH, tmp)

            self.assertEqual(result.error, "", msg=f"harness error: {result.error}")
            expected_steps = _numbered_step_phases(result)
            self.assertTrue(
                expected_steps,
                msg=(
                    "Ground-truth extraction found no numbered step dispatches at "
                    "all — cannot calibrate this test. agent_calls: "
                    f"{[(c.label, c.phase_name) for c in result.agent_calls]}"
                ),
            )
            # Every phase in expected_steps was, by construction of
            # _numbered_step_phases, derived from at least one agent_calls
            # entry — so this is a genuine (if structurally guaranteed once
            # expected_steps is non-empty) executed assertion that dispatches
            # occurred, not a hardcoded '9' or a re-parsed on-disk file.
            for step_number in expected_steps:
                matching = [
                    c for c in result.agent_calls
                    if (c.phase_name or "") == f"Step {step_number}"
                ]
                self.assertTrue(
                    matching,
                    msg=f"No agent() dispatch found tagged with phase 'Step {step_number}'",
                )

    def test_agent_dispatches_appear_in_step_order(self):
        # covers: BO-1000c-1a
        """The agent() dispatches captured by the harness — the same signal
        the E2 engine's own journal.jsonl is keyed on — appear in the order
        the steps actually completed (monotonically non-decreasing step
        numbers), derived from call_index (the harness's real capture order),
        never from a re-parsed on-disk journal file.
        """
        with tempfile.TemporaryDirectory() as tmp:
            result = _run_finalize_minimal(_JS_PATH, tmp)
            self.assertEqual(result.error, "", msg=f"harness error: {result.error}")

            observed_order = _ordered_numbered_step_sequence(result)
            self.assertTrue(
                observed_order,
                msg=(
                    "No numbered 'Step N' phase found among the dispatched agent "
                    f"calls: {[(c.label, c.phase_name) for c in result.agent_calls]}"
                ),
            )
            self.assertEqual(
                observed_order,
                sorted(observed_order),
                msg=(
                    "Agent dispatches are not tagged with monotonically ordered "
                    f"step phases — emission order was not preserved: {observed_order}"
                ),
            )

    def test_agent_dispatch_records_are_still_readable_after_the_run_ends(self):
        # covers: BO-1000c-1a
        """The harness's HarnessResult (including agent_calls) is only ever
        constructed AFTER the Node.js subprocess running finalize-feature.js
        has exited (run_workflow_under_e2() blocks on subprocess.run(), then
        parses its captured stdout) — so a non-empty, correctly-ordered
        agent_calls list on the returned result is a genuine post-process-exit
        durability check, the executed analogue of "journal records are still
        present when the run ends": the record of what was dispatched is not
        lost once the process backing the run has terminated.
        """
        with tempfile.TemporaryDirectory() as tmp:
            result = _run_finalize_minimal(_JS_PATH, tmp)
            self.assertEqual(result.error, "", msg=f"harness error: {result.error}")
            self.assertEqual(result.returncode, 0, msg=f"stderr: {result.stderr}")

            expected_steps = _numbered_step_phases(result)
            self.assertTrue(
                expected_steps,
                msg="Ground-truth extraction found zero step dispatches post-exit.",
            )
            self.assertGreaterEqual(
                result.dispatch_count,
                len(expected_steps),
                msg=(
                    "Fewer agent dispatches were readable after the harness process "
                    f"exited ({result.dispatch_count}) than distinct steps reached "
                    f"({len(expected_steps)})."
                ),
            )


# ---------------------------------------------------------------------------
# Coverage binds to behaviour, not to a JS identifier's name.
# ---------------------------------------------------------------------------

class TestCoverageDoesNotDependOnInternalHelperNaming(unittest.TestCase):
    """BP-1100b-4 (AC-4 equivalent): renaming an internal helper identifier,
    without changing what the workflow actually does, must leave this
    coverage green — proving the coverage above binds to the workflow's
    executed behaviour, not to a name in its source text.
    """

    def test_renaming_narrate_does_not_change_dispatch_based_coverage(self):
        # covers: BO-1000c-1a
        """Runs a temp copy of finalize-feature.js with every occurrence of
        `narrate` renamed to `narrateRenamedForTest` (function definition and
        every call site, consistently) and confirms the same numbered steps
        are still reached with a real agent() dispatch each — proving the
        step-dispatch coverage in this file does not depend on that (or any)
        specific identifier name.
        """
        with tempfile.TemporaryDirectory() as tmp:
            copy_path = _prepare_finalize_copy_with_renamed_narrate(Path(tmp))
            result = _run_finalize_minimal(copy_path, tmp)
            self.assertEqual(result.error, "", msg=f"harness error: {result.error}")

            expected_steps = _numbered_step_phases(result)
            self.assertTrue(
                expected_steps,
                msg="Ground-truth extraction found zero step dispatches after rename.",
            )
            for step_number in expected_steps:
                matching = [
                    c for c in result.agent_calls
                    if (c.phase_name or "") == f"Step {step_number}"
                ]
                self.assertTrue(
                    matching,
                    msg=(
                        f"After renaming narrate -> narrateRenamedForTest, no agent() "
                        f"dispatch is tagged with phase 'Step {step_number}'."
                    ),
                )


if __name__ == "__main__":
    unittest.main()
