"""
MODULE: unit_tests/commit_guardian/test_ge_127h_1.py
COVERS: GE-127h-1 -- "A file's decision-history block is left out of its
    measured length, in every covered language, and nothing else changes"

GOAL: The six test_spec descriptors of GE-127h-1, built exactly as the test
    design lists them. Shared builders, loaders and the independent counter
    live in _ge_127h_fixture.py (see its docstring for the pinned name of the
    prefix constant, DECISION_HISTORY_COMMENT_PREFIXES).

RED TODAY: count_content_lines counts every '#', '//' and '--' comment line,
    so a line-comment DECISION HISTORY block adds its own lines to the
    measured length. The two "measures as before" descriptors are
    preservation guards and are expected to hold before and after the
    change; the docstring/block-comment descriptor carries a control row
    (the same block as line comments) that is red today.

DECISION HISTORY
- 2026-10-21 [test-writer/GE-127h-1]: Initial authoring.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ge_127d_2_fixture as d2  # noqa: E402
import _ge_127h_fixture as fx  # noqa: E402

_SHIPPED_EXTENSIONS = json.loads(fx.SHIPPED_CONFIG.read_text(encoding="utf-8"))["file_size"]["checked_extensions"]


@pytest.fixture()
def ratchet():
    return fx.load_ratchet()


def test_ge_127h_1_python_and_javascript_history_blocks_are_not_measured(ratchet, tmp_path):
    # covers: GE-127h-1
    # angle: criterion
    """The 80-line Python file with its 25-line ruled '#' block measures 80;
    the 120-line JavaScript file with its 15-line unruled '//' header block
    measures 120."""
    python_text = fx.python_example()
    javascript_text = fx.javascript_example()
    assert fx.pre_change_count(python_text) == 105
    assert fx.pre_change_count(javascript_text) == 135

    assert fx.measure_text(ratchet, tmp_path, "example.py", python_text) == 80
    assert fx.measure_text(ratchet, tmp_path, "example.js", javascript_text) == 120


def test_ge_127h_1_history_block_is_left_out_of_the_length_the_size_check_quotes(tmp_path):
    # covers: GE-127h-1
    # angle: reachability
    """Through the fixture copy of check_file_size.py: under a limit of 80
    the Python example passes, listed at 80 lines; one more code line is
    refused quoting Lines: 81."""
    at_limit_root = tmp_path / "at_limit"
    at_limit_root.mkdir()
    d2.build_fixture_tree(at_limit_root, line_limit=80, checked_extensions=[".py"])
    result = fx.stage_and_check(at_limit_root, "src/example.py", fx.python_example())
    output = d2.combined_output(result)
    assert result.returncode == 0, output
    assert "src/example.py (new, 80 lines - OK)" in output

    over_root = tmp_path / "over"
    over_root.mkdir()
    d2.build_fixture_tree(over_root, line_limit=80, checked_extensions=[".py"])
    result = fx.stage_and_check(over_root, "src/example.py", fx.python_example(extra_code_lines=1))
    output = d2.combined_output(result)
    assert result.returncode == 1, output
    assert d2.parse_lines_and_limit(output) == (81, 80), output


@pytest.mark.parametrize("extension", _SHIPPED_EXTENSIONS)
def test_ge_127h_1_line_comment_block_is_left_out_in_every_covered_language(extension, ratchet, tmp_path):
    # covers: GE-127h-1
    # angle: discrimination
    """For every shipped checked extension: N measured lines plus a block
    headed '<prefix> DECISION HISTORY' measures N; the prefix comes from the
    one constant, which is exactly ('#', '//', '--'); a heading followed by
    lines of ANOTHER prefix ends at the first such line, which is counted;
    and rewriting the constant (in a disposable copy) moves both the
    measurement and the published rule -- no second copy of the prefixes."""
    assert extension in fx.PREFIX_BY_EXTENSION, f"no line-comment prefix known for shipped {extension}"
    prefix = fx.PREFIX_BY_EXTENSION[extension]
    body = fx.body_lines(10, prefix, "value_{i} = {i}")
    block = [f"{prefix} DECISION HISTORY", *fx.history_entries(prefix, 4)]
    content = "\n".join([*body, *block]) + "\n"
    assert fx.measure_text(ratchet, tmp_path, f"sample{extension}", content) == 10

    constant = fx.prefix_constant(ratchet)
    assert constant == fx.EXPECTED_PREFIXES, f"{fx.PREFIX_CONSTANT_NAME} = {constant!r}"

    foreign = fx.EXPECTED_PREFIXES[(fx.EXPECTED_PREFIXES.index(prefix) + 1) % 3]
    mixed = [*body, f"{prefix} DECISION HISTORY", f"{prefix} - entry", f"{foreign} not part of it", f"{foreign} nor this"]
    assert fx.measure_text(ratchet, tmp_path, f"mixed{extension}", "\n".join(mixed) + "\n") == 12

    rewritten = (*(p for p in fx.EXPECTED_PREFIXES if p != prefix), ";;")
    copy = fx.load_ratchet_with_prefixes(tmp_path, rewritten, extension.lstrip("."))
    assert copy is not None, f"{fx.PREFIX_CONSTANT_NAME} is not a module-level assignment"
    assert fx.measure_text(copy, tmp_path, f"dropped{extension}", content) == 15
    novel = "\n".join([*body, ";; DECISION HISTORY", *fx.history_entries(";;", 4)]) + "\n"
    assert fx.measure_text(copy, tmp_path, f"novel{extension}", novel) == 10
    assert ";;" in copy.describe_measurement_rule(), copy.describe_measurement_rule()


def test_ge_127h_1_lines_outside_the_block_measure_as_before(ratchet, tmp_path):
    # covers: GE-127h-1
    # angle: criterion
    """Ordinary '#' and '//' comments, a docstring, a JSDoc block and blank
    lines keep their pre-change count; only the 5 block lines go."""
    content = "\n".join(
        [
            '"""Module docstring line one.',
            "",
            "More docstring.",
            '"""',
            "# ordinary hash comment",
            "// ordinary slash comment",
            "/**",
            " * JSDoc line",
            " * @param x the input",
            " */",
            "value_a = 1",
            "",
            "value_b = 2",
            "// comment directly above the block's rule line",
            f"# {'=' * 68}",
            "# DECISION HISTORY",
            f"# {'=' * 68}",
            "# - 2026-10-21 [python-coder/GE-127h-1]: entry one",
            "#   continuation of entry one",
        ]
    ) + "\n"
    pinned_pre_change = 11
    assert fx.pre_change_count(content) == pinned_pre_change
    assert fx.measure_text(ratchet, tmp_path, "mixed.py", content) == pinned_pre_change - 5


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
        8,
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
        5,
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
        6,
    ),
}


