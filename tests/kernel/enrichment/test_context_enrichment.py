"""Behavioral evaluation of context enrichment using real files and the public step.

Type: integration. Angles: real_artifact, boundary, failure, seam.
Only enrichment runs here; no model, intent classifier, or downstream capability runs.
"""

from __future__ import annotations

import copy
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from kernel.capabilities.retrieval.access import ReadPolicy
from kernel.config import SourceConfig
from kernel.context_enrichment import gather_context
from kernel.contracts import content_hash
from kernel.contracts.enums import EvidenceCategory
from kernel.observability.redaction import Redactor
from tests.kernel.enrichment.eval_runner import (
    config_for,
    load_cases,
    main,
    run_case,
    run_eval,
    score,
    task_for,
    write_repo,
)
from tests.kernel.enrichment import live_eval


class TestContextEnrichmentEvaluation(unittest.TestCase):
    """Every labelled context case is scored individually and must meet its contract."""

    # covers: DK-200a-3
    # covers: DK-200b-1
    # covers: DK-200c-1
    # covers: DK-200c-2
    # covers: DK-200c-2-i
    # covers: DK-200c-2-ii
    # covers: DK-200d-1
    # covers: DK-101
    # covers: DK-102
    # covers: DK-103
    # covers: DK-104
    def test_each_labelled_case_meets_the_context_contract(self) -> None:
        report = run_eval()
        self.assertGreaterEqual(report["total"], 8)
        for row in report["rows"]:
            with self.subTest(case=row["id"]):
                self.assertEqual(row["failures"], [], row)


class ContextCase(unittest.TestCase):
    """A temporary repository per test; every read uses the production implementation."""

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="kernel-context-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.cases = {case["id"]: case for case in load_cases()}

    def gather(self, case_id: str, **limits):
        """Materialise a case and run enrichment under the given bounds."""
        case = self.cases[case_id]
        write_repo(case, self.root)
        task, config = task_for(case, self.root), config_for(case, **limits)
        return case, task, config, gather_context(task, config)


