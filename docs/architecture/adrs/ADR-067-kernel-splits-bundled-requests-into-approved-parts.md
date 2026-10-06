---
title: "ADR-067: The Kernel Splits a Bundled Request into Parts a Person Approves"
description: "A request that bundles several questions is split inside the kernel: the host proposes 2 to 5 verbatim-quoted parts through a new host operation, host.decompose_goal, deterministic code converts the proposal, and only a person approves it before the parts run one at a time in dependency order. This replaces the hand split outside the kernel and keeps capability-gap counts honest; the ADR pins the four schema ids (a new leafcutter.split_answer.v1, not an extension of leafcutter.human_answer.v1), the endings by trigger, the bounds and budgets, and the staged rollout of split.enabled."
type: "adr"
status: "active"
created: "2026-10-05"
last_updated: "2026-10-05"
deciders:
  - BrainCandy
components:
  - decision_kernel
related_docs:
  - docs/reference/kernel-request-splitting.md
  - docs/reference/kernel-request-splitting-2-conversion-gate-runs-config.md
  - docs/architecture/adrs/ADR-052-capabilities-replace-agents-prompts-are-compiled.md
  - docs/architecture/adrs/ADR-053-intelligence-selection-deterministic-jev-llm-human.md
  - docs/architecture/adrs/ADR-055-capability-registry-starts-empty.md
  - docs/architecture/adrs/ADR-059-decision-store-reviewable-yaml-records-now-graph-later.md
  - docs/architecture/adrs/ADR-060-source-of-truth-and-approval-authority.md
  - docs/architecture/components/decision-kernel.md
  - docs/acceptance-criteria/decision-kernel/DK-400-split-compound-requests/DK-400.yaml
  - docs/product-truth/mock-data/leafcutter/decisions.mock.json
  - docs/product-truth/flows/leafcutter/decision-forming.flow.json
  - docs/product-truth/mockups/leafcutter/decision-split-approve.mockup.json
  - docs/product-truth/mockups/leafcutter/decision-split-progress.mockup.json
  - docs/decisions/dec-9925ebf1895222f4.yaml
  - docs/analysis/2026-10-01-kernel-trace-review-decision-records-run.md
  - docs/analysis/2026-09-30-decision-kernel-design-3-kernel-scheduler.md
  - docs/analysis/2026-09-30-decision-kernel-design-4-jev-and-capabilities.md
  - tickets/00_inbox/TICKET-20261001-KernelCompoundGoalSplit.md
related_code:
  - config/capability_registry.json
  - config/capability_registry.schema.json
  - config/kernel_config.default.json
  - config/kernel_config.schema.json
  - kernel/config.py
  - kernel/contracts/schema_ids.py
  - kernel/contracts/schema_catalog.py
  - kernel/contracts/interaction.py
  - kernel/contracts/payloads.py
  - kernel/interaction/submissions.py
  - kernel/capabilities/host/registry.py
  - kernel/capabilities/host/generate_options.py
  - kernel/scheduler/routing.py
  - kernel/scheduler/nodes_route.py
  - kernel/scheduler/nodes_gaps.py
  - kernel/intent/classify.py
  - kernel/intent/questions.py
  - kernel/schemas
  - kernel/adapters/claude_code/SKILL.md
  - kernel/adapters/codex/SKILL.md
---

# ADR-067: The Kernel Splits a Bundled Request into Parts a Person Approves

## Status

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-05 |
| Deciders | BrainCandy |
| Author | `adr-author`, recording the decisions approved at the DK-400 gates of 2026-10-05, the IT PO design those gates approved, and the build plan of decision dec-9925ebf1895222f4 |
| Supersedes | None. It replaces the design of two tickets that the DK-400 tree superseded: TICKET-20261002-KernelDecomposeMultiPartGoal and TICKET-20261001-KernelCompoundGoalSplit. |
| Decision record | [dec-9925ebf1895222f4](../../decisions/dec-9925ebf1895222f4.yaml) (run-0e9524762c1b4f85, approved by human:user on 2026-10-05). It puts this ADR in Step 0, before DK-400c-1 is built. |

