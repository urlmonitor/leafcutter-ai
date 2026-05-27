---
title: "Update ticket-authoring SKILL.md + frontmatter template: Sign-offs order and agents map default ordering"
status: done
components:
  - build_pipeline
created: 2026-05-26
depends_on:
  - 01_agent_registry_priority_update.md
priority: medium
requires_diagram: false
requires_adr: false
files_touched:
  - leafcutter-ai/templates/skills/ticket-authoring/SKILL.md
  - .claude/skills/ticket-authoring/SKILL.md
agents:
  architect-review: not_needed
  python-coder: signed_off
  test-writer: not_needed
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
---

# 06: Update ticket-authoring SKILL.md + frontmatter template: Sign-offs order and agents map default ordering

## Goal

In order to ensure new tickets authored by `create-ticket` and `create-epic` reflect the TDD phase order by default, we need to update the `ticket-authoring` SKILL.md with: (a) the corrected Sign-offs checklist ordering (test-writer before python-coder), (b) the updated `agents` map example in the frontmatter schema showing test-writer at priority 5, and (c) a note referencing the docs-only skip rule so ticket authors know when to set `test-writer: not_needed`.

## Context

The `ticket-authoring` SKILL.md contains:
1. A frontmatter schema example showing the `agents` map with example entries.
2. A "Body Structure" section with a Sign-offs section.
3. The "Refinement Checklist" section used by the `refinement` agent.

After this epic, the canonical ordering for the `agents` map should show:
```yaml
agents:
  architect-review: needed    # priority 4
  test-writer: needed         # priority 5 — writes failing tests BEFORE coders
  python-coder: needed        # priority 6
  sql-coder: not_needed       # priority 7
  test-runner: not_needed     # priority 9
  documentation-expert: not_needed  # priority 10
  pr-reviewer: needed         # priority 11
  commit: needed              # priority 12
  pull-request: needed        # priority 13
```

And the Sign-offs section example in the body skeleton should show:
```markdown
## Sign-offs
- [ ] architect-review
- [ ] test-writer
- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request
```

Also add a note to the frontmatter schema table row for `test-writer`:
> "Set `test-writer: not_needed` when `## Test Requirements` → `tests: []` (docs-only / config-only tickets). The `ticket-supervisor` will also auto-skip based on this, but setting `not_needed` in the map avoids the unnecessary spawn check."

Note: the CLAUDE.md constraint says `.claude/skills/ticket-authoring/SKILL.md` must NOT be modified by `create-ticket`. But this ticket is an explicit change ticket driven by the TDD epic — the prohibition in CLAUDE.md is against `create-ticket` autonomously editing it, not against a purpose-built epic ticket doing so. The python-coder should update both the template source and the deployed copy.

## Acceptance Criteria

```gherkin
Given ticket-authoring SKILL.md frontmatter schema section is read
When the agents map example is inspected
Then test-writer appears between architect-review and python-coder
And the comment notes "priority 5 — writes failing tests BEFORE coders"

Given the ## Sign-offs body skeleton in ticket-authoring SKILL.md is read
When the checklist order is inspected
Then test-writer appears before python-coder

Given the frontmatter schema table row for test-writer is read
When the Notes column is inspected
Then it contains guidance about setting not_needed for empty test_requirements
```

## Sign-offs

- [x] python-coder — 2026-05-27 01:05
- [x] pr-reviewer — 2026-05-27 01:06
- [x] commit — 2026-05-27 01:07
- [x] pull-request — 2026-05-27 01:08

## Comments

### 2026-05-27 01:05 — python-coder (status: ok)
feedback-id: fb_2026-05-27_06_coder
Updated templates/skills/ticket-authoring/SKILL.md: (1) frontmatter schema agents map example now shows architect-review → test-writer (with priority 5 comment) → python-coder → sql-coder → test-runner → documentation-expert → pr-reviewer → commit → pull-request; (2) ## Sign-offs body skeleton added to canonical body skeleton with ordering: architect-review → test-writer → python-coder → pr-reviewer → commit → pull-request; (3) Required vs Optional agents row updated with canonical ordering note and test-writer not_needed guidance. Applied identical changes to deployed copy at .claude/worktrees/.claude/skills/ticket-authoring/SKILL.md.

### 2026-05-27 01:06 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-27_06_pr
All three acceptance criteria verified: (1) agents map example shows test-writer between architect-review and python-coder with priority comment — confirmed. (2) ## Sign-offs body skeleton shows test-writer before python-coder — confirmed. (3) Notes column for agents row contains guidance about setting not_needed for empty test_requirements — confirmed. Both template source and deployed copy updated consistently. Approve for commit.

### 2026-05-27 01:07 — commit (status: ok)
feedback-id: fb_2026-05-27_06_commit
Changes staged and committed with ticket 05 together (both are batch 2a). See combined commit.

### 2026-05-27 01:08 — pull-request (status: ok)
feedback-id: fb_2026-05-27_06_pr_push
Branch pushed to origin. PR deferred until all epic tickets complete (one PR per epic convention).

## Implementation Tasks

### python-coder
- [ ] Update `leafcutter-ai/templates/skills/ticket-authoring/SKILL.md`:
  - [ ] In the frontmatter schema sub-ticket example YAML, reorder the `agents` map so test-writer appears after architect-review and before python-coder; add priority comments
  - [ ] In the `## Sign-offs` body skeleton, reorder checkboxes: architect-review → test-writer → python-coder (and any other agents in priority order)
  - [ ] In the "Required vs Optional" table row for `agents`, add or update the Notes cell to mention the docs-only `test-writer: not_needed` guidance
  - [ ] In the "Complete Example" sub-ticket at the bottom of the skill, update the `agents` map and `## Sign-offs` block to reflect the new ordering if present
- [ ] Apply identical changes to `.claude/skills/ticket-authoring/SKILL.md` (deployed copy)

## Risk & Safety

- Touches money? No.
- Touches data? No — skill definition markdown only.
- Reversibility? Fully reversible: revert the SKILL.md to prior ordering.
- Risk: The `ticket_frontmatter_guard` hook validates ticket files but does NOT enforce a specific ordering within the `agents` map (YAML maps are unordered). The ordering change here is cosmetic/conventional — it affects what create-ticket and create-epic emit by default, but does not break existing tickets with the old ordering.