def test_ge_127h_1_file_without_a_history_block_measures_as_before(ratchet, tmp_path):
    # covers: GE-127h-1
    # angle: criterion
    """Python, SQL and JavaScript files without a block (but with rule lines,
    mentions and near-miss headings) measure their pinned pre-change length."""
    for name, (content, pinned) in _NO_BLOCK_FILES.items():
        assert fx.pre_change_count(content) == pinned, name
        assert fx.measure_text(ratchet, tmp_path, name, content) == pinned, name


def test_ge_127h_1_block_inside_a_docstring_or_block_comment_is_not_subtracted_twice(ratchet, tmp_path):
    # covers: GE-127h-1
    # angle: discrimination
    """A history block inside a trailing triple-quoted string (the form
    _file_size_ratchet.py uses) or inside a /* */ header measures exactly
    what it did before, even when '#'/'//' lines follow the closing
    delimiter; control row: the same block as line comments IS left out."""
    trailing_docstring = "CONST = 1\n\n" '"""\n' f"{'=' * 68}\nDECISION HISTORY\n{'=' * 68}\n- 2026-10-21 entry\n" '"""\n'
    hash_inside_docstring = "CONST = 1\n" '"""\n' "# DECISION HISTORY\n" '# - 2026-10-21 entry """\n' "# trailing one\n# trailing two\n"
    js_header = "/*\n// DECISION HISTORY\n// - 2026-10-21 entry */\n// ordinary one\n// ordinary two\nconst a = 1;\n"
    cases = {"trailing.py": (trailing_docstring, 2), "hashdoc.py": (hash_inside_docstring, 3), "header.js": (js_header, 3)}
    for name, (content, pinned) in cases.items():
        assert fx.pre_change_count(content) == pinned, name
        assert fx.measure_text(ratchet, tmp_path, name, content) == pinned, name

    control = "CONST = 1\n# DECISION HISTORY\n# - 2026-10-21 entry\n"
    assert fx.measure_text(ratchet, tmp_path, "control.py", control) == 1
