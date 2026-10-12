---
title: "Reference: Kernel Request Splitting Specification (ADR-067), Part 2 of 2"
description: "The full rules behind ADR-067 sections 5 to 11, read when building or reviewing a split: proposal conversion, the split gate, endings by trigger, bounds, order and budgets, the split output, gap accounting, and configuration with the staged rollout."
type: reference
status: active
created: 2026-10-05
last_updated: 2026-10-05
components:
  - decision_kernel
related_docs:
  - docs/architecture/adrs/ADR-067-kernel-splits-bundled-requests-into-approved-parts.md
  - docs/reference/kernel-request-splitting.md
  - docs/architecture/adrs/ADR-052-capabilities-replace-agents-prompts-are-compiled.md
  - docs/architecture/adrs/ADR-053-intelligence-selection-deterministic-jev-llm-human.md
  - docs/architecture/adrs/ADR-055-capability-registry-starts-empty.md
  - docs/architecture/adrs/ADR-060-source-of-truth-and-approval-authority.md
  - docs/architecture/components/decision-kernel.md
  - docs/acceptance-criteria/decision-kernel/DK-400-split-compound-requests/DK-400.yaml
  - docs/product-truth/mock-data/leafcutter/decisions.mock.json
  - docs/decisions/dec-9925ebf1895222f4.yaml
related_code:
  - config/kernel_config.default.json
  - config/kernel_config.schema.json
  - kernel/config.py
  - kernel/interaction/submissions.py
  - kernel/scheduler/nodes_gaps.py
  - kernel/intent/questions.py
  - kernel/adapters/claude_code/SKILL.md
  - kernel/adapters/codex/SKILL.md
---

# Kernel Request Splitting Specification, Part 2 of 2

The full rules behind [ADR-067](../architecture/adrs/ADR-067-kernel-splits-bundled-requests-into-approved-parts.md)
§5 to §11: conversion, the split gate, endings, bounds and budgets, outputs, gap accounting and
configuration. [Part 1](kernel-request-splitting.md) holds §1 to §4: the mechanism of each step,
detection, the host operation and the four schemas.

Section numbers and titles match the ADR's Decision section, so a "§" number means the same
section in the ADR and in this specification. Every MUST here is part of ADR-067's decision. The
ADR states each decision in short; this document states it in full. The two must not disagree,
so a change to either is a change to ADR-067 and updates both.

## 5. Conversion is total and deterministic

The host's answer MUST be converted in this fixed order (DK-400c-1):

1. **Schema validation** against `leafcutter.goal_decomposition.v1`.
2. **Dependency validation** over all proposed ids, before the quote check (DK-400c-1-ii). A cycle,
   including a self-dependency, refuses the answer with a message naming the cycle in order, with
   the first id repeated (`p1 -> p2 -> p1`). A dependency on an id the proposal does not contain
   refuses it with that id named. Duplicate part ids are refused the same way.
3. **Allowed-capability check** (§3, DK-400b-1).
4. **Quote check and set-aside** (DK-400c-2, DK-400c-2-i). Both `subject_text` and the quote are
   normalised by collapsing every run of whitespace (spaces, tabs, line breaks) to one space and
   trimming the ends. They are then compared as an exact, case-sensitive substring. Nothing else
   is normalised. A proposal whose quote fails moves to `dropped[]` with a reason from a template
   by subject kind ("quote not found in the goal" for a goal). It gets no part id, no gate answer
   can name it, it is never run, and it counts for nothing in the part count or the per-run
   allowance.
5. **Release of dependencies on set-aside proposals.** A kept part that waited for a set-aside
   proposal MUST have that dependency released. The release MUST be shown beside the part at the
   gate and recorded as the run event `split.dependency_released`. No part is ever left waiting
   for something that cannot settle.
6. **Part count**, taken after the set-aside and before the cut. Fewer than 2 parts means no
   split (§7, DK-400c-3).
7. **The five-part cut and the per-run allowance** (DK-400c-1-i). The offered parts MUST be the
   first parts of the run order (the shared ordering function of §8), up to `split.max_parts`, so
   the offered set is always dependency-closed. The remaining part allowance caps the offer the
   same way. The others become `not_covered[]` entries in proposed order, each with its id, text
   and quote and no `depends_on`. All not-covered entries of a split MUST share one reason naming
   the limit that bound the offer: "beyond the five-part cap" when `split.max_parts` bound it, or
   "beyond the run's part allowance" when the run's remaining allowance, below
   `split.max_parts`, bound it. When fewer than 2 parts fit the allowance, there is no split (§7).
8. **Gate.** The state becomes `proposed`, the split gate opens, and the run is `waiting_human`.

