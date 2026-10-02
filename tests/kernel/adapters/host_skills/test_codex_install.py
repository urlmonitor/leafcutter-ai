"""
MODULE: tests.kernel.adapters.host_skills.test_codex_install
GOAL: Test the Codex installer: the three files it writes, the explicit-only policy, the rules
    that allow exactly run, resume and status, the marker-based overwrite guard, and the CLI
    flags `--host`, `--repository-root` and `--workspace-id`.
BUSINESS CONTEXT: A Codex prefix rule runs the matched command outside the sandbox with no
    prompt, so it must allow only the transport subcommands and must not clobber a hand-written
    skill, policy or rules file of the same name.
ARCHITECTURE: Calls `install_codex_skill` and the shipped `main` against temporary directories;
    the rules file is parsed back from the text the installer wrote, never hand-written.
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from typing import cast

import yaml

from kernel.adapters.cli import main
from kernel.adapters.codex.install import (
    MARKER,
    InstallRefused,
    install_codex_skill,
    render_codex_skill,
)
from kernel.adapters.codex.rules import render_rules
from kernel.adapters.skill_common import render_scope, shell_path
from tests.kernel.helpers import narrow

REPO = Path("/repo/leafcutter")
PYTHON = "/usr/bin/python3"
HAND_WRITTEN = "# somebody else's file\n"
RULE = re.compile(r"prefix_rule\((.*?)\n\)", re.DOTALL)
SUBCOMMAND = re.compile(r'pattern = \[.*?, "-m", "kernel", "(\w[\w-]*)"\]')


def posix_text(text: str) -> Path:
    """Return `text` as a POSIX-flavoured path object (backslashes stay text), typed as Path."""
    return cast(Path, PurePosixPath(text))


def cli(*argv: str) -> tuple[int, dict]:
    """Run the shipped CLI in-process and return (exit code, stdout JSON)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = main(list(argv))
    return code, json.loads(out.getvalue())


class CodexCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.skill = self.root / ".agents" / "skills" / "leafcutter" / "SKILL.md"
        self.policy = self.skill.parent / "agents" / "openai.yaml"
        self.rules = self.root / ".codex" / "rules" / "leafcutter.rules"

    def install(self, **kwargs) -> list[Path]:
        """Install with fixed interpreter, checkout and run root."""
        base = {"repo": REPO, "python": PYTHON, "run_root": Path("/runs")}
        return install_codex_skill(self.root, "leafcutter", **{**base, **kwargs})

    def files(self) -> list[Path]:
        """Return every file below the temporary workspace root."""
        return sorted(p for p in self.root.rglob("*") if p.is_file())


class TestInstalledFiles(CodexCase):
    def test_writes_exactly_the_three_files_and_lists_them(self) -> None:
        written = self.install()
        self.assertEqual(sorted(written), sorted([self.skill, self.policy, self.rules]))
        self.assertEqual(self.files(), sorted(written))

    def test_every_file_carries_the_marker(self) -> None:
        for path in self.install():
            self.assertIn(MARKER, path.read_text(encoding="utf-8"), path.name)

    def test_the_policy_is_explicit_only_with_a_display_name(self) -> None:
        self.install()
        policy = yaml.safe_load(self.policy.read_text(encoding="utf-8"))
        self.assertIs(policy["policy"]["allow_implicit_invocation"], False)
        self.assertTrue(policy["interface"]["display_name"])

    def test_rules_allow_exactly_run_resume_and_status(self) -> None:
        self.install()
        bodies = RULE.findall(self.rules.read_text(encoding="utf-8"))
        self.assertEqual(len(bodies), 3)
        subcommands = []
        for body in bodies:
            self.assertIn('decision = "allow"', body)
            self.assertIn(PYTHON, body)
            subcommands.append(narrow(SUBCOMMAND.search(body)).group(1))
        self.assertEqual(sorted(subcommands), ["resume", "run", "status"])

    def test_forbidden_subcommands_are_only_negative_examples(self) -> None:
        self.install()
        for body in RULE.findall(self.rules.read_text(encoding="utf-8")):
            allowed, _, negatives = body.partition("not_match")
            for subcommand in ("cancel", "gaps", "decisions", "install-skill"):
                self.assertNotIn(subcommand, allowed)
            self.assertIn("install-skill", negatives)

    def test_windows_interpreters_match_in_native_and_forward_slash_form(self) -> None:
        text = render_rules("leafcutter", "C:\\Users\\dev\\.venv\\Scripts\\python.exe")
        self.assertIn('["C:\\\\Users\\\\dev\\\\.venv\\\\Scripts\\\\python.exe", '
                      '"C:/Users/dev/.venv/Scripts/python.exe"]', text)

    def test_examples_use_forward_slashes_and_posix_paths_stay_single(self) -> None:
        win = render_rules("leafcutter", "C:\\Users\\dev\\.venv\\Scripts\\python.exe")
        for line in win.splitlines():
            if line.strip().startswith(("match", "not_match")):
                self.assertNotIn("\\", line)
        posix = render_rules("leafcutter", "/usr/bin/python3")
        self.assertIn('pattern = ["/usr/bin/python3", "-m", "kernel", "run"]', posix)

    def test_windows_strings_render_the_same_on_any_os(self) -> None:
        # PurePosixPath keeps backslashes as text, as a Linux runner sees a Windows string.
        win = str(posix_text("C:\\Users\\dev\\leafcutter ai"))
        self.assertEqual(shell_path(win), '"C:/Users/dev/leafcutter ai"')
        scope = render_scope(posix_text("C:\\Users\\dev\\repo"), None)
        self.assertEqual(scope, {"REPOSITORY_ROOT": "C:/Users/dev/repo", "WORKSPACE_ID": "repo"})
        text = render_codex_skill("leafcutter", posix_text("C:\\kern"), "C:\\py\\python.exe",
                                  posix_text("C:\\runs"))
        self.assertIn("`C:/py/python.exe -m kernel`", text)
        self.assertIn("working directory `C:/kern`", " ".join(text.split()))
        self.assertIn("C:/runs/client/", text)

    def test_the_skill_names_the_rendered_scope(self) -> None:
        self.install(repository_root=Path("/work/r"), workspace_id="ws")
        text = self.skill.read_text(encoding="utf-8")
        self.assertIn('"repository_root": "/work/r"', text)
        self.assertIn('"workspace_id": "ws"', text)


