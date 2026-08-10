"""
MODULE: test_bo_1000b_3
GOAL: Verify that step outcomes and the final recap carry concrete result data,
    never a content-free 'done' or 'ok' (AC BO-1000b-3).

    The tests parse finalize-feature.js as text so they guard the actual
    content reaching the agent at dispatch time, mirroring the pattern
    established in test_bo_1000b_1.py.

    Problematic steps identified in the current implementation:
      - Step 3 (pass-path): `Tests passed on post-merge worktree` — a
        template-backtick string with NO ${} interpolation; no concrete data
        (test count, SHA, etc.).
      - Step 5: 'Local main synced to origin/main HEAD' — a bare static
        single-quoted string; no concrete data (HEAD SHA, commit message).

TICKET: 11_TICKET-20260720-BO-1000b-3.md
AC: BO-1000b-3
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_JS_PATH = _REPO_ROOT / "templates" / "workflows-js" / "finalize-feature.js"


# ---------------------------------------------------------------------------
# Helpers (mirrors pattern from test_bo_1000b_1.py)
# ---------------------------------------------------------------------------

def _js_text() -> str:
    """Return the full text of finalize-feature.js."""
    return _JS_PATH.read_text(encoding="utf-8")


def _get_step_block(js: str, step_label: str, next_step_label: str | None) -> str:
    """Extract the text for a given step phase block.

    Returns text from phase('<step_label>') up to (but not including)
    phase('<next_step_label>'). Returns the tail of the file when
    next_step_label is None or the end marker is absent.
    Returns an empty string when the start marker is absent.
    """
    start_marker = f"phase('{step_label}')"
    start = js.find(start_marker)
    if start == -1:
        return ""
    if next_step_label is None:
        return js[start:]
    end_marker = f"phase('{next_step_label}')"
    end = js.find(end_marker, start)
    if end == -1:
        return js[start:]
    return js[start:end]


_OUTCOME_PATTERN = re.compile(r"\boutcome\s*\(")


# ---------------------------------------------------------------------------
# AC-1: the outcome text states the concrete result data for the step rather
# than a content-free acknowledgement (BO-1000b-3)
# ---------------------------------------------------------------------------

class TestOutcomeTextStatesConcreteResultData(unittest.TestCase):
    """AC-1: Each step outcome must state the concrete result data produced
    by that step rather than a content-free acknowledgement such as
    'Tests passed' or 'Synced'. Template literal ${...} interpolation is
    the required mechanism to carry the concrete values.

    Problem steps in current implementation:
      - Step 3 pass-path: `Tests passed on post-merge worktree` (no ${})
      - Step 5: 'Local main synced to origin/main HEAD' (no ${}; static string)
    """

    def test_ac1_step3_pass_path_includes_concrete_result_data(self):
        # covers: BO-1000b-3
        """Step 3 runs the full post-merge test suite — when tests pass,
        that is a measurable result. The concrete data includes at minimum:
        the count of passing tests, the baseline SHA being compared against,
        or the count of pre-existing failures that were present but did not
        constitute regressions.

        The outcome text for the pass-path must include a template literal
        with ${...} interpolation referencing concrete result variables (e.g.
        baselineFailures.length, baselineSha) rather than a bare static
        label.

        Must be implemented to make this test green:
          In finalize-feature.js, update the Step 3 pass-path outcome to
          include concrete result data, e.g.:
            outcome('Step 3 of 9', testPassed
              ? `Tests passed: no new failures (${baselineFailures !== null
                  ? baselineFailures.length : 'N/A'} pre-existing on main)`
              : ...)
          The exact wording is flexible, but at least one ${...} variable
          reference to a count, SHA, or enumeration is required.
        """
        js = _js_text()

        step3_block = _get_step_block(js, "Step 3", "Step 3.5")
        self.assertTrue(
            step3_block,
            msg="phase('Step 3') block not found in finalize-feature.js.",
        )

        outcome_match = _OUTCOME_PATTERN.search(step3_block)
        self.assertIsNotNone(
            outcome_match,
            msg=(
                "No outcome() call found in the Step 3 phase block. "
                "AC BO-1000b-3 requires every step that did real work to emit "
                "a concrete outcome — add an outcome() call to Step 3."
            ),
        )

        # Extract up to 600 chars from the outcome() call to capture both
        # branches of the ternary expression.
        outcome_region = step3_block[
            outcome_match.start(): outcome_match.start() + 600
        ]

        # The Step 3 outcome passes a ternary: testPassed ? <pass-text> : <fail-text>
        # The pass-path branch (true branch) must include ${} interpolation.
        # Current: testPassed ? `Tests passed on post-merge worktree`
        #          — backtick string but NO ${} — content-free acknowledgement.
        pass_branch_match = re.search(
            r"testPassed\s*\n?\s*\?\s*`([^`]*?)`",
            outcome_region,
        )

        if pass_branch_match is None:
            # Ternary structure has changed — check the entire outcome region
            # for any ${} interpolation on the pass path.
            has_any_template_var = "${" in outcome_region
            self.assertTrue(
                has_any_template_var,
                msg=(
                    "Step 3 outcome() does not include any template literal "
                    "variable interpolation (${...}) — the outcome appears to "
                    "be a content-free acknowledgement without concrete data.\n\n"
                    "AC BO-1000b-3: when Step 3 runs tests and they pass, the "
                    "outcome must state the concrete result data (e.g. test count, "
                    "baseline SHA, or pre-existing failure count) rather than a "
                    "bare label.\n\n"
                    "Fix: include ${...} in the Step 3 pass-path outcome referencing "
                    "concrete result data such as baselineFailures.length or baselineSha."
                ),
            )
        else:
            pass_branch_text = pass_branch_match.group(1)
            self.assertIn(
                "${",
                pass_branch_text,
                msg=(
                    "Step 3 pass-path outcome text lacks concrete result data "
                    "(no ${...} template literal interpolation).\n\n"
                    "AC BO-1000b-3: the outcome text must state the concrete "
                    "result data for the step rather than a content-free "
                    "acknowledgement. Step 3 ran the full post-merge test suite — "
                    "the pass-path outcome must include concrete data such as test "
                    "counts, baseline SHA, or pre-existing failure counts.\n\n"
                    f"Current pass-path text: {pass_branch_text!r}\n\n"
                    "Expected: a template literal like:\n"
                    "  `Tests passed: no new failures "
                    "(${baselineFailures !== null ? baselineFailures.length : 'N/A'} "
                    "pre-existing on main)`"
                ),
            )

    def test_ac1_step5_includes_concrete_result_data(self):
        # covers: BO-1000b-3
        """Step 5 syncs local main by running 'git checkout main && git pull'.
        This is a real git operation with a measurable result — the new HEAD
        SHA and commit message returned by the sync agent. The outcome text
        must include a template literal with ${...} variable interpolation
        carrying those concrete values.

        Must be implemented to make this test green:
          In finalize-feature.js, update the Step 5 outcome to include
          the concrete result data from the syncResult payload, e.g.:
            outcome('Step 5 of 9',
              `Local main synced: HEAD ${headSha} — ${headMessage}`)
          where headSha and headMessage are read from the sync agent's response.
        """
        js = _js_text()

        step5_block = _get_step_block(js, "Step 5", "Step 6")
        self.assertTrue(
            step5_block,
            msg="phase('Step 5') block not found in finalize-feature.js.",
        )

        outcome_match = _OUTCOME_PATTERN.search(step5_block)
        self.assertIsNotNone(
            outcome_match,
            msg=(
                "No outcome() call found in the Step 5 phase block. "
                "AC BO-1000b-3 requires Step 5 to emit a concrete outcome "
                "after the sync operation — add an outcome() call."
            ),
        )

        # Extract up to 300 chars from the outcome() call for inspection.
        outcome_region = step5_block[
            outcome_match.start(): outcome_match.start() + 300
        ]

        # Step 5 outcome must include ${} template literal interpolation.
        # Current: outcome('Step 5 of 9', 'Local main synced to origin/main HEAD')
        # — a single-quoted static string with NO ${} — this will FAIL.
        has_template_data = "${" in outcome_region
        self.assertTrue(
            has_template_data,
            msg=(
                "Step 5 outcome text lacks concrete result data "
                "(no ${...} template literal interpolation).\n\n"
                "AC BO-1000b-3: Step 5 syncs local main via "
                "'git checkout main && git pull'. This produces a measurable "
                "result — the new HEAD SHA and commit message. The outcome "
                "must state this concrete result data rather than a "
                "content-free acknowledgement.\n\n"
                "Current: outcome('Step 5 of 9', "
                "'Local main synced to origin/main HEAD')  "
                "— static string, no result data.\n\n"
                "Expected: a template literal like:\n"
                "  `Local main synced: HEAD ${headSha} — ${headMessage}`\n"
                "where headSha and headMessage come from the syncResult payload."
            ),
        )


# ---------------------------------------------------------------------------
# AC-2: a step that did real work never reports its outcome as only "ok"
# or "done" without the accompanying result data (BO-1000b-3)
# ---------------------------------------------------------------------------

class TestWorkedStepNeverReportsBareOkOrDone(unittest.TestCase):
    """AC-2: A step that did real work (dispatched at least one agent() call
    with a measurable result) must never report its outcome using a bare
    static string without accompanying result data.

    'Bare static string' here means either:
      - A single-quoted static Python string (e.g. 'Local main synced...'), OR
      - A template-backtick string with NO ${...} interpolation
        (e.g. `Tests passed on post-merge worktree`).

    Both forms are content-free acknowledgements that BO-1000b-3 prohibits
    for steps that did real, measurable work.
    """

    def test_ac2_step5_never_reports_bare_static_string(self):
        # covers: BO-1000b-3
        """Step 5 always does real work (git checkout main + git pull) —
        there is no 'already done' skip path for this step. Its outcome
        must therefore NEVER be a bare static single-quoted string.

        Current violation: outcome('Step 5 of 9', 'Local main synced to origin/main HEAD')
        — a single-quoted static string with no result data.

        Must be implemented to make this test green:
          Replace the Step 5 static string with a template literal that
          includes the concrete result data from the sync agent's response:
            outcome('Step 5 of 9', `Local main synced: HEAD ${headSha} — ${headMessage}`)
        """
        js = _js_text()

        step5_block = _get_step_block(js, "Step 5", "Step 6")
        self.assertTrue(step5_block, msg="phase('Step 5') block not found.")

        # A bare single-quoted static string as the second argument to outcome()
        # is the pattern AC-2 prohibits: it reports completion without result data.
        step5_bare_static = re.search(
            r"outcome\(\s*'Step 5 of 9'\s*,\s*'[^']*'\s*\)",
            step5_block,
        )
        self.assertIsNone(
            step5_bare_static,
            msg=(
                "Step 5 reports its outcome as a bare static single-quoted "
                "string — no result data.\n\n"
                "AC BO-1000b-3 AC-2: a step that did real work must never "
                "report its outcome as a content-free bare string without "
                "accompanying result data. Step 5 always runs 'git checkout "
                "main && git pull' — this is real work with a measurable "
                "result (new HEAD SHA + commit message).\n\n"
                "Found: outcome('Step 5 of 9', 'Local main synced to "
                "origin/main HEAD')\n\n"
                "Fix: replace the static string with a template literal "
                "that includes the concrete sync result:\n"
                "  outcome('Step 5 of 9', "
                "`Local main synced: HEAD ${headSha} — ${headMessage}`)"
            ),
        )

    def test_ac2_step3_pass_path_never_bare_template_without_variable_data(self):
        # covers: BO-1000b-3
        """Step 3 runs the full post-merge test suite — when tests pass, the
        step did real work. Its pass-path outcome must not be a bare template
        literal (backtick string) with no ${} interpolation, as that is
        functionally equivalent to a static content-free acknowledgement.

        Current violation: `Tests passed on post-merge worktree`
        — uses backticks (looks like a template literal) but contains NO
        ${} variable interpolation. This is a content-free label that carries
        no concrete result data about what the test run produced.

        Must be implemented to make this test green:
          Replace the pass-path literal with one that includes ${} referencing
          concrete data, e.g.:
            `Tests passed: no new failures (${baselineFailures !== null
                ? baselineFailures.length : 'N/A'} pre-existing on main)`
        """
        js = _js_text()

        step3_block = _get_step_block(js, "Step 3", "Step 3.5")
        self.assertTrue(step3_block, msg="phase('Step 3') block not found.")

        outcome_match = _OUTCOME_PATTERN.search(step3_block)
        self.assertIsNotNone(
            outcome_match,
            msg="No outcome() call found in Step 3 block.",
        )

        outcome_region = step3_block[
            outcome_match.start(): outcome_match.start() + 600
        ]

        # Match the pass-path branch (true branch of testPassed ternary).
        # A bare template literal (backticks but no ${}) is the content-free
        # pattern this test guards against.
        pass_branch_match = re.search(
            r"testPassed\s*\n?\s*\?\s*`([^`]*?)`",
            outcome_region,
        )

        if pass_branch_match is None:
            # Ternary structure changed — verify ${} appears somewhere for
            # the pass-path scenario.
            has_any_template_var = "${" in outcome_region
            self.assertTrue(
                has_any_template_var,
                msg=(
                    "Step 3 outcome does not include any template literal "
                    "variable interpolation (${...}) — the outcome appears to "
                    "be a bare static acknowledgement without concrete data.\n\n"
                    "AC BO-1000b-3 AC-2: a step that did real work must never "
                    "report its outcome without accompanying result data. "
                    "Step 3 ran the full post-merge test suite — concrete data "
                    "(counts, SHA) must appear in the outcome text.\n\n"
                    "Fix: include ${} interpolation referencing result variables "
                    "such as baselineFailures.length or baselineSha."
                ),
            )
        else:
            pass_branch_text = pass_branch_match.group(1)
            # The pass-path template literal must include ${} — actual variable
            # interpolation, not just a static label in backticks.
            self.assertIn(
                "${",
                pass_branch_text,
                msg=(
                    "Step 3 pass-path outcome is a bare template literal "
                    "with no ${} variable interpolation — it is a content-free "
                    "label equivalent to 'done' for the step.\n\n"
                    "AC BO-1000b-3 AC-2: a step that did real work must never "
                    "report its outcome as only a content-free label. The test "
                    "runner ran the full suite — the pass-path outcome must "
                    "state concrete result data.\n\n"
                    f"Current pass-path text: {pass_branch_text!r}\n\n"
                    "Fix: update the pass-path branch to include concrete data "
                    "via ${} interpolation, e.g.:\n"
                    "  `Tests passed: no new failures "
                    "(${baselineFailures !== null ? baselineFailures.length "
                    ": 'N/A'} pre-existing on main)`"
                ),
            )

    def test_ac2_steps_with_real_work_have_dynamic_outcome_text(self):
        # covers: BO-1000b-3
        """For all numbered steps that dispatched at least one agent() call
        (i.e. did real, measurable work), the corresponding outcome() call
        must include template literal ${...} interpolation in its description
        argument.

        Steps identified as 'always doing real work' (no skip-path to a
        static string):
          - Step 0: baseline capture (always dispatches status-checker)
          - Step 3: test run (always dispatches test-runner + conditionally triage)
          - Step 5: local main sync (always dispatches status-checker)
          - Step 6: scope detection (always dispatches status-checker)

        Must be implemented to make this test green:
          Ensure the outcome() calls for steps 3 (pass-path), 5, and any
          other steps that always do real work include ${} interpolation
          referencing the step's concrete result data.
        """
        js = _js_text()

        # Steps that always dispatch at least one agent() call on all paths
        # (i.e. no early-exit skip-path that would legitimately yield a static string).
        always_real_work_steps = [
            ("Step 0", "Step 1", "baseline capture"),
            ("Step 3", "Step 3.5", "post-merge test run"),
            ("Step 5", "Step 6", "local main sync"),
            ("Step 6", "Step 7", "scope detection"),
        ]

        violations: list[str] = []
        for step_label, next_label, step_name in always_real_work_steps:
            block = _get_step_block(js, step_label, next_label)
            if not block:
                violations.append(
                    f"{step_label} ({step_name}): phase block not found"
                )
                continue

            outcome_match = _OUTCOME_PATTERN.search(block)
            if outcome_match is None:
                violations.append(
                    f"{step_label} ({step_name}): no outcome() call found"
                )
                continue

            outcome_region = block[outcome_match.start(): outcome_match.start() + 600]

            if "${" not in outcome_region:
                violations.append(
                    f"{step_label} ({step_name}): outcome() call has no "
                    f"${'{'}...{'}'} interpolation — content-free static string"
                )

        self.assertEqual(
            violations,
            [],
            msg=(
                "The following steps that always do real work have outcome() "
                "calls without template literal ${...} interpolation — their "
                "outcomes are content-free acknowledgements:\n"
                + "\n".join(f"  - {v}" for v in violations)
                + "\n\n"
                "AC BO-1000b-3: a step that did real work must state the "
                "concrete result data (counts, identifiers, or decisions) in "
                "its outcome text. Bare static strings do not satisfy this "
                "requirement for steps that always dispatch agent() calls.\n\n"
                "Fix the flagged steps by including ${} interpolation in their "
                "outcome() description argument."
            ),
        )


if __name__ == "__main__":
    unittest.main()
