"""
MODULE: test_km_kgs_100a_3_vii
GOAL: TDD stubs for KM-KGS-100a-3-vii — an explicitly empty list and an
      absent field must both read as no values, indistinguishably.
BUSINESS CONTEXT: This is the boundary guard for the sibling reading fixes
    in this group (KM-KGS-100a-3-i..-vi): a fix that makes column-zero or
    quoted lists read correctly must not make an explicitly empty list read
    as a one-item list holding the empty string or the literal bracket text.
    These tests are expected to already hold for the current reader (they
    guard against regression during the sibling fixes); see red_baseline
    notes for any that pass immediately.
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


def test_explicit_empty_lists_read_as_no_items(tmp_path):
    # covers: KM-KGS-100a-3-vii
    # angle: boundary
    """covered_by: [] and implemented_by: [] both read as empty."""
    fields = _read_fields(
        tmp_path,
        "explicit_empty.yaml",
        "id: KM-EX-EMPTY1\ncovered_by: []\nimplemented_by: []\n",
    )
    assert (fields.get("covered_by") or []) == []
    assert (fields.get("implemented_by") or []) == []


def test_absent_relationship_fields_read_as_no_items(tmp_path):
    # covers: KM-KGS-100a-3-vii
    # angle: boundary
    """A record declaring neither field reads both as empty, same as the explicit form."""
    explicit = _read_fields(
        tmp_path,
        "explicit_empty2.yaml",
        "id: KM-EX-EMPTY2\ncovered_by: []\nimplemented_by: []\n",
    )
    absent = _read_fields(
        tmp_path,
        "absent_fields.yaml",
        "id: KM-EX-ABSENT1\ntitle: no relationship fields declared\n",
    )
    assert (absent.get("covered_by") or []) == []
    assert (absent.get("implemented_by") or []) == []
    assert (absent.get("covered_by") or []) == (explicit.get("covered_by") or [])
    assert (absent.get("implemented_by") or []) == (explicit.get("implemented_by") or [])


def test_empty_relationship_values_contain_no_placeholder_text(tmp_path):
    # covers: KM-KGS-100a-3-vii
    # angle: boundary
    """Neither value contains '', '[]' or '\"[]\"' as a stray item."""
    explicit = _read_fields(
        tmp_path,
        "explicit_empty3.yaml",
        "id: KM-EX-EMPTY3\ncovered_by: []\nimplemented_by: []\n",
    )
    absent = _read_fields(
        tmp_path,
        "absent_fields2.yaml",
        "id: KM-EX-ABSENT2\ntitle: no relationship fields declared\n",
    )
    for fields in (explicit, absent):
        for field in ("covered_by", "implemented_by"):
            value = fields.get(field) or []
            assert "" not in value
            assert "[]" not in value
            assert '"[]"' not in value


def test_reading_record_without_relationship_fields_does_not_raise(tmp_path):
    # covers: KM-KGS-100a-3-vii
    # angle: failure
    """Reading a file that omits both relationship fields must not raise."""
    p = tmp_path / "absent_fields3.yaml"
    p.write_text("id: KM-EX-ABSENT3\ntitle: no relationship fields declared\n", encoding="utf-8")
    # Must complete without raising.
    fields = _parse_yaml_file(p.read_text(encoding="utf-8"))
    assert fields.get("id") == "KM-EX-ABSENT3"