Rules for the conversion:

- Conversion MUST be total. Any failure refuses the answer or abandons the split. It MUST NOT
  yield a partial split.
- A refused answer leaves run state unchanged, and the `decompose_goal` interaction stays
  pending. The host can send a corrected proposal under the existing repair rule:
  `host.max_repair_attempts`, with the packet returned in `error.details.pending_interaction`.
- When the repair attempts run out, the split MUST be abandoned, never failed. No gate opens and
  no part exists. The subject goes on by its trigger, exactly as for fewer than two parts (§7).
  The run's limitations name the refused proposal and why. A bad proposal is never worse than
  today.
- The kernel MUST NOT request a second decomposition for the same item.

## 6. The split gate: only a person answers

- The split gate MUST be a persisted `HumanQuestion` (run status `waiting_human`), built
  deterministically from the split record. It shows the subject verbatim, then each offered part
  in proposed order with its id, text, quote, dependencies (with any release) and child
  capability. Set-aside proposals and not-covered parts are shown read-only with their reasons.
  The wording comes from templates. When parts were cut, it MUST name the limit that bound the
  offer (at the five-part cap, that the request holds more than five parts) and say that the
  not-covered ones can be asked again as a request of their own.
- Only a person answers the gate (ADR-060). `gate_by` MUST be the submission's human actor id;
  `gate_at` MUST be the kernel runtime clock at acceptance, in UTC. `relayed_by` MUST be kept
  separately and MUST NOT become `gate_by`. Jev, a host and the kernel MUST NOT answer the gate.
  The `/leafcutter` and `$leafcutter` skills only show the gate and relay the person's answer
  unchanged; they never choose a default (DK-400d-1-ii).
- At the gate a person can keep, reword or leave out each offered part, and can combine rewording
  and leaving out in one approval, or reject the split (DK-400d-1, DK-400d-2):
  - An edited part keeps `covers` unchanged and keeps the host's words in `proposed_text`. It
    runs with the person's text as its question. The person's text is not quote-checked, so it
    can carry a set-aside proposal's question; that proposal stays in `dropped[]`
    (DK-400d-2-ii).
  - A left-out part gets review `left_out` and outcome `not_run`, and never gets a work item. A
    kept part's dependency on it is released and recorded as a run event.
  - A person MUST NOT be able to add a part or change a part's dependencies or capability at the
    gate (DK-400, decision Q7). A missing question is added by rewording a part, or asked again
    as its own request.
- A refused answer MUST exit with code 3 and leave the run at the same state revision, with the
  gate still pending. The host shows the kernel's message and asks again. It MUST NOT repair a
  person's answer; the one-repair rule is for host work only.
- A duplicate identical answer returns the current envelope. A restart just before or just after
  the submission ledger write MUST neither lose nor duplicate the answer or any part.
- On approval, the parts MUST be released to the scheduler in the same integrate pass. No part
  work item exists before the answer is accepted.
- On rejection, the kernel MUST record in one step: `gate_answer` `rejected`, `gate_by`,
  `gate_at`, the note word for word, and every part with review `rejected` and outcome
  `not_run`. No part work item is ever created (DK-400d-3).

## 7. Endings are keyed on the trigger

How the work goes on after a rejection, after a proposal with fewer than two parts, or after the
repair attempts run out MUST be chosen deterministically from the split record's `trigger` and
`found_at`, never by a model (DK-400c-3, DK-400d-3, DK-400a-1-i):

| Trigger | Rejected at the gate | Fewer than two parts, or repairs exhausted |
|---|---|---|
| `jev_none` | State `rejected`. The run ends `blocked` and records today's `unsupported` gap. | Today's gap is recorded, and the run ends `blocked` with today's blocked report. |
| `ambiguous` | State `rejected_clarify`. Today's clarification question opens, and the run is `waiting_human`. | Today's clarification question opens, and the run is `waiting_human`. |
| `bundled_accepted` | State `rejected_kept_whole`. The subject resumes from `kept_routing` as one decision from the precedent step. | The subject goes ahead from `kept_routing` as one decision. |
| none (`mid_run`) | State `rejected_kept_whole`. The item resumes from its own routing result as one decision or research step. | The item goes ahead as one decision or research step. |

- The `ambiguous` fallback MUST be today's `insufficient_context` path, unchanged. With
  `routing.on_insufficient_context` set to `human`, it opens today's clarification question,
  with the same template and choices as today. Follow-ups count against
  `intent.max_clarifications`. Today's ambiguous gap is recorded only if the request ends
  unresolved, because the person cannot be asked or the follow-up limit is reached, and only
  then does the run end `blocked`.