Amended 2026-10-05: the IT PO settled Open Questions 1, 2, 3, 5 and 6 in the DK-400 ACs, and
the Decision section was aligned with those answers. Question 4 stays open. The fixes:

- §2 gates and §7: the bundle check is skipped by the WorkItem flag `split_checked`, not by a
  closed split record. A proposal with fewer than two parts, or an abandoned one, keeps no
  `Decomposition`, only a run event and a limitation (Open Question 1, DK-400c-3).
- §4.1: the request's `max_parts` is `split.max_parts` and is never lowered by the allowance
  (Open Question 3, DK-400c-1).
- §5 step 7 and §6: not-covered entries carry one reason naming the binding limit, the
  five-part cap or the run's part allowance, and the gate wording names that limit (Open
  Question 2, DK-400c-1-i).
- §8: new "Part payload" rule, and "No nesting" now pins each part's binding at creation from
  the run's pinned registry snapshot (Open Question 5, DK-400e-1).
- Open Questions: each settled question is marked Resolved, and Question 6 lists the three
  confirmed interpretations.

Amended 2026-10-05 (split for length): the full rules of §1 to §11 moved word for word into the
companion specification ([part 1][spec1], [part 2][spec2]) under the same numbers and titles;
each Decision section keeps its number, title and binding decision in short. Context,
Consequences and Alternatives (now a table) were condensed without dropping a point.

## Context

The kernel's decision capability takes one bounded question. Two runs showed what happens to a
request that bundles several:

- **Turned away.** Run run-40d2159630bb48bd (2026-10-02) held four decisions in one goal
  (storage format, Neo4j projection, clustering method, mining source). Routing ended
  `no_match` with reason `jev_none`, and the run was blocked with an `unsupported` gap. The
  orchestrating Claude Code session then split the goal by hand, outside the kernel; its first
  part became decision dec-93c1c730463c1f3c (mock record `dcp-reusable-criteria-by-hand`).
- **Squeezed into one choice.** Run run-5d246775f5e54f11 (2026-10-01) bundled five sub-decisions.
  The decision capability answered them as one pick-one-of-N, and the person had to add a
  composite option ([trace review, Finding 5](../../analysis/2026-10-01-kernel-trace-review-decision-records-run.md)).

Not deciding costs two exit criteria of `phase_kernel_1_founding`. The hand split is the "hidden
host-side orchestration" that the first rules out. Capability-gap counts, the second, go wrong
both ways: a compound request counted as a gap overstates what the kernel lacks, and a real gap
hidden behind a split understates it.

