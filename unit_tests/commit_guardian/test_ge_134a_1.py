"""
MODULE: unit_tests/commit_guardian/test_ge_134a_1.py
COVERS: GE-134a-1 -- "A file's decision-history block is left out of its
    measured length, in every covered language, and nothing else changes"

GOAL: The six test_spec descriptors of GE-134a-1, built exactly as the test
    design lists them. Shared builders, loaders and the independent counter
    live in _ge_134a_fixture.py (see its docstring for the pinned name of the
    prefix constant, DECISION_HISTORY_COMMENT_PREFIXES).

RED TODAY: count_content_lines counts every '#', '//' and '--' comment line,
    so a line-comment DECISION HISTORY block adds its own lines to the
    measured length. The two "measures as before" descriptors are
    preservation guards and are expected to hold before and after the
    change; the docstring/block-comment descriptor carries a control row
    (the same block as line comments) that is red today.

DECISION HISTORY
- 2026-10-21 [test-writer/GE-134a-1]: Initial authoring.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ge_127d_2_fixture as d2  # noqa: E402
import _ge_134a_fixture as fx  # noqa: E402

_SHIPPED_EXTENSIONS = json.loads(fx.SHIPPED_CONFIG.read_text(encoding="utf-8"))["file_size"]["checked_extensions"]


@pytest.fixture()
def ratchet():
    return fx.load_ratchet()


def test_ge_134a_1_python_and_javascript_history_blocks_are_not_measured(ratchet, tmp_path):
    # covers: GE-134a-1
    # angle: criterion
    """The 80-line Python file with its 25-line ruled '#' block and the 120-line
    JavaScript file with its 15-line unruled '//' header block: the history block adds
    nothing. Under GE-127d-3 (2026-10-21, supersedes GE-134a) ordinary comments and blank
    lines do not count either, so the lengths are the code-line counts: 64 and 96."""
    python_text = fx.python_example()
    javascript_text = fx.javascript_example()
    assert fx.pre_change_count(python_text) == 105
    assert fx.pre_change_count(javascript_text) == 135
    assert fx.independent_count(python_text) == 64
    assert fx.line_rule_count(javascript_text) == 96

    assert fx.measure_text(ratchet, tmp_path, "example.py", python_text) == 64
    assert fx.measure_text(ratchet, tmp_path, "example.js", javascript_text) == 96
    assert fx.measure_text(ratchet, tmp_path, "body_only.py", "\n".join(fx.body_lines(80, "#")) + "\n") == 64


def test_ge_134a_1_history_block_is_left_out_of_the_length_the_size_check_quotes(tmp_path):
    # covers: GE-134a-1
    # angle: reachability
    """Through the fixture copy of check_file_size.py: under a limit equal to the
    example's independently derived length (64) the Python example passes, listed at 64
    lines; one more code line is refused quoting Lines: 65."""
    at_limit = fx.independent_count(fx.python_example())
    assert at_limit == 64
    at_limit_root = tmp_path / "at_limit"
    at_limit_root.mkdir()
    d2.build_fixture_tree(at_limit_root, line_limit=at_limit, checked_extensions=[".py"])
    result = fx.stage_and_check(at_limit_root, "src/example.py", fx.python_example())
    output = d2.combined_output(result)
    assert result.returncode == 0, output
    assert f"src/example.py (new, {at_limit} lines - OK)" in output

    over_root = tmp_path / "over"
    over_root.mkdir()
    d2.build_fixture_tree(over_root, line_limit=at_limit, checked_extensions=[".py"])
    result = fx.stage_and_check(over_root, "src/example.py", fx.python_example(extra_code_lines=1))
    output = d2.combined_output(result)
    assert result.returncode == 1, output
    assert d2.parse_lines_and_limit(output) == (at_limit + 1, at_limit), output


@pytest.mark.parametrize("extension", _SHIPPED_EXTENSIONS)
def test_ge_134a_1_line_comment_block_is_left_out_in_every_covered_language(extension, ratchet, tmp_path):
    # covers: GE-134a-1
    # angle: discrimination
    """For every shipped checked extension: the body's code lines plus a block headed
    '<prefix> DECISION HISTORY' measure just the code lines (the 10-line body holds 8
    code lines, one ordinary comment and one blank, neither of which counts under
    GE-127d-3's 2026-10-21 rule, and the block adds nothing); a heading followed by
    comment lines of ANOTHER prefix is not special either -- the measure has no
    DECISION_HISTORY_COMMENT_PREFIXES constant any more, each language's own lexer
    decides what a comment is."""
    assert extension in fx.PREFIX_BY_EXTENSION, f"no line-comment prefix known for shipped {extension}"
    prefix = fx.PREFIX_BY_EXTENSION[extension]
    body = fx.body_lines(10, prefix, "value_{i} = {i}")
    block = [f"{prefix} DECISION HISTORY", *fx.history_entries(prefix, 4)]
    content = "\n".join([*body, *block]) + "\n"
    code_lines = fx.line_rule_count("\n".join(body) + "\n")
    assert code_lines == 8
    assert fx.measure_text(ratchet, tmp_path, f"sample{extension}", content) == code_lines
    assert fx.measure_text(ratchet, tmp_path, f"nohistory{extension}", "\n".join(body) + "\n") == code_lines


def test_ge_134a_1_lines_outside_the_block_measure_as_before(ratchet, tmp_path):
    # covers: GE-134a-1
    # angle: criterion
    """Under GE-127d-3 (2026-10-21) the lines around a history block are no longer
    counted either: in Python, ordinary '#' comments, a docstring and blank lines add 0;
    in JavaScript, '//' comments, a JSDoc block and blank lines add 0. Only code lines
    remain (2 each), with or without the block."""
    python_lines = [
        '"""Module docstring line one.',
        "",
        "More docstring.",
        '"""',
        "# ordinary hash comment",
        "value_a = 1",
        "",
        "value_b = 2",
        "# comment directly above the block's rule line",
        f"# {'=' * 68}",
        "# DECISION HISTORY",
        f"# {'=' * 68}",
        "# - 2026-10-21 [python-coder/GE-134a-1]: entry one",
        "#   continuation of entry one",
    ]
    content = "\n".join(python_lines) + "\n"
    assert fx.independent_count(content) == 2
    assert fx.measure_text(ratchet, tmp_path, "mixed.py", content) == 2

    javascript = "\n".join(
        [
            "// ordinary slash comment",
            "/**",
            " * JSDoc line",
            " * @param x the input",
            " */",
            "const value_a = 1;",
            "",
            "const value_b = 2;",
            "// DECISION HISTORY",
            "// - 2026-10-21 [python-coder/GE-134a-1]: entry one",
        ]
    ) + "\n"
    assert fx.measure_text(ratchet, tmp_path, "mixed.js", javascript) == 2


