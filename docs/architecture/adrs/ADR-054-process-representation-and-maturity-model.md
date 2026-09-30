---
title: "ADR-054: Process Representation and the Process-Maturity Model — Workflow vs Policy/Checklist vs LLM-Guided"
description: "Process knowledge is held as a LangGraph workflow when its sequence is known, as a Jev-evaluated policy/checklist when only its considerations are known, and as LLM-guided execution while it is still being discovered. Repeated LLM reasoning is promoted into policies and repeated policies into workflows, so LLMs bootstrap engineering knowledge instead of permanently holding it."
type: "adr"
status: "active"
created: "2026-09-30"
last_updated: "2026-09-30"
deciders:
  - BrainCandy
components:
  - decision_kernel
related_docs:
  - docs/architecture/adrs/ADR-052-capabilities-replace-agents-prompts-are-compiled.md
  - docs/architecture/adrs/ADR-053-intelligence-selection-deterministic-jev-llm-human.md
  - docs/architecture/components/decision-kernel.md
  - docs/analysis/2026-09-30-decision-kernel-design.md
  - docs/analysis/2026-09-30-decision-kernel-design-2-contracts-registry-config.md
  - docs/analysis/2026-09-30-decision-kernel-design-3-kernel-scheduler.md
  - docs/analysis/2026-09-30-decision-kernel-design-4-jev-and-capabilities.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-2-runtime-and-registry.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-3-contracts.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-6-gaps-build-verification.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-7-later-stages.md
related_code: []
---

# ADR-054: Process Representation and the Process-Maturity Model — Workflow vs Policy/Checklist vs LLM-Guided

## Status

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-09-30 |
| Deciders | BrainCandy |
| Author | `adr-author`, recorded from the 2026-09-30 design conversation held during `TICKET-20260930-KernelBootstrapV0` |
| Supersedes | None |

## Context

Today most of Leafcutter's engineering process lives in agent prompts.
[ADR-052](ADR-052-capabilities-replace-agents-prompts-are-compiled.md) replaces agents with
capabilities and compiles prompts from contracts.
[ADR-053](ADR-053-intelligence-selection-deterministic-jev-llm-human.md), the companion
"intelligence" ADR, decides whether deterministic code, Jev, an LLM or a human answers a given
question. Neither ADR says how the *process* knowledge itself is represented, or how that
representation changes as Leafcutter learns. This ADR is the companion "process" ADR.

Process knowledge comes in three states. Each state fails differently when it is stored in the
wrong form:

- **Established.** The steps and branches are known. Kept as prompt prose, nothing enforces the
  sequence, and a model can skip or reorder steps.
- **Partly known.** We know which concerns must be considered, but the relevant subset and the
  order differ per task. As a fixed sequence it runs irrelevant steps. As prompt prose a
  required concern can be silently missed.
- **Not understood yet.** The problem is new, several approaches need research, and we are still
  discovering which questions to ask. Forcing this into a workflow means guessing the process.
  Leaving it in an LLM transcript means the next task rediscovers it from scratch.

BrainCandy's observation in the design conversation was that an LLM makes sense whenever there is
no workflow yet, or only a vague one that still needs definition. The kernel design already
works this way. The kernel specification normalizes the earlier `NO_CAPABILITY`,
`NEEDS_OPTIONS` and `NEEDS_SYNTHESIS` names into routing outcomes and `waiting` results
([spec part 3](../../analysis/2026-09-30-leafcutter-kernel-spec-rev3-3-contracts.md), §7.6).
Generative work goes to explicit `host_handoff` capabilities rather than being hidden in the
scheduler ([design part 4](../../analysis/2026-09-30-decision-kernel-design-4-jev-and-capabilities.md)).
And the capability registry starts empty
([design part 1](../../analysis/2026-09-30-decision-kernel-design.md), deliberate deviation 1).

Without a recorded rule, each new capability picks its process representation ad hoc. Process
knowledge keeps piling up in prompts and transcripts, where it is not enforced and is repeated
on every task.

## Decision

### 1. Process knowledge MUST take one of three representations

