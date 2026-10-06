"""
MODULE: tests.kernel.adapters.test_skill_scope
GOAL: Prove the rendered skill pre-approves only what a transport needs: the kernel's run,
    resume and status commands, file edits inside the client scratch directory, and reads of
    the kernel run root.
BUSINESS CONTEXT: `allowed-tools` pre-approves tools without a prompt. A prompt-injected packet
    must not be able to cancel a run, reinstall the skill or write an arbitrary repository file
    without the user being asked (Rev 3 section 11).
ARCHITECTURE: Renders the real SKILL.md template through `render_skill` and parses the real
    frontmatter line; no hand-written fixture of the frontmatter is used.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from kernel.adapters.claude_code.install import render_skill

REPO = Path("/repo/leafcutter")
PYTHON = "/usr/bin/python3"
RUN_ROOT = Path("/data/kernel_runs")
COMMAND = "PYTHONPATH=/repo/leafcutter /usr/bin/python3 -m kernel"
RULE = re.compile(r"[A-Za-z]+(?:\([^)]*\))?")


def _allowed(text: str) -> list[str]:
    """Return the `allowed-tools` rules of a rendered skill."""
    line = next(ln for ln in text.splitlines() if ln.startswith("allowed-tools:"))
    return RULE.findall(line.split(":", 1)[1])


class TestAllowedToolsScope(unittest.TestCase):
    """The pre-approved tools are the least a transport needs."""

    def setUp(self) -> None:
        self.text = render_skill("leafcutter", REPO, PYTHON, RUN_ROOT)
        self.rules = _allowed(self.text)

    def test_bash_is_limited_to_run_resume_and_status(self) -> None:
        # covers: DK-600c-4
        # covers: DK-600d-1
        bash = sorted(r for r in self.rules if r.startswith("Bash"))
        self.assertEqual(bash, sorted(f"Bash({COMMAND} {sub} *)"
                                      for sub in ("run", "resume", "status")))

    def test_cancel_gaps_and_install_skill_are_not_pre_approved(self) -> None:
        joined = " ".join(self.rules)
        for forbidden in ("cancel", "gaps", "install-skill", "--force"):
            self.assertNotIn(forbidden, joined)

    def test_no_unscoped_read_or_write(self) -> None:
        for rule in self.rules:
            self.assertNotIn(rule, ("Read", "Write", "Edit", "Bash"))

    def test_file_writes_are_scoped_to_the_client_scratch_directory(self) -> None:
        edits = [r for r in self.rules if r.startswith(("Edit(", "Write("))]
        self.assertEqual(edits, ["Edit(//data/kernel_runs/client/**)"])
        self.assertIn("/data/kernel_runs/client", self.text.split("---", 2)[2])

    def test_reads_are_scoped_to_the_run_root(self) -> None:
        reads = [r for r in self.rules if r.startswith("Read")]
        self.assertEqual(reads, ["Read(//data/kernel_runs/**)"])

    def test_windows_run_root_becomes_a_posix_drive_rule(self) -> None:
        text = render_skill("leafcutter", REPO, PYTHON, Path("C:/Users/dev/runs"))
        self.assertIn("Edit(//c/Users/dev/runs/client/**)", _allowed(text))

    def test_user_questions_stay_available(self) -> None:
        self.assertIn("AskUserQuestion", self.rules)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 16:10 [python-coder]: Rules use the current space-star Bash form and `Edit(...)`
#   for writes (Claude Code consults only Edit/Read path rules; a `Write(path)` rule is
#   accepted but never consulted). (#KernelBootstrapV0/FIXC)
# ====================================================================