The [DK-400 tree](../../acceptance-criteria/decision-kernel/DK-400-split-compound-requests/DK-400.yaml)
(merged in PR #1012) specifies the behaviour, with the user's PO-gate and final-gate decisions of
2026-10-05 and the IT PO's design in its ACs. Its product truth is the v6 `Decomposition` entity
of [decisions.mock.json](../../product-truth/mock-data/leafcutter/decisions.mock.json), the
`split-*` nodes of the [decision-forming flow](../../product-truth/flows/leafcutter/decision-forming.flow.json)
and the mockups `decision-split-approve` and `decision-split-progress`. The IT PO left the
split-answer schema id to this ADR (DK-400d-1); DK-400c-1 needs this ADR before its registry
entry lands; the build plan [dec-9925ebf1895222f4](../../decisions/dec-9925ebf1895222f4.yaml)
places it in Step 0.

Constraints: [ADR-053](ADR-053-intelligence-selection-deterministic-jev-llm-human.md) orders
deterministic code, Jev, an LLM, then a human; Jev never invents (§2), and an uncertain answer
never passes silently (§6). [ADR-052](ADR-052-capabilities-replace-agents-prompts-are-compiled.md)
sends host work as a compiled, fingerprinted packet (§3).
[ADR-055](ADR-055-capability-registry-starts-empty.md) admits a capability only by a recorded
decision. [ADR-060](ADR-060-source-of-truth-and-approval-authority.md): only a person approves,
and the kernel stays read-only toward the repository during a run. In code, `_expectation`
(`kernel/interaction/submissions.py`) returns `leafcutter.human_answer.v1` for every
`HumanQuestion`, and `HumanAnswerPayload` takes exactly one of `choice_id`, `free_text` or a
structured approval.

Two superseded tickets were the first design: "Kernel: split a multi-part design goal into
bounded decisions instead of blocking" (2026-10-02, branch `docs/kernel-tickets-criteria-reuse`)
named `host.decompose_goal` and the two decomposition schemas, and [the compound-goal-split
ticket](../../../tickets/00_inbox/TICKET-20261001-KernelCompoundGoalSplit.md) asked for one record
per sub-decision. DK-400 changed two of their rules: a request the kernel would accept as one is
split too, and a rejected `ambiguous` split falls back to today's clarification question.

## Decision

Each section states the binding decision in short; its full rules, under the same number and
title, are in the companion specification, [part 1][spec1] (§1 to §4) and [part 2][spec2] (§5 to
§11). The companion is part of this decision: its MUST statements bind as this ADR's do.

### 1. Splitting happens inside the kernel, and each step uses one mechanism

A request that bundles several separate questions MUST be split inside the kernel run, never by
hand outside it, and the kernel MUST NOT record a split made outside it (DK-400 Q4). A split is
generic: subject kind `goal`, `research_request` or `decision_question`, found at `routing` or
`mid_run`. Jev MUST NOT write, merge, reword, order or judge parts. Each step MUST use only its
ADR-053 mechanism ([spec §1][s1]):

| Step | Mechanism |
|---|---|
| Gates (§2); conversion (§5); scheduling the parts (§8) | Deterministic |
| "One question or several?", template `kernel.split.bundled` (§2) | Jev |
| Proposing the parts, `host.decompose_goal` (§3) | LLM, as host |
| Split gate: approve, reword, leave out or reject (§6) | Human |

### 2. Detection: gates first, then one Jev question that adds no provider call

Deterministic gates MUST run first, and any failing gate skips the check: `split.enabled`; a
host-operation budget for one decomposition; semantic routing (not fixed, continued, retried,
a deterministic `no_match`, or a part of an approved split); not a caller-supplied
`leafcutter.decision_request.v1`; a remaining part allowance of at least 2; a decision, evidence
or unresolved answer kind; and the item's `split_checked` flag not yet set. Then one literal Jev
`noul`, `kernel.split.bundled`, MUST ride the item's first existing Jev batch and MUST NOT add a
provider call, unless the batch passes `jev.max_questions_per_call`. A subject is bundled only at
or above `split.bundle_threshold` (0.8); keyword heuristics MUST NOT decide it. Triggers
`jev_none`, `ambiguous` and `bundled_accepted` are caught at routing on the root, in the same
route pass, never inside a capability; a non-root item found `mid_run` has no trigger. The split
record (`dcp-` plus 16 hex) is checkpointed at detection, and the run waits on `waiting_host`.
Full rules: [spec §2][s2].

### 3. The host operation `host.decompose_goal` and its registry entry

The new host operation `host.decompose_goal` MUST propose the parts, on the pattern of
`host.generate_options`: a compiled, fingerprinted `HostWorkRequest` that allows only
`read_supplied_artifacts` and `propose_split`, grants no repository access, costs one host
operation on the root's budget and records no `host_only` gap. Its entry in
`config/capability_registry.json` is `host_handoff`, `routing` `fixed`, accepts
`leafcutter.goal_decomposition_request.v1`, produces `leafcutter.goal_decomposition.v1`, and is
admitted by `native_registration` with `decision_ref` `ADR-067`. This ADR is the recorded
decision ADR-055 requires. It is never a `no_match` fallback. Allowed child capabilities follow
the subject kind (`goal`: decision or research; `research_request`: research;
`decision_question`: decision). Full rules: [spec §3][s3].

### 4. Four schema ids

Four ids MUST be registered in `SCHEMA_CATALOG` and `KNOWN_SCHEMA_IDS`, exported to
`kernel/schemas/<id>.schema.json` with fixtures, and serve all three subject kinds. Where an AC
names an id differently, this ADR wins. Full rules: [spec §4][s4].

| Schema id | Carries | Sent by |
|---|---|---|
| `leafcutter.goal_decomposition_request.v1` | The request of `decompose_goal` | Kernel |
| `leafcutter.goal_decomposition.v1` | The host's proposal | Host |
| `leafcutter.split_answer.v1` | The person's answer at the split gate | Person, relayed by the host |
| `leafcutter.decomposition.v1` | The split record, and the output of a split item | Kernel |

#### 4.1 `leafcutter.goal_decomposition_request.v1`

The request carries `split_id`, `subject_kind`, `subject_text`, `allowed_capabilities`,
`min_parts` (2) and `max_parts` = `split.max_parts`, never lowered by the run's remaining
allowance. Full rules: [spec §4.1][s41].

#### 4.2 `leafcutter.goal_decomposition.v1`

The proposal carries `parts` (`id`, `text`, verbatim `covers`, `depends_on`, `child_capability`)
and `one_question_rewording`. It MUST accept 0 parts up to a ceiling above `split.max_parts`.
Full rules: [spec §4.2][s42].

#### 4.3 `leafcutter.decomposition.v1`: the split record

The split record MUST carry the fields delivered by DK-400a-1, DK-400c-1, DK-400d-1 and
DK-400e-1, with `state` null until the proposal arrives and then one of the eight product states
of mock-data v6. It MUST NOT admit the hand-split-only values of the mock dataset, and it MUST
satisfy the v6 `Decomposition` invariants that apply to a kernel split. Full rules:
[spec §4.3][s43].

#### 4.4 `leafcutter.split_answer.v1`: the person's answer

The split gate MUST accept a new schema, `leafcutter.split_answer.v1`;
`leafcutter.human_answer.v1` MUST NOT be extended. Three reasons:

1. `human_answer.v1` takes exactly one of three modes, with no room for an answer, per-part
   reviews and a note side by side; extending it would change a published v1 schema that every
   existing question accepts.
2. An extension would let every question accept a split answer, and the split gate a
   `choice_id` or free text, refused only by a new flag as `semantic_invalid`, not `wrong_kind`.
3. DK-400d-1-ii's skill-example test only means something against a dedicated schema.

The answer is `answer` (approved or rejected), `parts` (one `{id, review, text}` per offered
part on approval, empty on rejection) and `note`, with no other field. A `HumanQuestion` MUST
declare the response schema it accepts (default `leafcutter.human_answer.v1`), `_expectation`
MUST return it, and the actor kind stays `human`. Full rules: [spec §4.4][s44].

### 5. Conversion is total and deterministic

The host's proposal MUST be converted in a fixed order: schema; dependencies (cycles, unknown
and duplicate ids refused); allowed capabilities; the verbatim quote check with set-aside;
release of dependencies on set-aside proposals; the part count; the cut to `split.max_parts` and
the run's allowance in run order, with one not-covered reason naming the binding limit; then the
gate. Conversion MUST NOT yield a partial split. When the repair attempts run out, the split is
abandoned, never failed, and the subject goes on as for fewer than two parts ([spec §5][s5]).

