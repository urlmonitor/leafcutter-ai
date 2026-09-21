"""
MODULE: unit_tests/commit_guardian/test_bo_2500b_1_iii_covered_by_composite.py
GOAL: RED test stubs for BO-2500b-1-iii — check_staged_done_proofs must treat ANY
    done AC with a non-empty covered_by as a composite proven by its children,
    not only ones whose level is L0/L1.

=== Bug being reproduced ===

    Location: templates/scripts/commit_guardian/check_done_proof.py,
    check_staged_done_proofs() (~line 646: ``if level in ("L0", "L1"):``) and the
    matching recursion guard in _unproven_composite_children (~line 396:
    ``if child_level in ("L0", "L1"):``).

    Both places decide "is this a composite" purely from `level` being L0/L1.
    scripts/ac_store/done_proof.py::_verify_composite_eligible (BO-2500a-6),
    which mark_ac_done.py itself uses to allow marking an AC done, instead
    decides "is this a composite" from `covered_by` being non-empty, at ANY
    level. A done L2 AC with a non-empty covered_by (e.g. UXP-700d-3, whose
    children UXP-700d-3-i and -ii are both done and covered) is therefore
    accepted by mark_ac_done.py but then refused by the pre-commit
    check_staged_done_proofs gate as lacking its own "# covers: <id>" tag — an
    L2 composite can never be committed as done, and
    check-ticket-ac-status-parity then also blocks its ticket from closing.

=== Desired behaviour (this AC) ===

    - A done AC at ANY level (including L2) whose covered_by is non-empty, and
      whose every covered_by child is itself done and covered, produces NO
      violation for the composite itself.
    - A done AC at ANY level with a non-empty covered_by but an unproven child
      STILL produces a violation naming that unproven child — composites are
      never skipped unconditionally (ACD-400a guard).
    - A done AC with an EMPTY covered_by (a true leaf) still requires its own
      "# covers: <id>" tag, with the existing unchanged message — proving the
      fix does not loosen the leaf path.

=== Mocking strategy ===

    None. This exercises the real check_staged_done_proofs entry point against
    real on-disk AC YAML records (built with yaml.safe_dump, not hand-typed
    literals — fixture-authenticity mandate) and a real test tree containing
    real "# covers:" tags.

=== Import path note ===

    The scripts/commit_guardian symlink in this worktree is broken (points at a
    removed worktree). The canonical source is templates/scripts/commit_guardian,
    which is what build.py deploys from — this file adds that path to sys.path.

=== Red baseline ===

    test_done_l2_with_all_children_covered_is_not_a_violation: RED
        (AssertionError) — current code decides "composite" by level in
        ("L0", "L1") only, so a done L2 with covered_by is treated as a leaf,
        falls through to the direct-tag branch, and is flagged for lacking a
        "# covers: <its-own-id>" tag even though both its children are done
        and covered.
    test_done_l2_with_unproven_child_is_still_a_violation: RED
        (AssertionError) — current code DOES flag the L2 (it flags every done
        AC lacking its own direct tag, accidentally landing on a violation),
        but the reason string is the direct-tag leaf message, which never
        names the unproven child — the assertion on reason content fails.
    test_done_l2_with_empty_covered_by_still_requires_own_tag: expected to
        already PASS against current code (regression pin / negative control
        proving the leaf path for a true L2 leaf, with empty covered_by, is
        untouched by the fix) — flagged in red_baseline as "passes
        immediately" per the negative-control convention.
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
    mirroring the real store layout — the on-disk shape any resolution of a
    composite's children must work against.

    Args:
        group_dir: Directory shared by a composite and its children.
        ac_id: Identifier for the AC.
        level: AC level (e.g. "L2" for the composite under test in this file).
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
# BO-2500b-1-iii — an L2 with non-empty covered_by is still a composite
# ---------------------------------------------------------------------------


class TestDoneProofCoveredByDecidesCompositeAtAnyLevel(unittest.TestCase):
    """BO-2500b-1-iii: non-empty covered_by (not level) decides "composite"."""

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

    def test_done_l2_with_all_children_covered_is_not_a_violation(self) -> None:
        # covers: BO-2500b-1-iii
        # angle: real_artifact
        """A done L2 whose covered_by lists children that are each done and
        carry a '# covers: <child-id>' tag produces NO violation, even though
        no tag anywhere names the L2's own id.

        RED mechanism: check_staged_done_proofs only treats level in
        ("L0", "L1") as a composite, so this done L2 falls into the direct-tag
        leaf branch and is flagged for lacking "# covers: BO-9101a" even
        though both its children are done and covered — reproducing the
        UXP-700d-3 symptom.
        """
        composite_id = "BO-9101a"
        child_id_1 = "BO-9101a-i"
        child_id_2 = "BO-9101a-ii"
        composite_path = _write_ac(
            self.group_dir,
            composite_id,
            level="L2",
            work_status="done",
            covered_by=[child_id_1, child_id_2],
        )
        _write_ac(
            self.group_dir, child_id_1, level="L3", work_status="done", covered_by=[]
        )
        _write_ac(
            self.group_dir, child_id_2, level="L3", work_status="done", covered_by=[]
        )

        # Real covers tags for the CHILDREN only — never one naming the L2.
        _write_py_test(
            self.test_root,
            "test_children_only_covers_tags.py",
            f"""\
            def test_child_one_behaviour():
                # covers: {child_id_1}
                assert True


            def test_child_two_behaviour():
                # covers: {child_id_2}
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
            "check_staged_done_proofs must NOT flag a done L2 with non-empty "
            "covered_by whose children are all done and covered — 'composite' "
            "must be decided by non-empty covered_by, not by level. "
            f"Violations: {violations}",
        )

    def test_done_l2_with_unproven_child_is_still_a_violation(self) -> None:
        # covers: BO-2500b-1-iii
        # angle: failure
        """Negative control (tied to the fix, not to an empty fixture): a done
        L2 with a non-empty covered_by whose child is NOT done must still be
        flagged, and the violation's reason must name the unproven child.

        RED mechanism: the current code happens to flag the L2 (via the
        direct-tag branch, since no tag names BO-9102a), but that reason
        string is the leaf message and never names the unproven child — the
        assertion on reason content fails.
        """
        composite_id = "BO-9102a"
        child_id = "BO-9102a-i"
        composite_path = _write_ac(
            self.group_dir,
            composite_id,
            level="L2",
            work_status="done",
            covered_by=[child_id],
        )
        # Child exists but is NOT done — the composite's fulfilment is unproven.
        _write_ac(
            self.group_dir, child_id, level="L3", work_status="todo", covered_by=[]
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
            "A done L2 with non-empty covered_by and an unproven (not-done) "
            f"child must still be reported as a violation. Violations: {violations}",
        )
        self.assertIn(
            child_id,
            matching[0].get("reason", ""),
            "The violation reason for an unproven L2 composite must name the "
            f"unproven child ({child_id}), not the leaf direct-tag message. "
            f"Reason was: {matching[0].get('reason', '')!r}",
        )

    def test_done_l2_with_empty_covered_by_still_requires_own_tag(self) -> None:
        # covers: BO-2500b-1-iii
        # angle: criterion
        """Regression pin / negative control: a done L2 with an EMPTY
        covered_by (a true leaf) still requires its own covers tag and
        produces the existing, unchanged violation message — proving the
        covered_by-decides-composite fix does not loosen true leaves.

        This assertion is expected to already hold against the unmodified
        code (it pins current, correct leaf behaviour); included so any
        change which loosens the true-leaf requirement while fixing
        covered_by-composites is caught immediately.
        """
        leaf_id = "BO-9103a"
        leaf_path = _write_ac(
            self.group_dir,
            leaf_id,
            level="L2",
            work_status="done",
            covered_by=[],
        )
        # test_root exists but has no covers tags at all.
        self.test_root.mkdir(parents=True, exist_ok=True)

        violations = check_staged_done_proofs(
            [leaf_path],
            test_root=self.test_root,
        )
        matching = [v for v in violations if v.get("ac_id") == leaf_id]
        self.assertTrue(
            matching,
            f"A done L2 leaf ({leaf_id}) with an empty covered_by and no "
            f"covers tag anywhere must still be reported as a violation. "
            f"Violations: {violations}",
        )
        expected_reason = (
            f"no '# covers: {leaf_id}' or '// covers: {leaf_id}' "
            f"tag found anywhere under {self.test_root}"
        )
        self.assertEqual(
            matching[0].get("reason", ""),
            expected_reason,
            "The true-leaf (empty covered_by) violation reason string must be "
            "unchanged by the covered_by-decides-composite fix.",
        )

    def test_done_leaf_with_test_path_covered_by_and_own_tag_is_not_a_violation(
        self,
    ) -> None:
        # covers: BO-2500b-1-iii
        # angle: boundary
        """A done AC whose covered_by holds ONLY a test-file path (this store's
        own convention — e.g. BO-2500b-1-iii's real record) is a LEAF, not a
        composite: the test path must never be mistaken for an AC-id child.
        Since the leaf carries its own '# covers: <id>' tag, it produces NO
        violation.

        RED mechanism: the regression under test treats ANY non-empty
        covered_by as proof the AC is a composite, so the test-path entry is
        resolved as a child AC id (it does not resolve to a store record) and
        reported as an unproven child — even though a real covers tag for the
        AC's own id exists.
        """
        leaf_id = "BO-9104a"
        leaf_path = _write_ac(
            self.group_dir,
            leaf_id,
            level="L3",
            work_status="done",
            covered_by=["unit_tests/commit_guardian/test_bo_9104a_fixture.py"],
        )
        _write_py_test(
            self.test_root,
            "test_bo_9104a_fixture.py",
            f"""\
            def test_leaf_behaviour():
                # covers: {leaf_id}
                assert True
            """,
        )

        violations = check_staged_done_proofs(
            [leaf_path],
            test_root=self.test_root,
        )
        ac_ids = [v.get("ac_id", "") for v in violations]
        self.assertNotIn(
            leaf_id,
            ac_ids,
            "A done AC whose covered_by holds only a test-file path is a "
            "leaf, not a composite — the test path must not be treated as "
            f"an unproven AC-id child when the leaf carries its own covers "
            f"tag. Violations: {violations}",
        )

    def test_done_l2_with_ac_children_and_test_path_mixed_covered_by_is_not_a_violation(
        self,
    ) -> None:
        # covers: BO-2500b-1-iii
        # angle: boundary
        """A done L2 whose covered_by mixes done-and-covered AC-id children
        WITH a test-file path produces NO violation — the test-path entry is
        ignored for compositeness (it is not a child to prove), and the
        composite is still proven purely by its real AC-id children.

        RED mechanism: the regression treats the test-path entry as an
        unresolved child AC id and reports it as unproven alongside (or
        instead of) any genuinely unproven child.
        """
        composite_id = "BO-9105a"
        child_id = "BO-9105a-i"
        composite_path = _write_ac(
            self.group_dir,
            composite_id,
            level="L2",
            work_status="done",
            covered_by=[
                child_id,
                "unit_tests/commit_guardian/test_bo_9105a_decoy.py",
            ],
        )
        _write_ac(
            self.group_dir, child_id, level="L3", work_status="done", covered_by=[]
        )
        _write_py_test(
            self.test_root,
            "test_children_only_covers_tags_mixed.py",
            f"""\
            def test_child_behaviour():
                # covers: {child_id}
                assert True
            """,
        )
        # The decoy file named by the test-path covered_by entry — present on
        # disk but carrying no covers tag for the composite or the child;
        # its mere presence in covered_by must not be treated as a child.
        _write_py_test(
            self.test_root,
            "test_bo_9105a_decoy.py",
            """\
            def test_decoy_behaviour():
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
            "A done L2 whose covered_by mixes a done-and-covered AC-id child "
            "with a test-file path must NOT be flagged — the test-path entry "
            f"must be ignored for compositeness. Violations: {violations}",
        )


if __name__ == "__main__":
    unittest.main()
