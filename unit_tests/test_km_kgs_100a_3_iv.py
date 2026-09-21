"""
MODULE: test_km_kgs_100a_3_iv
GOAL: TDD stubs for KM-KGS-100a-3-iv — a ::test_function suffix on a coverage
      item must survive reading intact, in both quoted and unquoted form.
BUSINESS CONTEXT: The AC schema allows covered_by items to carry an optional
    ::test_function suffix. A line-oriented reader that splits on the first
    colon, or that fails to read the column-zero block-list form at all
    (KM-KGS-100a-3-i), would truncate or drop this value. Both records here
    are written in the column-zero form the store actually uses, so the
    unquoted case is expected to fail for the same underlying reason as
    KM-KGS-100a-3-i until that reader fix lands, and the quoted case
    additionally exercises the different quoted-item code path.
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


def test_unquoted_covered_by_item_keeps_test_function_suffix(tmp_path):
    # covers: KM-KGS-100a-3-iv
    # angle: criterion
    """An unquoted covered_by item with a ::test_function suffix reads intact."""
    fields = _read_fields(
        tmp_path,
        "suffix_unquoted.yaml",
        "id: KM-EX-SUFFIX1\n"
        "covered_by:\n"
        "- unit_tests/test_alpha.py::test_beta_returns_two_items\n",
    )
    assert fields.get("covered_by") == [
        "unit_tests/test_alpha.py::test_beta_returns_two_items"
    ]


def test_double_quoted_covered_by_item_keeps_test_function_suffix(tmp_path):
    # covers: KM-KGS-100a-3-iv
    # angle: criterion
    """The same item declared double-quoted reads to the same one-item value."""
    fields = _read_fields(
        tmp_path,
        "suffix_quoted.yaml",
        "id: KM-EX-SUFFIX2\n"
        "covered_by:\n"
        '- "unit_tests/test_alpha.py::test_beta_returns_two_items"\n',
    )
    value = fields.get("covered_by") or []
    assert value == ["unit_tests/test_alpha.py::test_beta_returns_two_items"]
    assert any(
        "::test_beta_returns_two_items" in item for item in value
    )


def test_test_function_suffix_item_not_split_at_colons(tmp_path):
    # covers: KM-KGS-100a-3-iv
    # angle: boundary
    """Neither the quoted nor unquoted form is split into multiple entries at ':'."""
    unquoted = _read_fields(
        tmp_path,
        "suffix_unquoted2.yaml",
        "id: KM-EX-SUFFIX3\n"
        "covered_by:\n"
        "- unit_tests/test_alpha.py::test_beta_returns_two_items\n",
    )
    quoted = _read_fields(
        tmp_path,
        "suffix_quoted2.yaml",
        "id: KM-EX-SUFFIX4\n"
        "covered_by:\n"
        '- "unit_tests/test_alpha.py::test_beta_returns_two_items"\n',
    )
    assert len(unquoted.get("covered_by") or []) == 1
    assert len(quoted.get("covered_by") or []) == 1
