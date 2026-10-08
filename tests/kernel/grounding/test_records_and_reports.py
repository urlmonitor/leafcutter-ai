"""
MODULE: tests.kernel.grounding.test_records_and_reports
GOAL: Tests of the gap record fixes (stable first-seen title, need-based draft title, a draft for
    every build opportunity, honest decline schema and wording), per-provider usage rows with
    model ids and known costs, and the Langfuse trace link in report.md and the envelope.
BUSINESS CONTEXT: Gap drafts feed the capability backlog and the envelope feeds cost review and
    trace inspection (Rev 3 sections 12, 14 and 16); a draft titled with an unrelated goal, a
    decline blaming caller permissions, or a usage row without model and cost cannot be acted on.
ARCHITECTURE: Pure helpers and the real aggregation, draft renderer, envelope builder and report
    renderer; the decline checks go through the real service with the intent scenario rig.
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast

from kernel.contracts import CapabilityGap, GapType, RunStatus, Usage
from kernel.intent.roots import write_denial_reason
from kernel.observability.tracer import TraceState
from kernel.persistence.base import aggregate_gaps
from kernel.persistence.gap_store import publish_gap, render_gap_draft
from kernel.persistence.memory import MemoryGapStore
from kernel.scheduler import guards
from kernel.scheduler.nodes_lifecycle import render_report_md
from kernel.scheduler.state import Budgets, KernelState, RunOutcome
from kernel.service_envelope import _usage
from tests.kernel.helpers import narrow
from tests.kernel.intent.support import SURE, IntentCase

NOW = datetime(2026, 10, 1, 4, 23, tzinfo=UTC)


def _gap(**changes: Any) -> CapabilityGap:
    fields: dict[str, Any] = dict(
        id="gap-0000000000000001", gap_key="k" * 16, gap_type=GapType.HOST_ONLY,
        goal="Where are tests saved in leafcutter?", normalized_need="synthesize_evidence",
        need_title="Where are tests saved in leafcutter?", request_kind="synthesis",
        input_schema="leafcutter.synthesis_request.v1", output_schema="leafcutter.findings.v1",
        created_at=NOW, first_seen=NOW, last_seen=NOW)
    fields.update(changes)
    return CapabilityGap(**fields)


class TestGapRecords(unittest.TestCase):
    """Titles, drafts and aggregation of gap records."""

    def test_the_merged_gap_keeps_the_first_seen_readable_need(self) -> None:
        first = _gap()
        later = _gap(id="gap-0000000000000002", goal="Come up with ideas",
                     need_title="Come up with ideas", last_seen=NOW + timedelta(hours=1),
                     created_at=NOW + timedelta(hours=1), first_seen=NOW + timedelta(hours=1))
        (merged,) = aggregate_gaps([later, first])
        self.assertEqual(merged.need_title, "Where are tests saved in leafcutter?")
        self.assertEqual(merged.goal, "Where are tests saved in leafcutter?")
        self.assertEqual(merged.last_seen, NOW + timedelta(hours=1))

    def test_a_draft_is_titled_from_the_need_not_the_root_goal(self) -> None:
        store = MemoryGapStore()
        stored = publish_gap(store, _gap())
        self.assertIsNotNone(narrow(stored).proposal)
        self.assertNotIn("Where are tests saved", narrow(narrow(stored).proposal).title)
        self.assertIn("synthesis", narrow(narrow(stored).proposal).title)
        draft = store.drafts[narrow(narrow(narrow(stored).proposal).draft_ref)]
        self.assertNotIn("Where are tests saved", draft.split("\n")[0])

    def test_an_evidence_gap_is_titled_by_its_category(self) -> None:
        gap = _gap(request_kind="evidence", normalized_need="authoritative_guidance",
                   need_title="Official documentation ... Question: Where are tests saved?")
        stored = publish_gap(MemoryGapStore(), gap)
        self.assertIn("authoritative_guidance", narrow(narrow(stored).proposal).title)
        self.assertNotIn("Where are tests saved", narrow(narrow(stored).proposal).title)

    def test_a_host_only_gap_with_a_native_twin_still_gets_a_draft(self) -> None:
        store = MemoryGapStore()
        twin = _gap(request_kind="evidence", normalized_need="authoritative_guidance",
                    why_insufficient="host-backed only; native alternatives for this request "
                                     "kind: research, retrieve.repository")
        stored = publish_gap(store, twin)
        self.assertIsNotNone(narrow(stored).proposal)
        self.assertIn("native alternatives", store.drafts[narrow(narrow(narrow(stored).proposal).draft_ref)])

    def test_a_declined_gap_does_not_claim_a_report_schema(self) -> None:
        text = render_gap_draft(_gap(gap_type=GapType.UNSUPPORTED, output_schema="none"))
        self.assertIn("Output schema: none", text)

    def test_the_write_denial_names_the_design_not_the_callers_permissions(self) -> None:
        for permissions in (["read_repo"], ["read_repo", "write_repo"]):
            reason = write_denial_reason(permissions)
            self.assertIn("read-only by design", reason)
            self.assertNotIn("permissions do not allow", reason)


class TestDeclinedGapRecords(IntentCase):
    """A decline records its classified kind, never the report schema it never produced."""

    async def test_declined_gaps_have_no_output_schema_and_an_accurate_reason(self) -> None:
        self.intents = [("change", *SURE)]
        envelope = await self.service().start_run(self.goal_task("Implement a critical AC."))
        self.assertEqual(envelope.status, RunStatus.BLOCKED)
        (gap,) = self.service().list_gaps()
        self.assertEqual(gap.gap_type, GapType.PERMISSION)
        self.assertEqual(gap.output_schema, "none")
        self.assertIn("read-only by design", gap.why_insufficient)
        self.assertNotIn("caller's permissions", gap.why_insufficient)


class TestUsageRows(unittest.TestCase):
    """One row per provider and model, with known cost and unknown left null."""

    def _budgets(self, *usages: Usage) -> Budgets:
        return guards.account_usage(Budgets(jev_calls=1, host_operations=1), usages, None)

    def test_jev_rows_carry_the_model_id_and_the_summed_cost(self) -> None:
        jev: dict[str, Any] = dict(provider="jev", model_id="jev-1.13.0", input_tokens=100, output_tokens=10,
                   cost_usd=0.001, cost_provenance="estimated", calls=1)
        summary = _usage({"budgets": self._budgets(Usage(**jev), Usage(**jev))})
        (row,) = summary.usage
        self.assertEqual((row.provider, row.model_id, row.calls), ("jev", "jev-1.13.0", 2))
        self.assertAlmostEqual(narrow(row.cost_usd), 0.002)
        self.assertEqual(row.cost_provenance, "estimated")
        self.assertEqual((row.input_tokens, row.output_tokens), (200, 20))

    def test_host_reported_usage_and_model_get_their_own_row(self) -> None:
        jev = Usage(provider="jev", model_id="jev-1.13.0", cost_usd=0.001,
                    cost_provenance="estimated", calls=1)
        host = Usage(provider="host", model_id="claude-x", input_tokens=500, output_tokens=40,
                     calls=1)
        summary = _usage({"budgets": self._budgets(jev, host)})
        rows = {r.provider: r for r in summary.usage}
        self.assertEqual(rows["host"].model_id, "claude-x")
        self.assertEqual(rows["host"].input_tokens, 500)

    def test_an_unknown_cost_stays_null_never_zero(self) -> None:
        host = Usage(provider="host", calls=1, duration_ms=1500)
        summary = _usage({"budgets": self._budgets(host)})
        (row,) = summary.usage
        self.assertIsNone(row.cost_usd)
        self.assertEqual(row.cost_provenance, "unavailable")
        self.assertIsNone(row.input_tokens)
        self.assertIsNone(row.model_id)

    def test_a_partly_known_cost_row_is_not_presented_as_complete(self) -> None:
        known = Usage(provider="jev", model_id="m", cost_usd=0.001, cost_provenance="reported",
                      calls=1)
        unknown = Usage(provider="jev", model_id="m", calls=1)
        (row,) = _usage({"budgets": self._budgets(known, unknown)}).usage
        self.assertIsNone(row.cost_usd)


class TestTraceLink(unittest.TestCase):
    """The report names the Langfuse trace so a reader can open it."""

    def _state(self, trace: TraceState | None) -> KernelState:
        return cast(KernelState, {"run_id": "run-0000000000000001", "work_items": {},
                "task": SimpleNamespace(original_goal="Where are tests saved?"),
                **({"trace": trace} if trace else {})})

    def test_report_md_links_the_trace_when_tracing_exported_one(self) -> None:
        url = "https://cloud.langfuse.com/project/p/traces/abc"
        text = render_report_md(self._state(TraceState(trace_id="abc", trace_url=url)),
                                RunOutcome(status=RunStatus.COMPLETED))
        self.assertIn(f"- Trace: {url}", text)

    def test_report_md_has_no_trace_line_when_tracing_is_off(self) -> None:
        text = render_report_md(self._state(TraceState(trace_id="abc")),
                                RunOutcome(status=RunStatus.COMPLETED))
        self.assertNotIn("Trace:", text)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 23:00 [python-coder]: Tests for G7, G8 and G9 written first and seen failing.
#   (#KernelBootstrapV0/GROUND)
# ====================================================================
