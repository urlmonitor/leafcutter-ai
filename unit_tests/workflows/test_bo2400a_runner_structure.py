"""
MODULE: unit_tests/workflows/test_bo2400a_runner_structure.py
GOAL: RED structural tests for BO-2400a-1, BO-2400a-2 (gate reference),
      BO-2400a-3 (gate reference), BO-2400a-4 (gate reference), BO-2400a-5.

=== Target file (to be created by llm-expert) ===

Location: templates/workflows-js/fast-lane-build.js

Required structural properties:

  1. Declares `export const meta` (standard E2 workflow contract).

  2. Contains EXACTLY TWO agent() dispatches in the top-level flow
     (BO-2400a-1): one for test-writer and one for a coder (python-coder /
     sql-coder / frontend-coder / llm-expert).  The invocation count must not
     grow with batch size N — the two dispatches are flat (not inside a
     per-AC or per-ticket for-loop).

  3. References the deterministic select_batch gate (BO-2400a-2) — the batch
     AC selection is performed by the python script, not by an LLM planner.
     The file must reference 'select_batch' or 'selectBatch'.

  4. References the red-baseline gate (BO-2400a-3): the file must reference
     'verify_red_baseline' or 'verifyRedBaseline' or 'red_baseline' or
     'redBaseline'.

  5. References the green+coverage gate (BO-2400a-4): the file must reference
     'verify_green_and_coverage' or 'verifyGreenAndCoverage' or
     'green_and_coverage' or 'greenAndCoverage'.

  6. Does NOT contain 'ticket-supervisor' (BO-2400a-5): no per-ticket
     supervisor agent is dispatched.

  7. Does NOT contain a planner-as-agent dispatch (BO-2400a-5): the phase
     order is fixed and code-defined, not determined by an LLM planner.

  8. Is a single-worktree, single-command workflow (BO-2400a-5): no
     per-ticket worktree construction (no pattern like creating one worktree
     per ticket or per AC within the loop).

=== Red baseline ===

  All tests are RED because templates/workflows-js/fast-lane-build.js does
  not exist yet.  The AssertionError produced by the missing file IS the
  intended red state — it confirms the production code does not yet exist.

  Once llm-expert creates the file with the correct structure, all tests in
  this file must turn green.

=== Fixture-authenticity mandate (BO-2500c) ===

  These are pure text-parsing tests.  They read the REAL on-disk file
  templates/workflows-js/fast-lane-build.js.  No hand-typed JS content
  is used — the tests always read the actual file.
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
# Helper — read content or None
# ---------------------------------------------------------------------------


def _read_js_content() -> str | None:
    """Return the file content as a string, or None if the file does not exist."""
    if not _JS_PATH.exists():
        return None
    try:
        return _JS_PATH.read_text(encoding="utf-8")
    except OSError:
        return None


def _count_agent_calls(content: str) -> list[str]:
    """Return non-comment lines that contain an agent() function call.

    Specifically matches `agent(` with a word-boundary prefix to avoid
    false-positives from property names like `agentType`.  Skips lines
    that are pure JS line-comments or JSDoc/block-comment lines.

    Args:
        content: Raw JS file content.

    Returns:
        List of non-comment lines that contain at least one `agent(` call.
    """
    lines = content.split("\n")
    agent_lines = []
    for line in lines:
        stripped = line.strip()
        # Skip pure comment lines
        if (
            stripped.startswith("//")
            or stripped.startswith("*")
            or stripped.startswith("/*")
        ):
            continue
        # Match `agent(` as a function call (word-boundary ensures 'agentType' is excluded)
        if re.search(r"\bagent\s*\(", stripped):
            agent_lines.append(line)
    return agent_lines


# ---------------------------------------------------------------------------
# Base class with shared file-require helper
# ---------------------------------------------------------------------------


class _FastLaneRunnerTestBase(unittest.TestCase):
    """Base class providing _require_file() for all structural tests."""

    def _require_file(self) -> str:
        """Assert the JS file exists and return its content.

        Fails the test with a clear message if the file does not yet exist.
        This is the primary red state — coders must create the file.
        """
        content = _read_js_content()
        self.assertIsNotNone(
            content,
            f"templates/workflows-js/fast-lane-build.js does not exist at "
            f"{_JS_PATH}. llm-expert must create it — this is the red state "
            "confirming the production code does not yet exist.",
        )
        return content  # type: ignore[return-value]  # None case already asserted above


# ---------------------------------------------------------------------------
# TestFastLaneRunnerExists — prerequisite gate
# ---------------------------------------------------------------------------


class TestFastLaneRunnerExists(_FastLaneRunnerTestBase):
    """Structural prerequisite: the fast-lane-build.js file must exist."""

    def test_runner_file_exists(self) -> None:
        # covers: BO-2400a-5
        """The fast-lane runner script must exist at the expected path.

        This test is the primary red gate: it fails when the file has not been
        created yet, confirming the production code does not exist.

        To make this green, llm-expert must create:
            templates/workflows-js/fast-lane-build.js
        """
        self.assertTrue(
            _JS_PATH.exists(),
            f"templates/workflows-js/fast-lane-build.js must exist at {_JS_PATH}. "
            "llm-expert must create this file.",
        )

    def test_runner_file_is_non_empty(self) -> None:
        # covers: BO-2400a-5
        """The fast-lane runner script must not be empty."""
        content = self._require_file()
        self.assertGreater(
            len(content.strip()),
            50,
            "fast-lane-build.js must contain substantial content — not an empty file.",
        )


# ---------------------------------------------------------------------------
# TestMetaDeclaration — E2 workflow contract
# ---------------------------------------------------------------------------


class TestMetaDeclaration(_FastLaneRunnerTestBase):
    """The file must declare export const meta per the E2 workflow contract."""

    def test_export_const_meta_declared(self) -> None:
        # covers: BO-2400a-5
        """fast-lane-build.js must declare 'export const meta'.

        All Claude Code E2 workflow scripts export a meta object with name,
        description, and phases.  This is the structural contract for the engine.

        To make this green, fast-lane-build.js must contain the declaration.
        """
        content = self._require_file()
        self.assertIn(
            "export const meta",
            content,
            "fast-lane-build.js must declare 'export const meta' per the E2 "
            "workflow contract (same as build-feature.js, build-ticket.js).",
        )

    def test_meta_has_name_field(self) -> None:
        # covers: BO-2400a-5
        """meta must include a non-empty name field."""
        content = self._require_file()
        self.assertIn(
            "name:",
            content,
            "meta object must include a 'name:' field.",
        )
        # Reject empty name: name: "" or name: ''
        self.assertFalse(
            re.search(r"name\s*:\s*[\"'][\"']", content),
            "meta.name must not be empty.",
        )

    def test_meta_has_description_field(self) -> None:
        # covers: BO-2400a-5
        """meta must include a non-empty description field."""
        content = self._require_file()
        self.assertIn(
            "description:",
            content,
            "meta object must include a 'description:' field.",
        )


# ---------------------------------------------------------------------------
# TestExactlyTwoAgentDispatches — BO-2400a-1
# ---------------------------------------------------------------------------


class TestExactlyTwoAgentDispatches(_FastLaneRunnerTestBase):
    """The fast lane must dispatch EXACTLY one test-writer and one coder.

    AC scope: BO-2400a-1 — total invocation count == 2, independent of N.
    """

    def test_ac1_exactly_two_agent_calls(self) -> None:
        # covers: BO-2400a-1
        """fast-lane-build.js must contain exactly two agent() dispatches.

        The fast lane dispatches one test-writer and one coder — total 2.
        A count > 2 means per-AC or per-ticket agent fan-out (violates BO-2400a-1).
        A count < 2 means a phase is missing.

        To make this green, fast-lane-build.js must have exactly two agent( calls
        in non-comment lines.
        """
        content = self._require_file()
        agent_call_lines = _count_agent_calls(content)
        self.assertEqual(
            len(agent_call_lines),
            2,
            f"fast-lane-build.js must contain EXACTLY 2 agent() dispatches "
            f"(one test-writer + one coder), independent of batch size N.  "
            f"Found {len(agent_call_lines)} agent() lines (BO-2400a-1).\n"
            f"Lines found: {agent_call_lines}",
        )

    def test_ac1_test_writer_agent_dispatched(self) -> None:
        # covers: BO-2400a-1
        """One of the two agent dispatches must target the test-writer agent.

        The test-writer phase runs before the coder and writes the failing
        stubs for the whole batch.

        To make this green, fast-lane-build.js must reference 'test-writer'
        as an agentType in one of its two agent() calls.
        """
        content = self._require_file()
        self.assertIn(
            "test-writer",
            content,
            "fast-lane-build.js must dispatch the 'test-writer' agent "
            "as one of its two agent() calls (BO-2400a-1).",
        )

    def test_ac1_coder_agent_dispatched(self) -> None:
        # covers: BO-2400a-1
        """One of the two agent dispatches must target a coder agent.

        The coder phase (python-coder, sql-coder, frontend-coder, or llm-expert)
        makes the batch tests green after the test-writer writes them.

        To make this green, fast-lane-build.js must reference at least one
        coder agentType in its agent() calls.
        """
        content = self._require_file()
        coder_types = ("python-coder", "sql-coder", "frontend-coder", "llm-expert")
        self.assertTrue(
            any(coder in content for coder in coder_types),
            "fast-lane-build.js must dispatch at least one coder agent "
            f"({', '.join(coder_types)}) as one of its two agent() calls "
            "(BO-2400a-1).",
        )

    def test_ac1_agent_count_independent_of_batch_size(self) -> None:
        # covers: BO-2400a-1
        """The two agent() calls must NOT be inside a per-AC or per-ticket for-loop.

        If an agent() call appears inside a loop that iterates over ACs or
        tickets, the invocation count would scale with N — violating BO-2400a-1.
        The two calls must be flat (at the top-level of the workflow body, not
        nested inside a for-of or forEach loop over ACs).

        To make this green, fast-lane-build.js must have the two agent() calls
        at the top level, not inside a for-of/forEach loop body.

        We check this structurally: no agent() call line must be immediately
        preceded by a `for (` or `forEach(` loop over ACs/batch items.
        """
        content = self._require_file()
        # A per-AC loop would look like:
        #   for (const ac of batchAcs) { ... agent( ... ) ... }
        #   batchAcs.forEach(ac => { ... agent( ... ) ... })
        # We detect this by checking whether any agent() call appears inside
        # a for-of or forEach block that iterates over an AC/batch variable.
        per_ac_loop_with_agent = re.search(
            r"for\s*\(\s*(const|let|var)\s+\w+\s+of\s+\w+.*?\)\s*\{[^}]*\bagent\s*\(",
            content,
            re.DOTALL,
        )
        self.assertIsNone(
            per_ac_loop_with_agent,
            "agent() must NOT be called inside a per-AC/per-ticket for-of loop — "
            "the count must stay at 2 regardless of batch size N (BO-2400a-1).",
        )


# ---------------------------------------------------------------------------
# TestDeterministicGateReferences — BO-2400a-2, BO-2400a-3, BO-2400a-4
# ---------------------------------------------------------------------------


class TestDeterministicGateReferences(_FastLaneRunnerTestBase):
    """The runner must reference the deterministic script gates instead of LLM planners.

    AC scope: BO-2400a-2 (select_batch), BO-2400a-3 (red-baseline),
              BO-2400a-4 (green+coverage).
    """

    def test_ac2_references_select_batch_gate(self) -> None:
        # covers: BO-2400a-2
        """The file must reference the deterministic select_batch gate.

        Batch AC selection is performed by the Python script select_batch(),
        not by an LLM agent.  The runner must call or invoke this gate.

        To make this green, fast-lane-build.js must contain 'select_batch' or
        'selectBatch' to reference the deterministic selector.
        """
        content = self._require_file()
        has_select_batch_ref = (
            "select_batch" in content
            or "selectBatch" in content
        )
        self.assertTrue(
            has_select_batch_ref,
            "fast-lane-build.js must reference 'select_batch' or 'selectBatch' — "
            "the deterministic AC selection gate (BO-2400a-2).  Batch selection "
            "must be a script, not an LLM agent call.",
        )

    def test_ac3_references_red_baseline_gate(self) -> None:
        # covers: BO-2400a-3
        """The file must reference the red-baseline verification gate.

        The red-baseline gate runs before the coder is dispatched and verifies
        all batch tests fail.  It must be a deterministic script gate, not an
        agent judgment.

        To make this green, fast-lane-build.js must contain a reference to
        'verify_red_baseline', 'verifyRedBaseline', 'red_baseline', or
        'redBaseline'.
        """
        content = self._require_file()
        red_baseline_patterns = (
            "verify_red_baseline",
            "verifyRedBaseline",
            "red_baseline",
            "redBaseline",
        )
        has_red_baseline_ref = any(p in content for p in red_baseline_patterns)
        self.assertTrue(
            has_red_baseline_ref,
            "fast-lane-build.js must reference the red-baseline gate using one of: "
            f"{', '.join(red_baseline_patterns)}.  The gate must confirm all batch "
            "tests fail before the coder is dispatched (BO-2400a-3).",
        )

    def test_ac4_references_green_and_coverage_gate(self) -> None:
        # covers: BO-2400a-4
        """The file must reference the green+coverage verification gate.

        The green+coverage gate runs after the coder and verifies both that
        tests pass and that every AC id has a covering test.  It must be a
        deterministic script gate before commit staging.

        To make this green, fast-lane-build.js must contain a reference to
        'verify_green_and_coverage', 'verifyGreenAndCoverage',
        'green_and_coverage', or 'greenAndCoverage'.
        """
        content = self._require_file()
        coverage_patterns = (
            "verify_green_and_coverage",
            "verifyGreenAndCoverage",
            "green_and_coverage",
            "greenAndCoverage",
        )
        has_coverage_ref = any(p in content for p in coverage_patterns)
        self.assertTrue(
            has_coverage_ref,
            "fast-lane-build.js must reference the green+coverage gate using one of: "
            f"{', '.join(coverage_patterns)}.  The gate must confirm all tests pass "
            "AND every AC id is covered before commit staging (BO-2400a-4).",
        )

    def test_ac3_red_baseline_referenced_before_coder(self) -> None:
        # covers: BO-2400a-3
        """The red-baseline gate reference must appear before the coder agent dispatch.

        The sequencing constraint: select_batch → test-writer dispatch →
        red-baseline gate → coder dispatch → green+coverage gate.  The
        coder must NOT be dispatched before the red-baseline check.

        To make this green, the red-baseline reference must appear textually
        before the coder agent dispatch in the file.
        """
        content = self._require_file()
        red_baseline_patterns = (
            "verify_red_baseline",
            "verifyRedBaseline",
            "red_baseline",
            "redBaseline",
        )
        coder_types = ("python-coder", "sql-coder", "frontend-coder", "llm-expert")

        # Find the first position of a red-baseline reference
        red_positions = [
            content.find(p) for p in red_baseline_patterns if content.find(p) != -1
        ]
        coder_positions = [
            content.find(c) for c in coder_types if content.find(c) != -1
        ]

        if not red_positions or not coder_positions:
            # If either is missing, the existence tests above will catch it.
            return

        first_red_pos = min(red_positions)
        first_coder_pos = min(coder_positions)

        self.assertLess(
            first_red_pos,
            first_coder_pos,
            "The red-baseline gate reference must appear BEFORE the coder agent "
            "dispatch in fast-lane-build.js — the coder must not run before the "
            "baseline is verified (BO-2400a-3).",
        )


# ---------------------------------------------------------------------------
# TestNoHeavyPathConstructs — BO-2400a-5
# ---------------------------------------------------------------------------


class TestNoHeavyPathConstructs(_FastLaneRunnerTestBase):
    """The fast lane must NOT use heavy-path coordination constructs.

    AC scope: BO-2400a-5 — no ticket-supervisor, no planner-as-agent,
              single worktree / single command.
    """

    def test_ac5_no_ticket_supervisor_dispatched(self) -> None:
        # covers: BO-2400a-5
        """fast-lane-build.js must NOT reference 'ticket-supervisor' as an agent type.

        Per-ticket supervisor dispatch is a heavy-path construct.  The fast
        lane inlines phase dispatch directly (no supervisor nesting).

        To make this green, fast-lane-build.js must not contain 'ticket-supervisor'.
        """
        content = self._require_file()
        self.assertNotIn(
            "ticket-supervisor",
            content,
            "fast-lane-build.js must NOT dispatch a 'ticket-supervisor' agent — "
            "that is the heavy-path construct.  Phase sequencing is inlined in the "
            "fast-lane loop (BO-2400a-5).",
        )

    def test_ac5_no_planner_as_agent_invocation(self) -> None:
        # covers: BO-2400a-5
        """fast-lane-build.js must NOT dispatch a planner agent to sequence the phases.

        The phase order is fixed and code-defined in the fast lane.  No LLM
        planner decides the sequence at runtime.  Constructs like dispatching
        an agent with agentType containing 'planner' or calling
        workflow('plan-feature') are forbidden.

        To make this green, fast-lane-build.js must not contain a planner
        agent dispatch.
        """
        content = self._require_file()
        # Check for explicit planner agent dispatch patterns
        planner_dispatch = re.search(
            r"agentType\s*:\s*[\"'].*planner.*[\"']",
            content,
            re.IGNORECASE,
        )
        self.assertIsNone(
            planner_dispatch,
            "fast-lane-build.js must NOT dispatch a planner agent.  "
            "The phase order is code-defined, not an LLM decision (BO-2400a-5).",
        )

        # Also check for workflow('plan-feature') style calls
        self.assertNotIn(
            "plan-feature",
            content,
            "fast-lane-build.js must NOT invoke the plan-feature workflow — "
            "the fast lane has no LLM planner in its loop (BO-2400a-5).",
        )

    def test_ac5_no_per_ticket_worktree_construction(self) -> None:
        # covers: BO-2400a-5
        """The fast lane must NOT create per-ticket worktrees.

        The heavy path uses a separate worktree per ticket; the fast lane must
        operate within a single worktree under a single command invocation.

        To make this green, fast-lane-build.js must not contain patterns that
        create a new worktree per ticket (e.g. calling worktree-agent per ticket
        or constructing ticket-specific worktree paths in a loop).
        """
        content = self._require_file()
        # The heavy path creates per-ticket worktrees.
        # Detect this by looking for worktree-agent dispatch inside a loop.
        worktree_agent_in_loop = re.search(
            r"for\s*\(\s*(?:const|let|var)\s+\w+.*?\)\s*\{[^}]*worktree-agent",
            content,
            re.DOTALL,
        )
        self.assertIsNone(
            worktree_agent_in_loop,
            "fast-lane-build.js must NOT dispatch 'worktree-agent' per ticket "
            "in a loop — the fast lane uses a single worktree (BO-2400a-5).",
        )

    def test_ac5_not_three_command_three_worktree_pattern(self) -> None:
        # covers: BO-2400a-5
        """The fast lane must not split into three commands across three worktrees.

        The heavy-path signature is three separate command invocations in three
        worktrees.  The fast lane must operate as a single command.

        To make this green, fast-lane-build.js must be a self-contained single
        workflow that does NOT reference three distinct worktree paths
        (test_worktree, coder_worktree, commit_worktree or similar).
        """
        content = self._require_file()
        # Check for multiple distinct worktree path variables (the three-worktree smell)
        worktree_vars = re.findall(r"\bworktree_path\w*\b", content)
        unique_worktree_vars = set(worktree_vars)
        self.assertLessEqual(
            len(unique_worktree_vars),
            1,
            f"fast-lane-build.js must use at most ONE worktree path variable — "
            f"found {len(unique_worktree_vars)}: {unique_worktree_vars}.  "
            "The three-worktree heavy pattern is forbidden here (BO-2400a-5).",
        )


if __name__ == "__main__":
    unittest.main()
