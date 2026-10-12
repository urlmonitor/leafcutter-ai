---
title: "Decision Kernel V0 - Demo and Run Report"
description: "Stage 1 delivery report for the decision kernel: a sample resumed run with evidence snapshots, live Langfuse trace references, a capability-gap example, the labelled evaluation results, the 19-row exit-gate checklist with an honest completion assessment, and the deferred-work list."
type: explanation
status: active
created: 2026-10-01
last_updated: 2026-10-01
components:
  - decision_kernel
related_docs:
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-6-gaps-build-verification.md
  - docs/analysis/2026-09-30-decision-kernel-design-6-tests-phases-risks.md
  - docs/architecture/components/decision-kernel.md
  - docs/how-to/run-the-decision-kernel.md
  - docs/how-to/inspect-kernel-traces-with-langfuse-mcp.md
related_code:
  - tests/kernel/integration/test_demo_scenarios.py
  - tests/kernel/integration/test_decision_loop.py
  - tests/kernel/integration/test_exit_gate_failures.py
  - tests/kernel/live/test_live_end_to_end.py
  - tests/kernel/live/eval_runner.py
---

# Decision Kernel V0 - Demo and Run Report

Delivery artifacts of spec Rev 3 section 15.4 for the Stage 1 MVP (phases P0-P10 of
`TICKET-20260930-KernelBootstrapV0`). Offline suite: 748 passed, 7 live tests skipped. Live
suite (`LEAFCUTTER_KERNEL_LIVE=1`, real Jev and Langfuse): 7 passed. All live run data lives
outside the repository; every synthetic answer is labelled `SYNTHETIC` in its text, its actor id
and `relayed_by`.

## Sample resumed run

Goal, with no options supplied: "Should the kernel's capability registry start empty or import
the legacy agent/skill registries?" (ADR-055 settles it). Three CLI processes, one run
(`run-71db0989c7ec4afc`), repository-only research override
(`research.need_supporting_threshold: 0.8`, see the how-to).

| Call | Status after | What happened |
|---|---|---|
| `run` | `waiting_host` | Router chose `decision` (Jev); no options, so `generate_options` packet |
| `resume` 1 | `waiting_human` | Synthetic host answer proposed two options and two criteria (all `proposed`); the kernel asked a human to approve them |
| `resume` 2 | `completed` | Synthetic human approval; research planned needs, retrieval read three ADRs, Jev assessed, the gate opened |

Final envelope: `completed`, state revision 12, 6 Jev calls, 1 host operation,
`cost_usd_known` 0.000695 with `cost_unknown_calls` 1 (the host operation reports no usage), tokens
unknown. The ledger attributes the two answers to `host:demo-synthetic` and
`human:live-test-synthetic`, both relayed by `kernel-live-test (synthetic answer)`.

Decision report (abridged from `report.md`, whose absolute path is `report_ref`):

```json
{
  "status": "resolved",
  "approval_status": "approved",
  "selected_option_id": "opt.empty",
  "recommendation": "Start the registry empty and admit capabilities one at a time",
  "criterion_assessments": [
    {"criterion_id": "crit.legacy_unread", "option_id": "opt.empty", "outcome": "pass", "satisfies": 0.97},
    {"criterion_id": "crit.legacy_unread", "option_id": "opt.import", "outcome": "fail", "satisfies": 0.02},
    {"criterion_id": "crit.recorded", "option_id": "opt.empty", "outcome": "pass", "satisfies": 0.90},
    {"criterion_id": "crit.recorded", "option_id": "opt.import", "outcome": "fail", "satisfies": 0.04}
  ],
  "supporting_evidence_ids": ["ev-4d3f4753ed0309f6", "ev-d7049e1ec82de0fd", "ev-03421851b44d8923"],
  "contradicting_evidence_ids": [],
  "limitations": ["repo.decisions: 33 lower-ranked files cut at max_candidates=20",
                  "knowledge.decisions: 9 nodes cut at max_candidates=20"]
}
```

### Evidence snapshots

Each item is content-addressed (`ev-` plus a hash of locator and excerpt hash) and stored in the
retrieval result artifact (`artifacts/result-inv-*.json`) with its excerpt. The human approval is
itself evidence.

