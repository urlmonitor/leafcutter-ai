---
title: Product-truth steps carry a one-sentence description and an actor kind
status: in_progress
components:
- ux_prototyping
created: '2026-10-09'
last_updated: '2026-10-09'
depends_on: []
priority: high
roadmap_phase: phase_1
change_target: schema
risk_surface: internal
requires_diagram: false
requires_adr: false
agents:
  test-writer: signed_off
  python-coder: signed_off
  frontend-coder: signed_off
  llm-expert: signed_off
  documentation-expert: signed_off
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
files_touched:
- docs/INDEX.md
- docs/acceptance-criteria/ux-prototyping/UXP-520-atlas-flow-explorer/UXP-523-3.yaml
- docs/acceptance-criteria/ux-prototyping/UXP-520-atlas-flow-explorer/UXP-523-4.yaml
- docs/acceptance-criteria/ux-prototyping/UXP-540-pt-authoring-agents/UXP-542-1.yaml
- docs/acceptance-criteria/ux-prototyping/UXP-700-truthful-project-record/UXP-700e-2-ii.yaml
- docs/architecture/components/ux-prototyping.md
- docs/how-to/authoring-product-truth-artifacts.md
- docs/how-to/product-truth-schema-reference.md
- docs/how-to/reading-a-drift-report-and-reconciling-the-record.md
- docs/how-to/starting-a-project-record-from-nothing.md
- docs/product-truth/JSON-CONTRACTS.md
- docs/product-truth/README.md
- docs/product-truth/flows/fern-and-fig/checkout-and-pay.flow.json
- docs/product-truth/flows/fern-and-fig/customer-buys-a-plant.flow.json
- docs/product-truth/flows/fern-and-fig/track-an-order.flow.json
- docs/product-truth/flows/leafcutter/ac-lifecycle.flow.json
- docs/product-truth/flows/leafcutter/author-product-truth.flow.json
- docs/product-truth/flows/leafcutter/criteria-library.flow.json
- docs/product-truth/flows/leafcutter/decision-forming.flow.json
- docs/product-truth/flows/leafcutter/decision-lifecycle.flow.json
- docs/product-truth/flows/leafcutter/decision-publishing.flow.json
- docs/product-truth/flows/leafcutter/decision-retrieval.flow.json
- docs/product-truth/flows/leafcutter/decision-staging.flow.json
- docs/product-truth/flows/leafcutter/define-a-feature.flow.json
- docs/product-truth/flows/leafcutter/deliver-a-feature.flow.json
- docs/product-truth/flows/leafcutter/explore-flows-in-atlas.flow.json
- docs/product-truth/flows/leafcutter/finalize-feature.flow.json
- docs/product-truth/flows/leafcutter/flow-render-pipeline.flow.json
- docs/product-truth/flows/leafcutter/generate-product-truth.flow.json
- docs/product-truth/flows/leafcutter/how-acs-are-built.flow.json
- docs/product-truth/flows/leafcutter/product-truth-architecture.flow.json
- docs/product-truth/flows/leafcutter/python-coder-internal.flow.json
- docs/product-truth/flows/leafcutter/retrieval-current-baseline.flow.json
- docs/product-truth/flows/leafcutter/retrieval-needs-interpretation.flow.json
- docs/product-truth/flows/leafcutter/retrieval-query-build.flow.json
- docs/product-truth/flows/leafcutter/retrieval-registered-query.flow.json
- docs/product-truth/flows/leafcutter/retrieval-search-preparation.flow.json
- docs/product-truth/flows/leafcutter/retrieval-source-traversal.flow.json
- docs/product-truth/flows/leafcutter/retrieve-project-knowledge.flow.json
- docs/product-truth/mock-data/pipeline-prompts/draft-flow.prompt.json
- docs/product-truth/schemas/atlas-flows-view-props.schema.json
- docs/product-truth/schemas/atlas-normalized-flow.schema.json
- docs/product-truth/schemas/flow.schema.json
- docs/product-truth/scripts/README.md
- docs/product-truth/scripts/product_truth_contract_render.py
- docs/product-truth/scripts/product_truth_contracts.py
- docs/product-truth/scripts/product_truth_descriptions.py
- docs/product-truth/scripts/product_truth_flow_fields.py
- docs/product-truth/scripts/validate_product_truth.py
- docs/reference/product-truth-size-bounds.md
- knowledge/native_types/flow.py
- leafcutter-web/components/flows/__tests__/flow-decisions.fixture.ts
- leafcutter-web/components/flows/__tests__/flow-drawer.contracts.test.tsx
- leafcutter-web/components/flows/__tests__/flow-explorer.contracts.test.tsx
- leafcutter-web/components/flows/flow-drawer.tsx
- leafcutter-web/components/flows/flow-step-view.ts
- leafcutter-web/components/flows/step-runner.tsx
- leafcutter-web/fixtures/docs/product-truth/flows/leafcutter/deliver-a-feature.flow.json
- leafcutter-web/fixtures/docs/product-truth/flows/leafcutter/mock-mode-toggle.flow.json
- leafcutter-web/fixtures/docs/product-truth/flows/leafcutter/write-review-decision-fork.flow.json
- leafcutter-web/lib/data/__tests__/actor-kind.test.ts
- leafcutter-web/lib/data/__tests__/flows.contracts.test.ts
- leafcutter-web/lib/data/__tests__/graph.decisions.test.ts
- leafcutter-web/lib/data/actor-kind.ts
- leafcutter-web/lib/data/flow-contracts.ts
- leafcutter-web/lib/data/flows.ts
- leafcutter-web/lib/data/graph.ts
- leafcutter-web/lib/data/types.ts
- templates/agents/flow-author.md
- tests/fixtures/entity_context/owners.json
- tests/fixtures/product_truth_contracts/request.json
- tests/knowledge/test_native_flow.py
- tickets/00_inbox/TICKET-20261009-ProductTruthDescriptionActorKind.md
- unit_tests/product_truth/_bounds_harness.py
- unit_tests/product_truth/_uxp700b1_harness.py
- unit_tests/product_truth/_uxp_700c_2_fixtures.py
- unit_tests/product_truth/_uxp_700c_2_ii_fixtures.py
- unit_tests/product_truth/test_flow_io_contract_gate.py
- unit_tests/product_truth/test_flow_io_contract_migration.py
- unit_tests/product_truth/test_product_truth_descriptions.py
- unit_tests/product_truth/test_uxp_700a_1_ii.py
- unit_tests/product_truth/test_uxp_700b_1_i.py
- unit_tests/product_truth/test_uxp_700b_1_ii.py
- unit_tests/product_truth/test_uxp_700b_2.py
- unit_tests/product_truth/test_uxp_700c_1.py
- unit_tests/product_truth/test_uxp_700c_1_i.py
- unit_tests/product_truth/test_uxp_700c_3.py
- unit_tests/product_truth/test_uxp_700d_1_i.py
- unit_tests/product_truth/test_uxp_700d_3_ii.py
- unit_tests/product_truth/test_uxp_700e_1_i.py
- unit_tests/product_truth/test_uxp_700e_2.py
- unit_tests/product_truth/test_uxp_700e_2_i.py
- unit_tests/product_truth/test_uxp_700e_3.py
- unit_tests/product_truth/test_uxp_700e_3_i.py
---

