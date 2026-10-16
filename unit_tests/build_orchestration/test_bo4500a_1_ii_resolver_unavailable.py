"""
MODULE: unit_tests/build_orchestration/test_bo4500a_1_ii_resolver_unavailable.py
GOAL: BO-4500a-1-ii fails closed when the parent resolver cannot be loaded.

The step finds a named AC record's structural parent through
ac_store/ac_parent_id.py, looked up beside the script (deployed layout) or in the
source tree. When neither is present, committing the named children without their
edited parent would recreate KI-BO-20260928 (the edited parent left unstaged)
while reporting success. These tests run the REAL step from an isolated copy that
has no resolver beside it -- the shape of a broken deployment -- and assert it
refuses instead, and that a request naming no AC record is unaffected.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _commit_step_support import STEP, StepScenario  # noqa: E402

FOLDER = "docs/acceptance-criteria/reliable-builds/BP-100-reliable-builds"
CHILD = "BP-100k-4-iv"
PARENT = "BP-100k-4"


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


class TestParentResolverUnavailable(unittest.TestCase):
    def setUp(self) -> None:
        # <tmp>/isolated/a/b/commit_changes.py: neither b/ac_store/ nor
        # isolated/scripts/ac_store/ exists, so the resolver cannot be found.
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        holder = Path(self._tmp.name) / "isolated" / "a" / "b"
        holder.mkdir(parents=True)
        self.isolated_step = holder / "commit_changes.py"
        shutil.copy2(STEP, self.isolated_step)

    def _run_isolated(self, sc: StepScenario, paths: list[str]) -> dict:
        proc = subprocess.run(
            [sys.executable, str(self.isolated_step), "--message-file", str(sc.message_file), *paths],
            cwd=sc.repo,
            env=sc.env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError:
            self.fail(f"step stdout was not one JSON object: rc={proc.returncode} {proc.stdout!r} {proc.stderr[-400:]!r}")

    def test_named_ac_record_without_resolver_is_refused_not_committed(self):
        # covers: BO-4500a-1-ii
        # angle: failure
        """AC BO-4500a-1-ii: no resolver + a named AC child -> refused, nothing committed."""
        sc = StepScenario(self)
        sc.seed_and_commit({_rel(PARENT): _record(PARENT, None, [])})
        sc.write(_rel(CHILD), _record(CHILD, PARENT, []))
        sc.write(_rel(PARENT), _record(PARENT, None, [CHILD]))
        commits_before = sc.commit_count()

        answer = self._run_isolated(sc, [_rel(CHILD)])

        self.assertEqual(answer.get("status"), "refused", answer)
        self.assertEqual(answer.get("reason_code"), "step_parent_resolver_unavailable", answer)
        self.assertIn(_rel(CHILD), answer.get("reason") or "")
        self.assertEqual(sc.commit_count(), commits_before, "a commit was recorded")
        self.assertEqual(sc.staged_names(), [], "the shared index was changed")

    def test_request_naming_no_ac_record_still_commits_without_resolver(self):
        # covers: BO-4500a-1-ii
        # angle: boundary
        """AC BO-4500a-1-ii: with no AC record named, a missing resolver changes nothing."""
        sc = StepScenario(self)
        sc.seed_and_commit({"src/a.py": "x = 1\n"})
        sc.write("src/a.py", "x = 2\n")

        answer = self._run_isolated(sc, ["src/a.py"])

        self.assertEqual(answer.get("status"), "committed", answer)
        self.assertEqual(sc.head_files(), ["src/a.py"])


if __name__ == "__main__":
    unittest.main()
