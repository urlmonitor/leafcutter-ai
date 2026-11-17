"""
MODULE: unit_tests/commit_guardian/test_bo_2500a_1_ii_composite_waiver.py
GOAL: RED tests for BO-2500a-1-ii at the composite layer -- a composite whose
    children include a documentation leaf waived from the covers tag
    (test_required false + non-empty test_rationale) must be provable done.

=== Bug ===
    scripts/ac_store/_done_proof_composite.py::_unproven_composite_children
    requires every done leaf child to carry its own "# covers: <child-id>" tag
    and never consults is_covers_tag_waived, so a composite with a waived
    documentation child can never be marked done (found closing DK-600).

=== Fixtures ===
    AC records are written with yaml.safe_dump into a store-shaped temp tree;
    covers tags live in real test files.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_AC_STORE_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_COMMIT_GUARDIAN_DIR))
sys.path.insert(0, str(_AC_STORE_DIR))

from _done_proof_composite import (  # noqa: E402
    _collect_all_covered_ids,
    _unproven_composite_children,
)
from check_done_proof import check_staged_done_proofs  # noqa: E402

_MARK_DONE = _AC_STORE_DIR / "mark_ac_done.py"

COMPOSITE = "BO-9201"
CODE_CHILD = "BO-9201-i"
DOC_CHILD = "BO-9201-ii"


def _write_ac(group_dir: Path, ac_id: str, **overrides) -> Path:
    group_dir.mkdir(parents=True, exist_ok=True)
    data: dict = {
        "id": ac_id,
        "title": f"Synthetic test AC {ac_id}",
        "component": "build-orchestration",
        "level": "L3",
        "status": "active",
        "work_status": "done",
        "readiness": "approved",
        "priority": "medium",
        "depends_on": [],
        "amended_by": [],
        "covered_by": [],
        "implemented_by": [],
        "superseded_by": None,
    }
    data.update(overrides)
    path = group_dir / f"{ac_id}.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


class _StoreCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "docs" / "acceptance-criteria"
        self.group_dir = self.ac_root / "build-orchestration" / "grp"
        self.test_root = root / "unit_tests"
        self.test_root.mkdir(parents=True)
        (self.test_root / "test_code_child.py").write_text(
            textwrap.dedent(
                f"""\
                def test_code_child():
                    # covers: {CODE_CHILD}
                    assert True
                """
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _build(self, *, composite_status="in_progress", doc_overrides=None):
        composite = _write_ac(
            self.group_dir,
            COMPOSITE,
            level="L2",
            work_status=composite_status,
            covered_by=[CODE_CHILD, DOC_CHILD],
        )
        _write_ac(self.group_dir, CODE_CHILD)
        doc = {
            "test_required": False,
            "test_rationale": "Documentation only; no runtime behaviour.",
        }
        doc.update(doc_overrides or {})
        _write_ac(self.group_dir, DOC_CHILD, **doc)
        return composite

    def _unproven(self, composite: Path) -> list[str]:
        data = yaml.safe_load(composite.read_text(encoding="utf-8"))
        return _unproven_composite_children(
            data, self.ac_root, _collect_all_covered_ids(self.test_root)
        )


class TestCompositeWaiver(_StoreCase):
    def test_a_composite_with_a_waived_documentation_child_is_proven(self) -> None:
        # covers: BO-2500a-1-ii
        # angle: criterion
        """Tagged code leaf + waived doc leaf (no tag): nothing unproven."""
        composite = self._build()
        self.assertEqual(self._unproven(composite), [])

    def test_a_documentation_child_without_a_rationale_is_still_unproven(self) -> None:
        # covers: BO-2500a-1-ii
        # angle: discrimination
        """test_required false but empty/missing rationale does not waive.

        Catches a wrong version that waives on test_required alone.
        """
        for rationale in ("", "   ", None):
            with self.subTest(rationale=rationale):
                composite = self._build(doc_overrides={"test_rationale": rationale})
                self.assertEqual(self._unproven(composite), [DOC_CHILD])
        composite = self._build()
        doc_path = self.group_dir / f"{DOC_CHILD}.yaml"
        data = yaml.safe_load(doc_path.read_text(encoding="utf-8"))
        del data["test_rationale"]
        doc_path.write_text(yaml.safe_dump(data), encoding="utf-8")
        self.assertEqual(self._unproven(composite), [DOC_CHILD])

    def test_a_not_done_documentation_child_is_still_unproven(self) -> None:
        # covers: BO-2500a-1-ii
        # angle: failure
        """A waived doc leaf that is not work_status done stays unproven."""
        composite = self._build(doc_overrides={"work_status": "in_progress"})
        self.assertEqual(self._unproven(composite), [DOC_CHILD])

    def test_test_required_true_doc_child_without_tag_is_still_unproven(self) -> None:
        # covers: BO-2500a-1-ii
        # angle: discrimination
        """A rationale alone does not waive; test_required must be exactly False."""
        composite = self._build(doc_overrides={"test_required": True})
        self.assertEqual(self._unproven(composite), [DOC_CHILD])

    def test_a_composite_with_no_ac_id_children_still_fails(self) -> None:
        # covers: BO-2500a-1-ii
        # angle: boundary
        """No AC-id children: the composite reports itself, waiver or not."""
        composite = _write_ac(
            self.group_dir,
            COMPOSITE,
            level="L2",
            covered_by=[],
            test_required=False,
            test_rationale="Docs only.",
        )
        self.assertEqual(self._unproven(composite), [COMPOSITE])


class TestCompositeWaiverEntryPoints(_StoreCase):
    def _run_mark_done(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                str(_MARK_DONE),
                "--ac",
                COMPOSITE,
                "--ac-root",
                str(self.ac_root),
                "--test-root",
                str(self.test_root),
            ],
            capture_output=True,
            text=True,
            cwd=str(_AC_STORE_DIR),
        )

    def test_mark_ac_done_marks_a_composite_whose_doc_children_are_waived(self) -> None:
        # covers: BO-2500a-1-ii
        # angle: reachability
        """mark_ac_done.py CLI marks the composite done; staged check accepts it."""
        composite = self._build(composite_status="in_progress")
        proc = self._run_mark_done()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        data = yaml.safe_load(composite.read_text(encoding="utf-8"))
        self.assertEqual(data["work_status"], "done", proc.stdout + proc.stderr)

        violations = check_staged_done_proofs([composite], test_root=self.test_root)
        self.assertNotIn(COMPOSITE, [v.get("ac_id", "") for v in violations], violations)

    def test_mark_ac_done_still_refuses_doc_child_without_rationale(self) -> None:
        # covers: BO-2500a-1-ii
        # angle: failure
        """Control: without a rationale the composite does not become done."""
        composite = self._build(doc_overrides={"test_rationale": ""})
        self._run_mark_done()
        data = yaml.safe_load(composite.read_text(encoding="utf-8"))
        self.assertNotEqual(data["work_status"], "done")


if __name__ == "__main__":
    unittest.main()