- A request that fell back to the clarification question MUST NOT be offered a second split in
  the same run. The item's `split_checked` flag stays set, so the bundle check is skipped for it,
  even after the person's answer changes its effective goal, and even when that answer itself
  bundles several questions. The person can start a new run to get a split.
- A kept-whole subject's output is what its one capability produces, exactly as in the run with
  `split.enabled` false. When that one decision's record is staged, `whole_decision_id` names it.
- After a proposal with fewer than two parts, or an abandoned one, the split record MUST NOT be
  kept as a `Decomposition`: it never reaches the envelope, the output or `report.md`, and there
  is no split section. A run event and a limitation naming why keep the trace, and the item's
  `split_checked` flag stays set (DK-400c-3).
- A caller-supplied `leafcutter.decision_request.v1` MUST NOT be checked for bundling or split.
  It goes ahead as the one decision the caller named, with its question, options and criteria
  unchanged (DK-400a-3-ii).
- A rejected split's report MUST keep one plain line saying that a split was offered and
  rejected, by whom, and how the work went on (DK-400f-3).

## 8. Bounds, order and budgets

- **Bounds.** A split offers 2 to 5 parts: `split.max_parts` defaults to 5, and the config schema
  MUST bound it to 2 to 5, so the product rule cannot be configured away. A run offers at most
  `split.max_parts_per_run` parts (default 5), counting every part offered by every split in the
  run.
- **One at a time.** Approved parts MUST run strictly one at a time, whatever
  `limits.max_concurrent_native` allows. Parallel children are out of scope (DK-400, SETTLED 5).
- **Order.** One shared ordering function MUST order the parts: Kahn's order over `depends_on`,
  taking the free part with the lowest proposed index first. The five-part cut (§5) MUST use the
  same function. A part starts only after every part it depends on has settled, and
  `settled_order` counts 1 to n without gaps (DK-400e-1).
- **Same run.** Each part MUST run as a work item of the same run, a child of the split item. It
  MUST NOT run as a new run.
- **Part payload.** Each part's work item MUST carry what a stand-alone run of its question
  would: a `leafcutter.goal_request.v1` payload whose goal is the part's text as approved,
  request kind `capability`, and `requested_output_schema` `leafcutter.decision_report.v1` for a
  decision part or `leafcutter.evidence_bundle.v1` for a research part. It MUST NOT be a typed
  `leafcutter.decision_request.v1` or `leafcutter.research_request.v1` (DK-400e-1).
- **No nesting.** Each part's binding MUST be pinned at creation to its approved child
  capability, from the run's pinned registry snapshot. A part is never routed, intent-classified
  or checked for bundling. Splits do not nest (depth 1).
  A part that still bundles questions is reworded or left out at the gate, or asked again as its
  own request (DK-400b-2).
- **Decision questions.** The parts of a `decision_question` subject MUST run as decision
  children only (§3).
- **Precedent.** A later decided part receives the records of the parts decided before it as
  precedent evidence, which stays evidence, never authority (ADR-060 §4).
- **Per-part budgets.** Each part MUST run with its own allowance, equal to what a stand-alone run
  of its question would get from config: Jev calls, host operations, work items, active seconds,
  and depth headroom measured from the part's own work item. The allowance is configurable under
  `split`.
  - A part's unspent allowance MUST NOT be lent to other parts.
  - The root's spend before the gate (routing, decomposition) MUST be charged to the root.
  - A run-level guard MUST NOT stop a part that a stand-alone run of its question would have
    passed.
  - A run's total spend therefore stays bounded by `split.max_parts_per_run` times the per-part
    allowance, plus the root's own.
- **A part that does not settle.** The part becomes `not_settled`, with `stop_reason` mapped
  deterministically from how its work ended. Its dependants, transitively, become `not_run`,
  each with `waited_for` naming the part it waited for. Independent parts carry on. The run
  ends `partial`, never `completed`, and the split ends `ended_partial` (DK-400e-4).
- **Restart and cancellation.** A restart between parts MUST NOT re-run a settled part or skip a
  pending one. Cancelling MUST stop at the next safe point, and the running part ends
  `not_settled` with `stop_reason` `cancelled`.

## 9. What an approved split produces

- A split item's terminal status MUST be derived from its parts: `completed` if every part not
  left out settled, `partial` otherwise.
- The root-completion rule of `finalize` MUST be extended for a split root only. Its output MUST
  be the split record under `leafcutter.decomposition.v1`. The envelope's `decision_ids` MUST list
  every decided part's record. No `decision_report.v1` is produced for the bundle as a whole
  (DK-400e-1).
