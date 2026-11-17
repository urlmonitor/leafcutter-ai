---
title: "Reference: Kernel Request Splitting Specification (ADR-067), Part 1 of 2"
description: "The full rules behind ADR-067 sections 1 to 4, read when building or reviewing a split: the mechanism of each step, bundle detection and its triggers, the host.decompose_goal operation and registry entry, and the fields of the four split schemas."
type: reference
status: active
created: 2026-10-05
last_updated: 2026-10-05
components:
  - decision_kernel
related_docs:
  - docs/architecture/adrs/ADR-067-kernel-splits-bundled-requests-into-approved-parts.md
  - docs/reference/kernel-request-splitting-2-conversion-gate-runs-config.md
  - docs/architecture/adrs/ADR-052-capabilities-replace-agents-prompts-are-compiled.md
  - docs/architecture/adrs/ADR-053-intelligence-selection-deterministic-jev-llm-human.md
  - docs/architecture/adrs/ADR-055-capability-registry-starts-empty.md
  - docs/architecture/adrs/ADR-060-source-of-truth-and-approval-authority.md
  - docs/architecture/components/decision-kernel.md
  - docs/acceptance-criteria/decision-kernel/DK-400-split-compound-requests/DK-400.yaml
  - docs/product-truth/mock-data/leafcutter/decisions.mock.json
related_code:
  - config/capability_registry.json
  - config/capability_registry.schema.json
  - kernel/contracts/schema_ids.py
  - kernel/contracts/schema_catalog.py
  - kernel/contracts/interaction.py
  - kernel/contracts/payloads.py
  - kernel/interaction/submissions.py
  - kernel/capabilities/host/generate_options.py
  - kernel/scheduler/routing.py
  - kernel/scheduler/nodes_route.py
  - kernel/intent/classify.py
---

# Kernel Request Splitting Specification, Part 1 of 2

The full rules behind [ADR-067](../architecture/adrs/ADR-067-kernel-splits-bundled-requests-into-approved-parts.md)
§1 to §4: the mechanism of each step, detection, the host operation and the four schemas.
[Part 2](kernel-request-splitting-2-conversion-gate-runs-config.md) holds §5 to §11: conversion,
the split gate, endings, bounds and budgets, outputs, gap accounting and configuration.

Section numbers and titles match the ADR's Decision section, so a "§" number means the same
section in the ADR and in this specification. Every MUST here is part of ADR-067's decision. The
ADR states each decision in short; this document states it in full. The two must not disagree,
so a change to either is a change to ADR-067 and updates both.

## 1. Splitting happens inside the kernel, and each step uses one mechanism

- A request that bundles several separate questions MUST be split inside the kernel run, not by
  hand outside it. The kernel MUST NOT record a split made outside it. Hand splits are history
  only (DK-400, decision Q4).
- A split is generic. Its subject kind is `goal`, `research_request` or `decision_question`, and
  it is found at `routing` or `mid_run` (DK-400, SETTLED 3).
- The steps follow ADR-053's order. Each step MUST use only the mechanism in this table:

| Step | Mechanism | What it does |
|---|---|---|
| Gates | Deterministic | Skip the check wherever splitting cannot apply (§2) |
| "One question or several?" | Jev | One bounded judgement, template `kernel.split.bundled` (§2) |
| Proposal | LLM, as host | `host.decompose_goal` proposes the parts (§3) |
| Conversion | Deterministic | Validate, quote-check, release, count and cut (§5) |
| Split gate | Human | Approve, reword, leave out or reject (§6) |
| Part runs | Deterministic scheduling, then each part's own capability | One part at a time, in dependency order (§8) |

- Jev MUST NOT write, merge, reword, order or judge parts. Its only split question is whether a
  subject is bundled (ADR-053 §2). Every conversion check MUST be deterministic code (ADR-053
  §5).

## 2. Detection: gates first, then one Jev question that adds no provider call

**Gates.** Deterministic gates MUST run first. When any gate fails, the item MUST skip the
bundle check entirely (DK-400a-1):

- `split.enabled` is true;
- host operations are enabled, and the host-operation budget can fund one decomposition;
- the item is routed semantically: request kind `capability`, not a fixed, continued or retried
  binding, not a deterministic `no_match` with no eligible candidate, and not a part of an
  approved split;
- its payload is not a caller-supplied `leafcutter.decision_request.v1`. This is an exact check
  on the item's input payload schema id, made before any Jev question is assembled
  (DK-400a-3-ii);
