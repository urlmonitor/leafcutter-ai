---
title: "Reference: Decision record"
description: "Every field of the decision record the kernel stages and publishes to docs/decisions/, with type, requiredness, default and meaning; consult it to read, validate or review a record."
type: reference
status: active
created: 2026-10-10
last_updated: 2026-10-10
components:
  - decision_kernel
related_docs:
  - docs/how-to/file-and-reuse-decisions-with-the-kernel.md
  - docs/architecture/components/decision-kernel.md
  - docs/architecture/diagrams/c3-026-decision-kernel-flows-record-staging.md
  - docs/architecture/diagrams/c3-028-decision-kernel-flows-record-lifecycle.md
  - docs/architecture/adrs/ADR-059-decision-store-reviewable-yaml-records-now-graph-later.md
  - docs/architecture/adrs/ADR-060-source-of-truth-and-approval-authority.md
  - docs/architecture/adrs/ADR-061-identity-of-declared-and-learned-records.md
---

# Decision record

The decision record is the YAML file `docs/decisions/<id>.yaml` that holds one decision a human approved; this page lists every field of it, grouped as identity, question, filters, answer, evidence, authority, provenance and corrections.

---

## Record rules

| Rule | Statement |
|---|---|
| Schema | The kernel validates each record against `config/decision_record.schema.json` (`$id` `leafcutter.decision_record.v1`, generated from `kernel.memory.models`). Unknown fields are refused (`additionalProperties: false`). |
| Required at the top level | `id`, `repository_id`, `title`, `decision_type`, `question`, `selected_option_id`, `task_context`, `rationale`, `options`, `approval`, `provenance`. |
| Approval | Only a decision a human approved produces a record. `approval.approval_status` is always `approved`, and `approval.approved_at` and `approval.approved_by` are required. A host or service cannot approve. |
| Evidence | Evidence is held as locators and content hashes, never as text. |
| Corrections | `corrections` is append-only. The original fields are never edited. |
| Origin | `provenance.origin` is `learned` for a record the kernel filed from an approved run. |

---

## Identity

Names the record and the repository it belongs to; `repository_id` with `id` forms the identity key.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `schema_version` | `1.0` (fixed) | No | `"1.0"` | Version of this record format, so a reader can reject a record written for another shape. |
| `kind` | `decision` (fixed) | No | `"decision"` | Marks the file as a decision record among other documents. |
| `id` | string | Yes | — | Identifier (`dec-<16 hex>`) that links and precedent lookups refer to this record by. |
| `repository_id` | string | Yes | — | Repository the decision belongs to; with the id it forms the record's identity key. |
| `title` | string | Yes | — | Short name shown in the decision index. |
| `description` | string | No | `""` | One-line summary shown in the decision index. |

---

## Question

What was asked, the context it was asked in, and the options and criteria it was weighed against.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `question` | string | Yes | — | The decision question as asked; precedent lookup matches new questions against it. |
| `decision_type` | string | Yes | — | Kind of decision (a slug), so similar decisions can be grouped. |
| `task_context` | object | Yes | — | What the run was asked and where. |
| `task_context.component_ids` | list of strings | No | — | Components the task concerned, to find the record again by component. |
| `task_context.constraints` | list of strings | No | — | Constraints the task stated, which the chosen option had to respect. |
| `task_context.goal` | string | Yes | — | What the run was asked, in the caller's words. |
| `task_context.technologies` | list of strings | No | — | Technologies the task involved, as context for judging whether the decision still applies. |
| `options` | list of objects | Yes | — | The options that were weighed, including the one chosen. |
| `options[].approved_by` | string or null | No | `null` | Actor that approved the option. |
| `options[].assumptions` | list of strings | No | — | Premises the option relied on, kept verbatim so a later reader can check whether they still hold. |
| `options[].description` | string | No | `""` | What the option meant in practice. |
| `options[].evidence_ids` | list of strings | No | — | Evidence the option cites, resolved in the record's evidence list. |
| `options[].id` | string | Yes | — | Stable id the selection and the criteria evidence refer to. |
| `options[].proposed_by` | string or null | No | `null` | Actor that proposed the option. |
| `options[].title` | string | Yes | — | Short name of the option. |
| `criteria` | list of objects | No | — | The criteria the options were weighed against. |
| `criteria[].evidence_ids` | list of strings | No | — | Evidence cited for the criterion, resolved in the record's evidence list. |
| `criteria[].id` | string | Yes | — | Stable id of the criterion within this record. |
| `criteria[].kind` | enum: `evidence_answerable`, `design_judgement` | No | `"evidence_answerable"` | Whether evidence could settle the criterion or it was a judgement of the designs themselves. |
| `criteria[].priority` | enum: `required`, `supporting` | No | `"required"` | Whether the criterion was required for a decision or only supporting. |
| `criteria[].question` | string | Yes | — | The question each option was weighed against. |

