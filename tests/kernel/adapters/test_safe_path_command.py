"""
MODULE: tests.kernel.adapters.test_safe_path_command
GOAL: Prove the rendered kernel command (`python -P -m kernel`) runs the kernel on PYTHONPATH even
    when the current directory holds another `kernel/` package.
BUSINESS CONTEXT: Live failure 2026-10-02: resume from another checkout's directory imported that
    checkout's kernel and answered run_not_found.
ARCHITECTURE: Real subprocess of the real CLI; a dummy shadow package stands in for the other checkout.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from kernel.adapters.claude_code.install import command_line, render_skill
from kernel.config import repo_root

SHADOW = 'raise RuntimeError("shadow kernel imported from cwd")\n'


class SafePathCommand(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.cwd = Path(tmp.name).resolve()
        (self.cwd / "kernel").mkdir()
        (self.cwd / "kernel" / "__init__.py").write_text(SHADOW, encoding="utf-8")
        self.run_root = self.cwd / "runs"

    def _run(self, *flags: str) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "PYTHONPATH": str(repo_root()),
               "LEAFCUTTER_KERNEL_RUN_ROOT": str(self.run_root)}
        env.pop("PYTHONSAFEPATH", None)
        return subprocess.run([sys.executable, *flags, "-m", "kernel", "gaps", "--json"],
                              cwd=self.cwd, env=env, capture_output=True, text=True, timeout=60)

    def test_without_safe_path_the_shadow_wins(self) -> None:
        result = self._run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("shadow kernel imported", result.stderr)

    def test_safe_path_runs_the_real_kernel(self) -> None:
        result = self._run("-P")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("shadow", result.stderr)
        self.assertIn("total", json.loads(result.stdout))

    def test_rendered_command_and_skill_use_safe_path(self) -> None:
        command = command_line(Path("/repo"), "/usr/bin/python3")
        self.assertIn("python3 -P -m kernel", command)
        text = render_skill("leafcutter", repo=repo_root(), python=sys.executable)
        self.assertIn(" -P -m kernel run *", text)


if __name__ == "__main__":
    unittest.main()
