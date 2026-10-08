"""
MODULE: tests.kernel.memory.test_publish_command_runnable
GOAL: The `decisions publish` command the kernel prints in the staged-record limitation runs
    exactly as printed, from any shell and any directory.
BUSINESS CONTEXT: Plain `python` in the owner's shell is the system interpreter, without the
    project venv or the kernel on its path, so the printed command failed with "No module named
    kernel". The command must name the interpreter the kernel runs under and the path needed to
    import `kernel`, and must say which folder it writes to.
ARCHITECTURE: The text comes from a real staged run (the precedent-reuse scenario); the printed
    command is the text after "publish it for review with: " to the end of the note, and must be a
    plain argv (no `cd`, `&&` or env-var prefix) so it runs without a shell.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from kernel.capabilities.decision import publish_command as pc
from kernel.config import load_kernel_config, repo_root
from tests.kernel.memory import test_decision_precedent as scenario

MARKER = "publish it for review with: "


class TestPrintedPublishCommand(scenario.PrecedentCase):
    """The limitation text of a staged record, taken from a real run."""

    config = None  # a KernelConfig to run the decision under; None keeps the default

    def ctx(self, evidence=None, **overrides):  # noqa: ANN001, ANN201
        if self.config is not None:
            overrides["config"] = self.config
        return super().ctx(evidence, **overrides)

    def note(self) -> str:
        inv, ctx, waiting = self.goal()
        done = self.answer(inv, ctx, waiting, {"choice_id": "reuse"}, actor="human:ada")
        (note,) = [x for x in done.limitations if x.startswith("decision record staged:")]
        return note

    def test_ac1_names_the_interpreter_the_kernel_runs_under(self) -> None:
        # covers: UNKNOWN
        # angle: criterion
        note = self.note()
        self.assertIn(sys.executable, note.split(MARKER, 1)[1])
        self.assertNotIn(f"{MARKER}python -m", note)

    def test_ac2_names_the_path_needed_to_import_kernel(self) -> None:
        # covers: UNKNOWN
        # angle: criterion
        command = self.note().split(MARKER, 1)[1]
        self.assertIn(str(repo_root()), command)

    def test_ac3_states_the_folder_it_writes_to(self) -> None:
        # covers: UNKNOWN
        # angle: criterion
        note = self.note()
        before = note.split(MARKER, 1)[0]
        self.assertIn("docs", before + note)
        self.assertIn("decisions", before)
        self.assertIn(str(repo_root()), before)
    def test_folder_in_notice_follows_configured_decisions_dir(self) -> None:
        # covers: UNKNOWN
        # angle: regression
        """A non-default memory.decisions_dir is the folder the notice names (not docs/decisions)."""
        base = load_kernel_config()
        memory = base.memory.model_copy(update={"decisions_dir": "records/custom-decisions"})
        self.config = base.model_copy(update={"memory": memory})
        before = self.note().split(MARKER, 1)[0]
        expected = memory.decisions_folder(repo_root())
        self.assertIn(str(expected), before)
        self.assertNotIn(str(repo_root() / "docs" / "decisions"), before)

    def test_ac4_printed_command_runs_from_an_unrelated_directory(self) -> None:
        # covers: UNKNOWN
        # angle: reachability
        """Run the printed command verbatim (no shell) from a temp dir; expect a JSON result.

        The run id is a fixture id with no staged record, so nothing is written to the checkout;
        the command must still import kernel and answer with a JSON document (a refusal).
        """
        command = self.note().split(MARKER, 1)[1].strip().removeprefix("& ")
        argv = shlex.split(command, posix=(os.name != "nt"))
        argv = [a[1:-1] if len(a) > 1 and a[0] == a[-1] == '"' else a for a in argv]
        argv[-1:] = ["run-doesnotexist00000000"]  # replace the real run id (last token)
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        with tempfile.TemporaryDirectory() as elsewhere:
            proc = subprocess.run(argv, cwd=elsewhere, env=env, capture_output=True, text=True,
                                  timeout=60, check=False)
        self.assertNotIn("No module named", proc.stderr)
        doc = json.loads(proc.stdout)
        self.assertIn("ok", doc)


    def test_ac5_command_uses_scripts_launcher_without_spaces_unquoted(self) -> None:
        # covers: UNKNOWN
        # angle: criterion
        command = self.note().split(MARKER, 1)[1]
        if " " not in sys.executable and " " not in str(repo_root()):
            self.assertFalse(command.startswith(("&", '"')))
        self.assertIn("run_kernel.py decisions publish --run-id ", command)
        self.assertIn(str(Path("scripts") / "run_kernel.py"), command)


class TestPublishCommandQuoting(unittest.TestCase):
    """Quote only whitespace paths; PowerShell `&` prefix only when quoting on Windows."""

    def build(self, exe: str, root: str, os_name: str) -> str:
        with mock.patch.object(pc, "repo_root", return_value=Path(root)),                 mock.patch.object(pc.sys, "executable", exe),                 mock.patch.object(pc.os, "name", os_name):
            return pc.publish_command("run-1")

    def test_no_spaces_prints_plain_form_on_every_os(self) -> None:
        # covers: UNKNOWN
        # angle: criterion
        for os_name in ("nt", "posix"):
            command = self.build("/py/python", "/repo", os_name)
            self.assertEqual(
                command, f"/py/python {Path('/repo') / 'scripts' / 'run_kernel.py'} "
                         "decisions publish --run-id run-1")

    def test_spaces_quote_path_and_prefix_ampersand_on_windows(self) -> None:
        # covers: UNKNOWN
        # angle: edge
        command = self.build("/py/python", "/my repo", "nt")
        launcher = Path("/my repo") / "scripts" / "run_kernel.py"
        self.assertEqual(command, f'& /py/python "{launcher}" decisions publish --run-id run-1')

    def test_spaces_quote_without_ampersand_on_posix(self) -> None:
        # covers: UNKNOWN
        # angle: edge
        command = self.build("/py thon/python", "/repo", "posix")
        self.assertTrue(command.startswith('"/py thon/python" '))
        self.assertFalse(command.startswith("&"))


if __name__ == "__main__":
    unittest.main()