### 6. The split gate: only a person answers

The split gate MUST be a persisted `HumanQuestion` built deterministically from the split record,
and only a person answers it: `gate_by` is the human actor id, never `relayed_by`; `gate_at` is
the kernel clock in UTC. A person can keep, reword or leave out parts, or reject, but MUST NOT add
a part or change a part's dependencies or capability. A refused answer exits with code 3 and
changes nothing; no part work item exists before an accepted answer. Full rules: [spec §6][s6].

### 7. Endings are keyed on the trigger

Endings MUST be chosen deterministically from `trigger` and `found_at`, never by a model:

| Trigger | Rejected at the gate | Fewer than two parts, or repairs exhausted |
|---|---|---|
| `jev_none` | `rejected`; run `blocked` with today's `unsupported` gap | Today's gap; run `blocked` |
| `ambiguous` | `rejected_clarify`; today's clarification question, run `waiting_human` | Today's clarification question |
| `bundled_accepted` | `rejected_kept_whole`; one decision from `kept_routing` | One decision from `kept_routing` |
| none (`mid_run`) | `rejected_kept_whole`; one decision or research step | One decision or research step |

A clarified request MUST NOT be offered a second split in the same run, and a caller-supplied
`leafcutter.decision_request.v1` MUST NOT be split. Full rules: [spec §7][s7].