| Representation | Use when | What it holds |
|---|---|---|
| Workflow | The sequence and branches are known. | A LangGraph workflow. It MUST NOT be kept as instructions. |
| Policy / checklist | The required considerations are known, but execution stays contextual. | WHAT must be considered, not the order of execution. Jev evaluates each item's applicability per task. |
| LLM-guided | The process itself is still being discovered. | Exploration, research, questions, possible approaches and decision criteria. The output MUST become reusable knowledge. It MUST NOT disappear when the task ends. |

The representation MUST follow from what is known about the process. A process MUST NOT be
written as a workflow before its sequence is known. Once a sequence is known, it moves out of
instructions into a workflow whenever practical (§3). Jev is what makes the policy and workflow
layers dynamic.

Examples from the design conversation:

- **Workflow — New Feature:** component discovery → retrieve related architecture → resolve
  blocking decisions → compile implementation contract → implementation → verification.
- **Policy — LangGraph policy:** Does state change? Node or subgraph? Parallel execution? Retry
  semantics? Persistence? Documentation impact? Test impact? For one task Jev answers, for
  example, state YES, node_vs_subgraph YES, parallel_execution NO.
- **LLM-guided:** "We don't yet know how a new LangGraph integration should be designed." →
  LLM → research → questions → possible approaches → decision criteria.

### 2. Process maturity is measured on five levels

| Level | Name | Meaning |
|---|---|---|
| 0 | Unknown | "We haven't figured out how to do this." |
| 1 | LLM-guided | "Use reasoning/research and discover the process." |
| 2 | Policy-guided | "We know the important questions." |
| 3 | Workflow-guided | "We know the process and its branches." |
| 4 | Deterministic | "We can compute or verify this exactly." |

Level 4 is not a target for every capability. Writing code will likely stay generative. The
process *around* writing code can still reach Level 3 or 4 — that is the distinction the
maturity model draws.

### 3. The promotion rule: knowledge moves upward

> **Convert repeated LLM reasoning into policies and repeated policies into workflows whenever
> practical.**

```text
UNKNOWN PROCESS → LLM (exploration/research) → discover recurring concerns
  → CHECKLIST / POLICY → observe recurring sequence → WORKFLOW → deterministic orchestration
```

Example. At first an LLM checks whether concurrent LangGraph execution introduces risks. Over
many tasks it keeps checking the same things: merge semantics, timeouts, partial failures and
state mutation. Those checks become `parallel_execution_policy`. Later we learn that the checks
always occur in a certain order, and the policy becomes `parallel_execution_review_graph`.

A promotion MUST go through the normal development process. The runtime can propose a new
capability or policy, but it MUST NOT activate or execute newly generated code by itself
([spec part 1](../../analysis/2026-09-30-leafcutter-kernel-spec-rev3.md), §2.3). New native
capabilities are implemented, tested, reviewed, versioned and registered like any other code
([spec part 6](../../analysis/2026-09-30-leafcutter-kernel-spec-rev3-6-gaps-build-verification.md), §14).
How promotion is detected or triggered is not decided here (see Open Questions).

### 4. The kernel resolves a request by capability and by process maturity

The kernel asks two questions:

1. What capability can solve this? (decision, research, retrieve, implement, verify)
2. How mature is our process for solving it?

It MUST resolve in this order and MUST use the most mature representation available:

```text
REQUEST
  Known workflow?                              YES → RUN WORKFLOW
  NO → Known policy/checklist?                 YES → APPLY POLICY (Jev) → dynamic execution
  NO → Known capability, but process unclear?  YES → LLM-guided capability
  NO → CAPABILITY GAP
```

How the V0 kernel design already expresses each rung:

| Rung | V0 kernel design |
|---|---|
| Known workflow | A registered `native` capability backed by a LangGraph graph (V0: `decision`, `research`), dispatched on routing outcome `selected`. |
| Known policy/checklist | No policy catalog exists in V0. Component-scoped executable policies are Stage 3 (spec part 7, §18.4), and spec §4.3 excludes a policy engine from the MVP. The nearest V0 analogue is the `decision` capability, which assesses supplied `Criterion` entries with Jev. |
| Known capability, process unclear | A `host_handoff` capability (`host.generate_options`, `host.synthesize`, `host.research`, `host.formulate_question`): bounded generative work under a typed `HostWorkRequest`. |
| Capability gap | §5 below. |