_NO_BLOCK_FILES = {
    "plain.py": (
        "\n".join(
            [
                '"""Docstring."""',
                "# see the DECISION HISTORY notes in the wiki",
                f"# {'=' * 40}",
                "# DECISION HISTORY notes are kept elsewhere",
                "import os",
                "",
                "LABEL = 'DECISION HISTORY'",
                f"# {'=' * 40}",
                "value = os.sep",
            ]
        )
        + "\n",
        3,
    ),
    "plain.sql": (
        "\n".join(
            [
                "/* header",
                "   block comment */",
                f"-- {'=' * 40}",
                "-- see DECISION HISTORY in the docs",
                "SELECT 1;",
                "",
                "-- trailing comment",
            ]
        )
        + "\n",
        1,
    ),
    "plain.js": (
        "\n".join(
            [
                "/**",
                " * JSDoc header",
                " */",
                f"// {'=' * 40}",
                "// DECISION HISTORY lives in the docs",
                "const a = 1;",
                "",
                "// ordinary comment",
                "export default a;",
            ]
        )
        + "\n",
        2,
    ),
}
# Pre-GE-127d-3 lengths of the same files (kept to prove the fixtures still distinguish the rules).
_OLD_RULE_LENGTH = {"plain.py": 8, "plain.sql": 5, "plain.js": 6}


def test_ge_134a_1_file_without_a_history_block_measures_as_before(ratchet, tmp_path):
    # covers: GE-134a-1
    # angle: criterion
    """Python, SQL and JavaScript files without a block (but with rule lines,
    mentions and near-miss headings) measure their code-line count: comments, mentions,
    rule lines, docstrings and blank lines add nothing (GE-127d-3, 2026-10-21)."""
    for name, (content, pinned) in _NO_BLOCK_FILES.items():
        assert fx.pre_change_count(content) == _OLD_RULE_LENGTH[name], name
        if name.endswith(".py"):
            assert fx.independent_count(content) == pinned, name
        assert fx.measure_text(ratchet, tmp_path, name, content) == pinned, name


def test_ge_134a_1_block_inside_a_docstring_or_block_comment_is_not_subtracted_twice(ratchet, tmp_path):
    # covers: GE-134a-1
    # angle: discrimination
    """A history block inside a trailing triple-quoted string (the form
    _file_size_ratchet.py uses) or inside a /* */ header measures exactly
    what its code lines are (never subtracted twice), even when '#'/'//' lines follow
    the closing delimiter; control row: the same block as line comments adds 0 too."""
    trailing_docstring = "CONST = 1\n\n" '"""\n' f"{'=' * 68}\nDECISION HISTORY\n{'=' * 68}\n- 2026-10-21 entry\n" '"""\n'
    hash_inside_docstring = "CONST = 1\n" '"""\n' "# DECISION HISTORY\n" '# - 2026-10-21 entry """\n' "# trailing one\n# trailing two\n"
    js_header = "/*\n// DECISION HISTORY\n// - 2026-10-21 entry */\n// ordinary one\n// ordinary two\nconst a = 1;\n"
    cases = {
        "trailing.py": (trailing_docstring, 2, 1),
        "hashdoc.py": (hash_inside_docstring, 3, 1),
        "header.js": (js_header, 3, 1),
    }
    for name, (content, old_rule, pinned) in cases.items():
        assert fx.pre_change_count(content) == old_rule, name
        assert fx.measure_text(ratchet, tmp_path, name, content) == pinned, name

    control = "CONST = 1\n# DECISION HISTORY\n# - 2026-10-21 entry\n"
    assert fx.measure_text(ratchet, tmp_path, "control.py", control) == 1
