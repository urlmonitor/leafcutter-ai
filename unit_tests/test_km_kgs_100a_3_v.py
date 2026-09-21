"""
MODULE: test_km_kgs_100a_3_v
GOAL: TDD stubs for KM-KGS-100a-3-v — a #symbol anchor on an implemented_by
      item must not be mistaken for a YAML comment.
BUSINESS CONTEXT: The AC schema allows implemented_by items to carry an
    optional #anchor. A # only opens a YAML comment when preceded by
    whitespace or at the start of a token, so an unquoted path#symbol is one
    scalar; a reader that strips from the first # onward would silently
    truncate or empty the value. Both records are written in the column-zero
    form the store actually uses, so this also exercises KM-KGS-100a-3-i.
    This L3 asserts only that the anchor survives into the field value — the
    anchor's effect on a resolved target id belongs to the parent AC
    (KM-KGS-100a-3) and is not asserted here.
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


def test_unquoted_implemented_by_item_keeps_symbol_anchor(tmp_path):
    # covers: KM-KGS-100a-3-v
    # angle: criterion
    """An unquoted implemented_by item with a #anchor reads to that exact item."""
    fields = _read_fields(
        tmp_path,
        "anchor_unquoted.yaml",
        "id: KM-EX-ANCHOR1\n"
        "implemented_by:\n"
        "- scripts/example_module.py#example_function\n",
    )
    assert fields.get("implemented_by") == [
        "scripts/example_module.py#example_function"
    ]


def test_double_quoted_implemented_by_item_keeps_symbol_anchor(tmp_path):
    # covers: KM-KGS-100a-3-v
    # angle: criterion
    """The same item declared double-quoted reads with #example_function present in full."""
    fields = _read_fields(
        tmp_path,
        "anchor_quoted.yaml",
        "id: KM-EX-ANCHOR2\n"
        "implemented_by:\n"
        '- "scripts/example_module.py#example_function"\n',
    )
    value = fields.get("implemented_by") or []
    assert value == ["scripts/example_module.py#example_function"]
    assert any("#example_function" in item for item in value)


def test_symbol_anchor_item_not_truncated_at_hash(tmp_path):
    # covers: KM-KGS-100a-3-v
    # angle: boundary
    """Neither form truncates the item at the # character."""
    unquoted = _read_fields(
        tmp_path,
        "anchor_unquoted2.yaml",
        "id: KM-EX-ANCHOR3\n"
        "implemented_by:\n"
        "- scripts/example_module.py#example_function\n",
    )
    quoted = _read_fields(
        tmp_path,
        "anchor_quoted2.yaml",
        "id: KM-EX-ANCHOR4\n"
        "implemented_by:\n"
        '- "scripts/example_module.py#example_function"\n',
    )
    expected = ["scripts/example_module.py#example_function"]
    # A reader that truncates at '#' would produce ["scripts/example_module.py"];
    # a reader that drops the field entirely (KM-KGS-100a-3-i) would produce
    # None/[]. Either failure mode is caught by requiring the full value.
    assert unquoted.get("implemented_by") == expected
    assert quoted.get("implemented_by") == expected
    assert "scripts/example_module.py" not in (unquoted.get("implemented_by") or [])
    assert "scripts/example_module.py" not in (quoted.get("implemented_by") or [])


def test_symbol_anchor_value_has_no_empty_string_item(tmp_path):
    # covers: KM-KGS-100a-3-v
    # angle: boundary
    """No item of the implemented_by value read from either file is the empty string."""
    unquoted = _read_fields(
        tmp_path,
        "anchor_unquoted3.yaml",
        "id: KM-EX-ANCHOR5\n"
        "implemented_by:\n"
        "- scripts/example_module.py#example_function\n",
    )
    quoted = _read_fields(
        tmp_path,
        "anchor_quoted3.yaml",
        "id: KM-EX-ANCHOR6\n"
        "implemented_by:\n"
        '- "scripts/example_module.py#example_function"\n',
    )
    assert "" not in (unquoted.get("implemented_by") or [])
    assert "" not in (quoted.get("implemented_by") or [])
    assert len(unquoted.get("implemented_by") or []) == 1
    assert len(quoted.get("implemented_by") or []) == 1
