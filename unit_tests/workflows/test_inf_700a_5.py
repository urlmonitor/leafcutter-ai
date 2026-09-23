"""
MODULE: unit_tests/workflows/test_inf_700a_5.py
GOAL: RED behavioral test baseline for INF-700a-5 — "A learning written
    while work was in flight is still readable after the place that work
    ran in is gone".

AC: docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700a-5.yaml

CONTRACT THIS TEST FILE ESTABLISHES FOR python-coder (TDD: this is the spec):

    `scripts/knowledge/completion_routing.py` must exist and expose
    `stage_completion()` / `confirm_routed()` as described in
    unit_tests/workflows/_inf700a5_fixtures.py's module docstring. The
    durability obligation is proven here with REAL git: a real install
    repo standing in for "the merged tree", a real working-directory clone
    on its own branch, a real `git pull` merge, and a real `shutil.rmtree`
    teardown of the working directory BEFORE the destination is read back
    — per this repo's "Real-artifact behavioral spot-check" convention and
    per this AC's own test_rationale ("a test that drives a completion
    path and then reads the destination in the same directory the path ran
    in passes on precisely the implementation this AC rejects").

RED baseline: scripts/knowledge/completion_routing.py does not exist, so
every test below fails at `load_completion_routing()` with
FileNotFoundError.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

import workflows._inf700a5_fixtures as fx  # noqa: E402


class _RealGitFixtureCase(unittest.TestCase):
    """Common real-git setup shared by every test in this module: one
    install repo (the merged tree) seeded with a tracked destination file,
    plus a helper to spin up a fresh isolated working-directory clone."""

    DESTINATION_REL = "memory/inf700a5_test_destination.md"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)
        self.install_root = fx.init_install_repo(
            self.tmp_root / "install", {self.DESTINATION_REL: "seed\n"}
        )
        self.sink_path = self.tmp_root / "shared-sink" / "knowledge_emissions.jsonl"
        self.state_path = self.tmp_root / "shared-sink" / "harvest_state.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _new_working_dir(self, branch: str) -> Path:
        working_dir = self.tmp_root / f"work-{branch}"
        return fx.clone_working_dir(self.install_root, working_dir, branch)


class TestTheLearningSurvivesRemovalOfTheWorkingDirectoryTheWorkRanIn(_RealGitFixtureCase):
    def test_the_learning_survives_removal_of_the_working_directory_the_work_ran_in(
        self,
    ) -> None:
        # covers: INF-700a-5
        # angle: criterion
        """Drive a completion path to completion inside an isolated working
        directory whose declared (shared) sink holds one record naming a
        tracked destination; publish and merge as that path does; remove the
        working directory; then read the destination IN THE MERGED TREE and
        assert it holds the learning text. Assertion happens strictly AFTER
        the working directory has been rmtree'd."""
        completion_routing = fx.load_completion_routing()

        fx.emit(
            self.sink_path,
            agent="python-coder",
            component="infrastructure",
            destination=self.DESTINATION_REL,
            entry_kind="memory-project",
            text="INF-700a-5 durability fixture learning",
        )

        working_dir = self._new_working_dir("unit-of-work-durability")
        outcome = completion_routing.stage_completion(
            sink_path=self.sink_path,
            state_path=self.state_path,
            working_dir=working_dir,
        )
        self.assertEqual(outcome["written"], 1, f"expected 1 write, got {outcome!r}")
        self.assertIn(
            str(working_dir / self.DESTINATION_REL),
            outcome["manifest"],
            f"manifest must name the absolute working_dir path written: {outcome!r}",
        )

        fx.commit_paths(
            working_dir, [self.DESTINATION_REL], "route INF-700a-5 durability learning"
        )
        fx.merge_into_install(self.install_root, working_dir, "unit-of-work-durability")
        completion_routing.confirm_routed(
            state_path=self.state_path, record_ids=outcome["record_ids"]
        )

        # The teardown boundary this AC exists to prove is durable across.
        shutil.rmtree(working_dir)
        self.assertFalse(working_dir.exists())

        merged_content = fx.read_file(self.install_root / self.DESTINATION_REL)
        self.assertIn(
            "INF-700a-5 durability fixture learning",
            merged_content,
            "The learning must be present in the MERGED TREE after the "
            f"working directory it was written in has been removed. Merged "
            f"content: {merged_content!r}",
        )


