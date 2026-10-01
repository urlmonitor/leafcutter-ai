---
title: "Decision Kernel V0 Design - Part 6 of 6: Tests, Phases and Risks"
description: "Test plan mapped one-to-one to the Revision 3 section 16 exit gate and the V0 testing strategy, the ten-phase implementation plan in spec section 15.2 order with exact file ownership, dependencies and parallel-safe groupings, the coding conventions every phase must follow to pass this repo's hooks, and the open risks."
type: explanation
status: active
created: 2026-09-30
last_updated: 2026-09-30
components:
  - decision_kernel
---

# Decision Kernel V0 Design — Part 6 of 6: Tests, phases and risks

**Status (2026-10-01): P0-P10 complete.** The Stage 1 exit gate is proven by offline scenario
tests and one live run; see the [V0 demo and run report](2026-10-01-decision-kernel-v0-demo-report.md).
The tables below are the plan; the test names in the §16 table are the as-built ones.

Back to [part 1](2026-09-30-decision-kernel-design.md). Exit gate: §16 in
[spec part 6](2026-09-30-leafcutter-kernel-spec-rev3-6-gaps-build-verification.md).

## Test layout

All kernel tests live in `tests/kernel/`, with an `__init__.py` in every directory.
`tests/` is a package, so modules import as `tests.kernel.*`. A
`unit_tests/kernel/` package would shadow the real `kernel` under pytest's
prepend import mode.

Shared helpers live in `tests/kernel/helpers.py` and are imported explicitly (no
conftest, per `tests/README`). They provide:

- a temporary run root
- `ScriptedJev` scripts
- `RecordingTracer`
- fake capability executors
- `FakeHostResponder`, which answers `waiting_host` envelopes from fixtures

The integration step (after wave B) created `tests/kernel/integration/__init__.py` and
`integration/test_wiring.py`. The wiring test runs the real graph with the real P5 executors,
`ScriptedJev`, the P2 file stores and the real sqlite checkpointer. It is a smoke test for the
seams between phases only; P9 and P10 add their scenario tests as new files in that package.

Rules for every test:

- **Offline by default.** No network. Jev is always `ScriptedJev` or an `httpx2.MockTransport`-backed classifier.
- **Live tests** live in `tests/kernel/live/` and are guarded by `@pytest.mark.skipif(os.environ.get("LEAFCUTTER_KERNEL_LIVE") != "1", …)`. Use `skipif`, never `pytest.skip`, because `check-contract-shrinking` rejects the latter. No new pytest markers.
- **Real entry points.** Assert behaviour through the real entry points: `graph.ainvoke`, `RunService`, and `python -m kernel` as a subprocess. Never by grepping source (CLAUDE.md "verify behaviorally").

## Spec §16 exit gate → tests