### 8. Bounds, order and budgets

A split offers 2 to 5 parts (`split.max_parts`, bounded to 2 to 5), a run at most
`split.max_parts_per_run` (5). Parts MUST run one at a time, in Kahn's dependency order (lowest
proposed index first), as work items of the same run; parallel children are out of scope. Each
part carries a `leafcutter.goal_request.v1` like a stand-alone run of its question, is bound at
creation from the run's pinned registry snapshot, is never routed or split again, and MUST get
a stand-alone run's budget, never lent to another part. Full rules: [spec §8][s8].

### 9. What an approved split produces

A split item's status MUST follow its parts: `completed` if every part not left out settled,
`partial` otherwise. A split root's output MUST be the split record under
`leafcutter.decomposition.v1`, with every decided part's record in `decision_ids`, and no
`decision_report.v1` for the bundle. Each decided part stages its own record through the
existing staging gate, with the record schema unchanged. Full rules: [spec §9][s9].

### 10. Gap accounting keeps counts honest in both directions

The gap for the split's subject MUST be decided when the split's outcome is known: none when
approved, kept whole or cancelled before the gate; today's `unsupported` gap for a failed
`jev_none` split; today's ambiguous gap only if an `ambiguous` request's clarification ends
unresolved. A part's own observations are attributed to the part. Full rules: [spec §10][s10].

### 11. Configuration, the off switch and the staged rollout

Every tunable MUST live under `split` in `config/kernel_config.default.json`, and
`split.enabled` false MUST restore today's behaviour exactly. The approved default is on, but
epics E1 and E2 of dec-9925ebf1895222f4 MUST ship `split.enabled` false; DK-400e-1, in E3,
returns it to on once the split gate (DK-400d) and the part runs (DK-400e) are both merged. Every
split test MUST set `split.enabled` explicitly. Mid-run splits are built now but dormant: only an
injected test producer reaches them. Full rules: [spec §11][s11].

## Consequences

### Positive

- The live case runs inside the kernel, traceable end to end; the hand split that exit
  criterion 1 rules out is no longer needed.
- Gap counts stay honest both ways: a split, kept-whole or unanswered request is no gap, while a
  single unsupported request or a rejected `jev_none` split records today's gap, same fields.
- Each step uses ADR-053's mechanism (code gates and converts, Jev only judges, the host only
  proposes, a person approves); no model writes, merges, orders or approves parts.
- The bundle check rides an existing Jev batch, so normally it adds no provider call.
- A refused, too-small or abandoned proposal falls back to exactly today's path for its trigger.
- Costs stay bounded: five parts per run, each with a stand-alone budget, so no part starves.
- The split answer's own schema makes the gate refuse anything else with `wrong_kind`, and the
  skills' example answers are checked against the exact contract.
- `split.enabled` false is a complete off switch; the staged rollout keeps main usable.

### Negative

- **Every routed request pays:** accepted bundles are split too, so each semantically routed item
  carries one more Jev question (gates, then Jev, before any generative call): more prompt and
  latency, and one more provider call when a batch passes `jev.max_questions_per_call`.
- **False judgements cost:** a single question judged bundled costs a host operation, a
  `waiting_host` round trip and, if two or more parts come back, a gate. A bundled request judged
  single goes on as today. The 0.8 threshold trades the second error for fewer of the first.
- **Gap counts depend on the gate and on Jev:** a real single-question gap judged bundled waits
  for the gate, and a run cancelled before it records none; a compound request judged single is
  still counted as a gap, as today.