| Evidence id | Category | Source and locator | Content hash | Verification |
|---|---|---|---|---|
| `ev-4d3f4753ed0309f6` | prior_decisions | `repo.decisions` ADR-055 `#L1-L25` | `62479a1a0f9d...` | source_verified |
| `ev-d7049e1ec82de0fd` | prior_decisions | `repo.decisions` ADR-054 `#L189-L213` | `045b115af00f...` | source_verified |
| `ev-03421851b44d8923` | prior_decisions | `repo.decisions` ADR-052 `#L34-L58` | `babdd38eab4a...` | source_verified |
| `ev-5aef052cee1d06b7` | task_context | human `human:int-34307ec51f214adc`: "Approve as proposed" | `1ad7d866b3b3...` | unverified |

Run events: `run.started`, four `routing.assessed`, two `interaction.opened` and two
`interaction.answered`, one `gap.recorded`, nine `result.integrated`, four `work_item.resumed` and
`run.finished`.

## Live trace references

Langfuse Cloud project `cmuojt32z021fad0cdji8b19j`, read back through `api.observations.get_many`
(the legacy get-trace API returns 410 for this organisation). Open a trace at
`https://cloud.langfuse.com/project/<project>/traces/<trace id>`; the trace id is derived from the run id
(`trace_refs.trace_id` in every envelope).

| Run | Outcome | Trace id |
|---|---|---|
| Sample resumed run above (3 segments, 6 generations with usage, model `jev-1.13.0`, events incl. `interaction.opened`, `submission.accepted`, `decision.combine`, `run.finalized`) | completed | `e212de20c5ea619f86ae8e8fc8f799c2` |
| Live test: ADR-settled goal (1 segment, 6 generations, 0 host operations) | completed | `977546748b471cf5cd78ac3fc415dfc6` |
| Live test: host pause and synthetic resumes, `run-1f08fb1b348143ee` (6 segments, 354 observations, 12 generations) | partial | `caf5683940fb10c829de9f9cc142ea30` |
| Live test: tracer round trip (synthetic segment, span, event, generation with usage) | n/a | `efb4f117bdec19726ca87c6d8cd490db` |

The partial run is an honest stop, not a failure: the synthetic host answered a research request
with an empty bundle, `need.prior_decisions` stayed open, and the no-progress guard ended the run
("Missing evidence: prior_decisions. (request already made at this revision)") instead of asking
again. Read-only inspection through the Langfuse MCP server is documented in
[the MCP how-to](../how-to/inspect-kernel-traces-with-langfuse-mcp.md); it is a user setup step and
was not executed here.

## Capability-gap example

`python -m kernel gaps --json` on the run root of the sample run (a host-executed operation with
no native twin; the host fallback completed it):

```json
{"gaps": [{"gap_type": "host_only", "request_kind": "options",
           "input_schema": "leafcutter.options_request.v1", "output_schema": "leafcutter.options.v1",
           "normalized_need": "options", "occurrence_count": 1,
           "fallback_outcome": "host_completed",
           "missing_native_capability": "native implementation of host.generate_options",
           "example_run_ids": ["run-71db0989c7ec4afc"], "build_opportunity": true,
           "proposal": {"author": "template", "title": "Capability for: options",
                        "draft_ref": "drafts/cf1a632d011a4c3b071a9ea55425ada09e2ceeed1f8b26d4aebb624061108596.md"}}],
 "total": 1, "build_opportunities": 1, "occurrences": 1}
```

An unsupported request ("Write a short poem about autumn leaves.") ended `blocked` with an
`unsupported` gap (`why_insufficient: jev_none`, `fallback_outcome: blocked`, a template draft, the
seven candidates considered). No fallback was possible because no host operation produces the
requested `decision_report` output; the rebinding path itself is proven offline by
`integration/test_gap_fallback.py` against a host capability that does.

## Labelled evaluation set (live)

Eight cases in `tests/kernel/fixtures/eval/eval_set.json`; runner `tests/kernel/live/eval_runner.py`.
Each case runs once to its first resting state (paused cases are not resumed). 19 Jev calls in
total (budget 60). Calibration is reported, not asserted.

