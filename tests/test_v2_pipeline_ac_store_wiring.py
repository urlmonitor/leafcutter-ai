"""
MODULE: tests/test_v2_pipeline_ac_store_wiring.py
GOAL: Verify that business-analyst-v2.md contains the required AC-store wiring strings.
BUSINESS CONTEXT: AC-7 requires a static test confirming the four AC-store strings
    are present in business-analyst-v2.md before a live agent run is needed.
    This guards against regressions where the template loses its AC store query section.
ARCHITECTURE: Template-level static test. Reads the markdown template file directly
    and asserts string presence. No agent invocation, no file system side effects.
"""
from __future__ import annotations

import pytest
from pathlib import Path


WORKTREE_ROOT = Path(__file__).resolve().parent.parent
BA_V2_TEMPLATE = WORKTREE_ROOT / "templates" / "agents" / "business-analyst-v2.md"

REQUIRED_STRINGS = [
    "ac_creations",
    "ac_amendments",
    "origin_agent",
    "docs/acceptance-criteria",
]


class TestV2PipelineACStoreWiring:
    """AC-7: Verify business-analyst-v2.md contains all required AC store wiring strings."""

    def _get_template_content(self) -> str:
        """Read the business-analyst-v2.md template content."""
        if not BA_V2_TEMPLATE.exists():
            pytest.fail(
                f"Template file not found: {BA_V2_TEMPLATE}. "
                "The business-analyst-v2.md template must exist for AC store wiring."
            )
        return BA_V2_TEMPLATE.read_text(encoding="utf-8")

    def test_ac_creations_present(self) -> None:
        # covers: UNKNOWN
        """AC-7 (partial): business-analyst-v2.md must contain 'ac_creations'."""
        content = self._get_template_content()
        assert "ac_creations" in content, (
            "business-analyst-v2.md is missing 'ac_creations'. "
            "The v2 BA must include this field in its output contract (AC-2) "
            "and in its AC store query step (AC-1)."
        )

    def test_ac_amendments_present(self) -> None:
        # covers: UNKNOWN
        """AC-7 (partial): business-analyst-v2.md must contain 'ac_amendments'."""
        content = self._get_template_content()
        assert "ac_amendments" in content, (
            "business-analyst-v2.md is missing 'ac_amendments'. "
            "The v2 BA must include this field in its output contract (AC-2) "
            "and in its AC store query step (AC-1)."
        )

    def test_origin_agent_present(self) -> None:
        # covers: UNKNOWN
        """AC-7 (partial): business-analyst-v2.md must contain 'origin_agent'."""
        content = self._get_template_content()
        assert "origin_agent" in content, (
            "business-analyst-v2.md is missing 'origin_agent'. "
            "The v2 BA must set origin_agent: 'business-analyst-v2' in ac_creations "
            "entries (AC-3) so compliance auditing can distinguish v1 vs v2 ACs."
        )

    def test_docs_acceptance_criteria_present(self) -> None:
        # covers: UNKNOWN
        """AC-7 (partial): business-analyst-v2.md must contain 'docs/acceptance-criteria'."""
        content = self._get_template_content()
        assert "docs/acceptance-criteria" in content, (
            "business-analyst-v2.md is missing 'docs/acceptance-criteria'. "
            "The v2 BA must reference this path in its AC store query step (AC-1) "
            "to read the AC store index."
        )

    def test_all_required_strings_present(self) -> None:
        # covers: UNKNOWN
        """AC-7 (full): business-analyst-v2.md contains all four required AC store strings.

        This is the canonical single-assertion test for AC-7. It fails if any of the
        four strings is absent, and the error message lists exactly which strings are
        missing so the implementer knows what to add.
        """
        content = self._get_template_content()
        missing = [s for s in REQUIRED_STRINGS if s not in content]
        assert not missing, (
            f"business-analyst-v2.md is missing the following required AC store "
            f"wiring strings: {missing}. "
            f"Add these strings as part of the AC store query step (AC-1/AC-2/AC-3) "
            f"and the output contract."
        )
