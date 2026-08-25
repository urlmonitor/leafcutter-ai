"""
MODULE: test_check_skill_refs
GOAL: Unit tests for scripts/check_skill_refs.py, the build guard that fails when a
      template tells an agent to load a skill that does not exist in templates/skills/.
BUSINESS CONTEXT: Six dangling skill references accumulated across at least three epics
      (KI-BP-007) because the build's only skill-reference check reads the
      `skills_invoked` registry field, never the hand-typed path in a Markdown body.
      Every call site treats "skill not found" as a pass, so all six were silent no-ops.
ARCHITECTURE: Each test builds a synthetic templates/ tree in a sandbox and asserts on
      the exit code and the classified findings. The two discriminators that keep the
      guard from failing on accurate history — DECISION HISTORY comment stripping and
      the imperative/descriptive split — get a test each, since a guard that over-fires
      on a correctly-retired skill would be turned off rather than fixed.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import check_skill_refs as csr  # noqa: E402


def _make_templates(tmp: Path, skills: list[str]) -> Path:
    """Create a templates/ tree containing the named (real) skill directories."""
    templates = tmp / "templates"
    (templates / "skills").mkdir(parents=True)
    (templates / "agents").mkdir(parents=True)
    for name in skills:
        (templates / "skills" / name).mkdir()
        (templates / "skills" / name / "SKILL.md").write_text(
            f"---\nname: {name}\n---\n", encoding="utf-8")
    return templates


class TestCheckSkillRefs(unittest.TestCase):
    def test_resolvable_reference_passes(self):
        """A Load instruction naming a skill that exists is clean."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            templates = _make_templates(root, ["signoff"])
            (templates / "agents" / "a.md").write_text(
                "1. Load `.claude/skills/signoff/SKILL.md` and follow it.\n", encoding="utf-8")
            self.assertEqual(csr.main(["--repo-root", str(root)]), 0)

    def test_dangling_imperative_reference_fails(self):
        """A Load instruction naming a skill that does not exist is a failure."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            templates = _make_templates(root, ["signoff"])
            (templates / "agents" / "a.md").write_text(
                "1. Load `.claude/skills/route-learning/SKILL.md` and apply it.\n",
                encoding="utf-8")
            self.assertEqual(csr.main(["--repo-root", str(root)]), 1)

    def test_dangling_exec_reference_fails(self):
        """A `python .../script.py` invocation of a missing skill is a failure.

        This is the agent-telemetry shape: eight emit_event.py calls in the
        building-epics runbook, none of which could ever have run.
        """
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            templates = _make_templates(root, ["signoff"])
            (templates / "skills" / "signoff" / "SKILL.md").write_text(
                "python .claude/skills/agent-telemetry/scripts/emit_event.py --event x\n",
                encoding="utf-8")
            self.assertEqual(csr.main(["--repo-root", str(root)]), 1)

    def test_decision_history_mention_does_not_fail(self):
        """A deleted skill named inside a DECISION HISTORY comment is accurate history.

        The create-ac control case: retired into plan-feature (#184) and still named
        in the comment block that records the migration. Failing here would make the
        guard punish a correct record.
        """
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            templates = _make_templates(root, ["plan-feature"])
            (templates / "skills" / "plan-feature" / "SKILL.md").write_text(
                "# plan-feature\n\n"
                "<!--\n"
                "DECISION HISTORY\n"
                "- 2026-06-29: Migrated §1-§3 from\n"
                "  templates/skills/create-ac/SKILL.md into this canonical surface.\n"
                "  Load `.claude/skills/create-ac/SKILL.md` was the old instruction.\n"
                "-->\n",
                encoding="utf-8")
            self.assertEqual(csr.main(["--repo-root", str(root)]), 0)

    def test_descriptive_mention_does_not_fail(self):
        """A path named in prose, with no instruction to act on it, is not a failure."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            templates = _make_templates(root, ["signoff"])
            (templates / "agents" / "a.md").write_text(
                "The old templates/skills/legacy-thing/SKILL.md was removed last year.\n",
                encoding="utf-8")
            self.assertEqual(csr.main(["--repo-root", str(root)]), 0)

    def test_both_path_forms_on_one_line_count_once(self):
        """`.claude/skills/x` and `templates/skills/x` on one line is ONE reference.

        Agent templates routinely write both forms as a fallback pair; counting them
        twice inflates every report from PO/BA/IT-PO v3.
        """
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            templates = _make_templates(root, ["signoff"])
            (templates / "agents" / "a.md").write_text(
                "1. Load `.claude/skills/route-learning/SKILL.md` "
                "(or `templates/skills/route-learning/SKILL.md`).\n",
                encoding="utf-8")
            bad, _ = csr.scan(templates, {"signoff"})
            self.assertEqual(len(bad), 1, f"expected 1 reference, got {bad}")

    def test_reports_every_distinct_missing_skill(self):
        """All dangling skills are reported, not just the first one found."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            templates = _make_templates(root, ["signoff"])
            (templates / "agents" / "research-agent.md").write_text(
                "| x | `.claude/skills/import-scanner/SKILL.md` — invoke via `Bash` |\n"
                "| y | `.claude/skills/trade-analysis/SKILL.md` — invoke via `Bash` |\n",
                encoding="utf-8")
            bad, _ = csr.scan(templates, {"signoff"})
            self.assertEqual(
                {rec["skill"] for rec in bad}, {"import-scanner", "trade-analysis"})

    def test_unreadable_skills_dir_is_hard_error(self):
        """A missing templates/skills/ returns 2, never a misleading 0."""
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(csr.main(["--repo-root", str(Path(d))]), 2)


class TestBundledFileReferences(unittest.TestCase):
    """A reference into a skill bundle must resolve to the FILE, not just the directory.

    Skill bundles ship executables. `python .claude/skills/agent-telemetry/scripts/
    emit_event.py` names a real skill and a script that may or may not be there — a
    directory-only check passes the bundle whose script was never written, which is
    the same defect one level in.
    """

    def test_missing_bundled_script_fails(self):
        """Skill directory present, referenced script absent → failure."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            templates = _make_templates(root, ["agent-telemetry"])
            (templates / "skills" / "agent-telemetry" / "SKILL.md").write_text(
                "python .claude/skills/agent-telemetry/scripts/emit_event.py --event x\n",
                encoding="utf-8")
            self.assertEqual(csr.main(["--repo-root", str(root)]), 1)

    def test_present_bundled_script_passes(self):
        """The same reference is clean once the script exists."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            templates = _make_templates(root, ["agent-telemetry"])
            scripts = templates / "skills" / "agent-telemetry" / "scripts"
            scripts.mkdir()
            (scripts / "emit_event.py").write_text("# real\n", encoding="utf-8")
            (templates / "skills" / "agent-telemetry" / "SKILL.md").write_text(
                "python .claude/skills/agent-telemetry/scripts/emit_event.py --event x\n",
                encoding="utf-8")
            self.assertEqual(csr.main(["--repo-root", str(root)]), 0)

    def test_missing_skill_md_fails(self):
        """A bare skill directory with no SKILL.md does not satisfy a Load instruction."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            templates = _make_templates(root, ["signoff"])
            (templates / "skills" / "signoff" / "SKILL.md").unlink()
            (templates / "agents" / "a.md").write_text(
                "1. Load `.claude/skills/signoff/SKILL.md` and follow it.\n",
                encoding="utf-8")
            self.assertEqual(csr.main(["--repo-root", str(root)]), 1)

    def test_reason_distinguishes_missing_dir_from_missing_file(self):
        """The report says which of the two failed — they need different fixes."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            templates = _make_templates(root, ["agent-telemetry"])
            (templates / "agents" / "a.md").write_text(
                "python .claude/skills/agent-telemetry/scripts/emit_event.py\n"
                "1. Load `.claude/skills/nope/SKILL.md` now.\n",
                encoding="utf-8")
            bad, _ = csr.scan(templates, {"agent-telemetry"})
            reasons = {rec["skill"]: rec["reason"] for rec in bad}
            self.assertIn("has no scripts/emit_event.py", reasons["agent-telemetry"])
            self.assertIn("no skill directory", reasons["nope"])


if __name__ == "__main__":
    unittest.main()
