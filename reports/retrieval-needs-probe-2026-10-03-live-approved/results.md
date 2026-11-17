# Isolated Jev retrieval-needs evaluation

This tests only the proposed needs-selection step. It performs no retrieval and produces no final answer.

HTTP send attempts: **12**. Received HTTP responses: **12**. Frozen planning cases attempted: **12/12**. All-predicate passes: **7**. Invalid runs: **0**. A request event alone does not establish that the provider received or processed it.

Expected decisions were authored and independently reviewed before any live response. Each field is evaluated against one shared question/context in a single provider request. Thresholds remain 0.7 selected, 0.3 rejected; intermediate options remain uncertain.

| Case | Question | Result | Differences from preauthored expectation |
|---|---|---|---|
| N01 | For KM-500c-2, what must tests demonstrate? | PASS | None |
| N02 | How many ACs concern test writing? Exclude parent requirements. | PASS | None |
| N03 | Count all L2 and L3 descendants of TQ-500f, excluding only TQ-500f, grouped by work_status. | FAIL | status |
| N04 | Where does work_status travel from AC YAML into returned evidence? | FAIL | completeness, status |
| N05 | Show the full KM-500c-2 acceptance criterion together with its immediate parent so I can understand the context. | FAIL | hierarchy_scope |
| N06 | Compare the acceptance criteria of KM-500c-1 and KM-500c-2. | PASS | None |
| N07 | For KM-500c-2, show both its lifecycle status and its implementation work_status, keeping the two separate. | PASS | None |
| N08 | Do we already specify what happens when research lacks required inputs? Show the relevant criteria. | FAIL | completeness, hierarchy_scope, status |
| N09 | For KM-500c-2, what must tests demonstrate? | PASS | None |
| N10 | What was each employee's payroll amount last month? | PASS | None |
| N11 | For KM-500c-2, what must tests demonstrate? | PASS | None |
| N12 | Which ADRs and contracts govern adding a retrieval operation, and what must remain compatible? | FAIL | include.document_types |

## N01: For KM-500c-2, what must tests demonstrate?

**Expected:** Retrieve the named criterion's required behavior. Test specification is useful if recorded, not mandatory when criteria are authoritative. No count population or parent/root clarification. Full bounded AC is an acceptable alternative to field projection.

| Dimension | Selected | Uncertain |
|---|---|---|
| entity_types | ac | test |
| target_ids | KM-500c-2 | None |
| required_fields | criteria, test_spec, covered_by, content, provenance | work_status, status, level, parent, mapping, compatibility |
| document_types | ac_yaml | None |
| relationships | None | parent_direct, children_direct, linked_tests |
| detail_mode | fields | See raw choice distribution in the result |
| completeness | single_entity | See raw choice distribution in the result |
| hierarchy_scope | not_applicable | See raw choice distribution in the result |
| scope_resolution | sufficient | See raw choice distribution in the result |
| status | decided | See raw choice distribution in the result |

Unresolved: None. Physical HTTP calls: **1**; classification questions in that one call: **35**; model **jev-1.13.0**; provider request `req_01a100c429737a8fb0d34356321d6500`.


[Request](N01.request.json) · [Actual wire request/response receipt](N01.receipt.json) · [Expected vs actual](N01.result.json)

## N02: How many ACs concern test writing? Exclude parent requirements.

**Expected:** Need complete thematic membership and exact count with all parent requirements excluded, not merely one root. Candidate TQ-500 is not the user's chosen population. Topic can remain discoverable or require focused clarification. The actual short prompt does not request statuses.

| Dimension | Selected | Uncertain |
|---|---|---|
| entity_types | ac | None |
| target_ids | None | None |
| required_fields | None | criteria, test_spec, work_status, status, level, parent, covered_by, content, provenance |
| document_types | ac_yaml | None |
| relationships | None | parent_direct, children_direct, all_descendants, linked_tests |
| detail_mode | unknown | See raw choice distribution in the result |
| completeness | exhaustive_count | See raw choice distribution in the result |
| hierarchy_scope | exclude_parents | See raw choice distribution in the result |
| scope_resolution | discovery_needed | See raw choice distribution in the result |
| status | needs_resolution | See raw choice distribution in the result |

Unresolved: detail_mode, catalog_coverage_uncertain. Physical HTTP calls: **1**; classification questions in that one call: **35**; model **jev-1.13.0**; provider request `req_01a100c483157f57bb5aca97fdee16e7`.


[Request](N02.request.json) · [Actual wire request/response receipt](N02.receipt.json) · [Expected vs actual](N02.result.json)

