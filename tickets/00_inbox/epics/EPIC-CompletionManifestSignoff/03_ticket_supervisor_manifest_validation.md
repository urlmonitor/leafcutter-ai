---
title: "Add §2.3 manifest validation to ticket-supervisor"
status: todo
components:
  - build_pipeline
created: 2026-05-28
depends_on:
  - 01_signoff_skill_manifest_section.md
  - 02_agent_default_checklists.md
priority: high
requires_diagram: false
requires_adr: false
agents:
  architect-review: needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
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

- [ ] architect-review
- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### architect-review
- [ ] Review the proposed §2.3 insertion point in the ticket-supervisor five-step loop (between status-tag parse and route-on-status) — confirm it does not break the existing ok/handoff/blocker/question branching
- [ ] Confirm the retry-once behaviour for malformed manifests is bounded (single retry only, then treat as malformed-blocker)
- [ ] Verify the checklist resolution order (agent defaults → ticket overrides → union) aligns with the building-epics skill dispatch contract

### documentation-expert
- [ ] Insert §2.3 into `templates/agents/ticket-supervisor.md` after the existing "parse comment status tag" step in the five-step loop description
- [ ] Document the validation algorithm: resolve expected checklist, parse manifest, check parity, downgrade-to-blocker on ok+false
- [ ] Document the malformed-manifest retry protocol (single retry, then blocker)
- [ ] Document the legacy graceful skip (absent manifest = warn, not block)
- [ ] Add a YAML example showing the supervisor's blocker payload when ok+false parity is violated

## Risk & Safety
- Touches money? No.
- Touches data? No.
- Reversibility? Doc-only edit to a template file. The validation step is additive to the supervisor loop and has a graceful degradation path for legacy tickets.
