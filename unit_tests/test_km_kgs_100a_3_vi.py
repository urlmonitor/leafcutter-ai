"""
MODULE: test_km_kgs_100a_3_vi
GOAL: TDD stubs for KM-KGS-100a-3-vi — a comma inside a quoted inline item
      must not split that item into two.
BUSINESS CONTEXT: Measured evidence (2026-09-16) shows the inline-sequence
    branch of _parse_scalar_value splits the bracketed text on every comma
    with no quote awareness, so a comma interior to a quoted item (a real
    shape: covered_by items may carry free-text ::test_function suffixes)
    produces spurious extra items. All tests are RED before python-coder
    implements a quote-aware split (e.g. via csv.reader, stdlib-only).
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


def test_inline_quoted_item_with_commas_reads_as_single_item(tmp_path):
    # covers: KM-KGS-100a-3-vi
    # angle: criterion
    """A double-quoted inline item containing commas reads as exactly one item."""
    fields = _read_fields(
        tmp_path,
        "comma_double.yaml",
        'id: KM-EX-COMMA1\n'
        'covered_by: ["unit_tests/test_alpha.py::test_accepts_a, b, and c"]\n',
    )
    assert len(fields.get("covered_by") or []) == 1


def test_inline_quoted_item_with_commas_keeps_full_text(tmp_path):
    # covers: KM-KGS-100a-3-vi
    # angle: criterion
    """The single item equals the full comma-bearing text, untruncated."""
    fields = _read_fields(
        tmp_path,
        "comma_double2.yaml",
        'id: KM-EX-COMMA2\n'
        'covered_by: ["unit_tests/test_alpha.py::test_accepts_a, b, and c"]\n',
    )
    assert fields.get("covered_by") == [
        "unit_tests/test_alpha.py::test_accepts_a, b, and c"
    ]


def test_inline_quoted_item_with_commas_yields_no_fragments(tmp_path):
    # covers: KM-KGS-100a-3-vi
    # angle: criterion
    """No item of the value is the fragment 'b' or 'and c'."""
    fields = _read_fields(
        tmp_path,
        "comma_double3.yaml",
        'id: KM-EX-COMMA3\n'
        'covered_by: ["unit_tests/test_alpha.py::test_accepts_a, b, and c"]\n',
    )
    value = fields.get("covered_by") or []
    assert "b" not in value
    assert "and c" not in value


def test_inline_two_separate_quoted_items_still_yield_two_items(tmp_path):
    # covers: KM-KGS-100a-3-vi
    # angle: boundary
    """A genuine two-item inline sequence must still read as two items (no over-fix)."""
    fields = _read_fields(
        tmp_path,
        "comma_two_items.yaml",
        'id: KM-EX-COMMA4\n'
        'covered_by: ["unit_tests/test_alpha.py", "unit_tests/test_beta.py"]\n',
    )
    assert fields.get("covered_by") == [
        "unit_tests/test_alpha.py",
        "unit_tests/test_beta.py",
    ]


def test_single_quoted_inline_item_with_commas_reads_as_single_item(tmp_path):
    # covers: KM-KGS-100a-3-vi
    # angle: boundary
    """The comma-bearing item declared single-quoted also reads as one full item."""
    fields = _read_fields(
        tmp_path,
        "comma_single.yaml",
        "id: KM-EX-COMMA5\n"
        "covered_by: ['unit_tests/test_alpha.py::test_accepts_a, b, and c']\n",
    )
    assert fields.get("covered_by") == [
        "unit_tests/test_alpha.py::test_accepts_a, b, and c"
    ]
