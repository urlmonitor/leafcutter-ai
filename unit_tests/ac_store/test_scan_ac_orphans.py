"""
MODULE: test_scan_ac_orphans
GOAL: Unit tests for scan_ac_orphans.py — the store-wide AC orphan detection scan.
TICKET: EPIC-AcParentChildLinkEnforcement/04_TICKET-20260607-ACS-100i-4.md
COVERS: ACS-100i-4

Gherkin scenarios covered:
  - Scan detects orphaned child ACs and reports them grouped by parent.
  - Scan exits non-zero when orphans are found.
  - Scan exits zero when every child is listed in its parent's covered_by.
  - Report includes: child AC ID, expected parent AC ID, parent file path.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_AC_STORE_SCRIPTS = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_AC_STORE_SCRIPTS))

from scan_ac_orphans import (  # noqa: E402
    _build_id_index,
    _extract_covered_by,
    _load_ac,
    find_orphaned_children,
    main,
)
from ac_parent_id import derive_parent_id  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures — minimal YAML files written to tmpdir
# ---------------------------------------------------------------------------


def _write_yaml(tmp_path: Path, filename: str, content: str) -> Path:
    """Write a YAML file to tmp_path and return its Path.

    Args:
        tmp_path: Temporary directory provided by pytest.
        filename: Name of the YAML file (relative to tmp_path).
        content: YAML content string.

    Returns:
        Absolute Path to the written file.
    """
    p = tmp_path / filename
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# _extract_covered_by()
# ---------------------------------------------------------------------------


class TestExtractCoveredBy:
    """Unit tests for the _extract_covered_by() helper."""

    def test_returns_list_when_present(self) -> None:
        # covers: ACS-100i-4
        data = {"covered_by": ["ACS-300h-1", "ACS-300h-2"]}
        assert _extract_covered_by(data) == ["ACS-300h-1", "ACS-300h-2"]

    def test_returns_empty_list_when_absent(self) -> None:
        # covers: ACS-100i-4
        data = {}
        assert _extract_covered_by(data) == []

    def test_returns_empty_list_for_empty_list(self) -> None:
        # covers: ACS-100i-4
        data = {"covered_by": []}
        assert _extract_covered_by(data) == []

    def test_returns_empty_list_for_none(self) -> None:
        # covers: ACS-100i-4
        data = {"covered_by": None}
        assert _extract_covered_by(data) == []

    def test_handles_string_fallback_bracketed(self) -> None:
        # covers: ACS-100i-4
        # Minimal fallback parser returns covered_by as a raw string.
        data = {"covered_by": "[ACS-300h-1, ACS-300h-2]"}
        result = _extract_covered_by(data)
        assert result == ["ACS-300h-1", "ACS-300h-2"]

    def test_handles_string_fallback_empty_brackets(self) -> None:
        # covers: ACS-100i-4
        data = {"covered_by": "[]"}
        assert _extract_covered_by(data) == []


# ---------------------------------------------------------------------------
# _build_id_index()
# ---------------------------------------------------------------------------


class TestBuildIdIndex:
    """Unit tests for _build_id_index()."""

    def test_builds_correct_index(self) -> None:
        # covers: ACS-100i-4
        records = [
            {"id": "ACS-300h", "covered_by": []},
            {"id": "ACS-300h-1", "covered_by": []},
        ]
        index = _build_id_index(records)
        assert "ACS-300h" in index
        assert "ACS-300h-1" in index
        assert len(index) == 2

    def test_skips_records_without_id(self) -> None:
        # covers: ACS-100i-4
        records = [{"title": "no id here"}, {"id": "ACS-100"}]
        index = _build_id_index(records)
        assert list(index.keys()) == ["ACS-100"]

    def test_skips_empty_string_id(self) -> None:
        # covers: ACS-100i-4
        records = [{"id": "  "}, {"id": "ACS-200"}]
        index = _build_id_index(records)
        assert list(index.keys()) == ["ACS-200"]


# ---------------------------------------------------------------------------
# find_orphaned_children() — core logic
# ---------------------------------------------------------------------------


class TestFindOrphanedChildren:
    """Unit tests for find_orphaned_children() — the core orphan detection function."""

    def _make_index_with_orphan(self) -> dict:
        """Build an index where ACS-300h-1 is orphaned (parent covered_by empty)."""
        return {
            "ACS-300h": {"id": "ACS-300h", "covered_by": [], "_path": "/fake/ACS-300h.yaml"},
            "ACS-300h-1": {"id": "ACS-300h-1", "covered_by": [], "_path": "/fake/ACS-300h-1.yaml"},
            "ACS-300h-2": {"id": "ACS-300h-2", "covered_by": [], "_path": "/fake/ACS-300h-2.yaml"},
            "ACS-300h-3": {"id": "ACS-300h-3", "covered_by": [], "_path": "/fake/ACS-300h-3.yaml"},
        }

    def _make_index_all_linked(self) -> dict:
        """Build an index where all children are in their parent's covered_by."""
        return {
            "ACS-300h": {
                "id": "ACS-300h",
                "covered_by": ["ACS-300h-1", "ACS-300h-2", "ACS-300h-3"],
                "_path": "/fake/ACS-300h.yaml",
            },
            "ACS-300h-1": {"id": "ACS-300h-1", "covered_by": [], "_path": "/fake/ACS-300h-1.yaml"},
            "ACS-300h-2": {"id": "ACS-300h-2", "covered_by": [], "_path": "/fake/ACS-300h-2.yaml"},
            "ACS-300h-3": {"id": "ACS-300h-3", "covered_by": [], "_path": "/fake/ACS-300h-3.yaml"},
        }

    def test_detects_orphaned_children(self) -> None:
        # covers: ACS-100i-4
        """Children not in parent covered_by are returned as orphans."""
        index = self._make_index_with_orphan()
        orphans = find_orphaned_children(index, derive_parent_id)
        assert "ACS-300h" in orphans
        orphan_ids = {e["child_id"] for e in orphans["ACS-300h"]}
        assert orphan_ids == {"ACS-300h-1", "ACS-300h-2", "ACS-300h-3"}

    def test_each_orphan_entry_has_required_fields(self) -> None:
        # covers: ACS-100i-4
        """Each orphan dict must contain child_id, parent_id, parent_file."""
        index = self._make_index_with_orphan()
        orphans = find_orphaned_children(index, derive_parent_id)
        for entries in orphans.values():
            for entry in entries:
                assert "child_id" in entry
                assert "parent_id" in entry
                assert "parent_file" in entry

    def test_orphan_entry_parent_id_is_correct(self) -> None:
        # covers: ACS-100i-4
        index = self._make_index_with_orphan()
        orphans = find_orphaned_children(index, derive_parent_id)
        for entry in orphans["ACS-300h"]:
            assert entry["parent_id"] == "ACS-300h"

    def test_orphan_entry_parent_file_is_correct(self) -> None:
        # covers: ACS-100i-4
        index = self._make_index_with_orphan()
        orphans = find_orphaned_children(index, derive_parent_id)
        for entry in orphans["ACS-300h"]:
            assert entry["parent_file"] == "/fake/ACS-300h.yaml"

    def test_returns_empty_when_all_linked(self) -> None:
        # covers: ACS-100i-4
        """No orphans when all children are in their parent's covered_by."""
        index = self._make_index_all_linked()
        orphans = find_orphaned_children(index, derive_parent_id)
        assert orphans == {}

    def test_root_acs_not_treated_as_orphans(self) -> None:
        # covers: ACS-100i-4
        """Root-level ACs (no parent) are never classified as orphans."""
        index = {
            "ACS-300": {"id": "ACS-300", "covered_by": [], "_path": "/fake/ACS-300.yaml"},
        }
        orphans = find_orphaned_children(index, derive_parent_id)
        assert orphans == {}

    def test_partial_coverage_detected(self) -> None:
        # covers: ACS-100i-4
        """Only children absent from covered_by are reported as orphans."""
        index = {
            "ACS-300h": {
                "id": "ACS-300h",
                "covered_by": ["ACS-300h-1"],  # ACS-300h-2 and ACS-300h-3 missing
                "_path": "/fake/ACS-300h.yaml",
            },
            "ACS-300h-1": {"id": "ACS-300h-1", "covered_by": [], "_path": "/fake/ACS-300h-1.yaml"},
            "ACS-300h-2": {"id": "ACS-300h-2", "covered_by": [], "_path": "/fake/ACS-300h-2.yaml"},
            "ACS-300h-3": {"id": "ACS-300h-3", "covered_by": [], "_path": "/fake/ACS-300h-3.yaml"},
        }
        orphans = find_orphaned_children(index, derive_parent_id)
        orphan_ids = {e["child_id"] for e in orphans["ACS-300h"]}
        assert orphan_ids == {"ACS-300h-2", "ACS-300h-3"}
        assert "ACS-300h-1" not in orphan_ids

    def test_child_with_missing_parent_in_index_is_skipped(self) -> None:
        # covers: ACS-100i-4
        """Children whose parent is not in the index are not reported as orphans."""
        index = {
            "ACS-300h-1": {"id": "ACS-300h-1", "covered_by": [], "_path": "/fake/ACS-300h-1.yaml"},
        }
        orphans = find_orphaned_children(index, derive_parent_id)
        assert orphans == {}

    def test_groups_orphans_by_parent(self) -> None:
        # covers: ACS-100i-4
        """Orphans from different parents are grouped under their respective parent IDs."""
        index = {
            "ACS-300h": {"id": "ACS-300h", "covered_by": [], "_path": "/fake/ACS-300h.yaml"},
            "ACS-300h-1": {"id": "ACS-300h-1", "covered_by": [], "_path": "/fake/ACS-300h-1.yaml"},
            "ACS-300i": {"id": "ACS-300i", "covered_by": [], "_path": "/fake/ACS-300i.yaml"},
            "ACS-300i-1": {"id": "ACS-300i-1", "covered_by": [], "_path": "/fake/ACS-300i-1.yaml"},
        }
        orphans = find_orphaned_children(index, derive_parent_id)
        assert "ACS-300h" in orphans
        assert "ACS-300i" in orphans
        assert len(orphans["ACS-300h"]) == 1
        assert len(orphans["ACS-300i"]) == 1


