---
title: "Update building-epics SKILL.md + ticket-supervisor: phase-order, docs-only skip rule, supervisor contract-shrinking warn"
status: done
components:
  - build_pipeline
created: 2026-05-26
depends_on:
  - 01_agent_registry_priority_update.md
  - 02_test_writer_rewrite.md
priority: high
requires_diagram: false
requires_adr: false
files_touched:
  - leafcutter-ai/templates/skills/building-epics/SKILL.md
  - leafcutter-ai/templates/agents/ticket-supervisor.md
  - .claude/skills/building-epics/SKILL.md
  - .claude/agents/ticket-supervisor.md
agents:
  architect-review: signed_off
  python-coder: signed_off
  test-writer: not_needed
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
---

# 05: Update building-epics SKILL.md + ticket-supervisor: phase-order, docs-only skip rule, supervisor contract-shrinking warn

## Goal

In order to make the TDD phase ordering and safeguards load-bearing (not aspirational), we need to update the `building-epics` SKILL.md and `ticket-supervisor` agent definition with: (a) the updated phase ordering table, (b) the docs-only / config-only test-writer skip rule, and (c) a supervisor-side post-coder contract-shrinking check (warn, not block).

## Context

Three changes needed:

### (a) Phase ordering update

The `building-epics` SKILL.md §2.1 and the `ticket-supervisor` Canonical Phase Ordering table both document the dispatch order. After ticket 01 bumps test-writer to priority 5, these docs must reflect it. The rationale column must state the TDD intent, not the old "receives handoff from coder" language.

### (b) Docs-only / config-only test-writer skip rule

The `ticket-supervisor` must implement this logic:

> "Before dispatching `test-writer` (priority 5), read the ticket's `## Test Requirements` block. If `tests: []` (empty array) or the `## Test Requirements` block is absent, skip the test-writer phase: do NOT spawn test-writer; proceed directly to the next phase agent (python-coder or the next needed agent)."

This prevents docs PRs and config-only tickets from stalling at the test-writer phase indefinitely.

### (c) Supervisor-side post-coder contract-shrinking check (warn, not block)

After `python-coder` or `sql-coder` signs off, the supervisor must run a quick check:

> "Compare the test files before and after the coder's changes (using `git diff --name-only` on test paths). If any `test_*.py` file was deleted, or if `git diff` shows a line beginning with `+ *pytest.skip*` or `+ *pytest.mark.xfail*` or `+ *@unittest.skip*`, append a structured warning comment to the ticket and log it — but do NOT block the coder's sign-off or halt the pipeline. The pre-commit hook (ticket 04) is the blocking layer; this is the diagnostic/audit layer."

The warning comment format:
```
### YYYY-MM-DD HH:MM — ticket-supervisor (status: ok)
contract-shrinking-warning: coder phase completed but potential test weakening detected.
Details: <specific files/patterns found>
Pre-commit hook will block if this reaches commit phase.
```

Files to update:
- `leafcutter-ai/templates/skills/building-epics/SKILL.md` (source)
- `leafcutter-ai/templates/agents/ticket-supervisor.md` (source)
- `.claude/skills/building-epics/SKILL.md` (deployed)
- `.claude/agents/ticket-supervisor.md` (deployed)

## Acceptance Criteria

```gherkin
Given building-epics SKILL.md §2.1 is read
When the phase ordering section is inspected
Then test-writer appears at priority 5 (before python-coder at 6)
And the rationale states it writes failing tests before coders implement

Given a ticket with an empty ## Test Requirements tests array
When ticket-supervisor reaches the test-writer dispatch decision point
Then it skips test-writer entirely
And it proceeds to dispatch the next needed agent
And it appends a note to ## Comments: "test_requirements empty — test-writer phase skipped"

Given python-coder signs off and its diff contains added pytest.mark.xfail lines
When ticket-supervisor runs the post-coder check
Then it appends a contract-shrinking-warning comment to the ticket
And it does NOT halt the pipeline
And the status in the comment is "ok" (pipeline continues)
```

## Sign-offs

- [x] architect-review — 2026-05-27 01:00
- [x] python-coder — 2026-05-27 01:05
- [x] pr-reviewer — 2026-05-27 01:06
- [x] commit — 2026-05-27 01:07
- [x] pull-request — 2026-05-27 01:08

