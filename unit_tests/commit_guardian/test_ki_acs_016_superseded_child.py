"""
MODULE: unit_tests/commit_guardian/test_ki_acs_016_superseded_child
GOAL: A superseded covered_by child must not block its composite from being proved
    done, in BOTH the pre-commit path and the CI path (KI-ACS-016).

=== Bug ===
    _unproven_composite_children (pre-commit) and _resolve_all_child_ids (CI)
    ignored supersession, so a withdrawn child (req_status: superseded and/or a
    non-empty superseded_by, work_status not done) refused its composite forever.

=== Fixtures ===
    AC records are written with yaml.safe_dump into a store-shaped temp tree.
    The covers tag lives in a real test file.

=== Contract change (ACS-900d-4) ===
    The old rule withdrew a child on ANY non-empty superseded_by or
    req_status "superseded". The shared predicate (ac_retirement.is_retired) is
    stricter: the child needs a superseded STATUS and EXISTING successors, and
    req_status is ignored. The withdrawn children below therefore use the
    retired shape (status superseded_by, or the older spelling superseded, with
    a successor that exists in the temp store) instead of req_status-only
    records or the nonexistent successor BO-9999. Each test keeps its intent.
"""
from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "templates" / "scripts" / "commit_guardian"))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "ac_store"))

from _done_proof_composite import (  # noqa: E402
    _collect_all_covered_ids,
    _unproven_composite_children,
)
from _done_proof_phase_helpers import _build_ac_status_map  # noqa: E402
from done_proof import _resolve_all_child_ids, _verify_composite_eligible  # noqa: E402

COMPOSITE = "BO-9301"
DONE_CHILD = "BO-9301-i"
GONE_CHILD = "BO-9301-ii"
TODO_CHILD = "BO-9301-iii"
SUCCESSOR = "BO-9302"  # exists in the temp store (written by _Store.setUp)
RETIRED_FORMS: dict[str, dict[str, object]] = {
    "status_superseded_by": {"status": "superseded_by", "superseded_by": [SUCCESSOR]},
    "legacy_status_superseded": {"status": "superseded", "superseded_by": [SUCCESSOR]},
    "status_and_req_status": {
        "status": "superseded_by",
        "req_status": "superseded",
        "superseded_by": [SUCCESSOR],
    },
}
RETIRED = RETIRED_FORMS["status_superseded_by"]


def _write_ac(group_dir: Path, ac_id: str, **overrides) -> Path:
    group_dir.mkdir(parents=True, exist_ok=True)
    data: dict = {
        "id": ac_id,
        "title": f"Synthetic test AC {ac_id}",
        "component": "build-orchestration",
        "level": "L3",
        "status": "active",
        "work_status": "done",
        "covered_by": [],
        "implemented_by": [],
        "superseded_by": None,
    }
    data.update(overrides)
    path = group_dir / f"{ac_id}.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


class _Store(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "docs" / "acceptance-criteria"
        self.group = self.ac_root / "build-orchestration" / "grp"
        self.test_root = root / "unit_tests"
        self.test_root.mkdir(parents=True)
        _write_ac(self.group, SUCCESSOR, work_status="todo")  # the successor every retired child names
        (self.test_root / "test_done_child.py").write_text(
            textwrap.dedent(
                f"""\
                def test_done_child():
                    # covers: {DONE_CHILD}
                    assert True
                """
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _build(self, children: dict[str, dict]) -> dict:
        """Write the composite plus *children* (id -> overrides); return composite data."""
        composite = _write_ac(self.group, COMPOSITE, level="L2", covered_by=list(children))
        for child_id, overrides in children.items():
            _write_ac(self.group, child_id, **overrides)
        return yaml.safe_load(composite.read_text(encoding="utf-8"))

    def _precommit(self, data: dict) -> list[str]:
        return _unproven_composite_children(
            data, self.ac_root, _collect_all_covered_ids(self.test_root)
        )

    def _ci_leaves(self, data: dict) -> list[str]:
        return _resolve_all_child_ids(data["covered_by"], _build_ac_status_map(self.ac_root))


class TestSupersededChildSkipped(_Store):
    def test_superseded_not_done_child_does_not_block_either_path(self) -> None:
        # covers: BO-2500a-1-ii
        # angle: parity
        """KI-ACS-016: one superseded todo child + one done covered child passes both."""
        for name, form in RETIRED_FORMS.items():
            with self.subTest(form=name):
                data = self._build(
                    {DONE_CHILD: {}, GONE_CHILD: {"work_status": "todo", **form}}
                )
                self.assertEqual(self._precommit(data), [])
                self.assertEqual(self._ci_leaves(data), [DONE_CHILD])

    def test_ci_verdict_has_no_uncovered_children_for_superseded_child(self) -> None:
        # covers: BO-2500a-1-ii
        # angle: parity
        """KI-ACS-016: the CI verdict never names the superseded child as uncovered."""
        data = self._build(
            {DONE_CHILD: {}, GONE_CHILD: {"work_status": "todo", **RETIRED}}
        )
        verdict = _verify_composite_eligible(
            COMPOSITE,
            data["covered_by"],
            ac_status_map=_build_ac_status_map(self.ac_root),
            all_tags=[],
            dangling_tags=[],
        )
        self.assertNotIn(GONE_CHILD, verdict["reason"])

    def test_covered_by_keeps_the_superseded_child(self) -> None:
        # covers: BO-2500a-1-ii
        # angle: discrimination
        """KI-ACS-016: skipping must not strip the audit trail from covered_by."""
        data = self._build(
            {DONE_CHILD: {}, GONE_CHILD: {"work_status": "todo", **RETIRED}}
        )
        self.assertEqual(data["covered_by"], [DONE_CHILD, GONE_CHILD])


class TestStillRefused(_Store):
    def test_all_children_superseded_is_refused_on_both_paths(self) -> None:
        # covers: BO-2500a-1-ii
        # angle: boundary
        """KI-ACS-016: nothing left to derive from, so the composite stays refused."""
        data = self._build(
            {
                DONE_CHILD: {"work_status": "todo", **RETIRED},
                GONE_CHILD: {"work_status": "todo", **RETIRED_FORMS["legacy_status_superseded"]},
            }
        )
        self.assertNotEqual(self._precommit(data), [])
        self.assertEqual(self._ci_leaves(data), [])
        verdict = _verify_composite_eligible(
            COMPOSITE,
            data["covered_by"],
            ac_status_map=_build_ac_status_map(self.ac_root),
            all_tags=[],
            dangling_tags=[],
        )
        self.assertFalse(verdict["eligible"])

    def test_non_superseded_todo_child_is_refused_and_named_alone(self) -> None:
        # covers: BO-2500a-1-ii
        # angle: failure
        """KI-ACS-016: a superseded child beside a todo child names only the todo child."""
        data = self._build(
            {
                DONE_CHILD: {},
                GONE_CHILD: {"work_status": "todo", **RETIRED},
                TODO_CHILD: {"work_status": "todo"},
            }
        )
        self.assertEqual(self._precommit(data), [TODO_CHILD])
        self.assertEqual(self._ci_leaves(data), [DONE_CHILD, TODO_CHILD])


if __name__ == "__main__":
    unittest.main()
