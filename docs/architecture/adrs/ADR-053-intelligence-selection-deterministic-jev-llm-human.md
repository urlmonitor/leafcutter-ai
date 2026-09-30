---
title: "ADR-053: Intelligence Selection — Deterministic vs Jev vs LLM vs Human"
description: "Every check is answered by exactly one declared mechanism (deterministic code, Jev, an LLM or a human), chosen by a fixed escalation path. Jev decides against known decision knowledge and LLMs create that knowledge when it is missing, so exact facts stay exact and an uncertain model answer is escalated instead of passing silently."
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
  - docs/architecture/adrs/ADR-054-process-representation-and-maturity-model.md
  - docs/architecture/components/decision-kernel.md
  - docs/analysis/2026-09-30-decision-kernel-design-4-jev-and-capabilities.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-3-contracts.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-4-scheduler-jev-capabilities.md
related_code:
  - kernel/__init__.py
---

# ADR-053: Intelligence Selection — Deterministic vs Jev vs LLM vs Human

## Status

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-09-30 |
| Deciders | BrainCandy |
| Author | `adr-author`, recorded from the 2026-09-30 design conversation (BrainCandy with an assistant) |
| Supersedes | None |

## Context

[ADR-052][adr052] replaces Leafcutter's agents with capabilities. Each capability runs a fixed
lifecycle: PREPARE, PRE-CHECK, COMPILE INVOCATION, EXECUTE, POST-CHECK, and then ACCEPT, REPAIR,
REQUEST INFORMATION or ESCALATE. Every pre-check and post-check is a question that something
has to answer. Four mechanisms can answer one:

- **Deterministic code** computes or verifies an answer exactly.
- **Jev** is TypeSafe's classifier model. The [Decision Kernel][kernel] calls it through
  `langchain-typesafe`. It takes a state and typed questions (`Noul`, `Choice`, `Score`) and
  returns bounded answers with probability distributions. It does not invent the criteria,
  write the questions or generate the work.
- **A generative LLM** writes, synthesizes, interprets and proposes.
- **A human** holds preference, ownership and authority.

Without a recorded rule, the choice of mechanism drifts in three predictable directions:

1. **Everything goes to an LLM**, because a prompt is the easiest thing to write. Exact facts
   such as "did the tests pass?" then become model claims.
2. **Everything goes to Jev**, because it is bounded and cheap to call. Exact checks become
   probabilities, and open architectural judgments get squeezed into a classifier. The kernel
   spec already warns against this: "Do not force an architectural judgment into a classifier
   merely to keep Claude out of the process" ([spec part 4][spec4], §9.4).
3. **The shape of the question decides.** "Is this concurrent implementation correct?" has a
   yes/no answer, but answering it can need deep reasoning.

The design discussion also passed on guidance from TypeSafe's documentation for jev-1.13. That
guidance says the model interprets instructions literally, struggles with extra reasoning
indirection, and needs clear criteria and boundary cases. It also recommends keeping exact
computation and structural invariants in code. This ADR relies on that guidance **as reported
in the design discussion**. It was not re-checked against TypeSafe's documentation for this
record. The kernel design already applies the guidance as template rules: one literal judgement
per question, and nothing that code can compute goes to Jev ([design part 4][design4]).

The decision comes from a design conversation on 2026-09-30, in which BrainCandy proposed this
ADR. It governs the Decision Kernel specified for TICKET-20260930-KernelBootstrapV0. Its
companion, [ADR-054][adr054], decides how *process* knowledge is represented (a workflow, a
policy or checklist, or LLM-guided work) and how it matures. This ADR decides which mechanism
supplies the *intelligence* for a single question. The discussion summed up the idea behind
both: the kernel routes uncertainty to the cheapest mechanism that can reduce it.

## Decision

### 1. Four mechanisms, chosen by what the question needs

