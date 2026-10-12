"""
MODULE: tests.kernel.adapters.test_cli_gaps
GOAL: Test `python -m kernel gaps --json`: one JSON document with the aggregated, deduplicated
    capability gaps, occurrence counts, example run ids, the build-opportunity marker, and no
    need for a Jev credential or an existing run.
BUSINESS CONTEXT: The gap view is how a maintainer sees what the kernel could not serve; it must
    count one need once however often and however worded it was asked, and must mark only
    unsupported and host-only gaps as build opportunities (Rev 3 section 14).
ARCHITECTURE: Observations are written through the real FileGapStore under a temporary run root;
    the command runs both in-process (fast) and as the harness child process (one-document
    stdout contract). One test records a real gap by driving a fallback run through the service.
"""

from __future__ import annotations

import asyncio
import json
import unittest
from datetime import UTC, datetime, timedelta

from kernel.adapters.cli import gaps_document
from kernel.contracts import (
    CapabilityGap,
    FallbackOutcome,
    GapType,
    RequestKind,
    RunStatus,
    compute_gap_key,
    new_id,
    schema_ids,
)
from kernel.persistence import FileGapStore
from kernel.service import KernelService
from tests.kernel.adapters.cli_support import CliSession
from tests.kernel.adapters.support import answer, rig_environment
from tests.kernel.integration.test_gap_fallback import fallback_rig

T0 = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


def observation(run_id: str, gap_type: GapType = GapType.UNSUPPORTED, need: str = "prior_decisions",
                minutes: int = 0, outcome: FallbackOutcome = FallbackOutcome.BLOCKED
                ) -> CapabilityGap:
    """Return one raw observation of a gap (one occurrence in one run)."""
    at = T0 + timedelta(minutes=minutes)
    return CapabilityGap(
        id=new_id("gap"), created_at=at, updated_at=at, first_seen=at, last_seen=at,
        gap_key=compute_gap_key(gap_type, RequestKind.EVIDENCE, schema_ids.RETRIEVAL_REQUEST,
                                schema_ids.EVIDENCE_BUNDLE, need, []),
        gap_type=gap_type, goal=f"Find {need}", normalized_need=need,
        request_kind=RequestKind.EVIDENCE, input_schema=schema_ids.RETRIEVAL_REQUEST,
        output_schema=schema_ids.EVIDENCE_BUNDLE, example_run_ids=[run_id],
        fallback_outcome=outcome)


class GapsCase(unittest.TestCase):
    def setUp(self) -> None:
        self.session = CliSession("host")
        self.addCleanup(self.session.close)
        self.store = FileGapStore(self.session.root)

    def seed(self) -> None:
        """Record two runs of one unsupported need plus a permission and an ambiguous gap."""
        for run_id, minutes in (("run-a", 0), ("run-b", 5)):
            self.store.record(observation(run_id, minutes=minutes))
        self.store.record(observation("run-c", GapType.PERMISSION, "internal_principles", 7))
        self.store.record(observation("run-d", GapType.AMBIGUOUS, "existing_patterns", 9,
                                      FallbackOutcome.NONE))


class TestGapsCommand(GapsCase):
    def test_an_empty_store_prints_an_empty_view_and_needs_no_run(self) -> None:
        result = self.session.inprocess("gaps", "--json")
        self.assertEqual(result.code, 0, result.stderr)
        self.assertEqual(result.document(), {"gaps": [], "total": 0, "build_opportunities": 0,
                                             "occurrences": 0})

    def test_observations_are_aggregated_by_need_with_counts_and_example_runs(self) -> None:
        self.seed()
        result = self.session.inprocess("gaps", "--json")
        self.assertEqual(result.code, 0, result.stderr)
        document = result.document()
        self.assertEqual((document["total"], document["occurrences"]), (3, 4))
        by_need = {g["normalized_need"]: g for g in document["gaps"]}
        repeated = by_need["prior_decisions"]
        self.assertEqual(repeated["occurrence_count"], 2)
        self.assertEqual(repeated["example_run_ids"], ["run-a", "run-b"])
        self.assertEqual(repeated["first_seen"] < repeated["last_seen"], True)

    def test_only_unsupported_and_host_only_gaps_are_build_opportunities(self) -> None:
        self.seed()
        self.store.record(observation("run-e", GapType.HOST_ONLY, "options", 11,
                                      FallbackOutcome.HOST_COMPLETED))
        document = self.session.inprocess("gaps").document()
        marked = {g["gap_type"]: g["build_opportunity"] for g in document["gaps"]}
        self.assertEqual(marked, {"unsupported": True, "host_only": True, "permission": False,
                                  "ambiguous": False})
        self.assertEqual(document["build_opportunities"], 2)

    def test_the_child_process_prints_exactly_one_json_document_without_a_credential(self
                                                                                      ) -> None:
        self.seed()
        result = self.session.cli("gaps", "--json", nojev=True)
        self.assertEqual(result.code, 0, result.stderr)
        self.assertEqual(result.document()["total"], 3)

    def test_gaps_document_is_pure_over_the_aggregated_gaps(self) -> None:
        self.seed()
        document = gaps_document(self.store.load_gaps())
        self.assertEqual([g["gap_key"] for g in document["gaps"]],
                         sorted(g["gap_key"] for g in document["gaps"]))
        json.dumps(document)  # JSON-serialisable as printed

    def test_an_unreadable_line_in_the_store_does_not_break_the_view(self) -> None:
        self.seed()
        with self.store.observations_file.open("a", encoding="utf-8") as handle:
            handle.write("{not json\n")
        self.assertEqual(self.session.inprocess("gaps").document()["total"], 3)


class TestGapFromARealFallbackRun(unittest.TestCase):
    def test_a_run_with_a_host_fallback_shows_up_as_one_gap_with_its_outcome(self) -> None:
        session = CliSession("host")
        self.addCleanup(session.close)
        rig = fallback_rig()

        async def run_twice() -> None:
            for _ in range(2):
                service = KernelService(rig_environment(session.root, rig))
                paused = await service.start_run(rig.task_input())
                done = await KernelService(rig_environment(session.root, rig)).resume_run(
                    paused.run_id, answer(paused))
                assert done.status is RunStatus.COMPLETED

        asyncio.run(run_twice())
        document = session.inprocess("gaps", "--json").document()
        (gap,) = document["gaps"]
        self.assertEqual((gap["gap_type"], gap["fallback_outcome"], gap["occurrence_count"]),
                         ("unsupported", "host_completed", 2))
        self.assertTrue(gap["build_opportunity"])
        self.assertEqual(gap["proposal"]["author"], "template")
        draft = session.root / "gaps" / gap["proposal"]["draft_ref"]
        self.assertIn("NOT a registry entry", draft.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 15:20 [python-coder]: The real-run test uses the service and file stores (not a
#   hand-built observation) so the view is proven against what the scheduler actually writes.
#   (#KernelBootstrapV0/P9)
# ====================================================================
