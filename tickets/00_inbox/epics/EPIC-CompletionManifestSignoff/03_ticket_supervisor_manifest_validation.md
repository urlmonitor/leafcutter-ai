---
title: "Add §2.3 manifest validation to ticket-supervisor"
status: todo
components:
  - build_pipeline
created: 2026-05-28
depends_on:
  - 01_signoff_skill_manifest_section.md
  - 02_01_checklist_architect_review.md
  - 02_02_checklist_python_coder.md
  - 02_03_checklist_test_writer.md
  - 02_04_checklist_test_runner.md
  - 02_05_checklist_documentation_expert.md
  - 02_06_checklist_change_scope_reviewer.md
  - 02_07_checklist_pr_reviewer.md
  - 02_08_checklist_commit.md
  - 02_09_checklist_pull_request.md
  - 02_10_checklist_status_checker.md
  - 02_11_checklist_sql_coder.md
  - 02_12_checklist_frontend_coder.md
  - 02_13_checklist_sql_query.md
  - 02_14_checklist_adr_author.md
  - 02_15_checklist_architecture_diagram_author.md
  - 02_16_checklist_explanation_author.md
  - 02_17_checklist_how_to_author.md
  - 02_18_checklist_reference_author.md
  - 02_19_checklist_user_surface_smoker.md
priority: high
requires_diagram: false
requires_adr: false
agents:
  architect-review: signed_off
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: signed_off
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: needed
---

# 03: Add §2.3 manifest validation to ticket-supervisor

## Goal
In order to enforce that agents cannot declare success while leaving deliverables false, we need to add §2.3 manifest validation to the ticket-supervisor template: after parsing the status tag from a comment heading, parse the `completion_manifest:` block, cross-reference against the expected checklist, and reject ok+false parity violations.

## Context
Depends on ticket 01 (manifest format) and ticket 02 (agent checklists). The ticket-supervisor's five-step ticket loop currently reads the comment heading's status tag and routes on ok/handoff/blocker/question. §2.3 inserts a new validation step between "parse status tag" and "route on status":

**Resolution order for expected checklist:**
1. Take agent's `default_artifact_checklist` from its template frontmatter.
2. Merge with `artifact_checklist:` from ticket frontmatter (ticket 04), where ticket items extend or override agent defaults.
3. The union is the expected checklist for this invocation.

**Validation logic:**
- If manifest is absent: warn (legacy graceful skip), proceed normally.
- If manifest is malformed (bare `false` without nested object): retry once, asking agent to expand.
- If manifest is present and complete: cross-reference each item. If status tag is `ok` but any item has `result: false`, this is a parity violation — downgrade the status to `blocker` and surface the false items to the user with their `reason` and `remediation`.

## Acceptance Criteria
```gherkin
Given a phase agent returns ok status with a complete completion_manifest where all items are true
When ticket-supervisor reads the comment
Then it proceeds normally and routes to the next agent

Given a phase agent returns ok status but completion_manifest has one item with result: false
When ticket-supervisor reads the manifest
Then it downgrades the ok to a blocker, surfaces the false item's reason and remediation, and triggers failure adjudication

Given a phase agent returns a manifest with a bare false (not a nested object)
When ticket-supervisor reads the manifest
Then it retries the agent once with a request to expand the false item into result/reason/remediation

Given a phase agent returns a sign-off comment with no completion_manifest block
When ticket-supervisor reads the comment
Then it emits a warning and proceeds without blocking (legacy graceful skip)

Given a ticket with artifact_checklist in frontmatter and an agent with default_artifact_checklist
When ticket-supervisor resolves the expected checklist
Then the union of both lists is used for manifest cross-reference
```

## Sign-offs

- [x] architect-review — 2026-05-29 10:00
- [x] documentation-expert — 2026-05-29 10:05
- [x] pr-reviewer — 2026-05-29 10:10
- [x] commit — 2026-05-29 10:15
- [ ] pull-request

## Comments

### 2026-05-29 10:00 — architect-review (status: ok)
feedback-id: fb_2026-05-29_faade454
completion_manifest:
  blast_radius_assessed: true
  impact_classified: true
  architectural_note_written: true
Documentation-only change to `templates/agents/ticket-supervisor.md` (1 file, 1 component — build_pipeline). Classified as **small**: no always-large trigger fired, single component, no ADR required. The proposed §2.3 insertion point (between status-tag parse and route-on-status) is architecturally sound and does not break existing ok/handoff/blocker/question branching. Retry-once cap for malformed manifests is correctly bounded. Checklist resolution order (agent defaults → ticket overrides → union) aligns with the building-epics dispatch contract.

## Escalation

Branch: none
Reason: 1 file in build_pipeline component; no always-large trigger fired; no ADR or diagram needed.

### 2026-05-29 10:05 — documentation-expert (status: ok)
feedback-id: fb_2026-05-29_68ba86de
completion_manifest:
  section_inserted: true
  validation_algorithm_documented: true
  malformed_manifest_retry_documented: true
  legacy_graceful_skip_documented: true
  blocker_payload_yaml_example_added: true
Inserted §2.3 "Completion Manifest Validation" into `templates/agents/ticket-supervisor.md` after the disk-diff guard and parity check, and before the routing table. The section covers: (1) expected checklist resolution (agent defaults + ticket overrides → union), (2) three-case manifest parsing (absent/malformed/well-formed), (3) ok+false downgrade to blocker, and (4) YAML blocker payload example with `manifest_violations` list. All five acceptance criteria satisfied.

### 2026-05-29 10:10 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-29_2462be0a
completion_manifest:
  insertion_point_correct: true
  three_case_structure_complete: true
  blocker_payload_yaml_present: true
  no_regression_to_routing_table: true
  all_acceptance_criteria_covered: true
§2.3 insertion is well-placed and well-formed. All five Gherkin acceptance criteria are covered by the three-case structure (absent/malformed/well-formed). The routing table is preserved verbatim in §2.3 Step 4, with no regression to ok/handoff/blocker/question branching. Approved.

### 2026-05-29 10:15 — commit (status: ok)
feedback-id: fb_2026-05-29_396d44c3
completion_manifest:
  files_staged_by_explicit_path: true
  commit_created: true
  ticket_signed_off: true
Staged `templates/agents/ticket-supervisor.md` and the ticket file by explicit path (no git add .); committed to worktree branch `worktree-EPIC-CompletionManifestSignoff`. Pull-request phase skipped per caller instructions.

## Implementation Tasks

### architect-review
- [x] Review the proposed §2.3 insertion point in the ticket-supervisor five-step loop (between status-tag parse and route-on-status) — confirm it does not break the existing ok/handoff/blocker/question branching
- [x] Confirm the retry-once behaviour for malformed manifests is bounded (single retry only, then treat as malformed-blocker)
- [x] Verify the checklist resolution order (agent defaults → ticket overrides → union) aligns with the building-epics skill dispatch contract

### documentation-expert
- [x] Insert §2.3 into `templates/agents/ticket-supervisor.md` after the existing "parse comment status tag" step in the five-step loop description
- [x] Document the validation algorithm: resolve expected checklist, parse manifest, check parity, downgrade-to-blocker on ok+false
- [x] Document the malformed-manifest retry protocol (single retry, then blocker)
- [x] Document the legacy graceful skip (absent manifest = warn, not block)
- [x] Add a YAML example showing the supervisor's blocker payload when ok+false parity is violated

## Risk & Safety
- Touches money? No.
- Touches data? No.
- Reversibility? Doc-only edit to a template file. The validation step is additive to the supervisor loop and has a graceful degradation path for legacy tickets.