| Mechanism | Use when | Examples |
|---|---|---|
| Deterministic | The answer can be computed or verified exactly | Did the tests pass? Does the file exist? Is the schema valid? |
| Jev | A bounded semantic decision with defined criteria or options | Is this document relevant? Which component is affected? Node or subgraph, according to the ADR's criteria? |
| LLM | Generation, synthesis, interpretation, option creation, or genuinely open-ended reasoning | Generate architecture options, synthesize research, write code, explain a conflict |
| Human | The answer is a preference, ownership, risk acceptance, product intent, or an unresolved organizational decision | Should force-refresh update the cache? Which UX do we want? |

Deterministic code MUST answer when the facts can be computed. Jev MUST answer when a bounded
semantic decision can be judged against known criteria. An LLM MUST answer when synthesis,
generation or open-ended reasoning is required. A human MUST answer when the missing answer is
a preference, an authority decision or a risk acceptance.

### 2. The core rule

> **Jev decides against known decision knowledge. LLMs help create decision knowledge when it does not yet exist.**

Jev MUST NOT be asked to invent options, criteria or questions. When options or criteria are
missing, they MUST be created first and only then decided against. Options and criteria that an
LLM creates are proposals until an approval rule accepts them. The kernel records them as
`proposal_status=proposed` and approval status `proposed` ([spec part 4][spec4] §10.4;
[spec part 3][spec3] §7.7). An LLM MUST NOT settle a missing user preference by quietly
changing criteria or their weights (§10.4). A generative response MUST NOT impersonate a human
answer or approve a policy (§7.8).

### 3. The escalation path

A question MUST go to the first mechanism on this path that can answer it:

```text
Can code decide it exactly?
  yes --> DETERMINISTIC
  no  --> Are the options AND the criteria known?
            no  --> LLM creates or synthesizes them (as proposals) --> JEV
            yes --> JEV decides against them
                      confident?  yes --> result
                                  no, evidence missing --> retrieval / research --> JEV again

Knowledge cannot resolve it (preference, authority, risk acceptance) --> HUMAN
```

Jev MUST be asked again only after the evidence has changed. Asking the same question with
unchanged inputs is not progress, and the kernel's no-progress guard stops it. Research MUST
NOT continue merely to raise a confidence score ([spec part 4][spec4] §8.4, §10.5).

### 4. A binary-shaped question is not necessarily a simple classification

The yes/no form of a question MUST NOT decide its mechanism. Two things decide it: whether the
options and criteria are known and bounded, and whether Jev can judge them literally. "Is this
concurrent implementation correct?" MUST NOT go to Jev as a single yes/no question. It needs
executable evidence (`test_runner`) together with `reasoning` or `human` review.

Such a concern can move toward Jev over time, as recurring checks become explicit criteria. In
the design discussion, the example concerns (merge semantics, timeouts, partial failures and
state mutation) became a `parallel_execution_policy` ([ADR-054][adr054]). Jev can then decide
which of those known concerns apply to a task. That makes Jev the judge of which known concerns
apply. It does not make Jev the judge of correctness.

### 5. Exact computation and structural invariants stay in code

Exact computation and structural invariants MUST be implemented as deterministic code. They
MUST NOT be delegated to Jev or to an LLM. Examples: an artifact exists, a schema validates, a
test passed, a dependency resolved, a file lies within the authorized scope. In the kernel,
the exact checks (permissions, schema compatibility, presence of required evidence, approved
policy constraints, and remaining budgets) MUST run before Jev evaluates anything
([spec part 4][spec4] §9.4).

### 6. The runtime guarantees that a check ran, not that its answer is correct

The runtime can guarantee that a required check RAN. It cannot guarantee that a semantic
model's answer is CORRECT. Therefore:

- The result of a `jev` or `reasoning` check MUST NOT be presented as verification of the claim
  it judged. A model-generated summary is not independently verified evidence, and schema
  validation checks structure, not truth ([spec part 3][spec3] §7.3, §7.11).
- An important outcome MUST be backed by executable evidence wherever such evidence can exist.
  It MUST also keep an escalation path to further evidence, to reasoning or to a human.
