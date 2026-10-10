---
title: "Reference: Knowledge Retrieval Evidence"
description: "Canonical evidence fields, field-specific citations, requested source disclosure and availability limits for repository research answers."
type: reference
status: active
created: '2026-10-09'
last_updated: '2026-10-10'
components:
  - knowledge_management
  - decision_kernel
related_docs:
  - docs/reference/knowledge-retrieval-answers.md
  - docs/how-to/kernel-query-growth.md
  - docs/architecture/components/knowledge-retrieval.md
---
# Knowledge Retrieval Evidence

This reference describes the evidence returned through the
[knowledge retrieval answer contracts](knowledge-retrieval-answers.md), including
field-specific provenance, immutable source excerpts and limits on availability.

## Field provenance and availability

| Evidence field | Type | Default | Description |
|---|---|---|---|
| `entity.canonical_id`, `kind`, `title` | Strings | Source values | These fields retain canonical identity and entity type. |
| `entity.properties` | Object | Disclosed allowlist | Exact mapped values remain separate from generated summaries and interpretations. |
| `entity.source` | Object | Actual source | The object contains `repository_id`, `source_sha`, repository-relative `path`, `locator` and optional `content_hash`. |
| `content` | String or null | Disclosure-dependent | Level 3 returns bounded exact source content. AC `/criteria` returns the decoded canonical YAML string rather than YAML quote syntax. |
| `evidence_id` | String | Generated from actual evidence | The identity binds source and disclosed content. |
| `field_availability` | String map | `{}` | Required fields report `present`, `canonical_absent`, `projection_missing`, `disclosure_omitted`, `truncated` or `unknown`. |
| `field_locators` | String map | `{}` | A header field such as `work_status` uses `/work_status` within the same file/SHA; it is not located by the default `/criteria` excerpt pointer. |
| `field_contents` | String map | `{}` | Exact supplementary source excerpts keyed by requested field name; currently `test_spec` at level 3. Each excerpt uses its own `field_locators` entry in the same immutable source. |
| `field_derivations` | String map | `{}` | Derived hierarchy values state the rule instead of masquerading as literal YAML fields. |
| `path`, `relationships` | Relation lists | `[]` | Each relation retains source/target IDs, edge type and declaration source/locator. |
| `related`, `signals`, `seed_id` | Context fields | Empty or null | These fields carry bounded structural or relevance context. |
| `limitations` | String list | `[]` | Actual source truncation and unavailable excerpt conditions remain visible. |

Mapper `6` maps canonical AC `status`, `req_status`, `work_status`, `readiness`, `priority`, `level`, optional `parent`, `covered_by`, `implemented_by`, `depends_on`, `test_required` and source-disclosed `criteria`. Values have no invented defaults. `structural_parent` uses an explicit parent override or the existing `derive_parent_id` rule; its locator is `/parent` or `/id`. `has_children` is derived from structural-parent membership at the pinned revision. The exact rule is named in `field_derivations` when requested.

`test_spec` is not added to the graph mapping or disclosed by default. When explicitly
requested, level 3 reads `/test_spec` from the same pinned source file. The parsed
YAML list appears in `entity.properties.test_spec`; its exact source span appears
in `field_contents.test_spec`, with `field_locators.test_spec: "/test_spec"` and
`field_availability.test_spec: "present"`. Missing, malformed or unavailable reads
remain `unknown`; a lower disclosure level reports `disclosure_omitted`. Neither
case proves canonical absence.

The public adapter emits a separate ordinary `Evidence` record for that span:
`excerpt` is the retained source text, `source.section_locator` is `/test_spec`,
and `source.source_version.commit` retains the same pinned revision. The default
`/criteria` excerpt is preserved separately. Additional excerpts consume the
existing source-byte, public evidence-count and shared character allowances;
trimming cannot become a fulfilled answer.

For example, this illustrative projection shows the two parallel maps, not a
complete retrieval response or a captured source receipt:

```json
{
  "field_contents": {"test_spec": "- name: illustrative_test\n  description: Check the stated acceptance clause.\n"},
  "field_locators": {"test_spec": "/test_spec"},
  "field_availability": {"test_spec": "present"}
}
```

Arbitrary roadmap facts, full code graphs, execution receipts and deployment
state are not automatically projected by these mappings. Test/SourceFile nodes
represent declared references, not a complete repository file inventory. Unknown
mapping metadata in an older manifest remains unknown.

## Acceptance clauses and verification specifications

The host catalog separates `criteria` (required acceptance behavior) from
`test_spec` (authored scenarios, assertions, test angles and wrong implementations
to catch). A verification-obligation question needs both; the specification does
not replace the clauses. This is an interpretation instruction, not a deterministic
addition to every accepted request or a claim that the semantic repair has passed.

| Requested meaning | Evidence to request |
|---|---|
| What tests must demonstrate | `criteria` and authored `test_spec`, each with its own source locator |
| Only acceptance obligations | `criteria` |
| Only the authored test specification | `test_spec` |
| Declared test references | The AC's `covered_by` or an equivalent attributable reference set; no execution claim |
| Implementation and lifecycle status | `work_status` and `status`; `req_status` is governance, not lifecycle |
| Whole canonical document | Preserve `full_document`; a bounded `content` excerpt is insufficient |
| Whether tests passed | Actual execution evidence identifying the run and tested revision; declarations and status do not establish it |

Field availability is checked after retrieval. Missing or withheld specifications
remain explicit; the interpreter cannot infer their absence from a catalog label.
Interpretation quality and faithful retrieval of the chosen fields are separate
measurements. The frozen Oct3 experiment allowed an optional specification; its
historic gold and receipts remain unchanged by the current precision contract.

The [closed precision evaluation](../../reports/retrieval-needs-precision-v2-2026-10-09/stage1b/review.html) passed 16/16 interpretations. The subsequent [live source review](../../reports/retrieval-aura-2026-10-09/runs/precision-v2-44406d9/review.html) retained both fields in 4/4 interpretations; A01 and A03 returned exact canonical values and separate field citations, yielding 2/3 complete positive answers and a passing stale control. A02 stopped below the unchanged selection threshold with no retrieved evidence. This accepts the narrow interpretation repair while leaving selection reliability open; it does not establish full-document or actual test-execution support. Historical 10/12 interpretation and 0/3 whole-answer receipts remain unchanged.

## Bounded content

A required `content` field is satisfied only by a nonempty excerpt actually read
at disclosure level 3, with `field_locators.content` equal to the entity's canonical
`source.locator`. A graph property named `content`, a summary, or a lower-level
projection cannot satisfy it. The excerpt retains the pinned revision and consumes
the existing source/content budgets; it never proves a full document was returned.

| Actual disclosure | `field_availability.content` | Answer consequence |
|---|---|---|
| Nonempty canonical-source excerpt with matching locator | `present` | May satisfy this field within the requested bounded answer. |
| Authorized read returns empty or whitespace-only text | `canonical_absent` | This requested excerpt is empty; the field remains unmet. |
| Source read is unavailable or fails | `unknown` | No claim that the canonical source is empty. |
| Requested disclosure is below level 3 | `disclosure_omitted` | Withheld source text remains unmet. |
| The source-disclosure allowance cuts the excerpt | `truncated` | Useful text remains partial and cannot prove fulfillment. |
| A later public evidence-character allowance cuts previously disclosed text | May remain `present`; result `truncated` is true | The recomputed answer remains partial despite the earlier field availability. |

## See Also

- [Knowledge Retrieval Answers](knowledge-retrieval-answers.md) defines request, status, counting and answer-assessment contracts.
- [Kernel query growth](../how-to/kernel-query-growth.md) describes the public research and continuation route.