- the run's remaining part allowance (`split.max_parts_per_run`) is at least 2;
- the resolved answer kind is decision or evidence, or is unresolved. Roots whose answer kind is
  ideas, change or out_of_domain are never split;
- the item's `split_checked` flag is not set. The flag MUST be set in the route pass that asks
  the item's bundle question, whatever the answer, and checkpointed with the item; it defaults to
  false. An item is therefore never checked twice, not on a continuation or retry either
  (DK-400a-3, DK-400c-3).

**The Jev question.**

- The judgement MUST be one literal Jev `noul` per checked item, with the versioned template id
  `kernel.split.bundled`.
- It MUST ride the item's first existing Jev batch: the intent batch for a root without an
  explicit output contract, otherwise the routing batch.
- It MUST NOT add a Jev provider request. A checked run makes as many provider calls as the same
  run with `split.enabled` false, unless the added question pushes a batch past
  `jev.max_questions_per_call`.
- A subject MUST count as bundled only at or above `split.bundle_threshold` (default 0.8, biased
  against false positives). Below it, the item MUST go on exactly as today.
- The probability and the threshold MUST be recorded in the routing assessment, in a run event
  and in the trace. An uncertain answer is visible but never starts a split (ADR-053 §6).
- Code MUST NOT decide bundling by keyword heuristics. The proposal's fewer-than-two rule (§7)
  is the backstop for a false positive.

**Where each trigger is caught.**

| Trigger | Caught when | What the split replaces |
|---|---|---|
| `jev_none` | Routing on the root ends `no_match` with reason `jev_none`, and the subject is bundled | Today's gap recording and the host fallback rebinding of `host.fallback_on_no_match`. Split detection takes precedence over the `no_match` fallback. The gap decision waits for the split's outcome (§10) |
| `ambiguous` | The root's intent or routing assessment ends `insufficient_context` (the needs-context answer, or an answer below the configured probability or confidence), and the subject is bundled | Today's clarification question at detection. The top candidate is never bound, and no ambiguous gap is recorded at detection (DK-400a-1-i) |
| `bundled_accepted` | Routing on the root (depth 0) selected one capability, and the subject is bundled. It is caught in the same route pass, never inside the capability (DK-400a-2) | The selected capability is not invoked for the root while the split is open. No options request, criteria proposal, precedent search or assessment runs for the whole subject |
| none (`mid_run`) | A non-root work item that is routed semantically passes the gates (DK-400b-2) | The item waits. It is neither routed again nor executed as one, and its parent keeps waiting on it |

- For `bundled_accepted` and `mid_run`, the routing result that selected the capability MUST be
  kept on the split record as `kept_routing`: the RoutingAssessment id (or the intent-bound
  binding), the capability id and the version. It MUST be the only source a kept-whole ending
  resumes from. Such an ending MUST NOT route again or ask a second routing Jev question.
- A root resolved to research is caught the same way, with subject kind `research_request`.
- Kernel-internal typed children MUST NOT be checked: evidence requests with planned needs,
  options, synthesis, human and retrieval requests (DK-400b-2).

**The split record at detection.**

- The split record MUST be created at detection, with id `dcp-` plus 16 hex derived from the
  owning work item's id. It MUST be checkpointed before the run returns `waiting_host` with the
  pending operation `decompose_goal`. A re-executed node or a resumed run MUST NOT create a
  second split for the same item.
- `subject_text` MUST be the subject as submitted, with each run of whitespace collapsed to one
  space and nothing else changed. One shared normalisation helper MUST serve this field and the
  quote check (§5). A mid-run split's subject is the work item's own question, never the root
  goal.
- `subject_kind` MUST be derived deterministically: `research_request` when the item's
  requested or classified output is `leafcutter.evidence_bundle.v1`; `decision_question` for a
  mid-run item whose request asks a decision question; `goal` otherwise.

## 3. The host operation `host.decompose_goal` and its registry entry

- Proposing parts MUST be host (LLM) work done by the new host operation `host.decompose_goal`.
  It follows the pattern of `host.generate_options`, `host.synthesize` and
  `host.formulate_question`: a deterministically compiled and fingerprinted `HostWorkRequest`
  (ADR-052 §3) with operation `decompose_goal`.
- The packet MUST allow only the operations `read_supplied_artifacts` and `propose_split`, and
  MUST forbid the standard forbidden operations. It MUST NOT grant repository access:
  `permissions_required` is empty, and the input artifact carries only the subject text, its
  kind and the proposal rules.