| §16 scenario | Test (path under `tests/kernel/`) | Phase |
|---|---|---|
| Existing applicable decision basis | `integration/test_demo_scenarios.py::TestExistingBasis::test_existing_basis_resolves_without_host_work` | P10 |
| Missing decision basis → evidence → resume | `integration/test_decision_loop.py::TestDecisionLoop::test_insufficient_then_research_then_resolved` | P10 |
| Unknown options | `integration/test_demo_scenarios.py::TestUnknownOptions::test_unknown_options_use_host_proposals_then_human_approval`; `interaction/test_criteria_approval.py` | P6, P10 |
| Missing human preference | `interaction/test_human_interrupt_resume.py`; `integration/test_demo_scenarios.py::TestPreferencePause::test_preference_pauses_and_resumes` | P6, P10 |
| Two independent evidence needs run concurrently | `scheduler/test_parallel_fanout.py::test_independent_children_overlap_in_time` and `::test_merge_order_is_independent_of_completion_order` | P4 |
| Child finishes before root | `scheduler/test_root_completion.py::test_root_resumes_after_child_and_only_then_completes`, `::test_child_completed_but_root_blocked_is_not_completed` | P4 |
| True capability gap | `integration/test_gap_fallback.py`, `integration/test_gap_no_fallback.py`; `integration/test_demo_scenarios.py::TestUnavailableCapability` | P9, P10 |
| Known but unavailable | `registry/test_eligibility.py`; `scheduler/test_routing.py::test_unavailable_is_not_a_gap`; `integration/test_gap_no_fallback.py::test_unavailable_native_capability_is_not_recorded_or_rerouted` | P1, P4, P9 |
| Invalid host result or forged IDs | `interaction/test_submissions.py::TestRejections` (`test_rejects_*`); `interaction/test_host_security.py` | P6, P8 |
| Duplicate resume | `interaction/test_submissions.py::TestReplayAndLedger::test_identical_replay_idempotent`, `::test_conflicting_replay_is_rejected_without_state_loss`, `TestRejections::test_rejects_stale_revision` | P6 |
| Process restart at handoff | `interaction/test_restart_resume.py` and `adapters/test_cli_restart.py` (CLI subprocess killed before and after the ledger write) | P6, P7 |
| Repeated question, no new information | `scheduler/test_guards.py::test_reworded_repeat_is_blocked_after_the_limit`, `::test_passes_without_progress_across_items_halt_the_run`; `scheduler/test_guards_hardening.py`; `capabilities/test_decision_graph.py::test_same_request_at_same_revision_is_partial_no_progress` | P4, P9 |
| Provider failure | `integration/test_exit_gate_failures.py::TestProviderFailure`; `providers/test_jev_adapter.py::test_retries_then_unavailable`; `scheduler/test_routing.py::test_provider_unavailable_fails_without_gap` | P3, P4, P10 |
| Conflicting evidence | `integration/test_exit_gate_failures.py::TestConflictingEvidence`; `capabilities/test_decision_graph.py::TestConflict::test_conflict_escalates`; `capabilities/test_research_graph.py::test_conflict_recorded` | P5, P10 |
| Unknown billing | `integration/test_exit_gate_failures.py::TestUnknownBilling`; `contracts/test_models.py::test_usage_unknown_is_none`; `capabilities/test_host_operations.py::test_host_usage_unavailable` | P1, P8, P10 |
| Malicious source instructions | `integration/test_exit_gate_failures.py::TestMaliciousSourceInstructions`; `capabilities/test_retrieval_repository.py::TestInstructionText` | P5, P10 |
| Cancelled run | `integration/test_cancel.py` | P9 |
| Trace inspection | `integration/test_decision_loop.py::TestTraceInspection`; `observability/test_langfuse_tracer.py` (in-memory OTel exporter; correlation IDs); `live/test_live_langfuse.py`, `live/test_live_end_to_end.py` | P2, P10 |
| Different decision domain | `integration/test_demo_scenarios.py::TestDifferentDomain::test_cache_location_question_uses_same_graphs` | P10 |

The as-built checklist (scenario, proof, status), with the live evidence, is in the
[V0 demo and run report](2026-10-01-decision-kernel-v0-demo-report.md).

Earlier V0 §25 items are covered as follows:

- **Contract validation and serialization.** `contracts/test_models.py`, `test_schema_catalog.py`, `test_fixtures.py` (valid/invalid JSON fixtures per schema id), `test_schema_export.py` (committed JSON Schemas match) and `persistence/test_checkpointer_serde.py` (strict msgpack round-trip). Owners: P1, P2.
- **Routing, including NONE and low confidence.** `scheduler/test_routing.py`.
- **Merge semantics.** `scheduler/test_merge.py`.
- **Every guard.** `scheduler/test_guards.py`.
- **Registry adaptation.** `registry/test_registry_load.py` and `test_bindings.py`.
- **Host fallback with a fake adapter.** `capabilities/test_host_operations.py`.
- **Live suite.** `live/test_live_jev.py`, `live/test_live_langfuse.py`, `live/test_live_end_to_end.py` and `live/test_live_eval.py` (the labelled evaluation set, `fixtures/eval/eval_set.json`; its shape is checked offline by `integration/test_eval_set.py`).

## Phase plan (spec §15.2 order)

"Owns" lists the files a phase creates or edits. No two phases in the same wave touch the same
file. A file handed from one phase to the next is marked "takes over".