---

## Filters

Classification filters that precedent lookup matches on; each value is drawn from an existing vocabulary only (`docs/components.json`, `docs/roadmap.json`, the ticket vocabulary).

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `components` | list of strings | No | — | Classification filters, drawn only from the existing vocabularies (see `validate`). |
| `change_target` | list of strings | No | — | Kinds of change the decision applies to (a filter drawn from the ticket vocabulary). |
| `risk_surface` | list of strings | No | — | Risk surfaces the decision applies to (a filter drawn from the ticket vocabulary). |
| `roadmap_phase` | list of strings | No | — | Roadmap phases the decision applies to (a filter). |
| `file_globs` | list of strings | No | — | File path patterns the decision applies to (a filter). |
| `repository_wide` | boolean | No | `false` | True when the decision applies to the whole repository, so it needs no other filter. |

---

## Answer

The chosen option, why it was chosen, and how the kernel assessed it.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `selected_option_id` | string | Yes | — | Id of the option the human chose; it must be one of the listed options. |
| `rationale` | object | Yes | — | Why the option was chosen. |
| `rationale.origin` | enum: `template`, `host` | No | `"template"` | Who wrote the text: a kernel template or the host, never hidden model reasoning. |
| `rationale.text` | string | Yes | — | Why the option was chosen. |
| `assumptions` | list of strings | No | — | Premises the decision as a whole rests on, kept verbatim for later review. |
| `unresolved_risks` | list of strings | No | — | Risks that remained open when the decision was made. |
| `assessment` | object | No | — | How the decision was assessed, including the ranking the human saw. |
| `assessment.basis` | enum: `kernel_ranking`, `resolved_gate`, `precedent_reuse` | No | `"kernel_ranking"` | How the outcome came about: from the kernel ranking, a resolved gate, or reuse of a precedent. |
| `assessment.confidence` | number or null | No | `null` | The model's confidence in its assessment (0 to 1), when it gave one. |
| `assessment.design_reason` | string or null | No | `null` | Why the kernel stopped researching and handed the ranking to a human; null when it did not. |
| `assessment.ranking` | list of objects | No | — | The ranking the human saw when choosing. |
| `assessment.ranking[].option_id` | string | Yes | — | The option this ranking entry describes. |
| `assessment.ranking[].rank` | integer | Yes | — | Position in the kernel ranking shown to the human (1 is best); evidence, never authority. |
| `assessment.ranking[].required_mean` | number or null | No | `null` | Mean satisfies probability over the required criteria. |
| `assessment.ranking[].required_passed` | integer or null | No | `null` | How many required criteria the option met at the satisfies threshold. |
| `assessment.ranking[].required_total` | integer or null | No | `null` | How many required criteria were assessed. |
| `assessment.ranking[].scores` | object | No | — | Satisfies probability per criterion id behind the ranking. |
| `assessment.selected_rank` | integer or null | No | `null` | Rank the human's choice held in the ranking shown, so overrides of the ranking are visible. |
| `final_outcome` | object | No | — | What later happened to the decision. |
| `final_outcome.note` | string | No | `""` | What was observed, in a sentence. |
| `final_outcome.observed_at` | string or null | No | `null` | When the outcome was observed (UTC). |
| `final_outcome.status` | enum: `pending`, `confirmed`, `corrected`, `abandoned` | No | `"pending"` | What later happened to the decision: still pending, confirmed, corrected or abandoned. |

