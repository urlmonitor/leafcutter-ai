"""
MODULE: tests.kernel.memory.test_store
GOAL: The file backend: precedent lookup through the generated index (filters, text match, limit,
    stale index), reading a record by id, staging into the run root only, and the null backend.
BUSINESS CONTEXT: The kernel reads precedent and stages records through the ColonyMemory port; the
    file backend must find a matching record, never serve a record the index does not describe,
    and never write into the repository (ADR-059, ADR-060).
ARCHITECTURE: A temporary repository with real schema and vocabularies, records written by the
    real dumper, the index built by the real generator.
"""

from __future__ import annotations

from kernel.memory.codec import dump_record
from kernel.memory.file_store import FileColonyMemory, filters_match, staged_dir, text_score
from kernel.memory.index import INDEX_NAME, build_entries
from kernel.memory.port import ColonyMemory, DecisionQuery, NullColonyMemory
from kernel.memory.publish import rebuild_index
from tests.kernel.memory.support import StoreCase, make_record, schema, vocabulary

FIRST_ID = "dec-0123456789abcdef"
OTHER_ID = "dec-1111111111111111"
QUESTION = "Where should the kernel file approved decisions so later runs find them?"


class TestFind(StoreCase):
    """Candidates come from the index and the text score."""

    def setUp(self) -> None:
        super().setUp()
        self.write_record(make_record())
        self.write_record(make_record(
            id=OTHER_ID, question="Which logging library should the scheduler use?",
            title="Use stdlib logging", roadmap_phase=["phase_2"]))
        report, written = rebuild_index(self.folder, schema(), vocabulary())
        self.assertTrue(written, report.problems)
        self.memory = FileColonyMemory(self.root, self.run_root)

    def test_the_same_question_is_found_first(self) -> None:
        # covers: DK-100e-1
        hits = self.memory.find_decisions(DecisionQuery(text=QUESTION))
        self.assertEqual(hits[0].record.id, FIRST_ID)
        self.assertEqual(hits[0].score, 1.0)
        self.assertEqual(hits[0].path, f"docs/decisions/{FIRST_ID}.yaml")

    def test_an_unrelated_question_finds_nothing(self) -> None:
        # covers: DK-100e-1
        query = DecisionQuery(text="Should the pricing page use a carousel?", min_score=0.3)
        self.assertEqual(self.memory.find_decisions(query), [])

    def test_a_minimum_score_and_a_limit_bound_the_result(self) -> None:
        # covers: DK-100e-1
        query = DecisionQuery(text="Where should the kernel file approved decisions?", limit=1)
        self.assertEqual(len(self.memory.find_decisions(query)), 1)
        strict = DecisionQuery(text="logging library scheduler", min_score=0.9)
        self.assertEqual([h.record.id for h in self.memory.find_decisions(strict)], [OTHER_ID])

    def test_a_facet_the_query_names_filters_out_a_record_without_overlap(self) -> None:
        # covers: DK-100e-1
        query = DecisionQuery(text="logging library scheduler",
                              roadmap_phase=["phase_kernel_1_founding"])
        self.assertEqual(self.memory.find_decisions(query), [])
        both = DecisionQuery(text="logging library scheduler", roadmap_phase=["phase_2"])
        self.assertEqual([h.record.id for h in self.memory.find_decisions(both)], [OTHER_ID])

    def test_a_repository_wide_record_passes_every_facet(self) -> None:
        # covers: DK-100e-1
        wide = make_record(id="dec-2222222222222222", repository_wide=True, components=[],
                           change_target=[], risk_surface=[], roadmap_phase=[],
                           question="Where do approved decisions live?")
        self.write_record(wide)
        rebuild_index(self.folder, schema(), vocabulary())
        query = DecisionQuery(text="approved decisions live", components=["scheduler"])
        found = [h.record.id for h in
                 FileColonyMemory(self.root, self.run_root).find_decisions(query)]
        self.assertIn("dec-2222222222222222", found)

    def test_a_record_edited_after_the_index_is_skipped(self) -> None:
        # covers: DK-100e-1
        path = self.folder / f"{FIRST_ID}.yaml"
        path.write_text(path.read_text(encoding="utf-8") + "# edited\n", encoding="utf-8")
        found = [h.record.id for h in self.memory.find_decisions(DecisionQuery(text=QUESTION))]
        self.assertNotIn(FIRST_ID, found)

    def test_a_missing_index_gives_no_precedent(self) -> None:
        # covers: DK-100e-1
        (self.folder / INDEX_NAME).unlink()
        self.assertEqual(self.memory.find_decisions(DecisionQuery(text=QUESTION)), [])

    def test_a_superseded_record_is_marked(self) -> None:
        # covers: DK-100e-3-iii
        newer = make_record(id="dec-3333333333333333", supersedes=[FIRST_ID],
                            question="Where should the kernel file approved decisions now?")
        self.write_record(newer)
        rebuild_index(self.folder, schema(), vocabulary())
        hits = FileColonyMemory(self.root, self.run_root).find_decisions(
            DecisionQuery(text=QUESTION, limit=5))
        by_id = {h.record.id: h for h in hits}
        self.assertTrue(by_id[FIRST_ID].superseded)
        self.assertEqual(by_id[FIRST_ID].superseded_by, ("dec-3333333333333333",))
        self.assertFalse(by_id["dec-3333333333333333"].superseded)


