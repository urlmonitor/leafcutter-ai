"""
MODULE: unit_tests/build_orchestration/test_bo4500a_1_ii_structural_parent.py
GOAL: RED tests for BO-4500a-1-ii -- a parent AC record the work edited goes in
      with the child records that changed it (exactly one hop, never a sibling or
      grandparent).

Production target: templates/scripts/commit_changes.py (does not exist yet).
AC fixtures are written with yaml.safe_dump (the real serializer), never typed.
The real_artifact test installs the REAL check_ac_parent_covered_by hook as the
scratch repo's pre-commit check.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _commit_step_support import REAL_COVERED_BY_HOOK, REPO_ROOT, StepScenario  # noqa: E402

FOLDER = "docs/acceptance-criteria/reliable-builds/BP-100-reliable-builds"
CHILDREN = ["BP-100k-4-iv", "BP-100k-4-v", "BP-100k-4-vi", "BP-100k-4-vii"]
PARENT = "BP-100k-4"
GRANDPARENT = "BP-100k"
SIBLING = "BP-100k-3"


def _rel(ac_id: str) -> str:
    return f"{FOLDER}/{ac_id}.yaml"


def _record(ac_id: str, depends_on: str | None, covered_by: list[str]) -> str:
    data = {
        "id": ac_id,
        "title": f"fixture record {ac_id}",
        "level": "L3",
        "depends_on": [depends_on] if depends_on else [],
        "covered_by": covered_by,
    }
    return yaml.safe_dump(data, sort_keys=False)


def _scenario(case: unittest.TestCase, parent_modified: bool = True) -> StepScenario:
    """Committed parent/grandparent/sibling records; four NEW untracked children."""
    sc = StepScenario(case)
    sc.seed_and_commit(
        {
            _rel(GRANDPARENT): _record(GRANDPARENT, None, [PARENT, SIBLING]),
            _rel(PARENT): _record(PARENT, GRANDPARENT, []),
            _rel(SIBLING): _record(SIBLING, GRANDPARENT, []),
        }
    )
    for child in CHILDREN:
        sc.write(_rel(child), _record(child, PARENT, []))
    if parent_modified:
        sc.write(_rel(PARENT), _record(PARENT, GRANDPARENT, list(CHILDREN)))
    return sc


class TestStructuralParentInclusion(unittest.TestCase):
    def test_modified_parent_is_committed_with_its_named_children(self):
        # covers: BO-4500a-1-ii
        # angle: criterion
        """AC BO-4500a-1-ii: four named children + modified parent -> five records committed."""
        sc = _scenario(self)
        answer = sc.run_step([_rel(c) for c in CHILDREN])
        self.assertEqual(answer.get("status"), "committed", answer)
        expected = sorted(_rel(c) for c in [*CHILDREN, PARENT])
        self.assertEqual(sc.head_files(), expected)
        self.assertEqual(sorted(answer.get("paths") or []), expected)
        self.assertEqual(answer.get("added_parents"), [_rel(PARENT)])
        self.assertIn(PARENT, sc.committed_text(_rel(PARENT)))

    def test_covered_by_check_sees_the_edited_parent(self):
        # covers: BO-4500a-1-ii
        # angle: real_artifact
        """AC BO-4500a-1-ii: the REAL covered_by hook passes because it was given the edited parent."""
        sc = _scenario(self)
        # Precondition (non-vacuity): with the parent NOT staged and its committed
        # copy lacking the back-link, the real hook must reject a staged child.
        probe = _scenario(self, parent_modified=False)
        probe.git("add", "--", _rel(CHILDREN[0]))
        verdict = subprocess.run(
            [sys.executable, str(REAL_COVERED_BY_HOOK)],
            cwd=probe.repo,
            env={**probe.env, "PYTHONPATH": str(REPO_ROOT)},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            verdict.returncode, 1, f"fixture hook did not reject: {verdict.stdout}{verdict.stderr}"
        )

        sc.install_hook(f"PYTHONPATH={REPO_ROOT} exec {sys.executable} {REAL_COVERED_BY_HOOK}\n")
        answer = sc.run_step([_rel(c) for c in CHILDREN])
        self.assertEqual(answer.get("status"), "committed", answer)
        self.assertEqual(answer.get("added_parents"), [_rel(PARENT)])
        committed_parent = sc.committed_text(_rel(PARENT))
        self.assertEqual(
            sorted(yaml.safe_load(committed_parent)["covered_by"]), sorted(CHILDREN)
        )

    def test_unmodified_parent_is_not_staged(self):
        # covers: BO-4500a-1-ii
        # angle: boundary
        """AC BO-4500a-1-ii: with the parent unmodified, only the four children are committed."""
        sc = _scenario(self, parent_modified=False)
        answer = sc.run_step([_rel(c) for c in CHILDREN])
        self.assertEqual(answer.get("status"), "committed", answer)
        self.assertEqual(sc.head_files(), sorted(_rel(c) for c in CHILDREN))
        self.assertEqual(answer.get("added_parents"), [])
        self.assertEqual(sc.staged_names(), [])
        self.assertEqual(len(answer.get("paths") or []), 4)

    def test_modified_non_parent_sibling_stays_out(self):
        # covers: BO-4500a-1-ii
        # angle: discrimination
        """AC BO-4500a-1-ii: naming BP-100k-4-iv only, a modified BP-100k-3 is not committed.

        Wrong versions this must catch: adding every modified record in the folder
        (sibling BP-100k-3), and adding the grandparent (BP-100k) as well.
        """
        sc = _scenario(self)
        sc.write(_rel(SIBLING), _record(SIBLING, GRANDPARENT, ["BP-100k-3-i"]))
        sc.write(_rel(GRANDPARENT), _record(GRANDPARENT, None, [PARENT, SIBLING, "extra"]))
        sibling_bytes = sc.read(_rel(SIBLING))
        answer = sc.run_step([_rel(CHILDREN[0])])
        self.assertEqual(answer.get("status"), "committed", answer)
        # exactly one hop: the named child plus its direct parent, nothing else
        self.assertEqual(sc.head_files(), sorted([_rel(CHILDREN[0]), _rel(PARENT)]))
        self.assertEqual(answer.get("added_parents"), [_rel(PARENT)])
        status = sc.porcelain()
        self.assertEqual(status.get(_rel(SIBLING)), " M", "sibling was staged or committed")
        self.assertEqual(status.get(_rel(GRANDPARENT)), " M", "grandparent was staged or committed")
        self.assertEqual(sc.read(_rel(SIBLING)), sibling_bytes)


if __name__ == "__main__":
    unittest.main()