### 5. A capability gap follows the spec's `no_match` path

When no rung applies, the kernel MUST follow the specification's existing behaviour. It MUST NOT
invent a process. `NO_CAPABILITY` maps to the routing outcome `no_match`, a gap record, and
either an approved fallback or a blocked result (spec §7.6). "No suitable capability" is product
feedback, not permission to invent and execute a new graph (spec §14). The V0 design
([part 3](../../analysis/2026-09-30-decision-kernel-design-3-kernel-scheduler.md),
[part 4](../../analysis/2026-09-30-decision-kernel-design-4-jev-and-capabilities.md))
implements this as follows:

- The `route` node sends `no_match` items to `record_gaps`. That node records a `CapabilityGap`
  with gap type `unsupported`, plus a backlog-ready draft authored by `template`. A draft is
  never a registry entry.
- Fallback is allowed only when `host.fallback_on_no_match` is set, the request kind maps to an
  approved `host.*` capability that passes eligibility, budget remains, and the gap type is not
  `permission`. The item is then rebound and runs as LLM-guided work, and the gap's
  `fallback_outcome` is updated. Otherwise the item is blocked with `no_capability`.
- Only a genuine `no_match` is a missing capability. `unavailable` and `insufficient_context`
  MUST NOT be relabelled as one
  ([spec part 2](../../analysis/2026-09-30-leafcutter-kernel-spec-rev3-2-runtime-and-registry.md), §6.1; spec §14).

### 6. The learning loop

LLM-guided execution MUST feed a learning loop that asks: "Could anything learned here be
converted into a policy or workflow?" A "yes" becomes a reviewed proposal under §3. It MUST NOT
change a policy, workflow or registry entry by itself. This is the process-knowledge side of
spec Stage 4, "Controlled learning" (spec part 7, §19), which requires review before activation,
preserved versions and a rollback path.

### 7. LLMs bootstrap engineering knowledge; they are not where it lives

LLMs are a bootstrap mechanism for new engineering knowledge, not the place where engineering
knowledge permanently lives. Leafcutter gradually extracts process knowledge out of LLMs:
LLM behavior → observed recurring reasoning → explicit policy → explicit workflow.

"The kernel is routing uncertainty to the cheapest mechanism capable of reducing that
uncertainty." Process maturity (§4) selects the representation that runs. ADR-053 selects the
mechanism that answers each individual question.

### 8. Consistent with the empty capability registry

The kernel reads only `config/capability_registry.json`, which starts empty. Legacy agent and
skill registries are never read. A legacy asset becomes routable only through an `admission`
record of kind `legacy_admission`, with a `legacy_source` and a `decision_ref` that names an
ADR. There is no bulk import path
([design part 2](../../analysis/2026-09-30-decision-kernel-design-2-contracts-registry-config.md)).
This ADR relies on that rule. A legacy agent prompt is process knowledge stored as instructions.
It MUST NOT count as a known process just because it exists. A process becomes known to the
kernel only when it is registered: natively, or through a recorded admission decision.

## Consequences

### Positive

- Every piece of process knowledge has one home, chosen by an explicit rule. A reviewer can ask
  "is this in the right form?" and get a checkable answer.
- Known sequences are enforced by the graph, not by a model following instructions.
- New problems are not blocked waiting for a workflow. LLM-guided execution is a legitimate first
  step, not a failure.
- What an LLM discovers is kept and promoted, so later tasks do not rediscover it.
- The gap path stays honest: an unmet need is recorded and never covered by an improvised graph.

### Negative

- Level 2 has no runtime home in V0. Until Stage 3 lands, policy/checklist is a representation
  choice without a policy catalog, and the nearest mechanism is the `decision` capability's
  supplied criteria.
- "Whenever practical" leaves judgement to people. Knowledge can stay at Level 1 indefinitely if
  nobody promotes it, especially while the trigger is open.
- Policies evaluated by Jev inherit Jev's limits. The runtime can guarantee that a check ran, not
  that its answer was correct (spec §2.3).
- Promoted knowledge can go stale. A recorded decision is reusable knowledge, not permanent truth
  (spec §19.1). A workflow can end up encoding an outdated sequence after a framework upgrade.