# ---------------------------------------------------------------------------
# main() — CLI integration tests using real YAML files in tmpdir
# ---------------------------------------------------------------------------


class TestMainCliIntegration:
    """Integration tests for main() using temporary YAML files."""

    def test_exits_zero_when_all_clean(self, tmp_path: Path) -> None:
        # covers: ACS-100i-4
        """main() exits 0 when every child is listed in its parent's covered_by."""
        _write_yaml(tmp_path, "ACS-300h.yaml", """\
            id: ACS-300h
            covered_by:
              - ACS-300h-1
              - ACS-300h-2
        """)
        _write_yaml(tmp_path, "ACS-300h-1.yaml", """\
            id: ACS-300h-1
            covered_by: []
        """)
        _write_yaml(tmp_path, "ACS-300h-2.yaml", """\
            id: ACS-300h-2
            covered_by: []
        """)
        result = main(["--ac-root", str(tmp_path)])
        assert result == 0

    def test_exits_one_when_orphans_found(self, tmp_path: Path) -> None:
        # covers: ACS-100i-4
        """main() exits 1 when one or more orphaned children are detected."""
        _write_yaml(tmp_path, "ACS-300h.yaml", """\
            id: ACS-300h
            covered_by: []
        """)
        _write_yaml(tmp_path, "ACS-300h-1.yaml", """\
            id: ACS-300h-1
            covered_by: []
        """)
        _write_yaml(tmp_path, "ACS-300h-2.yaml", """\
            id: ACS-300h-2
            covered_by: []
        """)
        _write_yaml(tmp_path, "ACS-300h-3.yaml", """\
            id: ACS-300h-3
            covered_by: []
        """)
        result = main(["--ac-root", str(tmp_path)])
        assert result == 1

    def test_exits_two_on_missing_ac_root(self, tmp_path: Path) -> None:
        # covers: ACS-100i-4
        """main() exits 2 when the --ac-root directory does not exist."""
        result = main(["--ac-root", str(tmp_path / "nonexistent")])
        assert result == 2

    def test_reports_child_id_parent_id_and_parent_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        # covers: ACS-100i-4
        """Report output includes child AC ID, parent AC ID, and parent file path."""
        parent_file = _write_yaml(tmp_path, "ACS-300h.yaml", """\
            id: ACS-300h
            covered_by: []
        """)
        _write_yaml(tmp_path, "ACS-300h-1.yaml", """\
            id: ACS-300h-1
            covered_by: []
        """)
        main(["--ac-root", str(tmp_path)])
        captured = capsys.readouterr()
        assert "ACS-300h-1" in captured.out
        assert "ACS-300h" in captured.out
        assert str(parent_file) in captured.out

    def test_groups_orphans_by_parent_in_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        # covers: ACS-100i-4
        """Report groups orphaned children under their parent's section heading."""
        _write_yaml(tmp_path, "ACS-300h.yaml", """\
            id: ACS-300h
            covered_by: []
        """)
        _write_yaml(tmp_path, "ACS-300h-1.yaml", """\
            id: ACS-300h-1
            covered_by: []
        """)
        _write_yaml(tmp_path, "ACS-300h-2.yaml", """\
            id: ACS-300h-2
            covered_by: []
        """)
        main(["--ac-root", str(tmp_path)])
        captured = capsys.readouterr()
        # The parent heading must appear before both child IDs.
        parent_idx = captured.out.find("ACS-300h\n")
        child1_idx = captured.out.find("ACS-300h-1")
        child2_idx = captured.out.find("ACS-300h-2")
        assert parent_idx < child1_idx
        assert parent_idx < child2_idx

    def test_empty_store_exits_zero(self, tmp_path: Path) -> None:
        # covers: ACS-100i-4
        """main() exits 0 when the AC store is empty (no YAML files)."""
        result = main(["--ac-root", str(tmp_path)])
        assert result == 0

    def test_at_least_four_orphans_detected(self, tmp_path: Path) -> None:
        # covers: ACS-100i-4
        """Gherkin: at least 4 orphaned children are detected and reported."""
        _write_yaml(tmp_path, "ACS-300h.yaml", """\
            id: ACS-300h
            covered_by: []
        """)
        for i in range(1, 5):
            _write_yaml(tmp_path, f"ACS-300h-{i}.yaml", f"""\
                id: ACS-300h-{i}
                covered_by: []
            """)
        result = main(["--ac-root", str(tmp_path)])
        assert result == 1

    def test_yaml_load_error_exits_two(self, tmp_path: Path) -> None:
        # covers: ACS-100i-4
        """main() exits 2 when a YAML file cannot be parsed."""
        bad_file = tmp_path / "ACS-999h.yaml"
        bad_file.write_bytes(b"\xff\xfe bad utf-8 \xc0\xc1")
        result = main(["--ac-root", str(tmp_path)])
        assert result == 2


# ---------------------------------------------------------------------------
# _load_ac() edge cases
# ---------------------------------------------------------------------------


class TestLoadAc:
    """Unit tests for _load_ac() file loading."""

    def test_loads_valid_yaml(self, tmp_path: Path) -> None:
        # covers: ACS-100i-4
        p = _write_yaml(tmp_path, "ACS-300h.yaml", """\
            id: ACS-300h
            covered_by: []
        """)
        record = _load_ac(p)
        assert record is not None
        assert record["id"] == "ACS-300h"

    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        # covers: ACS-100i-4
        result = _load_ac(tmp_path / "nonexistent.yaml")
        assert result is None

    def test_injects_path_field(self, tmp_path: Path) -> None:
        # covers: ACS-100i-4
        p = _write_yaml(tmp_path, "ACS-300h.yaml", "id: ACS-300h\ncovered_by: []\n")
        record = _load_ac(p)
        assert record is not None
        assert "_path" in record
        assert record["_path"] == str(p)
