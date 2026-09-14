"""
MODULE: unit_tests/commit_guardian/test_bo_2500b_1_ii_composite_levels.py
GOAL: RED test stubs for BO-2500b-1-ii — check_staged_done_proofs must treat a done
    L0/L1 composite AC as proven by its own done-and-covered children, rather than
    demanding a "# covers: <composite-id>" tag the composite can never legitimately
    carry (its implementation lives under each child's own covers tag by
    construction, per the ac-fulfillment-gate model).

=== Bug being reproduced ===

    Location: templates/scripts/commit_guardian/check_done_proof.py,
    check_staged_done_proofs(), the per-AC loop (~lines 389-419).

    check_staged_done_proofs has NO level-awareness at all: for every staged AC
    whose work_status is "done" it requires a "# covers: <ac_id>" (or
    "// covers: <ac_id>") tag naming THAT EXACT id somewhere under test_root — with
    no exception for L0/L1 composites, whose behaviour is proven by their children,
    not by a tag of their own. Observed live 2026-09-07 committing GE-127b (an L1
    whose only child GE-127b-1 was itself done and tagged): the commit was refused
    until a "# covers: GE-127b" tag was hand-added to a test purely to satisfy this
    check. The same wall was hit again on GE-127a.

=== Desired behaviour (this AC) ===

    - A done L0/L1 composite whose every covered_by child is itself done AND
      covered produces NO violation for the composite — without needing a tag
      naming the composite's own id.
    - A done L0/L1 composite with an unproven child (not done, or done but
      uncovered) STILL produces a violation, and that violation names the
      unproven child — composites are never skipped unconditionally (that would
      admit the ACD-400a falsely-done-composite defect, 20 recorded instances).
    - A done L2/L3 leaf AC with no covers tag STILL produces the existing,
      unchanged violation message — the leaf path is not weakened.

=== Mocking strategy ===

    None. This exercises the real check_staged_done_proofs entry point against
    real on-disk AC YAML records (built with yaml.safe_dump, not hand-typed
    literals — fixture-authenticity mandate) and a real test tree containing
    real "# covers:" tags. A direct-import unit test of a helper would not be
    sufficient: the defect is that the function has no notion of level at all,
    so the fix must be observed through the exact code path the pre-commit hook
    actually runs.

=== Import path note ===

    The scripts/commit_guardian symlink in this worktree is broken (points at a
    removed worktree). The canonical source is templates/scripts/commit_guardian,
    which is what build.py deploys from — this file adds that path to sys.path.

=== Red baseline ===

    test_done_composite_with_all_children_covered_is_not_a_violation: RED
        (AssertionError) — current code has no level-awareness and flags the
        composite because no "# covers: <composite-id>" tag exists, even though
        its only child is done and covered.
    test_done_composite_with_unproven_child_is_still_a_violation: RED
        (AssertionError) — current code DOES flag the composite (accidentally
        correct outcome), but its reason string never names the unproven child,
        because the function has no concept of covered_by at all.
    test_done_leaf_without_covers_tag_still_violates_with_unchanged_message:
        expected to already PASS against current code (regression pin proving
        the leaf path is untouched by the fix) — flagged in red_baseline as
        "passes immediately" per the negative-control convention.
"""
from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Repo path wiring
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
# Use the templates source path — scripts/commit_guardian symlink is broken
# in this worktree (points to a removed worktree). The canonical source is
# templates/scripts/commit_guardian, which is what build.py deploys from.
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_AC_STORE_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_COMMIT_GUARDIAN_DIR))
sys.path.insert(0, str(_AC_STORE_DIR))

from check_done_proof import check_staged_done_proofs  # noqa: E402


# ---------------------------------------------------------------------------
# Shared fixture helpers (yaml.safe_dump — fixture-authenticity mandate)
# ---------------------------------------------------------------------------


def _write_ac(
    group_dir: Path,
    ac_id: str,
    *,
    level: str = "L2",
    work_status: str = "done",
    covered_by: list[str] | None = None,
) -> Path:
    """Write a minimal AC YAML using yaml.safe_dump into a real store-shaped dir.

    Composite and child ACs are written as SIBLINGS in the same *group_dir*,
    mirroring the real store layout (e.g.
    docs/acceptance-criteria/build-orchestration/BO-2500-mechanical-done-proof/
    holds BO-2500b-1-ii.yaml alongside its sibling records) — this is the
    on-disk shape any level-aware resolution of a composite's children must
    work against.

    Args:
        group_dir: Directory shared by a composite and its children.
        ac_id: Identifier for the AC.
        level: AC level ("L0"/"L1" for composites, "L2"/"L3" for leaves).
        work_status: AC work status.
        covered_by: List of child AC ids this AC's fulfilment derives from.

    Returns:
        Path to the written YAML file.
    """
    group_dir.mkdir(parents=True, exist_ok=True)
    path = group_dir / f"{ac_id}.yaml"
    data: dict = {
        "id": ac_id,
        "title": f"Synthetic test AC {ac_id}",
        "component": "build-orchestration",
        "level": level,
        "status": "active",
        "work_status": work_status,
        "readiness": "approved",
        "priority": "medium",
        "depends_on": [],
        "amended_by": [],
        "covered_by": covered_by or [],
        "implemented_by": [],
        "superseded_by": None,
    }
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _write_py_test(test_root: Path, filename: str, content: str) -> Path:
    """Write a Python test file (with real '# covers:' tags) to test_root."""
    test_root.mkdir(parents=True, exist_ok=True)
    path = test_root / filename
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# BO-2500b-1-ii — composite (L0/L1) fulfilment is derived from children
# ---------------------------------------------------------------------------


