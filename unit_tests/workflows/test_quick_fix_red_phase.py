"""
MODULE: test_quick_fix_red_phase
GOAL: /quick-fix (BP-600 ACs) source-contract coverage for the Red Phase:
      test-writer dispatch with a mandatory '# covers: <AC-ID>' tag, written
      before the fix (BP-600c-1), and running the test to confirm it is
      actually RED with a halt if it unexpectedly passes (BP-600c-2).

Split out of the former monolithic test_quick_fix_workflow.py (1731 content
lines) — see _quick_fix_harness.py's module docstring for the shared-fixture
rationale. The behavioral proof that these halts are actually wired into
control flow (not just mentioned in a prompt) lives in the sibling file
test_quick_fix_verification_trust_boundary.py.

TICKET: EPIC-BuildPipelineTestBackfill/02_bp600_quick_fix_test_coverage.md
ACs: BP-600c-1, BP-600c-2
"""

from __future__ import annotations

import sys
from pathlib import Path

# unit_tests/workflows/ must be on sys.path so the flat sibling import below
# resolves — this package has __init__.py, so pytest's rootdir insertion
# does not add it automatically (mirrors the unit_tests/ insertion pattern
# _quick_fix_harness.py itself uses for _workflow_engine_harness).
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from _quick_fix_harness import _js, _phase_block, _skill  # noqa: E402


# ===========================================================================
# BP-600c-1 — dispatches test-writer; test has # covers: tag; written before fix
# ===========================================================================

class TestBP600c1TestWriterDispatch:
    """BP-600c-1: Dispatches test-writer; test has # covers: tag; before fix."""

    def test_ac_bp600c1_dispatches_test_writer_agent(self):
        # covers: BP-600c-1
        """quick-fix.js must dispatch agentType: 'test-writer' in the Red Phase."""
        js = _js()
        red_block = _phase_block(js, "Red Phase", "Fix")
        assert "agentType: 'test-writer'" in red_block or '"test-writer"' in red_block, (
            "Red Phase must dispatch agentType: 'test-writer' (BP-600c-1)."
        )

    def test_ac_bp600c1_test_writer_prompt_includes_covers_tag(self):
        # covers: BP-600c-1
        """The test-writer prompt must instruct the agent to include '# covers: <AC-ID>'."""
        js = _js()
        red_block = _phase_block(js, "Red Phase", "Fix")
        assert "# covers:" in red_block, (
            "test-writer dispatch prompt must instruct the agent to include "
            "'# covers: <AC-ID>' in the test (BP-600c-1)."
        )

    def test_ac_bp600c1_test_writer_before_fix_phase(self):
        # covers: BP-600c-1
        """test-writer dispatch must appear before the Fix phase in quick-fix.js."""
        js = _js()
        red_phase_idx = js.find("phase('Red Phase')")
        fix_phase_idx = js.find("phase('Fix')")
        assert red_phase_idx != -1, "quick-fix.js must contain 'phase(Red Phase)'"
        assert fix_phase_idx != -1, "quick-fix.js must contain 'phase(Fix)'"
        assert red_phase_idx < fix_phase_idx, (
            "Red Phase (test-writer) must appear before Fix phase in the control "
            "flow, ensuring the test is written before the fix (BP-600c-1)."
        )

    def test_ac_bp600c1_test_writer_schema_requires_test_file(self):
        # covers: BP-600c-1
        """TEST_WRITER_SCHEMA must require the test_file field in the result."""
        js = _js()
        # Check schema has test_file as required
        assert "test_file" in js, (
            "TEST_WRITER_SCHEMA must include test_file as a required field to record "
            "the path of the written test (BP-600c-1)."
        )


# ===========================================================================
# BP-600c-2 — runs test and confirms RED; halts if unexpectedly passes
# ===========================================================================

class TestBP600c2RedPhaseVerification:
    """BP-600c-2: Runs test and confirms RED; halts if test unexpectedly passes."""

    def test_ac_bp600c2_dispatches_test_runner_for_red(self):
        # covers: BP-600c-2
        """quick-fix.js must dispatch agentType: 'test-runner' for red-phase verification."""
        js = _js()
        red_block = _phase_block(js, "Red Phase", "Fix")
        assert "agentType: 'test-runner'" in red_block or \
               "label: 'test-runner/red'" in red_block, (
            "Red Phase must dispatch a test-runner for red-phase verification (BP-600c-2)."
        )

    def test_ac_bp600c2_halts_when_test_passes_unexpectedly(self):
        # covers: BP-600c-2
        """quick-fix.js must return blocked with halt_reason:'red_phase_pass' if test passes."""
        js = _js()
        assert "red_phase_pass" in js, (
            "quick-fix.js must return halt_reason:'red_phase_pass' when the test "
            "passes before the fix is applied (BP-600c-2)."
        )

    def test_ac_bp600c2_red_phase_checks_passed_equals_true(self):
        # covers: BP-600c-2
        """quick-fix.js must check redResult.passed === true to detect unexpected pass."""
        js = _js()
        assert "redResult.passed === true" in js or "redResult.passed" in js, (
            "quick-fix.js must check redResult.passed to detect unexpected test pass "
            "in red phase (BP-600c-2)."
        )

    def test_ac_bp600c2_skill_halt_text_matches_spec(self):
        # covers: BP-600c-2
        """SKILL.md halt message must match the specified warning text."""
        skill = _skill()
        assert (
            "already been fixed" in skill
            or "already fixed" in skill
            or "passes before the fix" in skill
        ), (
            "SKILL.md halt message for unexpected red-phase pass must match the "
            "AC-specified warning text (BP-600c-2)."
        )