---

## Evidence

References to the evidence cited. Evidence is held as locators and content hashes, never as text.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `evidence` | list of objects | No | — | References to the evidence cited, without the text. |
| `evidence[].category` | string | Yes | — | Kind of evidence (guidance, prior decision, existing pattern, ...). |
| `evidence[].content_hash` | string | Yes | — | Hash of the text at the time, so a later reader can tell whether the source changed. |
| `evidence[].id` | string | Yes | — | Evidence id the options and criteria cite. |
| `evidence[].locator` | string | Yes | — | Where the evidence was read, so it can be found again; the text itself is not stored. |
| `evidence[].relevance` | number or null | No | `null` | Judged relevance to the question (0 to 1). |
| `evidence[].source_version` | object or null | No | `null` | Repository revision the evidence was read at. |
| `evidence[].source_version.commit` | string or null | No | `null` | Commit the fact was read at, so a later reader can tell whether the repository has moved on. |
| `evidence[].source_version.dirty` | boolean | No | `false` | True when the working tree differed from that commit. |
| `evidence[].verification` | string | No | `"unverified"` | How far the text was checked against its source. |

---

## Authority

Who approved the decision, and how it relates to earlier decisions.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `approval` | object | Yes | — | Who approved the decision and when. |
| `approval.approval_status` | `approved` (fixed) | Yes | — | Always approved, because a record is filed only for a decision a human approved. |
| `approval.approved_at` | string | Yes | — | When the human approved (UTC). |
| `approval.approved_by` | string | Yes | — | The human who approved the decision (`human` or `human:<id>`); a host or service cannot approve. |
| `approval.note` | string | No | `""` | Anything the approver added, such as a condition. |
| `precedents_considered` | list of objects | No | — | Earlier decisions the kernel considered, and what became of each. |
| `precedents_considered[].action` | enum: `used_as_evidence`, `offered_for_reuse`, `reused`, `set_aside`, `not_applicable` | No | `"used_as_evidence"` | What became of it: used as evidence, offered for reuse, reused, set aside or not applicable. |
| `precedents_considered[].applicability` | number or null | No | `null` | Judged probability (0 to 1) that the earlier decision applied. |
| `precedents_considered[].id` | string | Yes | — | Id of the earlier decision that was considered. |
| `precedents_considered[].note` | string | No | `""` | Why, in a sentence. |
| `supersedes` | list of strings | No | — | Ids of earlier decisions this one replaces. |
| `superseded_by` | list of strings | No | — | Ids of later decisions that replace this one. |
| `related` | list of strings | No | — | Ids of decisions that are linked without replacing each other. |

---

## Provenance

Where, when and under which versions the record was made.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `provenance` | object | Yes | — | Where, when and under which versions the record was made. |
| `provenance.created_at` | string | Yes | — | When the record was created (UTC). |
| `provenance.created_by_capability` | string | No | `"decision"` | Capability that produced the decision. |
| `provenance.decision_versions` | object | No | — | Versions of the components that took part in the decision, keyed by component. |
| `provenance.kernel_version` | string or null | No | `null` | Version of the kernel that produced the record. |
| `provenance.langfuse_trace_id` | string or null | No | `null` | Trace id in Langfuse, for opening the run's trace. |
| `provenance.langfuse_trace_url` | string or null | No | `null` | Link to the trace in Langfuse. |
| `provenance.model_version` | string or null | No | `null` | Version of the model that answered. |
| `provenance.origin` | `learned` (fixed) | No | `"learned"` | How the record came to exist; learned means the kernel filed it from an approved run. |
| `provenance.policy_version` | string or null | No | `null` | Version of the policy under which the decision was made. |
| `provenance.repository_revision` | object | No | — | Repository revision the run read. |
| `provenance.repository_revision.commit` | string or null | No | `null` | Commit the fact was read at, so a later reader can tell whether the repository has moved on. |
| `provenance.repository_revision.dirty` | boolean | No | `false` | True when the working tree differed from that commit. |
| `provenance.root_task_id` | string or null | No | `null` | Root task of that run. |
| `provenance.run_id` | string | Yes | — | Run that produced the decision, to find its trace and artifacts. |
| `provenance.template_version` | string or null | No | `null` | Version of the prompt templates used. |