class TestSameCommitCountWithAndWithoutRecordsToRoute(_RealGitFixtureCase):
    def test_a_unit_of_work_produces_the_same_number_of_commits_with_and_without_records_to_route(
        self,
    ) -> None:
        # covers: INF-700a-5
        # angle: criterion
        """Drive the same completion path twice — once with an empty sink,
        once with three routable records — and assert the resulting branch's
        commit count is EQUAL between the two runs, while the destination
        contents differ. An implementation that appends a commit of its own
        (the rejected "new commit inside the routing step" alternative) goes
        red here even though the durability test above is green."""
        completion_routing = fx.load_completion_routing()

        # Run A: nothing to route.
        empty_sink = self.tmp_root / "empty-sink" / "knowledge_emissions.jsonl"
        empty_state = self.tmp_root / "empty-sink" / "harvest_state.json"
        working_dir_a = self._new_working_dir("unit-of-work-a-empty")
        outcome_a = completion_routing.stage_completion(
            sink_path=empty_sink, state_path=empty_state, working_dir=working_dir_a
        )
        self.assertEqual(outcome_a["written"], 0)
        # The completion path's OWN commit for its own output — the routing
        # step must ride this, never add a second one of its own.
        (working_dir_a / "own_output.txt").write_text("unit of work A output\n")
        fx.commit_paths(working_dir_a, ["own_output.txt"], "unit of work A output")
        commits_a = fx._run_git(["rev-list", "--count", "HEAD"], working_dir_a).stdout.strip()

        # Run B: three routable records.
        full_sink = self.tmp_root / "full-sink" / "knowledge_emissions.jsonl"
        full_state = self.tmp_root / "full-sink" / "harvest_state.json"
        for i in range(3):
            fx.emit(
                full_sink,
                agent="python-coder",
                component="infrastructure",
                destination=self.DESTINATION_REL,
                entry_kind="memory-project",
                text=f"commit-count fixture learning {i}",
            )
        working_dir_b = self._new_working_dir("unit-of-work-b-three-records")
        outcome_b = completion_routing.stage_completion(
            sink_path=full_sink, state_path=full_state, working_dir=working_dir_b
        )
        self.assertEqual(outcome_b["written"], 3, f"expected 3 writes, got {outcome_b!r}")
        paths_to_commit = [self.DESTINATION_REL, "own_output.txt"]
        (working_dir_b / "own_output.txt").write_text("unit of work B output\n")
        fx.commit_paths(working_dir_b, paths_to_commit, "unit of work B output + routing")
        commits_b = fx._run_git(["rev-list", "--count", "HEAD"], working_dir_b).stdout.strip()

        self.assertEqual(
            commits_a,
            commits_b,
            "A unit of work must produce the SAME number of commits whether "
            "or not there was anything to route — the routing step's writes "
            "must ride the completion path's own commit, never add a "
            f"second one. commits_a={commits_a!r} commits_b={commits_b!r}",
        )


class TestDestinationAbsentWhenRoutingWriteNotCarried(_RealGitFixtureCase):
    def test_the_destination_is_absent_from_the_merged_tree_when_the_routing_write_is_not_carried(
        self,
    ) -> None:
        # covers: INF-700a-5
        # angle: failure
        """Negative control (test_rationale's explicit must-fail case): wire
        a completion path that writes the destination into the working
        directory and does NOT carry it into publication (no commit, no
        merge). Assert the merged tree never receives it — proving this
        test suite can actually distinguish a durable write from one that
        merely exists before teardown. Without this control, the durability
        test above could be satisfied by a fixture that never tears
        anything down."""
        completion_routing = fx.load_completion_routing()

        fx.emit(
            self.sink_path,
            agent="python-coder",
            component="infrastructure",
            destination=self.DESTINATION_REL,
            entry_kind="memory-project",
            text="never-published fixture learning",
        )
        working_dir = self._new_working_dir("unit-of-work-never-published")
        outcome = completion_routing.stage_completion(
            sink_path=self.sink_path,
            state_path=self.state_path,
            working_dir=working_dir,
        )
        self.assertEqual(outcome["written"], 1)

        # Deliberately DO NOT commit or merge — the write never leaves the
        # working directory, and the working directory is removed as-is.
        self.assertIn("never-published fixture learning", fx.read_file(
            working_dir / self.DESTINATION_REL
        ))
        shutil.rmtree(working_dir)

        merged_content = fx.read_file(self.install_root / self.DESTINATION_REL)
        self.assertNotIn(
            "never-published fixture learning",
            merged_content,
            "The negative control failed: the learning appeared in the "
            "merged tree despite never being committed or merged. A test "
            "harness that cannot produce this failure cannot prove the "
            f"durability test above means anything. Merged content: {merged_content!r}",
        )


if __name__ == "__main__":
    unittest.main()