class TestDoneProofCompositeLevelAwareness(unittest.TestCase):
    """BO-2500b-1-ii: a done composite is proven by its children, not its own tag."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        # Real store shape: docs/acceptance-criteria/<component>/<group>/
        self.group_dir = (
            root / "docs" / "acceptance-criteria" / "build-orchestration" / "grp"
        )
        self.test_root = root / "unit_tests"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_done_composite_with_all_children_covered_is_not_a_violation(self) -> None:
        # covers: BO-2500b-1-ii
        # angle: real_artifact
        """A done L1 whose only child is done and carries a '# covers: <child-id>'
        tag in the test tree must produce NO violation for the composite itself,
        even though no tag anywhere names the composite's own id.

        RED mechanism: check_staged_done_proofs has no level-awareness, so it
        demands "# covers: BO-9001a" and, finding none, flags the composite
        anyway — even though its only child is done and properly covered.
        """
        composite_id = "BO-9001a"
        child_id = "BO-9001a-1"
        composite_path = _write_ac(
            self.group_dir,
            composite_id,
            level="L1",
            work_status="done",
            covered_by=[child_id],
        )
        _write_ac(
            self.group_dir,
            child_id,
            level="L2",
            work_status="done",
            covered_by=[],
        )

        # Real covers tag for the CHILD only — never one naming the composite.
        _write_py_test(
            self.test_root,
            "test_child_only_covers_tag.py",
            f"""\
            def test_child_behaviour():
                # covers: {child_id}
                assert True
            """,
        )

        violations = check_staged_done_proofs(
            [composite_path],
            test_root=self.test_root,
        )
        ac_ids = [v.get("ac_id", "") for v in violations]
        self.assertNotIn(
            composite_id,
            ac_ids,
            "check_staged_done_proofs must NOT flag a done L1 composite whose "
            "only child is done and covered — the composite is proven by its "
            f"children, not by a tag naming its own id. Violations: {violations}",
        )

    def test_done_composite_with_unproven_child_is_still_a_violation(self) -> None:
        # covers: BO-2500b-1-ii
        # angle: failure
        """Negative control (tied to the fix, not to an empty fixture): a done
        L1 whose covered_by child is NOT done must still be flagged, and the
        violation's reason must name the unproven child — proving composites
        are never skipped unconditionally (guards against the ACD-400a
        falsely-done-composite defect, 20 recorded instances in this repo).

        RED mechanism: the current code happens to flag the composite (it flags
        every done AC lacking its own tag), but check_staged_done_proofs has no
        concept of covered_by at all, so its reason string can never name the
        unproven child — the assertion on reason content fails.
        """
        composite_id = "BO-9002a"
        child_id = "BO-9002a-1"
        composite_path = _write_ac(
            self.group_dir,
            composite_id,
            level="L1",
            work_status="done",
            covered_by=[child_id],
        )
        # Child exists but is NOT done — the composite's fulfilment is unproven.
        _write_ac(
            self.group_dir,
            child_id,
            level="L2",
            work_status="todo",
            covered_by=[],
        )
        # No covers tags anywhere — irrelevant decoy test file only.
        _write_py_test(
            self.test_root,
            "test_unrelated.py",
            """\
            def test_unrelated_behaviour():
                assert True
            """,
        )

        violations = check_staged_done_proofs(
            [composite_path],
            test_root=self.test_root,
        )
        matching = [v for v in violations if v.get("ac_id") == composite_id]
        self.assertTrue(
            matching,
            "A done L1 composite with an unproven (not-done) child must still "
            f"be reported as a violation. Violations: {violations}",
        )
        self.assertIn(
            child_id,
            matching[0].get("reason", ""),
            "The violation reason for an unproven composite must name the "
            f"unproven child ({child_id}), not just repeat the composite's own "
            f"id. Reason was: {matching[0].get('reason', '')!r}",
        )

    def test_done_leaf_without_covers_tag_still_violates_with_unchanged_message(
        self,
    ) -> None:
        # covers: BO-2500b-1-ii
        # angle: criterion
        """Regression pin: a done L2 (and a done L3) leaf AC with no covers tag
        anywhere must STILL produce a violation carrying the existing, unchanged
        reason string — proving the leaf path is not weakened by this fix.

        This assertion is expected to already hold against the unmodified code
        (it pins current, correct leaf behaviour); it is included so that any
        change which loosens the leaf requirement while fixing composites is
        caught immediately.
        """
        leaf_l2_id = "BO-9003a"
        leaf_l3_id = "BO-9003b"
        leaf_l2_path = _write_ac(
            self.group_dir, leaf_l2_id, level="L2", work_status="done"
        )
        leaf_l3_path = _write_ac(
            self.group_dir, leaf_l3_id, level="L3", work_status="done"
        )
        # test_root exists but has no covers tags at all.
        self.test_root.mkdir(parents=True, exist_ok=True)

        for leaf_id, leaf_path in (
            (leaf_l2_id, leaf_l2_path),
            (leaf_l3_id, leaf_l3_path),
        ):
            violations = check_staged_done_proofs(
                [leaf_path],
                test_root=self.test_root,
            )
            matching = [v for v in violations if v.get("ac_id") == leaf_id]
            self.assertTrue(
                matching,
                f"A done leaf AC ({leaf_id}) with no covers tag anywhere must "
                f"still be reported as a violation. Violations: {violations}",
            )
            expected_reason = (
                f"no '# covers: {leaf_id}' or '// covers: {leaf_id}' "
                f"tag found anywhere under {self.test_root}"
            )
            self.assertEqual(
                matching[0].get("reason", ""),
                expected_reason,
                "The leaf violation reason string must be unchanged by the "
                "composite-level fix.",
            )


if __name__ == "__main__":
    unittest.main()
