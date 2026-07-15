"""
MODULE: test_bp_stragglers_backfill
GOAL: Green test coverage for BP-400c-1 (feedback-analysis deploy artifacts)
      and BP-900c-1-1 (broken-reference consolidation).
TICKET: 06_stragglers_test_coverage.md (EPIC-BuildPipelineTestBackfill)

Both ACs are CODE_NO_TEST straggler items.  The production code already exists;
these tests establish the missing coverage so each AC's ``work_status`` can
honestly be backed by verifiable test coverage.

BP-400c-1 — feedback-analysis deploy artifacts
  Assert that ``build_skills()``, ``build_agents()``, and ``build_workflows()``
  together produce all four feedback-analysis artifacts in a temp target dir:
    skills/feedback-analysis/SKILL.md
    skills/feedback-analysis/scripts/trend_report.py
    agents/feedback-analyst.md
    commands/feedback-report.md

BP-900c-1-1 — consolidated multi-template entry
  Assert that ``build_broken_ref_report()`` emits ONE ``BrokenRefEntry`` (not
  two) when a single missing script path is referenced by two different
  templates, and that the single entry names both templates.
"""

from __future__ import annotations

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — make scripts/ importable regardless of working directory.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


# ===========================================================================
# BP-400c-1 — feedback-analysis deploy artifacts
# ===========================================================================

class TestFeedbackAnalysisDeployArtifacts:
    """BP-400c-1: build deploy produces all four feedback-analysis artifacts.

    The four required artifacts after a build deploy:
      ``skills/feedback-analysis/SKILL.md``
      ``skills/feedback-analysis/scripts/trend_report.py``
      ``agents/feedback-analyst.md``
      ``commands/feedback-report.md``

    Each is produced by a distinct build phase:
      ``build_skills()``    → skills/feedback-analysis/…
      ``build_agents()``    → agents/feedback-analyst.md
      ``build_workflows()`` → commands/feedback-report.md
    """

    # Minimal platform config: only the claude platform is active.
    # This avoids spurious writes to gemini/, cursor/, copilot/, cline/ paths.
    _CLAUDE_ONLY_CONFIG: dict = {
        "platforms": {
            "claude": True,
            "antigravity": False,
            "cursor": False,
            "copilot": False,
            "cline": False,
        },
    }

    def test_ac1_build_skills_deploys_feedback_analysis_skill_md(self, tmp_path):
        # covers: BP-400c-1
        """build_skills() must deploy SKILL.md for the feedback-analysis skill.

        What must be true for this test to stay green:
          templates/skills/feedback-analysis/SKILL.md must exist and
          build_skills() must pick it up automatically via its rglob walk.
        """
        from build_phases import build_skills

        build_skills(tmp_path, self._CLAUDE_ONLY_CONFIG, dry_run=False, force=True)

        skill_md = tmp_path / "skills" / "feedback-analysis" / "SKILL.md"
        assert skill_md.is_file(), (
            f"{skill_md} was not deployed by build_skills(). "
            "Ensure templates/skills/feedback-analysis/SKILL.md exists and "
            "build_skills() picks up the feedback-analysis folder automatically."
        )

    def test_ac1_build_skills_deploys_trend_report_py(self, tmp_path):
        # covers: BP-400c-1
        """build_skills() must copy trend_report.py verbatim into the skill dir.

        Non-markdown files in skill subdirectories are copied verbatim (no
        template compilation).  The source must be:
          templates/skills/feedback-analysis/scripts/trend_report.py
        The target must be:
          {target}/skills/feedback-analysis/scripts/trend_report.py
        """
        from build_phases import build_skills

        build_skills(tmp_path, self._CLAUDE_ONLY_CONFIG, dry_run=False, force=True)

        trend_report = (
            tmp_path / "skills" / "feedback-analysis" / "scripts" / "trend_report.py"
        )
        assert trend_report.is_file(), (
            f"{trend_report} was not deployed by build_skills(). "
            "Ensure templates/skills/feedback-analysis/scripts/trend_report.py "
            "exists and that build_skills() rglob includes subdirectory files."
        )

    def test_ac1_build_agents_deploys_feedback_analyst_md(self, tmp_path):
        # covers: BP-400c-1
        """build_agents() must compile and deploy feedback-analyst.md.

        The template source is templates/agents/feedback-analyst.md.
        The deployed target for the claude platform is:
          {target}/agents/feedback-analyst.md
        """
        from build_phases import build_agents

        build_agents(tmp_path, self._CLAUDE_ONLY_CONFIG, dry_run=False, force=True)

        feedback_analyst = tmp_path / "agents" / "feedback-analyst.md"
        assert feedback_analyst.is_file(), (
            f"{feedback_analyst} was not deployed by build_agents(). "
            "Ensure templates/agents/feedback-analyst.md exists and "
            "build_agents() compiles and writes it for the claude platform."
        )

    def test_ac1_build_workflows_deploys_feedback_report_md(self, tmp_path):
        # covers: BP-400c-1
        """build_workflows() must deploy feedback-report.md to commands/.

        The template source is templates/workflows/feedback-report.md.
        The deployed target for the claude platform is:
          {target}/commands/feedback-report.md
        """
        from build_phases import build_workflows

        build_workflows(tmp_path, self._CLAUDE_ONLY_CONFIG, dry_run=False, force=True)

        feedback_report = tmp_path / "commands" / "feedback-report.md"
        assert feedback_report.is_file(), (
            f"{feedback_report} was not deployed by build_workflows(). "
            "Ensure templates/workflows/feedback-report.md exists and "
            "build_workflows() deploys it to commands/ for the claude platform."
        )

    def test_ac1_all_four_artifacts_present_after_combined_deploy(self, tmp_path):
        # covers: BP-400c-1
        """All four feedback-analysis artifacts must exist after a combined deploy.

        This is the primary integration assertion from the AC: calling all three
        relevant phase functions against the same target directory must produce
        all four required artifacts simultaneously.
        """
        from build_phases import build_skills, build_agents, build_workflows

        config = self._CLAUDE_ONLY_CONFIG
        build_skills(tmp_path, config, dry_run=False, force=True)
        build_agents(tmp_path, config, dry_run=False, force=True)
        build_workflows(tmp_path, config, dry_run=False, force=True)

        expected = [
            tmp_path / "skills" / "feedback-analysis" / "SKILL.md",
            tmp_path / "skills" / "feedback-analysis" / "scripts" / "trend_report.py",
            tmp_path / "agents" / "feedback-analyst.md",
            tmp_path / "commands" / "feedback-report.md",
        ]
        missing = [str(p) for p in expected if not p.is_file()]
        assert not missing, (
            f"Missing feedback-analysis artifacts after combined deploy: {missing}. "
            "All four paths must be produced by build_skills() + build_agents() "
            "+ build_workflows(): SKILL.md, trend_report.py, feedback-analyst.md, "
            "feedback-report.md."
        )


