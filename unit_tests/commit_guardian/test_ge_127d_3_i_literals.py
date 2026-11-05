"""
MODULE: unit_tests/commit_guardian/test_ge_127d_3_i_literals.py
COVERS: GE-127d-3-i -- marker sequences inside literals are counted, in every
    covered language (the KI glob repro, literals, regex vs division, JSX text).

DECISION HISTORY
- 2026-10-20 [GE-127d-3-i/test-writer]: Initial authoring.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ge_127d_3_content as content  # noqa: E402
import _ge_127d_3_fixture as fx  # noqa: E402


class TestLiteralsAreNotComments(unittest.TestCase):
    def test_ge_127d_3_i_the_ki_glob_repro_measures_seven_not_two(self):
        # covers: GE-127d-3-i
        # angle: discrimination
        """The 2026-10-09 KI's 8-line JavaScript file measures 7 (the incumbent
        returns 2); deleting the glob line reads as a one-line shrink (6)."""
        lines = [
            "const a = 1;", 'const glob = "templates/**/*.js";', "const b = 2;", "const c = 3;",
            "const d = 4;", "const e = 5;", "/* a real comment */", "const f = 6;",
        ]
        text = "\n".join(lines) + "\n"
        without_glob = "\n".join([lines[0], *lines[2:]]) + "\n"
        template_literal = text.replace('"templates/**/*.js"', "`templates/**/*.js`")
        single_quoted = text.replace('"templates/**/*.js"', "'templates/**/*.js'")
        # The KI's own glob opens ``/*`` without closing it on its line (the AC's ``/**/`` closes
        # itself and cannot swallow a later line), so the incumbent reads it as a 6-line span.
        ki_glob = "scripts/commit_guardian/*.py"
        ki_variants = [text.replace("templates/**/*.js", ki_glob), template_literal.replace("templates/**/*.js", ki_glob),
                       single_quoted.replace("templates/**/*.js", ki_glob)]
        measured = fx.measure_texts([(".js", t) for t in (text, without_glob, template_literal, single_quoted, *ki_variants)])
        self.assertEqual([7, 6, 7, 7, 7, 7, 7], measured, msg="a glob in any string literal opens nothing")

    def test_ge_127d_3_i_markers_inside_literals_are_counted_in_every_covered_language(self):
        # covers: GE-127d-3-i
        # angle: criterion
        """One generated file per covered extension carrying the criteria's marker
        sequences inside literals plus genuine comments, N and M varied: each
        measures exactly its code-line count; no marker swallows a later line."""
        items, wanted = [], []
        for ext, rows in content.LITERAL_CASES.items():
            for repeat in (1, 3):
                for pad in (2, 5):
                    text, expected = content.corpus_text(rows, repeat, pad, ext)
                    items.append((ext, text))
                    wanted.append((ext, repeat, pad, expected))
        measured = fx.measure_texts(items)
        wrong = [(ext, rep, pad, got, want) for (ext, rep, pad, want), got in zip(wanted, measured) if got != want]
        self.assertEqual([], wrong, msg="every literal-carried marker line must count; every genuine comment must not")

    def test_ge_127d_3_i_regex_literals_and_division_are_told_apart(self):
        # covers: GE-127d-3-i
        # angle: discrimination
        """A JS corpus where a misread flips the count: regex literals holding
        ``/*`` or a quote, regex after an if-header ``)``, and genuine division."""
        items, wanted = [], []
        for ext in (".js", ".mjs", ".ts"):
            for repeat in (1, 3):
                for pad in (0, 4):
                    text, expected = content.corpus_text(content.REGEX_DIVISION_JS, repeat, pad, ext)
                    items.append((ext, text))
                    wanted.append((ext, repeat, pad, expected))
        measured = fx.measure_texts(items)
        wrong = [(ext, rep, pad, got, want) for (ext, rep, pad, want), got in zip(wanted, measured) if got != want]
        self.assertEqual([], wrong, msg="a regex/division misread must never change the measured length")

    def test_ge_127d_3_i_jsx_text_is_text_not_a_string_or_a_comment(self):
        # covers: GE-127d-3-i
        # angle: boundary
        """JSX text with an apostrophe, a double quote, ``//`` and ``/*`` counts line by
        line; the standalone ``{/* */}`` container line does not; ``<T>expr`` in a
        .ts file is a type assertion, not JSX."""
        items, wanted = [], []
        for ext in (".tsx", ".js"):
            for repeat in (1, 2):
                text, expected = content.corpus_text(content.JSX_LINES, repeat, 2, ext)
                items.append((ext, text))
                wanted.append((ext, repeat, expected))
        text, expected = content.corpus_text(content.TS_ASSERTION_LINES, 2, 2, ".ts")
        items.append((".ts", text))
        wanted.append((".ts", 2, expected))
        measured = fx.measure_texts(items)
        wrong = [(ext, rep, got, want) for (ext, rep, want), got in zip(wanted, measured) if got != want]
        self.assertEqual([], wrong, msg="JSX text lines count; only the {/* */} container line is uncounted")


if __name__ == "__main__":
    unittest.main()