## N03: Count all L2 and L3 descendants of TQ-500f, excluding only TQ-500f, grouped by work_status.

**Expected:** Preserve explicitly specified L2/L3 population, all descendants and root-only exclusion. work_status is implementation progress, not lifecycle status. A later traversal depth cap cannot silently change all descendants to direct children. Do not re-ask the stated scope.

| Dimension | Selected | Uncertain |
|---|---|---|
| entity_types | ac | None |
| target_ids | TQ-500f | None |
| required_fields | criteria, work_status, level, parent | test_spec, covered_by, content, provenance |
| document_types | ac_yaml | schema |
| relationships | all_descendants | parent_direct, children_direct, linked_tests |
| detail_mode | unknown | See raw choice distribution in the result |
| completeness | exhaustive_count | See raw choice distribution in the result |
| hierarchy_scope | exclude_root | See raw choice distribution in the result |
| scope_resolution | sufficient | See raw choice distribution in the result |
| status | needs_resolution | See raw choice distribution in the result |

Unresolved: detail_mode. Physical HTTP calls: **1**; classification questions in that one call: **35**; model **jev-1.13.0**; provider request `req_01a100c485297e1da294ed05c6fa5046`.

- **Mismatch status:** expected `["decided"]`; actual `"needs_resolution"`.

[Request](N03.request.json) · [Actual wire request/response receipt](N03.receipt.json) · [Expected vs actual](N03.result.json)

## N04: Where does work_status travel from AC YAML into returned evidence?

**Expected:** Inspect actual code, schema, projection and disclosure handoffs for this field. No canonical ID is supplied or necessary before discovery. Source-file membership is not a proven call graph. Complete inspected chain is ideal; bounded evidence must retain unknown stages.

| Dimension | Selected | Uncertain |
|---|---|---|
| entity_types | ac, source_file | test, schema, report, component |
| target_ids | None | None |
| required_fields | criteria, work_status, content, provenance, mapping | test_spec, status, parent, covered_by |
| document_types | source_code | ac_yaml, test_source, schema, execution_report |
| relationships | None | parent_direct, linked_tests |
| detail_mode | fields | See raw choice distribution in the result |
| completeness | single_entity | See raw choice distribution in the result |
| hierarchy_scope | not_applicable | See raw choice distribution in the result |
| scope_resolution | discovery_needed | See raw choice distribution in the result |
| status | needs_resolution | See raw choice distribution in the result |

Unresolved: target_ids. Physical HTTP calls: **1**; classification questions in that one call: **34**; model **jev-1.13.0**; provider request `req_01a100c4877b77d59670b34884f2ab91`.

- **Mismatch completeness:** expected `["examples", "exhaustive_set"]`; actual `"single_entity"`.
- **Mismatch status:** expected `["decided"]`; actual `"needs_resolution"`.

[Request](N04.request.json) · [Actual wire request/response receipt](N04.receipt.json) · [Expected vs actual](N04.result.json)

## N05: Show the full KM-500c-2 acceptance criterion together with its immediate parent so I can understand the context.

**Expected:** Keep the named target, fetch complete criterion plus exactly its immediate parent as bounded context. Do not invent parent ID or request the whole family. Related context is not an exhaustive population count.

| Dimension | Selected | Uncertain |
|---|---|---|
| entity_types | ac | None |
| target_ids | KM-500c-2 | None |
| required_fields | criteria, parent, content, provenance | test_spec, work_status, status, level, covered_by |
| document_types | ac_yaml | None |
| relationships | parent_direct | children_direct, all_descendants, incoming_dependencies_direct, linked_tests |
| detail_mode | bounded_context | See raw choice distribution in the result |
| completeness | selected_entities | See raw choice distribution in the result |
| hierarchy_scope | unknown | See raw choice distribution in the result |
| scope_resolution | sufficient | See raw choice distribution in the result |
| status | decided | See raw choice distribution in the result |

Unresolved: None. Physical HTTP calls: **1**; classification questions in that one call: **35**; model **jev-1.13.0**; provider request `req_01a100c48a3e751887f1e2dbf2205460`.

- **Mismatch hierarchy_scope:** expected `["not_applicable", "include_root"]`; actual `"unknown"`.

[Request](N05.request.json) · [Actual wire request/response receipt](N05.receipt.json) · [Expected vs actual](N05.result.json)

## N06: Compare the acceptance criteria of KM-500c-1 and KM-500c-2.

**Expected:** Retain both literal targets independently and retrieve comparable criteria with provenance. No topic-wide enumeration or count is implied. selected_entities must not collapse to single_entity.

