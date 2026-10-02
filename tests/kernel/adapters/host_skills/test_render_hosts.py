"""
MODULE: tests.kernel.adapters.host_skills.test_render_hosts
GOAL: Prove both host skills render the repository scope as fixed values, that the Codex skill
    follows the Codex facts, and that no committed template carries a machine-specific path.
BUSINESS CONTEXT: A session started in a non-repository workspace folder scoped a live run to the
    wrong folder because the skill asked the host to guess `repository_root`. The scope must be
    written at install time, and Codex needs its own explicit-only, transport-only skill.
ARCHITECTURE: Renders the real templates through `render_skill` (Claude Code) and
    `render_codex_skill` (Codex); the scope example is parsed as JSON, never searched as text.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import yaml

from kernel.adapters.claude_code import install as claude
from kernel.adapters.codex import install as codex
from kernel.config import repo_root

REPO = Path("/repo/leafcutter")
PYTHON = "/usr/bin/python3"
RUNS = Path("/data/kernel_runs")
TARGET = Path("/work/project")
SCOPE = re.compile(r'"scope": (\{.*?\})\}`', re.DOTALL)
MACHINE_PATH = re.compile(r"[A-Za-z]:[\\/]|/Users/|/home/|\\Users\\")
TEMPLATES = [Path(claude.TEMPLATE), Path(codex.TEMPLATE), Path(codex.OPENAI_TEMPLATE)]


def _scope(text: str) -> dict:
    """Return the `scope` object of the TaskInput example in a rendered skill."""
    match = SCOPE.search(text)
    assert match, "scope example not found"
    return json.loads(match.group(1).replace("\n", " "))


def _render(host: str, **kwargs) -> str:
    """Render the skill of `host` with fixed checkout, interpreter and run root."""
    render = claude.render_skill if host == "claude_code" else codex.render_codex_skill
    return render("leafcutter", REPO, PYTHON, RUNS, **kwargs)


class TestScopeIsRendered(unittest.TestCase):
    """Both hosts write the repository root and workspace id in at install time."""

    def test_both_hosts_render_repository_root_and_workspace_id(self) -> None:
        for host in ("claude_code", "codex"):
            text = _render(host, repository_root=Path("/work/my-repo"), workspace_id="ws-1")
            self.assertEqual(_scope(text),
                             {"workspace_id": "ws-1", "repository_root": "/work/my-repo"}, host)

    def test_no_placeholder_remains(self) -> None:
        for host in ("claude_code", "codex"):
            text = _render(host, repository_root=Path("/work/my-repo"))
            for stale in ("<absolute project root>", "<project name>"):
                self.assertNotIn(stale, text, host)
            self.assertIsNone(re.search(r"\{\{[A-Z_]+\}\}", text), host)

    def test_workspace_id_defaults_to_the_repository_folder_name(self) -> None:
        for host in ("claude_code", "codex"):
            text = _render(host, repository_root=Path("/work/my-repo"))
            self.assertEqual(_scope(text)["workspace_id"], "my-repo", host)

    def test_repository_root_defaults_to_the_kernel_checkout(self) -> None:
        for host in ("claude_code", "codex"):
            render = claude.render_skill if host == "claude_code" else codex.render_codex_skill
            scope = _scope(render("leafcutter", python=PYTHON, run_root=RUNS))
            self.assertEqual(scope["repository_root"], repo_root().as_posix(), host)
            self.assertEqual(scope["workspace_id"], repo_root().name, host)

    def test_values_are_json_escaped(self) -> None:
        for host in ("claude_code", "codex"):
            text = _render(host, repository_root=Path("/work/a b"), workspace_id='x"y\\z')
            self.assertEqual(_scope(text),
                             {"workspace_id": 'x"y\\z', "repository_root": "/work/a b"}, host)

    def test_windows_roots_use_forward_slashes(self) -> None:
        text = _render("codex", repository_root=Path("C:/Users/dev/leafcutter-ai"))
        self.assertEqual(_scope(text)["repository_root"], "C:/Users/dev/leafcutter-ai")


class TestCodexSkill(unittest.TestCase):
    """The Codex skill is explicit-only, transport-only and rendered for this checkout."""

    def setUp(self) -> None:
        self.text = codex.render_codex_skill("leafcutter", REPO, PYTHON, RUNS,
                                             repository_root=Path("/work/r"))
        _, front, self.body = self.text.split("---\n", 2)
        self.front = yaml.safe_load(front)

    def test_frontmatter_has_only_name_and_description(self) -> None:
        self.assertEqual(sorted(self.front), ["description", "name"])
        self.assertEqual(self.front["name"], "leafcutter")
        description = self.front["description"]
        self.assertIn("$leafcutter", description)
        self.assertIn("only when the user types", description)

    def test_goal_is_the_text_after_the_skill_mention(self) -> None:
        flat = " ".join(self.body.split())
        self.assertIn("text after `$leafcutter`", flat)
        self.assertNotIn("$ARGUMENTS", self.body)

    def test_commands_run_from_the_checkout_without_an_env_prefix(self) -> None:
        self.assertNotIn("PYTHONPATH", self.text)
        self.assertIn("/usr/bin/python3 -m kernel", self.body)
        self.assertIn(f"working directory `{REPO.as_posix()}`", " ".join(self.body.split()))

    def test_submission_files_stay_in_the_client_directory(self) -> None:
        self.assertIn(f"{RUNS.as_posix()}/client", self.body)

    def test_human_questions_use_the_tool_when_present_else_plain_text(self) -> None:
        flat = " ".join(self.body.split())
        self.assertIn("request_user_input", flat)
        self.assertNotIn("AskUserQuestion", flat)
        for needle in ("why_research_cannot_settle", "choices", "ask once more",
                       "Never choose for the user"):
            self.assertIn(needle, flat)

    def test_keeps_the_transport_rules(self) -> None:
        flat = " ".join(self.body.split())
        for needle in ("VERBATIM", "waiting_host", "waiting_human", "forbidden_operations",
                       "Do NOT run it", "decisions publish", "decision record staged",
                       "relayed_by", "Do NOT add `requested_output_schema`", "--json"):
            self.assertIn(needle, flat)
        self.assertIn('"relayed_by": "codex"', flat)
        self.assertIn('{"kind": "host", "id": "codex"}', flat)


class TestTemplatesAreMachineIndependent(unittest.TestCase):
    """Committed templates carry placeholders, never a developer's paths."""

    def test_no_machine_specific_path_in_any_template(self) -> None:
        for template in TEMPLATES:
            text = template.read_text(encoding="utf-8")
            self.assertIsNone(MACHINE_PATH.search(text), template.name)

    def test_templates_use_the_scope_placeholders(self) -> None:
        for template in (Path(claude.TEMPLATE), Path(codex.TEMPLATE)):
            text = template.read_text(encoding="utf-8")
            self.assertIn("{{REPOSITORY_ROOT}}", text, template)
            self.assertIn("{{WORKSPACE_ID}}", text, template)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-02 [python-coder]: The scope example is parsed as JSON for both hosts so a
#   reintroduced host-guessed placeholder fails here. (#KernelCodexSkill)
# ====================================================================