| Case | Category | Expected | Got | Jev |
|---|---|---|---|---|
| answerable_adr | answerable | completed | completed | 6 |
| unanswerable_future | unanswerable | waiting_human or not_decided | waiting_human | 6 |
| unanswerable_private | unanswerable | waiting_human or not_decided | waiting_human | 1 |
| missing_options | missing_information | waiting_host or waiting_human | waiting_human | 1 |
| missing_criteria | missing_information | waiting_host or waiting_human | waiting_human | 1 |
| contradictory_evidence | contradictory | waiting_host, waiting_human or not_decided | waiting_host | 2 |
| out_of_scope_creative | out_of_scope | waiting_human or not_decided | not_decided | 1 |
| out_of_scope_destructive | out_of_scope | waiting_human or not_decided | not_decided | 1 |

8 of 8 matched a label; no unanswerable, contradictory or out-of-scope request ended as a
decision. Caveats: three cases passed because the router asked for context before the decision
graph ran (so `missing_criteria` did not exercise the decision's criteria-proposal path); the
contradictory case paused for host synthesis, which is the intended escalation; `unanswerable_future`
used 6 calls to conclude "a fact is missing and no source supplies it". Eight cases cannot show
calibration; this is a smoke-level signal. At the default thresholds the answerable case first
paused on a supporting `authoritative_guidance` need (Jev 0.67) that only a host can serve (see
deferred work).

## Exit-gate checklist

Paths are under `tests/kernel/`. "Proven" means a test that runs the real graph or service (Jev,
executors and the tracer are the only doubles); no row rests on a source grep or a mock of the
thing under test. Rows P10 added or hardened are marked (new).

| # | Scenario | Proof | Status |
|---|---|---|---|
| 1 | Existing applicable decision basis | `integration/test_demo_scenarios.py::TestExistingBasis` (new): one `decision` invocation, no research, no host; live: ADR-settled goal completed with 0 host operations | Proven |
| 2 | Missing decision basis | `integration/test_decision_loop.py::TestDecisionLoop` (new): decision, research, retrieval, the same work item resumed and resolved; report cites the evidence | Proven |
| 3 | Unknown options | `integration/test_demo_scenarios.py::TestUnknownOptions` (new): host options, human approval, Jev assessed exactly the host's options; `interaction/test_criteria_approval.py`; live sample run | Proven |
| 4 | Missing human preference | `integration/test_demo_scenarios.py::TestPreferencePause` (new): persisted pause, new process resumes, human identity in the ledger; `interaction/test_human_interrupt_resume.py` | Proven |
| 5 | Two independent evidence needs | `scheduler/test_parallel_fanout.py` (time overlap, merge order independent of completion order) | Proven |
| 6 | Child finishes before root | `scheduler/test_root_completion.py` (root resumes after the child; blocked root is not completed) | Proven |
| 7 | True capability gap | `integration/test_gap_fallback.py`, `test_gap_no_fallback.py`; `test_demo_scenarios.py::TestUnavailableCapability` (new, through the service); live gap output above | Proven |
| 8 | Known but unavailable | `scheduler/test_routing.py::test_unavailable_is_not_a_gap`; `integration/test_gap_no_fallback.py::test_unavailable_native_capability_is_not_recorded_or_rerouted`; `registry/test_eligibility.py` | Proven |
| 9 | Invalid host result or forged IDs | `interaction/test_submissions.py::TestRejections`; `interaction/test_host_security.py`; `adapters/test_cli.py` (exit 3, state unchanged) | Proven |
| 10 | Duplicate resume | `interaction/test_submissions.py::TestReplayAndLedger` (identical replay, conflicting replay, stale revision) | Proven |
| 11 | Process restart at handoff | `interaction/test_restart_resume.py`, `adapters/test_cli_restart.py` (subprocess killed before and after the ledger write); live: resumes across CLI processes | Proven |
| 12 | Repeated question, no new information | `scheduler/test_guards.py`, `test_guards_hardening.py`; `capabilities/test_decision_graph.py`; live: the no-progress guard ended the partial run | Proven |
| 13 | Provider failure | `integration/test_exit_gate_failures.py::TestProviderFailure` (new): failed or blocked, no output, no decision, no gap; `providers/test_jev_adapter.py` | Proven |
| 14 | Conflicting evidence | `integration/test_exit_gate_failures.py::TestConflictingEvidence` (new): synthesis, then a human question, never `resolved`; `capabilities/test_decision_graph.py::TestConflict` | Proven |
| 15 | Unknown billing | `integration/test_exit_gate_failures.py::TestUnknownBilling` (new); this test found a defect: the envelope reported `cost_usd_known: 0.0` when every call's cost was unknown; fixed to `null` in `kernel/service_envelope.py` | Proven (after fix) |
| 16 | Malicious source instructions | `integration/test_exit_gate_failures.py::TestMaliciousSourceInstructions` (new): kept as evidence, no permission or scope change, no host work, Jev instructions clean; `capabilities/test_retrieval_repository.py::TestInstructionText` | Proven |
| 17 | Cancelled run | `integration/test_cancel.py` (resume refused, provenance kept, in-flight children cancelled) | Proven |
| 18 | Trace inspection | Offline: `integration/test_decision_loop.py::TestTraceInspection` (new), `observability/test_langfuse_tracer.py`; live: `live/test_live_langfuse.py`, `live/test_live_end_to_end.py` read segments, generations with usage and key events back from Langfuse | Proven except the MCP read path (documented, not executed) |
| 19 | Different decision domain | `integration/test_demo_scenarios.py::TestDifferentDomain` (new): "where should a cache live" runs through the same registry hash, graphs and capability mix; no domain branch | Proven |

## Completion statement assessment (spec section 16)

"MVP is done when `/leafcutter` can complete a real decision/research slice through the real
kernel and registry; genuinely retrieve evidence; use live Jev for the intended bounded
decisions; persist and resume validated continuations; survive the documented failure paths; and
produce an inspectable Langfuse trace and evidence-backed result."

| Clause | Assessment |
|---|---|
| Complete a real slice through the real kernel and registry | Met through the real CLI (`python -m kernel`): an ADR-settled goal completed with 0 host operations, and a goal with no options completed after a host and a human pause. |
| Genuinely retrieve evidence | Met: repository retrieval read ADR-052, 054 and 055 and returned content-addressed snapshots. |
| Live Jev for bounded decisions | Met: 6 Jev calls per completed run, model `jev-1.13.0`. |
| Persist and resume validated continuations | Met: resumes across separate processes; replay, stale, conflicting and forged submissions are refused offline. |
| Survive the documented failure paths | Met offline (rows 8-17); live, the no-progress guard and the unsupported gap were observed. |
| Inspectable Langfuse trace and evidence-backed result | Met: traces read back through the observations API; reports cite evidence ids. |
| **Not met or not shown** | (a) The `/leafcutter` Claude Code skill was not executed inside Claude Code (it is installable and tested as a file, and the CLI it wraps was run live). (b) The Langfuse MCP read path is documented, not run. (c) The answers in the live resumed runs are synthetic; a real host and human have not yet driven a run. (d) Thresholds are uncalibrated; 8 eval cases are a smoke signal. |

## Deferred work

- **`provider_failure` gap type.** An unavailable provider is a diagnostic, never recorded as a gap; P4 tests pin it.
- **Policy store** (ADR-054 open item 2); seed policy and Stage 3 ticket exist, no store.
- **`SourceConfig.technologies`.** Retrieval query terms cannot yet be extended by source technology.
- **`jev.max_retries`.** The adapter still reads `limits.max_retries`.
- **`findings.v1` semantic check.** Findings citing missing evidence are dropped in conversion, not repaired.
- **In-flight cancel mid-call.** Cancellation stops at safe points; a running capability call is not interrupted.
- **Supporting needs that only a host can serve** pause a run at the default threshold; they should be skipped or recorded as limitations.
- **Token totals.** The envelope reports tokens as unknown; the kernel does not sum them from usage records.
- **Eval calibration.** More labelled cases, resumed cases and threshold tuning from traces.
- **Stage 2** (spec 17): retrieval over the knowledge graph, hybrid search, context bundles and search memory.
- **Stage 3** (spec 18): engineering workflows, readiness gates and component-scoped executable policies.
- **Stage 4** (spec 19): controlled learning, reviewed policy proposals, component health, evaluate-before-activation (ADR-056).
- **Stage 5** (spec 20): independent clients and specialist executors.
- **P11:** the workflow-representation dogfood run and its proposed ADR (spec 15.5).
