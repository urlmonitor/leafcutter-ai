---
title: "ADR-064: Persona Discovery Before Feature Planning"
description: "Agent-facing feature planning starts with attributed interviews of its consuming roles, so acceptance criteria and evaluations follow explicit usage needs instead of assumed tool success."
type: adr
status: active
created: '2026-10-01'
last_updated: '2026-10-01'
deciders:
  - Hendrik
components:
  - ac_store
  - decision_kernel
  - knowledge_management
related_docs:
  - docs/architecture/adrs/ADR-010-ac-store-as-authoritative-backlog.md
  - docs/architecture/adrs/ADR-012-retire-create-ticket-js.md
  - docs/architecture/adrs/ADR-023-product-truth-flow-first-upstream-layer.md
  - docs/architecture/adrs/ADR-053-intelligence-selection-deterministic-jev-llm-human.md
  - docs/architecture/adrs/ADR-054-process-representation-and-maturity-model.md
  - docs/architecture/components/decision-kernel.md
  - docs/analysis/2026-10-01-repository-query-catalog.md
  - docs/analysis/2026-10-01-repository-query-evaluation-cases.json
related_code:
  - templates/skills/plan-feature/SKILL.md
  - templates/workflows-js/plan-feature.js
  - templates/agents/product-owner.md
  - templates/agents/business-analyst.md
  - templates/agents/it-po.md
---

# ADR-064: Persona Discovery Before Feature Planning

## Status

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-01 |
| Decider | Hendrik, by explicit instruction to preserve this planning decision |
| Author | Delegated ADR author, recording the user's decision |
| Supersedes | None |
| Implementation | ADR-only delivery; future planning architecture, AC design, enforcement and runtime precedent registration require separately scoped work |

## Context

A real repository question asked how many acceptance criteria concern test writing and what
their work statuses are. The retrieval tool returned successful requests and discovered the
selected family, but omitted `work_status`. Lifecycle `status: active` answered a different
question. A local receipt also did not establish an accessible Langfuse trace. Execution success
alone therefore failed to establish that the consumer's question was answerable.

The subsequent [role question catalog](../../analysis/2026-10-01-repository-query-catalog.md)
preserves 25 proposed questions from BA, PO, IT PO, coder and QA, grouped into eight families.
The [initial evaluation specification](../../analysis/2026-10-01-repository-query-evaluation-cases.json)
defines 12 planned cases across six families. These are attributed role proposals and unexecuted
evaluation specifications, not measured usage or proof that the new tool answers them. The pilot
does not retroactively establish that every role was interviewed under the full process below.

The user decided to make consumer interviews a prerequisite to future feature planning, including
planning coordinated by Jev. [ADR-010](ADR-010-ac-store-as-authoritative-backlog.md) keeps ACs
authoritative, and [ADR-012](ADR-012-retire-create-ticket-js.md) keeps ticket creation downstream
of ACs. This decision supplies usage evidence before AC design. It complements the approved
flow and product-truth layer in [ADR-023](ADR-023-product-truth-flow-first-upstream-layer.md);
it does not replace that layer or its existing approval process.

[ADR-053](ADR-053-intelligence-selection-deterministic-jev-llm-human.md) distinguishes bounded
Jev judgments from human authority, and
[ADR-054](ADR-054-process-representation-and-maturity-model.md) distinguishes a policy from
implemented enforcement. A decision file must not be presented as runtime wiring.

## Decision

### 1. Identify the real consumers before designing acceptance criteria

For every new or materially changed agent-facing feature, the planning owner MUST identify the
roles that will actually consume it and record why each is in scope. The owner MUST interview
those personas before creating or materially amending the feature's acceptance criteria.
BA, PO, IT PO, coder and QA are examples, not a mandatory roster of five agents.

Each persona interview MUST load the corresponding real agent template and any applicable role
context, preserve that role's restrictions, and record the template path and source revision or
content identity. A generic agent merely claiming to act as a role does not satisfy this step.
When a required role template is missing, the planning owner MUST record the gap and resolve the
role definition instead of inventing an authoritative charter.

### 2. Ask for concrete recurring use and the conditions for a useful answer

Each in-scope persona MUST be asked for five expected recurring query or use-case types, with a
concrete example for each. The interviewer MUST capture:

- The task and trigger, the user's or agent's goal, and the intended scope.
- Required outputs, field meanings, evidence and source provenance.
- Clarification needed when inputs, scope or authority are missing.
- Failure and partial-result expectations, including what the consumer must not infer.
- Why the type is expected to recur, and whether that claim is a proposal or is supported by
  observed usage.

When the role can substantiate fewer than five distinct types, the interviewer MUST record the
shortfall and its reason rather than fabricate demand. Human responses and corrections MUST
take precedence over persona suggestions. Agent role proxies MUST be labeled as proxies; their
answers MUST NOT be presented as interviews with actual human users or empirical frequency data.

### 3. Preserve attribution while consolidating the discovery

The planning owner MUST preserve each original question, its role and interview provenance with
a stable origin identifier. Shared needs MUST be consolidated into a traceable usage catalog
without silently narrowing the original questions or discarding conflicting needs.

The catalog MUST separate facts absent from the authoritative source, facts not exposed by the
index or interface, missing query operations over available data, and behavior not yet verified.
It MUST also separate execution success from answerability, declared links from observed proof,
and complete results from bounded or unknown totals.