- An uncertain answer MUST NOT pass silently. The kernel already applies this rule to routing:
  a low-confidence answer becomes `insufficient_context`, and the top candidate is never
  selected silently ([design part 4][design4]).

### 7. Every check declares its executor

Every PRE-CHECK and POST-CHECK in the [ADR-052][adr052] capability lifecycle MUST declare its
executor explicitly, as one of these values:

| Executor | Mechanism | Answers |
|---|---|---|
| `deterministic` | Deterministic | Exact facts and structural invariants (§5) |
| `test_runner` | Deterministic | Runs tests and supplies executable evidence for behavioural claims (§6) |
| `jev` | Jev | Bounded semantic judgments against supplied criteria |
| `reasoning` | LLM | Conflicting criteria, ambiguous evidence, or decisions that need substantial analysis |
| `human` | Human | Preference, authority and risk acceptance |

A `jev` check MUST also declare where an uncertain answer goes, for example to an evidence
request or to a review request. The design discussion's illustrative capability configuration
expresses this with an `on_uncertain` key. That configuration is not a native LangGraph or Jev
API, and ADR-052 owns its schema. This ADR fixes only the executor vocabulary and the rule that
every check declares its executor.

### 8. How the kernel's outcomes map to the mechanisms

The kernel's V0 decision capability applies this path ([design part 4][design4]). Its
`validate_basis` and `combine` nodes are deterministic, and its `assess` node sends one batch
to Jev. Kernel routing, research need planning and retrieval reranking also use Jev. Each
decision outcome maps to the mechanism that handles it:

| Decision outcome (spec §7.7) | Earlier name (spec §7.6) | Raised by `combine` when | Mechanism | Kernel follow-up |
|---|---|---|---|---|
| `resolved` | `RESOLVED` | Every resolution condition holds | Jev against a known basis; thresholds applied in code | `completed` with `decision_report.v1` |
| `needs_evidence` | `NEEDS_INFORMATION` | A required criterion lacks sufficient evidence | Retrieval or research, then Jev again | `research_request.v1` child; research binds `retrieve.repository` or `host.research` |
| `needs_options` | `NEEDS_OPTIONS` | The options are unknown | LLM | `options_request.v1` to `host.generate_options` |
| `needs_synthesis` | `NEEDS_REASONING` / `NEEDS_SYNTHESIS` | Evidence is sufficient but the answer is uncertain, or evidence conflicts | LLM | `synthesis_request.v1` to `host.synthesize` |
| `needs_human` | `NEEDS_HUMAN` | A preference, a tie, or an approval | Human | Persisted human interaction (`human_question_request.v1`) |

A `needs_*` outcome MUST NOT be collapsed into a guessed result. It becomes `waiting` with a
child request, or `partial` with open questions if the evidence has not changed since the
previous attempt. The routing outcome `no_match` (earlier `NO_CAPABILITY`) means that no
registered capability can meet the need. The kernel records a capability gap and then either
runs an approved fallback or returns a `blocked` result.

V0 splits the "options or criteria are missing" branch in two, and a human approves any
criteria an LLM proposes before Jev decides:

- A request with no options goes to an options request with `propose_criteria=true`.
- A request that has options but no criteria goes to `host.generate_options` with
  `propose_criteria=true, max_options=0`. The run then pauses on a `human_question_request.v1`
  so a human can approve or edit the proposed criteria.
- Jev decides only against approved criteria.

The flow is specified in [design part 4][design4].

## Consequences

### Positive

- Each check names its executor, so a reader can tell which results rest on computation and
  which rest on a model's judgment.
- Exact facts stay exact. Jev answers stay bounded, with thresholds applied in code. LLM output
  stays a proposal until something decides against it or approves it.
- Uncertainty is routed rather than swallowed. Each kind of missing knowledge has a named next
  mechanism and a kernel request that serves it.
- The rule matches the kernel as designed, so V0 complies without a redesign. Deterministic
  `validate_basis` and `combine`, Jev `assess`, and generative and human handoffs for `needs_*`
  are already in place.
