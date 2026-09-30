"""
MODULE: test_km_kgs_100a_3_iii
GOAL: TDD stubs for KM-KGS-100a-3-iii — quoted block-list items must lose
      their quotes, matching the inline-sequence result.
BUSINESS CONTEXT: Measured evidence (2026-09-16) shows the block-list reader
    strips the leading dash and surrounding whitespace but never quote
    characters, so a quoted item keeps its quotes. The inline-sequence path
    already strips quotes correctly — the defect is an inconsistency between
    the two read paths, so the load-bearing test compares them against each
    other (read-path vs read-path), not only against a hand-typed literal.
    All tests are RED before python-coder makes the block-list path strip a
    matched surrounding quote pair the same way the inline path does.
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from knowledge_query import _parse_yaml_file  # noqa: E402


def _read_fields(tmp_path, filename, content):
    p = tmp_path / filename
    p.write_text(content, encoding="utf-8")
    return _parse_yaml_file(p.read_text(encoding="utf-8"))


def test_quoted_block_list_items_read_without_quotes(tmp_path):
    # covers: KM-KGS-100a-3-iii
    # angle: criterion
    """A covered_by block list with a double- and single-quoted item strips both."""
    fields = _read_fields(
        tmp_path,
        "quoted_block.yaml",
        "id: KM-EX-QBLOCK\n"
        "covered_by:\n"
        '  - "unit_tests/test_alpha.py"\n'
        "  - 'unit_tests/test_beta.py'\n",
    )
    assert fields.get("covered_by") == [
        "unit_tests/test_alpha.py",
        "unit_tests/test_beta.py",
    ]


def test_quoted_block_list_items_have_no_leading_or_trailing_quote(tmp_path):
    # covers: KM-KGS-100a-3-iii
    # angle: criterion
    """No item read from the quoted block list may begin or end with a quote char."""
    fields = _read_fields(
        tmp_path,
        "quoted_block2.yaml",
        "id: KM-EX-QBLOCK2\n"
        "covered_by:\n"
        '  - "unit_tests/test_alpha.py"\n'
        "  - 'unit_tests/test_beta.py'\n",
    )
    for item in fields.get("covered_by") or []:
        assert not item.startswith('"') and not item.startswith("'")
        assert not item.endswith('"') and not item.endswith("'")


def test_quoted_block_list_value_equals_inline_sequence_value(tmp_path):
    # covers: KM-KGS-100a-3-iii
    # angle: criterion
    """Block-list reading and inline-sequence reading of the same two items must agree."""
    block_fields = _read_fields(
        tmp_path,
        "quoted_block3.yaml",
        "id: KM-EX-QBLOCK3\n"
        "covered_by:\n"
        '  - "unit_tests/test_alpha.py"\n'
        "  - 'unit_tests/test_beta.py'\n",
    )
    inline_fields = _read_fields(
        tmp_path,
        "quoted_inline3.yaml",
        "id: KM-EX-QINLINE3\n"
        'covered_by: ["unit_tests/test_alpha.py", \'unit_tests/test_beta.py\']\n',
    )
    assert block_fields.get("covered_by") == inline_fields.get("covered_by")


def test_interior_quote_character_in_block_list_item_survives(tmp_path):
    # covers: KM-KGS-100a-3-iii
    # angle: boundary
    """Only a matched surrounding quote pair is stripped; an interior quote survives."""
    fields = _read_fields(
        tmp_path,
        "interior_quote.yaml",
        "id: KM-EX-INTQUOTE\n"
        "covered_by:\n"
        '  - unit_tests/test_alpha.py::test_says_"hello"\n',
    )
    assert fields.get("covered_by") == [
        'unit_tests/test_alpha.py::test_says_"hello"'
    ]
