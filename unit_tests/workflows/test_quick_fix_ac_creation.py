"""
MODULE: test_quick_fix_ac_creation
GOAL: /quick-fix (BP-600 ACs) source-contract coverage for the AC Creation
      phase: required YAML fields (BP-600b-1), component prefix + sequential
      ID derivation from index.yaml (BP-600b-2), component inference from
      the target file path with a hard stop-and-ask when nothing matches
      (BP-600b-2-i), and the AC file's permanence after the ticket lifecycle
      closes (BP-600b-3).

Split out of the former monolithic test_quick_fix_workflow.py (1731 content
lines) — see _quick_fix_harness.py's module docstring for the shared-fixture
rationale and the sibling files covering the rest of the BP-600 AC set.

TICKET: EPIC-BuildPipelineTestBackfill/02_bp600_quick_fix_test_coverage.md
ACs: BP-600b-1, BP-600b-2, BP-600b-2-i, BP-600b-3
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
# BP-600b-1 — creates AC YAML with required fields
# ===========================================================================

class TestBP600b1ACCreation:
    """BP-600b-1: Creates an AC YAML file in the AC store with required fields."""

    def test_ac_bp600b1_ac_creation_phase_exists(self):
        # covers: BP-600b-1
        """quick-fix.js must contain an AC Creation phase."""
        js = _js()
        assert "phase('AC Creation')" in js, (
            "quick-fix.js must have an AC Creation phase (BP-600b-1)."
        )

    def test_ac_bp600b1_ac_has_given_when_then(self):
        # covers: BP-600b-1
        """The AC creation prompt must request Given/When/Then criteria."""
        js = _js()
        ac_block = _phase_block(js, "AC Creation", "Red Phase")
        assert "Given" in ac_block and "When" in ac_block and "Then" in ac_block, (
            "AC creation phase must request Given/When/Then criteria structure (BP-600b-1)."
        )

    def test_ac_bp600b1_skill_ac_yaml_required_fields(self):
        # covers: BP-600b-1
        """SKILL.md must document the required AC YAML fields."""
        skill = _skill()
        for field in ("id:", "status: active", "component:", "title:", "criteria:"):
            assert field in skill, (
                f"SKILL.md must document required AC YAML field '{field}' (BP-600b-1)."
            )

    def test_ac_bp600b1_ac_reads_docs_acceptance_criteria(self):
        # covers: BP-600b-1
        """AC creation must write to the docs/acceptance-criteria/ directory."""
        js = _js()
        ac_block = _phase_block(js, "AC Creation", "Red Phase")
        assert "docs/acceptance-criteria" in ac_block, (
            "AC creation phase must write the AC YAML under docs/acceptance-criteria/ "
            "(BP-600b-1)."
        )


# ===========================================================================
# BP-600b-2 — uses component prefix from index.yaml + sequential ID
# ===========================================================================

class TestBP600b2ComponentPrefixAndSequentialId:
    """BP-600b-2: Uses component prefix from index.yaml + next sequential ID."""

    def test_ac_bp600b2_reads_index_yaml(self):
        # covers: BP-600b-2
        """AC creation must read docs/acceptance-criteria/index.yaml."""
        js = _js()
        ac_block = _phase_block(js, "AC Creation", "Red Phase")
        assert "index.yaml" in ac_block, (
            "AC creation phase must read docs/acceptance-criteria/index.yaml to obtain "
            "the component prefix (BP-600b-2)."
        )

    def test_ac_bp600b2_skill_reads_index_yaml(self):
        # covers: BP-600b-2
        """SKILL.md Step 1.1 must read index.yaml for component prefix."""
        skill = _skill()
        assert "index.yaml" in skill, (
            "SKILL.md must document reading index.yaml to determine component prefix "
            "(BP-600b-2)."
        )


# ===========================================================================
# BP-600b-2-i — infers component from file path; asks when no mapping
# ===========================================================================

class TestBP600b2iInferComponent:
    """BP-600b-2-i: Infers component from file path via index.yaml; asks when no match."""

    def test_ac_bp600b2i_infers_from_file_path(self):
        # covers: BP-600b-2-i
        """AC creation must infer component from target_file path."""
        js = _js()
        ac_block = _phase_block(js, "AC Creation", "Red Phase")
        # The prompt references target_file and uses it to match a component
        assert "target_file" in ac_block, (
            "AC creation phase must reference target_file when inferring the component "
            "from the file path via index.yaml (BP-600b-2-i)."
        )

    def test_ac_bp600b2i_skill_infers_component_from_path(self):
        # covers: BP-600b-2-i
        """SKILL.md must describe component inference from file path."""
        skill = _skill()
        assert "directory_patterns" in skill or "file path" in skill, (
            "SKILL.md must describe inferring component from the target file path "
            "using index.yaml directory_patterns (BP-600b-2-i)."
        )

    def test_ac_bp600b2i_asks_user_when_no_mapping(self):
        # covers: BP-600b-2-i
        """Neither surface may silently default the component when no pattern
        matches — BP-600b-2-i requires asking.

        This assertion previously read
        `"no mapping" in skill or "ask" in skill or "fall back" in skill`.
        That third clause accepted the exact defaulting behaviour the AC
        forbids, so the test went green against code contradicting its own
        criterion — the test had been loosened to fit the implementation
        rather than the requirement. The real-world cost is on record:
        BP-600f.yaml was created misfiled by a live /quick-fix run and stayed
        wrong for six weeks.

        Both surfaces are checked, because a fix applied to only one of them
        leaves the other silently misfiling.
        """
        skill = _skill()
        js = _js()
        for name, source in (("SKILL.md", skill), ("quick-fix.js", js)):
            assert "Default to build-pipeline" not in source, (
                f"{name} still silently defaults the component to build-pipeline "
                "when no pattern matches. BP-600b-2-i requires asking the user "
                "instead — build-pipeline is a real component that would absorb "
                "the criterion, and the AC file it produces is permanent."
            )
        assert "do not default to a component" in js.lower(), (
            "quick-fix.js must instruct the AC-creation phase to block rather "
            "than default when no component matches (BP-600b-2-i)."
        )
        assert "stop and ask" in skill.lower(), (
            "SKILL.md must instruct the agent to stop and ask for the component "
            "when no pattern matches (BP-600b-2-i)."
        )


# ===========================================================================
# BP-600b-3 — AC file persists after ticket lifecycle closes
# ===========================================================================

class TestBP600b3ACPersists:
    """BP-600b-3: AC YAML file persists (status active) after lifecycle closes."""

    def test_ac_bp600b3_skill_declares_ac_permanent(self):
        # covers: BP-600b-3
        """SKILL.md must declare the AC YAML file as permanent — must not be deleted."""
        skill = _skill()
        assert (
            "permanent" in skill
            or "must NOT be deleted" in skill
            or "do not delete" in skill.lower()
        ), (
            "SKILL.md must state the AC YAML is permanent and must not be deleted "
            "after lifecycle closes (BP-600b-3)."
        )

    def test_ac_bp600b3_js_does_not_delete_ac(self):
        # covers: BP-600b-3
        """quick-fix.js must not contain any code that deletes or reverts the AC file."""
        js = _js()
        # Check that there's no file deletion logic for the ac_path
        assert "rm " + "ac_path" not in js and "delete ac_path" not in js.lower(), (
            "quick-fix.js must not delete or revert the AC file (BP-600b-3)."
        )

    def test_ac_bp600b3_escalation_preserves_ac(self):
        # covers: BP-600b-3
        """SKILL.md escalation path must preserve the AC file."""
        skill = _skill()
        # Escalation section should say to NOT delete the AC YAML
        escalation_start = skill.find("Escalation Path")
        if escalation_start == -1:
            escalation_start = skill.find("escalat")
        escalation_text = skill[escalation_start:escalation_start + 2000] if escalation_start >= 0 else skill
        assert (
            "not delete" in escalation_text.lower()
            or "do NOT delete" in escalation_text
            or "preserved" in escalation_text
        ), (
            "SKILL.md escalation path must preserve the AC YAML (not delete it) "
            "(BP-600b-3)."
        )