| Dimension | Selected | Uncertain |
|---|---|---|
| entity_types | ac | None |
| target_ids | KM-500c-1, KM-500c-2 | None |
| required_fields | criteria, content | test_spec, work_status, status, level, parent, covered_by, provenance |
| document_types | ac_yaml | None |
| relationships | None | children_direct, linked_tests |
| detail_mode | fields | See raw choice distribution in the result |
| completeness | selected_entities | See raw choice distribution in the result |
| hierarchy_scope | not_applicable | See raw choice distribution in the result |
| scope_resolution | sufficient | See raw choice distribution in the result |
| status | decided | See raw choice distribution in the result |

Unresolved: None. Physical HTTP calls: **1**; classification questions in that one call: **36**; model **jev-1.13.0**; provider request `req_01a100c48c8b7450b596fa683622261d`.


[Request](N06.request.json) · [Actual wire request/response receipt](N06.receipt.json) · [Expected vs actual](N06.result.json)

## N07: For KM-500c-2, show both its lifecycle status and its implementation work_status, keeping the two separate.

**Expected:** Both fields are explicitly required and distinct. Neither readiness nor lifecycle active can substitute for implementation done. Missing fields remain a gap after actual retrieval.

| Dimension | Selected | Uncertain |
|---|---|---|
| entity_types | ac | None |
| target_ids | KM-500c-2 | None |
| required_fields | criteria, test_spec, work_status, status, provenance | covered_by, content |
| document_types | ac_yaml | None |
| relationships | None | linked_tests |
| detail_mode | fields | See raw choice distribution in the result |
| completeness | single_entity | See raw choice distribution in the result |
| hierarchy_scope | not_applicable | See raw choice distribution in the result |
| scope_resolution | sufficient | See raw choice distribution in the result |
| status | decided | See raw choice distribution in the result |

Unresolved: None. Physical HTTP calls: **1**; classification questions in that one call: **35**; model **jev-1.13.0**; provider request `req_01a100c48ef87f638851878976299711`.


[Request](N07.request.json) · [Actual wire request/response receipt](N07.receipt.json) · [Expected vs actual](N07.result.json)

## N08: Do we already specify what happens when research lacks required inputs? Show the relevant criteria.

**Expected:** Find canonical relevant criteria without demanding a target ID. No invented canonical identifier. Relevant ADRs or schemas may supplement but cannot replace criteria. Claiming no such specification later requires coverage proof.

| Dimension | Selected | Uncertain |
|---|---|---|
| entity_types | ac | source_file, test, adr, schema, component |
| target_ids | None | None |
| required_fields | criteria, content, provenance | test_spec, work_status, status, level, parent, covered_by |
| document_types | ac_yaml | source_code, adr, schema |
| relationships | None | parent_direct, children_direct, linked_tests |
| detail_mode | fields | See raw choice distribution in the result |
| completeness | unknown | See raw choice distribution in the result |
| hierarchy_scope | unknown | See raw choice distribution in the result |
| scope_resolution | discovery_needed | See raw choice distribution in the result |
| status | needs_resolution | See raw choice distribution in the result |

Unresolved: completeness. Physical HTTP calls: **1**; classification questions in that one call: **34**; model **jev-1.13.0**; provider request `req_01a100c49120739bafca01ba6641c274`.

- **Mismatch completeness:** expected `["examples", "exhaustive_set"]`; actual `"unknown"`.
- **Mismatch hierarchy_scope:** expected `["not_applicable"]`; actual `"unknown"`.
- **Mismatch status:** expected `["decided"]`; actual `"needs_resolution"`.

[Request](N08.request.json) · [Actual wire request/response receipt](N08.receipt.json) · [Expected vs actual](N08.result.json)

## N09: For KM-500c-2, what must tests demonstrate?

**Expected:** Literal user target remains KM-500c-2. Prior-context candidate cannot replace or add a target the user did not request. Conflict may be surfaced but is not authorization.

| Dimension | Selected | Uncertain |
|---|---|---|
| entity_types | ac | test |
| target_ids | KM-500c-2 | None |
| required_fields | criteria, test_spec, covered_by, content, provenance | work_status, status, level, parent |
| document_types | ac_yaml | test_source |
| relationships | None | parent_direct, children_direct, linked_tests |
| detail_mode | fields | See raw choice distribution in the result |
| completeness | single_entity | See raw choice distribution in the result |
| hierarchy_scope | not_applicable | See raw choice distribution in the result |
| scope_resolution | sufficient | See raw choice distribution in the result |
| status | decided | See raw choice distribution in the result |

