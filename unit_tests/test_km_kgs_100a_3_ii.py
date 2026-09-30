"""
MODULE: test_km_kgs_100a_3_ii
GOAL: TDD stubs for KM-KGS-100a-3-ii — zero-, two- and four-space indented
      block lists must all read to the same value.
BUSINESS CONTEXT: KM-KGS-100a-3-i pins that column-zero lists must not read
    as empty; this criterion pins the complementary invariant that no single
    indentation is privileged — a fix that merely swaps the hard-coded
    two-space prefix check for a zero-space one still fails this contract.
    Values are compared read-path-to-read-path across three real on-disk
    files that differ only in indentation. All tests are RED before
    python-coder implements indentation-invariant block-list reading.
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


def test_covered_by_block_list_reads_one_item_at_indent_0_2_and_4(tmp_path):
    # covers: KM-KGS-100a-3-ii
    # angle: criterion
    """A single covered_by item declared at 0/2/4-space indents all read the same."""
    f0 = _read_fields(
        tmp_path, "indent0.yaml",
        "id: KM-EX-IND0\ncovered_by:\n- unit_tests/test_example.py\n",
    )
    f2 = _read_fields(
        tmp_path, "indent2.yaml",
        "id: KM-EX-IND2\ncovered_by:\n  - unit_tests/test_example.py\n",
    )
    f4 = _read_fields(
        tmp_path, "indent4.yaml",
        "id: KM-EX-IND4\ncovered_by:\n    - unit_tests/test_example.py\n",
    )
    expected = ["unit_tests/test_example.py"]
    assert f0.get("covered_by") == expected
    assert f2.get("covered_by") == expected
    assert f4.get("covered_by") == expected


def test_covered_by_block_list_values_equal_across_indents(tmp_path):
    # covers: KM-KGS-100a-3-ii
    # angle: criterion
    """The three covered_by values obtained above must be equal to one another."""
    f0 = _read_fields(
        tmp_path, "indent0.yaml",
        "id: KM-EX-IND0\ncovered_by:\n- unit_tests/test_example.py\n",
    )
    f2 = _read_fields(
        tmp_path, "indent2.yaml",
        "id: KM-EX-IND2\ncovered_by:\n  - unit_tests/test_example.py\n",
    )
    f4 = _read_fields(
        tmp_path, "indent4.yaml",
        "id: KM-EX-IND4\ncovered_by:\n    - unit_tests/test_example.py\n",
    )
    assert f0.get("covered_by") == f2.get("covered_by") == f4.get("covered_by")


def test_implemented_by_block_list_values_equal_across_indents(tmp_path):
    # covers: KM-KGS-100a-3-ii
    # angle: criterion
    """implemented_by at 0/2/4-space indents must read to the same one-item value."""
    f0 = _read_fields(
        tmp_path, "impl_indent0.yaml",
        "id: KM-EX-IMPL0\nimplemented_by:\n- scripts/example_module.py\n",
    )
    f2 = _read_fields(
        tmp_path, "impl_indent2.yaml",
        "id: KM-EX-IMPL2\nimplemented_by:\n  - scripts/example_module.py\n",
    )
    f4 = _read_fields(
        tmp_path, "impl_indent4.yaml",
        "id: KM-EX-IMPL4\nimplemented_by:\n    - scripts/example_module.py\n",
    )
    expected = ["scripts/example_module.py"]
    assert f0.get("implemented_by") == expected
    assert f2.get("implemented_by") == expected
    assert f4.get("implemented_by") == expected


def test_indented_block_list_does_not_absorb_list_of_following_key(tmp_path):
    # covers: KM-KGS-100a-3-ii
    # angle: boundary
    """The scan must stop at the next key, not absorb a deeper-indented sibling list."""
    fields = _read_fields(
        tmp_path, "no_absorb.yaml",
        "id: KM-EX-NOABSORB\n"
        "covered_by:\n"
        "  - unit_tests/test_example.py\n"
        "implemented_by:\n"
        "      - scripts/should_not_be_absorbed.py\n",
    )
    assert fields.get("covered_by") == ["unit_tests/test_example.py"]
    assert "scripts/should_not_be_absorbed.py" not in (fields.get("covered_by") or [])
