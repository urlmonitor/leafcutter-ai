"""
MODULE: unit_tests/workflows/test_bo2400a_runner_wiring.py
GOAL: SEMANTIC wiring tests for DEFECT H-1 — fast-lane-build.js defines gate
      invocation strings but never executes or consumes them.  These tests
      verify that the gate strings are USED (in conditionals and agent prompts),
      not merely defined.  They complement the structural tests in
      test_bo2400a_runner_structure.py which check gate-name PRESENCE only.

=== DEFECT H-1 (Dead Gate Strings / Unconditional Dispatch) ===

Independent review found that fast-lane-build.js:

1. Defines `redBaselineInvocation` (line 164-166) as a string variable but
   NEVER embeds it in any conditional, Bash() call, or agent prompt.  The
   coder is dispatched unconditionally at line 178 — the red-baseline gate
   is declared but never enforced.

2. Defines `greenCoverageInvocation` (line 227-231) but NEVER executes it,
   never passes it to an agent, and never branches on its result.  The final
   `status:"ok"` return at line 238 is unconditional.

3. The `gates_passed` array in the return value lists
   ["select_batch", "verify_red_baseline", "verify_green_and_coverage"] —
   all three gates are claimed as passed even though only select_batch is
   actually referenced in an agent prompt.

4. `choose_lane` (path_selection.py), `emit_agent_telemetry`
   (agent_telemetry.py), and `assemble_context_bundle` (injection_builders.py)
   are not referenced anywhere in the runner — the b/c/d integration found
   dormant by the review.

=== What these tests assert (SEMANTIC, not structural) ===

  Test 1: redBaselineInvocation variable is referenced at LEAST TWICE —
          once in its definition (assignment) and at least once more in a
          conditional branch, Bash() call, or agent prompt string.

  Test 2: greenCoverageInvocation variable is referenced at least twice —
          defined and consumed in a conditional or agent prompt.

  Test 3: The coder agent dispatch is GUARDED — between the test-writer
          agent() call and the coder agent() call, there is at least one
          conditional branch keyword (if/else/throw/return) that references
          the red-baseline result.  A branch keyword between the two agent()
          calls that references 'red' or 'baseline' confirms the guard exists.

  Test 4: The final `status:"ok"` / `gates_passed` return is CONDITIONAL on
          the green+coverage result — a conditional keyword (if/throw/return)
          references the green or coverage result between the coder dispatch
          and the final return.

  Test 5: `choose_lane` is referenced in the runner (path_selection integration
          is not dormant).

  Test 6: `emit_agent_telemetry` is referenced in the runner (telemetry
          integration is not dormant).

  Test 7: `assemble_context_bundle` is referenced in the runner (context
          bundle assembly integration is not dormant).

=== Red baseline ===

  All tests are RED against the current fast-lane-build.js because:
  - redBaselineInvocation appears only once (its definition)
  - greenCoverageInvocation appears only once (its definition)
  - No conditional between test-writer and coder dispatch references the red result
  - The final return is unconditional
  - choose_lane, emit_agent_telemetry, assemble_context_bundle are absent

=== Fixture-authenticity mandate ===

  Tests always read the REAL on-disk fast-lane-build.js — no hand-typed JS.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve the script under test
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_JS_PATH = _REPO_ROOT / "templates" / "workflows-js" / "fast-lane-build.js"


# ---------------------------------------------------------------------------
# Shared read helper
# ---------------------------------------------------------------------------


def _require_js() -> str:
    """Return the JS file content, failing if absent."""
    assert _JS_PATH.exists(), (
        f"fast-lane-build.js not found at {_JS_PATH}. "
        "Create the file before running wiring tests."
    )
    return _JS_PATH.read_text(encoding="utf-8")


def _non_comment_lines(content: str) -> list[str]:
    """Return lines that are not pure JS single-line comments.

    Args:
        content: Full JS file content.

    Returns:
        Lines that don't start with // after stripping.
    """
    result = []
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
            continue
        result.append(line)
    return result


def _count_occurrences_in_non_comment(content: str, pattern: str) -> int:
    """Count how many non-comment lines contain the pattern.

    Args:
        content: Full JS file content.
        pattern: Substring to search for.

    Returns:
        Count of non-comment lines containing the pattern.
    """
    lines = _non_comment_lines(content)
    return sum(1 for line in lines if pattern in line)


def _find_text_between(content: str, start_pattern: str, end_pattern: str) -> str | None:
    """Extract the JS text between the first match of start_pattern and end_pattern.

    Args:
        content: Full JS file content.
        start_pattern: Regex pattern marking the start of the region.
        end_pattern: Regex pattern marking the end of the region.

    Returns:
        Substring between the matched patterns, or None if either not found.
    """
    start_match = re.search(start_pattern, content)
    end_match = re.search(end_pattern, content)
    if start_match is None or end_match is None:
        return None
    if start_match.end() >= end_match.start():
        return None
    return content[start_match.end():end_match.start()]


# ---------------------------------------------------------------------------
# TestRedBaselineGateConsumed — DEFECT H-1 / Test 1
# ---------------------------------------------------------------------------


class TestRedBaselineGateConsumed(unittest.TestCase):
    """Assert that the red-baseline gate invocation string is CONSUMED, not dead.

    DEFECT H-1: redBaselineInvocation is defined once but never used.
    FIX SIGNAL: the variable must appear in at least one conditional branch
    (if/else) or be embedded in the agent prompt that the coder receives.
    """

    def test_h1_red_baseline_invocation_referenced_twice(self) -> None:
        # covers: BO-2400a-3
        """redBaselineInvocation must appear in at least 2 non-comment lines.

        DEFECT H-1: The variable is only defined (1 occurrence in a const
        assignment). A second occurrence in a Bash() call, an agent prompt,
        or a conditional is required for the gate to actually execute.

        To make this green, embed redBaselineInvocation in a Bash() call or
        in the conditional guard before the coder dispatch:
            const redResult = await bash(redBaselineInvocation);
            if (redResult.exit_code !== 0) { ... }
        or pass it to an agent prompt that runs the gate.
        """
        content = _require_js()

        # Count non-comment occurrences of the variable name
        occurrences = _count_occurrences_in_non_comment(content, "redBaselineInvocation")

        self.assertGreaterEqual(
            occurrences,
            2,
            f"DEFECT H-1: 'redBaselineInvocation' appears in {occurrences} non-comment "
            "line(s) — the variable is defined but NEVER consumed. "
            "A second reference in a Bash() call, conditional, or agent prompt is required "
            "so the gate actually executes before the coder is dispatched (BO-2400a-3).",
        )

    def test_h1_red_baseline_result_used_in_conditional(self) -> None:
        # covers: BO-2400a-3
        """The red-baseline gate result must be used in a conditional branch.

        DEFECT H-1: After redBaselineInvocation is defined, no conditional
        uses it.  The gate verdict is discarded.

        The fix must include a branch that acts on the result:
            if (redVerdictOrResult.all_red !== true) {
                return { status: "blocked", ... };
            }
        A conditional keyword (if|else if|throw|return) must appear adjacent
        to a reference to the red-baseline variable or its result variable
        between the test-writer dispatch and the coder dispatch.
        """
        content = _require_js()
        non_comments = "\n".join(_non_comment_lines(content))

        # Find the region between the test-writer dispatch and the coder dispatch.
        # The test-writer label in agent() appears before the coder.
        between = _find_text_between(
            non_comments,
            r"agentType\s*:\s*[\"']test-writer[\"']",
            r"agentType\s*:\s*[\"']python-coder[\"']",
        )

        if between is None:
            # The agent types are not present or the order is wrong —
            # fail with a clear message but let the existence tests catch the root cause.
            self.fail(
                "DEFECT H-1: Could not find the region between 'test-writer' dispatch "
                "and 'python-coder' dispatch. Structural tests may also be failing."
            )

        # A guard must exist in this region that references the red result.
        # Look for any conditional keyword followed by a reference to the
        # red-baseline concept (either the variable name or 'all_red').
        guard_pattern = re.search(
            r"\b(if|else\s+if|throw|return)\b[^;{]*\b(redBaseline|all_red|red_baseline|red_result)",
            between,
            re.DOTALL | re.IGNORECASE,
        )

        self.assertIsNotNone(
            guard_pattern,
            "DEFECT H-1: No conditional guard referencing the red-baseline result was "
            "found between the test-writer dispatch and the coder dispatch. "
            "The coder is dispatched UNCONDITIONALLY. "
            "Fix: add 'if (!redVerdict.all_red) { return {..., status: \"blocked\"} }' "
            "between the two agent() calls (BO-2400a-3).",
        )


# ---------------------------------------------------------------------------
# TestGreenCoverageGateConsumed — DEFECT H-1 / Test 2
# ---------------------------------------------------------------------------


class TestGreenCoverageGateConsumed(unittest.TestCase):
    """Assert that the green+coverage gate invocation string is CONSUMED, not dead.

    DEFECT H-1: greenCoverageInvocation is defined once but never used.
    FIX SIGNAL: the variable must appear in a Bash() call or conditional after
    the coder dispatch, and the final return must be guarded by its result.
    """

    def test_h1_green_coverage_invocation_referenced_twice(self) -> None:
        # covers: BO-2400a-4
        """greenCoverageInvocation must appear in at least 2 non-comment lines.

        DEFECT H-1: The variable is only defined once. A second occurrence in
        a Bash() call or conditional guard is required for the gate to run.

        To make this green, embed greenCoverageInvocation in a Bash() call
        after the coder dispatch:
            const greenVerdict = await bash(greenCoverageInvocation);
            if (!greenVerdict.green || !greenVerdict.coverage_ok) { ... }
        """
        content = _require_js()
        occurrences = _count_occurrences_in_non_comment(content, "greenCoverageInvocation")

        self.assertGreaterEqual(
            occurrences,
            2,
            f"DEFECT H-1: 'greenCoverageInvocation' appears in {occurrences} non-comment "
            "line(s) — the variable is defined but NEVER consumed. "
            "A second reference in a Bash() call or conditional is required so the "
            "gate actually executes after the coder finishes (BO-2400a-4).",
        )

    def test_h1_final_ok_return_is_inside_green_coverage_guard(self) -> None:
        # covers: BO-2400a-4
        """The final status:ok / gates_passed return must be guarded by the green+coverage result.

        DEFECT H-1: The final 'return { status: "ok", ..., gates_passed: [...] }'
        at line 238 is unconditional — it returns success regardless of whether
        the green+coverage gate passed.

        Fix: the final ok-return must follow a conditional that checks the
        green+coverage verdict.  A conditional referencing 'green' or 'coverage'
        must appear between the coder dispatch and the final ok-return.
        """
        content = _require_js()
        non_comments = "\n".join(_non_comment_lines(content))

        # Find the region from the coder dispatch to the final gates_passed return.
        between = _find_text_between(
            non_comments,
            r"agentType\s*:\s*[\"']python-coder[\"']",
            r"gates_passed",
        )

        if between is None:
            self.fail(
                "DEFECT H-1: Could not find the region between 'python-coder' dispatch "
                "and 'gates_passed' return. The gates_passed return may be absent or "
                "appear before the coder dispatch (structural issue)."
            )

        # A guard must exist: a JavaScript if-statement whose condition references
        # the green/coverage gate result.  We use `if\s*\(` (an explicit JS if-opener)
        # rather than matching `return` or `throw`, which can appear inside string
        # literals and create false positives.  The condition must reference one of
        # the gate-result identifiers — not just the word "green" from an error message.
        guard_pattern = re.search(
            r"\bif\s*\([^;{]*\b(greenCoverage\w*|coverage_ok|greenVerdict|greenResult)",
            between,
            re.DOTALL | re.IGNORECASE,
        )

        self.assertIsNotNone(
            guard_pattern,
            "DEFECT H-1: The final 'gates_passed' / 'status:ok' return is UNCONDITIONAL "
            "— no JavaScript if-statement referencing the green+coverage gate result "
            "(greenCoverageInvocation result, coverage_ok, greenVerdict, greenResult, etc.) "
            "was found between the coder dispatch and the final return. "
            "Fix: run the gate and branch on its result: "
            "'if (!greenVerdict.green || !greenVerdict.coverage_ok) { "
            "return {..., status: \"blocked\"} }' before the final ok return (BO-2400a-4).",
        )


# ---------------------------------------------------------------------------
# TestIntegrationReferencesNotDormant — DEFECT H-1 / Tests 5-7
# ---------------------------------------------------------------------------


class TestIntegrationReferencesNotDormant(unittest.TestCase):
    """Assert that choose_lane, emit_agent_telemetry, and assemble_context_bundle
    are referenced in the runner — the b/c/d integration the review found dormant.

    DEFECT H-1: These three symbols from path_selection.py, agent_telemetry.py,
    and injection_builders.py are nowhere in fast-lane-build.js.  The review
    found them dormant — the integration code paths were never wired in.
    """

    def test_h1_choose_lane_referenced_in_runner(self) -> None:
        # covers: BO-2400b-3
        """fast-lane-build.js must reference choose_lane (path_selection integration).

        DEFECT H-1: choose_lane is not referenced — the path selection integration
        is dormant.  The runner must call choose_lane (or invoke the gate script
        that wraps it) to determine which lane applies to the current batch.

        To make this green, reference 'choose_lane' or 'chooseLane' in the runner,
        either as a direct function call (if imported) or as a CLI invocation of
        path_selection.py.
        """
        content = _require_js()
        has_choose_lane = "choose_lane" in content or "chooseLane" in content
        self.assertTrue(
            has_choose_lane,
            "DEFECT H-1: 'choose_lane' (from scripts/build_orchestration/path_selection.py) "
            "is not referenced in fast-lane-build.js. "
            "The path-selection integration (BO-2400b-3) is dormant — "
            "add a reference to choose_lane or path_selection.py in the runner.",
        )

    def test_h1_emit_agent_telemetry_referenced_in_runner(self) -> None:
        # covers: BO-2400d-1
        """fast-lane-build.js must reference emit_agent_telemetry (telemetry integration).

        DEFECT H-1: emit_agent_telemetry is not referenced — the telemetry sink
        integration is dormant.  Phase agents must call emit_agent_telemetry
        after each phase so the retrospective-agent can compare lanes.

        To make this green, reference 'emit_agent_telemetry' or
        'emitAgentTelemetry' in the runner or in its agent prompts.
        """
        content = _require_js()
        has_telemetry = "emit_agent_telemetry" in content or "emitAgentTelemetry" in content
        self.assertTrue(
            has_telemetry,
            "DEFECT H-1: 'emit_agent_telemetry' (from scripts/agent-health/agent_telemetry.py) "
            "is not referenced in fast-lane-build.js. "
            "The telemetry integration (BO-2400d-1) is dormant — "
            "add emit_agent_telemetry calls after each phase dispatch.",
        )

    def test_h1_assemble_context_bundle_referenced_in_runner(self) -> None:
        # covers: BO-2400c-1
        """fast-lane-build.js must reference assemble_context_bundle (context assembly).

        DEFECT H-1: assemble_context_bundle is not referenced — the context
        bundle assembly integration is dormant.  The runner must build the
        layered context bundle so agents receive stable-prefix-optimized context.

        To make this green, reference 'assemble_context_bundle' or
        'assembleContextBundle' in the runner.
        """
        content = _require_js()
        has_context_bundle = (
            "assemble_context_bundle" in content
            or "assembleContextBundle" in content
        )
        self.assertTrue(
            has_context_bundle,
            "DEFECT H-1: 'assemble_context_bundle' (from scripts/injection_builders.py) "
            "is not referenced in fast-lane-build.js. "
            "The context-bundle integration (BO-2400c-1) is dormant — "
            "add a call to assemble_context_bundle before each agent dispatch.",
        )


# ---------------------------------------------------------------------------
# TestGatesPassed_ClaimMatchesReality — DEFECT H-1 / gates_passed audit
# ---------------------------------------------------------------------------


class TestGatesPassedClaimMatchesReality(unittest.TestCase):
    """Assert that gates listed in gates_passed are actually executed.

    DEFECT H-1: The current code claims gates_passed includes
    'verify_red_baseline' and 'verify_green_and_coverage' in the final return,
    but neither gate is actually executed.  The claim is a phantom-done signal.
    The gates_passed array must only list gates that the runner actually ran.
    """

    def test_h1_gates_passed_is_conditional_not_hardcoded(self) -> None:
        # covers: BO-2400a-3
        # covers: BO-2400a-4
        """gates_passed must be built from actual gate results, not a hardcoded list.

        DEFECT H-1: The final return hardcodes
            gates_passed: ["select_batch", "verify_red_baseline", "verify_green_and_coverage"]
        regardless of whether the gates actually ran or passed.  This is a
        phantom-done signal that falsely claims all three gates passed.

        Fix: gates_passed must be constructed from the actual gate results:
            const gatesPassed = ["select_batch"];
            if (redVerdict.all_red) gatesPassed.push("verify_red_baseline");
            if (greenVerdict.green && greenVerdict.coverage_ok) gatesPassed.push("verify_green_and_coverage");
        OR the return must be inside a branch that only runs when the gates passed.

        The test detects the hardcoded pattern by looking for the constant
        array literal ["select_batch", "verify_red_baseline", "verify_green_and_coverage"]
        in the final unconditional return — NOT inside a conditional block.
        The pattern is: the hardcoded array appears in a non-comment line that
        is not preceded by any gate-result conditional.
        """
        content = _require_js()

        # Find the hardcoded gates_passed assignment pattern (the phantom-done signal).
        # The pattern is: a single line or inline array containing all three gate names
        # assigned unconditionally (not inside any if block referencing gate results).
        hardcoded_gates_passed_pattern = re.compile(
            r"gates_passed\s*:\s*\[.*select_batch.*verify_red_baseline.*verify_green_and_coverage.*\]",
            re.DOTALL,
        )

        match = hardcoded_gates_passed_pattern.search(content)
        if match is None:
            # gates_passed array not hardcoded — the fix is in place.
            return

        # The hardcoded pattern is present. Verify it's in an unconditional context
        # (not guarded by a gate-result check). Extract the text from the last
        # gate-result conditional to the gates_passed assignment.
        text_before_match = content[:match.start()]

        # Look for the last occurrence of a green-result conditional before gates_passed.
        last_guard = max(
            (m.end() for m in re.finditer(
                r"\b(if|else\s+if)\b[^{]*\b(green|coverage|all_red|red)",
                text_before_match,
                re.IGNORECASE,
            )),
            default=0,
        )

        # Look for the last { ... } block end before the hardcoded gates_passed.
        last_block_end = max(
            (m.end() for m in re.finditer(r"\}", text_before_match)),
            default=0,
        )

        # If the last guard is before the last block end, the gates_passed
        # assignment is outside the conditional block — it's unconditional.
        if last_guard < last_block_end:
            self.fail(
                "DEFECT H-1: gates_passed is a hardcoded array claiming all three gates "
                "passed, but the gates are not actually executed. "
                "This is a phantom-done signal: status:ok + gates_passed lists all three "
                "gates unconditionally even when neither verify_red_baseline nor "
                "verify_green_and_coverage actually ran. "
                "Fix: build gates_passed from actual gate results or make the final "
                "ok-return conditional on both gate verdicts.",
            )


if __name__ == "__main__":
    unittest.main()