- **More stops:** a bundled request waits for the host's proposal, then the person's answer.
- **Wider contract change:** `HumanQuestion` declares a response schema, and the split gate is
  the first question that accepts one other than `leafcutter.human_answer.v1`.
- **A new contract:** the split record has eight states and many invariants, read by the
  scheduler, `finalize`, the envelope, the report, the gap store and two host skills.
- **Dormant code** on the mid-run path can drift, since only an injected test producer runs it.
- **Naming:** two schema ids keep "goal" though they also serve the other subject kinds.
- **Rollout:** main runs without splitting through E1 and E2; every test sets `split.enabled`.

### Operational

- `split.enabled` false, under `split` in `config/kernel_config.default.json`, turns it off.
- `host.decompose_goal` is the first registry entry admitted by an ADR rather than a ticket
  (`native_registration` accepts `ADR-nnn`); `config/capability_registry.schema.json` gains the
  two decomposition ids. The registry is not a watched package registry and the kernel is not
  shipped to adopters, so the ACs declare `package_surface: false`.
- Both host skills (`kernel/adapters/claude_code/SKILL.md`, `kernel/adapters/codex/SKILL.md`)
  change together and are re-rendered with `python -m kernel install-skill` (DK-400d-1-ii).
- The diagrams of DK-400c-4, DK-400c-5 and DK-400d-5 use the names pinned here.
- Review rejects: Jev asked to write, merge, reword, order or judge parts; keyword bundling
  heuristics; a bundle check adding a provider call in the normal case; a split of a caller's
  `decision_request.v1`; a checked or nested part; a split answer from a non-human actor or a
  `gate_by` from `relayed_by`; a partial split; a `host_only` gap for the decomposition; a mid-run
  producer in the registry or composition root; a split test relying on the shipped default.
- A rule change updates the ADR section and the companion section of the same number together.
- The component doc, the ADR index, and the flow and mock-data notes are updated separately.

## Alternatives

| Alternative | Rejected because |
|---|---|
| Extend `leafcutter.human_answer.v1` with split fields | Its exactly-one-of-three rule has no room for an answer, per-part reviews and a note side by side, so the extension would change a published v1 schema that every question accepts. Every question would then accept a split answer, and the gate a `choice_id` or free text, refused only after validation (`semantic_invalid`, not `wrong_kind`). |
| Reuse `human_answer.v1`'s structured approval, with parts as options | An approval naming no ids declines every proposal, turning "untick every part" into a rejection, which DK-400d-2-i forbids. `edited_criteria` treats an entry without an id as new, which would let the gate add a part (DK-400d-1 forbids it). |
| Let Jev propose, merge or reword the parts | Proposing parts is generation, and ADR-053 §2 forbids asking Jev to invent options or questions. |
| Detect bundling with keyword heuristics | Bundling is a semantic judgement. A keyword rule cannot tell "A and B" inside one question from two questions, so it would split single questions or miss compound ones, with no recorded probability. |
| Use the host's proposal as the only detector | Every routed request would cost a host operation and a `waiting_host` stop, so a single question would no longer reach today's interactions (DK-400a-3). |
| Ask the bundle question in its own Jev call | It would add a provider call to every routed request; riding the intent or routing batch adds none in the normal case. |
| Catch `bundled_accepted` inside the decision capability | Research would need a second detector; the capability would already be invoked for a root that is not to run as one; and the routing result a kept-whole rejection resumes from would not sit in one place on the split record. |
| Run each part as a new run | Each part would get its own envelope, budget and report, so the split could not be followed in one view, and the orchestration would again sit outside the kernel. |
| Run independent parts in parallel | Out of scope (DK-400, SETTLED 5), and parallel parts would lose earlier parts' records as precedent for later ones. |
| Let parts be split again | Nesting would make cost and the gate unbounded. A part that still bundles is reworded, left out or asked again on its own. |
| One shared budget for all parts | The first parts could starve the later ones, so a part could stop where a stand-alone run of its question would have settled. |
| Cut at the first five parts in proposed order | An offered part could wait for a cut part (p3 waits for p6) and never start. Run order keeps the offered set dependency-closed. |
| End a rejected or too-small `ambiguous` split blocked, with a gap | Rejected by the user at the final gate (2026-10-05). An unclear request gets a clarification question today, and a rejected split must not make it worse. |
| Fail the split when the repair attempts run out | A malformed proposal would end a request that today's path would have handled; abandoning the split falls back to that path. |
| Ship `split.enabled` on from the first epic | Rejected by dec-9925ebf1895222f4. Before DK-400d and DK-400e merge, a bundled request on main would reach a gate whose answer or part runs are not built, and daily kernel runs would stall. |
| Keep `split.enabled` off by default for good | The user chose on at the final gate; off would leave the hand split as the normal path. |
| Wire mid-run splits in production now | No shipped capability produces a semantically routed child below the root, so there is nothing to wire. A producer is a new capability and needs its own recorded decision (ADR-055). |

