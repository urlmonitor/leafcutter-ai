"""
MODULE: unit_tests/workflows/test_bo2400a_runner_structure.py
GOAL: Structural tests for BO-2400a-1, BO-2400a-2 (gate reference),
      BO-2400a-3 (gate reference), BO-2400a-4 (gate reference), BO-2400a-5.

=== BO-2400c-1-v migration note (this file was re-pointed) ===

`templates/workflows-js/fast-lane-build.js` is an ORPHANED second fast-lane
runner — nothing invokes it. The `/fast-lane-build` command routes to
`templates/workflows-js/fast-lane-ship.js`, which is the lane that actually
runs. This file held the SOLE proof for BO-2400a-1 and BO-2400a-5 (both
`done`), so before the orphan could be deleted the target had to move to the
live lane. A blunt path swap does NOT work: fast-lane-ship.js has ~20
non-comment agent() call sites (worktree, resolver, producibility, claim,
context-bundle, test-writer, coder, review, changelog, commit, PR, plus
release-branch retries) where the orphan had exactly 2, and it references no
`select_batch`/`selectBatch` string at all — it resolves a connected build
set via `select_connected` instead. See each test's docstring below for how
the assertion was rewritten (or, for BO-2400a-2, broadened) to state honestly
what the live lane actually does, rather than being re-aimed at an unrelated
string that merely happens to appear in the file.

=== Target file ===

Location: templates/workflows-js/fast-lane-ship.js

Required structural properties (re-expressed for the live lane):

  1. Declares `export const meta` (standard E2 workflow contract).

  2. Dispatches EXACTLY ONE test-writer agent and EXACTLY ONE coder agent as
     flat, non-looped call sites (BO-2400a-1) — the invocation count must not
     grow with the number of ACs in the resolved connected build set. Unlike
     the orphan (whose ENTIRE workflow was two agent() calls), the live lane
     has ~20 call sites total (worktree, resolve, claim, review, commit, PR,
     etc.) because it does the full ship arc, not just the lean build loop.
     The invariant BO-2400a-1 actually protects — one test-writer dispatch,
     one coder dispatch, neither multiplied by batch size N — is checked via
     each dispatch's unique `label:` anchor, not via a raw agent()-call count.

  3. References a deterministic, script-driven AC-selection mechanism
     (BO-2400a-2) — selection performed by a python script, never by an LLM
     planner's judgment. The orphan named this `select_batch`; the live lane
     performs the equivalent role (deterministic, script-resolved AC ids,
     consumed downstream) under the name `select_connected`. Both are
     accepted.

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
     per ticket or per AC within a loop).

=== Fixture-authenticity mandate (BO-2500c) ===

  These are pure text-parsing tests.  They read the REAL on-disk file
  templates/workflows-js/fast-lane-ship.js.  No hand-typed JS content
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
_JS_PATH = _REPO_ROOT / "templates" / "workflows-js" / "fast-lane-ship.js"


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


def _strip_comment_lines(content: str) -> str:
    """Return content with pure comment lines removed, preserving line order.

    Uses the same stripping rule as `_count_agent_calls` (skip lines that are
    pure JS line-comments, JSDoc lines, or block-comment lines). Raw string
    positions computed via `.find()` on the RESULT reflect the actual code
    sequence, rather than being skewed by a header/JSDoc comment that mentions
    an implementation detail (e.g. a coder agentType) out of real execution
    order — exactly the false-positive/false-negative trap a naive
    `content.find()` on the whole file falls into (see
    test_ac3_red_baseline_referenced_before_coder below).

    Args:
        content: Raw JS file content.

    Returns:
        The content with comment-only lines removed, newline-joined.
    """
    kept = []
    for line in content.split("\n"):
        stripped = line.strip()
        if (
            stripped.startswith("//")
            or stripped.startswith("*")
            or stripped.startswith("/*")
        ):
            continue
        kept.append(line)
    return "\n".join(kept)


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
            f"templates/workflows-js/fast-lane-ship.js does not exist at "
            f"{_JS_PATH}. This is the live fast lane — it must exist.",
        )
        return content  # type: ignore[return-value]  # None case already asserted above


# ---------------------------------------------------------------------------
# TestFastLaneRunnerExists — prerequisite gate
# ---------------------------------------------------------------------------


class TestFastLaneRunnerExists(_FastLaneRunnerTestBase):
    """Structural prerequisite: the fast-lane-ship.js file must exist."""

    def test_runner_file_exists(self) -> None:
        # covers: BO-2400a-5
        """The live fast-lane runner script must exist at the expected path."""
        self.assertTrue(
            _JS_PATH.exists(),
            f"templates/workflows-js/fast-lane-ship.js must exist at {_JS_PATH}.",
        )

    def test_runner_file_is_non_empty(self) -> None:
        # covers: BO-2400a-5
        """The fast-lane runner script must not be empty."""
        content = self._require_file()
        self.assertGreater(
            len(content.strip()),
            50,
            "fast-lane-ship.js must contain substantial content — not an empty file.",
        )


# ---------------------------------------------------------------------------
# TestMetaDeclaration — E2 workflow contract
# ---------------------------------------------------------------------------


class TestMetaDeclaration(_FastLaneRunnerTestBase):
    """The file must declare export const meta per the E2 workflow contract."""

    def test_export_const_meta_declared(self) -> None:
        # covers: BO-2400a-5
        """fast-lane-ship.js must declare 'export const meta'.

        All Claude Code E2 workflow scripts export a meta object with name,
        description, and phases.  This is the structural contract for the engine.
        """
        content = self._require_file()
        self.assertIn(
            "export const meta",
            content,
            "fast-lane-ship.js must declare 'export const meta' per the E2 "
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
    """The fast lane must dispatch exactly one test-writer and one coder call
    site, each flat and independent of batch size N.

    AC scope: BO-2400a-1.

    Migration note (BO-2400c-1-v): the orphan's ENTIRE workflow was two
    agent() calls, so "exactly two agent() calls in the file" and "one
    test-writer + one coder dispatch" were the same fact. The live lane
    (fast-lane-ship.js) does the full ship arc — worktree, resolve,
    producibility, claim, context-bundle, test-writer, coder, review,
    changelog, commit, PR, plus release-on-failure retries — so it has ~20
    non-comment agent() call sites. A literal "count == 2" assertion is
    therefore false on its face for the live lane and would have to be
    dropped or lied about. The invariant BO-2400a-1 actually protects survives
    intact, though: "one test-writer dispatch and one coder dispatch, neither
    multiplied by batch size N." That is checked below via each dispatch's
    unique `label:` anchor (`"test-writer-connected"` / `"coder-connected"`),
    which occurs exactly once each in the live lane regardless of how many AC
    ids are in the resolved connected build set.
    """

    def test_ac1_single_test_writer_and_single_coder_dispatch(self) -> None:
        # covers: BO-2400a-1
        """The test-writer and coder agent dispatches are each a single call site.

        Counts occurrences of each dispatch's unique `label:` anchor —
        `"test-writer-connected"` for the test-writer phase and
        `"coder-connected"` for the coder phase. Each label is assigned to
        exactly one `agent()` call in the file, so a count of 1 for each
        proves the dispatch is a single flat call, not one multiplied by the
        number of AC ids in the resolved connected build set (BO-2400a-1). A
        count > 1 would mean the dispatch was duplicated or moved inside a
        per-AC loop; a count of 0 would mean the phase went missing.
        """
        content = self._require_file()
        test_writer_dispatches = content.count('label: "test-writer-connected"')
        coder_dispatches = content.count('label: "coder-connected"')
        self.assertEqual(
            test_writer_dispatches,
            1,
            "fast-lane-ship.js must dispatch the test-writer agent exactly "
            f"once (found {test_writer_dispatches} occurrences of "
            'label: "test-writer-connected") — the dispatch must not be '
            "duplicated or multiplied by batch size N (BO-2400a-1).",
        )
        self.assertEqual(
            coder_dispatches,
            1,
            "fast-lane-ship.js must dispatch the coder agent exactly once "
            f"(found {coder_dispatches} occurrences of "
            'label: "coder-connected") — the dispatch must not be duplicated '
            "or multiplied by batch size N (BO-2400a-1).",
        )

    def test_ac1_test_writer_agent_dispatched(self) -> None:
        # covers: BO-2400a-1
        """One of the agent dispatches must target the test-writer agent.

        The test-writer phase runs before the coder and writes the failing
        stubs for the whole resolved build set.
        """
        content = self._require_file()
        self.assertIn(
            "test-writer",
            content,
            "fast-lane-ship.js must dispatch the 'test-writer' agent "
            "(BO-2400a-1).",
        )

    def test_ac1_coder_agent_dispatched(self) -> None:
        # covers: BO-2400a-1
        """One of the agent dispatches must target a coder agent.

        The coder phase (python-coder, sql-coder, frontend-coder, or llm-expert)
        makes the batch tests green after the test-writer writes them.
        """
        content = self._require_file()
        coder_types = ("python-coder", "sql-coder", "frontend-coder", "llm-expert")
        self.assertTrue(
            any(coder in content for coder in coder_types),
            "fast-lane-ship.js must dispatch at least one coder agent "
            f"({', '.join(coder_types)}) (BO-2400a-1).",
        )

    def test_ac1_agent_count_independent_of_batch_size(self) -> None:
        # covers: BO-2400a-1
        """The test-writer/coder agent() calls must NOT be inside a per-AC for-loop.

        If an agent() call appears inside a loop that iterates over ACs or
        tickets, the invocation count would scale with N — violating BO-2400a-1.
        The live lane in fact contains NO for-loops at all (confirmed via a
        direct grep of the file during migration) — its resolved AC ids are
        threaded through as a single joined string (`batchIds`) into the
        dispatch prompts, never iterated to produce one call per id.

        We check this structurally: no agent() call line must be immediately
        preceded by a `for (` or `forEach(` loop over ACs/batch items.
        """
        content = self._require_file()
        # A per-AC loop would look like:
        #   for (const ac of acIds) { ... agent( ... ) ... }
        #   acIds.forEach(ac => { ... agent( ... ) ... })
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
            "the test-writer and coder dispatch counts must stay at 1 each "
            "regardless of batch size N (BO-2400a-1).",
        )


# ---------------------------------------------------------------------------
# TestDeterministicGateReferences — BO-2400a-2, BO-2400a-3, BO-2400a-4
# ---------------------------------------------------------------------------


class TestDeterministicGateReferences(_FastLaneRunnerTestBase):
    """The runner must reference the deterministic script gates instead of LLM planners.

    AC scope: BO-2400a-2 (deterministic AC-selection gate), BO-2400a-3
              (red-baseline), BO-2400a-4 (green+coverage).
    """

    def test_ac2_references_deterministic_ac_selection_gate(self) -> None:
        # covers: BO-2400a-2
        """The file must reference a deterministic, script-driven AC-selection gate.

        AC selection must be performed by a Python script, not by an LLM
        agent's judgment. The orphan (fast-lane-build.js) named this gate
        `select_batch` — "pick the next N approved ACs from the store." The
        live lane (fast-lane-ship.js) performs the equivalent role under the
        name `select_connected`: it resolves the connected build set for one
        AC id (subtree + unmet-dependency closure, in dependency order) via
        the same `fast_lane.py` gate script, and the LLM dispatch that runs it
        (`agentType: "status-checker"`, label `"resolve-connected"`) is
        instructed to parse the script's JSON stdout verbatim, not to decide
        the set itself.

        This is a genuine, honestly-verified analog, not a re-aim at an
        unrelated string: both names denote "a python script — not an LLM
        planner — decides which AC id(s) this run builds," and grep-confirmed
        during migration that `fast-lane-ship.js` contains no `select_batch`/
        `selectBatch` string at all, so re-pointing this test verbatim (rather
        than broadening it) would make it silently and permanently fail red.

        Note (BO-2400a-2 is NOT sole-proofed by this file): other test files
        cover BO-2400a-2 independently, so a defect in this specific
        assertion's honesty judgment does not leave the AC unguarded.
        """
        content = self._require_file()
        has_deterministic_selector_ref = (
            "select_batch" in content
            or "selectBatch" in content
            or "select_connected" in content
            or "selectConnected" in content
        )
        self.assertTrue(
            has_deterministic_selector_ref,
            "fast-lane-ship.js must reference 'select_batch'/'selectBatch' or "
            "'select_connected'/'selectConnected' — a deterministic, "
            "script-driven AC-selection gate (BO-2400a-2). AC selection must "
            "be a script call, not an LLM agent's judgment.",
        )

    def test_ac3_references_red_baseline_gate(self) -> None:
        # covers: BO-2400a-3
        """The file must reference the red-baseline verification gate.

        The red-baseline gate runs before the coder is dispatched and verifies
        at least one newly-added covering test is red.  It must be a
        deterministic script gate, not an agent judgment.
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
            "fast-lane-ship.js must reference the red-baseline gate using one of: "
            f"{', '.join(red_baseline_patterns)}.  The gate must confirm the "
            "resolved build set is red before the coder is dispatched (BO-2400a-3).",
        )

    def test_ac4_references_green_and_coverage_gate(self) -> None:
        # covers: BO-2400a-4
        """The file must reference the green+coverage verification gate.

        The green+coverage gate runs after the coder and verifies both that
        tests pass and that every AC id has a covering test.  It must be a
        deterministic script gate before commit staging.
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
            "fast-lane-ship.js must reference the green+coverage gate using one of: "
            f"{', '.join(coverage_patterns)}.  The gate must confirm all tests pass "
            "AND every AC id is covered before commit staging (BO-2400a-4).",
        )

    def test_ac3_red_baseline_referenced_before_coder(self) -> None:
        # covers: BO-2400a-3
        """The red-baseline gate reference must precede the coder agent dispatch
        in REAL CONTROL FLOW — not in raw whole-file string position.

        Migration note (BO-2400c-1-v): a raw `content.find()` comparison over
        the WHOLE file (comments included) gives a FALSE answer here. The
        module's JSDoc header (line 14, "the two-agent test-writer →
        python-coder loop") mentions "python-coder" before the header even
        reaches "verify_red_baseline" (line 16) — confirmed by direct
        measurement during migration: raw `content.find("python-coder")` ==
        832 while raw `content.find("verify_red_baseline")` == 952, so the
        original assertLess(red_pos, coder_pos) would assert 952 < 832 and
        FAIL, even though the real runtime ordering is correct.

        This rewrite establishes ordering from real control flow instead:

          1. `_strip_comment_lines()` removes every line that is a pure JS
             line-comment, block-comment, or JSDoc line, so a header mention
             can no longer masquerade as a code-level reference.
          2. The coder anchor is `label: "coder-connected"` — the unique
             `label:` field on the ONE agent() call that is the actual coder
             dispatch (see test_ac1_single_test_writer_and_single_coder_dispatch
             above). This is deliberately NOT a bare "python-coder" substring
             search: that string also appears, in real non-comment code,
             earlier in the file as the `RELEASE_EXECUTOR_AGENT_TYPE` constant
             and inside the context-bundle phase's agentType — neither of
             which is the coder dispatch this AC is about. Anchoring on the
             call site's own unique label points at the actual dispatch, not
             at a decoy.
          3. Because this is a single-threaded, top-to-bottom E2 script with
             no loops or gotos, source line order among comment-stripped
             top-level statements IS real execution order — so a `.find()`
             comparison on the stripped text is a sound proxy for "ran before."
        """
        content = self._require_file()
        code_only = _strip_comment_lines(content)
        red_baseline_patterns = (
            "verify_red_baseline",
            "verifyRedBaseline",
            "red_baseline",
            "redBaseline",
        )
        coder_dispatch_anchor = 'label: "coder-connected"'

        red_positions = [
            code_only.find(p) for p in red_baseline_patterns if code_only.find(p) != -1
        ]
        coder_pos = code_only.find(coder_dispatch_anchor)

        if not red_positions or coder_pos == -1:
            # If either is missing, the existence tests above will catch it.
            return

        first_red_pos = min(red_positions)

        self.assertLess(
            first_red_pos,
            coder_pos,
            "The red-baseline gate reference must appear (in real, non-comment "
            "control flow) BEFORE the coder agent dispatch "
            f"({coder_dispatch_anchor!r}) in fast-lane-ship.js — the coder "
            "must not run before the baseline is verified (BO-2400a-3).",
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
        """fast-lane-ship.js must NOT reference 'ticket-supervisor' as an agent type.

        Per-ticket supervisor dispatch is a heavy-path construct.  The fast
        lane inlines phase dispatch directly (no supervisor nesting).
        """
        content = self._require_file()
        self.assertNotIn(
            "ticket-supervisor",
            content,
            "fast-lane-ship.js must NOT dispatch a 'ticket-supervisor' agent — "
            "that is the heavy-path construct.  Phase sequencing is inlined in the "
            "fast-lane loop (BO-2400a-5).",
        )

    def test_ac5_no_planner_as_agent_invocation(self) -> None:
        # covers: BO-2400a-5
        """fast-lane-ship.js must NOT dispatch a planner agent to sequence the phases.

        The phase order is fixed and code-defined in the fast lane.  No LLM
        planner decides the sequence at runtime.  Constructs like dispatching
        an agent with agentType containing 'planner' or calling
        workflow('plan-feature') are forbidden.
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
            "fast-lane-ship.js must NOT dispatch a planner agent.  "
            "The phase order is code-defined, not an LLM decision (BO-2400a-5).",
        )

        # Also check for workflow('plan-feature') style calls
        self.assertNotIn(
            "plan-feature",
            content,
            "fast-lane-ship.js must NOT invoke the plan-feature workflow — "
            "the fast lane has no LLM planner in its loop (BO-2400a-5).",
        )

    def test_ac5_no_per_ticket_worktree_construction(self) -> None:
        # covers: BO-2400a-5
        """The fast lane must NOT create per-ticket worktrees.

        The heavy path uses a separate worktree per ticket; the fast lane must
        operate within a single worktree under a single command invocation.
        fast-lane-ship.js in fact dispatches 'worktree-agent' exactly once,
        at the top level (Phase 1, "Worktree"), never inside a loop.
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
            "fast-lane-ship.js must NOT dispatch 'worktree-agent' per ticket "
            "in a loop — the fast lane uses a single worktree (BO-2400a-5).",
        )

    def test_ac5_not_three_command_three_worktree_pattern(self) -> None:
        # covers: BO-2400a-5
        """The fast lane must not split into three commands across three worktrees.

        The heavy-path signature is three separate command invocations in three
        worktrees.  The fast lane must operate as a single command.

        KNOWN WEAKNESS (flagged during BO-2400c-1-v migration, carried forward
        rather than silently inherited): this regex only matches the literal
        snake_case substring `worktree_path`. fast-lane-ship.js names its
        actual path variable `worktreePath` (camelCase) and uses the literal
        string `"worktree_path"` only as an OUTPUT FIELD KEY repeated ~20
        times across its various return payloads — always the SAME string,
        so `set(...)` collapses it to size 1 and this assertion passes. It
        would pass just as vacuously on a genuinely reintroduced
        three-worktree pattern if that pattern also used camelCase or a
        different key name; it does not, on its own, prove single-worktree
        behaviour for this file. That structural fact IS independently
        verified by test_ac5_no_per_ticket_worktree_construction above (single
        'worktree-agent' dispatch, not looped) and by the worktree phase's
        own code (Phase 1 dispatches worktree-agent exactly once). This test
        is retained unmodified — not strengthened — because the migration
        task's mandate was to repair what a blunt path swap breaks; this
        assertion still returns a pass either way, so it does not need
        repair, but its pass here should not be read as meaningful proof.
        """
        content = self._require_file()
        # Check for multiple distinct worktree path variables (the three-worktree smell)
        worktree_vars = re.findall(r"\bworktree_path\w*\b", content)
        unique_worktree_vars = set(worktree_vars)
        self.assertLessEqual(
            len(unique_worktree_vars),
            1,
            f"fast-lane-ship.js must use at most ONE worktree path variable — "
            f"found {len(unique_worktree_vars)}: {unique_worktree_vars}.  "
            "The three-worktree heavy pattern is forbidden here (BO-2400a-5).",
        )


if __name__ == "__main__":
    unittest.main()
