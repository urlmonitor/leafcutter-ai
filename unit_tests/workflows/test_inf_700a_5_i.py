"""
MODULE: unit_tests/workflows/test_inf_700a_5_i.py
GOAL: RED behavioral test baseline for INF-700a-5-i — "A learning that could
    not be published is said out loud before the place it was written is
    removed".

AC: docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700a-5-i.yaml

CONTRACT THIS TEST FILE ESTABLISHES FOR python-coder (TDD: this is the spec):

    In addition to `stage_completion()` / `confirm_routed()` (established by
    test_inf_700a_5.py), `scripts/knowledge/completion_routing.py` must
    expose:

        unconfirmed_writes_report(*, working_dir, install_root, manifest,
                                   record_ids, state_path) -> list[dict]

    Read-only (per this AC's it_requirements: "STATING ELIGIBILITY IS A READ
    OF THE BOOKKEEPING, AND THAT READ MUST NOT MUTATE IT"). For each
    manifest path, compares the working_dir content against install_root's
    real merged content (a real git-repo comparison, not a mock), and
    reports any whose learning text never reached install_root, each
    carrying the destination, the learning text, and whether the record is
    still eligible for a later run (state_path does not yet mark it
    processed).

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
    DESTINATION_A = "memory/inf700a5i_destination_a.md"
    DESTINATION_B = "memory/inf700a5i_destination_b.md"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)
        self.install_root = fx.init_install_repo(
            self.tmp_root / "install",
            {self.DESTINATION_A: "seed a\n", self.DESTINATION_B: "seed b\n"},
        )
        self.sink_path = self.tmp_root / "shared-sink" / "knowledge_emissions.jsonl"
        self.state_path = self.tmp_root / "shared-sink" / "harvest_state.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _new_working_dir(self, branch: str) -> Path:
        return fx.clone_working_dir(self.install_root, self.tmp_root / f"work-{branch}", branch)


class TestARefusedPublicationReportsRecordsUnwrittenAndNamesDestinations(_RealGitFixtureCase):
    def test_a_refused_publication_reports_the_records_unwritten_and_names_the_destinations(
        self,
    ) -> None:
        # covers: INF-700a-5-i
        # angle: criterion
        """Drive a completion path with two routable records and refuse the
        publication (no commit is ever made on the working_dir's branch —
        the gate-refused case). Assert unconfirmed_writes_report names both
        destinations and reports both as still holding un-merged learning
        text — never as written."""
        completion_routing = fx.load_completion_routing()

        fx.emit(
            self.sink_path,
            agent="python-coder",
            component="infrastructure",
            destination=self.DESTINATION_A,
            entry_kind="memory-project",
            text="refused-publication learning A",
        )
        fx.emit(
            self.sink_path,
            agent="python-coder",
            component="infrastructure",
            destination=self.DESTINATION_B,
            entry_kind="memory-project",
            text="refused-publication learning B",
        )
        working_dir = self._new_working_dir("unit-of-work-refused")
        outcome = completion_routing.stage_completion(
            sink_path=self.sink_path, state_path=self.state_path, working_dir=working_dir
        )
        self.assertEqual(outcome["written"], 2, f"expected 2 writes, got {outcome!r}")

        # Publication REFUSED: no commit is ever made — the gate blocked it.
        report = completion_routing.unconfirmed_writes_report(
            working_dir=working_dir,
            install_root=self.install_root,
            manifest=outcome["manifest"],
            record_ids=outcome["record_ids"],
            state_path=self.state_path,
        )
        reported_destinations = {entry["destination"] for entry in report}
        self.assertEqual(
            reported_destinations,
            {self.DESTINATION_A, self.DESTINATION_B},
            f"Both destinations must be reported unwritten. Got: {report!r}",
        )
        for entry in report:
            self.assertIn(
                "refused-publication learning",
                entry.get("text", ""),
                f"report entry must carry the learning text: {entry!r}",
            )


class TestTeardownStepNamesEveryLearningAbsentFromMergedTree(_RealGitFixtureCase):
    def test_the_teardown_step_names_every_learning_absent_from_the_merged_tree(
        self,
    ) -> None:
        # covers: INF-700a-5-i
        # angle: seam
        """Reach the removal step with one learning published and one not.
        Assert the removal-step report names ONLY the unpublished
        destination (not the published one), states it is still eligible
        (the shared sink/state outlives this removal), and that the working
        directory is removed either way — the fail-open half and the
        announcement half must both hold."""
        completion_routing = fx.load_completion_routing()

        fx.emit(
            self.sink_path,
            agent="python-coder",
            component="infrastructure",
            destination=self.DESTINATION_A,
            entry_kind="memory-project",
            text="this one gets published",
        )
        fx.emit(
            self.sink_path,
            agent="python-coder",
            component="infrastructure",
            destination=self.DESTINATION_B,
            entry_kind="memory-project",
            text="this one never gets published",
        )
        working_dir = self._new_working_dir("unit-of-work-mixed")
        outcome = completion_routing.stage_completion(
            sink_path=self.sink_path, state_path=self.state_path, working_dir=working_dir
        )
        self.assertEqual(outcome["written"], 2)

        # Publish ONLY destination A.
        fx.commit_paths(working_dir, [self.DESTINATION_A], "publish A only")
        fx.merge_into_install(self.install_root, working_dir, "unit-of-work-mixed")

        report = completion_routing.unconfirmed_writes_report(
            working_dir=working_dir,
            install_root=self.install_root,
            manifest=outcome["manifest"],
            record_ids=outcome["record_ids"],
            state_path=self.state_path,
        )
        reported_destinations = {entry["destination"] for entry in report}
        self.assertEqual(
            reported_destinations,
            {self.DESTINATION_B},
            f"Only the UNPUBLISHED destination B should be named; A was "
            f"published and must not appear. Got: {report!r}",
        )
        self.assertTrue(
            report[0]["eligible"],
            "The unpublished record must be reported as still eligible for "
            f"a later run — it lives in the shared sink/state, not just "
            f"this working directory. Got: {report!r}",
        )

        # The fail-open half: removal proceeds regardless of the report.
        shutil.rmtree(working_dir)
        self.assertFalse(working_dir.exists())


if __name__ == "__main__":
    unittest.main()