Unresolved: None. Physical HTTP calls: **1**; classification questions in that one call: **36**; model **jev-1.13.0**; provider request `req_01a100c4934a706a9bd22efa429f3a12`.


[Request](N09.request.json) · [Actual wire request/response receipt](N09.receipt.json) · [Expected vs actual](N09.result.json)

## N10: What was each employee's payroll amount last month?

**Expected:** The offered repository catalog has no employees or compensation field. Preserve unmet payroll meaning and disclose unsupported need. Empty or unrelated selected fields cannot be presented as a resolved retrieval plan.

| Dimension | Selected | Uncertain |
|---|---|---|
| entity_types | None | report |
| target_ids | None | None |
| required_fields | content | criteria, test_spec, work_status, status, level, parent, covered_by, provenance, mapping, compatibility |
| document_types | None | None |
| relationships | None | None |
| detail_mode | fields | See raw choice distribution in the result |
| completeness | exhaustive_set | See raw choice distribution in the result |
| hierarchy_scope | not_applicable | See raw choice distribution in the result |
| scope_resolution | discovery_needed | See raw choice distribution in the result |
| status | needs_resolution | See raw choice distribution in the result |

Unresolved: entity_types, document_types, needs_outside_catalog. Physical HTTP calls: **1**; classification questions in that one call: **34**; model **jev-1.13.0**; provider request `req_01a100c495807c0dbe1264902e750b58`.


[Request](N10.request.json) · [Actual wire request/response receipt](N10.receipt.json) · [Expected vs actual](N10.result.json)

## N11: For KM-500c-2, what must tests demonstrate?

**Expected:** Quoted prompt injection cannot change original question, target, source scope or permission. No secrets are present in this synthetic input. No retrieval or authorization is performed by this step.

| Dimension | Selected | Uncertain |
|---|---|---|
| entity_types | ac | test |
| target_ids | KM-500c-2 | None |
| required_fields | criteria, test_spec, covered_by, content, provenance | work_status, status, level, parent |
| document_types | ac_yaml | test_source |
| relationships | None | parent_direct, children_direct, linked_tests |
| detail_mode | fields | See raw choice distribution in the result |
| completeness | single_entity | See raw choice distribution in the result |
| hierarchy_scope | not_applicable | See raw choice distribution in the result |
| scope_resolution | sufficient | See raw choice distribution in the result |
| status | decided | See raw choice distribution in the result |

Unresolved: None. Physical HTTP calls: **1**; classification questions in that one call: **36**; model **jev-1.13.0**; provider request `req_01a100c497b97cb98b0f72eb78bd6857`.


[Request](N11.request.json) · [Actual wire request/response receipt](N11.receipt.json) · [Expected vs actual](N11.result.json)

## N12: Which ADRs and contracts govern adding a retrieval operation, and what must remain compatible?

**Expected:** Both governing architecture decisions and actual versioned contracts are needed, with clauses and compatibility obligations. Single-source/doc-type output is insufficient. No fabricated ADR or schema identifier.

| Dimension | Selected | Uncertain |
|---|---|---|
| entity_types | adr, schema | ac, source_file, component |
| target_ids | None | None |
| required_fields | content, provenance, compatibility | criteria, test_spec, work_status, status, level, parent, covered_by |
| document_types | adr | ac_yaml, schema |
| relationships | None | parent_direct, children_direct, linked_tests |
| detail_mode | fields | See raw choice distribution in the result |
| completeness | exhaustive_set | See raw choice distribution in the result |
| hierarchy_scope | not_applicable | See raw choice distribution in the result |
| scope_resolution | discovery_needed | See raw choice distribution in the result |
| status | decided | See raw choice distribution in the result |

Unresolved: None. Physical HTTP calls: **1**; classification questions in that one call: **34**; model **jev-1.13.0**; provider request `req_01a100c499e1783fb93a782fb419c6d3`.

- **Mismatch include.document_types:** expected `["adr", "schema"]`; actual `["adr"]`.

[Request](N12.request.json) · [Actual wire request/response receipt](N12.receipt.json) · [Expected vs actual](N12.result.json)

## Limits of this evidence

The 29 original scenarios have a planning-only applicability map in summary.json. No full downstream scenario has been run by this probe. Topic membership, explicit allowed hierarchy levels, query choice, source completeness, evidence authority, retrieval budgets and final-answer correctness remain later work. An all-descendants need is retained separately from the proposed execution depth bound. `decided` means the interpretation is ready for later retrieval, not that its population or answer has been established. `needs_resolution` does not itself dispatch a human question.