The owner MUST record unresolved scope, evidence and authority questions. Material ambiguity
MUST be clarified with the relevant persona or human before the affected AC design proceeds.

### 4. Derive ACs and evaluation cases from the discovered usage

PO, BA and IT PO MUST reuse or amend existing canonical ACs where applicable and map every
in-scope catalog need to an AC, a planned evaluation case, or an explicit deferred/out-of-scope
decision with its reason. They MUST resolve coverage gaps before calling the feature fully
covered. The discovery catalog itself MUST NOT be labeled an AC store or proof of implementation.

Planned evaluation cases MUST carry independent expected evidence, the answer contract and
controls that distinguish plausible wrong behavior. Source-oracle inspection MUST NOT replace
tool output during later execution. Planned cases MUST remain distinguishable from runnable
tests and recorded execution results. Implementation and ticket generation will follow the
normal AC-driven path.

### 5. Jev checks the supplied discovery evidence and requests what is missing

Future automated planning enforcement MUST be a LangGraph flow, with Jev owning contextual decisions about what needs planning, which concerns apply and what evidence to seek, consistent with ADR-053 and ADR-054. A narrow JavaScript persona gate or an outer LangGraph wrapper around a hand-written decision tree does not satisfy this architectural direction.

A future Jev-driven planning capability MUST receive this policy, the consumer-role scope and the
attributed catalog as explicit evidence. It MUST check the proposed work against the discovered
uses and identify missing roles, missing required information and unresolved coverage. It MUST
request further research or clarification instead of treating a plausible plan as sufficient.

Deterministic checks MUST establish structural facts such as required fields and traceability
links where possible. Jev's semantic judgment MUST NOT be described as proof of correctness.
Human authority, preferences and risk acceptance remain governed by ADR-053.

This policy MUST NOT grant permission to contact an external service, send repository context,
publish records or change existing access rights. Existing authorization boundaries still apply.

### 6. Apply the discovery requirement proportionately

A typo correction, a purely mechanical internal change or a small fix with unchanged consumer
behavior MUST record why new persona interviews are not applicable, including the existing
usage and AC evidence on which that conclusion rests. The size of a diff alone MUST NOT justify
an exemption when outputs, field meanings, permissions or failure behavior materially change.

The applicability decision MUST be visible to the normal planning reviewer. An exemption MUST
NOT bypass existing AC, product-truth or approval requirements.

### 7. Keep the accepted policy separate from its implementation

This ADR is the canonical record of the user's accepted planning policy. The links in
`CLAUDE.md`, the `plan-feature` entry point and the decision-kernel component documentation
will make the policy discoverable. These links MUST NOT be reported as implemented workflow
checks, configured Jev behavior, or a successfully reused runtime precedent.

The user explicitly limited this delivery to the ADR and minimal policy-discovery links. Planning architecture, planning-enforcement AC design and implementation are outside this delivery and require separately scoped work; no narrow persona gate is included. If that future work is commissioned, PO, BA and IT PO will use the canonical AC process before implementation. Once the actual decision-store implementation is integrated, any runtime precedent
registration MUST follow its governed validation and publication path with truthful provenance.
No fabricated kernel run, learned-decision identifier, approval timestamp or trace will be
created merely to make this conversation conform to a runtime record schema.

## Consequences

### Positive

- Real consumer tasks shape the required fields, evidence, failure handling and evaluations
  before implementation choices obscure missing needs.
- Attribution preserves disagreement and makes it possible to trace an AC back to the role's
  original question.
- Human decisions remain authoritative while persona agents supply useful design hypotheses.

### Negative

- Material agent-facing changes take additional discovery effort before AC authoring.
- Persona suggestions can be mistaken or repetitive and require review; they do not substitute
  for observed usage or human research.
- Catalog and evaluation mappings need maintenance when consumer behavior changes.

### Operational

- The `plan-feature` skill and workflow are the existing planning entry points. Their future
  enforcement changes require ACs and verification; no kernel code or workflow implementation
  is changed by this record.
- Existing role templates remain the source of role constraints. Interview attribution records
  which versions were loaded.
- This branch has no integrated runtime decision store. The sibling decision-store work
  constrains records to genuine human-approved kernel decisions; an ADR is not silently
  converted into one. Registration and a demonstrated future Jev read remain pending work.
- No planning implementation AC or ticket is included in this decision-only delivery. Any separately commissioned future planning work will cite this record through its own AC handoff.

## Alternatives

- **Design ACs from the initial tool concept alone.** Rejected by the user's request to gather
  role queries first. It misses required distinctions such as lifecycle versus work status and
  successful retrieval versus an answered question.
- **Leave interviews as an informal, unlinked conversation.** Rejected because future planning
  runs cannot reliably find the consumer's original examples or explain how an AC covers them.
- **Make every task run the same five role interviews.** Rejected because the relevant consumers
  vary and purely mechanical changes do not justify fabricated personas or repetitive answers.
- **Treat the saved policy as configured Jev behavior.** Rejected because a document does not
  implement the capability, establish provider authorization or demonstrate runtime retrieval.

## References

- [Repository query catalog](../../analysis/2026-10-01-repository-query-catalog.md)
- [Planned evaluation cases](../../analysis/2026-10-01-repository-query-evaluation-cases.json)
- [Plan-feature entry point](../../../templates/skills/plan-feature/SKILL.md)
- [Decision kernel component](../components/decision-kernel.md)
