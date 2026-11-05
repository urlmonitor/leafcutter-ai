"""
MODULE: unit_tests/commit_guardian/test_ge_127d_3_iv.py
COVERS: GE-127d-3-iv -- added lines are diffed over COUNTED lines keyed by their
    non-comment text, so restyling a comment never counts as lines added.

DECISION HISTORY
- 2026-10-20 [GE-127d-3-iv/test-writer]: Initial authoring.
"""

from __future__ import annotations

import ast
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ge_127d_3_content as content  # noqa: E402
import _ge_127d_3_fixture as fx  # noqa: E402

_LIMIT = 30
_POSITIONS = ("module", "function", "between", "trailing")


def _scenario(rel: str, head: str, staged: str, limit: int = _LIMIT):
    with tempfile.TemporaryDirectory() as tmp:
        result, output = fx.change_outcome(Path(tmp), rel, head, staged, limit=limit)
    return result, output, fx.outcome_numbers(output)


class TestRestyleAddsNothing(unittest.TestCase):
    def test_ge_127d_3_iv_restyling_comments_either_way_adds_zero_lines(self):
        # covers: GE-127d-3-iv
        # angle: discrimination
        """Over-limit .js (``//`` run to a block and back) and .py (``#`` run to a standalone
        string and back at module, function, between-function and trailing-DECISION-HISTORY
        positions): each completes, states 0 lines added, and quotes equal lengths."""
        line_js, _ = content.build_text(".js", 40, 4, "line")
        block_js, _ = content.build_text(".js", 40, 4, "block")
        pairs = [("big.js", line_js, block_js), ("big.js", block_js, line_js)]
        for position in _POSITIONS:
            hashed = content.py_positioned(position, "hash", 4, extra_code=40)
            string = content.py_positioned(position, "string", 4, extra_code=40)
            pairs += [(f"big_{position}.py", hashed, string), (f"big_{position}.py", string, hashed)]
        problems = []
        for rel, head, staged in pairs:
            result, output, numbers = _scenario(rel, head, staged)
            if result.returncode != 0 or numbers["added"] != 0 or numbers["previous"] != numbers["new"]:
                problems.append((rel, result.returncode, numbers, output[-300:]))
        self.assertEqual([], problems, msg="a restyle in either direction must add 0 lines and move nothing")

    def test_ge_127d_3_iv_paragraph_to_block_restyles_and_blank_line_only_changes_add_zero(self):
        # covers: GE-127d-3-iv
        # angle: discrimination
        """Over-limit files: (a) blank-separated ``//`` / ``#`` comment paragraphs rewritten as
        one block / standalone string with a blank inside; (b) a change that ONLY adds blank
        lines, or ONLY removes them, anywhere (between code, between comments, inside a used
        multi-line string). Each completes, states 0 lines added, quotes equal lengths."""
        problems = []
        filler_js = "".join(f"{content.code_line('.js', i)}\n" for i in range(40))
        filler_py = "".join(f"{content.code_line('.py', i)}\n" for i in range(40))
        pairs = [
            ("big.js", "// a\n\n// b\n" + filler_js, "/* a\n\n b */\n" + filler_js),
            ("big.js", "/* a\n\n b */\n" + filler_js, "// a\n\n// b\n" + filler_js),
            ("big.py", "# a\n\n# b\n" + filler_py, '"""a\n\nb"""\n' + filler_py),
            ("big.py", '"""a\n\nb"""\n' + filler_py, "# a\n\n# b\n" + filler_py),
        ]
        spaced_js = filler_js.replace("\n", "\n\n")
        used_py = 'TEXT = """\nfirst\nsecond\n"""\n' + filler_py
        pairs += [
            ("blank.js", filler_js, spaced_js),
            ("blank.js", spaced_js, filler_js),
            ("blank.py", used_py, used_py.replace("first\n", "first\n\n\n")),
            ("blank.py", used_py.replace("first\n", "first\n\n\n"), used_py),
        ]
        for rel, head, staged in pairs:
            result, output, numbers = _scenario(rel, head, staged)
            if result.returncode != 0 or numbers["added"] != 0 or numbers["previous"] != numbers["new"]:
                problems.append((rel, result.returncode, numbers, output[-300:]))
        self.assertEqual([], problems, msg="paragraph-to-block restyles and blank-line-only changes add 0 lines")

    def test_ge_127d_3_iv_appending_to_a_trailing_decision_history_string_adds_zero(self):
        # covers: GE-127d-3-iv
        # angle: real_artifact
        """A real tracked .py ending in a module-level DECISION HISTORY string, copied into a
        temporary repository (limit set so it is over): appending E entries inside that string
        completes, states 0 lines added, and quotes the same length before and after."""
        listing = subprocess.run(
            ["git", "-C", str(fx.REPO_ROOT), "ls-files", "templates/scripts/commit_guardian/*.py"],
            capture_output=True, text=True, timeout=60, check=True,
        ).stdout.split()
        candidates = []
        for rel in listing:
            text = (fx.REPO_ROOT / rel).read_text(encoding="utf-8")
            try:
                last = ast.parse(text).body[-1]
                independent = content.independent_python_length(text)
            except (SyntaxError, IndexError, ValueError):
                continue
            is_string = isinstance(last, ast.Expr) and isinstance(last.value, ast.Constant)
            if is_string and isinstance(last.value.value, str) and "DECISION HISTORY" in last.value.value and independent >= 60:
                candidates.append((independent, rel, text))
        self.assertTrue(candidates, msg="the real tree must hold a file ending in a DECISION HISTORY string")
        independent, rel, text = min(candidates)
        for entries in (1, 7):
            cut = text.rstrip().rfind('"""')
            appended = text[:cut] + "".join(f"- appended entry {i}\n" for i in range(entries)) + text[cut:]
            result, output, numbers = _scenario("real_history.py", text, appended, limit=independent // 2)
            self.assertEqual(0, result.returncode, msg=f"E={entries}: must complete. Got: {output!r}")
            self.assertEqual(0, numbers["added"], msg=f"E={entries}: appended string lines add 0. Got: {output!r}")
            self.assertEqual((independent, independent), (numbers["previous"], numbers["new"]), msg=output)

    def test_ge_127d_3_iv_a_restyle_does_not_hide_code_added_in_the_same_change(self):
        # covers: GE-127d-3-iv
        # angle: criterion
        """The restyle plus K new code lines (nothing out): refused, K added, and the file is
        required to stand at its previous length minus K (or the limit if that is less demanding)."""
        line_js, _ = content.build_text(".js", 40, 4, "line")
        block_js, _ = content.build_text(".js", 40, 4, "block")
        for extra in (3, 5):
            staged = block_js + "".join(f"const extra_{i} = {i};\n" for i in range(extra))
            result, output, numbers = _scenario("big.js", line_js, staged)
            self.assertEqual(1, result.returncode, msg=f"K={extra}: must be refused. Got: {output!r}")
            self.assertEqual(extra, numbers["added"], msg=f"K={extra}: states K added. Got: {output!r}")
            self.assertEqual(max(_LIMIT, 40 - extra), numbers["required"], msg=f"K={extra}: required. {output!r}")

    def test_ge_127d_3_iv_restyling_a_trailing_comment_on_a_code_line_adds_zero(self):
        # covers: GE-127d-3-iv
        # angle: boundary
        """On an over-limit .js and .sql file, T trailing comments rewritten from line form to
        block form state 0 added and pass; changing the code on one of those lines states 1."""
        shapes = {
            ".js": ("const v{i} = {i}; // n{i}", "const v{i} = {i}; /* n{i} */", "const v0 = 999; /* n0 */"),
            ".sql": ("SELECT {i}; -- n{i}", "SELECT {i}; /* n{i} */", "SELECT 999; /* n0 */"),
        }
        for ext, (line_form, block_form, changed_first) in shapes.items():
            for trailing in (2, 5):
                def build(form: str) -> str:
                    rows = [form.format(i=i) if i < trailing else form.split(";")[0].format(i=i) + ";" for i in range(45)]
                    return "\n".join(rows) + "\n"
                head, restyled = build(line_form), build(block_form)
                result, output, numbers = _scenario(f"tail{ext}", head, restyled)
                self.assertEqual((0, 0), (result.returncode, numbers["added"]), msg=f"{ext} T={trailing}: {output!r}")
                changed = "\n".join([changed_first, *restyled.splitlines()[1:]]) + "\n"
                result, output, numbers = _scenario(f"tail{ext}", head, changed)
                self.assertEqual(1, numbers["added"], msg=f"{ext} T={trailing}: one code change adds 1. {output!r}")


if __name__ == "__main__":
    unittest.main()
