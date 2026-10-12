"""
MODULE: tests.kernel.memory.test_publish_cli
GOAL: Publication and the `decisions` CLI: a staged record is validated and written into the
    store with a regenerated index only when `publish` runs, an invalid or conflicting record
    writes nothing, publishing twice is idempotent, and `--correct` appends a correction to the
    superseded record without changing anything else.
BUSINESS CONTEXT: The kernel never writes the repository during a run (ADR-060); the explicit
    publish command is the single writer of docs/decisions, and a correction is a deliberate,
    append-only edit.
ARCHITECTURE: A temporary repository root and run root, a record staged through the real file
    backend, and the real argparse entry point (`kernel.adapters.cli.main`) for the CLI cases.
"""

from __future__ import annotations

import ast
import contextlib
import io
import json
import subprocess
import unittest

from kernel.adapters.cli import main
from kernel.config import load_kernel_config
from kernel.contracts.task import Scope
from kernel.memory.codec import dump_record, load_record_file
from kernel.memory.file_store import FileColonyMemory
from kernel.memory.index import INDEX_NAME, read_index
from kernel.memory.precedent import find_precedents
from kernel.memory.publish import apply_correction, publish, rebuild_index
from kernel.memory.validate import validate_store
from tests.kernel.memory.support import CHECKOUT, StoreCase, make_record, schema, vocabulary

FIRST_ID = "dec-0123456789abcdef"
NEWER_ID = "dec-4444444444444444"
RUN = "run-aaaaaaaaaaaaaaaa"
STAGED_QUESTION = "Which logging library should the scheduler use for structured output?"
MEMORY_PACKAGE = CHECKOUT / "kernel" / "memory"
SHELL_CALLS = {("os", "system"), ("os", "popen"), ("os", "execv"), ("os", "execvp"),
               ("os", "spawnv"), ("os", "startfile")}


class PublishCase(StoreCase):
    """A store, a run root and helpers to stage and publish."""

    def stage(self, record=None) -> None:  # noqa: ANN001
        FileColonyMemory(self.root, self.run_root).stage_decision(record or make_record())

    def publish(self, **kw):  # noqa: ANN003, ANN202
        return publish(RUN, folder=self.folder, run_root=self.run_root, schema=schema(),
                       vocab=vocabulary(), **kw)

    def newer(self, **kw):  # noqa: ANN003, ANN202
        return make_record(id=NEWER_ID, supersedes=[FIRST_ID],
                           question="Where should the kernel file approved decisions now?", **kw)


class TestPublish(PublishCase):
    """What publish writes and what it refuses."""

    def test_nothing_is_written_until_publish_runs(self) -> None:
        # covers: DK-600d-1-i
        # covers: DK-600d-1
        self.stage()
        self.assertFalse(self.folder.exists())

    def test_a_staged_record_is_published_with_an_index(self) -> None:
        # covers: DK-600d-3
        self.stage()
        result = self.publish()
        self.assertTrue(result.ok, result.problems)
        self.assertEqual(result.published, [FIRST_ID])
        self.assertTrue(result.index_written)
        self.assertEqual((self.folder / f"{FIRST_ID}.yaml").read_text(encoding="utf-8"),
                         dump_record(make_record()))
        report = validate_store(self.folder, schema=schema(), vocab=vocabulary())
        self.assertTrue(report.ok, report.problems)

    def test_publishing_twice_is_idempotent(self) -> None:
        # covers: DK-600d-3
        self.stage()
        self.publish()
        before = (self.folder / INDEX_NAME).read_bytes()
        again = self.publish()
        self.assertTrue(again.ok, again.problems)
        self.assertEqual(again.already_present, [FIRST_ID])
        self.assertEqual(again.published, [])
        self.assertEqual((self.folder / INDEX_NAME).read_bytes(), before)

    def test_a_run_with_nothing_staged_is_refused(self) -> None:
        # covers: DK-600d-2-i
        result = self.publish()
        self.assertFalse(result.ok)
        self.assertIn("no staged decision record", result.problems[0].message)

    def test_an_invalid_staged_record_writes_nothing(self) -> None:
        # covers: DK-600d-2
        # covers: DK-600d-2-ii
        self.stage(make_record(components=["not_a_component"]))
        result = self.publish()
        self.assertFalse(result.ok)
        self.assertFalse(self.folder.exists())

    def test_a_different_record_with_a_published_id_is_refused(self) -> None:
        # covers: DK-600d-2
        self.stage()
        self.publish()
        (self.run_root / "runs" / RUN / "staged" / "decisions" / f"{FIRST_ID}.yaml").write_text(
            dump_record(make_record(title="A different title")), encoding="utf-8")
        result = self.publish()
        self.assertIn("already published", " ".join(p.message for p in result.problems))

    def test_a_broken_store_is_not_published_into(self) -> None:
        # covers: DK-600d-2
        self.write_record(make_record(related=["dec-9999999999999999"]))
        self.stage(make_record(id=NEWER_ID))
        result = self.publish()
        self.assertFalse(result.ok)
        self.assertFalse((self.folder / f"{NEWER_ID}.yaml").exists())

    def test_an_unsafe_run_id_is_refused(self) -> None:
        # covers: DK-600d-2-i
        result = publish("../x", folder=self.folder, run_root=self.run_root, schema=schema(),
                         vocab=vocabulary())
        self.assertFalse(result.ok)


