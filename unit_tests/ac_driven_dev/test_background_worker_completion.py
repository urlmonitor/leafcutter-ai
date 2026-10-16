"""Checked completion becomes reviewable target-tree dependency evidence."""

import tempfile

import unittest

from pathlib import Path

import yaml

from scripts.background_worker.completion import complete_ac

from scripts.background_worker.execution_boundary import ExecutorError



class CompletionTests(unittest.TestCase):

    def setUp(self):

        self.temp = tempfile.TemporaryDirectory()

        self.addCleanup(self.temp.cleanup)

        self.root = Path(self.temp.name)

        self.ac = self.root / "docs/acceptance-criteria"

        self.ac.mkdir(parents=True)

        self.records = {

            "TEST-100": {"id": "TEST-100", "level": "L0", "covered_by": ["TEST-100a", "TEST-100b"]},

            "TEST-100a": {"id": "TEST-100a", "level": "L1", "covered_by": ["TEST-100a-1", "TEST-100a-2"]},

            "TEST-100a-1": {"id": "TEST-100a-1", "level": "L2", "criteria": "first behavior"},

            "TEST-100a-2": {"id": "TEST-100a-2", "level": "L2", "criteria": "second behavior"},

        }

        for identifier, record in self.records.items():

            self.write(identifier, {**record, "work_status": "todo"})

        self.plan = {"ac_ids": ["TEST-100a-1", "TEST-100a-2"], "source_context": {"obligations": self.records}}

        (self.root / "code.py").write_text("result = 1")


    def write(self, identifier, record):

        (self.ac / (identifier + ".yaml")).write_text(yaml.safe_dump(record), encoding="utf-8")


    def read(self, identifier):

        return yaml.safe_load((self.ac / (identifier + ".yaml")).read_text(encoding="utf-8"))


    # covers: ACD-1300f-2 ACD-1300e-3

    def test_checked_leaf_then_feature_rollup_preserves_unfinished_root(self):

        self.assertTrue(complete_ac(self.root, self.plan, "TEST-100a-1", ["code.py"]))

        self.assertEqual(self.read("TEST-100a-1")["implemented_by"], ["code.py"])

        self.assertEqual(self.read("TEST-100a")["work_status"], "todo")

        complete_ac(self.root, self.plan, "TEST-100a-2", ["code.py"], completed_ac_ids=["TEST-100a-1"])

        self.assertEqual(self.read("TEST-100a")["work_status"], "done")

        self.assertEqual(self.read("TEST-100a")["implemented_by"], ["code.py"])

        self.assertEqual(self.read("TEST-100")["work_status"], "todo")


    # covers: ACD-1300e-3

    def test_changed_requirements_and_missing_records_reject_before_any_write(self):

        original = self.read("TEST-100a-1")

        self.write("TEST-100a-2", {**self.records["TEST-100a-2"], "criteria": "model invented scope"})

        with self.assertRaisesRegex(ExecutorError, "changed approved"):

            complete_ac(self.root, self.plan, "TEST-100a-1", ["code.py"])

        self.assertEqual(self.read("TEST-100a-1"), original)

        (self.ac / "TEST-100a-2.yaml").unlink()

        with self.assertRaisesRegex(ExecutorError, "exactly one"):

            complete_ac(self.root, self.plan, "TEST-100a-1", ["code.py"])


    # covers: ACD-1300f-2

    def test_model_done_claim_cannot_roll_up_unchecked_sibling(self):

        self.write("TEST-100a-2", {**self.records["TEST-100a-2"], "work_status": "done", "implemented_by": ["code.py"]})

        with self.assertRaisesRegex(ExecutorError, "Unproven model-authored"):

            complete_ac(self.root, self.plan, "TEST-100a-1", ["code.py"])

        self.assertEqual(self.read("TEST-100a")["work_status"], "todo")

        self.assertEqual(self.read("TEST-100a-1")["work_status"], "todo")


    # covers: ACD-1300f-2

    def test_state_files_and_missing_paths_cannot_be_completion_evidence(self):

        (self.root / ".leafcutter").mkdir()

        (self.root / ".leafcutter/state.json").write_text("{}")

        with self.assertRaisesRegex(ExecutorError, "evidence path"):

            complete_ac(self.root, self.plan, "TEST-100a-1", ["missing.py", ".leafcutter/state.json", "docs/acceptance-criteria/TEST-100a-1.yaml"])

        self.assertEqual(self.read("TEST-100a-1")["work_status"], "todo")


    # covers: ACD-1300f-2

    def test_target_reader_recognizes_merged_completion_records(self):

        import io

        import subprocess

        import tarfile

        from unittest.mock import patch

        from scripts.background_worker.sources import target_completed


        complete_ac(self.root, self.plan, "TEST-100a-1", ["code.py"])

        complete_ac(self.root, self.plan, "TEST-100a-2", ["code.py"], completed_ac_ids=["TEST-100a-1"])

        archive = io.BytesIO()

        with tarfile.open(fileobj=archive, mode="w") as bundle:

            for path in self.ac.glob("*.yaml"):

                bundle.add(path, arcname=path.relative_to(self.root).as_posix())

        results = [subprocess.CompletedProcess([], 0, "merged-sha"),

                   subprocess.CompletedProcess([], 0, archive.getvalue()),

                   subprocess.CompletedProcess([], 0, b"code.py\0")]

        with patch("scripts.background_worker.sources._run_git", side_effect=results):

            self.assertEqual(target_completed(self.root, "origin/main"),

                             {"TEST-100a", "TEST-100a-1", "TEST-100a-2"})


    # covers: ACD-1300f-2

    def test_unproven_ancestor_done_is_rejected_but_source_baseline_is_preserved(self):

        root = {**self.records["TEST-100"], "work_status": "done"}

        self.write("TEST-100", root)

        with self.assertRaisesRegex(ExecutorError, "Unproven model-authored"):

            complete_ac(self.root, self.plan, "TEST-100a-1", ["code.py"])

        self.plan["source_context"]["completion_baseline"] = {"TEST-100": {"work_status": "done"}}

        complete_ac(self.root, self.plan, "TEST-100a-1", ["code.py"])

        self.assertEqual(self.read("TEST-100"), root)


    # covers: ACD-1300f-2

    def test_real_git_merge_target_unlocks_checked_feature_only_after_advancement(self):

        import subprocess

        from scripts.background_worker.sources import target_completed


        def git(*args):

            return subprocess.run(["git", "-C", str(self.root), *args], check=True,

                                  capture_output=True, text=True).stdout.strip()


        git("init", "--initial-branch=main")

        git("config", "user.name", "Worker completion fixture")

        git("config", "user.email", "worker-fixture@example.invalid")

        git("add", ".")

        git("commit", "-m", "Fixture baseline")

        git("switch", "-c", "worker")

        complete_ac(self.root, self.plan, "TEST-100a-1", ["code.py"])

        complete_ac(self.root, self.plan, "TEST-100a-2", ["code.py"], completed_ac_ids=["TEST-100a-1"])

        git("add", ".")

        git("commit", "-m", "Fixture checked completion")

        self.assertEqual(target_completed(self.root, "main"), set())

        git("switch", "main")

        git("merge", "--ff-only", "worker")

        self.assertEqual(target_completed(self.root, "main"),

                         {"TEST-100a", "TEST-100a-1", "TEST-100a-2"})


    # covers: ACD-1300f-2

    def test_repair_preserves_previously_checked_parent_completion(self):

        complete_ac(self.root, self.plan, "TEST-100a-1", ["code.py"])

        complete_ac(self.root, self.plan, "TEST-100a-2", ["code.py"], completed_ac_ids=["TEST-100a-1"])

        complete_ac(self.root, self.plan, "TEST-100a-1", ["code.py"], completed_ac_ids=self.plan["ac_ids"])

        self.assertEqual(self.read("TEST-100a")["work_status"], "done")


    # covers: ACD-1300f-2

    def test_unicode_implementation_path_is_preserved(self):

        name = "größer.py"

        (self.root / name).write_text("value = 1")

        complete_ac(self.root, self.plan, "TEST-100a-1", [name])

        self.assertEqual(self.read("TEST-100a-1")["implemented_by"], [name])