- When an LLM creates options and criteria, Jev can reuse them in later decisions. This is how
  [ADR-054][adr054] moves process knowledge from LLM-guided work toward policies and workflows.

### Negative

- Authoring costs more. Every check needs an executor, and every `jev` check also needs clear
  criteria, boundary cases and a route for an uncertain answer.
- "Are the options and criteria known?" is itself a judgment. If a hard question is filed as a
  bounded Jev question, Jev gives a confident wrong answer, and by §6 the runtime cannot tell.
- This ADR does not define "important outcome" mechanically. The executable-evidence duty in §6
  depends on capability authors applying it.
- The Jev characteristics rest on jev-1.13 guidance passed on in the design discussion. They
  were not independently verified here, and a different Jev model can behave differently.
- The human path can stall. An unanswered question keeps a run in `waiting_human` until it is
  cancelled ([design part 4][design4]).

### Operational

- Under ADR-052, a capability definition gives every check an `executor`. A review rejects a
  check that has no executor, or one that gives exact computation to `jev` or `reasoning`.
- Jev question templates follow the kernel's template rules. Each question makes one literal
  judgement and names the parts of the state it reads. Each template has an id and a version
  ([design part 4][design4]).
- Jev thresholds are configurable and risk-specific, and are tuned on representative tasks.
  Provider confidence is a statistic derived from the distribution, not a readiness percentage
  ([spec part 4][spec4] §9.4).
- Every Jev call is traced with the `model_id` it returns, its template ids and versions, its
  input fingerprint and its raw distributions. Each answer can therefore be traced to the
  mechanism and version that produced it.

## Alternatives

- **An LLM for everything.** Rejected. Exact checks would become model claims that can be wrong
  where code cannot be, and each one would cost a generative call. A free-text verdict gives the
  kernel's thresholds in code nothing to evaluate. Engineering process would again live inside
  prompts, which is what ADR-052 moves away from.
- **Jev for everything, including exact checks.** Rejected. Jev returns a probability for a
  literal judgment. Sending an exact check through it turns a certain answer into a probable
  one, which the kernel's template rule forbids. Jev also cannot supply missing options or
  criteria, and spec §9.4 rules out forcing open architectural judgments into a classifier. The
  jev-1.13 guidance passed on in the design discussion (literal reading, weak with reasoning
  indirection) points the same way.
- **Deterministic code only, with a human fallback.** Rejected. Code cannot make bounded
  semantic judgments such as document relevance, the affected component or capability routing.
  The kernel's routing, research planning, reranking and decision assessment all depend on those
  judgments. Every one of them would wait on a person, who would also have to create every
  option and criterion by hand. The human would become the bottleneck even for questions that
  known criteria already settle.

## References

- Originating discussion: the design conversation of 2026-09-30, in which BrainCandy proposed
  this ADR and endorsed the framing it records.
- [ADR-052: Capabilities replace agents; prompts are compiled][adr052]. Defines the
  PRE-CHECK / POST-CHECK lifecycle whose checks declare the executors fixed in §7.
- [ADR-054: Process representation and maturity model][adr054]. The companion "process" ADR:
  workflow, policy or checklist, or LLM-guided work, and maturity levels 0–4.
- [Decision Kernel component][kernel], [kernel design part 4][design4], and the kernel spec
  [part 3][spec3] (contracts, §7.6 and §7.7) and [part 4][spec4] (Jev and capabilities, §8–§10).

[adr052]: ADR-052-capabilities-replace-agents-prompts-are-compiled.md
[adr054]: ADR-054-process-representation-and-maturity-model.md
[kernel]: ../components/decision-kernel.md
[design4]: ../../analysis/2026-09-30-decision-kernel-design-4-jev-and-capabilities.md
[spec3]: ../../analysis/2026-09-30-leafcutter-kernel-spec-rev3-3-contracts.md
[spec4]: ../../analysis/2026-09-30-leafcutter-kernel-spec-rev3-4-scheduler-jev-capabilities.md
