"""
MODULE: test_done_proof_child_resolution
GOAL: Verify BO-2500a-6-ii — the leaf-or-composite classification is applied at
    every level of the covered_by tree, not only at the top.

BUSINESS CONTEXT: FIELD EVIDENCE — 2026-09-23, CI on PR #862. The required
    Proof-of-done gate failed with "composite BO-400e has no coverable children" and
    the same for BP-1100e-1, while both composites' children were present in the
    status map, done, and covered by passing covers-tagged tests.

    Cause: _resolve_all_child_ids's recursive step branched on `if child_covered_by:`
    — non-emptiness — while the top-level caller branched on _has_resolvable_child.
    The dominant convention for a LEAF in this store is to record its test files in
    covered_by, so every such leaf looked composite one level down, was recursed into,
    and yielded nothing. BO-2500a-6's M-2 remediation introduced _has_resolvable_child
    for exactly this confusion and applied it at one level only.

ARCHITECTURE: Calls _resolve_all_child_ids directly with a synthetic status map. The
    defect is in that function's classification, so driving the whole oracle would
    reproduce it only at several removes and take minutes rather than milliseconds.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "ac_store"))

import done_proof as dp  # noqa: E402


class TestClassificationIsAppliedAtEveryLevel:
    """BO-2500a-6-ii: the same leaf-vs-composite rule, one level down."""

    def test_children_recording_test_paths_are_leaves_not_empty_composites(self) -> None:
        # covers: BO-2500a-6-ii
        # angle: criterion
        """The case that broke CI: a leaf whose covered_by holds test paths.

        Non-empty covered_by made it look composite; recursing into it found only
        unresolvable paths, so the parent flattened to nothing and could not be proven.
        """
        status_map = {
            "PARENT": {"status": "done", "covered_by": ["CHILD-A", "CHILD-B"]},
            "CHILD-A": {"status": "done", "covered_by": ["unit_tests/test_a.py"]},
            "CHILD-B": {"status": "done", "covered_by": ["unit_tests/test_b.py"]},
        }
        leaves = dp._resolve_all_child_ids(status_map["PARENT"]["covered_by"], status_map)
        assert sorted(leaves) == ["CHILD-A", "CHILD-B"], (
            "children that record their proof as test-file paths are leaves; treating "
            f"them as composites flattens the parent to nothing. Got: {leaves}"
        )

    def test_a_genuine_nested_composite_is_still_expanded(self) -> None:
        # covers: BO-2500a-6-ii
        # angle: boundary
        """This is a correction, not a removal of the recursion.

        A fix that simply stopped recursing would satisfy the other two tests while
        silently dropping real nesting.
        """
        status_map = {
            "PARENT": {"status": "done", "covered_by": ["MID"]},
            "MID": {"status": "done", "covered_by": ["GRANDCHILD"]},
            "GRANDCHILD": {"status": "done", "covered_by": ["unit_tests/test_g.py"]},
        }
        leaves = dp._resolve_all_child_ids(status_map["PARENT"]["covered_by"], status_map)
        assert leaves == ["GRANDCHILD"], (
            f"a child naming resolvable ACs must still be expanded; got {leaves}"
        )

    def test_an_unresolvable_entry_still_contributes_nothing(self) -> None:
        # covers: BO-2500a-6-ii
        # angle: failure
        """BO-2500a-6's own M-2 behaviour is preserved."""
        status_map = {
            "PARENT": {
                "status": "done",
                "covered_by": ["unit_tests/test_direct.py", "CHILD-A"],
            },
            "CHILD-A": {"status": "done", "covered_by": ["unit_tests/test_a.py"]},
        }
        leaves = dp._resolve_all_child_ids(status_map["PARENT"]["covered_by"], status_map)
        assert leaves == ["CHILD-A"], (
            f"an entry resolving to no AC record must contribute nothing; got {leaves}"
        )
