"""BO-4500a-4-viii: commit_step_base.git() decodes child output as UTF-8 with replacement."""

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "templates" / "scripts"))

import commit_step_base  # noqa: E402

# UTF-8 right-arrow (e2 86 92) then a raw 0x8f byte (invalid UTF-8, unmapped in cp1252).
_EMIT = r"!printf 'go \342\206\222 end \217 tail'"
_EMIT_CLEAN = r"!printf 'go \342\206\222 end'"


def _run(alias_body: str, cwd: Path):
    return commit_step_base.git(["-c", f"alias.emit={alias_body}", "emit"], cwd)


class TestGitUtf8Decoding(unittest.TestCase):
    def test_git_decodes_non_locale_bytes_as_utf8_with_replacement(self):
        # covers: BO-4500a-4-viii
        # angle: criterion
        with tempfile.TemporaryDirectory() as tmp:
            proc = _run(_EMIT, Path(tmp))
        self.assertIsInstance(proc.stdout, str)
        self.assertIsInstance(proc.stderr, str)
        self.assertIn("go \u2192 end", proc.stdout)
        self.assertIn("\ufffd", proc.stdout)
        self.assertTrue(proc.stdout.endswith(" tail"))

    def test_git_clean_utf8_output_is_intact_control(self):
        # covers: BO-4500a-4-viii
        # angle: criterion
        with tempfile.TemporaryDirectory() as tmp:
            proc = _run(_EMIT_CLEAN, Path(tmp))
        self.assertEqual(proc.stdout, "go \u2192 end")
        self.assertNotIn("\ufffd", proc.stdout)


if __name__ == "__main__":
    unittest.main()