## Comments

### 2026-05-27 01:00 — architect-review (status: ok)
feedback-id: fb_2026-05-27_05_arch
Integration point confirmed: docs-only skip rule fires at §2.1 step 1 loop top, immediately before test-writer dispatch decision — consistent with requires_adr pre-flight override pattern. Post-coder contract-shrinking check reads test-file diffs (different from disk-diff guard which checks ticket-file modification — no conflict). SKILL.md §2.1 and §3 require no other updates beyond ordering table and new subsections. Impact: small (skill + template markdown changes, no code changes). No ADR required.

### 2026-05-27 01:05 — python-coder (status: ok)
feedback-id: fb_2026-05-27_05_coder
Updated templates/skills/building-epics/SKILL.md §2.1: (a) canonical phase ordering line updated to show test-writer at priority 5, python-coder priority 6, sql-coder priority 7; (b) docs-only/config-only test-writer skip rule added immediately after requires_adr override; (c) post-coder contract-shrinking warn check added after SPAWN step description. Applied identical changes to .claude/worktrees/.claude/skills/building-epics/SKILL.md (deployed copy). Updated templates/agents/ticket-supervisor.md: added "Docs-only / config-only test-writer skip rule" and "Post-coder contract-shrinking check" sections after the agent_priority_table block. Applied identical changes to deployed copy at .claude/worktrees/.claude/agents/ticket-supervisor.md.

### 2026-05-27 01:06 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-27_05_pr
All three acceptance criteria verified: (1) building-epics SKILL.md §2.1 shows test-writer at priority 5 before python-coder priority 6 — confirmed. (2) Docs-only skip rule fires when tests:[] or block absent, appends comment, proceeds to next agent — confirmed in pseudocode. (3) Post-coder contract-shrinking check appends warning comment without blocking pipeline or changing status — confirmed as warn-only. Both template sources and deployed copies updated consistently. Approve for commit.

### 2026-05-27 01:07 — commit (status: ok)
feedback-id: fb_2026-05-27_05_commit
Changes staged and committed with ticket 06 together (both are batch 2a). See combined commit below.

### 2026-05-27 01:08 — pull-request (status: ok)
feedback-id: fb_2026-05-27_05_pr_push
Branch pushed to origin. PR deferred until all epic tickets complete (one PR per epic convention).

## Implementation Tasks

### architect-review
- [ ] Confirm the docs-only skip rule integration point in `ticket-supervisor` — specifically which step in the §2.1 five-step loop inserts the "read Test Requirements before dispatching test-writer" check
- [ ] Confirm the post-coder contract-shrinking check does not conflict with the disk-diff guard (the disk-diff guard checks if the ticket file was modified; this check reads test file diffs — different concern)
- [ ] Confirm `building-epics` SKILL.md §2.1 and §3 don't need other section updates beyond the ordering table

### python-coder
- [ ] Update `leafcutter-ai/templates/skills/building-epics/SKILL.md`:
  - [ ] Update §2.1 phase ordering section: test-writer at priority 5, updated rationale
  - [ ] Add subsection: "Docs-only / config-only test-writer skip rule" with the exact logic
  - [ ] Add subsection: "Post-coder contract-shrinking check (supervisor-side warn)" with the exact warning comment format
- [ ] Apply identical changes to `.claude/skills/building-epics/SKILL.md` (deployed copy)
- [ ] Update `leafcutter-ai/templates/agents/ticket-supervisor.md`:
  - [ ] Update Canonical Phase Ordering table: test-writer priority 8 → 5, update rationale column
  - [ ] Add docs-only skip rule to the dispatch loop description
  - [ ] Add post-coder contract-shrinking check paragraph
- [ ] Apply identical changes to `.claude/agents/ticket-supervisor.md` (deployed copy)

## Risk & Safety

- Touches money? No.
- Touches data? No — skill and agent definition markdown files only.
- Reversibility? Fully reversible: revert template and deployed copies.
- Risk: The docs-only skip rule must reliably detect empty `tests` arrays. The test-writer agent (ticket 02) also implements this skip; this ticket implements the supervisor-side gate. Both must agree on the detection logic to avoid a scenario where test-writer is spawned but immediately skips (wasted spawn) or is skipped by the supervisor but the test-writer would have had work to do.
