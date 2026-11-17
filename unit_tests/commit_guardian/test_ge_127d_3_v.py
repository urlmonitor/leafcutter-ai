"""
MODULE: unit_tests/commit_guardian/test_ge_127d_3_v.py
COVERS: GE-127d-3-v -- a line holding several statements counts once per
    statement, so joining statements onto fewer lines moves neither the
    measured length nor the two-for-one repayment.

DECISION HISTORY
- 2026-10-23 [GE-127d-3-v]: Initial authoring.
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

# Runs in a fresh interpreter: another test in the same worker may already hold a
# different copy of _file_size_measure in sys.modules.
_PROBE = """
import json, sys
sys.path.insert(0, sys.argv[1])
from _file_size_measure import counted_line_keys
from _file_size_measure.rule_statement import describe
import _file_size_ratchet as ratchet
cases = json.loads(sys.argv[2])
per_line = lambda content, ext: len([l for l in content.splitlines() if l.strip()])
print(json.dumps({
    "keys": [[counted_line_keys(text, ext) for text in texts] for ext, texts in cases],
    "rule": describe(ratchet.count_content_lines),
    "per_line_rule": describe(per_line),
}))
"""


def _fresh(cases: list[tuple[str, list[str]]]) -> dict:
    """Counted keys for *cases* and the generated rules, from a fresh interpreter."""
    result = subprocess.run(
        [sys.executable, "-c", _PROBE, str(fx.GUARDIAN_SRC), json.dumps(cases)],
        capture_output=True, text=True, timeout=120, check=False,
    )
    if result.returncode != 0:
        message = f"probe failed: {result.stderr!r}"
        raise AssertionError(message)
    return json.loads(result.stdout)

# (extension, joined form, the same statements one per line)
_JOINS = (
    (".py", "x = 1; y = 2; z = 3\n", "x = 1\ny = 2\nz = 3\n"),
    (".py", "def f():\n    a = 1; b = 2; return a + b\n", "def f():\n    a = 1\n    b = 2\n    return a + b\n"),
    (".py", "if ready: start()\n", "if ready:\n    start()\n"),
    (".py", "for item in items: handle(item)\n", "for item in items:\n    handle(item)\n"),
    (".py", "class Stub: pass\n", "class Stub:\n    pass\n"),
    (".js", "a(); b(); c();\n", "a();\nb();\nc();\n"),
    (".js", "function f() {\n  const x = 1; const y = 2; return x + y;\n}\n",
     "function f() {\n  const x = 1;\n  const y = 2;\n  return x + y;\n}\n"),
    (".js", "xs.forEach((x) => { a(x); b(x); });\n", "xs.forEach((x) => {\n  a(x);\n  b(x);\n});\n"),
    (".ts", "let a = 1; let b = 2;\n", "let a = 1;\nlet b = 2;\n"),
    (".tsx", "const a = 1; const b = 2;\n", "const a = 1;\nconst b = 2;\n"),
)

# (extension, text, its measured length): a ';' or ':' that separates no statements
_NOT_SPLIT = (
    (".py", "f = lambda: 1\n", 1),
    (".py", "x: int = 1\n", 1),
    (".py", "d = {1: 2}\ns = a[1:2]\n", 2),
    (".py", "x = 1  # a; b\n", 1),
    (".py", "s = 'a; b'\n", 1),
    (".py", 'def f(): "doc"\n', 1),
    (".py", "if x:\n    y = 1\n", 2),
    (".js", "for (let i = 0; i < 3; i++) f(i);\n", 1),
    (".js", "const s = 'a; b'; \n", 1),
    (".js", "a(); // x; y\n", 1),
    (".js", "const t = `a; ${b}; c`;\n", 1),
    (".js", "x = 1;\n", 1),
    (".sql", "SELECT ';' FROM t;\n", 1),
    (".sh", "echo 'a; b'\n", 1),
)


def _code(ext: str, count: int) -> str:
    """*count* distinct one-statement lines of code in *ext*."""
    line = "value_{0} = {0}\n" if ext == ".py" else "const value_{0} = {0};\n"
    return "".join(line.format(i) for i in range(count))


class TestJoinedStatementsMeasureAsIfOnTheirOwnLines(unittest.TestCase):
    def test_ge_127d_3_v_joined_statements_measure_as_if_each_stood_on_its_own_line(self):
        # covers: GE-127d-3-v
        # angle: discrimination
        """Each joined form measures exactly what the one-per-line form measures,
        and fewer physical lines than it measures (so a line count could not)."""
        items = [(ext, text) for ext, joined, split in _JOINS for text in (joined, split)]
        measured = fx.measure_texts(items)
        for index, (ext, joined, split) in enumerate(_JOINS):
            as_joined, as_split = measured[2 * index], measured[2 * index + 1]
            self.assertEqual(as_split, as_joined, msg=f"{ext}: joining moved the length: {joined!r}")
            self.assertGreater(as_joined, len(joined.splitlines()), msg=f"{ext}: counted lines, not statements")

    def test_ge_127d_3_v_a_separator_that_separates_no_statements_does_not_split_a_line(self):
        # covers: GE-127d-3-v
        # angle: boundary
        """A ``for (;;)`` header, a ``;`` in a string, template literal or comment, a
        lambda's or annotation's ``:``, a docstring on its header line, and a ``;``
        inside a SQL or shell string each measure exactly their code lines (SQL and
        shell splitting itself is GE-127d-3-vi's)."""
        measured = fx.measure_texts([(ext, text) for ext, text, _ in _NOT_SPLIT])
        for (ext, text, expected), got in zip(_NOT_SPLIT, measured, strict=True):
            self.assertEqual(expected, got, msg=f"{ext}: {text!r}")

    def test_ge_127d_3_v_semicolon_joins_key_exactly_like_the_split_form(self):
        # covers: GE-127d-3-v
        # angle: criterion
        """The counted-line keys the added-lines diff compares are identical for a
        ``;`` join and its one-per-line form, in Python and JavaScript."""
        semicolon_joins = [case for case in _JOINS if ";" in case[1].replace(";\n", "\n")]
        self.assertGreaterEqual(len(semicolon_joins), 5)
        keys = _fresh([(ext, [joined, split]) for ext, joined, split in semicolon_joins])["keys"]
        for (_ext, joined, _split), (as_joined, as_split) in zip(semicolon_joins, keys, strict=True):
            self.assertEqual(as_split, as_joined, msg=joined)


class TestJoinOnlyChangeThroughTheGate(unittest.TestCase):
    def _gate(self, rel: str, head: str, staged: str) -> tuple[int, dict[str, int | None], str]:
        with tempfile.TemporaryDirectory() as tmp:
            result, outcome = fx.change_outcome(Path(tmp), rel, head, staged, limit=30)
        return result.returncode, fx.outcome_numbers(outcome), outcome

    def test_ge_127d_3_v_a_join_only_change_on_an_over_limit_file_adds_zero_and_keeps_its_length(self):
        # covers: GE-127d-3-v
        # angle: criterion
        """On an over-limit .py and .js file, joining J statement pairs with ``;`` and
        the reverse each complete, state 0 added and quote equal lengths."""
        for ext, joiner in ((".py", "; "), (".js", " ")):
            split = _code(ext, 40)
            lines = split.splitlines()
            for pairs in (1, 5):
                joined_lines = [joiner.join(lines[2 * i : 2 * i + 2]) for i in range(pairs)] + lines[2 * pairs :]
                joined = "\n".join(joined_lines) + "\n"
                for head, staged in ((split, joined), (joined, split)):
                    code, numbers, outcome = self._gate(f"big{ext}", head, staged)
                    self.assertEqual(0, code, msg=f"{ext} J={pairs}: must complete. {outcome!r}")
                    self.assertEqual(numbers["previous"], numbers["new"], msg=f"{ext}: length moved. {outcome!r}")
                    self.assertEqual(0, numbers["added"], msg=f"{ext}: a join is not added code. {outcome!r}")

    def test_ge_127d_3_v_a_join_does_not_hide_code_added_in_the_same_change(self):
        # covers: GE-127d-3-v
        # angle: criterion
        """A join plus K new statements written on the joined lines states K added
        and is refused on a file already over its limit."""
        split = _code(".js", 40)
        lines = split.splitlines()
        for extra in (1, 3):
            added = " ".join(f"const extra_{i} = {i};" for i in range(extra))
            staged = "\n".join([f"{lines[0]} {lines[1]} {added}", *lines[2:]]) + "\n"
            code, numbers, outcome = self._gate("big.js", split, staged)
            self.assertEqual(extra, numbers["added"], msg=f"K={extra}: {outcome!r}")
            self.assertNotEqual(0, code, msg=f"K={extra}: growth on an over-limit file must be refused. {outcome!r}")


class TestPublishedRuleNamesThePerStatementCount(unittest.TestCase):
    def test_ge_127d_3_v_the_published_rule_states_the_per_statement_count_only_while_it_holds(self):
        # covers: GE-127d-3-v
        # angle: seam
        """The generated rule names the per-statement count for the languages where
        the measure applies it, and drops the clause under a measure that counts
        physical lines (so the published rule cannot outlive the behaviour)."""
        rules = _fresh([])
        # The language list grows as lexers learn to split (GE-127d-3-vi added SQL and shell).
        self.assertIn("once per statement (Python, JavaScript, TypeScript", rules["rule"])
        self.assertNotIn("once per statement", rules["per_line_rule"])


if __name__ == "__main__":
    unittest.main()