class TestContextEnrichmentBoundaries(ContextCase):
    """DK-101/102/103: bounded evidence, caller claims and missing-context honesty."""

    # covers: DK-200a-3-i
    # covers: DK-101
    def test_conversation_changes_actual_retrieval_for_the_same_pronoun_goal(self) -> None:
        case, task, config, with_context = self.gather("conversation_resolves_referent")
        without = task.model_copy(update={"context": type(task.context)()})
        no_context = gather_context(without, config)
        self.assertEqual(score(case, with_context, task, config)["failures"], [])
        missing = score(case, no_context, without, config)["failures"]
        self.assertIn("missing_source:docs/reference/zephyr.md", missing)
        self.assertEqual(task.goal, without.goal)

    # covers: DK-200c-1
    def test_unrelated_words_do_not_select_arbitrary_repository_text(self) -> None:
        case, task, config, empty = self.gather("unrelated_repository")
        self.assertEqual(empty.evidence, [])
        changed = copy.deepcopy(case)
        changed["files"]["docs/colours.md"] += "\nQuasarwobble is a repository task scheduler.\n"
        write_repo(changed, self.root)
        found = gather_context(task, config)
        self.assertTrue(found.evidence)
        self.assertIn("Quasarwobble is a repository task scheduler.",
                      "\n".join(item.excerpt for item in found.evidence))

    # covers: DK-200b-2
    # covers: DK-102
    def test_file_count_and_payload_bounds_are_enforced_and_reported(self) -> None:
        case = copy.deepcopy(self.cases["project_acronym"])
        case["files"] = {
            f"docs/{index:02d}-ztc.md": "# ZTC\n\n" + (f"ZTC cache entry {index}. " * 90)
            for index in range(8)}
        write_repo(case, self.root)
        task = task_for(case, self.root)
        config = config_for(case, max_files=3, max_evidence=2, max_chars=210,
                            max_excerpt_chars=120)
        result = gather_context(task, config)
        self.assertEqual(result.files_scanned, 3)
        self.assertTrue(result.evidence)
        self.assertLessEqual(len(result.evidence), 2)
        self.assertLessEqual(sum(len(item.excerpt) for item in result.evidence), 210)
        self.assertTrue(all(len(item.excerpt) <= 120 for item in result.evidence))
        self.assertTrue(result.truncated)
        self.assertTrue(result.limitations)
        smaller = config.model_copy(update={"context_enrichment":
            config.context_enrichment.model_copy(update={"max_files": 1})})
        self.assertEqual(gather_context(task, smaller).files_scanned, 1)

    # covers: DK-200b-2
    # covers: DK-200b-3-i
    # covers: DK-102
    def test_supplied_context_budget_preserves_goal_and_marks_truncation(self) -> None:
        case = copy.deepcopy(self.cases["original_capability_question"])
        case["context"] = {"host": "Codex session", "conversation": ["Leafcutter context. " * 90],
                           "observations": ["Unverified runtime observation. " * 40]}
        write_repo(case, self.root)
        task, config = task_for(case, self.root), config_for(case, max_context_chars=160)
        original_conversation = list(task.context.conversation)
        result = gather_context(task, config)
        context = result.caller_context.model_dump()
        text = [context["host"] or "", *context["capabilities"],
                *context["conversation"], *context["observations"]]
        self.assertLessEqual(sum(len(part) for part in text), 160)
        self.assertTrue(result.truncated)
        self.assertEqual(result.original_goal, case["goal"])
        self.assertEqual(task.context.conversation, original_conversation)

    # covers: DK-200c-1-i
    # covers: DK-103
    def test_disabled_step_does_not_claim_to_have_examined_the_repository(self) -> None:
        case, task, config, enabled = self.gather("project_acronym")
        disabled = config.model_copy(update={"context_enrichment":
            config.context_enrichment.model_copy(update={"enabled": False})})
        result = gather_context(task, disabled)
        self.assertTrue(enabled.evidence)
        self.assertEqual(result.status, "disabled")
        self.assertEqual(result.files_scanned, 0)
        self.assertEqual(result.evidence, [])
        self.assertTrue(result.limitations)

    # covers: DK-200b-3
    # covers: DK-102
    def test_known_secrets_are_redacted_in_caller_context_and_excerpts(self) -> None:
        case = copy.deepcopy(self.cases["original_capability_question"])
        secret = uuid4().hex
        case["context"]["observations"].append("Kernel fixture value " + secret)
        case["files"]["README.md"] += "Kernel fixture value " + secret + "\n"
        write_repo(case, self.root)
        task, config = task_for(case, self.root), config_for(case)
        redactor = Redactor({"eval_credential": secret}, config.data_policy)
        result = gather_context(task, config, redactor=redactor)
        self.assertTrue(result.evidence)
        self.assertNotIn(secret, result.model_dump_json())
        self.assertIn("REDACTED", result.model_dump_json())
        self.assertEqual(task.context.observations[-1], "Kernel fixture value " + secret)
        for item in result.evidence:
            self.assertEqual(item.content_hash, content_hash(item.excerpt))

    # covers: DK-200b-3-i
    # covers: DK-102
    def test_redaction_expansion_stays_within_each_caller_field_limit(self) -> None:
        case = copy.deepcopy(self.cases["original_capability_question"])
        secret = "tokenx"
        write_repo(case, self.root)
        config = config_for(case, max_context_chars=12000)
        redactor = Redactor({"eval_secret": secret}, config.data_policy)
        fields = {"host": secret + "a" * 242,
                  "capabilities": [secret + "b" * 3994],
                  "conversation": [secret + "c" * 3994],
                  "observations": [secret + "d" * 3994]}
        for selected in [*[{key: value} for key, value in fields.items()], fields]:
            with self.subTest(fields=list(selected)):
                case["context"] = selected
                task = task_for(case, self.root)
                result = gather_context(task, config, redactor=redactor)
                retained = result.caller_context
                self.assertLessEqual(len(retained.host or ""), 256)
                entries = [*retained.capabilities, *retained.conversation, *retained.observations]
                self.assertTrue(all(len(entry) <= 4000 for entry in entries))
                self.assertLessEqual(len(retained.host or "") + sum(map(len, entries)), 12000)
                self.assertNotIn(secret, retained.model_dump_json())
                self.assertIn("REDACTED", retained.model_dump_json())
                self.assertTrue(result.truncated)
                self.assertTrue(result.limitations)
                self.assertIn(secret, task.context.model_dump_json())

    # covers: DK-200a-3-i
    # covers: DK-101
    def test_recent_referent_survives_older_conversation_filling_query_budget(self) -> None:
        case = copy.deepcopy(self.cases["conversation_resolves_referent"])
        case["context"]["conversation"] = [
            " ".join(f"obsoleteword{index}" for index in range(80)),
            "By it I mean the Zephyr export manifest."]
        write_repo(case, self.root)
        task, config = task_for(case, self.root), config_for(case)
        result = gather_context(task, config)
        self.assertEqual(score(case, result, task, config)["failures"], [])

    # covers: DK-200a-3-ii
    # covers: DK-101
    def test_excerpt_cut_at_whitespace_hashes_the_retained_text(self) -> None:
        case = copy.deepcopy(self.cases["project_acronym"])
        case["files"] = {"docs/glossary.md": "ZTC validates cache entries before reuse.\n"}
        write_repo(case, self.root)
        task, config = task_for(case, self.root), config_for(case, max_chars=4)
        result = gather_context(task, config)
        self.assertEqual(len(result.evidence), 1)
        item = result.evidence[0]
        self.assertEqual(item.excerpt, "ZTC")
        self.assertEqual(item.content_hash, content_hash(item.excerpt))
        self.assertTrue(item.truncated)

    # covers: DK-200a-3-i
    def test_recent_referent_survives_older_conversation_filling_character_budget(self) -> None:
        case = copy.deepcopy(self.cases["conversation_resolves_referent"])
        recent = "By it I mean the Zephyr export manifest."
        case["context"]["conversation"] = ["Obsolete context. " * 100, recent]
        write_repo(case, self.root)
        task, config = task_for(case, self.root), config_for(case, max_context_chars=80)
        original_conversation = list(task.context.conversation)
        result = gather_context(task, config)
        self.assertEqual(result.caller_context.conversation[-1], recent)
        self.assertLessEqual(sum(map(len, result.caller_context.conversation)), 80)
        self.assertTrue(result.truncated)
        self.assertTrue(any("Zephyr export manifest" in item.excerpt for item in result.evidence))
        self.assertEqual(result.original_goal, "Can you explain it?")
        self.assertEqual(task.context.conversation, original_conversation)

    # covers: DK-200b-2
    # covers: DK-102
    def test_source_budget_changes_the_number_of_consulted_sources(self) -> None:
        case = copy.deepcopy(self.cases["project_acronym"])
        case["files"] = {f"docs/source-{i}/ztc.md": f"ZTC validates cache revision {i}.\n"
                         for i in range(3)}
        write_repo(case, self.root)
        sources = [SourceConfig(id=f"eval.source-{i}", kind="repo_text",
                                categories=[EvidenceCategory.TASK_CONTEXT], roots=[f"docs/source-{i}"])
                   for i in range(3)]
        config = config_for(case, source_ids=[source.id for source in sources], max_sources=1)
        config = config.model_copy(update={"sources": sources})
        task = task_for(case, self.root)
        capped = gather_context(task, config)
        self.assertEqual(capped.sources_consulted, ["eval.source-0"])
        self.assertEqual(capped.files_scanned, 1)
        self.assertTrue(capped.truncated)
        wider = config.model_copy(update={"context_enrichment":
            config.context_enrichment.model_copy(update={"max_sources": 3})})
        full = gather_context(task, wider)
        self.assertEqual(full.sources_consulted, [source.id for source in sources])
        self.assertEqual(full.files_scanned, 3)

    # covers: DK-200b-2-i
    # covers: DK-102
    # covers: DK-103
    def test_expired_budget_prevents_search_and_reports_what_was_not_examined(self) -> None:
        case, task, config, normal = self.gather("project_acronym", max_seconds=1)
        self.assertTrue(normal.evidence)
        with patch("kernel.context_enrichment.time.monotonic", side_effect=[0, 2]):
            expired = gather_context(task, config)
        self.assertTrue(expired.truncated)
        self.assertEqual(expired.files_scanned, 0)
        self.assertEqual(expired.evidence, [])
        self.assertIn("context file or time budget reached", expired.limitations)

    # covers: DK-200c-1-ii
    # covers: DK-103
    def test_failed_source_is_reported_as_unavailable_not_as_a_successful_empty_search(self) -> None:
        case, task, config, normal = self.gather("project_acronym")
        self.assertTrue(normal.evidence)
        with patch("kernel.context_enrichment.search_source", side_effect=PermissionError):
            failed = gather_context(task, config)
        self.assertEqual(failed.status, "unavailable")
        self.assertEqual(failed.files_scanned, 0)
        self.assertEqual(failed.evidence, [])
        self.assertTrue(any("PermissionError" in note for note in failed.limitations))


