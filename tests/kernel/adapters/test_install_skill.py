"""
MODULE: tests.kernel.adapters.test_install_skill
GOAL: Test `install-skill`: the rendered skill, the marker-based overwrite safety, `--force`, name
    and path safety, and the CLI exit codes, always against temporary directories.
BUSINESS CONTEXT: The skill is installed outside the repository by an explicit, user-approved
    command; it must never clobber a hand-written or build-managed skill of the same name, and
    must never write anywhere but `<target-dir>/<name>/SKILL.md` (design part 5).
ARCHITECTURE: Calls `install_skill` directly and through the shipped `main`. The real workspace
    `.claude/skills` is never touched: every target is a temporary directory.
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path

from kernel.adapters.claude_code.install import (
    MARKER,
    InstallRefused,
    install_skill,
    render_skill,
)
from kernel.adapters.cli import main

HAND_WRITTEN = "---\nname: leafcutter\n---\nThe hub command.\n"


def cli(*argv: str) -> tuple[int, dict]:
    """Run the shipped CLI in-process and return (exit code, stdout JSON)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = main(list(argv))
    return code, json.loads(out.getvalue())


class InstallCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.skills = Path(tmp.name).resolve() / ".claude" / "skills"


class TestRenderedSkill(InstallCase):
    def test_renders_name_command_marker_and_frontmatter(self) -> None:
        text = render_skill("leafcutter", Path("/repo/leafcutter"), "/usr/bin/python3", Path("/runs"))
        self.assertTrue(text.startswith("---\nname: leafcutter\n"))
        self.assertIn(MARKER, text)
        command = "PYTHONPATH=/repo/leafcutter /usr/bin/python3 -P -m kernel"
        self.assertIn(f"Bash({command} run *) Bash({command} resume *) Bash({command} status *)",
                      text)  # scope itself is asserted in test_skill_scope
        self.assertIn("disable-model-invocation: true", text)
        self.assertIsNone(re.search(r"\{\{[A-Z]+\}\}", text), "unsubstituted placeholder")

    def test_paths_with_spaces_are_quoted(self) -> None:
        text = render_skill("leafcutter", Path("/my repo"), "/usr/bin/python3")
        self.assertIn('PYTHONPATH="/my repo" /usr/bin/python3 -P -m kernel', text)

    def test_skill_routes_every_status_and_forbids_deciding(self) -> None:
        text = render_skill("leafcutter", Path("/r"), "python")
        for needle in ("waiting_host", "waiting_human", "completed", "blocked", "failed",
                       "allowed_operations", "forbidden_operations", "output_json_schema",
                       "output_requirements", "input_artifact_refs", "why_research_cannot_settle",
                       "structured_allowed", "relayed_by", "human:user", "trace_url",
                       "--input-file", "Never"):
            self.assertIn(needle, text)

    def test_rejects_names_that_are_not_plain(self) -> None:
        for bad in ("../x", "Leaf", "a/b", "", "-x", "x" * 70, "a b"):
            with self.assertRaises(InstallRefused, msg=bad) as caught:
                render_skill(bad)
            self.assertEqual(caught.exception.code, "invalid_name")


class TestInstallSafety(InstallCase):
    def test_installs_a_new_skill_and_reinstalling_our_own_is_allowed(self) -> None:
        path = install_skill(self.skills, "leafcutter")
        self.assertEqual(path, self.skills / "leafcutter" / "SKILL.md")
        self.assertIn(MARKER, path.read_text(encoding="utf-8"))
        again = install_skill(self.skills, "leafcutter", python="/other/python")
        self.assertIn("/other/python", again.read_text(encoding="utf-8"))

    def test_refuses_to_overwrite_a_skill_without_the_marker(self) -> None:
        target = self.skills / "leafcutter"
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text(HAND_WRITTEN, encoding="utf-8")
        with self.assertRaises(InstallRefused) as caught:
            install_skill(self.skills, "leafcutter")
        self.assertEqual(caught.exception.code, "not_a_leafcutter_skill")
        self.assertEqual((target / "SKILL.md").read_text(encoding="utf-8"), HAND_WRITTEN)

    def test_refuses_a_directory_with_no_skill_file(self) -> None:
        (self.skills / "leafcutter").mkdir(parents=True)
        with self.assertRaises(InstallRefused):
            install_skill(self.skills, "leafcutter")

    def test_force_replaces_only_skill_md_and_keeps_other_files(self) -> None:
        target = self.skills / "leafcutter"
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text(HAND_WRITTEN, encoding="utf-8")
        (target / "notes.txt").write_text("keep me", encoding="utf-8")
        install_skill(self.skills, "leafcutter", force=True)
        self.assertIn(MARKER, (target / "SKILL.md").read_text(encoding="utf-8"))
        self.assertEqual((target / "notes.txt").read_text(encoding="utf-8"), "keep me")

    def test_leaves_no_temp_files_behind(self) -> None:
        install_skill(self.skills, "leafcutter")
        self.assertEqual([p.name for p in (self.skills / "leafcutter").iterdir()], ["SKILL.md"])

    def test_a_plain_file_in_the_way_is_refused(self) -> None:
        self.skills.mkdir(parents=True)
        (self.skills / "leafcutter").write_text("not a dir", encoding="utf-8")
        with self.assertRaises(InstallRefused):
            install_skill(self.skills, "leafcutter")


class TestInstallThroughTheCli(InstallCase):
    def test_install_reports_the_path_and_exits_0(self) -> None:
        code, body = cli("install-skill", "--target-dir", str(self.skills), "--name", "kernel-x",
                         "--json")
        self.assertEqual(code, 0)
        self.assertEqual(Path(body["installed"]), self.skills / "kernel-x" / "SKILL.md")

    def test_refusal_exits_3_and_force_overrides(self) -> None:
        target = self.skills / "leafcutter"
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text(HAND_WRITTEN, encoding="utf-8")
        code, body = cli("install-skill", "--target-dir", str(self.skills), "--name", "leafcutter")
        self.assertEqual((code, body["error"]["code"]), (3, "not_a_leafcutter_skill"))
        code, body = cli("install-skill", "--target-dir", str(self.skills), "--name", "leafcutter",
                         "--force")
        self.assertEqual(code, 0)

    def test_a_traversing_name_exits_3_and_writes_nothing(self) -> None:
        code, body = cli("install-skill", "--target-dir", str(self.skills), "--name", "../evil")
        self.assertEqual((code, body["error"]["code"]), (3, "invalid_name"))
        self.assertFalse(self.skills.exists())


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 14:30 [python-coder]: Every target is a temporary directory; the orchestrator
#   installs into the real workspace after the naming PR merges. (#KernelBootstrapV0/P7)
# ====================================================================