| Phase | §15.2 | Owns (under `kernel/` unless given as a full path) | Depends on | Parallel-safe with |
|---|---|---|---|---|
| **P0** (done) | Stage 0 | `requirements-dev.txt`, `docs/components.json` (`decision_kernel` entry), `kernel/__init__.py`, ticket, spec copy, design docs, `docs/architecture/components/decision-kernel.md` | — | — |
| **P1** | 1 | `config.py`, `secrets.py`, `service.py` (protocol only), `contracts/*` (12 files), `schemas/*`, `registry/*`, `providers/{__init__,base,fakes}.py`, `observability/{__init__,tracer,correlation}.py`, `persistence/{__init__,base,memory}.py`, `capabilities/{__init__,base}.py`, `config/capability_registry.json` (empty) + `.schema.json`, `config/kernel_config.default.json` + `.schema.json`, `tests/kernel/{__init__,helpers}.py`, `tests/kernel/{fixtures,contracts,registry,config}/**`, `tests/kernel/observability/test_recording_tracer.py` | P0 | — |
| **P2** | 2 | `persistence/{run_store,checkpointer,gap_store,artifacts}.py`, `observability/{langfuse_tracer,redaction,spool}.py`, `tests/kernel/persistence/**`, `tests/…/observability/{test_langfuse_tracer,test_redaction}.py` | P1 | P3, P4, P5 |
| **P3** | 3 | `providers/{jev,jev_errors}.py`, `tests/…/providers/**`, `tests/…/live/{__init__,test_live_jev}.py` | P1 | P2, P4, P5 |
| **P4** | 4 (+ base guards of 9) | `scheduler/*` except where later taken over. P4 creates `nodes_interaction.py` (basic open/await with `interrupt`) and `nodes_gaps.py` (record, then block). `tests/…/scheduler/**` | P1 | P2, P3, P5 |
| **P5** | 5 | `capabilities/{decision,research,retrieval}/**`; `config/capability_registry.json` entries (all 7, including `host.*` descriptors); `tests/…/capabilities/test_{decision_graph,research_graph,retrieval_repository,knowledge_map_bridge}.py` | P1 | P2, P3, P4 |
| **P6** | 6 | Takes over `scheduler/nodes_interaction.py`; `interaction/{__init__,submissions,packets}.py`; `tests/…/interaction/**` | P2, P4 | — |
| **P7** | 7 | Takes over `service.py` (implementation); `bootstrap.py`, `__main__.py`, `__init__.py` (re-exports), `adapters/**` incl. `claude_code/{SKILL.md,install.py}`; `tests/…/adapters/**` | P2, P3, P5, P6 | — |
| **P8** | 8 | `capabilities/host/**`; edits `bootstrap.py` (registers `host.*` bindings) after P7; `tests/…/capabilities/test_host_operations.py` | P6, P7 | — |
| **P9** | 9 | Takes over `scheduler/nodes_gaps.py` and `scheduler/guards.py` (hardening); edits `service.py` (`cancel_run` path); `tests/…/integration/{test_gap_fallback,test_gap_no_fallback,test_cancel}.py` (the integration step already created `integration/__init__.py` and `integration/test_wiring.py`), `tests/…/scheduler/test_guards_hardening.py` | P7, P8 | — |
| **P10** | 10 | `tests/…/integration/{test_decision_loop,test_demo_scenarios}.py` (add to the existing `integration/` package), `tests/…/live/{test_live_langfuse,test_live_end_to_end}.py`, `docs/how-to/run-the-decision-kernel.md`, `docs/how-to/inspect-kernel-traces-with-langfuse-mcp.md`, demo report doc, `changelogs/<entry>.md`, `docs/components.json` (status active, `exposed_interfaces`), updates to this design series | all | — |
| **P11** (after MVP) | §15.5 | Dogfood run on workflow representation; a proposed ADR (number allocated when it is written), never auto-approved | P10 | — |

**Waves.**