## Open Questions

When this ADR was written, the sources did not settle the points below. On 2026-10-05 the IT PO
settled 1, 2, 3, 5 and 6 in the DK-400 ACs, and the Decision section now states those answers.
Question 4 stays open and is left to the build. The numbers are kept so that citations stay
stable.

1. **The closed split marker.** *Resolved (DK-400c-3; referenced from DK-400a-1, DK-400a-3,
   DK-400d-3 and DK-400d-3-i).* A WorkItem flag `split_checked` (the IT PO default name) is set
   in the route pass that asks the item's bundle question, whatever the answer, checkpointed with
   the item, and false by default. While a proposal is pending, the open split record (`state`
   null) holds the split. After fewer than two parts or an abandoned proposal, no `Decomposition`
   is kept, only a run event and a limitation. The eight product states stand.
2. **Not-covered entries cut by the per-run allowance.** *Resolved (DK-400c-1-i).* DK-400c-1-i is
   right. A split's not-covered entries share one reason naming the limit that bound the offer:
   "beyond the five-part cap" (`split.max_parts`) or "beyond the run's part allowance" (the
   remaining allowance below `split.max_parts`). The mock-data author widens the v6 invariant to
   match.
3. **Request `max_parts`.** *Resolved (DK-400c-1).* It is not lowered:
   `goal_decomposition_request.v1` carries `max_parts` = `split.max_parts`, and the conversion
   applies the allowance deterministically (ADR-053), with the cut entries visible as not
   covered.
4. **Names left to the build:** the per-part budget keys under `split`, the part ceiling of the
   proposal schema, the `HumanQuestion` field that declares the accepted response schema, the
   split gate's question template, and the final name of the `split_checked` flag (the IT PO
   default of Question 1).
5. **The payload a part's request carries.** *Resolved (DK-400e-1).* A part carries what a
   stand-alone run of its question would: `leafcutter.goal_request.v1` with the approved part
   text as its goal and `requested_output_schema` `leafcutter.decision_report.v1` or
   `leafcutter.evidence_bundle.v1`, bound at creation to the approved child capability from the
   run's pinned registry snapshot, and never routed.
6. **Interpretations made in this ADR.** *Resolved: all three confirmed.*
   - a. `leafcutter.decomposition.v1` holds none of the mock dataset's hand-split-only values
     (§4.3; DK-400e-1).
   - b. A rejected `leafcutter.split_answer.v1` has an empty `parts` list (§4.4; DK-400d-3).
   - c. A kept-whole item's output is its one capability's output (§7; DK-400d-3-ii).

## References

- Companion specification: [part 1][spec1] (§1 to §4), [part 2][spec2] (§5 to §11).
- [DK-400 tree](../../acceptance-criteria/decision-kernel/DK-400-split-compound-requests/DK-400.yaml): notes
  SETTLED, DECISIONS AT THE PO GATE, FINAL GATE, WORDING MAP and FOR THE IT PO; the IT PO design of
  DK-400a-1, a-1-i, a-1-ii, a-2, a-3, a-3-ii, a-4, b-1, b-2, c-1, c-1-i, c-1-ii, c-2, c-3, c-4, c-5,
  d-1, d-1-ii, d-2, d-2-i, d-2-ii, d-3, d-3-i, d-3-ii, d-5, e-1, e-2, e-4, f-1, f-2 and f-3.
