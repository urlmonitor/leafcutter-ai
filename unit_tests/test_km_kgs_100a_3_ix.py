"""
MODULE: test_km_kgs_100a_3_ix
GOAL: TDD stubs for KM-KGS-100a-3-ix — comment and blank lines between
      block-list items must not end the list or become items.
BUSINESS CONTEXT: A whole-store differential against PyYAML (see
    KM-KGS-100a-3-viii) left exactly one disagreement in the real store:
    BO-201.yaml declares covered_by as a block list whose first item is
    followed by seven indented comment lines and then a second, unquoted
    item carrying a ::TestListFormRegression suffix. PyYAML reads two
    items; scripts/knowledge_query.py::_parse_yaml_file (via
    _parse_block_children) treats the first comment line as the end of the
    list and silently drops every item after it. In YAML, a line whose
    first non-space character is # is a comment wherever it sits (including
    column zero, even when its text looks like 'key: value'), and a blank
    line carries no content — neither ends a block sequence nor
    contributes an item. The list must still end at the next real top-level
    key (KM-KGS-100a-3-ii), and a # inside an item value (a path#symbol
    anchor, KM-KGS-100a-3-v) must never be mistaken for a comment. Every
    Then here is proven by reading a real temp AC file through the
    production file-reading entry point, never a hand-built dictionary.
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


# The exact fixture named in KM-KGS-100a-3-ix's criteria: covered_by's first
# item is quoted, followed by an indented comment, then a column-zero
# comment shaped like a key ("# covers: KM-EX-010"), then a further item, a
# blank line, and a third item; implemented_by (no comments) follows as the
# next top-level key.
_CRITERIA_FIXTURE = (
    "id: KM-EX-COMMENTBUG-1\n"
    "covered_by:\n"
    '  - "unit_tests/test_alpha.py"\n'
    "  # Added by a later criterion; the entry above is kept.\n"
    "# covers: KM-EX-010\n"
    "  - unit_tests/test_beta.py::test_gamma\n"
    "\n"
    "  - unit_tests/test_delta.py\n"
    "implemented_by:\n"
    "  - scripts/example_module.py#example_function\n"
)


def _read_criteria_fixture(tmp_path):
    return _read_fields(tmp_path, "criteria_fixture.yaml", _CRITERIA_FIXTURE)


def test_column_zero_key_shaped_comment_does_not_end_covered_by_list(tmp_path):
    # covers: KM-KGS-100a-3-ix
    # angle: criterion
    """The criteria fixture's covered_by reads to the full three-item list
    even though a column-zero, key-shaped comment ('# covers: KM-EX-010')
    sits between its items."""
    fields = _read_criteria_fixture(tmp_path)
    assert fields.get("covered_by") == [
        "unit_tests/test_alpha.py",
        "unit_tests/test_beta.py::test_gamma",
        "unit_tests/test_delta.py",
    ]


def test_comment_text_never_becomes_list_item(tmp_path):
    # covers: KM-KGS-100a-3-ix
    # angle: boundary
    """No item of the covered_by value contains either comment line's text
    (including 'covers: KM-EX-010'), and no item begins with '#'."""
    fields = _read_criteria_fixture(tmp_path)
    value = fields.get("covered_by") or []
    for item in value:
        assert "Added by a later criterion" not in item
        assert "covers: KM-EX-010" not in item
        assert not item.startswith("#")


def test_blank_line_does_not_end_list_or_yield_empty_item(tmp_path):
    # covers: KM-KGS-100a-3-ix
    # angle: boundary
    """The item that follows the blank line (unit_tests/test_delta.py) is
    present in covered_by, and no item of that value is the empty string."""
    fields = _read_criteria_fixture(tmp_path)
    value = fields.get("covered_by") or []
    assert "unit_tests/test_delta.py" in value
    assert "" not in value


def test_list_with_comment_and_blank_lines_still_ends_at_next_top_level_key(tmp_path):
    # covers: KM-KGS-100a-3-ix
    # angle: boundary
    """implemented_by reads to exactly its own one-item list; no covered_by
    item appears in it and no implemented_by item appears in covered_by, so
    skipping comment and blank lines does not make the scan absorb the
    following field."""
    fields = _read_criteria_fixture(tmp_path)
    implemented = fields.get("implemented_by") or []
    covered = fields.get("covered_by") or []
    assert implemented == ["scripts/example_module.py#example_function"]
    assert not any(item in implemented for item in covered)
    assert not any(item in covered for item in implemented)


# A second real AC file, declaring implemented_by (not covered_by) with the
# same indented comment, column-zero key-shaped comment, and blank line
# between its items.
_IMPLEMENTED_BY_FIXTURE = (
    "id: KM-EX-COMMENTBUG-2\n"
    "implemented_by:\n"
    "  - scripts/module_a.py\n"
    "  # Added by a later criterion; the entry above is kept.\n"
    "# covers: KM-EX-011\n"
    "  - scripts/module_b.py::test_gamma\n"
    "\n"
    "  - scripts/module_c.py\n"
    "covered_by:\n"
    "  - unit_tests/test_other.py\n"
)


def test_implemented_by_block_list_with_comment_and_blank_lines_yields_all_items(tmp_path):
    # covers: KM-KGS-100a-3-ix
    # angle: criterion
    """A second real AC file declaring implemented_by as a block list with the
    same comment and blank-line shape reads to the full ordered item list,
    with no comment text, no item beginning with '#', and no empty-string
    item."""
    fields = _read_fields(tmp_path, "implemented_by_fixture.yaml", _IMPLEMENTED_BY_FIXTURE)
    value = fields.get("implemented_by") or []
    assert value == [
        "scripts/module_a.py",
        "scripts/module_b.py::test_gamma",
        "scripts/module_c.py",
    ]
    for item in value:
        assert "Added by a later criterion" not in item
        assert "covers: KM-EX-011" not in item
        assert not item.startswith("#")
    assert "" not in value


# Both fields carry a path#symbol item placed immediately after a comment
# line, so the anchor-survival guarantee (KM-KGS-100a-3-v) is proven to hold
# even once comment-skipping is in play.
_SYMBOL_ANCHOR_FIXTURE = (
    "id: KM-EX-COMMENTBUG-3\n"
    "covered_by:\n"
    "  - unit_tests/test_first.py\n"
    "  # comment line\n"
    "  - scripts/anchor_target.py#anchor_symbol\n"
    "implemented_by:\n"
    "  - scripts/impl_first.py\n"
    "  # comment line\n"
    "  - scripts/impl_anchor.py#impl_symbol\n"
)


def test_symbol_anchor_survives_comment_skipping_in_covered_by_and_implemented_by(tmp_path):
    # covers: KM-KGS-100a-3-ix
    # angle: boundary
    """A path#symbol item placed right after a comment line survives in full
    (not truncated at '#', not dropped as a comment) in both covered_by and
    implemented_by, consistent with KM-KGS-100a-3-v."""
    fields = _read_fields(tmp_path, "symbol_anchor_fixture.yaml", _SYMBOL_ANCHOR_FIXTURE)
    covered = fields.get("covered_by") or []
    implemented = fields.get("implemented_by") or []
    assert "scripts/anchor_target.py#anchor_symbol" in covered
    assert "scripts/impl_anchor.py#impl_symbol" in implemented
    assert "scripts/anchor_target.py" not in covered
    assert "scripts/impl_anchor.py" not in implemented


# The measured regression shape of the real docs/acceptance-criteria/
# build-orchestration/BO-201.yaml: a double-quoted first item, seven
# indented comment lines, then an unquoted item with a ::TestClass suffix,
# then the next top-level key.
_BO_201_SHAPED_FIXTURE = (
    "id: KM-EX-BO201SHAPE\n"
    "covered_by:\n"
    '  - "tests/test_first.py"\n'
    "  # comment 1\n"
    "  # comment 2\n"
    "  # comment 3\n"
    "  # comment 4\n"
    "  # comment 5\n"
    "  # comment 6\n"
    "  # comment 7\n"
    "  - unit_tests/test_second.py::TestClass\n"
    "test_spec:\n"
    "  - name: something\n"
)


def test_bo_201_shaped_list_reads_both_items(tmp_path):
    # covers: KM-KGS-100a-3-ix
    # angle: failure
    """Regression shape of BO-201.yaml, written to a temp AC file: covered_by
    with a double-quoted first item, then seven indented comment lines,
    then an unquoted item carrying a ::TestClass suffix, then the next
    top-level key; covered_by reads to exactly those two items in order."""
    fields = _read_fields(tmp_path, "bo_201_shaped.yaml", _BO_201_SHAPED_FIXTURE)
    assert fields.get("covered_by") == [
        "tests/test_first.py",
        "unit_tests/test_second.py::TestClass",
    ]