class TestAStagedRecordIsNotPrecedent(PublishCase):
    """DK-600d-1-i: what was staged and never published is not found by a later run."""

    def lookup(self, question: str) -> list[str]:
        """Return the ids a later decision run's precedent lookup finds for the question."""
        scope = Scope(workspace_id="ws", repository_root=str(self.root))
        memory = FileColonyMemory(self.root, self.run_root)
        cfg = load_kernel_config().memory.model_copy(update={"min_candidate_score": 0.0})
        return [h.record.id for h in find_precedents(memory, question, scope, [], cfg)]

    def test_a_staged_record_that_is_not_published_is_never_found(self) -> None:
        # covers: DK-600d-1-i
        self.write_record(make_record())  # an earlier, published decision
        rebuild_index(self.folder, schema(), vocabulary())
        staged = make_record(id=NEWER_ID, question=STAGED_QUESTION, title="Structured logging")
        self.stage(staged)  # the person chooses not to publish it
        path = self.run_root / "runs" / RUN / "staged" / "decisions" / f"{NEWER_ID}.yaml"
        self.assertTrue(path.is_file())  # it stays only in the run folder
        self.assertFalse((self.folder / f"{NEWER_ID}.yaml").exists())
        self.assertNotIn(NEWER_ID, [e.id for e in read_index(self.folder / INDEX_NAME)])
        for question in (STAGED_QUESTION, staged.question, make_record().question):
            self.assertNotIn(NEWER_ID, self.lookup(question), question)
        self.assertEqual(self.lookup(make_record().question), [FIRST_ID])  # sanity: lookup works
        published = self.publish()  # once a person publishes it, it is found
        self.assertTrue(published.ok, published.problems)
        self.assertEqual(self.lookup(STAGED_QUESTION)[:1], [NEWER_ID])


class TestPublishChangesOnlyTheStoreAndLeavesGitAlone(PublishCase):
    """DK-600d-4: publish writes the record and index, makes no commit/push/merge, and is found."""

    def git(self, *args: str) -> str:
        out = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.test",
                              "-c", "commit.gpgsign=false", *args], cwd=self.root, check=True,
                             capture_output=True, text=True)
        return out.stdout

    def test_publish_changes_only_the_record_and_the_index_and_no_git_state(self) -> None:
        # covers: DK-600d-4
        self.stage()  # the run root sits inside this checkout, so commit the staged record too
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "checkout")
        self.assertEqual(self.git("status", "--porcelain", "--untracked-files=all"), "")
        head, refs = self.git("rev-parse", "HEAD"), self.git("for-each-ref")
        result = self.publish()
        self.assertTrue(result.ok, result.problems)
        changed = sorted(line[3:] for line in
                         self.git("status", "--porcelain", "--untracked-files=all").splitlines())
        self.assertEqual(changed, [f"docs/decisions/{FIRST_ID}.yaml", "docs/decisions/index.json"])
        self.assertEqual(self.git("rev-parse", "HEAD"), head)  # no commit
        self.assertEqual(self.git("diff", "--cached", "--name-only"), "")  # nothing staged
        self.assertEqual(self.git("for-each-ref"), refs)  # no branch, tag or remote ref moved

    def test_kernel_memory_imports_no_subprocess_or_git_and_makes_no_shell_call(self) -> None:
        # covers: DK-600d-4
        files = sorted(MEMORY_PACKAGE.rglob("*.py"))
        self.assertTrue(files)
        for path in files:
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                         else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
                for name in names:
                    self.assertNotIn(name.split(".")[0], {"subprocess", "git", "pygit2", "dulwich",
                                                          "sh", "pexpect"}, f"{path.name}: {name}")
                if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                        and (node.value.id, node.attr) in SHELL_CALLS):
                    self.fail(f"{path.name} calls {node.value.id}.{node.attr}")

    def test_a_published_record_is_found_by_a_later_lookup_through_the_index(self) -> None:
        # covers: DK-600d-4
        self.stage()
        self.assertTrue(self.publish().ok)
        index = read_index(self.folder / INDEX_NAME)
        self.assertEqual([e.id for e in index], [FIRST_ID])
        scope = Scope(workspace_id="ws", repository_root=str(self.root))
        found = find_precedents(FileColonyMemory(self.root, self.run_root), make_record().question,
                                scope, [], load_kernel_config().memory)
        self.assertEqual([h.record.id for h in found], [FIRST_ID])
        self.assertEqual(found[0].path, f"docs/decisions/{FIRST_ID}.yaml")


