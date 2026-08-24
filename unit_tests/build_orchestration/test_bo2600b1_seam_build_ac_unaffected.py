"""
MODULE: unit_tests/build_orchestration/test_bo2600b1_seam_build_ac_unaffected.py
GOAL: RED-safe seam test for BO-2600b-1 (angle: seam) — the caller-side change
      to templates/workflows-js/fast-lane-ship.js (adding
      --exclude-structural-parent to its Resolve-phase select_connected
      invocation) must NOT touch:

        1. resolve_connected_build_set's own default (BO-2600a-1 fixed it at
           exclude_structural_parent=False as a backward-compatibility
           invariant — covered elsewhere by
           test_default_false_preserves_existing_behavior, which this test
           does not replace or duplicate).
        2. templates/agents/build-ac.md's own invocation, which already
           passes --exclude-structural-parent unconditionally
           (line ~333, BO-2600a) and whose behaviour is settled.

This is a Python-level / real-file seam test, not a JS-harness test — it
verifies the OTHER caller and the library default are provably undisturbed
by the fast-lane-ship.js change under test.

=== Fixture-authenticity ===

The AC YAML fixture is written with yaml.safe_dump (never hand-typed),
reusing the exact "Fixture A" geometry from
unit_tests/workflows/test_bo2600b_lane_scope_aiming.py (target leaf lists
its own structural parent as a prerequisite; that parent lists ITS parent;
two further not-done leaves sit beneath the grandparent).

=== Red baseline ===

This test is expected to be GREEN both before and after python-coder's
change lands — that is the point of a seam/regression test: it fails LOUDLY
only if the fast-lane-ship.js change is implemented in the wrong place (i.e.
by mutating resolve_connected_build_set's default, or by touching
build-ac.md). It is included in this red-baseline set per BO-2600b-1's own
test_spec (angle: seam) so a naive fix that changes the library default is
caught immediately rather than discovered later.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_MODULE_DIR = _REPO_ROOT / "scripts" / "build_orchestration"
if str(_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_MODULE_DIR))

from fast_lane import resolve_connected_build_set  # noqa: E402

_BUILD_AC_MD = _REPO_ROOT / "templates" / "agents" / "build-ac.md"


def _write_ac(
    ac_root: Path,
    ac_id: str,
    *,
    level: str,
    work_status: str,
    depends_on: list | None = None,
    covered_by: list | None = None,
) -> Path:
    """Write a minimal, valid AC YAML using yaml.safe_dump (never hand-typed)."""
    subdir = ac_root / "test-component"
    subdir.mkdir(parents=True, exist_ok=True)
    data: dict = {
        "id": ac_id,
        "title": f"Synthetic test AC {ac_id}",
        "component": "build-orchestration",
        "level": level,
        "status": "active",
        "work_status": work_status,
        "readiness": "approved",
        "priority": "medium",
        "estimated_complexity": "S",
        "depends_on": depends_on if depends_on is not None else [],
        "covered_by": covered_by if covered_by is not None else [],
        "amended_by": [],
        "implemented_by": [],
        "superseded_by": None,
    }
    path = subdir / f"{ac_id}.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


class TestFastLaneChangeDoesNotAffectBuildAcOrLibraryDefault(unittest.TestCase):
    """BO-2600b-1 seam test: /build-ac and the library default stay unaffected."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "acs" / "docs" / "acceptance-criteria"
        self.ac_root.mkdir(parents=True, exist_ok=True)
        # Same geometry as Fixture A in test_bo2600b_lane_scope_aiming.py.
        _write_ac(self.ac_root, "FLT-900a", level="L1", work_status="todo",
                  covered_by=["FLT-900a-1", "FLT-900a-2", "FLT-900a-3"])
        _write_ac(self.ac_root, "FLT-900a-1", level="L2", work_status="todo",
                  depends_on=["FLT-900a"], covered_by=["FLT-900a-1-i"])
        _write_ac(self.ac_root, "FLT-900a-1-i", level="L3", work_status="todo",
                  depends_on=["FLT-900a-1", "FLT-900b-1"])
        _write_ac(self.ac_root, "FLT-900a-2", level="L2", work_status="todo")
        _write_ac(self.ac_root, "FLT-900a-3", level="L2", work_status="todo")
        _write_ac(self.ac_root, "FLT-900b-1", level="L2", work_status="todo")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_build_ac_resolution_is_unchanged(self) -> None:
        # covers: BO-2600b-1
        """The resolver default and the /build-ac invocation resolve exactly
        as before this change.

        Part 1 — library default: calling resolve_connected_build_set with
        exclude_structural_parent OMITTED must still return the WIDE set
        (default False, BO-2600a-1's backward-compatibility invariant) —
        the fast-lane-ship.js caller decision must not have leaked into the
        library's own default.

        Part 2 — the other caller: templates/agents/build-ac.md must still
        pass --exclude-structural-parent unconditionally at its own call
        site (a real on-disk read, never a fabricated string), exactly as
        it already did under BO-2600a before this ticket's change.
        """
        # Part 1 — the library default is untouched.
        default_result = resolve_connected_build_set(
            "FLT-900a-1-i", ac_root=self.ac_root
        )
        self.assertCountEqual(
            default_result,
            ["FLT-900a-1", "FLT-900b-1", "FLT-900a-1-i", "FLT-900a-2", "FLT-900a-3"],
            "resolve_connected_build_set's default (exclude_structural_parent "
            "omitted) must still resolve the WIDE set — BO-2600a-1 fixed this "
            "default at False as a backward-compatibility invariant that the "
            "fast-lane-ship.js caller decision (BO-2600b-1) must not disturb. "
            f"Got: {default_result}"
        )

        explicit_false_result = resolve_connected_build_set(
            "FLT-900a-1-i", ac_root=self.ac_root, exclude_structural_parent=False
        )
        self.assertCountEqual(
            default_result,
            explicit_false_result,
            "Omitting exclude_structural_parent must be identical to passing "
            "exclude_structural_parent=False explicitly."
        )

        # Part 2 — build-ac.md's own invocation is untouched (real file read).
        self.assertTrue(
            _BUILD_AC_MD.exists(),
            f"templates/agents/build-ac.md must exist at {_BUILD_AC_MD}."
        )
        content = _BUILD_AC_MD.read_text(encoding="utf-8")
        self.assertIn(
            "select_connected --exclude-structural-parent",
            content,
            "templates/agents/build-ac.md must still pass "
            "--exclude-structural-parent unconditionally at its own "
            "select_connected call site (BO-2600a) — this ticket's change to "
            "fast-lane-ship.js must not touch build-ac.md at all."
        )


if __name__ == "__main__":
    unittest.main()
