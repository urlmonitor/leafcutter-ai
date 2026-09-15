"""
MODULE: test_quick_fix_escalation_and_topology
GOAL: /quick-fix (BP-600 ACs) source-contract coverage for the three
      escalation warnings — scope expansion beyond the target file
      (BP-600e-1), root-cause divergence between the diagnosis and the
      observed red-phase failure (BP-600e-2), and preserving the AC + test
      artifacts (with an AC-ID-bearing summary) on any escalation
      (BP-600e-3) — plus the "commits nothing, reverts nothing" guarantee
      when escalation happens AFTER the fix has already landed
      (BP-600e-3-i). Closes with a single end-to-end backbone test that
      pins the exact phase dispatch order for an uninterrupted successful
      run — the reference topology every other behavioral test in this
      family deviates from one label at a time.

Split out of the former monolithic test_quick_fix_workflow.py (1731 content
lines) — see _quick_fix_harness.py's module docstring for the shared-fixture
rationale.

TICKET: EPIC-BuildPipelineTestBackfill/02_bp600_quick_fix_test_coverage.md
ACs: BP-600e-1, BP-600e-2, BP-600e-3, BP-600e-3-i
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

from _quick_fix_harness import (  # noqa: E402
    _JS_PATH,
    _full_success_responses,
    _js,
    _labels,
    _skill,
    run_workflow_under_e2,
)


# ===========================================================================
# BP-600e-1 — warns when fix modifies more than the target file
# ===========================================================================

class TestBP600e1ScopeExpansionWarning:
    """BP-600e-1: Warns when fix modifies >= 2 source files."""

    def test_ac_bp600e1_checks_scope_expanded(self):
        # covers: BP-600e-1
        """quick-fix.js must check fixResult.scope_expanded flag."""
        js = _js()
        assert "scope_expanded" in js, (
            "quick-fix.js must check fixResult.scope_expanded to detect scope "
            "expansion (BP-600e-1)."
        )

    def test_ac_bp600e1_returns_blocked_on_scope_expansion(self):
        # covers: BP-600e-1
        """quick-fix.js must return halt_reason:'scope_expansion' when fix scope expands."""
        js = _js()
        assert "scope_expansion" in js, (
            "quick-fix.js must return halt_reason:'scope_expansion' when extra files "
            "are modified (BP-600e-1)."
        )

    def test_ac_bp600e1_scope_check_before_green_phase(self):
        # covers: BP-600e-1
        """Scope expansion check must appear before Green Phase in control flow."""
        js = _js()
        scope_check_idx = js.find("scope_expansion")
        green_phase_idx = js.find("phase('Green Phase')")
        assert scope_check_idx != -1, "quick-fix.js must have scope_expansion check"
        assert green_phase_idx != -1, "quick-fix.js must have Green Phase"
        assert scope_check_idx < green_phase_idx, (
            "Scope expansion check must appear before Green Phase — the workflow must "
            "pause before the green test when scope expands (BP-600e-1)."
        )

    def test_ac_bp600e1_skill_mentions_modified_n_files_warning(self):
        # covers: BP-600e-1
        """SKILL.md must include the scope expansion warning text."""
        skill = _skill()
        assert (
            "modified" in skill
            and ("beyond" in skill or "additional" in skill or "extra" in skill)
        ), (
            "SKILL.md must document the scope expansion warning (BP-600e-1)."
        )


# ===========================================================================
# BP-600e-2 — warns when red-phase failure diverges from diagnosed root cause
# ===========================================================================

class TestBP600e2RootCauseDivergenceWarning:
    """BP-600e-2: Warns when red-phase failure indicates a different root cause."""

    def test_ac_bp600e2_has_divergence_check(self):
        # covers: BP-600e-2
        """quick-fix.js must check for divergence between failure message and root cause."""
        js = _js()
        assert "divergence" in js.lower() or "divergenceCheck" in js, (
            "quick-fix.js must check for root-cause divergence in the red phase "
            "(BP-600e-2)."
        )

    def test_ac_bp600e2_returns_blocked_with_divergence_halt_reason(self):
        # covers: BP-600e-2
        """quick-fix.js must return halt_reason:'divergence_warning' when divergence detected."""
        js = _js()
        assert "divergence_warning" in js, (
            "quick-fix.js must return halt_reason:'divergence_warning' when the red-phase "
            "failure diverges from the diagnosed root cause (BP-600e-2)."
        )

    def test_ac_bp600e2_divergence_message_includes_diagnosed_and_observed(self):
        # covers: BP-600e-2
        """Divergence warning message must include both diagnosed and observed root cause."""
        js = _js()
        assert "Diagnosed" in js and "Observed" in js, (
            "Divergence warning must include both 'Diagnosed' and 'Observed' root cause "
            "information in the message (BP-600e-2)."
        )

    def test_ac_bp600e2_skill_divergence_warning_described(self):
        # covers: BP-600e-2
        """SKILL.md must document the root-cause divergence warning."""
        skill = _skill()
        assert (
            "diverge" in skill.lower()
            or "root cause may differ" in skill.lower()
        ), (
            "SKILL.md must document the root-cause divergence warning in Phase 2.5 "
            "(BP-600e-2)."
        )


# ===========================================================================
# BP-600e-3 — escalation preserves AC + test; outputs summary with AC id
# ===========================================================================

class TestBP600e3EscalationPreservesArtifacts:
    """BP-600e-3: On escalation, preserves AC+test; outputs summary with AC id."""

    def test_ac_bp600e3_skill_escalation_preserves_artifacts(self):
        # covers: BP-600e-3
        """SKILL.md escalation path must explicitly preserve AC YAML and test file."""
        skill = _skill()
        escalation_idx = skill.find("Escalation Path")
        escalation_text = skill[escalation_idx:escalation_idx + 3000] if escalation_idx >= 0 else skill
        assert (
            "AC YAML" in escalation_text
            or "ac_path" in escalation_text
            or "AC file" in escalation_text
        ), (
            "SKILL.md escalation path must preserve the AC YAML file (BP-600e-3)."
        )
        assert (
            "test file" in escalation_text.lower()
            or "TEST_FILE" in escalation_text
            or "test_file" in escalation_text
        ), (
            "SKILL.md escalation path must preserve the test file (BP-600e-3)."
        )

    def test_ac_bp600e3_skill_escalation_summary_includes_ac_id(self):
        # covers: BP-600e-3
        """SKILL.md escalation summary must include the AC ID."""
        skill = _skill()
        escalation_idx = skill.find("Escalation Path")
        escalation_text = skill[escalation_idx:escalation_idx + 3000] if escalation_idx >= 0 else skill
        assert "AC-ID" in escalation_text or "ac_id" in escalation_text.lower() or \
               "<AC-ID>" in escalation_text, (
            "SKILL.md escalation summary must include the AC ID for user reference "
            "(BP-600e-3)."
        )

    def test_ac_bp600e3_skill_escalation_references_build_feature(self):
        # covers: BP-600e-3
        """SKILL.md escalation must recommend /build-feature or /create-ticket."""
        skill = _skill()
        escalation_idx = skill.find("Escalation Path")
        escalation_text = skill[escalation_idx:escalation_idx + 3000] if escalation_idx >= 0 else skill
        assert (
            "/build-feature" in escalation_text
            or "build-feature" in escalation_text
        ), (
            "SKILL.md escalation must provide the /build-feature reference for the "
            "user to escalate (BP-600e-3)."
        )

    def test_ac_bp600e3_js_escalation_preserves_ac_and_test(self):
        # covers: BP-600e-3
        """quick-fix.js escalation path must include ac_id and test_file in response."""
        js = _js()
        # Check that blocked returns from Fix phase include ac_id and test_file
        assert "test_file: testFile" in js or "test_file:" in js, (
            "quick-fix.js escalation response must include test_file for the user "
            "(BP-600e-3)."
        )
        assert "ac_id," in js or "ac_id:" in js, (
            "quick-fix.js escalation response must include ac_id for the user "
            "(BP-600e-3)."
        )


# ===========================================================================
# BP-600e-3-i — on escalation after fix: commits nothing; files preserved unstaged
# ===========================================================================

class TestBP600e3iEscalationAfterFixNoCommit:
    """BP-600e-3-i: On escalation after fix, commits nothing; files remain unstaged."""

    def test_ac_bp600e3i_skill_no_commit_on_escalation(self):
        # covers: BP-600e-3-i
        """SKILL.md escalation path must NOT invoke the commit agent or git commit."""
        skill = _skill()
        escalation_idx = skill.find("Escalation Path")
        escalation_text = skill[escalation_idx:escalation_idx + 3000] if escalation_idx >= 0 else skill
        assert (
            "Do not" in escalation_text
            or "do NOT" in escalation_text
            or "not commit" in escalation_text.lower()
            or "Halt" in escalation_text
        ), (
            "SKILL.md escalation path must explicitly not commit any code (BP-600e-3-i)."
        )

    def test_ac_bp600e3i_skill_no_git_restore_on_escalation(self):
        # covers: BP-600e-3-i
        """SKILL.md escalation must not run git restore, git checkout, or git clean."""
        skill = _skill()
        escalation_idx = skill.find("Escalation Path")
        escalation_text = skill[escalation_idx:escalation_idx + 3000] if escalation_idx >= 0 else skill
        # Escalation text should not instruct reverting files
        assert (
            "git restore" not in escalation_text
            and "git checkout" not in escalation_text
            and "git clean" not in escalation_text
        ), (
            "SKILL.md escalation path must not revert files — the fix, AC YAML, and "
            "test file must remain on disk as unstaged changes (BP-600e-3-i)."
        )

    def test_ac_bp600e3i_js_scope_expansion_returns_before_commit(self):
        # covers: BP-600e-3-i
        """quick-fix.js scope-expansion blocked return must appear before commit dispatch."""
        js = _js()
        scope_expansion_idx = js.find("scope_expansion")
        commit_dispatch_idx = js.find("agentType: 'commit'")
        assert scope_expansion_idx != -1, "scope_expansion check must exist"
        assert commit_dispatch_idx != -1, "commit agent dispatch must exist"
        assert scope_expansion_idx < commit_dispatch_idx, (
            "Scope expansion check (which returns blocked before commit) must appear "
            "before the commit dispatch — ensuring no commit happens on escalation "
            "(BP-600e-3-i)."
        )

    def test_ac_bp600e3i_skill_informs_user_of_preserved_files(self):
        # covers: BP-600e-3-i
        """SKILL.md escalation summary must inform user which files are preserved."""
        skill = _skill()
        escalation_idx = skill.find("Escalation Path")
        escalation_text = skill[escalation_idx:escalation_idx + 3000] if escalation_idx >= 0 else skill
        assert (
            "preserved" in escalation_text.lower()
            or "Preserved" in escalation_text
        ), (
            "SKILL.md escalation must inform the user which files are preserved "
            "(BP-600e-3-i)."
        )


# ===========================================================================
# Full-run backbone (harness-driven)
#
# A single end-to-end topology test: every phase, in the exact order
# quick-fix.js's module docstring declares, given an uninterrupted
# all-'ok' run. This is the reference topology the more targeted behavioral
# tests in the sibling files deviate from one label at a time.
# ===========================================================================

class TestBP600WorkflowFullRunTopology:
    """The reference successful-run dispatch order and terminal status."""

    def test_ac_bp600_full_run_dispatches_every_phase_in_order(self):
        # covers: BP-600a-1
        # covers: BP-600b-1
        # covers: BP-600c-1
        # covers: BP-600d-2
        # covers: BP-600d-3
        # covers: BP-600d-4
        """An uninterrupted successful run dispatches exactly these labels,
        in this order, and returns status: ok."""
        result = run_workflow_under_e2(_JS_PATH, label_responses=_full_success_responses())
        assert _labels(result) == [
            "isolation-check",
            "guard-checks",
            "ac-creation",
            "test-writer",
            "red-verify/strict",
            "python-coder/fix",
            "green-verify/strict",
            "related-tests/strict",
            "mutation-proof",
            # INF-700a-1: the knowledge-routing step is dispatched immediately
            # before this path's FIRST (fix) commit, so any learning it routes
            # is carried by a commit the path already makes -- ADR-040. It is
            # deliberately NOT anchored to the later "commit/changelog" call;
            # INF-700a-5's it_requirements name the fix commit specifically,
            # and attaching it to the changelog commit was called out there as
            # the wrong anchor.
            "knowledge-routing-step",
            "commit",
            "changelog-author",
            "commit/changelog",
            "push-and-pr",
        ]
        assert result.result is not None
        assert result.result.get("status") == "ok"
