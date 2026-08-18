---
title: "Fast-Lane Build Path — Component Diagram"
description: "Shows the fast-lane two-agent batch build path, its three deterministic Python gates, and its collaborating components (AC store, telemetry), contrasted with the heavy supervisor-based pipeline to make the absence of a per-ticket supervisor and LLM planner explicit."
type: architecture
diagram_type: component
flight_level: L3-Component
status: active
created: 2026-07-21
last_updated: 2026-08-17
source_ticket: null
parent: agent_delivery_workflows.md
components:
  - build_orchestration
related_docs:
  - docs/architecture/diagrams/c3-fast-lane-build-loop-sequence.md
  - docs/architecture/components/build-orchestration.md
  - docs/how-to/fast-lane-build.md
  - docs/how-to/choose-build-path.md
related_code:
  - templates/workflows-js/fast-lane-build.js
  - scripts/build_orchestration/fast_lane.py
  - scripts/agent-health/agent_telemetry.py
tags:
  - fast-lane
  - build-orchestration
  - deterministic-gates
  - ac-store
---

# Fast-Lane Build Path — Component Diagram

The fast-lane build path is a lean, batch-oriented alternative to the heavy pipeline.
It dispatches **exactly two LLM agents** — test-writer and python-coder — regardless of
batch size N, and enforces correctness via **three deterministic Python gate scripts** with
no LLM calls in the critical path. There is **no per-ticket supervisor, no LLM planner,
and no per-ticket worktree isolation**.

---

## Diagram Legend

| Color | Role | Description |
|---|---|---|
| Grey | Data store | Persistent YAML files (AC store) |
| Green | Deterministic gate | Python script in the critical path; no LLM calls |
| Blue | LLM agent | One flat dispatch; produces test stubs or production code |
| Purple | Workflow runner | JS workflow entry point that sequences the two-agent loop |
| Red | Telemetry | Append-only event sink per agent invocation |
| Yellow | Heavy pipeline | Existing supervisor-based path shown for contrast |

---

## Component Diagram

