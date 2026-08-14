---
title: "Spike E2 edges; ADR + canonical E2 authoring template and E1-wrap shim spec"
status: done
components:
  - supervisor_system
created: 2026-07-01
depends_on: []
priority: high
requires_diagram: true
requires_adr: true
files_touched:
  - docs/architecture/adrs/ADR-dual-engine-workflow-support.md
  - docs/reference/workflow-authoring-contract.md
agents:
  architect-review: signed_off
  test-writer: not_needed
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: signed_off
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
---

# 03: Canonical E2 contract — spike, ADR, and authoring template

## Actor / Goal

In order to port scripts correctly and reproducibly, we need the E2 authoring
contract pinned down empirically and recorded as an ADR + reference template,
so every port (05/06) and the build transform (04) follow one documented shape.

## Context

The port design has one empirically-unconfirmed question and several known
non-transparent edges. This ticket resolves them BEFORE any porting, and produces
the canonical template + E1-wrap shim spec that 04/05/06 consume. `quick-fix.js`
is the working E2 reference to mirror. This is a design/spike ticket: no workflow
behaviour changes ship here — only docs, an ADR, and (optionally) a throwaway
probe used to answer the open question.

## Acceptance Criteria

```gherkin
Scenario: result-surfacing confirmed
  Given the live E2 engine
  When a top-level-body workflow returns a value
  Then the ADR records exactly how E2 surfaces the result (final-expression vs
   trailing-global) with the probe evidence.

Scenario: non-transparent edges documented
  Then the reference doc enumerates the E1/E2 differences that CANNOT be made
   transparent: Date.now()/Math.random() ban on E2, parallel() 4096 cap,
   schema-enforcement asymmetry, prompt()-gate vs agent-mediated gate,
   and the workflow() leaf-invariant — each with the required handling convention.

Scenario: canonical template published
  Then docs/reference/workflow-authoring-contract.md contains a copy-pasteable
   E2 canonical skeleton and the E1-wrap shim pattern (callAgent adapter, engine
   detection predicate), consistent with quick-fix.js.

Scenario: decision recorded
  Then an ADR records the "canonical-E2 + build-time-wrap-for-E1, no LLM fallback"
   decision, its alternatives, and consequences.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | ADR-030 §Probe Evidence records top-level-return result-surfacing with verbatim probe output (runWasCalled=false; top-level object returned as result) | |
| AC-2 | | workflow-authoring-contract.md §5 enumerates all 5 non-transparent edges with handling conventions | |
| AC-3 | | workflow-authoring-contract.md §2 has copy-pasteable E2 skeleton; §3 has E1-wrap shim pattern (callAgent adapter + engine-detection predicate) | |
| AC-4 | | ADR-030 §Decision records canonical-E2 + build-time-wrap + no-LLM-fallback decision with alternatives and consequences | |

## Sign-offs
- [x] architect-review — 2026-07-01 14:30
- [x] python-coder — 2026-07-01 15:00
- [x] documentation-expert — 2026-07-01 16:00
- [x] pr-reviewer — 2026-07-01 17:00
- [x] commit — 2026-07-01 17:15
- [x] pull-request — 2026-07-01 17:45

## Comments

### 2026-07-01 14:30 — architect-review (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  architectural_approach_reviewed: true
  e2_canonical_pattern_verified: true
  adr_scope_approved: true
  reference_doc_scope_approved: true
  data_flow_diagram_requirement_endorsed: true
Reviewed the proposed architectural approach for ticket 03. The E2-canonical + build-time-wrap-for-E1 (no LLM fallback) decision is well-grounded: `quick-fix.js` demonstrates the E2 top-level-body contract empirically (phase(), agent(), parallel(), log(), args globals; top-level return surfaces the result). The four ACs are coherent and tightly scoped to documentation outputs only — no workflow behavior changes ship in this ticket. ADR-030 is the correct next number (ADR-016 is the last in the current list). The non-transparent-edges list (Date.now()/Math.random() ban, parallel() 4096/~16 cap, schema-enforcement asymmetry, prompt-gate vs agent-mediated gate, workflow() leaf-invariant) is complete and correctly identified. The E1-wrap shim pattern (engine-detection predicate + callAgent adapter) is a sound compatibility strategy that avoids LLM fallback ambiguity. No architectural blockers — approved for documentation-expert to proceed.

### 2026-07-01 15:00 — python-coder (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  data_flow_diagram_created: true
  diagram_frontmatter_valid: true
  mermaid_flowchart_shows_build_time_transform: true
  mermaid_flowchart_shows_runtime_routing: true
  e1_e2_api_differences_documented: true
Created `docs/architecture/diagrams/df-001-dual-engine-workflow-build-transform.md` — a `data_flow` type Mermaid flowchart showing both the build-time E2 → E1-shim transform and the runtime engine-detection predicate routing. Frontmatter validated against `config/diagram_types.json` (type `data_flow` requires `related_code`, which is present). The diagram covers all five required elements: E2 author source, build-time transformer, E2 native variant, E1 shim variant (with callAgent adapter and engine-detection predicate), and runtime routing. Non-transparent edges are enumerated in the Key Design Constraints section.

### 2026-07-01 16:00 — documentation-expert (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  ADR_030_authored: true
  adr_probe_evidence_recorded: true
  adr_decision_canonical_e2_build_time_wrap_no_llm_fallback: true
  adr_alternatives_considered: true
  adr_non_transparent_edges_with_conventions: true
  reference_doc_authored: true
  reference_e2_skeleton_copy_pasteable: true
  reference_e1_shim_pattern_with_callAgent_adapter: true
  reference_primitive_mapping_table: true
  reference_5_non_transparent_edges_with_conventions: true
  reference_quick_reference_globals_table: true
  ac_coverage_table_filled: true
Authored `docs/architecture/adrs/ADR-030-dual-engine-workflow-support.md` recording the canonical-E2 + build-time-wrap + no-LLM-fallback decision, verbatim probe evidence (runWasCalled=false; top-level return surfaced as result), all five non-transparent edges with handling conventions, and three rejected alternatives. Authored `docs/reference/workflow-authoring-contract.md` with copy-pasteable E2 skeleton, E1-wrap shim pattern (callAgent adapter + engine-detection IIFE), complete primitive mapping table (E1 vs E2, 12 rows), and all five non-transparent edges with handling conventions. All four ACs covered: AC-1 (probe evidence in ADR), AC-2 (5 edges in reference §5), AC-3 (skeleton in §2, shim in §3), AC-4 (decision in ADR §Decision).

### 2026-07-01 17:00 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  ac1_result_surfacing_evidenced: true
  ac2_five_non_transparent_edges_enumerated: true
  ac3_e2_skeleton_and_e1_shim_present: true
  ac4_decision_alternatives_consequences_recorded: true
  diagram_frontmatter_data_flow_type_valid: true
  diagram_related_code_field_present: true
  ticket_ac_coverage_table_implementation_column_filled: true
  signoffs_consistent_with_frontmatter_agents_map: true
Reviewed staged diff against all 4 ACs. AC-1: ADR-030 §Probe Evidence records verbatim probe output (runWasCalled=false; top-level object returned as result). AC-2: workflow-authoring-contract.md §5 enumerates all 5 non-transparent edges (Date.now ban, parallel cap, schema asymmetry, user gate asymmetry, workflow() leaf-invariant) with handling conventions. AC-3: §2 has copy-pasteable E2 skeleton; §3 has E1-wrap shim with callAgent adapter and engine-detection IIFE. AC-4: ADR §Decision records canonical-E2 + build-time-wrap + no-LLM-fallback with 3 alternatives and consequences. Diagram frontmatter has diagram_type: data_flow and related_code field as required by config/diagram_types.json. No high-confidence blockers found.

### 2026-07-01 17:15 — commit (status: ok)
feedback-id: (pending)
completion_manifest:
  staged_files_verified: true
  pre_commit_hooks_passed: true
  description_field_fix_applied: true
  commit_sha: 6de25c42
  files_committed: 4
Committed 4 deliverables (ADR-030, workflow-authoring-contract.md, df-001 data_flow diagram, ticket) in commit 6de25c42. Pre-commit hook `check-description-field` caught a missing `description:` frontmatter field in `workflow-authoring-contract.md` — fixed inline and re-staged before the commit succeeded. All other hooks passed. The `.pre-commit-config.yaml` symlink was established in the worktree root to resolve the pre-commit config gap.

### 2026-07-01 17:45 — pull-request (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  pr_exists_verified: true
  gh_auth_urlmonitor_confirmed: true
  branch_pushed_to_origin: true
  ticket_signoff_applied: true
Verified PR #198 (EPIC-DualEngineWorkflowSupport) exists and is open. Confirmed gh auth is urlmonitor. Pushed branch bd521025..6ab7b1dc to origin/EPIC-DualEngineWorkflowSupport successfully. Applied pull-request sign-off to ticket frontmatter and Sign-offs checklist.

## Implementation Tasks
- [x] Run a zero-side-effect probe to confirm how E2 surfaces run()/top-level return values
- [x] Author ADR-dual-engine-workflow-support (decision, alternatives, consequences)
- [x] Author docs/reference/workflow-authoring-contract.md (E2 canonical skeleton + E1-wrap shim + per-primitive mapping table + non-transparent edges)
- [x] Add a data_flow diagram of source -> build transform -> E1/E2 variants

## Risk & Safety
- Touches money? No.
- Touches data? No — docs/ADR only. The one runtime probe is zero-side-effect.
