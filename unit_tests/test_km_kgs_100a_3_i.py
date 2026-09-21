"""
MODULE: test_km_kgs_100a_3_i
GOAL: TDD stubs for KM-KGS-100a-3-i — column-zero block lists must be read,
      not silently dropped.
BUSINESS CONTEXT: Measured evidence (2026-09-16) shows the hand-rolled YAML
    reader in scripts/knowledge_query.py (_parse_block_children) requires each
    block-list item line to start with two spaces, so a column-zero dash list
    (the form the store's own serializer routinely writes) is read back as an
    empty list. This silently drops relationship data used to build the
    knowledge graph. These tests read a real on-disk AC file through the
    production reader (_parse_yaml_file) and assert the column-zero form is
    not dropped. All tests are RED before python-coder fixes the reader.
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


def test_column_zero_implemented_by_block_list_reads_both_items(tmp_path):
    # covers: KM-KGS-100a-3-i
    # angle: criterion
    """Reader must not drop a column-zero implemented_by block list."""
    fields = _read_fields(
        tmp_path,
        "KM-EX-COL0-1.yaml",
        "id: KM-EX-COL0-1\n"
        "implemented_by:\n"
        "- scripts/example_module.py\n"
        "- templates/agents/example-agent.md\n",
    )
    assert fields.get("implemented_by") == [
        "scripts/example_module.py",
        "templates/agents/example-agent.md",
    ]


def test_column_zero_implemented_by_block_list_is_not_empty(tmp_path):
    # covers: KM-KGS-100a-3-i
    # angle: criterion
    """The column-zero implemented_by value must never come back empty."""
    fields = _read_fields(
        tmp_path,
        "KM-EX-COL0-2.yaml",
        "id: KM-EX-COL0-2\n"
        "implemented_by:\n"
        "- scripts/example_module.py\n",
    )
    assert fields.get("implemented_by") != []
    assert fields.get("implemented_by") is not None


def test_column_zero_covered_by_block_list_reads_items(tmp_path):
    # covers: KM-KGS-100a-3-i
    # angle: criterion
    """A covered_by field declared in the same column-zero form must also read."""
    fields = _read_fields(
        tmp_path,
        "KM-EX-COL0-3.yaml",
        "id: KM-EX-COL0-3\n"
        "covered_by:\n"
        "- unit_tests/test_example.py\n"
        "- unit_tests/test_example_two.py\n",
    )
    assert fields.get("covered_by") == [
        "unit_tests/test_example.py",
        "unit_tests/test_example_two.py",
    ]
