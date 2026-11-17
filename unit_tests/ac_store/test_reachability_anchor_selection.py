"""
MODULE: unit_tests/ac_store/test_reachability_anchor_selection.py
GOAL: Guard the real-store anchor selector used by
    test_derived_test_reachability_floor.py so selection never depends on where
    a record happens to sort.
WHY: An un-enriched draft (ACD-1600c-4-v) that sorted first became the anchor;
    its generated ticket legitimately carried no ``## Test Requirements`` block.
    Synthetic records are passed THROUGH THE SELECTOR only; the anchor the
    primary gates use is still drawn from the real store.

COVERS: UNKNOWN (no AC authored for this change)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from _reachability_anchor import declares_implementation_py  # noqa: E402
from test_derived_test_reachability_floor import _find_fallback_anchor  # noqa: E402


class TestFallbackAnchorSelection:
    """The anchor selector must not depend on where a record sorts."""

    _CRITERIA = "Given a\nWhen b\nThen c\nAnd d\nThen e\n"

    def _record(self, rec_id: str, doc_links: list) -> dict:
        return {
            "id": rec_id,
            "assigned_agent": "python-coder",
            "readiness": "draft",
            "criteria": self._CRITERIA,
            "doc_links": doc_links,
        }

    def test_unenriched_draft_sorting_first_is_not_the_anchor(self) -> None:
        # covers: UNKNOWN
        """A draft whose only edit surface is a doc is skipped for a later code AC.

        Mirrors ACD-1600c-4-v: coder-assigned, no test_spec, several Then
        clauses, but its generated ticket legitimately has no Test Requirements
        block because no implementation .py is in scope.
        """
        draft = self._record(
            "ZZ-1-draft",
            [{"path": "docs/reference/ac-schema.md", "relationship": "modifies"}],
        )
        enriched = self._record(
            "ZZ-2-enriched",
            [{"path": "scripts/ac_store/thing.py", "relationship": "modifies"}],
        )
        records = [(Path("a.yaml"), draft), (Path("b.yaml"), enriched)]

        assert _find_fallback_anchor(records)["id"] == "ZZ-2-enriched"

    def test_doc_test_and_non_edit_links_do_not_count_as_implementation(self) -> None:
        # covers: UNKNOWN
        """Docs, test files, tickets paths and informational links are excluded."""
        for links in (
            [{"path": "docs/x/helper.py", "relationship": "modifies"}],
            [{"path": "scripts/test_thing.py", "relationship": "modifies"}],
            [{"path": "scripts/thing_test.py", "relationship": "modifies"}],
            [{"path": "tickets/t/x.py", "relationship": "creates"}],
            [{"path": "scripts/thing.py", "relationship": "describes"}],
            [{"path": "scripts/thing.yaml", "relationship": "modifies"}],
            [],
        ):
            assert not declares_implementation_py(self._record("ZZ-3", links)), links

    def test_no_qualifying_record_fails_loudly(self) -> None:
        # covers: UNKNOWN
        """With no qualifying record the selector fails naming the condition."""
        draft = self._record(
            "ZZ-4", [{"path": "docs/reference/ac-schema.md", "relationship": "modifies"}]
        )
        with pytest.raises(AssertionError, match="implementation .py declared"):
            _find_fallback_anchor([(Path("a.yaml"), draft)])

    def test_structured_reference_file_path_counts(self) -> None:
        # covers: UNKNOWN
        """A structured it_requirements.reference_file_path to a .py qualifies."""
        record = self._record("ZZ-5", [])
        record["it_requirements"] = {"reference_file_path": "scripts/ac_store/x.py"}
        assert declares_implementation_py(record)