class TestCorrection(PublishCase):
    """A correction is explicit and append-only."""

    def setUp(self) -> None:
        super().setUp()
        self.write_record(make_record())
        self.stage(self.newer())

    def test_publishing_a_superseding_record_leaves_the_older_one_untouched(self) -> None:
        # covers: DK-600d-3-i
        old_text = (self.folder / f"{FIRST_ID}.yaml").read_text(encoding="utf-8")
        result = self.publish()
        self.assertTrue(result.ok, result.problems)
        self.assertEqual((self.folder / f"{FIRST_ID}.yaml").read_text(encoding="utf-8"), old_text)
        self.assertEqual(result.corrected, [])

    def test_correct_appends_one_entry_and_a_link_and_changes_nothing_else(self) -> None:
        # covers: DK-600d-3-i
        before = load_record_file(self.folder / f"{FIRST_ID}.yaml")
        result = self.publish(correct=[FIRST_ID], reason="the human decided anew")
        self.assertTrue(result.ok, result.problems)
        after = load_record_file(self.folder / f"{FIRST_ID}.yaml")
        self.assertEqual(result.corrected, [FIRST_ID])
        (entry,) = after.corrections
        self.assertEqual(entry.reason, "the human decided anew")
        self.assertEqual(entry.corrected_by, "human:tester")
        self.assertEqual(entry.superseded_by, NEWER_ID)
        self.assertEqual(entry.preserved.selected_option_id, before.selected_option_id)
        self.assertEqual(entry.preserved.evidence_ids, [e.id for e in before.evidence])
        self.assertEqual(entry.preserved.assumptions, ["PyYAML is available in development"])
        self.assertEqual(after.superseded_by, [NEWER_ID])
        untouched = {"corrections", "superseded_by"}
        self.assertEqual(after.model_dump(exclude=untouched), before.model_dump(exclude=untouched))
        self.assertTrue(validate_store(self.folder, schema=schema(), vocab=vocabulary()).ok)

    def test_a_second_correction_appends_to_the_first(self) -> None:
        # covers: DK-600d-3-i
        old = load_record_file(self.folder / f"{FIRST_ID}.yaml")
        newer = self.newer()
        once = apply_correction(old, newer, "first")
        twice = apply_correction(once, make_record(id="dec-5555555555555555",
                                                   supersedes=[FIRST_ID]), "second")
        self.assertEqual([c.reason for c in twice.corrections], ["first", "second"])
        self.assertEqual(twice.superseded_by, [NEWER_ID, "dec-5555555555555555"])

    def test_correct_without_a_superseding_staged_record_is_refused(self) -> None:
        # covers: DK-600d-3-i
        self.write_record(make_record(id="dec-6666666666666666"))
        result = self.publish(correct=["dec-6666666666666666"])
        self.assertFalse(result.ok)
        self.assertFalse((self.folder / f"{NEWER_ID}.yaml").exists())  # nothing was written

    def test_correct_naming_an_unknown_record_is_refused(self) -> None:
        # covers: DK-600d-3-i
        self.assertFalse(self.publish(correct=["dec-7777777777777777"]).ok)

    def test_the_default_reason_names_the_decider_and_the_run(self) -> None:
        # covers: DK-600d-3-i
        self.publish(correct=[FIRST_ID])
        (entry,) = load_record_file(self.folder / f"{FIRST_ID}.yaml").corrections
        self.assertIn(RUN, entry.reason)
        self.assertIn("human:tester", entry.reason)