```mermaid
flowchart TD
    classDef store fill:#f3f4f6,stroke:#4b5563,stroke-width:2px;
    classDef gate fill:#d1fae5,stroke:#059669,stroke-width:2px;
    classDef llm fill:#dbeafe,stroke:#2563eb,stroke-width:2px;
    classDef runner fill:#ede9fe,stroke:#7c3aed,stroke-width:2px;
    classDef telemetry fill:#fee2e2,stroke:#dc2626,stroke-width:2px;
    classDef heavy fill:#fef3c7,stroke:#d97706,stroke-width:2px;

    %% ── Shared input ─────────────────────────────────────────────────────────
    ACS[("AC YAML Store\ndocs/acceptance-criteria/\nreadiness: approved\nwork_status: todo")]:::store

    %% ─────────────────────────────────────────────────────────────────────────
    %% FAST LANE — 2 LLM dispatches, 3 Python gates, no supervisor, no planner
    %% ─────────────────────────────────────────────────────────────────────────
    subgraph FastLane ["Fast Lane — 2 LLM dispatches — 3 deterministic Python gates — no supervisor — no planner — single worktree"]
        direction TB

        WR["fast-lane-build.js\n──────────────────────────────────\nWorkflow Runner\nOrchestrates the lean two-agent loop\nNo planner. No supervisor.\nSets worktree_path, batch_size, ac_store_root"]:::runner

        SB["select_batch gate\n──────────────────────────────────\nfast_lane.py :: select_batch()\nDeterministic Python — no LLM\nReads AC store, filters to approved+todo,\nresolves depends_on, returns ordered batch list\n(priority-asc, complexity-asc, id-asc)"]:::gate

        TW["test-writer agent\n──────────────────────────────────\nLLM Dispatch 1 of 2\nRuns select_batch as its first Bash call\nWrites minimal failing stubs for all batch ACs\nNo production code written\nReturns: status, tests_written"]:::llm

        RB["verify_red_baseline gate\n──────────────────────────────────\nfast_lane.py :: verify_red_baseline()\nDeterministic Python — no LLM\nScans test root for covers: tags\nPartitions newly-added vs pre-existing via git\n(merge-base with origin/main, or --base-ref)\nat test-function granularity\nAt least one NEWLY-ADDED test must be RED\n(FAILED or XFAIL) before coder runs\nReturns: gate_passed, reason, red,\ngreen_at_baseline, inconclusive, preexisting"]:::gate

        PC["python-coder agent\n──────────────────────────────────\nLLM Dispatch 2 of 2 — final dispatch\nImplements minimum production code\nto make every failing stub GREEN\nReturns: status, files_modified"]:::llm

        GC["verify_green_and_coverage gate\n──────────────────────────────────\nfast_lane.py :: verify_green_and_coverage()\nDeterministic Python — no LLM\nAll tests GREEN + every AC id has\nat least one covers: tag\nDelegates to done_proof.verify_done_eligible()\nReturns: green, coverage_ok, uncovered_ac_ids, failing_tests"]:::gate

        CS["Commit Staging\n──────────────────────────────────\nBatch output staged for commit\ngates_passed list in final payload:\nselect_batch, verify_red_baseline,\nverify_green_and_coverage"]:::runner
    end

    TEL["agent_telemetry.py sink\n──────────────────────────\nscripts/agent-health/agent_telemetry.py\ndebugging/logs/agent_telemetry.jsonl\nOne record per agent invocation"]:::telemetry

    %% ─────────────────────────────────────────────────────────────────────────
    %% HEAVY PIPELINE — shown simplified for contrast
    %% N supervisors, LLM planner, per-ticket worktrees, LLM review + validator
    %% ─────────────────────────────────────────────────────────────────────────
    subgraph HeavyPipeline ["Heavy Pipeline (contrast) — 1 supervisor per ticket — LLM planner — per-ticket worktrees — LLM review and validator gates"]
        direction LR

        TS["ticket-supervisor\n────────────────────────\n1 supervisor per ticket\nN dispatches for N tickets\nPhase-by-phase orchestration"]:::heavy

        LP["LLM Planner\n────────────────────────\nReads ticket frontmatter\nReturns ordered phase list\nto ticket-supervisor"]:::heavy

        PTC["Per-ticket worktrees\n────────────────────────\nIsolated git checkout\nper ticket"]:::heavy

        PRR["pr-reviewer agent\n────────────────────────\nLLM code review"]:::heavy

        ACV["ac-validator agent\n────────────────────────\nLLM AC coverage gate\nat priority 11"]:::heavy

        ACF["ac-fulfillment-gate agent\n────────────────────────\nLLM fulfillment check\nat priority 11.7"]:::heavy

        CA["commit agent\n────────────────────────\nConfirmation-gated\ngit commit"]:::heavy

        PRA["pull-request agent\n────────────────────────\nPR creation\nper ticket"]:::heavy

        TS --> LP
        LP -->|"ordered phase list"| PTC
        PTC --> PRR
        PRR --> ACV
        ACV --> ACF
        ACF --> CA
        CA --> PRA
    end

    %% ── Fast lane data flows ──────────────────────────────────────────────────
    ACS -->|"YAML files\n(directory walk)"| SB
    WR --> SB
    SB -->|"ordered AC id list\n(up to batch_size N)"| TW
    TW -->|"stubs written\nstatus: ok"| RB
    RB -->|"gate_passed: true\ncoder dispatched"| PC
    PC -->|"tests green\nstatus: ok"| GC
    GC -->|"green: true\ncoverage_ok: true"| CS
    TW -.->|"telemetry event"| TEL
    PC -.->|"telemetry event"| TEL

    %% ── Heavy pipeline also reads AC store (via ticket ac_traceability) ───────
    ACS -.->|"via ticket ac_traceability"| TS
```

Parent: [Agent Code Delivery Workflows](../agent_delivery_workflows.md)

---

## Fast-Lane vs Heavy Pipeline: Key Distinctions

| Axis | Fast Lane | Heavy Pipeline |
|---|---|---|
| LLM dispatches | **2 total** — test-writer + python-coder | N per ticket: supervisor, planner, reviewer, validator, fulfillment, commit, PR agent |
| Correctness enforcement | 3 deterministic Python gate scripts (no LLM in critical path) | LLM review gates: pr-reviewer, ac-validator, ac-fulfillment-gate |
| Supervisor | **None** — no per-ticket supervisor | 1 `ticket-supervisor` per ticket |
| Planner | **None** — code-defined phase order in fast-lane-build.js | LLM planner reads ticket and returns ordered phase list |
| Worktree strategy | **Single** shared worktree for the whole batch | Isolated per-ticket worktree |
| Batch size | N ACs in one pair of dispatches | 1 ticket per supervisor (may span multiple ACs) |
| Telemetry | agent_telemetry.py — 1 record per dispatch | agent_telemetry.py — 1 record per dispatch |