class TestGetAndStage(StoreCase):
    """Reading by id and staging into the run root."""

    def test_get_returns_the_record_or_none(self) -> None:
        self.write_record(make_record())
        memory = FileColonyMemory(self.root, self.run_root)
        self.assertEqual(memory.get_decision(FIRST_ID), make_record())
        self.assertIsNone(memory.get_decision("dec-ffffffffffffffff"))
        self.assertIsNone(memory.get_decision("../../etc/passwd"))

    def test_stage_writes_only_under_the_run_root(self) -> None:
        memory = FileColonyMemory(self.root, self.run_root)
        staged = memory.stage_decision(make_record())
        assert staged is not None
        self.assertEqual(staged.path,
                         staged_dir(self.run_root, "run-aaaaaaaaaaaaaaaa") / f"{FIRST_ID}.yaml")
        self.assertEqual(staged.path.read_text(encoding="utf-8"), dump_record(make_record()))
        self.assertFalse(self.folder.exists())  # the repository store was not touched

    def test_staging_an_unsafe_run_id_keeps_nothing(self) -> None:
        provenance = {**make_record().provenance.model_dump(), "run_id": "../escape"}
        bad = make_record(provenance=provenance)
        self.assertIsNone(FileColonyMemory(self.root, self.run_root).stage_decision(bad))


class TestNullAndHelpers(StoreCase):
    """The null backend and the pure matching helpers."""

    def test_null_memory_remembers_and_stages_nothing(self) -> None:
        memory: ColonyMemory = NullColonyMemory()
        self.assertEqual(memory.find_decisions(DecisionQuery(text="anything")), [])
        self.assertIsNone(memory.get_decision(FIRST_ID))
        self.assertIsNone(memory.stage_decision(make_record()))
        self.assertIsInstance(memory, ColonyMemory)

    def test_text_score_is_an_overlap_coefficient_of_content_words(self) -> None:
        self.assertEqual(text_score("kernel logging", "kernel logging library"), 1.0)
        self.assertEqual(text_score("pricing page", "kernel logging"), 0.0)
        self.assertEqual(text_score("", "x"), 0.0)

    def test_filters_match_ignores_a_facet_the_record_does_not_set(self) -> None:
        # covers: DK-100e-1
        record = make_record(components=[])
        entry = build_entries([(record, dump_record(record))])[0]
        self.assertTrue(filters_match(entry, DecisionQuery(text="x", components=["anything"])))


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: A record edited after the index was built is skipped rather than
#   served, so the index and the file can never disagree about what precedent says.
#   (#KernelDecisionStore)
# ====================================================================
