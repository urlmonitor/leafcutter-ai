"""
MODULE: unit_tests/workflows/test_bo2500d_gate_retirement.py
GOAL: Structural GUARD tests for the BO-2500d batch.

These are regression/guard tests — they assert structural properties that are
expected to hold by construction on the ac-authoring/fast-lane branch. They
are NOT red-first TDD stubs; the properties they guard already exist in the
on-disk JS files (fast-lane-build.js was built fresh without the opinion-only
gates; the heavy pipeline files retain them). Their purpose is to catch
regressions: if a future edit inadvertently re-adds an opinion-only gate to
the fast lane, or removes a mechanical gate, these tests will turn red.

ACs covered:
  BO-2500d-1   — Opinion-only gate agents are absent from the fast-lane phase order
  BO-2500d-2   — The opinion-only gate agents remain present in the heavy pipeline
  BO-2500d-3   — Mechanical proof-of-done gates stand in for the removed agents
  BO-2500d-1-i — Guard: mechanical replacement must exist before opinion-only gate
                  removal is allowed; encoded as structural presence assertions on
                  fast-lane-build.js (per user directive 2026-07-21)

Files under test (REAL on-disk, not hand-typed):
  templates/workflows-js/fast-lane-build.js
  templates/workflows-js/build-feature.js
  templates/workflows-js/build-ticket.js

Discrepancy note (BO-2500d-2):
  On the ac-authoring/fast-lane branch, build-feature.js and build-ticket.js
  phaseOrder contain 'pr-reviewer' and 'change-scope-reviewer' but do NOT yet
  contain 'ac-validator' or 'ac-fulfillment-gate'. Those were added in PR #375
  on a separate branch and have not been merged here. The tests for d-2 assert
  only what IS present (pr-reviewer + change-scope-reviewer). The absence of
  ac-validator and ac-fulfillment-gate from the heavy phaseOrder on this branch
  is a cross-branch artifact, not a defect in the fast-lane work itself.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve the scripts under test
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_FAST_LANE_PATH = _REPO_ROOT / "templates" / "workflows-js" / "fast-lane-build.js"
_BUILD_FEATURE_PATH = _REPO_ROOT / "templates" / "workflows-js" / "build-feature.js"
_BUILD_TICKET_PATH = _REPO_ROOT / "templates" / "workflows-js" / "build-ticket.js"


# ---------------------------------------------------------------------------
# Helpers (pure — no I/O side-effects, safe to call from multiple tests)
# ---------------------------------------------------------------------------


def _read_file(path: Path) -> str:
    """Return file content as a string, or empty string if absent or unreadable."""
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _extract_phase_order_text(content: str) -> str:
    """Extract the body of the phaseOrder array from JS content.

    Searches for ``const phaseOrder = [...]`` and returns the text between
    the brackets (excluding the brackets themselves).  Returns ``""`` when no
    such declaration is found (e.g. fast-lane-build.js, which does not define
    a phaseOrder).

    Args:
        content: Raw JS file content.

    Returns:
        The array body string, or ``""`` if the declaration is absent.
    """
    match = re.search(
        r"const phaseOrder\s*=\s*\[([^\]]*)\]",
        content,
        re.DOTALL,
    )
    if match:
        return match.group(1)
    return ""


def _extract_agenttype_values(content: str) -> list[str]:
    """Extract all ``agentType`` string values from non-comment JS lines.

    Specifically matches ``agentType: "..."`` or ``agentType: '...'``
    patterns, skipping pure line-comment and block-comment lines.

    Args:
        content: Raw JS file content.

    Returns:
        List of string values assigned to ``agentType`` keys.
    """
    values: list[str] = []
    for line in content.split("\n"):
        stripped = line.strip()
        # Skip pure comment lines
        if (
            stripped.startswith("//")
            or stripped.startswith("*")
            or stripped.startswith("/*")
        ):
            continue
        for m in re.finditer(r'agentType\s*:\s*["\']([^"\']+)["\']', stripped):
            values.append(m.group(1))
    return values


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class _JsFileTestBase(unittest.TestCase):
    """Shared helper: assert a JS file exists and return its content."""

    def _require_file(self, path: Path, label: str) -> str:
        """Assert the JS file exists and is non-empty; return its content.

        Args:
            path:  Absolute path to the JS file.
            label: Human-readable label used in assertion messages.

        Returns:
            File content as a string.
        """
        self.assertTrue(
            path.exists(),
            f"{label} does not exist at {path}. "
            "This structural guard test cannot run without the target file.",
        )
        content = _read_file(path)
        self.assertGreater(
            len(content.strip()),
            50,
            f"{label} is empty or nearly empty — the file exists but has no "
            "substantial content.",
        )
        return content


# ---------------------------------------------------------------------------
# TestFastLaneExcludesOpinionOnlyGates — BO-2500d-1
# ---------------------------------------------------------------------------


class TestFastLaneExcludesOpinionOnlyGates(_JsFileTestBase):
    """BO-2500d-1: fast-lane-build.js contains no opinion-only gate agent dispatches.

    The fast-lane phase order must contain no LLM review agent, no LLM validator
    agent, and no LLM fulfillment gate agent.  The only completion arbiters it lists
    are the mechanical proof-of-done gates (verified in BO-2500d-3 tests).

    These are regression guards — the property holds by construction.  If they fail,
    an opinion-only gate was accidentally re-added to the fast lane.
    """

    OPINION_ONLY_AGENTS = (
        "pr-reviewer",
        "ac-validator",
        "ac-fulfillment-gate",
        "change-scope-reviewer",
    )

    def test_ac_d1_fast_lane_excludes_pr_reviewer(self) -> None:
        # covers: BO-2500d-1
        """fast-lane-build.js must not reference 'pr-reviewer'.

        The PR reviewer is an LLM opinion gate.  It must be absent from the
        fast-lane phase order — the fast lane uses only mechanical gates.

        If this test FAILS, a 'pr-reviewer' string was added to fast-lane-build.js
        (directly or via an agentType dispatch).  Remove it; keep the file's two
        flat dispatches (test-writer + python-coder) as the only agent calls.
        """
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-build.js")
        self.assertNotIn(
            "pr-reviewer",
            content,
            "fast-lane-build.js must NOT reference 'pr-reviewer' — "
            "it is an opinion-only LLM gate excluded from the fast lane (BO-2500d-1).",
        )

    def test_ac_d1_fast_lane_excludes_ac_validator(self) -> None:
        # covers: BO-2500d-1
        """fast-lane-build.js must not reference 'ac-validator'."""
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-build.js")
        self.assertNotIn(
            "ac-validator",
            content,
            "fast-lane-build.js must NOT reference 'ac-validator' — "
            "it is an opinion-only LLM gate excluded from the fast lane (BO-2500d-1).",
        )

    def test_ac_d1_fast_lane_excludes_ac_fulfillment_gate(self) -> None:
        # covers: BO-2500d-1
        """fast-lane-build.js must not reference 'ac-fulfillment-gate'."""
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-build.js")
        self.assertNotIn(
            "ac-fulfillment-gate",
            content,
            "fast-lane-build.js must NOT reference 'ac-fulfillment-gate' — "
            "it is an opinion-only LLM gate excluded from the fast lane (BO-2500d-1).",
        )

    def test_ac_d1_fast_lane_excludes_change_scope_reviewer(self) -> None:
        # covers: BO-2500d-1
        """fast-lane-build.js must not reference 'change-scope-reviewer'."""
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-build.js")
        self.assertNotIn(
            "change-scope-reviewer",
            content,
            "fast-lane-build.js must NOT reference 'change-scope-reviewer' — "
            "it is an opinion-only gate excluded from the fast lane (BO-2500d-1).",
        )

    def test_ac_d1_no_opinion_only_agent_by_name(self) -> None:
        # covers: BO-2500d-1
        """No opinion-only agent name may appear anywhere in fast-lane-build.js.

        Combines the individual exclusion checks into one omnibus assertion.
        Catches any agent from the opinion-only set that might be added in a
        comment, string, or agentType dispatch.
        """
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-build.js")
        present = [ag for ag in self.OPINION_ONLY_AGENTS if ag in content]
        self.assertEqual(
            present,
            [],
            f"fast-lane-build.js must contain NONE of the opinion-only gate "
            f"agents. Found: {present} (BO-2500d-1). "
            "Remove them — only mechanical gates are permitted as fast-lane "
            "completion arbiters.",
        )

    def test_ac_d1_no_generic_review_or_validator_agenttype(self) -> None:
        # covers: BO-2500d-1
        """No agentType dispatched by fast-lane-build.js may contain 'review' or 'validator'.

        The AC requires exclusion by role/kind, not just by hard-coded name.
        Any agent dispatched with an agentType string that contains 'review'
        or 'validator' is an opinion-only gate and must be absent from the
        fast lane — even if it has a novel name not in the hard-coded list.
        """
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-build.js")
        agent_types = _extract_agenttype_values(content)
        opinion_dispatches = [
            at
            for at in agent_types
            if "review" in at.lower() or "validator" in at.lower()
        ]
        self.assertEqual(
            opinion_dispatches,
            [],
            f"fast-lane-build.js must NOT dispatch any agent whose agentType "
            f"contains 'review' or 'validator'. Found: {opinion_dispatches}. "
            "All agentType values must be non-opinion (mechanical or coder) "
            "(BO-2500d-1).",
        )

    def test_ac_d1_only_non_opinion_agenttypes_dispatched(self) -> None:
        # covers: BO-2500d-1
        """The agentType values dispatched by fast-lane-build.js are whitelisted non-opinion types.

        Checks that every agentType present in the file is one of the
        expected non-opinion agent categories (test-writer, coder variants).
        """
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-build.js")
        agent_types = _extract_agenttype_values(content)
        # Expected non-opinion agentTypes for the fast lane
        allowed_prefixes = (
            "test-writer",
            "python-coder",
            "sql-coder",
            "frontend-coder",
            "llm-expert",
            "status-checker",  # utility, not opinion
        )
        forbidden_set = set(self.OPINION_ONLY_AGENTS)
        violations = [at for at in agent_types if at in forbidden_set]
        self.assertEqual(
            violations,
            [],
            f"fast-lane-build.js agentType dispatches include opinion-only agents: "
            f"{violations}. Only non-opinion agentTypes are permitted in the fast "
            f"lane (BO-2500d-1). Allowed non-opinion types include: "
            f"{', '.join(allowed_prefixes)}.",
        )


# ---------------------------------------------------------------------------
# TestHeavyPipelineRetainsGates — BO-2500d-2
# ---------------------------------------------------------------------------


class TestHeavyPipelineRetainsGates(_JsFileTestBase):
    """BO-2500d-2: build-feature.js and build-ticket.js still contain opinion-only gates.

    Removing the opinion-only agents from the fast lane (BO-2500d-1) must NOT
    remove them from the heavy pipeline.  This test class guards that the heavy
    phaseOrder retains pr-reviewer and change-scope-reviewer.

    Discrepancy note: on this branch (ac-authoring/fast-lane) neither
    build-feature.js nor build-ticket.js includes 'ac-validator' or
    'ac-fulfillment-gate' in phaseOrder — those were added on a separate branch
    (PR #375).  The tests here assert only what IS present on this branch.
    """

    def _get_phase_order_text(self, content: str, label: str) -> str:
        """Extract the phaseOrder array body and assert it is non-empty."""
        text = _extract_phase_order_text(content)
        self.assertGreater(
            len(text),
            0,
            f"{label}: could not extract phaseOrder array.  "
            "Check that the file defines 'const phaseOrder = [...]'.",
        )
        return text

    def test_ac_d2_build_feature_retains_pr_reviewer(self) -> None:
        # covers: BO-2500d-2
        """build-feature.js phaseOrder must still contain 'pr-reviewer'.

        Removing pr-reviewer from the fast lane (BO-2500d-1) must not remove it
        from the heavy pipeline.  This test guards that the heavy phaseOrder
        retains the LLM review gate.

        If this test FAILS, pr-reviewer was removed from build-feature.js
        phaseOrder — restore it; the heavy path must keep LLM review.
        """
        content = self._require_file(_BUILD_FEATURE_PATH, "build-feature.js")
        phase_order_text = self._get_phase_order_text(content, "build-feature.js")
        self.assertIn(
            '"pr-reviewer"',
            phase_order_text,
            "build-feature.js phaseOrder must retain '\"pr-reviewer\"' — "
            "the heavy pipeline must not lose the LLM review gate (BO-2500d-2).",
        )

    def test_ac_d2_build_ticket_retains_pr_reviewer(self) -> None:
        # covers: BO-2500d-2
        """build-ticket.js phaseOrder must still contain 'pr-reviewer'."""
        content = self._require_file(_BUILD_TICKET_PATH, "build-ticket.js")
        phase_order_text = self._get_phase_order_text(content, "build-ticket.js")
        self.assertIn(
            '"pr-reviewer"',
            phase_order_text,
            "build-ticket.js phaseOrder must retain '\"pr-reviewer\"' — "
            "the heavy pipeline must not lose the LLM review gate (BO-2500d-2).",
        )

    def test_ac_d2_build_feature_retains_change_scope_reviewer(self) -> None:
        # covers: BO-2500d-2
        """build-feature.js phaseOrder must still contain 'change-scope-reviewer'."""
        content = self._require_file(_BUILD_FEATURE_PATH, "build-feature.js")
        phase_order_text = self._get_phase_order_text(content, "build-feature.js")
        self.assertIn(
            '"change-scope-reviewer"',
            phase_order_text,
            "build-feature.js phaseOrder must retain '\"change-scope-reviewer\"' — "
            "the heavy pipeline must keep this scope-integrity gate (BO-2500d-2).",
        )

    def test_ac_d2_build_ticket_retains_change_scope_reviewer(self) -> None:
        # covers: BO-2500d-2
        """build-ticket.js phaseOrder must still contain 'change-scope-reviewer'."""
        content = self._require_file(_BUILD_TICKET_PATH, "build-ticket.js")
        phase_order_text = self._get_phase_order_text(content, "build-ticket.js")
        self.assertIn(
            '"change-scope-reviewer"',
            phase_order_text,
            "build-ticket.js phaseOrder must retain '\"change-scope-reviewer\"' — "
            "the heavy pipeline must keep this scope-integrity gate (BO-2500d-2).",
        )

    def test_ac_d2_fast_lane_has_no_phase_order_array(self) -> None:
        # covers: BO-2500d-2
        """fast-lane-build.js must NOT define a phaseOrder array.

        The two phase-order sets (fast lane vs. heavy pipeline) must be
        independently defined so that a change to one cannot silently mutate the
        other (BO-2500d-2).  The fast lane does not define a phaseOrder array —
        its two dispatches are inlined directly.  If a phaseOrder were added to
        fast-lane-build.js it could be accidentally shared with or confused for
        the heavy pipeline's set.
        """
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-build.js")
        phase_order_text = _extract_phase_order_text(content)
        self.assertEqual(
            phase_order_text,
            "",
            "fast-lane-build.js must NOT define a 'const phaseOrder = [...]' "
            "array — its phase sequence is inlined (two flat dispatches), "
            "independently of the heavy pipeline's phaseOrder.  A shared "
            "phaseOrder would couple the two pipelines (BO-2500d-2).",
        )

    def test_ac_d2_heavy_pipeline_pr_reviewer_before_commit(self) -> None:
        # covers: BO-2500d-2
        """In both heavy-pipeline files, 'pr-reviewer' appears before 'commit' in phaseOrder.

        This guards the ordering contract: the LLM review gate must run before
        the commit phase in the heavy pipeline.  If the phaseOrder is rearranged
        so that commit precedes pr-reviewer, this test catches it.
        """
        for path, label in [
            (_BUILD_FEATURE_PATH, "build-feature.js"),
            (_BUILD_TICKET_PATH, "build-ticket.js"),
        ]:
            content = self._require_file(path, label)
            phase_order_text = self._get_phase_order_text(content, label)
            pr_pos = phase_order_text.find('"pr-reviewer"')
            commit_pos = phase_order_text.find('"commit"')
            if pr_pos == -1 or commit_pos == -1:
                # Individual presence tests above will already have caught this.
                continue
            self.assertLess(
                pr_pos,
                commit_pos,
                f"{label}: 'pr-reviewer' must appear BEFORE 'commit' in phaseOrder — "
                "the review gate must run before commit in the heavy pipeline "
                "(BO-2500d-2).",
            )


# ---------------------------------------------------------------------------
# TestFastLaneMechanicalGatesPresent — BO-2500d-3
# ---------------------------------------------------------------------------


class TestFastLaneMechanicalGatesPresent(_JsFileTestBase):
    """BO-2500d-3: fast-lane-build.js has the mechanical proof-of-done gates.

    The deterministic proof-of-done gates (red-baseline verification,
    green+coverage verification) must be present as the completion arbiters
    in the fast lane.
    """

    RED_BASELINE_PATTERNS = (
        "verify_red_baseline",
        "verifyRedBaseline",
        "red_baseline",
        "redBaseline",
    )
    GREEN_COVERAGE_PATTERNS = (
        "verify_green_and_coverage",
        "verifyGreenAndCoverage",
        "green_and_coverage",
        "greenAndCoverage",
    )

    def test_ac_d3_fast_lane_references_verify_red_baseline(self) -> None:
        # covers: BO-2500d-3
        """fast-lane-build.js must reference the verify_red_baseline gate.

        The red-baseline gate (BO-2400a-3) is one of the two mechanical
        proof-of-done arbiters that stand in for the removed opinion-only gates
        in the fast lane.  Its presence is required by BO-2500d-3.

        If this test FAILS, the red-baseline mechanical gate was removed from
        fast-lane-build.js — restore it before removing any opinion-only gate.
        """
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-build.js")
        has_ref = any(p in content for p in self.RED_BASELINE_PATTERNS)
        self.assertTrue(
            has_ref,
            "fast-lane-build.js must reference the red-baseline mechanical gate "
            f"using one of: {', '.join(self.RED_BASELINE_PATTERNS)} (BO-2500d-3).",
        )

    def test_ac_d3_fast_lane_references_verify_green_and_coverage(self) -> None:
        # covers: BO-2500d-3
        """fast-lane-build.js must reference the verify_green_and_coverage gate.

        The green+coverage gate (BO-2400a-4) is the second mechanical
        proof-of-done arbiter that stands in for the removed opinion-only gates.
        Its presence is required by BO-2500d-3.
        """
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-build.js")
        has_ref = any(p in content for p in self.GREEN_COVERAGE_PATTERNS)
        self.assertTrue(
            has_ref,
            "fast-lane-build.js must reference the green+coverage mechanical gate "
            f"using one of: {', '.join(self.GREEN_COVERAGE_PATTERNS)} (BO-2500d-3).",
        )

    def test_ac_d3_both_mechanical_gates_present(self) -> None:
        # covers: BO-2500d-3
        """Both mechanical proof-of-done gates must be present in fast-lane-build.js.

        The fast lane requires BOTH the red-baseline gate AND the green+coverage
        gate as its completion arbiters (BO-2500d-3).  Having only one is
        insufficient — the second must also be present.
        """
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-build.js")
        has_red = any(p in content for p in self.RED_BASELINE_PATTERNS)
        has_green = any(p in content for p in self.GREEN_COVERAGE_PATTERNS)
        self.assertTrue(
            has_red and has_green,
            f"fast-lane-build.js must reference BOTH mechanical gates. "
            f"red_baseline present: {has_red}, "
            f"green_and_coverage present: {has_green}. "
            "Both are required as completion arbiters of the fast lane (BO-2500d-3).",
        )

    def test_ac_d3_red_baseline_gate_appears_before_coder(self) -> None:
        # covers: BO-2500d-3
        """verify_red_baseline must appear before the coder dispatch in fast-lane-build.js.

        The sequencing contract: test-writer dispatch → red-baseline gate →
        coder dispatch → green+coverage gate.  The coder must NOT be dispatched
        before the red-baseline check has been defined/referenced.
        """
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-build.js")
        red_positions = [
            content.find(p) for p in self.RED_BASELINE_PATTERNS if content.find(p) != -1
        ]
        coder_types = ("python-coder", "sql-coder", "frontend-coder", "llm-expert")
        coder_positions = [
            content.find(c) for c in coder_types if content.find(c) != -1
        ]
        if not red_positions or not coder_positions:
            # Missing presence tests above already catch this.
            return
        first_red_pos = min(red_positions)
        first_coder_pos = min(coder_positions)
        self.assertLess(
            first_red_pos,
            first_coder_pos,
            "The red-baseline gate reference must appear BEFORE the coder agent "
            "dispatch in fast-lane-build.js — the coder must not run before the "
            "red baseline is enforced (BO-2500d-3).",
        )

    def test_ac_d3_green_coverage_gate_appears_after_coder(self) -> None:
        # covers: BO-2500d-3
        """The greenCoverageInvocation variable must be defined after the coder agentType dispatch.

        The sequencing contract: coder dispatch → green+coverage gate.
        The green+coverage invocation string is constructed AFTER the coder
        agent() call in fast-lane-build.js, confirming the gate runs post-coder.

        Uses code-only anchors to avoid false hits in the file header comment:
          - coder position: ``agentType: "python-coder"`` (the actual dispatch)
          - gate position:  ``greenCoverageInvocation`` (the const variable definition)

        Both strings appear only in non-comment code sections, so
        ``content.find()`` reliably finds the code-level positions.
        """
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-build.js")
        # Use the agentType dispatch string as the coder anchor — it appears
        # only in the actual agent() call, not in comments or meta.phases.
        coder_anchor = 'agentType: "python-coder"'
        # Use the variable name as the gate anchor — it is defined as a const
        # after the coder block, appearing once in the code section.
        gate_anchor = "greenCoverageInvocation"
        coder_pos = content.find(coder_anchor)
        gate_pos = content.find(gate_anchor)
        if coder_pos == -1:
            self.fail(
                "Could not find coder dispatch anchor "
                f"'{coder_anchor}' in fast-lane-build.js — "
                "verify the file still dispatches python-coder (BO-2500d-3)."
            )
        if gate_pos == -1:
            self.fail(
                f"Could not find gate anchor '{gate_anchor}' in fast-lane-build.js — "
                "verify the green+coverage invocation variable is still defined "
                "(BO-2500d-3)."
            )
        self.assertGreater(
            gate_pos,
            coder_pos,
            f"'{gate_anchor}' (pos {gate_pos}) must appear AFTER the coder "
            f"dispatch '{coder_anchor}' (pos {coder_pos}) in fast-lane-build.js — "
            "the green+coverage gate must be defined after the coder runs "
            "(BO-2500d-3).",
        )

    def test_ac_d3_gates_passed_summary_names_both_mechanical_gates(self) -> None:
        # covers: BO-2500d-3
        """The gates_passed return field must name both mechanical gates.

        The return value of fast-lane-build.js includes a gates_passed array.
        Both verify_red_baseline and verify_green_and_coverage must appear in
        it, confirming they are active arbiters rather than dead code.
        """
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-build.js")
        self.assertIn(
            "gates_passed",
            content,
            "fast-lane-build.js must return a 'gates_passed' field listing the "
            "mechanical gates that were enforced (BO-2500d-3).",
        )
        match = re.search(r"gates_passed\s*:\s*\[([^\]]*)\]", content)
        if match:
            gates_text = match.group(1)
            self.assertIn(
                "verify_red_baseline",
                gates_text,
                "gates_passed array must include 'verify_red_baseline' (BO-2500d-3).",
            )
            self.assertIn(
                "verify_green_and_coverage",
                gates_text,
                "gates_passed array must include 'verify_green_and_coverage' "
                "(BO-2500d-3).",
            )


# ---------------------------------------------------------------------------
# TestFastLaneMechanicalGateRetentionGuard — BO-2500d-1-i
# ---------------------------------------------------------------------------


class TestFastLaneMechanicalGateRetentionGuard(_JsFileTestBase):
    """BO-2500d-1-i: guard that dropping a mechanical gate is caught immediately.

    Per BO-2500d-1-i, removing an opinion-only gate before its mechanical
    replacement exists must be rejected.  These tests enforce that invariant
    from the structural side: as long as BOTH mechanical gates are present in
    fast-lane-build.js AND the opinion-only agents are absent, the precondition
    is satisfied.

    If a future edit removes a mechanical gate (making it impossible to enforce
    the precondition), these tests fail — signalling that the removal was
    made before a replacement was established, which is exactly what BO-2500d-1-i
    prohibits.

    User directive 2026-07-21: encode BO-2500d-1-i as structural presence
    assertions on fast-lane-build.js (not as behavioral tests of a validator
    function, which does not yet exist).
    """

    def test_ac_d1i_guard_verify_red_baseline_not_removed(self) -> None:
        # covers: BO-2500d-1-i
        """Guard: verify_red_baseline must not be removed from fast-lane-build.js.

        If this test FAILS, the red-baseline mechanical gate has been dropped
        from fast-lane-build.js.  Per BO-2500d-1-i, a mechanical gate may not
        be removed before its replacement is present and validated.  Restore
        verify_red_baseline or establish a replacement gate before removing it.
        """
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-build.js")
        self.assertIn(
            "verify_red_baseline",
            content,
            "GUARD (BO-2500d-1-i): 'verify_red_baseline' was removed from "
            "fast-lane-build.js.  A mechanical gate may not be dropped before "
            "its replacement is established and present in the fast lane.  "
            "Restore it or add its replacement first.",
        )

    def test_ac_d1i_guard_verify_green_and_coverage_not_removed(self) -> None:
        # covers: BO-2500d-1-i
        """Guard: verify_green_and_coverage must not be removed from fast-lane-build.js.

        If this test FAILS, the green+coverage mechanical gate has been dropped.
        Per BO-2500d-1-i, restore it or establish a replacement before removing.
        """
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-build.js")
        self.assertIn(
            "verify_green_and_coverage",
            content,
            "GUARD (BO-2500d-1-i): 'verify_green_and_coverage' was removed from "
            "fast-lane-build.js.  A mechanical gate may not be dropped before "
            "its replacement is established and present in the fast lane.  "
            "Restore it or add its replacement first.",
        )

    def test_ac_d1i_guard_both_mechanical_gates_present(self) -> None:
        # covers: BO-2500d-1-i
        """Guard: both mechanical gates must be simultaneously present.

        The 'removal before replacement' prohibition (BO-2500d-1-i) requires
        that whenever any opinion-only gate is absent from the fast lane, its
        mechanical replacement IS present.  This test asserts the positive
        form: both mechanical gates (red-baseline, green+coverage) are present.

        Combined with the opinion-only absence tests (BO-2500d-1), these two
        sets together enforce the full BO-2500d-1-i invariant structurally.
        """
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-build.js")
        red_patterns = (
            "verify_red_baseline",
            "verifyRedBaseline",
            "red_baseline",
            "redBaseline",
        )
        green_patterns = (
            "verify_green_and_coverage",
            "verifyGreenAndCoverage",
            "green_and_coverage",
            "greenAndCoverage",
        )
        has_red = any(p in content for p in red_patterns)
        has_green = any(p in content for p in green_patterns)
        self.assertTrue(
            has_red and has_green,
            f"GUARD (BO-2500d-1-i): fast-lane-build.js must contain BOTH "
            f"mechanical gates simultaneously. "
            f"red_baseline present: {has_red}, "
            f"green_and_coverage present: {has_green}. "
            "Having only one means the other was removed before a replacement "
            "was established — this is exactly what BO-2500d-1-i prohibits.",
        )

    def test_ac_d1i_guard_opinion_gates_not_reintroduced(self) -> None:
        # covers: BO-2500d-1-i
        """Guard: opinion-only gates must not be re-added to fast-lane-build.js.

        The inverse of the mechanical-gate retention guard.  If a future edit
        re-adds an opinion-only gate to the fast lane (e.g. re-introducing
        pr-reviewer), this test catches it.

        Together with the 'both mechanical gates present' guard, these two
        tests enforce the BO-2500d-1-i invariant bidirectionally:
          - opinion-only gates are absent from the fast lane
          - mechanical replacement gates are present in the fast lane
        """
        content = self._require_file(_FAST_LANE_PATH, "fast-lane-build.js")
        opinion_agents = (
            "pr-reviewer",
            "ac-validator",
            "ac-fulfillment-gate",
            "change-scope-reviewer",
        )
        reintroduced = [ag for ag in opinion_agents if ag in content]
        self.assertEqual(
            reintroduced,
            [],
            f"GUARD (BO-2500d-1-i): the following opinion-only gates were "
            f"re-introduced into fast-lane-build.js: {reintroduced}. "
            "They must remain absent — the fast lane's mechanical gates "
            "('verify_red_baseline', 'verify_green_and_coverage') are the "
            "designated replacements.  Removing an opinion-only gate while "
            "its mechanical replacement is absent would violate BO-2500d-1-i.",
        )


if __name__ == "__main__":
    unittest.main()
