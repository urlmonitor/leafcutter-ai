---
title: "ADR-052: Capabilities Replace Agents — Prompts Are Compiled Outputs, Not the Source of Truth"
description: "Leafcutter's main abstraction is the contract-driven capability, not the agent. Process, evidence requirements and verification live in workflows, configuration and checks, and model instructions are small, versioned outputs of a deterministic invocation compiler, so prompts stop being the source of truth for the engineering process."
type: "adr"
status: "active"
created: "2026-09-30"
last_updated: "2026-09-30"
deciders:
  - BrainCandy
components:
  - decision_kernel
related_docs:
  - docs/architecture/adrs/ADR-053-intelligence-selection-deterministic-jev-llm-human.md
  - docs/architecture/adrs/ADR-054-process-representation-and-maturity-model.md
  - docs/architecture/components/decision-kernel.md
  - docs/analysis/2026-09-30-decision-kernel-design.md
  - docs/analysis/2026-09-30-decision-kernel-design-2-contracts-registry-config.md
  - docs/analysis/2026-09-30-decision-kernel-design-4-jev-and-capabilities.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-4-scheduler-jev-capabilities.md
related_code:
  - kernel/
---

# ADR-052: Capabilities Replace Agents — Prompts Are Compiled Outputs, Not the Source of Truth

## Status

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-09-30 |
| Deciders | BrainCandy |
| Author | `adr-author`, recorded from the 2026-09-30 design conversation that BrainCandy endorsed |
| Supersedes | None |

## Context

Each Leafcutter agent carries, inside its prompt, the workflow we want it to follow, and that
workflow makes up most of the prompt. A hypothetical implementation-agent prompt reads:
"Understand the request. Read the relevant architecture. Check for existing implementations.
Decide whether a new subgraph is needed. Ask questions when requirements are unclear. Implement
the change. Write tests. Check documentation. Report unresolved issues." Little of that is
generation. It is process, evidence gathering, decisions and verification, written as prose
that nothing enforces. The runtime cannot tell whether "run tests" actually happened.

The Decision Kernel
([TICKET-20260930-KernelBootstrapV0](../../../tickets/00_inbox/TICKET-20260930-KernelBootstrapV0.md),
design [part 1](../../analysis/2026-09-30-decision-kernel-design.md)) turns that process into
LangGraph workflows with Jev decisions inside them. The "agent" becomes a decision engine made
of pre-checks, some kind of work, and post-checks. So does Leafcutter still need agents, and
does it still need prompts? This needs an answer now for three reasons:

1. **The kernel's capability registry starts empty** by user decision (design part 1,
   deviation 1). A legacy agent or skill enters `config/capability_registry.json` only through
   a `legacy_admission` record whose `decision_ref` names an ADR, with no bulk import
   ([design part 2](../../analysis/2026-09-30-decision-kernel-design-2-contracts-registry-config.md)).
   What a capability *is* must be settled before entries are written.
2. **Porting drifts toward the old shape.** A capability copied from an agent's persona and
   prompt keeps the process in prose, unenforced and untestable.
3. **The opposite drift is just as likely.** "No prompts at all" fails too: a JSON contract
   passed to a model is still part of its prompt, and Jev still needs written instructions.

LangGraph suits this: nodes perform work, edges choose the next step, and either can be ordinary
code rather than an LLM call. It distinguishes workflows (predefined paths) from agents (which
choose their own process and tools); Leafcutter combines a defined runtime with dynamic
capability selection. What matters is where control lives, not the unit's name.

## Decision

The workflow defines the process. The contract defines the task. The model performs the
work. The runtime checks the result.

### 1. The capability, not the agent, is Leafcutter's main abstraction

Leafcutter MUST describe units of work as contract-driven capabilities:

```text
Capability = input contract + applicable policies + evidence preparation + decisions
           + execution strategy + verification + typed result
```

A capability contains no generative model, one model call, or a bounded worker loop. Callers
MUST NOT depend on which. They depend only on the input contract and the typed result, which
in the kernel are a descriptor's `accepts_schemas` and `produces_schemas` (design part 2).
"Agent" is not a kernel abstraction. A legacy agent or skill becomes a capability only through
an explicit, recorded admission decision. This ADR admits none, and it does not migrate,
rewrite or retire any existing agent template.

### 2. Process content moves out of prompts

Each kind of content now found in an agent prompt MUST move to the place this table names:

| Content currently inside the prompt | Where it moves |
|---|---|
| "First inspect architecture, then implement" | Workflow dependencies and transitions |
| "Find the relevant files and ADRs" | Retrieval capabilities and evidence requirements |
| "Consider whether this needs a subgraph" | A decision policy, with criteria and evidence |
| "Ask questions when information is missing" | A typed unresolved result and a question-formulation capability |
| "Implement the requested behavior" | A focused model invocation |
| "Run tests before declaring completion" | An enforced verification stage |
| "Do not modify unrelated components" | Execution scope, permissions, and diff checks |
| "Explain what happened" | A report assembled from recorded results |

