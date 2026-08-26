"""BO-1000c-1a — in-flight run-progress visibility for background finalize.

REDEFINED 2026-08-18. This file was previously a presence-only suite: ten tests
that read finalize-feature.js as text and asserted that an `appendJournal`
helper, a `journalPath` variable and an `fs.appendFileSync` call were present in
the source. Every one of them passed for the entire life of the defect, because
the strings really were there. None of them ever executed the mechanism, and the
mechanism never once ran: `appendJournal()` loaded Node's `fs` module through the
CommonJS module loader, and the E2 engine injects only
agent/parallel/pipeline/phase/log/args/workflow/budget into a workflow body — no
module loader (ADR-030). The `require('fs')` call threw on every invocation, a
surrounding try/catch logged a WARNING, and the run reported success. The AC read
`work_status: done` throughout.

That is the M1 failure mode from docs/reference/false-green-mechanisms.md in its
purest form, and it is worth being precise about why the old tests could not have
caught it: they asserted that code *exists*, which was true, as a stand-in for the
code *working*, which was false. No amount of adding more presence assertions
would have helped.

The criterion has been redefined onto the journal the engine already writes at
<transcriptDir>/journal.jsonl — a {"type":"started"} / {"type":"result"} record
pair per agent() dispatch. See BO-1000c-1a's `amended_by` entry for the full
decision record, including the rejected alternatives.

Scope of THIS file, before BP-1100b-4 landed: the absence guard below, which
needs nothing but the source text. The executed dispatch-coverage tests below
it land WITH BP-1100b-4's vm-sandboxed workflow harness — the fifth test_spec
descriptor for this AC is the absence guard above; the four below execute the
real, unmodified finalize-feature.js under the now engine-faithful
run_workflow_under_e2() and assert on the harness's genuine agent-dispatch
capture, never on source text.

HONEST LIMITATION (applies to the four executed classes below): the E2
engine's own journal.jsonl is written by the engine itself, entirely outside a
workflow script's control and outside what
unit_tests/_workflow_engine_harness.py's Node-subprocess stub can reproduce
(the harness has no engine-internal journal-writer to invoke). So no test
here — or anywhere at the unit level — can execute a real run and read back a
real journal.jsonl produced by production code; that would require an
integration-level harness around the actual E2 engine, which does not exist.
What CAN be executed and asserted on is the harness's own agent_calls capture
(unit_tests/_workflow_engine_harness.py's AgentCall list, keyed by real
agent() dispatches and their phase labels) — the same underlying signal (one
record per agent() dispatch) the engine's own journal is keyed on, just
observed from the test-harness side of the boundary rather than from a
re-parsed on-disk file.
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

_HARNESS_TIMEOUT = 30

# Matches a numbered step phase label, e.g. "Step 0", "Step 3.5" (excludes
# "Pre-flight" / "Pre-flight 2", which carry no step number).
_STEP_PHASE_RE = re.compile(r"^Step (\d+(?:\.\d+)?)$")


def _js_text() -> str:
    """Return the full text of finalize-feature.js."""
    return _JS_PATH.read_text(encoding="utf-8")


def _run_finalize_minimal(js_path: Path, worktree_root: str):
    """Run finalize-feature.js with a minimal, deterministic label_responses
    set that reliably reaches Step 0, Step 1 and Step 2, then halts (the
    generic stub response for step-2-merge-main is not a status the step
    recognises). Every response this scenario depends on for step
    reachability is explicit — nothing here relies on the harness's default
    fallback for a step this test counts, so the set of steps reached is
    stable across runs.

    ``args.target`` (not ``args.epicArg``) is the input finalize-feature.js
    actually reads (FIN-100g-2's epicArg-derivation line: ``args.target ||
    args.target_branch``) — confirmed by executing the harness against the
    real script, not assumed.
    """
    label_responses = {
        "pre-flight": {
            "found": True,
            "branch": "feature/test-bp1100b4",
            "worktree_root": worktree_root,
        },
    }
    return run_workflow_under_e2(
        js_path,
        label_responses=label_responses,
        args={"target": "test-bp1100b4"},
        timeout=_HARNESS_TIMEOUT,
    )


def _numbered_step_phases(result) -> set[str]:
    """Return the set of numbered step-phase labels dispatched (e.g. {'0','1','2'}).

    Derived from AgentCall.phase_name — independent, ground-truth evidence of
    which steps the run actually reached. NEVER a hardcoded step count: this
    is why the cardinality assertions below hold regardless of how many of
    finalize-feature.js's declared steps a given label_responses set reaches.
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
    to any particular JS identifier appearing in the source. `narrate` is
    renamed (rather than `outcome`) because it is used only as the function
    name and its call sites, with no other overloaded meaning elsewhere in
    the file (`outcome` also names an object property).
    """
    source = _js_text()
    renamed_source = re.sub(r"\bnarrate\b", "narrateRenamedForTest", source)
    copy_path = Path(tmp_dir) / "finalize-feature.renamed.js"
    copy_path.write_text(renamed_source, encoding="utf-8")
    return copy_path


class TestCustomFilesystemJournalMechanismIsFullyRemoved(unittest.TestCase):
    """A filesystem-backed journal append that *cannot* happen must not be a
    live code path at all — not merely fail loudly instead of silently.

    This is the one assertion in this file that reads source text directly, and
    it is deliberately an ABSENCE check rather than a presence claim. The
    distinction matters, and it is the reason this test is legitimate where the
    ten it replaces were not: a presence assertion stays green on dead code,
    which is exactly what happened here for weeks. An absence assertion cannot —
    it fails the moment the known-broken pattern reappears, whether or not the
    reintroduced version is wrapped in a swallowing try/catch, and whether or not
    it is ever reached at runtime.

    It exists to catch a REGRESSION that no executed test can detect: a
    reintroduced `require('fs')` journal write that is functionally inert would
    not change any observable dispatch, so a behavioural suite would stay green
    while the defect returned.
    """

    def test_no_module_loader_or_custom_journal_helper_remains(self):
        # covers: BO-1000c-1a
        """finalize-feature.js must contain neither a require(...) call nor the
        removed appendJournal helper nor its journalPath variable.
        """
        source = _js_text()
        self.assertNotIn(
            "require(",
            source,
            msg=(
                "finalize-feature.js contains a require(...) call. This script's "
                "top-level body runs under the E2 engine's ADR-030 contract, which "
                "injects no module loader — any require(...) here either throws "
                "unconditionally in production or, if wrapped in a try/catch, "
                "silently swallows that throw. The latter is the exact defect that "
                "kept BO-1000c-1a marked done while it had never written a line."
            ),
        )
        self.assertNotIn(
            "appendJournal",
            source,
            msg=(
                "finalize-feature.js still references appendJournal, the removed "
                "on-disk journal helper. In-flight visibility now comes from the E2 "
                "engine's own per-agent journal.jsonl; do not reintroduce a custom "
                "filesystem-backed journal helper."
            ),
        )
        self.assertNotIn(
            "journalPath",
            source,
            msg=(
                "finalize-feature.js still declares a journalPath variable. The "
                "custom on-disk journal was removed entirely, not relocated."
            ),
        )


# ---------------------------------------------------------------------------
# Executed coverage (BP-1100b-4): the workflow's step-dispatch behaviour,
# which is what the engine's own per-agent journal is keyed on, works
# correctly after the journal helper's removal.
# ---------------------------------------------------------------------------

class TestStepDispatchesStillReachableAndOrderedAfterJournalRemoval(unittest.TestCase):
    """Executes the REAL, unmodified finalize-feature.js (no require-shadowing
    trick is needed — the production script has no require() call left at
    all) and asserts on the harness's genuine agent-dispatch capture, never
    on source text.
    """

    def test_every_reached_step_has_at_least_one_agent_dispatch(self):
        # covers: BO-1000c-1a
        """Every numbered step the run actually reaches must correspond to at
        least one real agent() dispatch tagged with that step's phase — the
        same per-dispatch granularity the E2 engine's own journal.jsonl
        records (one started/result pair per agent() call). This is the
        executed analogue of "one journal record per completed step": the
        2026-08-18 redefinition gives up per-step granularity in favour of
        per-agent-dispatch, so a step making more than one agent() call
        (e.g. Step 1's PR probe followed by opening a PR) legitimately
        produces more than one record — cardinality is therefore asserted
        per phase (>=1), not as an exact global count.
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
            # occurred, not a hardcoded step count or a re-parsed on-disk file.
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
    """Renaming an internal helper identifier, without changing what the
    workflow actually does, must leave this coverage green — proving the
    coverage above binds to the workflow's executed behaviour, not to a name
    in its source text.
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
