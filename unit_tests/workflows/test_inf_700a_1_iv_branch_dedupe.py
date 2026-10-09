"""
MODULE: unit_tests/workflows/test_inf_700a_1_iv_branch_dedupe.py
GOAL: Behavioural tests, through the REAL completion_routing_cli.py in a real
    subprocess against real scratch git, for the multi-commit shape an epic
    drive gives the knowledge-routing step (INF-700a-1-iv): ticket-supervisor
    runs stage -> commit-by-name -> observe around EVERY ticket's commit, so
    one branch sees N stages before anything merges.

    Before this AC, `stage` skipped only records whose text was already on
    origin/main, so ticket 2 re-appended every learning ticket 1 had already
    committed on the branch: N tickets, N copies (INF-700a-1's "a second run
    over the same records adds nothing further" broken on every epic PR).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

import workflows._inf700a5_fixtures as fx  # noqa: E402

_CLI = fx._REPO_ROOT / "scripts" / "knowledge" / "completion_routing_cli.py"
_DEST = "memory/inf700a1iv_destination.md"
_LEARNING = "epic drive learning, routed once"


class _EpicBranchCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.install = fx.init_install_repo(self.root / "install", {_DEST: "seed\n"})
        self.sink = self.root / "install-logs" / "knowledge_emissions.jsonl"
        self.state = self.root / "install-logs" / "harvest_state.json"
        self.wt = fx.clone_working_dir(self.install, self.root / "wt-epic", "epic")
        fx.emit(
            self.sink, agent="python-coder", component="infrastructure",
            destination=_DEST, entry_kind="memory-project", text=_LEARNING,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def cli(self, *args: str) -> dict:
        proc = subprocess.run(
            [sys.executable, str(_CLI), *args, "--sink", str(self.sink), "--state", str(self.state)],
            capture_output=True, text=True, timeout=60, check=False,
        )
        self.assertEqual(proc.returncode, 0, f"CLI must exit 0 (fail-open): {proc.stderr}")
        return json.loads([ln for ln in proc.stdout.splitlines() if ln.strip()][-1])

    def ticket(self, n: int, *, commit_ok: bool = True) -> dict:
        """One epic ticket's commit phase, as SKILL.md section 5.9 orders it:
        stage, commit the ticket's own file plus the manifest BY NAME, observe."""
        staged = self.cli("stage", "--working-dir", str(self.wt))
        if commit_ok:
            (self.wt / f"ticket_{n}.txt").write_text(f"ticket {n}\n", encoding="utf-8")
            fx.commit_paths(self.wt, [f"ticket_{n}.txt", *staged["manifest"]], f"ticket {n}")
        observed = self.cli(
            "observe", "--working-dir", str(self.wt), "--commit-status", "ok" if commit_ok else "failed"
        )
        return {"staged": staged, "observed": observed}

    def copies_in_worktree(self) -> int:
        return fx.read_file(self.wt / _DEST).count(_LEARNING)


class TestNTicketsOnOneBranchLeaveOneCopy(_EpicBranchCase):
    def test_three_ticket_commits_on_one_branch_merge_exactly_one_copy(self) -> None:
        # covers: INF-700a-1-iv, INF-700a-1
        # angle: criterion
        runs = [self.ticket(n) for n in (1, 2, 3)]
        self.assertEqual(runs[0]["observed"]["written"], 1, runs[0])
        fx.merge_into_install(self.install, self.wt, "epic")
        self.assertEqual(fx.read_file(self.install / _DEST).count(_LEARNING), 1)

    def test_a_record_already_on_head_is_skipped_unclaimed_and_counted(self) -> None:
        # covers: INF-700a-1-iv
        # angle: boundary
        self.ticket(1)
        second = self.ticket(2)
        self.assertEqual(second["staged"]["manifest"], [], second)
        self.assertEqual(second["staged"]["written"], 0, second)
        self.assertEqual(second["staged"]["already_on_branch"], 1, second)
        self.assertEqual(second["observed"]["already_on_branch"], 1, second)
        self.assertEqual(self.copies_in_worktree(), 1)
        state = json.loads(self.state.read_text()) if self.state.exists() else []
        self.assertEqual(state, [], "text on the branch is not on origin/main: nothing is claimed")

    def test_the_second_ticket_adds_nothing_to_the_destination_file(self) -> None:
        # covers: INF-700a-1
        # angle: boundary
        self.ticket(1)
        before = (self.wt / _DEST).read_bytes()
        self.ticket(2)
        self.assertEqual((self.wt / _DEST).read_bytes(), before)


class TestAnUncommittedLeftoverIsCarriedNotDuplicated(_EpicBranchCase):
    def test_a_write_left_by_a_refused_commit_is_restaged_without_a_second_append(self) -> None:
        # covers: INF-700a-1-iv
        # angle: failure
        refused = self.ticket(1, commit_ok=False)
        self.assertEqual(refused["observed"]["written"], 0, refused)
        self.assertEqual(self.copies_in_worktree(), 1)
        retry = self.ticket(2)
        self.assertEqual(retry["staged"]["manifest"], [_DEST], "the leftover must ride this commit")
        self.assertEqual(self.copies_in_worktree(), 1, "no second append")
        self.assertEqual(retry["observed"]["written"], 1, retry)
        self.assertTrue(fx._run_git(["show", f"HEAD:{_DEST}"], self.wt).stdout.count(_LEARNING) == 1)


if __name__ == "__main__":
    unittest.main()