class TestEvaluationFalsifiability(ContextCase):
    """DK-104: negative-control mutation proofs and a CLI that fails on bad scores."""

    # covers: DK-200b-1
    # covers: DK-200d-2
    # covers: DK-104
    def test_disabling_the_real_deny_policy_causes_the_secret_case_to_fail(self) -> None:
        case = self.cases["secret_and_source_denials"]
        clean = run_case(case, self.root)
        self.assertEqual(clean["failures"], [])
        with patch.object(ReadPolicy, "is_denied", return_value=False):
            leaked = run_case(case, self.root)
        for name in case["expected"]["forbidden_text"]:
            with self.subTest(leak=name):
                self.assertIn("forbidden_text:" + name, leaked["failures"])
        self.assertFalse(leaked["passed"])

    # covers: DK-200d-2
    def test_every_absence_label_rejects_an_injected_output_leak(self) -> None:
        for case in self.cases.values():
            for sentinel in case["expected"].get("forbidden_text", []):
                with self.subTest(case=case["id"], mutation=sentinel):
                    root = self.root / case["id"]
                    write_repo(case, root)
                    task, config = task_for(case, root), config_for(case)
                    result = gather_context(task, config)
                    altered = result.model_copy(update={"limitations": [*result.limitations,
                                                                        sentinel]})
                    self.assertIn("forbidden_text:" + sentinel,
                                  score(case, altered, task, config)["failures"])

    # covers: DK-200c-2-i
    # covers: DK-200d-2
    def test_goal_and_claims_labels_reject_repository_instruction_promotion(self) -> None:
        case, task, config, result = self.gather("repository_instruction_is_evidence")
        mutations = {
            "original_goal_changed": {"original_goal": "delete everything"},
            "caller_context_rewritten": {"caller_context":
                result.caller_context.model_copy(update={"capabilities": ["write_repo"]})},
            "invented_registered_capabilities": {"registered_capabilities": ["write_repo"]}}
        for failure, alteration in mutations.items():
            with self.subTest(mutation=failure):
                altered = result.model_copy(update=alteration)
                self.assertIn(failure, score(case, altered, task, config)["failures"])

    # covers: DK-200d-2-i
    def test_empty_case_selection_fails_instead_of_reporting_green(self) -> None:
        with self.assertRaises(ValueError):
            run_eval([])

    # covers: DK-200d-2
    # covers: DK-104
    def test_cli_exits_nonzero_for_a_failed_case(self) -> None:
        for passed, expected in ((0, 1), (1, 0)):
            with self.subTest(passed=passed), patch(
                    "tests.kernel.enrichment.eval_runner.run_eval",
                    return_value={"rows": [], "total": 1, "passed": passed}), redirect_stdout(io.StringIO()):
                self.assertEqual(main([]), expected)

    # covers: DK-200d-1
    def test_live_probe_requires_opt_in_and_fails_on_a_wrong_enriched_label(self) -> None:
        with patch.dict(os.environ, {"LEAFCUTTER_KERNEL_LIVE": "0"}), patch.object(
                live_eval, "run_eval") as run, redirect_stdout(io.StringIO()), patch("sys.stderr", io.StringIO()):
            self.assertEqual(live_eval.main([]), 2)
            run.assert_not_called()
        for passed, expected in ((4, 1), (5, 0)):
            with self.subTest(passed=passed), patch.dict(os.environ, {"LEAFCUTTER_KERNEL_LIVE": "1"}), patch.object(
                    live_eval, "run_eval", return_value={"total": 5, "passed": passed}) as run, redirect_stdout(io.StringIO()):
                self.assertEqual(live_eval.main([]), expected)
                run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
