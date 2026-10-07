"""BO-1500a-1-ii: bootstrap child processes must not write to the JSON stdout channel."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
# The dev copy and the packaged template are both shipped and have diverged, so both are checked.
SCRIPT_DIRS = (REPO_ROOT / "scripts", REPO_ROOT / "templates" / "scripts")

_DRIVER = (
    "import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]);"
    "import setup_ticket_worktree as m; m._install_pre_commit_shims(Path(sys.argv[2]))"
)


def _run_with_fake_shim(scripts: Path, shim_body: str) -> subprocess.CompletedProcess:
    with tempfile.TemporaryDirectory() as tmp:
        main_repo = Path(tmp)
        shim_dir = main_repo / "scripts" / "commit_guardian"
        shim_dir.mkdir(parents=True)
        (shim_dir / "install_pre_commit_shims.py").write_text(shim_body, encoding="utf-8")
        return subprocess.run(
            [sys.executable, "-c", _DRIVER, str(scripts), str(main_repo)],
            capture_output=True,
            text=True,
            timeout=60,
        )


class TestBootstrapChildStdout(unittest.TestCase):
    def test_ac1_shim_installer_output_does_not_pollute_stdout(self):
        """AC-1: child progress lines go to stderr; stdout stays clean for JSON."""
        # covers: BO-1500a-1-ii
        # angle: failure
        for scripts in SCRIPT_DIRS:
            with self.subTest(copy=str(scripts.relative_to(REPO_ROOT))):
                result = _run_with_fake_shim(scripts, "print('[already_installed] commit-msg')\n")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    result.stdout,
                    "",
                    f"child output leaked onto the JSON stdout channel: {result.stdout!r}",
                )
                # Negative control: the progress line is preserved, on stderr.
                self.assertIn("[already_installed] commit-msg", result.stderr)


if __name__ == "__main__":
    unittest.main()