- The host skills MUST NOT carry operation-specific text for it. The host follows the packet's
  goal, output requirements and output JSON schema, as for every host operation (DK-400d-1-ii).
- The decomposition MUST be one host operation charged to the root's budget. It MUST NOT record a
  `host_only` gap observation (DK-400a-1-ii).
- The registry entry in `config/capability_registry.json` MUST read:

| Field | Value |
|---|---|
| `id` | `host.decompose_goal` |
| `execution_mode` | `host_handoff` |
| `routing` | `fixed` (never offered to Jev routing) |
| `request_kinds` | `["capability"]` |
| `operations` | `["decompose_goal"]` |
| `accepts_schemas` | `["leafcutter.goal_decomposition_request.v1"]` |
| `produces_schemas` | `["leafcutter.goal_decomposition.v1"]` |
| `side_effect_class` | `none` |
| `permissions_required` | `[]` |
| `admission` | `native_registration`, with `decision_ref` `ADR-067` |

- ADR-067 is the recorded decision that ADR-055 requires for the entry. The entry's binding
  MUST be registered at the composition root.
- `host.decompose_goal` MUST NOT be chosen as a `no_match` fallback, and MUST NOT be eligible
  for any other request.
- The child capabilities a proposal names MUST come from the set allowed for the subject kind
  (DK-400b-1):

| Subject kind | Allowed child capabilities |
|---|---|
| `goal` | `decision` or `research` |
| `research_request` | `research` |
| `decision_question` | `decision` |

- A part that names a capability outside that set MUST refuse the host's answer with a message
  naming each offending part id. The host can repair it within `host.max_repair_attempts`. The
  kernel MUST NOT re-label a part's capability itself.

## 4. Four schema ids

Every id below MUST be registered in `SCHEMA_CATALOG` and in `KNOWN_SCHEMA_IDS`
(`kernel/contracts/schema_ids.py`). Each MUST be exported as
`kernel/schemas/<id>.schema.json`, with valid and invalid fixtures, and the existing catalog
test MUST keep them in sync. The ids serve all three subject kinds. The word "goal" in two of
them is historical, from the superseded ticket, and there MUST NOT be per-kind variants. Where an
AC names an id differently, ADR-067 wins (DK-400c-1).

| Schema id | What it carries | Sent by | Read by |
|---|---|---|---|
| `leafcutter.goal_decomposition_request.v1` | The request of `decompose_goal` | Kernel | Host |
| `leafcutter.goal_decomposition.v1` | The host's proposal | Host | Conversion (§5) |
| `leafcutter.split_answer.v1` | The person's answer at the split gate | Person, relayed by the host | Split gate (§6) |
| `leafcutter.decomposition.v1` | The split record, and the output of a split item | Kernel | Envelope, parent item, report |

### 4.1 `leafcutter.goal_decomposition_request.v1`

Fields: `split_id`, `subject_kind`, `subject_text`, `allowed_capabilities` (a list drawn from
`decision` and `research`, per §3), `min_parts` (2) and `max_parts` (`split.max_parts`). The
request MUST NOT lower `max_parts` by the run's remaining allowance; the conversion applies the
allowance (§5).

### 4.2 `leafcutter.goal_decomposition.v1`

Fields: `parts`, a list of `{id, text, covers, depends_on: [part id], child_capability:
decision | research}`, and `one_question_rewording` (string or null).

- `covers` is the span of the subject that the part quotes.
- The schema MUST accept 0 parts, up to a configured ceiling above `split.max_parts`. More than
  five parts is a legal proposal, and the conversion cuts it (§5, DK-400c-1-i).
- `one_question_rewording` is the host's suggestion for asking the request as one bounded
  question. It is shown as a hint after a `jev_none` rejection and is never run (DK-400f-3).

### 4.3 `leafcutter.decomposition.v1`: the split record

The split record MUST carry these fields, which are the shapes delivered by DK-400a-1,
DK-400c-1, DK-400d-1 and DK-400e-1:

- `id`, `run_id`, `work_item_id`, `subject_kind`, `subject_text`, `found_at`,
  `work_item_depth`, `trigger`, `kept_routing` and `state`;
- `parts[]`: `{id, text, proposed_text, covers, depends_on, child_capability, review, outcome,
  settled_order, run_id, decision_id, result_ref, findings, stop_reason, waited_for}`;
