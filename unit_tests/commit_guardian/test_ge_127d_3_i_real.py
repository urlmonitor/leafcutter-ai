"""
MODULE: unit_tests/commit_guardian/test_ge_127d_3_i_real.py
COVERS: GE-127d-3-i -- the two real_artifact descriptors: tracked Python files
    against an independent ast/tokenize derivation, and every tracked JS/TS file
    against the TypeScript compiler's own comment ranges.

DECISION HISTORY
- 2026-10-20 [GE-127d-3-i/test-writer]: Initial authoring.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tokenize
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ge_127d_3_content as content  # noqa: E402
import _ge_127d_3_fixture as fx  # noqa: E402

_NATIVE_DECISION = fx.REPO_ROOT / "tests" / "knowledge" / "test_native_decision.py"


def _tracked(*patterns: str) -> list[Path]:
    out = subprocess.run(
        ["git", "-C", str(fx.REPO_ROOT), "ls-files", *patterns], capture_output=True, text=True, timeout=60, check=True
    )
    return sorted(fx.REPO_ROOT / line for line in out.stdout.splitlines() if (fx.REPO_ROOT / line).is_file())


class TestRealFilesAgainstIndependentTokenizers(unittest.TestCase):
    def test_ge_127d_3_i_a_real_python_file_measures_what_an_independent_tokenizer_says(self):
        # covers: GE-127d-3-i
        # angle: real_artifact
        """test_native_decision.py (the KI's 127-line false span) and a sample of real
        tracked .py files measure what ast (standalone strings) + tokenize (comments)
        derive independently, computed at run time -- never a literal."""
        tracked = _tracked("*.py")
        sample = [p for i, p in enumerate(tracked) if i % max(1, len(tracked) // 30) == 0]
        if _NATIVE_DECISION not in sample:
            sample.append(_NATIVE_DECISION)
        oracle: dict[Path, int] = {}
        for path in sample:
            try:
                oracle[path] = content.independent_python_length(path.read_text(encoding="utf-8"))
            except (SyntaxError, tokenize.TokenError, UnicodeDecodeError, ValueError):
                continue
        self.assertIn(_NATIVE_DECISION, oracle, msg="the KI's real file must be independently derivable")
        self.assertGreaterEqual(len(oracle), 10, msg="the real-file sample must not be trivially small")
        measured = fx.measure_files(list(oracle))
        wrong = [(str(p.relative_to(fx.REPO_ROOT)), measured[str(p)], want) for p, want in oracle.items()
                 if measured[str(p)] != want]
        self.assertEqual([], wrong, msg="a real Python file must measure what the independent tokenizer says")

    def test_ge_127d_3_i_every_tracked_js_and_ts_file_measures_what_the_typescript_compiler_says(self):
        # covers: GE-127d-3-i
        # angle: real_artifact
        """Every tracked .js/.mjs/.ts/.tsx file measures what the TypeScript compiler's own
        comment ranges derive (computed in a Node subprocess using leafcutter-web's installed
        typescript). Fails rather than skips in CI when Node or typescript is missing."""
        ts_dir = content.locate_typescript(fx.REPO_ROOT)
        if ts_dir is None:
            if os.environ.get("CI"):
                self.fail("typescript is not installed under leafcutter-web/node_modules (required in CI)")
            self.skipTest("typescript not installed locally; this descriptor fails (not skips) in CI")
        files = _tracked("*.js", "*.mjs", "*.ts", "*.tsx")
        self.assertGreater(len(files), 20, msg="the real tracked JS/TS population must be present")
        oracle = content.ts_oracle_lengths([str(p) for p in files], ts_dir)
        measured = fx.measure_files(files)
        wrong = [(Path(p).name, measured[p], want) for p, want in oracle.items() if measured[p] != want]
        self.assertEqual([], wrong, msg="every tracked JS/TS file must measure what the compiler's comment ranges say")


if __name__ == "__main__":
    unittest.main()
