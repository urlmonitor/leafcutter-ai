"""
MODULE: unit_tests/workflows/test_inf_700a_5_cli.py
GOAL: Behavioural tests for the PRODUCTION entry point the wired completion
    paths call for the INF-700a-5 durability step:
    scripts/knowledge/completion_routing_cli.py (`stage` before the path's own
    commit, `observe` after it).

WHY THIS FILE EXISTS: the sibling test_inf_700a_5*.py files exercise the
    library functions directly. Nothing in production calls those functions
    directly -- a workflow dispatches an agent that runs ONE Bash command. So
    every test here runs the CLI in a real subprocess, against a real install
    repo (the merged tree) and a real clone on its own branch (the isolated
    working directory), with sink records produced by the real
    emit_knowledge.py. The confirmation rule under test is the one BrainCandy
    chose on 2026-10-08: a record is never marked routed at commit time; a
    later `stage` claims it only once its text is already on the base branch
    (origin/main), and stages everything else again (a duplicate is the
    accepted failure, never a loss).
"""

from __future__ import annotations

import json
import shutil
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
_DEST = "memory/inf700a5_cli_destination.md"
_OTHER = "memory/inf700a5_cli_other.md"


class _CliCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.install = fx.init_install_repo(
            self.root / "install", {_DEST: "seed\n", _OTHER: "other seed\n"}
        )
        self.sink = self.root / "install-logs" / "knowledge_emissions.jsonl"
        self.state = self.root / "install-logs" / "harvest_state.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def cli(self, *args: str, sink: Path | None = None) -> dict:
        cmd = [sys.executable, str(_CLI), *args]
        if sink is not False:
            cmd += ["--sink", str(sink or self.sink), "--state", str(self.state)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(proc.returncode, 0, f"CLI must exit 0 (fail-open): {proc.stderr}")
        lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        self.assertTrue(lines, f"CLI printed no JSON. stderr={proc.stderr}")
        return json.loads(lines[-1])

    def emit(self, text: str, destination: str = _DEST) -> None:
        fx.emit(
            self.sink,
            agent="python-coder",
            component="infrastructure",
            destination=destination,
            entry_kind="memory-project",
            text=text,
        )

    def worktree(self, branch: str) -> Path:
        return fx.clone_working_dir(self.install, self.root / f"wt-{branch}", branch)

    def own_output(self, wt: Path, label: str) -> None:
        (wt / "own_output.txt").write_text(f"{label}\n", encoding="utf-8")

    def complete(self, wt: Path, branch: str, *, carry: bool = True, merge: bool = True) -> dict:
        """One unit of work: stage, commit its own output (+ the manifest
        when *carry*), observe, optionally merge, then remove the worktree."""
        staged = self.cli("stage", "--working-dir", str(wt))
        self.own_output(wt, branch)
        paths = ["own_output.txt"] + (staged["manifest"] if carry else [])
        fx.commit_paths(wt, paths, f"unit of work {branch}")
        observed = self.cli("observe", "--working-dir", str(wt), "--commit-status", "ok")
        if merge:
            fx.merge_into_install(self.install, wt, branch)
        shutil.rmtree(wt)
        return {"staged": staged, "observed": observed}

    def merged_count(self, text: str, destination: str = _DEST) -> int:
        return fx.read_file(self.install / destination).count(text)


class TestStageAndObserveCarryTheLearningIntoTheMergedTree(_CliCase):
    def test_the_learning_survives_removal_of_the_working_directory_via_the_cli(self) -> None:
        # covers: INF-700a-5
        # angle: criterion
        self.emit("cli durability learning")
        wt = self.worktree("durable")
        run = self.complete(wt, "durable")
        self.assertEqual(run["staged"]["manifest"], [_DEST], run)
        self.assertEqual(run["observed"]["written"], 1, run)
        self.assertEqual(run["observed"]["unwritten"], 0, run)
        self.assertFalse(wt.exists())
        self.assertEqual(self.merged_count("cli durability learning"), 1)

    def test_stage_never_marks_a_record_routed_at_routing_or_commit_time(self) -> None:
        # covers: INF-700a-5
        # angle: boundary
        self.emit("no early mark")
        wt = self.worktree("nomark")
        self.complete(wt, "nomark", merge=False)
        state = json.loads(self.state.read_text()) if self.state.exists() else []
        self.assertEqual(state, [], "nothing may be marked before the text is on main")

    def test_a_unit_of_work_makes_the_same_number_of_commits_with_and_without_records(
        self,
    ) -> None:
        # covers: INF-700a-5
        # angle: criterion
        counts = []
        for branch, records in (("empty", 0), ("three", 3)):
            for i in range(records):
                self.emit(f"commit-count learning {i}")
            wt = self.worktree(branch)
            staged = self.cli("stage", "--working-dir", str(wt))
            self.own_output(wt, branch)
            fx.commit_paths(wt, ["own_output.txt", *staged["manifest"]], branch)
            counts.append(fx._run_git(["rev-list", "--count", "HEAD"], wt).stdout.strip())
            self.assertEqual(staged["written"], records, staged)
        self.assertEqual(counts[0], counts[1], "the routing step must add no commit")


class TestUnpublishedWritesAreReportedAndRoutedAgain(_CliCase):
    def test_a_refused_commit_reports_the_write_unwritten_and_a_later_run_writes_it_once(
        self,
    ) -> None:
        # covers: INF-700a-5, INF-700a-5-i
        # angle: seam
        self.emit("refused then rerouted")
        wt = self.worktree("refused")
        staged = self.cli("stage", "--working-dir", str(wt))
        self.assertEqual(staged["written"], 1, staged)
        observed = self.cli("observe", "--working-dir", str(wt), "--commit-status", "failed")
        self.assertEqual(observed["written"], 0, observed)
        self.assertEqual(observed["unwritten"], 1, observed)
        entry = observed["unwritten_records"][0]
        self.assertEqual(entry["destination"], _DEST)
        self.assertEqual(entry["reason"], "publication_refused")
        self.assertIn("refused then rerouted", entry["text"])
        self.assertTrue(entry["eligible"], observed)
        shutil.rmtree(wt)
        self.assertEqual(self.merged_count("refused then rerouted"), 0)

        self.complete(self.worktree("second"), "second")
        self.assertEqual(self.merged_count("refused then rerouted"), 1)

    def test_a_stopped_path_names_the_stopped_reason(self) -> None:
        # covers: INF-700a-5-i
        # angle: failure
        self.emit("stopped before publication")
        wt = self.worktree("stopped")
        self.cli("stage", "--working-dir", str(wt))
        observed = self.cli("observe", "--working-dir", str(wt), "--commit-status", "not_run")
        reasons = [e["reason"] for e in observed["unwritten_records"]]
        self.assertEqual(reasons, ["stopped_before_publication"], observed)

    def test_a_record_routed_on_a_branch_that_never_merges_is_routed_again_once(self) -> None:
        # covers: INF-700a-5
        # angle: boundary
        self.emit("abandoned branch learning")
        self.complete(self.worktree("abandoned"), "abandoned", merge=False)
        self.assertEqual(self.merged_count("abandoned branch learning"), 0)
        self.complete(self.worktree("kept"), "kept")
        self.assertEqual(self.merged_count("abandoned branch learning"), 1)
        third = self.complete(self.worktree("third"), "third")
        self.assertEqual(third["staged"]["written"], 0, third)
        self.assertEqual(self.merged_count("abandoned branch learning"), 1)
        self.assertEqual(len(json.loads(self.state.read_text())), 1)

    def test_the_destination_is_absent_when_the_commit_does_not_carry_the_write(self) -> None:
        # covers: INF-700a-5
        # angle: failure
        self.emit("left out of the commit")
        run = self.complete(self.worktree("leftout"), "leftout", carry=False)
        self.assertEqual(run["observed"]["written"], 0, run)
        reasons = [e["reason"] for e in run["observed"]["unwritten_records"]]
        self.assertEqual(reasons, ["left_out_of_commit"], run)
        self.assertEqual(self.merged_count("left out of the commit"), 0)


class TestConflictingDestinationIsLeftOut(_CliCase):
    def test_a_conflicting_destination_is_dropped_and_the_work_still_publishes(self) -> None:
        # covers: INF-700a-5-i
        # angle: failure
        wt = self.worktree("conflict")
        (self.install / _DEST).write_text("seed\nmain moved on\n", encoding="utf-8")
        fx.commit_paths(self.install, [_DEST], "main edits the destination")
        self.emit("would conflict")
        staged = self.cli("stage", "--working-dir", str(wt))
        self.assertEqual(staged["manifest"], [], staged)
        self.assertEqual(
            [e["reason"] for e in staged["unwritten_records"]],
            ["conflicts_with_merged_tree"],
            staged,
        )
        self.own_output(wt, "conflict")
        fx.commit_paths(wt, ["own_output.txt"], "own output only")
        observed = self.cli("observe", "--working-dir", str(wt), "--commit-status", "ok")
        self.assertEqual(observed["unwritten"], 1, observed)
        # main moved on, so this is a true (non-fast-forward) merge.
        fx._run_git(["pull", "--no-rebase", "--no-edit", str(wt), "conflict"], self.install)
        self.assertTrue((self.install / "own_output.txt").exists())


class TestLateEmissionIsNamedAsWaiting(_CliCase):
    def test_observe_names_a_record_emitted_after_stage_as_waiting(self) -> None:
        # covers: INF-700a-5-ii
        # angle: criterion
        self.emit("read by the stage")
        wt = self.worktree("late")
        staged = self.cli("stage", "--working-dir", str(wt))
        self.emit("emitted by a publishing phase", destination=_OTHER)
        self.own_output(wt, "late")
        fx.commit_paths(wt, ["own_output.txt", *staged["manifest"]], "late")
        observed = self.cli("observe", "--working-dir", str(wt), "--commit-status", "ok")
        waiting = observed["waiting"]
        self.assertEqual((waiting["present"], waiting["read"], waiting["difference"]), (2, 1, 1))
        self.assertEqual([r["text"] for r in waiting["records"]], ["emitted by a publishing phase"])
        self.assertIn("next completed unit of work", waiting["note"])
        for word in ("lost", "discarded", "reclaimed"):
            self.assertNotIn(word, json.dumps(observed))
        self.assertEqual(observed["written"], 1, "the late record is not counted written")

    def test_the_difference_is_zero_when_nothing_emits_after_stage(self) -> None:
        # covers: INF-700a-5-ii
        # angle: boundary
        self.emit("quiet path")
        run = self.complete(self.worktree("quiet"), "quiet")
        self.assertEqual(run["observed"]["waiting"]["difference"], 0, run)


class TestFailOpenAndReadOnlyProperties(_CliCase):
    def test_stage_without_a_sink_declaration_reports_did_not_run_and_exits_zero(self) -> None:
        # covers: INF-700a-5
        # angle: failure
        wt = self.worktree("nosink")
        proc = subprocess.run(
            [sys.executable, str(_CLI), "stage", "--working-dir", str(wt)],
            capture_output=True, text=True, timeout=60, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        reply = json.loads(proc.stdout.splitlines()[-1])
        self.assertEqual(reply["case"], "did_not_run", reply)
        self.assertEqual(fx._run_git(["status", "--porcelain"], wt).stdout.strip(), "")

    def test_observe_writes_neither_the_sink_nor_the_state(self) -> None:
        # covers: INF-700a-5-ii, INF-700a-5-i
        # angle: boundary
        self.emit("read-only observe")
        wt = self.worktree("ro")
        self.cli("stage", "--working-dir", str(wt))
        before = (self.sink.read_bytes(), self.state.exists())
        self.cli("observe", "--working-dir", str(wt), "--commit-status", "failed")
        self.assertEqual((self.sink.read_bytes(), self.state.exists()), before)

    def test_stage_records_the_routing_run_for_the_recency_answer(self) -> None:
        # covers: INF-700a-5
        # angle: seam
        wt = self.worktree("recency")
        self.cli("stage", "--working-dir", str(wt))
        marker = self.state.parent / "harvest_last_run.json"
        self.assertTrue(marker.exists(), "the INF-700a-2 last-run marker must still be written")


if __name__ == "__main__":
    unittest.main()