Only the genuinely interpretive or generative parts remain model instructions.

### 3. Prompts are compiled outputs of a deterministic invocation compiler

Model instructions MUST be built by an invocation compiler from explicit inputs:

```text
Capability definition + applicable component policies + original task and clarified
requirements + retrieved evidence + approved decisions + output contract
    -> deterministic invocation compiler -> focused model instructions + task context
```

The compiler MUST be ordinary, deterministic code. An LLM MUST NOT improvise a new prompt on
each invocation. Leafcutter MUST NOT keep independently maintained giant agent prompts for its
capabilities; only small, versioned instruction templates compiled from explicit contracts
remain. A coding worker receives the operation, task, approved decisions, relevant evidence,
constraints and expected output (e.g. "A patch proposal and any unresolved implementation
questions"). It is not asked to pick a workflow, discover the architecture or remember the
development methodology; that work is already done.

The goal is not to get rid of prompts. It is to stop using prompts as the source of truth for
our engineering process. Prompts become a model-facing interface that Leafcutter generates;
the process itself becomes software.

### 4. Pre-check, execute, post-check is the reusable lifecycle

The reusable shape of a capability is this generic lifecycle. "Execute" covers code, research
synthesis, question formulation, or a deterministic tool call.

```text
PREPARE             Resolve policies and acquire evidence
PRE-CHECK           Can this operation proceed?
COMPILE INVOCATION  Build the operation-specific input (§3)
EXECUTE             Code / research / synthesis / tools
POST-CHECK          Evaluate the actual result
ACCEPT / REPAIR / REQUEST INFORMATION / ESCALATE
```

A capability's checks MUST run as stages before and after execution, not only as instructions
inside the execution prompt. Several capabilities can share one lifecycle graph, differing only
in policies, executors and output contracts; a former agent needs no hand-built graph of its own.

### 5. Capability definitions are configuration over registered implementations

A capability can be described largely by configuration. The example below is **ILLUSTRATIVE
ONLY**. It is not a LangGraph, Jev or Leafcutter API, and it is not the entry shape of
`config/capability_registry.json`, which design part 2 defines and this ADR does not amend.

```json
{
  "id": "implement_change",
  "version": "1",
  "inputs": ["original_task", "implementation_contract", "evidence_bundle"],
  "prechecks": [
    {"check": "blocking_decisions_resolved", "executor": "deterministic", "on_failure": "request_decision"},
    {"check": "implementation_context_relevant", "executor": "jev", "on_uncertain": "request_evidence"}
  ],
  "execution": {"executor": "coding_worker", "instruction_template": "implement_contract_v1", "output_schema": "PatchProposal"},
  "postchecks": [
    {"check": "changes_within_authorized_scope", "executor": "deterministic"},
    {"check": "required_tests_pass", "executor": "test_runner"},
    {"check": "documentation_impact", "executor": "jev", "on_uncertain": "request_review"}
  ],
  "on_failure": "repair_or_escalate"
}
```

Every identifier in a capability definition (check, executor, instruction template, output
schema) MUST resolve to a registered, tested implementation; configuration MUST NOT execute or
enforce anything by itself. The kernel already does this: a registry `binding` keys the trusted
`BindingTable`, never an import path (design part 2), and dispatch uses work-item data rather
than generated executable graph definitions
([spec part 4, §8](../../analysis/2026-09-30-leafcutter-kernel-spec-rev3-4-scheduler-jev-capabilities.md)).

### 6. Every check names its executor, and a check that ran is not a check that was right

Each pre-check and post-check MUST name its executor: **deterministic code** (an artifact
exists, a schema validates, a test passed, a dependency resolved, a file is in scope), **Jev**
(a bounded semantic judgement against a well-defined criterion), or **reasoning or human
review** (criteria conflict, evidence is ambiguous, or the decision needs substantial
analysis). [ADR-053](ADR-053-intelligence-selection-deterministic-jev-llm-human.md) owns the
selection rules. A yes/no phrasing does not make a question a simple classification: "Is this
concurrent implementation correct?" can need deep reasoning. The runtime can guarantee that a
required check ran, not that a semantic model's answer was correct. For important outcomes, a
capability MUST collect executable evidence and MUST keep an escalation path.

### 7. Leafcutter holds process authority; workers hold bounded implementation autonomy

Leafcutter MUST own process authority: required evidence, approvals, scope, budgets, workflow
transitions and completion. A worker in the execution stage gets limited implementation
autonomy: how to produce a satisfactory result within that boundary. Its local, agent-like loop
(inspect supplied code, propose a patch, run permitted tests, inspect failures, revise) runs
inside a bounded contract and does not control the engineering process. A worker that finds a
missing requirement MUST return a request and MUST NOT silently change the contract. The
kernel's host operations already follow this split: each is forbidden to `choose_next_step`,
`approve_policy` or `edit_repository`
([design part 4](../../analysis/2026-09-30-decision-kernel-design-4-jev-and-capabilities.md)).

### 8. Jev instructions are small decision specifications

Jev takes a state and typed questions and returns bounded answers. It MUST NOT be asked to
invent the engineering criteria, write the questions or generate the implementation. Every Jev
question MUST be a small decision specification that evaluates only supplied criteria and has
an explicit insufficient-evidence path. Compare "Is this implementation good?" with:

```text
According to the supplied decision policy, does this capability
need a separately reusable workflow boundary?
Evaluate only these supplied criteria:
- independent reuse
- separate state ownership
- multiple internal operations
Return INSUFFICIENT_EVIDENCE when the task or policy does not
establish the relevant facts.
```

In the V0 routing template that path is the `__NEEDS_CONTEXT__` choice, and every template has
an id and a version (design part 4); the Stage 0 smoke test resolved `jev-latest` to
`jev-1.13.0` (design part 1). According to the design discussion, TypeSafe's documentation for
jev-1.13 warns that the model interprets instructions literally, struggles with extra reasoning
indirection, and needs clear criteria and boundary cases. This ADR relies on that report and
has not verified it independently. Prompt design becomes narrower and more testable, not
absent: the work shifts from a persuasive agent prompt to an unambiguous, tested decision.

### 9. Every invocation records what produced it

Leafcutter MUST record, for each model invocation, the versions of the policies, evidence and
instruction template that produced it. The Jev adapter already traces template ids and
versions and an input fingerprint per call (design part 4), and the no-progress fingerprint
includes the relevant policy version (spec part 4, §8.4).

## Consequences

### Positive

- Verification, scope and required evidence become stages and checks the runtime can show
  ran, instead of prose a model is trusted to follow.
- Small, versioned instructions can each be tested, and recorded versions let a changed result
  be traced to a changed policy, evidence set or template.
- A capability can move from a worker loop toward deterministic code without its callers
  changing, the direction [ADR-054](ADR-054-process-representation-and-maturity-model.md)
  describes. One generic lifecycle avoids a hand-built graph per former agent.

### Negative

- More parts must exist before the first capability pays off: registered checks, executors,
  templates and schemas, an invocation compiler, and version records.
- Decision specifications still need careful wording and their own tests. If Jev reads
  instructions literally, as reported, an ambiguous criterion yields a wrong answer.
- A check that ran can be mistaken for a check that was right (§6).
- Existing agent templates keep their monolithic prompts until migrated, so two
  representations of the process coexist for a while.
- The benefit over prompt-driven agents is unmeasured; the comparison is only proposed.

### Operational

- A new kernel capability enters `config/capability_registry.json` through a
  `native_registration` admission; a legacy agent or skill only through a `legacy_admission`
  whose `decision_ref` names an ADR (design part 2).
- Capability review checks that every identifier resolves to a registered, tested
  implementation, no LLM compiles the invocation, each check names its executor, and a missing
  requirement returns a request. Changing a template or policy changes its version (§9).

## Alternatives

- **Keep per-agent monolithic prompts, ported into the kernel as they are.** Rejected. Process,
  evidence requirements and verification stay as prose the runtime cannot enforce or observe,
  and each invocation again asks the model to rediscover the workflow and the architecture.
- **Have an LLM write a fresh prompt for each invocation.** Rejected. Improvised instructions
  cannot be traced to the policy, evidence and template versions that produced them (§9), and
  process knowledge moves back into a model's improvisation.
- **A pure "no prompts" system of JSON contracts and checks only.** Rejected. A JSON contract
  passed to a model is still part of its prompt; changing the format does not remove the need to
  explain the intended transformation. Jev still needs carefully written decision instructions,
  and some checks need reasoning or human review that no contract format replaces.

## Follow-ups and open questions

- **PROPOSED, NOT DECIDED: migrate one existing agent prompt and compare.** The design
  discussion suggested adding no new abstraction layer yet, but taking one agent prompt through
  the lifecycle: process into the graph, evidence requirements into structured configuration,
  verifiable obligations into checks, remaining generation instructions into one small,
  versioned template, plus a deterministic `compile_invocation` step that records policy,
  evidence and template versions. Then compare with the prompt-driven original on the same
  tasks: process omissions, result quality, unresolved-question handling, latency, total cost.
  It needs its own ticket; the first agent is not chosen.
- **Open:** whether the V0 native decision and research graphs (design part 4) are restated in
  §4 lifecycle terms (not required here), the concrete capability-definition schema, and where
  the invocation compiler lives in `kernel/`. The §5 JSON is illustrative only.

## References

- Source: the 2026-09-30 design conversation between BrainCandy and an assistant (its first
  reply, sections 1–7 and the MVP suggestion), endorsed by BrainCandy: "Yea, that is a good way
  to phrase it." Sibling ADRs, kernel design parts and spec are linked inline where first cited.
- [Decision Kernel component](../components/decision-kernel.md)
