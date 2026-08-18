---
title: "Fast-Lane Build Loop — Sequence Diagram"
description: "L3 sequence diagram of the fast-lane build loop: ordered message flow from AC batch selection through test-writer, red-baseline gate, python-coder, green-and-coverage gate, and commit staging — including halt paths on each gate failure."
type: architecture
diagram_type: sequence
flight_level: L3-Component
status: active
created: 2026-07-21
last_updated: 2026-08-17
parent: docs/architecture/components/build-orchestration.md
source_ticket: null
components:
  - build_orchestration
related_docs:
  - docs/architecture/diagrams/c2-fast-lane-build-path-components.md
  - docs/architecture/components/build-orchestration.md
  - docs/how-to/fast-lane-build.md
related_code:
  - templates/workflows-js/fast-lane-build.js
  - scripts/build_orchestration/fast_lane.py
tags:
  - fast-lane
  - build-loop
  - two-dispatch
  - ac-batch
  - deterministic-gate
---

# Fast-Lane Build Loop — Sequence Diagram

This diagram documents the ordered message flow of the fast-lane build loop as
implemented in `templates/workflows-js/fast-lane-build.js` and its deterministic
Python gate functions in `scripts/build_orchestration/fast_lane.py`. The loop
dispatches exactly two LLM agents — one `test-writer` and one `python-coder` —
regardless of the batch size `N`, with three deterministic Python gates enforcing
correctness at each transition (BO-2400a-2, BO-2400a-3, BO-2400a-4).

> **Exactly 2 LLM dispatches.** The `test-writer` and `python-coder` each receive
> the full AC batch in a single flat dispatch — the invocation count is fixed at 2,
> independent of `N` (BO-2400a-1). No supervisor chain, no LLM planner, no per-ticket
> worktrees (BO-2400a-5). The gates are deterministic Python scripts, not LLM judgments.

---

```mermaid
sequenceDiagram
    autonumber
    actor Operator
    participant Workflow as fast-lane-build.js
    participant SelectBatch as select_batch<br/>(Python gate)
    participant TestWriter as test-writer<br/>(LLM agent)
    participant RedBaseline as verify_red_baseline<br/>(Python gate)
    participant Coder as python-coder<br/>(LLM agent)
    participant GreenCoverage as verify_green_and_coverage<br/>(Python gate)

    Operator->>Workflow: invoke(worktree_path, batch_size, ac_store_root)

    Note over Workflow,SelectBatch: Gate 1 — Batch Selection (deterministic Python, BO-2400a-2)
    Workflow->>SelectBatch: run select_batch gate
    Note right of SelectBatch: Reads AC YAML store · filters approved+unimplemented ACs<br/>Orders output by priority, then complexity, then id

    SelectBatch-->>Workflow: [ac_id1, ac_id2, ...] ordered batch list

    Note over Workflow,TestWriter: LLM Dispatch 1 of 2 — test-writer (one flat dispatch, whole batch)
    Workflow->>TestWriter: dispatch(batch_ac_list)
    TestWriter->>TestWriter: Read AC YAMLs · write failing stubs · run suite to confirm RED

    alt test-writer status != "ok"
        TestWriter-->>Workflow: {status: "blocked"|"failed", message: "..."}
        Workflow-->>Operator: {status: "blocked", failing_phase: "test-writer", classification: "halt"}
    else test-writer status == "ok"
        TestWriter-->>Workflow: {status: "ok", tests_written: ["path/test_...", ...]}

        Note over Workflow,RedBaseline: Gate 2 — Red Baseline (deterministic Python, BO-2400a-3)
        Workflow->>RedBaseline: run verify_red_baseline gate
        Note right of RedBaseline: Scans test_root for # covers:&lt;id&gt; tags matching batch ACs<br/>Partitions them into newly-added vs pre-existing via git, at test-function<br/>granularity (merge-base with origin/main, or an explicit --base-ref)<br/>Runs pytest on linked test files; classifies FAILED/XFAIL as red,<br/>PASSED/XPASS as green, SKIPPED/ERROR as inconclusive<br/>Passes iff at least one NEWLY-ADDED test is red; pre-existing tests<br/>are reported but never affect the verdict

        alt gate_passed == False (no newly-added covering test is red — coder must NOT run)
            RedBaseline-->>Workflow: {gate_passed: false, reason: no_new_covering_tests / all_new_tests_green_at_baseline / no_red_outcome_among_new_tests / baseline_partition_unavailable, red: [], green_at_baseline: [...], inconclusive: [...], preexisting: [...]}
            Workflow-->>Operator: {status: "blocked", failing_phase: "verify_red_baseline", classification: "halt"}
        else gate_passed == True
            RedBaseline-->>Workflow: {gate_passed: true, reason: null, red: [...], green_at_baseline: [...], inconclusive: [...], preexisting: [...]}

            Note over Workflow,Coder: LLM Dispatch 2 of 2 — python-coder (one flat dispatch, whole batch)
            Workflow->>Coder: dispatch(implement batch ACs to make stubs GREEN)
            Coder->>Coder: Implement production code · run suite to confirm GREEN

            alt python-coder status != "ok"
                Coder-->>Workflow: {status: "blocked"|"failed", message: "..."}
                Workflow-->>Operator: {status: "blocked", failing_phase: "python-coder", classification: "halt"}
            else python-coder status == "ok"
                Coder-->>Workflow: {status: "ok", files_modified: ["path/src_...", ...]}

                Note over Workflow,GreenCoverage: Gate 3 — Green + Coverage (deterministic Python, BO-2400a-4)
                Workflow->>GreenCoverage: run verify_green_and_coverage gate
                Note right of GreenCoverage: Calls verify_done_eligible per AC (reuses done_proof helpers)<br/>(a) All linked tests PASS (zero pytest exit)<br/>(b) Every AC id has ≥1 covering test

                alt green == False or coverage_ok == False (commit NOT staged)
                    GreenCoverage-->>Workflow: {green: false} or {coverage_ok: false}
                    Workflow-->>Operator: {status: "blocked", failing_phase: "verify_green_and_coverage", classification: "halt"}
                else green == True and coverage_ok == True
                    GreenCoverage-->>Workflow: {green: true, coverage_ok: true}
                    Workflow->>Workflow: Stage commit (batch output ready)
                    Workflow-->>Operator: {status: "ok", gates_passed: ["select_batch", "verify_red_baseline", "verify_green_and_coverage"]}
                end
            end
        end
    end
```

