"""
MODULE: unit_tests/commit_guardian/test_ge_127d_3_vi.py
COVERS: GE-127d-3-vi -- one-line blocks, SQL and shell statements are counted as
    their expanded forms, and a joined statement is keyed as it would stand on
    its own line.

DECISION HISTORY
- 2026-10-25 [GE-127d-3-vi]: Initial authoring.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ge_127d_3_fixture as fx  # noqa: E402

# (extension, joined form, the same code expanded one statement / brace per line)
_JOINS = (
    (".py", "if ready: start()\n", "if ready:\n    start()\n"),
    (".py", "for x in xs: a(x); b(x)\n", "for x in xs:\n    a(x)\n    b(x)\n"),
    (".py", "def f():\n    if x: return 1\n", "def f():\n    if x:\n        return 1\n"),
    (".js", "if (x) { a(); b(); }\n", "if (x) {\n  a();\n  b();\n}\n"),
    (".js", "function f() { return 1; }\n", "function f() {\n  return 1;\n}\n"),
    (".js", "  if (x) { a(); } else { b(); }\n", "  if (x) {\n    a();\n  } else {\n    b();\n  }\n"),
    (".js", "xs.forEach((x) => { a(x); b(x); });\n", "xs.forEach((x) => {\n  a(x);\n  b(x);\n});\n"),
    (".ts", "type T = { a: string; b: number };\n", "type T = {\n  a: string;\n  b: number\n};\n"),
    (".ts", "function f(): number { return 1; }\n", "function f(): number {\n  return 1;\n}\n"),
    (".tsx", "const f = () => { a(); b(); };\n", "const f = () => {\n  a();\n  b();\n};\n"),
    (".sql", "SELECT 1; SELECT 2;\n", "SELECT 1;\nSELECT 2;\n"),
    (".sql", "CREATE FUNCTION f() AS $$ BEGIN a; b; END $$;\n", "CREATE FUNCTION f() AS $$ BEGIN a;\nb;\nEND $$;\n"),
    (".sh", "a; b\n", "a\nb\n"),
    (".sh", "if x; then y; fi\n", "if x; then\n  y\nfi\n"),
    (".sh", "for i in 1 2; do echo $i; done\n", "for i in 1 2; do\n  echo $i\ndone\n"),
    (".sh", "if x; then a; else b; fi\n", "if x; then\n  a\nelse\n  b\nfi\n"),
)

# (extension, text, its measured length): braces, separators and keywords that split nothing
_NOT_SPLIT = (
    (".js", "const o = { a: 1, b: 2 };\n", 1),
    (".js", "const { a, b } = o;\n", 1),
    (".js", "if (x) {}\n", 1),
    (".js", "const s = '{ a; b }';\n", 1),
    (".js", "for (let i = 0; i < 3; i++) f(i);\n", 1),
    (".sql", "SELECT ';' FROM t;\n", 1),
    (".sql", 'SELECT "a;b" FROM t;\n', 1),
    (".sql", "SELECT 1; -- note; here\n", 1),
    (".sh", "a && b || c\n", 1),
    (".sh", "echo 'a; b'\n", 1),
    (".sh", "x=$(a; b)\n", 1),
    (".sh", "echo do it\n", 1),
)

_PROBE = """
import json, sys
sys.path.insert(0, sys.argv[1])
from _file_size_measure import counted_line_keys
from _file_size_measure.rule_statement import describe
import _file_size_ratchet as ratchet
cases = json.loads(sys.argv[2])
print(json.dumps({
    "keys": [[counted_line_keys(text, ext) for text in texts] for ext, texts in cases],
    "rule": describe(ratchet.count_content_lines),
}))
"""


def _fresh(cases: list[tuple[str, list[str]]]) -> dict:
    """Counted keys for *cases* and the generated rule, from a fresh interpreter."""
    result = subprocess.run(
        [sys.executable, "-c", _PROBE, str(fx.GUARDIAN_SRC), json.dumps(cases)],
        capture_output=True, text=True, timeout=120, check=False,
    )
    if result.returncode != 0:
        message = f"probe failed: {result.stderr!r}"
        raise AssertionError(message)
    return json.loads(result.stdout)


# Per language: one expanded block, and the same block written on one line.
_BLOCKS = {
    ".py": ("if c_{0}:\n    v_{0} = {0}\n", "if c_{0}: v_{0} = {0}\n"),
    ".js": ("if (c{0}) {{\n  v({0});\n}}\n", "if (c{0}) {{ v({0}); }}\n"),
    ".sql": ("SELECT {0};\nSELECT -{0};\n", "SELECT {0}; SELECT -{0};\n"),
    ".sh": ("if c{0}; then\n  v {0}\nfi\n", "if c{0}; then v {0}; fi\n"),
}


def _file(ext: str, joined: int, blocks: int = 20) -> str:
    """*blocks* blocks of *ext*, the first *joined* of them written on one line."""
    expanded, one_line = _BLOCKS[ext]
    return "".join((one_line if i < joined else expanded).format(i) for i in range(blocks))


class TestOneLineFormsMeasureAndKeyLikeTheirExpandedForms(unittest.TestCase):
    def test_ge_127d_3_vi_one_line_blocks_measure_and_key_like_their_expanded_forms(self):
        # covers: GE-127d-3-vi
        # angle: discrimination
        """Every joined form measures exactly its expanded form, and keys exactly like it."""
        items = [(ext, text) for ext, joined, split in _JOINS for text in (joined, split)]
        measured = fx.measure_texts(items)
        keys = _fresh([(ext, [joined, split]) for ext, joined, split in _JOINS])["keys"]
        for index, (ext, joined, _split) in enumerate(_JOINS):
            self.assertEqual(measured[2 * index + 1], measured[2 * index], msg=f"{ext}: length moved: {joined!r}")
            as_joined, as_split = keys[index]
            self.assertEqual(as_split, as_joined, msg=f"{ext}: keys differ: {joined!r}")

    def test_ge_127d_3_vi_object_literals_strings_and_argument_keywords_do_not_split(self):
        # covers: GE-127d-3-vi
        # angle: boundary
        """Object literals, destructuring, empty blocks, separators in strings and comments,
        shell lists, substitutions and keywords used as arguments measure their code lines."""
        measured = fx.measure_texts([(ext, text) for ext, text, _ in _NOT_SPLIT])
        for (ext, text, expected), got in zip(_NOT_SPLIT, measured, strict=True):
            self.assertEqual(expected, got, msg=f"{ext}: {text!r}")


class TestJoiningOnAnOverLimitFileAddsZero(unittest.TestCase):
    def test_ge_127d_3_vi_joining_or_splitting_blocks_on_an_over_limit_file_adds_zero(self):
        # covers: GE-127d-3-vi
        # angle: criterion
        """Writing J blocks on one line, and the reverse, on over-limit .py, .js, .sql and
        .sh files completes, states 0 added and quotes equal lengths."""
        for ext in _BLOCKS:
            for joined in (1, 6):
                expanded, one_line = _file(ext, 0), _file(ext, joined)
                for head, staged in ((expanded, one_line), (one_line, expanded)):
                    with tempfile.TemporaryDirectory() as tmp:
                        result, outcome = fx.change_outcome(Path(tmp), f"big{ext}", head, staged, limit=30)
                    numbers = fx.outcome_numbers(outcome)
                    self.assertEqual(0, result.returncode, msg=f"{ext} J={joined}: must complete. {outcome!r}")
                    self.assertEqual(numbers["previous"], numbers["new"], msg=f"{ext}: length moved. {outcome!r}")
                    self.assertEqual(0, numbers["added"], msg=f"{ext}: a join is not added code. {outcome!r}")


class TestPublishedRuleNamesSqlAndShell(unittest.TestCase):
    def test_ge_127d_3_vi_the_published_rule_names_sql_and_shell(self):
        # covers: GE-127d-3-vi
        # angle: seam
        """The generated per-statement clause names all five languages."""
        rule = _fresh([])["rule"]
        self.assertIn("once per statement (Python, JavaScript, TypeScript, SQL and shell)", rule)


if __name__ == "__main__":
    unittest.main()
