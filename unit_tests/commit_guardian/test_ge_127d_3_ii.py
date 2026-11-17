"""
MODULE: unit_tests/commit_guardian/test_ge_127d_3_ii.py
COVERS: GE-127d-3-ii -- content that cannot be tokenized is INDETERMINATE (exit 2,
    no length, never a raw count and never zero); valid modern syntax is measured.

DECISION HISTORY
- 2026-10-20 [GE-127d-3-ii/test-writer]: Initial authoring.
"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ge_127d_3_content as content  # noqa: E402
import _ge_127d_3_fixture as fx  # noqa: E402


def _indeterminate_lines(output: str) -> list[str]:
    return [ln for ln in output.splitlines() if ln.startswith("INDETERMINATE: reason=")]


def _states_a_length(output: str, rel: str) -> bool:
    return bool(re.search(rf"{re.escape(rel)}.*?\b\d+\s+lines", output))


class TestUntokenizableContentIsIndeterminate(unittest.TestCase):
    def test_ge_127d_3_ii_untokenizable_content_is_indeterminate_exit_2_with_no_length(self):
        # covers: GE-127d-3-ii
        # angle: failure
        """Each of the four untokenizable files: an INDETERMINATE line naming the file and its
        language, exit 2, no stated length, not in the PASSED list; the Python reason names
        the running interpreter's major.minor; the corrected file is measured and judged
        normally; an over-limit measured file is a different token and a different exit."""
        for ext, (language, bad, good) in content.UNTOKENIZABLE.items():
            rel = f"bad{ext}"
            with tempfile.TemporaryDirectory() as tmp:
                result, output = fx.change_outcome(Path(tmp), rel, None, bad)
            lines = _indeterminate_lines(output)
            self.assertEqual(2, result.returncode, msg=f"{rel}: must exit 2. Got: {output!r}")
            self.assertEqual(1, len(lines), msg=f"{rel}: exactly one INDETERMINATE line. Got: {output!r}")
            self.assertIn(rel, lines[0], msg=f"{rel}: the line must name the file")
            self.assertIn(language, lines[0], msg=f"{rel}: the line must name the language")
            self.assertIn("could not be read as", lines[0], msg=f"{rel}: must say it could not be read as that language")
            self.assertFalse(_states_a_length(output, rel), msg=f"{rel}: no length, no PASSED listing. Got: {output!r}")
            self.assertNotIn("Lines:", output, msg=f"{rel}: no over-limit block for an unmeasured file")
            if ext == ".py":
                version = f"{sys.version_info.major}.{sys.version_info.minor}"
                self.assertIn(version, lines[0], msg="the Python reason must name the running interpreter")
            with tempfile.TemporaryDirectory() as tmp:
                fixed, fixed_output = fx.change_outcome(Path(tmp), rel, None, good)
            self.assertEqual([], _indeterminate_lines(fixed_output), msg=f"{rel}: corrected file measured. {fixed_output!r}")
            self.assertEqual(0, fixed.returncode, msg=f"{rel}: corrected file is judged normally. {fixed_output!r}")
            self.assertTrue(_states_a_length(fixed_output, rel), msg=f"{rel}: corrected file states a length")
        big, _ = content.build_text(".js", 60, 2, "line")
        with tempfile.TemporaryDirectory() as tmp:
            refused, refused_output = fx.change_outcome(Path(tmp), "big.js", None, big)
        self.assertEqual(1, refused.returncode, msg="an over-limit measured file exits 1, not 2")
        self.assertEqual([], _indeterminate_lines(refused_output), msg="and never says INDETERMINATE")

    def test_ge_127d_3_ii_an_untokenizable_previous_version_is_reported_unresolvable(self):
        # covers: GE-127d-3-ii
        # angle: failure
        """HEAD holds an unclosed block comment, the staged version is valid: the previous
        length is reported unresolvable in GE-127b-1-i's vocabulary and the commit is refused."""
        _language, bad, good = content.UNTOKENIZABLE[".js"]
        with tempfile.TemporaryDirectory() as tmp:
            result, output = fx.change_outcome(Path(tmp), "prev.js", bad, good + "const more = 3;\n")
        lines = _indeterminate_lines(output)
        self.assertEqual(2, result.returncode, msg=f"must refuse with the INDETERMINATE exit. Got: {output!r}")
        self.assertEqual(1, len(lines), msg=f"exactly one INDETERMINATE line. Got: {output!r}")
        self.assertIn("previous length", lines[0])
        self.assertIn("could not be interpreted", lines[0])

    def test_ge_127d_3_ii_valid_modern_syntax_is_always_measured(self):
        # covers: GE-127d-3-ii
        # angle: boundary
        """Nested template literals, optional chaining, a regex containing ``/*`` and a Python
        f-string holding ``#`` in a replacement field are measured with a stated length and no
        INDETERMINATE; a .py file that tokenizes but does not parse is measured too."""
        cases = {
            "ok.js": (content.ACCEPTED_SYNTAX[".js"] + "// genuine\n/* genuine */\n", 6),
            "ok.py": (content.ACCEPTED_SYNTAX[".py"] + "# genuine\n", 3),
            "syntax_error.py": ("x = = 1\nreturn 5\nclass\n# genuine\n", 3),
        }
        for rel, (text, code_lines) in cases.items():
            with tempfile.TemporaryDirectory() as tmp:
                result, output = fx.change_outcome(Path(tmp), rel, None, text, limit=100)
            self.assertEqual([], _indeterminate_lines(output), msg=f"{rel}: valid syntax is never INDETERMINATE. {output!r}")
            self.assertEqual(0, result.returncode, msg=f"{rel}: must complete. Got: {output!r}")
            stated = re.search(rf"{re.escape(rel)}\s*\((?:new|modified),\s*(\d+)\s+lines", output)
            self.assertIsNotNone(stated, msg=f"{rel}: a length must be stated. Got: {output!r}")
            self.assertEqual(code_lines, int(stated.group(1)), msg=f"{rel}: the stated length is the code lines. {output!r}")

    def test_ge_127d_3_ii_a_refused_file_whose_part_cannot_be_tokenized_says_description_unavailable(self):
        # covers: GE-127d-3-ii
        # angle: seam
        """An over-limit .sql file whose CREATE-split segment cannot be lexed alone (the split
        falls inside a block comment) is refused at exit 1 with the ordinary over-limit block and
        a DESCRIPTION UNAVAILABLE line; no crash, no exit 2."""
        body = ["CREATE TABLE alpha (id int);", *[f"SELECT {i};" for i in range(14)], "/* old notes:",
                "CREATE TABLE ghost (id int);", "*/", *[f"SELECT {i};" for i in range(14, 28)]]
        with tempfile.TemporaryDirectory() as tmp:
            result, output = fx.change_outcome(Path(tmp), "schema.sql", None, "\n".join(body) + "\n", limit=10)
        self.assertEqual(1, result.returncode, msg=f"must be the ordinary over-limit refusal. Got: {output!r}")
        self.assertIn("FILE TOO LARGE", output)
        self.assertIn("DESCRIPTION UNAVAILABLE", output)
        self.assertNotIn("Traceback", output)
        self.assertEqual([], _indeterminate_lines(output))


if __name__ == "__main__":
    unittest.main()