- A split item below the root MUST report one child outcome to its parent, with its status set by
  the same rule and the split record as its result. A parent that cannot use that result MUST
  treat it as a failed required child, never as a fabricated single answer (DK-400b-2).
- Each decided part MUST stage its own record through the existing staging gate, which accepts
  only a decision resolved and approved by a person (ADR-060 §2). The record's question is the
  part's text as approved. The link from record to split, `Decision.split_part`, MUST be derived
  from `parts[].decision_id`. `config/decision_record.schema.json` and the published record shape
  MUST NOT change (ADR-059, DK-400e-2).
- The envelopes of run, resume and status MUST carry a split progress block whenever a split
  exists, and `status` MUST show it without a Jev key and without resuming the run (DK-400f-1).
- The report lines MUST be template text, never LLM output. They MUST be stored on the split
  record (`report_lines`), so the envelope, `report.md` and the progress view never disagree
  (DK-400f-2).

## 10. Gap accounting keeps counts honest in both directions

Gap accounting for the split's subject MUST be decided when the split's outcome is known, never
at detection (DK-400a-1-ii):

| Outcome | Gap for the request itself |
|---|---|
| Approved | None |
| `jev_none`: rejected, fewer than two parts, or abandoned | Exactly today's `unsupported` observation (the same `gap_key`, `gap_type` and fields, `fallback_outcome` `blocked`); `capability_gap_recorded` true |
| `ambiguous`: rejected, fewer than two parts, or abandoned | None while today's clarification question is open. Today's ambiguous observation only if the clarification ends unresolved |
| `bundled_accepted` or `mid_run` | Never |
| Run cancelled before the gate answer | None |

- Observations from a part's own work (its research, options or synthesis host operations, or a
  `no_match` of a part's child) MUST be recorded exactly as a stand-alone run of that part would
  record them. They are attributed to the part's request, never to the split's subject.
- A single question that no capability can meet MUST produce today's gap observation unchanged
  (`gap_key`, `gap_type`, `normalized_need`, `fallback_outcome`), so occurrence counts across
  runs stay comparable before and after this feature (DK-400a-4).

## 11. Configuration, the off switch and the staged rollout

- **Configuration.** Every new tunable MUST live under a `split` section of
  `config/kernel_config.default.json`: `split.enabled`, `split.bundle_threshold` (0.8),
  `split.max_parts` (5, bounded to 2 to 5), `split.max_parts_per_run` (5) and the per-part
  budget keys of §8. `config/kernel_config.schema.json` MUST be regenerated from the config model
  and kept equal by the existing config test. Node code MUST NOT hard-code a threshold or bound,
  and every value used MUST be recorded in the trace.
- **Off switch.** `split.enabled` false MUST restore today's behaviour exactly on the same
  inputs: no bundle question in any Jev batch, no split record, and today's gap, fallback,
  clarification and report.
- **Default.** The approved default of `split.enabled` is on (the user's final-gate choice).
- **Staged rollout.** Decision dec-9925ebf1895222f4 builds DK-400 in three dependency-checked
  epics, one PR each, merged one at a time with the user's confirmation:
  - E1: DK-400a and DK-400c, without DK-400c-5;
  - E2: DK-400b and DK-400d, without DK-400d-5, plus DK-400c-5;
  - E3: DK-400e, DK-400f and DK-400d-5.

  E1 and E2 MUST ship `split.enabled` false, both in `config/kernel_config.default.json` and as
  the config model's default. Splitting stays off on main until the split gate (DK-400d) and the
  part runs (DK-400e) are both merged, so main stays usable for daily kernel runs between merges.
  DK-400e-1, in E3, MUST return both to on, and `test_shipped_split_default_is_on` pins it.
- **Tests.** Every split test MUST enable splitting explicitly through a config override and
  MUST NOT rely on the shipped default. A test asserting that no split starts MUST run with
  splitting on, or it passes for the wrong reason.
- **Mid-run splits, built dormant.** The mid-run path MUST be built now and ship with no
  production producer wired. No capability in today's kernel proposes a semantically routed
  capability child below the root. The path MUST be exercised only through an injected test
  producer, registered in test code under `tests/kernel/`, never in
  `config/capability_registry.json` or the composition root. `split.enabled` alone MUST NOT
  activate it: with the shipped registry, no run starts a `mid_run` split (DK-400b-2).
- **Telemetry.** The split lifecycle MUST emit run and tracer events (`split.started`, then the
  later `split.*` events) carrying the split id, the trigger and the subject kind. Subject text
  in telemetry MUST obey the `data_policy` redaction rules.
- **Errors.** Split code MUST follow the project error-handling policy: catch specific
  exceptions, log at WARNING with the run, work item and split ids, and never swallow a failure
  silently.
