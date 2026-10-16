"""RED tests for BO-2600b-4 (+ -i, -ii, -iii): a dependency whose covered_by
lists the node is the node's structural parent even when the ids do not show it.

Fixtures are serialised with yaml.safe_dump (fixture-authenticity mandate).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
for _p in (_REPO_ROOT / "scripts" / "build_orchestration", _REPO_ROOT / "scripts" / "ac_store"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from fast_lane import resolve_connected_build_set  # noqa: E402
from ac_parent_id import derive_parent_id  # noqa: E402

_FAST_LANE = _REPO_ROOT / "scripts" / "build_orchestration" / "fast_lane.py"


def _write_ac(root, ac_id, *, level="L3", depends_on=None, covered_by="__omit__", work_status="todo"):
    sub = root / "comp"
    sub.mkdir(parents=True, exist_ok=True)
    data = {
        "id": ac_id,
        "title": f"Synthetic {ac_id}",
        "component": "build-orchestration",
        "level": level,
        "status": "active",
        "work_status": work_status,
        "readiness": "approved",
        "priority": "medium",
        "estimated_complexity": "S",
        "depends_on": depends_on or [],
        "amended_by": [],
        "implemented_by": [],
        "superseded_by": None,
    }
    if covered_by != "__omit__":
        data["covered_by"] = covered_by
    (sub / f"{ac_id}.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")


def _p590_store(root):
    kids = [f"UXP-{n}" for n in (510, 511, 512, 513, 514, 515, 516)]
    _write_ac(root, "UXP-590", level="L1", covered_by=kids)
    for k in kids:
        _write_ac(root, k, depends_on=["UXP-590"] if k == "UXP-512" else [])
    return kids


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def resolve(self, ac, exclude=True):
        return resolve_connected_build_set(ac, ac_root=self.root, exclude_structural_parent=exclude)


class TestRecordedParent(_Base):
    def test_recorded_covered_by_parent_excluded(self):
        # covers: BO-2600b-4
        # angle: criterion
        _p590_store(self.root)
        self.assertIsNone(derive_parent_id("UXP-512"))
        self.assertNotIn("UXP-590", self.resolve("UXP-512"))

    def test_recorded_parent_resolves_to_exactly_target(self):
        # covers: BO-2600b-4
        # angle: criterion
        _p590_store(self.root)
        self.assertEqual(self.resolve("UXP-512"), ["UXP-512"])

    def test_id_shape_parent_still_excluded(self):
        # covers: BO-2600b-4
        # angle: criterion
        _write_ac(self.root, "BO-2600b", level="L1", covered_by=["BO-2600b-4", "BO-2600b-1"])
        _write_ac(self.root, "BO-2600b-1")
        _write_ac(self.root, "BO-2600b-4", depends_on=["BO-2600b"])
        self.assertEqual(self.resolve("BO-2600b-4"), ["BO-2600b-4"])

    def test_cli_reachability_recorded_parent_excluded(self):
        # covers: BO-2600b-4
        # angle: reachability
        _p590_store(self.root)
        proc = subprocess.run(
            [sys.executable, str(_FAST_LANE), "select_connected", "--ac", "UXP-512",
             "--ac-root", str(self.root), "--exclude-structural-parent"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), ["UXP-512"])


class TestGenuineDeps(_Base):
    def _store(self):
        _write_ac(self.root, "T-100", depends_on=["P-100", "Q-100", "R-100", "S-100"])
        _write_ac(self.root, "P-100", level="L1", covered_by=["T-100"])
        _write_ac(self.root, "Q-100", level="L1", covered_by=["Q-101", "Q-102"])
        _write_ac(self.root, "Q-101")
        _write_ac(self.root, "Q-102")
        _write_ac(self.root, "R-100")  # no covered_by field at all
        _write_ac(self.root, "S-100", covered_by=["unit_tests/build_orchestration/test_s.py"])

    def test_dep_not_listing_node_walked_with_descendants(self):
        # covers: BO-2600b-4-i
        # angle: criterion
        self._store()
        out = self.resolve("T-100")
        self.assertTrue({"Q-101", "Q-102"} <= set(out))
        self.assertNotIn("P-100", out)

    def test_dep_without_covered_by_walked_without_error(self):
        # covers: BO-2600b-4-i
        # angle: boundary
        self._store()
        out = self.resolve("T-100")
        self.assertIn("R-100", out)
        self.assertNotIn("P-100", out)

    def test_dep_with_test_file_covered_by_not_parent(self):
        # covers: BO-2600b-4-i
        # angle: boundary
        self._store()
        out = self.resolve("T-100")
        self.assertIn("S-100", out)
        self.assertNotIn("P-100", out)

    def test_recorded_parent_excluded_alongside_genuine_deps(self):
        # covers: BO-2600b-4-i
        # angle: discrimination
        self._store()
        self.assertEqual(
            sorted(self.resolve("T-100")),
            ["Q-101", "Q-102", "R-100", "S-100", "T-100"],
        )


class TestTransitive(_Base):
    def _store(self):
        _write_ac(self.root, "T-200", depends_on=["G-700"])
        _write_ac(self.root, "G-700", depends_on=["H-800"])
        kids = ["G-700", "H-801", "H-802", "H-803", "H-804"]
        _write_ac(self.root, "H-800", level="L1", covered_by=kids)
        for k in kids[1:]:
            _write_ac(self.root, k)

    def test_genuine_prereq_recorded_parent_not_pulled(self):
        # covers: BO-2600b-4-ii
        # angle: criterion
        self._store()
        self.assertEqual(self.resolve("T-200"), ["G-700", "T-200"])

    def test_genuine_prereq_ordered_before_target(self):
        # covers: BO-2600b-4-ii
        # angle: criterion
        self._store()
        out = self.resolve("T-200")
        self.assertIn("G-700", out)
        self.assertLess(out.index("G-700"), out.index("T-200"))
        self.assertEqual(len(out), 2)

    def test_recorded_parent_siblings_absent_transitively(self):
        # covers: BO-2600b-4-ii
        # angle: discrimination
        self._store()
        out = set(self.resolve("T-200"))
        for x in ("H-800", "H-801", "H-802", "H-803", "H-804"):
            self.assertNotIn(x, out)


class TestDefaultUnchanged(_Base):
    def test_default_walks_recorded_parent_as_prereq(self):
        # covers: BO-2600b-4-iii
        # angle: criterion
        kids = _p590_store(self.root)
        out = self.resolve("UXP-512", exclude=False)
        self.assertEqual(sorted(out), sorted(kids))

    def test_default_result_identical_to_pre_change(self):
        # covers: BO-2600b-4-iii
        # angle: failure
        kids = _p590_store(self.root)
        golden = sorted(kids)
        default = self.resolve("UXP-512", exclude=False)
        self.assertEqual(default, resolve_connected_build_set("UXP-512", ac_root=self.root))
        self.assertEqual(sorted(default), golden)
        self.assertNotEqual(default, self.resolve("UXP-512", exclude=True))