# Product-truth steps carry a one-sentence description and an actor kind

## Actor / Goal

In order to read a product-truth flow as a description of WHAT happens, a
person reviewing a journey in Atlas or in the JSON needs every step and
branch to say what happens in one plain sentence and what kind of actor
runs it, so that the record stays short, stays true, and does not go stale when
the implementation changes.

## Context

Implements kernel decision `dec-7b1dcfd47f85cf0a`, chosen by the user:
"Rename the product-truth flow step field `human` to `description`, holding
ONE plain sentence of what happens, and add an `actor_kind` field
(deterministic | jev | llm | human)."

Why:

- The user found the field name `human` confusing: it reads like a boolean
  "a human does this step", not "the human-readable text".
- The field had grown into engineering narrative: code paths, symbol and
  function names, build status, design notes, and a generated contract
  section appended behind a marker. That bloats flows (median 410
  characters, up to 2,473) and goes stale as code moves.
- Product truth must describe WHAT happens, not HOW it is implemented. The
  structured contract metadata (`io_contracts`, `contract_definitions`)
  already carries the handoff detail and Atlas already renders it.
- ADR-053 names the four mechanisms that do work in this project:
  deterministic code, Jev, an LLM agent, and a human. `actor_kind` records
  which of the four runs a step, next to the existing free-text `agent`.