# ===========================================================================
# BP-900c-1-1 — consolidated multi-template entry
# ===========================================================================

class TestBrokenRefConsolidation:
    """BP-900c-1-1: broken-reference guard consolidates ONE entry for a missing
    script referenced by multiple templates.

    Scenario from the AC:
      scripts/ac_store/generate_ticket_from_ac.py is referenced by BOTH
      agents/build-ac.md AND skills/ac-scanner/SKILL.md, and the script is
      not in the deployable set.

    Expected: exactly one ``BrokenRefEntry``, not two — with both templates
    listed in its ``referencing_templates`` tuple and a single
    ``suggested_action``.
    """

    def test_ac2_one_entry_for_one_missing_path_two_templates(self):
        # covers: BP-900c-1-1
        """build_broken_ref_report emits ONE entry when one missing script is
        referenced by two different templates.

        AC BP-900c-1-1 requires consolidation by ``missing_path``: all
        referencing templates must be grouped into a single BrokenRefEntry's
        ``referencing_templates`` tuple rather than emitting one entry per
        (missing_path, template) pair.
        """
        from build_propagation_audit import build_broken_ref_report

        refs_to_sources: dict[str, set[str]] = {
            "scripts/ac_store/generate_ticket_from_ac.py": {
                "agents/build-ac.md",
                "skills/ac-scanner/SKILL.md",
            }
        }
        deployed_scripts: set[str] = set()

        entries = build_broken_ref_report(
            refs_to_sources=refs_to_sources,
            deployed_scripts=deployed_scripts,
            allowlist=frozenset(),
        )

        assert len(entries) == 1, (
            f"Expected 1 consolidated entry for the missing script, "
            f"got {len(entries)}. "
            "Two templates referencing the same missing script must produce "
            "a single BrokenRefEntry — not two separate entries "
            "(AC BP-900c-1-1)."
        )

    def test_ac2_consolidated_entry_names_both_referencing_templates(self):
        # covers: BP-900c-1-1
        """The single consolidated entry must list BOTH referencing templates.

        The ``referencing_templates`` tuple on the consolidated entry must
        contain both agents/build-ac.md and skills/ac-scanner/SKILL.md.
        """
        from build_propagation_audit import build_broken_ref_report

        refs_to_sources: dict[str, set[str]] = {
            "scripts/ac_store/generate_ticket_from_ac.py": {
                "agents/build-ac.md",
                "skills/ac-scanner/SKILL.md",
            }
        }
        entries = build_broken_ref_report(
            refs_to_sources=refs_to_sources,
            deployed_scripts=set(),
            allowlist=frozenset(),
        )

        entry = entries[0]
        assert entry.missing_path == "scripts/ac_store/generate_ticket_from_ac.py"
        templates = set(entry.referencing_templates)
        assert "agents/build-ac.md" in templates, (
            f"Expected 'agents/build-ac.md' in referencing_templates, "
            f"got {templates}"
        )
        assert "skills/ac-scanner/SKILL.md" in templates, (
            f"Expected 'skills/ac-scanner/SKILL.md' in referencing_templates, "
            f"got {templates}"
        )

    def test_ac2_suggested_action_present_on_consolidated_entry(self):
        # covers: BP-900c-1-1
        """The consolidated entry carries a non-empty suggested_action string.

        The suggested action appears exactly once (on the single consolidated
        entry) — not once per referencing template.  Verifying len(entries)==1
        and suggested_action is non-empty is sufficient: two un-consolidated
        entries would each carry their own action, making len(entries)==2.
        """
        from build_propagation_audit import build_broken_ref_report

        refs_to_sources: dict[str, set[str]] = {
            "scripts/ac_store/generate_ticket_from_ac.py": {
                "agents/build-ac.md",
                "skills/ac-scanner/SKILL.md",
            }
        }
        entries = build_broken_ref_report(
            refs_to_sources=refs_to_sources,
            deployed_scripts=set(),
            allowlist=frozenset(),
        )

        # One consolidated entry means suggested_action appears exactly once.
        assert len(entries) == 1, (
            f"Expected 1 entry, got {len(entries)}. "
            "Consolidation failure: two un-consolidated entries means "
            "suggested_action appears twice instead of once."
        )
        assert entries[0].suggested_action, (
            "suggested_action on the consolidated entry must be non-empty."
        )
