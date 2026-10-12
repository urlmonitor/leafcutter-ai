---
title: "Decision kernel Stage 1 MVP: exit-gate tests, live suite, labelled eval set, delivery docs and kernel CI lint (#KernelBootstrapV0/P10)"
date: "2026-10-01"
time: "18:30"
type: feature
components: 
  - decision_kernel
summary: "The decision kernel's Stage 1 exit gate (spec Rev 3 section 16) is proven by offline scenario tests through the real service and by a live suite against the real Jev and Langfuse, with run and Langfuse-MCP how-tos, a demo and run report, and CI now linting kernel/."
description: "P10 closes the Stage 1 build of the decision kernel. Offline: tests/kernel/integration gains scenario tests that drive the production registry and bindings through KernelService with a scripted Jev (existing basis, missing basis then research then resolved, unknown options, human preference pause and resume, a different decision domain, an unsupported request recording a deduplicated gap, provider failure, conflicting evidence, unknown billing and malicious source instructions) plus an offline shape check of the labelled evaluation set. Writing the unknown-billing test found a real defect: the run envelope reported cost_usd_known as 0.0 when every call's cost was unknown; it is now null (kernel/service_envelope.py). Live: tests/kernel/live adds a Langfuse round-trip, an end-to-end suite that runs python -m kernel against this repository (an ADR-settled goal completes with no host work; a goal that needs host work pauses and resumes on clearly labelled synthetic answers) and a labelled eval runner of eight cases under 60 Jev calls, all guarded by LEAFCUTTER_KERNEL_LIVE=1; traces are read back through the Langfuse observations API. Docs: how to run the kernel, how to inspect kernel traces with the Langfuse data MCP server (read-only, user-configured), the V0 demo and run report with the 19-row exit-gate checklist and the deferred-work list, the component doc and design part 6; docs/components.json marks decision_kernel active with its CLI, RunService and skill interfaces. CI: the ruff job now also lints kernel/, and kernel/ is held to E722, BLE001 and TRY."
---

## Entry

### Added

- `tests/kernel/integration/{scenario_support,test_demo_scenarios,test_decision_loop,test_exit_gate_failures,test_eval_set}.py`
  — exit-gate scenarios through `KernelService`.
- `tests/kernel/live/{live_support,test_live_langfuse,test_live_end_to_end,test_live_eval,eval_runner}.py` and
  `tests/kernel/fixtures/eval/eval_set.json` — the live suite and the labelled evaluation set
  (`LEAFCUTTER_KERNEL_LIVE=1`).
- `docs/how-to/run-the-decision-kernel.md`, `docs/how-to/inspect-kernel-traces-with-langfuse-mcp.md`
  and `docs/analysis/2026-10-01-decision-kernel-v0-demo-report.md`.

### Changed

- `kernel/service_envelope.py` — `cost_usd_known` is `null` when every call's cost is unknown.
- `kernel/service.py`, `kernel/service_errors.py` — `RunRecordContended` replaces a long-message
  `RuntimeError` (ruff TRY003).
- `.github/workflows/ci.yml`, `ruff.toml` — the ruff job lints `kernel/` and runs
  `ruff check kernel --select E722,BLE001,TRY`.
- `docs/components.json` — `decision_kernel` is `active` with CLI, RunService and skill interfaces.
- `docs/architecture/components/decision-kernel.md`, design part 6 — status and as-built test names.
