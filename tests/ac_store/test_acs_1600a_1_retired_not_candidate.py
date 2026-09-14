"""ACS-1600a-1 — a retired requirement is not offered as something to change.

Lives in its own file rather than in test_cross_reference_audit.py because
adding it there took that file from under the 400-line limit to 435, and
check-file-size correctly refused the commit. Splitting is the remedy that
gate asks for; this repo already names test files per-AC elsewhere
(test_bo_2900d_1_*.py, test_ge_127a_1_*.py), so the split follows an existing
convention rather than inventing one.
"""

from __future__ import annotations

from scripts.ac_store.cross_reference_audit import _filter_todo_acs


class TestRetiredRequirementIsNotAnEligibleCandidate:
    """ACS-1600a-1: A retired requirement is not offered as something to change."""

    def test_retired_requirement_is_not_an_eligible_candidate(self):
        # covers: ACS-1600a-1
        # angle: criterion
        """_filter_todo_acs must exclude retired (status: deprecated) records even
        though retirement changes neither work_status nor implemented_by.

        THE NEGATIVE ARM IS LOAD-BEARING: the two fixture records are identical
        in every field the selector reads today (work_status: todo,
        implemented_by: []) and differ ONLY by `status`. This forces the test to
        be about lifecycle status specifically — a selector that returns nothing
        at all, or that drops a record for some unrelated reason, cannot pass
        this test, because the active record must also be asserted present.

        Chose NOT to parametrize over `superseded` / `superseded_by` as well:
        the AC's criteria names only the active/retired distinction in the
        abstract, and the fix treats all non-active statuses identically via a
        single membership check against `_RETIRED_AC_STATUSES`, so a third and
        fourth row would exercise the same code path without adding
        distinguishing signal.
        """
        active_ac = {
            "id": "ACS-TEST-ACTIVE",
            "title": "A requirement still in force",
            "component": "ac-store",
            "status": "active",
            "work_status": "todo",
            "implemented_by": [],
        }
        deprecated_ac = {
            "id": "ACS-TEST-DEPRECATED",
            "title": "A requirement that has been retired",
            "component": "ac-store",
            "status": "deprecated",
            "work_status": "todo",
            "implemented_by": [],
        }

        result = _filter_todo_acs([active_ac, deprecated_ac])
        result_ids = [ac.get("id") for ac in result]

        assert "ACS-TEST-DEPRECATED" not in result_ids, (
            "retired (status: deprecated) AC must be excluded from backfill "
            f"candidates, but was returned: {result_ids}"
        )
        assert "ACS-TEST-ACTIVE" in result_ids, (
            "active AC must still be returned as an eligible candidate — its "
            "absence would mean the filter over-excludes rather than "
            f"correctly discriminating on status: {result_ids}"
        )