Amends the criteria that encoded the old rule: UXP-542-1 (authoring
standard), UXP-523-3 and UXP-523-4 (Atlas step detail), UXP-700e-2-ii
(generator-owned contract text).

## Scope

1. Schema: rename the step and branch field `human` to `description`;
   add `actor_kind` (enum `deterministic | jev | llm | human`), required on
   steps. Mirror the change in the Atlas view schemas.
2. Generator: stop writing a generated contract section into any text field.
   Compatibility `consumes`/`produces` labels stay generated.
3. Validator gates (errors): a description length bound and a code-token
   lint (no backticks, file paths or extensions, snake_case / dotted /
   camelCase identifiers, call parentheses, ticket / AC / ADR ids, build
   status words, more than one sentence).
4. Atlas: show `description` as the step text and `actor_kind` as a badge
   beside the agent; render contract detail only from `io_contracts`.
5. Migration of all 27 flows: rename, fill `actor_kind`, rewrite every
   description to one plain sentence of what happens.
6. Docs and the flow-author prompt: the never-list and the "what goes where"
   field guide; regenerate built copies.
7. Amend the ACs above; update every reader and test of the old field.

## Out of Scope

- Changing the free-text `agent` values or normalising them to registry ids.
- Rewriting `summary`, `label`, `condition` or `acceptance_scenarios`.
- Historical records (ADRs, changelogs, reports) that mention `human`.
- The kernel's own human-interaction contracts, where "human" means a
  person answering a kernel question; unrelated to this field.

## Sign-offs

- [x] test-writer — 2026-10-09
- [x] python-coder — 2026-10-09
- [x] frontend-coder — 2026-10-09
- [x] llm-expert — 2026-10-09
- [x] documentation-expert — 2026-10-09
- [x] pr-reviewer — 2026-10-09
- [ ] commit
- [ ] pull-request

## Comments

### 2026-10-09 17:30 — python-coder (status: ok)
feedback-id: fb_2026-10-09_66b760e0
Implemented dec-7b1dcfd47f85cf0a across schema, generator/validator, Atlas, the 27 flows, docs, the flow-author template and ACs UXP-523-3, UXP-523-4, UXP-700e-2-ii and UXP-542-1 (nothing committed).
- **Gates (errors):** a step description is at most 200 characters and one sentence; a code-token lint rejects backticks, paths and file extensions, identifiers, call parens, ids and build-status words.
- **actor_kind:** 304 nodes (deterministic 169, llm 60, human 46, jev 29). The kernel lookup run-97b1dc8db6604c36 (where Jev is called) settled two inconsistent calls in decision-forming: split-detect and research-options are jev.
- **Tests:** test_product_truth_descriptions.py (10 tests, 42 subtests), actor-kind.test.ts, 5 drawer tests and a read-both test for the knowledge flow reader. Atlas tsc and vitest are clean (128 tests).

### 2026-10-09 18:10 — pr-reviewer (status: ok)
feedback-id: fb_2026-10-09_40b0849e
No blocking defects. Fixed: the one-sentence gate no longer trips on prose abbreviations (e.g., i.e., vs., etc.; controls added), and decision-forming split-detect and research-options now name Jev's part, matching their jev actor_kind.
- **Left as is, by judgement:** steps that describe the outcome of a person's choice keep actor_kind human; Atlas does not fall back to a legacy human key, since every flow is migrated; a non-dict step is reported by the schema check before the description gate runs.
- **Follow-up:** free-text `agent` values still hold never-list content (e.g. criteria-library publish, "command not yet defined"); not gated in this change.