---

## Gate Function Contracts

| Gate | Script function | Guard condition |
|---|---|---|
| **select_batch** | `fast_lane.py::select_batch(ac_root, limit)` | Deterministic. Filters: `level L2/L3`, `status active`, `readiness approved`, `work_status todo`, `depends_on` resolved. Returns `[]` on empty store. |
| **verify_red_baseline** | `fast_lane.py::verify_red_baseline(ac_ids, test_root, base_ref=None)` | Partitions the batch's covering tests into newly-added vs pre-existing using git at test-function granularity (merge-base with `origin/main`, or an explicit `base_ref`). Passes iff at least one **newly-added** covering test is red (`FAILED` or `XFAIL`). A newly-added test that is green is reported as `green_at_baseline` — surfaced, non-fatal. Pre-existing tests are reported but never affect the verdict. Blocks coder dispatch with exactly one named `reason`: `no_new_covering_tests`, `all_new_tests_green_at_baseline`, `no_red_outcome_among_new_tests`, or `baseline_partition_unavailable` (fail-closed when git metadata is unresolvable). |
| **verify_green_and_coverage** | `fast_lane.py::verify_green_and_coverage(ac_ids, test_root, ac_root)` | Blocks commit staging if any test FAILS or any AC id has zero `# covers: <id>` tags. Delegates per-AC to `done_proof.verify_done_eligible()`. |

---

## Component Descriptions

| Component | Type | Role |
|---|---|---|
| **AC YAML Store** (`docs/acceptance-criteria/`) | Data store | Source of truth for approved+unimplemented ACs. `select_batch` reads from it; `verify_green_and_coverage` reads it for active-status resolution. |
| **fast-lane-build.js** | Workflow Runner | Orchestrates the two-agent loop. Halts immediately on `status: blocked` from either agent. |
| **select_batch gate** | Deterministic Python | Mirrors `scan_ac_store` filter/sort helpers so readiness semantics track the scanner exactly. |
| **test-writer agent** | LLM dispatch 1 | Runs `select_batch` as its first Bash call, then writes minimal failing test stubs. Returns `{status, tests_written}`. |
| **verify_red_baseline gate** | Deterministic Python | Scans test root for `# covers: <id>` tags, partitions the linked tests into newly-added vs pre-existing via git, runs them via pytest, and verifies at least one newly-added test is red before coder is dispatched. Outcome classification is three-way: `FAILED`/`XFAIL` = red, `PASSED`/`XPASS` = green, `SKIPPED`/`ERROR`/unknown = inconclusive (XFAIL counts as red because every AC in a fast-lane batch is not-yet-done, so the AC enforcement plugin rewrites its assertion failures to xfail). Requiring *all* covering tests to be red made every partially-implemented AC unbuildable — observed live on two unrelated ACs. |
| **python-coder agent** | LLM dispatch 2 | Reads the failing stubs, implements minimum production code. Returns `{status, files_modified}`. |
| **verify_green_and_coverage gate** | Deterministic Python | Both `green: true` AND `coverage_ok: true` required. Commit staging is blocked until both pass. |
| **Commit Staging** | Workflow output | Final state of fast-lane-build.js. The actual `git commit` is external to the fast-lane workflow. |
| **agent_telemetry.py sink** | Telemetry | Receives one append-only JSON event per agent invocation. Written to `debugging/logs/agent_telemetry.jsonl`. |

---

## Cross-Links

- [Agent Code Delivery Workflows](../agent_delivery_workflows.md) — parent; covers overall supervisor dispatch topology
- [AC-Driven Pipeline — Component Diagram](c2-001-ac-driven-pipeline.md) — sibling; shows how ACs reach `readiness: approved` before fast-lane picks them up
- [Build Orchestration — Component Reference](../components/build-orchestration.md) — component reference for the `build_orchestration` graph node
- [Architecture README](../README.md)

<!--
====================================================================
DECISION HISTORY
====================================================================
- 2026-07-21 [architecture-diagram-author]: Created for AC BO-2400a-8. Documents the
  fast-lane two-agent batch build path and its three deterministic Python gates alongside
  a simplified heavy-pipeline contrast view. Makes explicit that the fast lane uses no
  per-ticket supervisor and no LLM planner — exactly 2 LLM dispatches, 3 Python gates,
  single worktree. Scaffold script (scripts/scaffold/new_arch_doc.py) is not yet deployed;
  file hand-authored to match c2-001 model per task spec.
====================================================================
-->