- Each capability now carries two classifications: which mechanism answers its questions
  (ADR-053) and how mature its process is (this ADR).

### Operational

- New capabilities enter `config/capability_registry.json` with an `admission` record. Their
  process maturity is expressed by what is registered: a native graph, a `host_handoff`
  capability, or nothing.
- Gap observations in `.leafcutter/kernel/gaps/observations.jsonl` record reliance on LLM-guided
  work, including the `host_only` observation recorded for every host operation. They are
  available as evidence for promotion. They are not yet a trigger.
- Promotions follow the Stage 4 controls: review before activation, preserved previous versions,
  a rollback path, and evaluation on held-out cases (spec §19.2, §19.4).

## Alternatives

- **Encode every process as a workflow up front.** Rejected. A workflow needs a known sequence and
  known branches. For a new problem neither exists, so the graph would encode a guessed sequence
  that the first task that does not fit contradicts. New work would also wait until someone
  designs its process.
- **Keep all process knowledge in LLM prompts.** Rejected. This is the agent-prompt model that
  ADR-052 retires. Nothing enforces the sequence, a required concern can be silently skipped, and
  what one run learns is lost when its transcript ends, so every task rediscovers the process.
- **Checklists only.** Rejected. A checklist says what must be considered, not in what order.
  Where the sequence is known, leaving the order to per-task judgement re-decides a settled
  question on every run and nothing enforces it. Where the process is not understood yet, there
  is no checklist to write: the questions themselves are still being discovered.

## Open Questions

This ADR explicitly does not decide:

1. **How promotion is detected or triggered**: manual review, telemetry-driven detection, or
   both. Existing inputs are `CapabilityGap` observations (`occurrence_count`,
   `example_run_ids`, `host_only` fallback reliance) and the prioritization signals in spec §14
   (fallback frequency, total cost where known, latency, failure rate, usefulness). None of these
   is a decided trigger.
2. **Where policies are stored.** Spec part 7, §18.4 shows illustrative Stage 3 policy data
   (`LG-PARALLEL-001`). No storage location or format is decided.

Also outside this ADR: whether workflow definitions are authored as Python/LangGraph code,
declarative JSON/YAML, or a hybrid. That remains the spec's first dogfooding research question
(spec §15.5).

## References

- Source: the 2026-09-30 design conversation between BrainCandy and an assistant (user turn 2;
  assistant turn 2 "ADR 2", "Connection to the kernel", and the closing "constitution" section).
- Originating work: `tickets/00_inbox/TICKET-20260930-KernelBootstrapV0.md`
- [ADR-052: Capabilities replace agents; prompts are compiled](ADR-052-capabilities-replace-agents-prompts-are-compiled.md)
- [ADR-053: Intelligence selection — deterministic, Jev, LLM or human](ADR-053-intelligence-selection-deterministic-jev-llm-human.md)
- [Decision Kernel component overview](../components/decision-kernel.md)
- Kernel design: [part 1](../../analysis/2026-09-30-decision-kernel-design.md) (deviation 1),
  [part 2](../../analysis/2026-09-30-decision-kernel-design-2-contracts-registry-config.md) (registry, admission),
  [part 3](../../analysis/2026-09-30-decision-kernel-design-3-kernel-scheduler.md) (`route` → `record_gaps`),
  [part 4](../../analysis/2026-09-30-decision-kernel-design-4-jev-and-capabilities.md) (host operations, gaps)
- Kernel spec Rev 3: [part 1](../../analysis/2026-09-30-leafcutter-kernel-spec-rev3.md) (§2.3, §4.3),
  [part 2](../../analysis/2026-09-30-leafcutter-kernel-spec-rev3-2-runtime-and-registry.md) (§6.1),
  [part 3](../../analysis/2026-09-30-leafcutter-kernel-spec-rev3-3-contracts.md) (§7.6, §7.9),
  [part 6](../../analysis/2026-09-30-leafcutter-kernel-spec-rev3-6-gaps-build-verification.md) (§14, §15.5),
  [part 7](../../analysis/2026-09-30-leafcutter-kernel-spec-rev3-7-later-stages.md) (§18.4, §19)