Parent: [Build Orchestration — Epic & Ticket Dispatch Sequencing](../components/build-orchestration.md)

See also: [Interactive Pause/Resume — Pause, Ask, Answer, Resume Sequence](c3-002-interactive-pause-resume-sequence.md) — the companion sequence diagram for the pause/resume substrate in the same build orchestration component.

---

## Gate Summary

| Gate | Runs | Pass Condition | Halt Condition |
|------|------|----------------|----------------|
| `select_batch` | Before test-writer | Returns a non-empty ordered AC id list | Argument validation fails (`worktree_path` absent) |
| `verify_red_baseline` | After test-writer, before coder | At least one **newly-added** covering test is red — `FAILED` or `XFAIL` (`gate_passed == True`). Newly-added tests that are green are reported as `green_at_baseline` (non-fatal); pre-existing tests are reported but never affect the verdict | No newly-added covering test is red — coder is NOT dispatched. The halt carries exactly one named `reason`: `no_new_covering_tests`, `all_new_tests_green_at_baseline`, `no_red_outcome_among_new_tests`, or `baseline_partition_unavailable` (fail-closed when the git partition is unresolvable) |
| `verify_green_and_coverage` | After coder, before commit staging | All tagged tests PASS **and** every AC id has ≥1 covering test | Either condition fails — commit is NOT staged |

## Actors

| Actor | Type | Description |
|-------|------|-------------|
| Operator | Human / orchestrator | Invokes the workflow with `worktree_path`, `batch_size`, and `ac_store_root` |
| `fast-lane-build.js` | Workflow (E2 top-level body) | Orchestrates the two-dispatch sequence; holds no LLM state between gates |
| `select_batch` | Python gate (BO-2400a-2) | Deterministic: reads AC YAML store, filters approved+unimplemented, orders batch — no LLM |
| `test-writer` | LLM agent — dispatch 1 of 2 | Writes failing test stubs for the whole batch in one flat dispatch |
| `verify_red_baseline` | Python gate (BO-2400a-3) | Deterministic: partitions covering tests into newly-added vs pre-existing via git, then confirms at least one newly-added test is red before coder is dispatched. Requiring *every* covering test to be red made partially-implemented ACs unbuildable, so the rule was amended to one-red-is-enough (BO-2400a-3-v) |
| `python-coder` | LLM agent — dispatch 2 of 2 | Implements production code for the whole batch in one flat dispatch |
| `verify_green_and_coverage` | Python gate (BO-2400a-4) | Deterministic: confirms all batch tests pass and every AC id has ≥1 covering test |

## Key Property

The fast lane uses **exactly 2 LLM dispatches** regardless of batch size `N`. The
three gates (`select_batch`, `verify_red_baseline`, `verify_green_and_coverage`) are
deterministic Python scripts invoked via Bash — they do not consume LLM tokens and
cannot be "persuaded". This is the defining constraint of the fast lane over the
standard build path (`build-feature.js`), which dispatches one supervisor and one coder
per ticket.

## Cross-References

- [Build Orchestration — Epic & Ticket Dispatch Sequencing](../components/build-orchestration.md) — the component that owns `fast-lane-build.js` and `scripts/build_orchestration/fast_lane.py`.
- [Interactive Pause/Resume — Pause, Ask, Answer, Resume Sequence](c3-002-interactive-pause-resume-sequence.md) — companion sequence diagram for the pause/resume substrate in the same component.
- [Interactive Pause/Resume — Run Lifecycle State Diagram](c3-001-interactive-pause-resume-run-lifecycle.md) — run lifecycle states for the pause/resume mechanism.