---

## Corrections

Append-only corrections made after filing. The original is never edited.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `corrections` | list of objects | No | — | Append-only corrections made after filing; the original is never edited. |
| `corrections[].corrected_at` | string | Yes | — | When the correction was made (UTC). |
| `corrections[].corrected_by` | string | Yes | — | The human who made the correction. |
| `corrections[].new_selected_option_id` | string or null | No | `null` | Option that now stands, when the correction changes the choice. |
| `corrections[].preserved` | object | No | — | What the correction keeps of the original record, because records are never edited. |
| `corrections[].preserved.assumptions` | list of strings | No | — | Assumptions the record held before the correction. |
| `corrections[].preserved.evidence_ids` | list of strings | No | — | Evidence the record cited before the correction. |
| `corrections[].preserved.selected_option_id` | string or null | No | `null` | Option the record selected before the correction. |
| `corrections[].reason` | string | Yes | — | Why the decision was corrected. |
| `corrections[].superseded_by` | string or null | No | `null` | Id of the decision that replaces this one, when a new decision was filed. |

---
## Example

Excerpt of `docs/decisions/dec-d53e1c52cd47c832.yaml`, the record of the decision to make the kernel the default entry for design, planning and lookup questions.

```yaml
schema_version: '1.0'
kind: decision
id: dec-d53e1c52cd47c832
repository_id: leafcutter-ai
decision_type: design
repository_wide: true
selected_option_id: opt.kernel_entry_point
rationale:
  origin: template
assessment:
  basis: kernel_ranking
  design_reason: design_judgement
  confidence: 0.8033
  selected_rank: 1
evidence:
  - id: ev-f657e2f7b406cf8f
    locator: docs/decisions/dec-ef8ddcb79d668a67.yaml
    category: prior_decisions
    content_hash: 729963ea6862b0f7dd2aadbe1a011ec89256f97c6d165dd986bbce168015d53b
    verification: source_verified
    relevance: 0.62
    source_version:
      commit: a4b9a94f5b266503993e65a97727b5059717f6c4
      dirty: true
precedents_considered:
  - id: dec-ef8ddcb79d668a67
    applicability: 0.62
    action: used_as_evidence
approval:
  approval_status: approved
  approved_by: human:user
  approved_at: '2026-10-02T05:39:33Z'
provenance:
  origin: learned
  created_at: '2026-10-02T05:39:33Z'
  run_id: run-f0f15b38791a428f
corrections: []
```

---

## See Also

- [How to file approved decisions and reuse them as precedent](../how-to/file-and-reuse-decisions-with-the-kernel.md) - publish, validate and correct a record.
- [Decision kernel component](../architecture/components/decision-kernel.md) - the component that owns the record.
- [c3-026: staging a record](../architecture/diagrams/c3-026-decision-kernel-flows-record-staging.md) and [c3-028: record lifecycle](../architecture/diagrams/c3-028-decision-kernel-flows-record-lifecycle.md) - how a record is staged and what states it passes through.
- [ADR-059: Decision store](../architecture/adrs/ADR-059-decision-store-reviewable-yaml-records-now-graph-later.md) - one YAML record per approved decision.
- [ADR-060: Source of truth and approval authority](../architecture/adrs/ADR-060-source-of-truth-and-approval-authority.md) - only human approval creates a record.
- [ADR-061: Identity](../architecture/adrs/ADR-061-identity-of-declared-and-learned-records.md) - `dec-<16 hex>` ids and filter vocabularies.
- `config/decision_record.schema.json` - the schema the field list matches.
- `kernel/memory/record_sections.py` - the section models behind the schema.
