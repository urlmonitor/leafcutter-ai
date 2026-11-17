---
title: "How to answer the decision kernel's questions"
description: "Answer the two questions a decision asks you, the approval question and the ranked-choice question, with answers the kernel accepts as written, and know what each answer does."
type: how-to
status: active
created: 2026-10-10
last_updated: 2026-10-10
components:
  - decision_kernel
related_docs:
  - docs/how-to/run-the-decision-kernel.md
  - docs/how-to/file-and-reuse-decisions-with-the-kernel.md
  - docs/architecture/diagrams/c3-024-decision-kernel-flows-forming-round.md
  - docs/architecture/diagrams/c3-025-decision-kernel-flows-decision-states.md
  - docs/architecture/adrs/ADR-060-source-of-truth-and-approval-authority.md
related_code:
  - kernel/schemas/leafcutter.human_answer.v1.schema.json
  - kernel/interaction/submissions.py
  - kernel/capabilities/decision/approvals.py
  - kernel/capabilities/decision/requests.py
---

# How to answer the decision kernel's questions

A decision run stops twice to ask you something: whether to approve what it proposed, and which ranked option to choose. This guide shows each answer you can give, so the decision ends the way you intend.

## Prerequisites

- A run paused with `status` `waiting_human` ([How to run the decision kernel](run-the-decision-kernel.md), Step 4).
- The run's `run_id`, the interaction `id` and its `state_revision` from `pending_interaction`.
- In Claude Code the `/leafcutter` skill asks you the question and writes the answer file for you. Use the answers below when you resume by hand.

## Steps

### Step 1 — Tell which question you were asked

Read `pending_interaction.question`. The approval question starts "For the decision '...', approve these generated proposals?" and lists `Proposed options:` and `Proposed criteria:` with an `[id]` for each. The ranked-choice question lists the options as `#1, #2, ...`, each with its criteria in words and the evidence it cites.

### Step 2 — Answer the approval question

Every answer is the `response` object of the resume file described in [Step 5 of the run guide](run-the-decision-kernel.md). Pick one of the four answers.

Approve everything as proposed:

```json
{"choice_id": "approve"}
```

Approve a subset. Ids you list are approved and every other pending proposal of that kind is declined. Use ids from the question:

```json
{"approved_criterion_ids": ["crit.reversible"], "approved_option_ids": ["opt.atomic"]}
```

Reword a criterion, or add one of your own. An entry with the id of a proposal rewords it; an entry without an id is new. `priority` is `required` (blocks resolution) or `supporting` (weighs only in the ranking) and defaults to `required`:

```json
{"edited_criteria": [
  {"id": "crit.reversible", "question": "Can the change be undone within one release?", "priority": "required"},
  {"question": "Does it keep the public CLI unchanged?", "priority": "supporting"}
]}
```

Add an option of your own. It becomes an approved, human-supplied option and is researched like the others:

```json
{"added_options": [{"title": "Encapsulated subgraph", "description": "Wrap the capability in a subgraph with its own state."}]}
```

Three rules apply to these answers:

- `edited_criteria` replaces the whole proposed criteria set. A pending criterion you do not list is declined, so list every criterion you want to keep.
- `approved_criterion_ids` and `edited_criteria` are alternatives. The kernel refuses an answer that carries both (exit 3, `schema_invalid`, "approved_criterion_ids and edited_criteria are alternatives"), so send one of them.
- Free text alone at this question is only recorded. It is never turned into criteria, and the proposals stay unapproved. To approve with a condition, send `{"choice_id": "approve", "free_text": "<your condition>"}`.

### Step 3 — Answer the ranked-choice question

The kernel orders the options by required criteria passed, then the required mean, then the supporting mean. Pick one of three answers.

Choose an option. Use the option id from the question. The decision resolves with you as approver and the ranking in the rationale:

```json
{"choice_id": "opt.atomic"}
```

Add a condition to your choice by sending your words with it. They are recorded verbatim as a condition on that choice:

```json
{"choice_id": "opt.atomic", "free_text": "Only while the node stays under 200 lines."}
```

Add an option. The kernel researches it, assesses the decision again and asks a new ranked question:

```json
{"added_options": [{"title": "Encapsulated subgraph", "description": "Wrap the capability in a subgraph with its own state."}]}
```

Answer in your own words. The kernel assesses the decision again with your words as constraints and ranks again; your words do not pick an option:

```json
{"free_text": "Prefer whatever needs no new state schema."}
```

Giving a `choice_id` the question did not offer is refused (exit 3, `semantic_invalid`) and the run is unchanged, so you can answer again.

### Step 4 — Resume the run

Put your answer under `response` in the resume file and run the command from [Step 5 of the run guide](run-the-decision-kernel.md):

```bash
python -m kernel resume --run-id <run id> --input-file answer.json --json
```

The envelope that comes back is the next pause or the end of the run.

### Step 5 — Know what the ranking and your silence do

- The ranking is advice. The decision waits for your choice and never resolves a ranked question on its own.
- Leaving the question unanswered keeps the run waiting, and cancelling it keeps no record. Cancel with `python -m kernel cancel --run-id <run id> --actor human:<id> --json`. Only a decision you approved is staged as a record ([How to file approved decisions and reuse them as precedent](file-and-reuse-decisions-with-the-kernel.md)).

## Verification

```bash
python -m kernel status --run-id <run id> --json
```

Expected output: one JSON envelope with the run's `status` (exit code 0). A refused answer leaves the run exactly as it was, with the same `waiting_human` question still open. Read the `status` and `pending_interaction` to see the next pause, or the report path when the run is terminal.

## Troubleshooting

1. **Exit 3, `schema_invalid`.** The answer carries both `approved_criterion_ids` and `edited_criteria`, or sets none or several of `choice_id`, `free_text` and the structured fields. Send one mode (a choice may carry `free_text`).
2. **Exit 3, `semantic_invalid`.** The answer names an id the question did not offer, or uses free text or a structured answer on a question that does not allow it. Copy the ids from `pending_interaction.question`.
3. **Exit 3, `stale_revision` or `not_pending`.** Echo the packet's current `state_revision` and its `interaction_id` ([run guide](run-the-decision-kernel.md), Troubleshooting 4).

## See Also

- [How to run the decision kernel](run-the-decision-kernel.md)
- [How to file approved decisions and reuse them as precedent](file-and-reuse-decisions-with-the-kernel.md)
- [c3-024: one forming round](../architecture/diagrams/c3-024-decision-kernel-flows-forming-round.md)
- [c3-025: decision states](../architecture/diagrams/c3-025-decision-kernel-flows-decision-states.md)
- [ADR-060: Source of truth and approval authority](../architecture/adrs/ADR-060-source-of-truth-and-approval-authority.md)
- [Documentation Index](../INDEX.md)