class TestOverwriteGuard(CodexCase):
    def _plant(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(HAND_WRITTEN, encoding="utf-8")

    def test_each_foreign_file_blocks_the_install_and_nothing_is_written(self) -> None:
        for foreign in ("skill", "policy", "rules"):
            with self.subTest(foreign=foreign):
                self.setUp()
                path = getattr(self, foreign)
                self._plant(path)
                with self.assertRaises(InstallRefused) as caught:
                    self.install()
                self.assertEqual(caught.exception.code, "not_a_leafcutter_skill")
                self.assertIn(path.name, caught.exception.message)
                self.assertEqual(path.read_text(encoding="utf-8"), HAND_WRITTEN)
                self.assertEqual(self.files(), [path])

    def test_force_overwrites_all_three(self) -> None:
        for path in (self.skill, self.policy, self.rules):
            self._plant(path)
        self.install(force=True)
        for path in (self.skill, self.policy, self.rules):
            self.assertIn(MARKER, path.read_text(encoding="utf-8"))

    def test_reinstalling_our_own_files_is_allowed(self) -> None:
        self.install()
        self.install(python="/other/python")
        self.assertIn("/other/python", self.rules.read_text(encoding="utf-8"))

    def test_leaves_no_temp_files_behind(self) -> None:
        self.install()
        self.assertEqual(list(self.root.rglob("*.tmp")), [])

    def test_a_bad_name_is_refused_before_writing(self) -> None:
        with self.assertRaises(InstallRefused) as caught:
            install_codex_skill(self.root, "../evil")
        self.assertEqual(caught.exception.code, "invalid_name")
        self.assertEqual(list(self.root.iterdir()), [])


class TestCli(CodexCase):
    def test_codex_host_with_scope_flags_lists_every_file(self) -> None:
        repo = self.root / "my-repo"
        repo.mkdir()
        code, body = cli("install-skill", "--host", "codex", "--target-dir", str(self.root),
                         "--name", "leafcutter", "--repository-root", str(repo),
                         "--workspace-id", "ws-9", "--json")
        self.assertEqual(code, 0)
        self.assertEqual(body["host"], "codex")
        self.assertEqual(sorted(Path(p) for p in body["files"]),
                         sorted([self.skill, self.policy, self.rules]))
        text = self.skill.read_text(encoding="utf-8")
        self.assertIn(f'"repository_root": "{repo.as_posix()}"', text)
        self.assertIn('"workspace_id": "ws-9"', text)

    def test_workspace_id_defaults_to_the_folder_name(self) -> None:
        repo = self.root / "my-repo"
        repo.mkdir()
        code, _ = cli("install-skill", "--host", "codex", "--target-dir", str(self.root),
                      "--name", "leafcutter", "--repository-root", str(repo))
        self.assertEqual(code, 0)
        self.assertIn('"workspace_id": "my-repo"', self.skill.read_text(encoding="utf-8"))

    def test_claude_code_stays_the_default_host_and_takes_the_scope_flags(self) -> None:
        repo = self.root / "r"
        repo.mkdir()
        skills = self.root / ".claude" / "skills"
        code, body = cli("install-skill", "--target-dir", str(skills), "--name", "leafcutter",
                         "--repository-root", str(repo), "--workspace-id", "w")
        self.assertEqual(code, 0)
        self.assertEqual(Path(body["installed"]), skills / "leafcutter" / "SKILL.md")
        text = Path(body["installed"]).read_text(encoding="utf-8")
        self.assertIn(f'"repository_root": "{repo.as_posix()}"', text)

    def test_unknown_host_is_a_usage_error(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            code = main(["install-skill", "--host", "vim", "--target-dir", str(self.root),
                         "--name", "x"])
        self.assertEqual(code, 2)

    def test_a_missing_repository_root_is_rejected_and_writes_nothing(self) -> None:
        code, body = cli("install-skill", "--host", "codex", "--target-dir", str(self.root),
                         "--name", "leafcutter", "--repository-root", str(self.root / "nope"))
        self.assertEqual((code, body["error"]["code"]), (3, "repository_root_missing"))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_refusal_exits_3_and_force_overrides(self) -> None:
        self.rules.parent.mkdir(parents=True)
        self.rules.write_text(HAND_WRITTEN, encoding="utf-8")
        args = ["install-skill", "--host", "codex", "--target-dir", str(self.root), "--name",
                "leafcutter"]
        code, body = cli(*args)
        self.assertEqual((code, body["error"]["code"]), (3, "not_a_leafcutter_skill"))
        code, _ = cli(*args, "--force")
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-02 [python-coder]: The guard test plants each foreign file in turn and asserts that
#   no other file is written, so a half-installed skill cannot slip through. (#KernelCodexSkill)
# ====================================================================