| Wave | Phases |
|---|---|
| A | P1 |
| B | P2, P3, P4, P5 in parallel (disjoint files; each depends only on P1's ports, fakes and contracts) |
| C | P6 |
| D | P7 |
| E | P8 |
| F | P9 |
| G | P10 |

**Shared files and their single owners.**

| File | Owner |
|---|---|
| `requirements-dev.txt` | P0 |
| `config/kernel_config.*` | P1 |
| `config/capability_registry.schema.json` | P1 |
| `config/capability_registry.json` | P1 (created empty), then P5 |
| `docs/components.json` | P0, then P10 |
| `bootstrap.py` | P7, then P8 |
| `service.py` | P1, then P7, then P9 |

A config key missing from part 2 needs an orchestrator-sequenced edit. Never add one in parallel.

## Conventions every phase must follow

- **Documentation.**
  - Every `.py` file starts with a module docstring that has `MODULE`, `GOAL`, `BUSINESS CONTEXT` and `ARCHITECTURE`, and every public function and class has a docstring.
  - Files end with a `DECISION HISTORY` block. Entries use the format `- YYYY-MM-DD HH:MM [agent]: why. (#KernelBootstrapV0/P<n>)`. The tail-tag grammar requires the `/`.
- **Size.**
  - Files have a hard limit of 400 lines and a target of 300.
  - No folder may hold more than 15 non-markdown files.
  - Docs under `docs/` have at most 300 body lines and 25 `##` sections.
  - Any `docs/architecture/**` doc containing mermaid needs `parent:`/`children:` wiring or `root: true`.
- **Error handling (commit-blocking).**
  - `open()` and `subprocess.*` calls must sit inside `try` (IO-001).
  - No bare or blind `except` unless it logs at WARNING or above, or re-raises.
  - On every write, the PostToolUse hook runs `ruff --select E722,BLE001,TRY`. Define exception classes that build their own message (TRY003), return from `else:` (TRY300), and use `logger.exception` (TRY400).
- **Hook traps.**
  - Never use the words "stub", "placeholder" or "TODO" in the docstring of a `None`-default fallback (`check-placeholder-defaults`).
  - Never assign a quoted literal of 8 or more characters to a name containing password, secret, token or auth_key, not even a fake value in a test (`check-secrets` rule `GENERIC_SECRET`). Build test keys at runtime or keep them under 8 characters.
  - Do not use Python-3.14-only APIs (for example `uuid.uuid7`): CI runs 3.13.
- **Git hygiene.**
  - Stage files by explicit path only. The worktree carries about 62 unrelated build-modified files, so `git add -A` is forbidden.
  - Commit through the `commit` agent with `ticket_path=tickets/00_inbox/TICKET-20260930-KernelBootstrapV0.md`.
  - The PR needs a `changelogs/*.md` entry (CI `changelog-presence`), which P10 adds.
- **Logging.** Use `logging.getLogger(__name__)`. Never call `basicConfig` at import. Never log secret values.

## Risks and open issues

| # | Risk | Mitigation / owner |
|---|---|---|
| 1 | The `/leafcutter` skill-vs-command precedence is undocumented, and the name collides with the shipped knowledge hub | User decision (part 5); P7 verifies empirically |
| 2 | `langchain-typesafe` 0.0.1a3 is a `@beta` pre-release, so its API may change | Exact pin; the port isolates it; fallback is the `judge.py` HTTP shape behind the same port (P3) |
| 3 | Thresholds are uncalibrated (the smoke noul gave 0.69 for "requirements missing" on a clear task) | All values live in config and are traced. P10 added the labelled set (8 cases) and a live runner; results are reported in the demo report, not asserted. Still uncalibrated: a supporting need only a host could serve paused an ADR-settled decision at the default threshold |
| 4 | Jev cannot follow state across calls ("indirection"; see [the Jev triage evaluation](2026-09-25-jev-test-triage-evaluation.md)) | Literal, atomic templates; dependent judgments are combined in code |
| 5 | `aupdate_state(as_node="finalize")` on an interrupted thread is not yet verified | P9 verifies; `run.json` stays authoritative for cancellation |
| 6 | Nodes re-execute on resume | No side effects before `interrupt()`; tracer spans in `await_interaction` open only after resume |
| 7 | The knowledge map takes about 11.7 s per full build and is rebuilt per CLI process | Surface filter, per-process cache, timeout; a slow source becomes a limitation |
| 8 | The CI ruff job lints only `scripts tests unit_tests`, so `kernel/` is not linted in CI | **Resolved in P10** (user-approved): the job now runs `ruff check scripts tests unit_tests kernel` and `ruff check kernel --select E722,BLE001,TRY` |
| 9 | The Langfuse legacy trace API returns 410; MCP tool names are unverified | **Resolved in P10:** the observations API is used everywhere; the MCP tools are documented in [the MCP how-to](../how-to/inspect-kernel-traces-with-langfuse-mcp.md); the user configures MCP |
| 10 | CI now installs langchain, langgraph and langfuse | Accepted; the pins keep it reproducible |
| 11 | `transform-doc-index` regenerates `docs/INDEX.md` on every docs commit | Review the INDEX diff before each commit |
| 12 | In the main checkout, `.leafcutter/` may be a symlink to the shared install tree | Run data is then shared across checkouts. That is harmless (unique run ids) and even useful for gap telemetry |
| 13 | Repo excerpts go to third parties (Jev, Langfuse) | User-approved; the redactor plus `deny_globs` keep secrets out; `data_policy` switches exist |