- `dropped[]`: `{text, covers, reason}`, the set-aside proposals;
- `not_covered[]`: `{id, text, covers, reason}`, the proposals beyond the cut;
- `one_question_rewording`, `gate_answer`, `gate_by`, `gate_at`, `gate_note`,
  `whole_decision_id`, `capability_gap_recorded` and `report_lines`.

Rules for the record:

- `state` MUST be null while the host's proposal is awaited. After that it MUST be one of the
  eight product states of mock-data v6: `proposed`, `approved`, `in_progress`, `completed`,
  `ended_partial`, `rejected`, `rejected_clarify` and `rejected_kept_whole`.
- `review` MUST be one of `proposed`, `kept`, `edited`, `left_out` and `rejected`. `outcome`
  MUST be one of `not_run`, `pending`, `decided`, `answered` and `not_settled`. `stop_reason`
  MUST be one of `budget_stop`, `blocked`, `capability_gap` and `cancelled`.
- The values that the mock dataset holds only for the hand split MUST NOT be in the kernel
  schema: `proposed_by` `claude_code`, the outcome `settled_by_human` and the part field
  `human_answer`.
- The record MUST satisfy the invariants of the v6 `Decomposition` entity that apply to a split
  the kernel offered. Among them: 2 to 5 parts with unique ids once proposed; every `covers` a
  verbatim span of `subject_text`; `depends_on` acyclic and naming only part ids; `found_at`
  `routing` if and only if depth 0 if and only if a trigger is set; `gate_by` matching
  `^human(:<name>)?$` if and only if `gate_answer` is set.

### 4.4 `leafcutter.split_answer.v1`: the person's answer

**Decision.** The split gate MUST accept a new schema, `leafcutter.split_answer.v1`.
`leafcutter.human_answer.v1` MUST NOT be extended to carry the split answer. The rejected
extension is kept under ADR-067's Alternatives.

**Why.**

1. `human_answer.v1` takes exactly one of three modes. A split answer needs its own fourth
   shape: an answer, per-part reviews and a note side by side. A note next to the answer
   collides with the free-text mode. Extending the schema would change the meaning of a
   published v1 schema, its exported file and its fixtures, which every existing question
   accepts.
2. With an extension, every existing question would structurally accept a split answer, and the
   split gate would structurally accept a `choice_id` or free text. Refusing those would need a
   new per-question flag and more checks in `_answer_problem`. The refusal would also arrive as
   `semantic_invalid` instead of `wrong_kind`. DK-400d-1 requires the registered schema itself to
   refuse unknown fields, and with an extension, the option and criterion fields would be known
   fields at the split gate.
3. DK-400d-1-ii validates each host skill's example answer against the split-answer schema. A
   dedicated schema makes that test mean something: a plain free-text answer does not pass.

**Fields.** The fields of a part entry mirror the split record's `parts[]`.

| Field | Type | Rule |
|---|---|---|
| `answer` | `approved` or `rejected` | Required |
| `parts` | list of `{id, review, text}` | For `approved`: exactly one entry per offered part. `review` is `kept`, `edited` or `left_out`. `text` (the person's words, 1 to 4000 characters) is present if and only if `review` is `edited`. For `rejected`: the list MUST be empty, and the kernel records every part as rejected |
| `note` | string or null | Stored word for word, with only leading and trailing whitespace trimmed, within the configured input limits |

- The schema MUST NOT have any other field. Unknown fields MUST be refused. No field can add a
  part or change `depends_on` or `child_capability` (DK-400, decision Q7).
- The semantic check MUST read the offered part ids from the pending gate, never from the answer.
  It MUST refuse: an id that is not an offered part; an offered part listed twice or not at all;
  any set-aside or not-covered entry; an approval that leaves out every part. Such an approval
  MUST NOT be turned into a rejection (DK-400d-2-i).
- The submission is today's `InteractionSubmission`, with `response_schema_id`
  `leafcutter.split_answer.v1`, `actor` `{kind: human, id: human:<name>}` and `relayed_by` set to
  the relaying host's id.

**What changes in the submission check.**

- A `HumanQuestion` MUST declare the response schema it accepts. The default MUST be
  `leafcutter.human_answer.v1`, so every existing question and every persisted checkpoint keeps
  its meaning. The field name is left to the build.
- `_expectation` in `kernel/interaction/submissions.py` MUST return the declared schema for a
  `HumanQuestion`. The actor kind for every `HumanQuestion` MUST stay `human`, so the human-only
  rule of ADR-060 covers the split gate unchanged.
- `_answer_problem` MUST keep applying to `human_answer.v1` answers only.