class TestCli(PublishCase):
    """The argparse entry point prints one JSON document and the documented exit codes."""

    def run_cli(self, *argv: str) -> tuple[int, dict]:
        out, err = io.StringIO(), io.StringIO()
        override = self.root / "override.json"
        override.write_text(json.dumps({"paths": {"run_root": str(self.run_root),
                                                  "registry": "config/capability_registry.json"}}),
                            encoding="utf-8")
        args = [argv[0], argv[1], "--repo-root", str(self.root), "--config", str(override),
                *argv[2:]]
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(args)
        return code, json.loads(out.getvalue())

    def test_validate_passes_an_empty_store(self) -> None:
        code, doc = self.run_cli("decisions", "validate")
        self.assertEqual((code, doc["ok"], doc["records"]), (0, True, 0))

    def test_publish_then_validate_through_the_cli(self) -> None:
        # covers: DK-600d-3
        self.stage()
        code, doc = self.run_cli("decisions", "publish", "--run-id", RUN)
        self.assertEqual((code, doc["published"]), (0, [FIRST_ID]))
        code, doc = self.run_cli("decisions", "validate")
        self.assertEqual((code, doc["records"]), (0, 1))

    def test_validate_exits_3_and_lists_the_problems_for_a_bad_store(self) -> None:
        self.write_record(make_record())  # no index
        code, doc = self.run_cli("decisions", "validate")
        self.assertEqual(code, 3)
        self.assertFalse(doc["ok"])
        self.assertIn("index.json", doc["problems"][0]["file"])

    def test_index_regenerates_the_index_and_refuses_an_invalid_record(self) -> None:
        # covers: DK-600d-2-ii
        self.write_record(make_record())
        code, doc = self.run_cli("decisions", "index")
        self.assertEqual((code, doc["index_written"]), (0, True))
        self.write_record(make_record(id=NEWER_ID, components=["nope"]))
        code, doc = self.run_cli("decisions", "index")
        self.assertEqual(code, 3)

    def test_publish_exits_3_when_nothing_is_staged(self) -> None:
        # covers: DK-600d-2-i
        code, doc = self.run_cli("decisions", "publish", "--run-id", RUN)
        self.assertEqual(code, 3)
        self.assertFalse(doc["ok"])

    def test_an_unknown_filter_value_exits_3_names_it_and_the_fixed_record_publishes(self) -> None:
        # covers: DK-600d-2-ii
        cases = (("components", "no_such_component"), ("roadmap_phase", "phase_no_such_phase"))
        for field_name, unknown in cases:
            with self.subTest(field=field_name):
                self.stage(make_record(**{field_name: [unknown]}))
                code, doc = self.run_cli("decisions", "publish", "--run-id", RUN)
                self.assertEqual(code, 3)
                self.assertFalse(doc["ok"])
                self.assertIn(unknown, " ".join(p["message"] for p in doc["problems"]))
                self.assertIn(f"{field_name} value '{unknown}' is not in the existing vocabulary",
                              [p["message"] for p in doc["problems"]])
                self.assertFalse((self.folder / f"{FIRST_ID}.yaml").exists())  # nothing created
                self.assertFalse((self.folder / INDEX_NAME).exists())
                self.stage(make_record())  # the record is changed to known values only
                code, doc = self.run_cli("decisions", "publish", "--run-id", RUN)
                self.assertEqual((code, doc["ok"], doc["published"]), (0, True, [FIRST_ID]))
                (self.folder / f"{FIRST_ID}.yaml").unlink()  # the next case starts unpublished
                (self.folder / INDEX_NAME).unlink()

    def test_a_missing_environment_is_exit_5(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = main(["decisions", "validate", "--repo-root", str(self.root / "nowhere")])
        self.assertEqual(code, 5)
        self.assertEqual(json.loads(out.getvalue())["error"]["code"], "decisions_environment")


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: The CLI cases go through `kernel.adapters.cli.main` with
#   --repo-root and a config override pointing the run root at a temp folder, so no test can
#   write into the checkout's docs/decisions. (#KernelDecisionStore)
# ====================================================================
