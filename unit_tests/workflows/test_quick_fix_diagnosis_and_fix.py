"""
MODULE: test_quick_fix_diagnosis_and_fix
GOAL: /quick-fix (BP-600 ACs) source-contract coverage for how a diagnosis
      is consumed: parsing all four required fields — target_file,
      location_hint, symptom, root_cause — and threading them into later
      phases (BP-600d-1); rejecting a diagnosis missing the file path or
      root cause before AC creation even starts (BP-600d-1-i); and
      dispatching python-coder in the Fix phase under a single-file
      modification constraint, with the actually-modified files tracked for
      the later scope-expansion check (BP-600d-2).

Split out of the former monolithic test_quick_fix_workflow.py (1731 content
lines) — see _quick_fix_harness.py's module docstring for the shared-fixture
rationale.

TICKET: EPIC-BuildPipelineTestBackfill/02_bp600_quick_fix_test_coverage.md
ACs: BP-600d-1, BP-600d-1-i, BP-600d-2
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
# BP-600d-1 — parses structured diagnosis into file/location/symptom/root-cause
# ===========================================================================

class TestBP600d1DiagnosisParsing:
    """BP-600d-1: Parses structured diagnosis into required fields."""

    def test_ac_bp600d1_extracts_target_file(self):
        # covers: BP-600d-1
        """quick-fix.js must extract target_file from the diagnosis args."""
        js = _js()
        assert "target_file" in js, (
            "quick-fix.js must extract target_file from the diagnosis input (BP-600d-1)."
        )

    def test_ac_bp600d1_extracts_all_four_fields(self):
        # covers: BP-600d-1
        """quick-fix.js must destructure all four diagnosis fields."""
        js = _js()
        for field in ("target_file", "location_hint", "symptom", "root_cause"):
            assert field in js, (
                f"quick-fix.js must extract '{field}' from the diagnosis (BP-600d-1)."
            )

    def test_ac_bp600d1_uses_fields_in_subsequent_phases(self):
        # covers: BP-600d-1
        """Extracted diagnosis fields must be used in AC creation and fix phases."""
        js = _js()
        ac_block = _phase_block(js, "AC Creation", "Red Phase")
        fix_block = _phase_block(js, "Fix", "Green Phase")
        assert "root_cause" in ac_block, (
            "root_cause must be used in AC Creation phase (BP-600d-1)."
        )
        assert "target_file" in fix_block, (
            "target_file must be used in Fix phase (BP-600d-1)."
        )

    def test_ac_bp600d1_skill_documents_four_input_fields(self):
        # covers: BP-600d-1
        """SKILL.md must document the four required diagnosis fields."""
        skill = _skill()
        for field in ("target_file", "location_hint", "symptom", "root_cause"):
            assert field in skill, (
                f"SKILL.md must document required input field '{field}' (BP-600d-1)."
            )


# ===========================================================================
# BP-600d-1-i — rejects input lacking file path or root cause
# ===========================================================================

class TestBP600d1iInputValidation:
    """BP-600d-1-i: Rejects input missing file path or root cause."""

    def test_ac_bp600d1i_checks_for_missing_fields(self):
        # covers: BP-600d-1-i
        """quick-fix.js must check for missing target_file and root_cause."""
        js = _js()
        assert "!diagnosis.target_file" in js or "target_file" in js, (
            "quick-fix.js must validate that target_file is present (BP-600d-1-i)."
        )
        assert "!diagnosis.root_cause" in js or "root_cause" in js, (
            "quick-fix.js must validate that root_cause is present (BP-600d-1-i)."
        )

    def test_ac_bp600d1i_returns_blocked_on_missing_fields(self):
        # covers: BP-600d-1-i
        """quick-fix.js must return blocked status when required fields are missing."""
        js = _js()
        # The guard at the top checks for missing fields and returns blocked
        guards_text = js[:js.find("phase('AC Creation')")]
        assert "status: 'blocked'" in guards_text or "'blocked'" in guards_text, (
            "quick-fix.js must return status:'blocked' when diagnosis is missing "
            "required fields (BP-600d-1-i)."
        )

    def test_ac_bp600d1i_does_not_proceed_to_ac_creation(self):
        # covers: BP-600d-1-i
        """When fields are missing, quick-fix.js must return before AC creation."""
        js = _js()
        # The missing-fields check must appear before AC Creation phase
        missing_fields_check_idx = js.find("!diagnosis.target_file")
        if missing_fields_check_idx == -1:
            missing_fields_check_idx = js.find("Missing required diagnosis")
        ac_creation_idx = js.find("phase('AC Creation')")
        assert missing_fields_check_idx != -1, (
            "quick-fix.js must have a missing-fields check before AC creation (BP-600d-1-i)."
        )
        assert missing_fields_check_idx < ac_creation_idx, (
            "Missing-fields check must appear before AC Creation phase (BP-600d-1-i)."
        )

    def test_ac_bp600d1i_blocked_message_describes_requirements(self):
        # covers: BP-600d-1-i
        """The blocked message must describe what the diagnosis must include."""
        js = _js()
        # Find the guard message
        guards_text = js[:js.find("phase('AC Creation')")]
        assert (
            "target_file" in guards_text
            and "root_cause" in guards_text
        ), (
            "Blocked message must name required fields (target_file, root_cause) so "
            "the user knows what to provide (BP-600d-1-i)."
        )


# ===========================================================================
# BP-600d-2 — dispatches python-coder; coder modifies only target file
# ===========================================================================

class TestBP600d2PythonCoderDispatch:
    """BP-600d-2: Dispatches python-coder with diagnosis + test; modifies only target."""

    def test_ac_bp600d2_dispatches_python_coder(self):
        # covers: BP-600d-2
        """quick-fix.js must dispatch agentType: 'python-coder' in Fix phase."""
        js = _js()
        fix_block = _phase_block(js, "Fix", "Green Phase")
        assert "agentType: 'python-coder'" in fix_block or "'python-coder'" in fix_block, (
            "Fix phase must dispatch agentType: 'python-coder' (BP-600d-2)."
        )

    def test_ac_bp600d2_fix_prompt_includes_constraint(self):
        # covers: BP-600d-2
        """python-coder dispatch prompt must include single-file constraint."""
        js = _js()
        fix_block = _phase_block(js, "Fix", "Green Phase")
        assert (
            "MODIFY ONLY THE TARGET FILE" in fix_block
            or "Only modify" in fix_block
            or "only the target file" in fix_block.lower()
        ), (
            "python-coder dispatch prompt must include constraint to modify ONLY the "
            "target file (BP-600d-2)."
        )

    def test_ac_bp600d2_skill_python_coder_constraint(self):
        # covers: BP-600d-2
        """SKILL.md must document that python-coder may only modify the target file."""
        skill = _skill()
        assert "Modify ONLY the target file" in skill or \
               "ONLY the target file" in skill or \
               "Only modify" in skill, (
            "SKILL.md must document the single-file constraint for python-coder "
            "(BP-600d-2)."
        )

    def test_ac_bp600d2_fix_tracks_modified_files(self):
        # covers: BP-600d-2
        """Fix phase must capture the list of modified files for scope check."""
        js = _js()
        fix_block = _phase_block(js, "Fix", "Green Phase")
        assert "modified_files" in fix_block or "extra_files" in fix_block, (
            "Fix phase must track files modified by python-coder for scope expansion "
            "check (BP-600d-2)."
        )