- Build plan: [dec-9925ebf1895222f4](../../decisions/dec-9925ebf1895222f4.yaml) (run-0e9524762c1b4f85).
- Product truth: mock data and flow (linked in Context); mockups
  [decision-split-approve](../../product-truth/mockups/leafcutter/decision-split-approve.mockup.json),
  [decision-split-progress](../../product-truth/mockups/leafcutter/decision-split-progress.mockup.json).
- [ADR-052](ADR-052-capabilities-replace-agents-prompts-are-compiled.md) §3, [ADR-053](ADR-053-intelligence-selection-deterministic-jev-llm-human.md)
  §2, §3, §5, §6, [ADR-055](ADR-055-capability-registry-starts-empty.md), [ADR-059](ADR-059-decision-store-reviewable-yaml-records-now-graph-later.md),
  [ADR-060](ADR-060-source-of-truth-and-approval-authority.md) §2, §4.
- Superseded tickets: the 2026-10-02 multi-part-goal ticket (branch `docs/kernel-tickets-criteria-reuse`)
  and [TICKET-20261001-KernelCompoundGoalSplit](../../../tickets/00_inbox/TICKET-20261001-KernelCompoundGoalSplit.md).
- [Decision Kernel component](../components/decision-kernel.md); design parts [3](../../analysis/2026-09-30-decision-kernel-design-3-kernel-scheduler.md)
  and [4](../../analysis/2026-09-30-decision-kernel-design-4-jev-and-capabilities.md).
- Code: `kernel/interaction/submissions.py`, `kernel/contracts/payloads.py`,
  `kernel/contracts/interaction.py`, `config/capability_registry.json`, `config/kernel_config.default.json`.

[spec1]: ../../reference/kernel-request-splitting.md
[spec2]: ../../reference/kernel-request-splitting-2-conversion-gate-runs-config.md
[s1]: ../../reference/kernel-request-splitting.md#1-splitting-happens-inside-the-kernel-and-each-step-uses-one-mechanism
[s2]: ../../reference/kernel-request-splitting.md#2-detection-gates-first-then-one-jev-question-that-adds-no-provider-call
[s3]: ../../reference/kernel-request-splitting.md#3-the-host-operation-hostdecompose_goal-and-its-registry-entry
[s4]: ../../reference/kernel-request-splitting.md#4-four-schema-ids
[s41]: ../../reference/kernel-request-splitting.md#41-leafcuttergoal_decomposition_requestv1
[s42]: ../../reference/kernel-request-splitting.md#42-leafcuttergoal_decompositionv1
[s43]: ../../reference/kernel-request-splitting.md#43-leafcutterdecompositionv1-the-split-record
[s44]: ../../reference/kernel-request-splitting.md#44-leafcuttersplit_answerv1-the-persons-answer
[s5]: ../../reference/kernel-request-splitting-2-conversion-gate-runs-config.md#5-conversion-is-total-and-deterministic
[s6]: ../../reference/kernel-request-splitting-2-conversion-gate-runs-config.md#6-the-split-gate-only-a-person-answers
[s7]: ../../reference/kernel-request-splitting-2-conversion-gate-runs-config.md#7-endings-are-keyed-on-the-trigger
[s8]: ../../reference/kernel-request-splitting-2-conversion-gate-runs-config.md#8-bounds-order-and-budgets
[s9]: ../../reference/kernel-request-splitting-2-conversion-gate-runs-config.md#9-what-an-approved-split-produces
[s10]: ../../reference/kernel-request-splitting-2-conversion-gate-runs-config.md#10-gap-accounting-keeps-counts-honest-in-both-directions
[s11]: ../../reference/kernel-request-splitting-2-conversion-gate-runs-config.md#11-configuration-the-off-switch-and-the-staged-rollout
