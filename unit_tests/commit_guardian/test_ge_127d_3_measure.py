"""
MODULE: unit_tests/commit_guardian/test_ge_127d_3_measure.py
COVERS: GE-127d-3 -- the four measure-level descriptors (criterion, two boundary,
    discrimination). Every file is generated, written to disk and passed through
    the shared measure the hook calls; no total is hard-coded.

DECISION HISTORY
- 2026-10-20 [GE-127d-3/test-writer]: Initial authoring.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ge_127d_3_content as content  # noqa: E402
import _ge_127d_3_fixture as fx  # noqa: E402


class TestMeasureIsStyleIndependent(unittest.TestCase):
    def test_ge_127d_3_the_same_comment_text_measures_identically_in_every_style_and_language(self):
        # covers: GE-127d-3
        # angle: criterion
        """N code lines + K comment lines measure N for every style of every
        covered extension (and module/class/function docstrings for .py)."""
        cases, items = [], []
        for ext in content.EXTENSIONS:
            for style in content.styles_for(ext):
                for n in (2, 37):
                    for k in (1, 4, 40):
                        text, expected = content.build_text(ext, n, k, style)
                        items.append((ext, text))
                        cases.append((ext, style, n, k, expected))
        for position in ("module", "class", "function"):
            for k in (1, 4, 40):
                items.append((".py", content.py_positioned(position, "string", k)))
                items.append((".py", content.py_positioned(position, "none", k)))
                cases.append((".py", f"{position}-docstring", 0, k, None))
        measured = fx.measure_texts(items)
        wrong = []
        index = 0
        for ext, style, n, k, expected in cases:
            if expected is None:
                with_string, without = measured[index], measured[index + 1]
                index += 2
                if with_string != without:
                    wrong.append((ext, style, k, with_string, without))
            else:
                if measured[index] != expected:
                    wrong.append((ext, style, n, k, measured[index], expected))
                index += 1
        self.assertEqual([], wrong, msg="the measured length must move with code, never with comment style")


_USED_MULTILINE = {
    ".py": 'TEXT = """\nfirst\n\nsecond\n"""\n',
    ".js": "const t = `\nfirst\n\nsecond\n`;\n",
    ".mjs": "const t = `\nfirst\n\nsecond\n`;\n",
    ".ts": "const t = `\nfirst\n\nsecond\n`;\n",
    ".tsx": "const t = `\nfirst\n\nsecond\n`;\n",
    ".sql": "SELECT $$\nfirst\n\nsecond\n$$;\n",
    ".sh": "cat <<EOF\nfirst\n\nsecond\nEOF\n",
}


class TestBlankLinesAndEndings(unittest.TestCase):
    def test_ge_127d_3_blank_lines_count_outside_comments_and_not_inside_them(self):
        # covers: GE-127d-3
        # angle: boundary
        """Name kept from the 2026-10-16 rule; the claim is now the 2026-10-21 one:
        B blank lines outside comments add 0 (as do C blanks inside a block comment
        or docstring); a trailing comment on code counts once; CRLF and a missing
        final newline measure the same."""
        items, expected = [], []
        for ext, style in ((".py", "docstring"), (".js", "block"), (".sql", "block"), (".ts", "block")):
            for blanks in (0, 3):
                for inside in (0, 2, 5):
                    text, want = content.build_text(ext, 6, 4, style, blanks=blanks, blanks_in_comment=inside)
                    for variant in (text, text.replace("\n", "\r\n"), text.rstrip("\n")):
                        items.append((ext, variant))
                        expected.append(want)
        for ext, trailing in ((".js", "const t = 1; // note"), (".sql", "SELECT 1; -- note"), (".py", "t = 1  # note")):
            text, want = content.build_text(ext, 4, 2, "line")
            items.append((ext, text + trailing + "\n"))
            expected.append(want + 1)
        measured = fx.measure_texts(items)
        wrong = [(i, m, e) for i, (m, e) in enumerate(zip(measured, expected)) if m != e]
        self.assertEqual([], wrong, msg="blank lines add 0 outside and inside comments; CRLF/no-EOL never matter")

    def test_ge_127d_3_blank_lines_never_count_anywhere(self):
        # covers: GE-127d-3
        # angle: boundary
        """N code lines measure N whatever B (between code), C (between two
        line-comment paragraphs), D (inside a block comment or standalone string)
        and E (inside a used multi-line string, template literal, here-document or
        dollar-quoted body) blank lines are added, as empty or whitespace-only
        lines, in LF and CRLF."""
        items, expected, labels = [], [], []
        for ext in content.EXTENSIONS:
            for style in content.styles_for(ext):
                for blanks, inside in ((0, 0), (3, 0), (0, 4), (5, 2)):
                    if inside and style not in ("block", "docstring"):
                        continue
                    text, want = content.build_text(ext, 6, 4, style, blanks=blanks, blanks_in_comment=inside)
                    padded = text.replace("\n\n", "\n \t \n\n\t\n")
                    for tag, variant in (("lf", text), ("ws", padded), ("crlf", text.replace("\n", "\r\n"))):
                        items.append((ext, variant))
                        expected.append(want)
                        labels.append((ext, style, blanks, inside, tag))
            prefix = {".py": "# ", ".sh": "# ", ".sql": "-- "}.get(ext, "// ")
            paragraphs = f"{prefix}a\n\n\n{prefix}b\n" + content.code_line(ext, 0) + "\n"
            items.append((ext, paragraphs))
            expected.append(1)
            labels.append((ext, "paragraphs", 0, 0, "lf"))
            used = _USED_MULTILINE[ext]
            plain = used.replace("\n\n", "\n")
            items.extend([(ext, used), (ext, plain), (ext, used.replace("\n\n", "\n  \n\t\n\n"))])
            expected.extend([None, None, None])
            labels.extend([(ext, "used", 0, 0, "blank"), (ext, "used", 0, 0, "plain"), (ext, "used", 0, 0, "ws")])
        measured = fx.measure_texts(items)
        wrong = [(labels[i], m, e) for i, (m, e) in enumerate(zip(measured, expected)) if e is not None and m != e]
        used_cases = [i for i, e in enumerate(expected) if e is None]
        for first in used_cases[0::3]:
            if not (measured[first] == measured[first + 1] == measured[first + 2]):
                wrong.append((labels[first], measured[first : first + 3], "blank lines inside a used body must add 0"))
        self.assertEqual([], wrong, msg="a line counts only if it holds a code token")

    def test_ge_127d_3_the_reviewers_paragraph_restyle_repros_measure_equal(self):
        # covers: GE-127d-3
        # angle: discrimination
        """The pr-reviewer's repros byte for byte: `// a\\n\\n// b\\nx();\\n` and
        `/* a\\n\\n b */\\nx();\\n` (.js), `# a\\n\\n# b\\nx=1\\n` and
        `\"\"\"a\\n\\nb\"\"\"\\nx=1\\n` (.py) each measure 1."""
        pairs = [
            (".js", "// a\n\n// b\nx();\n", "/* a\n\n b */\nx();\n"),
            (".py", "# a\n\n# b\nx=1\n", '"""a\n\nb"""\nx=1\n'),
        ]
        items = [(ext, text) for ext, first, second in pairs for text in (first, second)]
        measured = fx.measure_texts(items)
        self.assertEqual([1, 1, 1, 1], measured, msg="paragraph-to-block restyles must be measure-neutral")
        # Through the hook: the same restyle on an over-limit file quotes one length and adds 0 lines.
        for ext, first, second in pairs:
            filler = "".join(f"{content.code_line(ext, i)}\n" for i in range(40))
            with tempfile.TemporaryDirectory() as tmp:
                result, output = fx.change_outcome(Path(tmp), f"big{ext}", first + filler, second + filler, limit=30)
            numbers = fx.outcome_numbers(output)
            self.assertEqual(0, result.returncode, msg=f"{ext}: a paragraph-to-block restyle must complete. {output!r}")
            self.assertEqual(numbers["previous"], numbers["new"], msg=f"{ext}: quoted length moved. {output!r}")
            self.assertEqual(0, numbers["added"], msg=f"{ext}: must state 0 lines added. {output!r}")

    def test_ge_127d_3_a_standalone_python_string_is_uncounted_wherever_it_stands(self):
        # covers: GE-127d-3
        # angle: boundary
        """An S-line string standing alone adds 0 as module/class/function
        docstring, bare mid-module, bare after the first statement, trailing."""
        items = []
        for position in ("module", "class", "function", "between", "trailing"):
            for s_lines in (1, 4, 25):
                for quote in ('"""', "'''"):
                    items.append(content.py_positioned(position, "string", s_lines).replace('"""', quote))
                    items.append(content.py_positioned(position, "none", s_lines))
        for position in ("module", "class", "function", "between", "trailing"):
            single = content.py_positioned(position, "string", 1)
            for quote in ('"', "'"):
                items.append(single.replace('"""slot text 0"""', f"{quote}slot text 0{quote}"))
                items.append(content.py_positioned(position, "none", 1))
        after_first = "def go():\n    first = 1\n" + '    """bare\n    string\n    here"""\n' + "    return first\n"
        items += [after_first, "def go():\n    first = 1\n    return first\n"]
        items += ['VALUE = 1\n"""\nDECISION HISTORY\n- entry one\n- entry two\n"""\n', "VALUE = 1\n"]
        measured = fx.measure_texts([(".py", text) for text in items])
        pairs = list(zip(measured[0::2], measured[1::2]))
        self.assertEqual([], [(i, a, b) for i, (a, b) in enumerate(pairs) if a != b], msg="standalone strings add 0")

    def test_ge_127d_3_the_same_python_string_counts_once_it_is_used(self):
        # covers: GE-127d-3
        # angle: discrimination
        """The same text assigned / passed / returned / joined, or a standalone
        f-string, adds exactly the lines it occupies (all counted)."""
        problems = []
        for kind in ("assigned", "argument", "returned", "joined", "fstring"):
            for s_lines in (2, 6):
                base, with_string = content.python_with_string_forms(kind, s_lines)
                want_delta = fx.plain_line_count(with_string) - fx.plain_line_count(base)
                oracle_delta = content.independent_python_length(with_string) - content.independent_python_length(base)
                got_base, got_with = fx.measure_texts([(".py", base), (".py", with_string)])
                if oracle_delta != want_delta or got_with - got_base != want_delta:
                    problems.append((kind, s_lines, want_delta, oracle_delta, got_with, got_base))
        self.assertEqual([], problems, msg="a used string (or standalone f-string) is code; every line counts")


if __name__ == "__main__":
    unittest.main()
