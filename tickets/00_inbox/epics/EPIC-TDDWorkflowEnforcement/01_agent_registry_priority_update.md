---
title: "Update agent_registry.json: test-writer priority 8 → 5 (before coders)"
status: todo
components:
  - build_pipeline
created: 2026-05-26
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
agents:
  architect-review: signed_off
  python-coder: signed_off
  test-writer: not_needed
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
---

# 01: Update agent_registry.json: test-writer priority 8 → 5 (before coders)

## Goal

In order to enforce test-first development, we need to update the canonical `priority` field for `test-writer` in `agent_registry.json` (and every build output that mirrors it) so that `ticket-supervisor` dispatches `test-writer` **before** `python-coder` and `sql-coder`, while preserving the full existing ordering chain.

## Context

Current confirmed priority values (read from `leafcutter-ai/config/agent_registry.json` at epic authoring time):

| Agent | Current priority | New priority |
|---|---|---|
| `status-checker` | 1 | 1 (unchanged) |
| `adr-author` | 2 | 2 (unchanged) |
| `architecture-diagram-author` | 3 | 3 (unchanged) |
| `architect-review` | 4 | 4 (unchanged) |
| **`test-writer`** | **8** | **5** |
| `python-coder` | 6 | 6 (unchanged) |
| `sql-coder` | 7 | 7 (unchanged) |
| `test-runner` | 9 | 9 (unchanged) |
| `documentation-expert` | 10 | 10 (unchanged) |
| `change-scope-reviewer` | 10 | 10 (unchanged) |
| `pr-reviewer` | 11 | 11 (unchanged) |
| `user-surface-smoker` | 11.5 | 11.5 (unchanged) |
| `commit` | 12 | 12 (unchanged) |
| `pull-request` | 13 | 13 (unchanged) |

The new ordering chain is: `status-checker (1) → adr-author (2) → architecture-diagram-author (3) → architect-review (4) → test-writer (5) → python-coder (6) → sql-coder (7) → test-runner (9) → docs/review (10–11) → commit/PR (12–13)`.

This is the first ticket of EPIC-TDDWorkflowEnforcement. All later tickets depend on this priority assignment being in place.

Files to update:
1. `leafcutter-ai/config/agent_registry.json` — the source of truth.
2. `.claude/agents/ticket-supervisor.md` — contains a hardcoded "Canonical Phase Ordering" table that must be kept in sync. (The `.gemini/` mirror, if it exists, must also be updated.)
3. `leafcutter-ai/templates/agents/ticket-supervisor.md` — the template source that `build.py` compiles into `.claude/agents/ticket-supervisor.md`; this is the real source of truth for the supervisor template.

Note: `build.py` regenerates `.claude/` from `leafcutter-ai/templates/` at install time. Updating only the template is the durable fix; updating the deployed `.claude/` copy ensures immediate effect on the running workspace.

## Acceptance Criteria

```gherkin
Given agent_registry.json is read
When the test-writer entry is inspected
Then its "priority" field equals 5

Given ticket-supervisor.md Canonical Phase Ordering table is read (both template and deployed copy)
When the test-writer row is inspected
Then it shows priority 5 with rationale "Writes failing tests before coders implement; ensures tests exist and are red before any production code is written"

Given the ordering table is read in full
When all priorities are listed in ascending order
Then the sequence is: status-checker(1) adr-author(2) architecture-diagram-author(3) architect-review(4) test-writer(5) python-coder(6) sql-coder(7) test-runner(9) documentation-expert/change-scope-reviewer/explanation-author/how-to-author/reference-author(10) pr-reviewer(11) user-surface-smoker(11.5) commit(12) pull-request(13)
```

## Sign-offs

- [x] architect-review — 2026-05-27 00:00
- [x] python-coder — 2026-05-27 00:01
- [x] pr-reviewer — 2026-05-27 00:02
- [ ] commit
- [ ] pull-request

## Comments

### 2026-05-27 00:00 — architect-review (status: ok)
feedback-id: fb_2026-05-27_858ad9cf
Verified no priority 5 collision in agent_registry.json (priority 5 slot is free). The bump from 8 → 5 is safe. Approved rationale wording: "Writes failing tests before coders implement; ensures tests exist and are red before any production code is written". Impact classification: small (config/template files only, single component build_pipeline, no always-large triggers). No ADR required, no diagram required.

### 2026-05-27 00:01 — python-coder (status: ok)
feedback-id: fb_2026-05-27_915b9f13
Updated config/agent_registry.json: test-writer priority 8→5, priority_rationale updated. Updated deployed .claude/agents/ticket-supervisor.md Canonical Phase Ordering table: added test-writer at priority 5 (before python-coder), updated test-runner rationale. Template source uses {{agent_priority_table}} which auto-generates from registry at build time — registry is the canonical source. Ran build.py --validate-only: Config validation complete (no files written). No priority 5 collision confirmed.

### 2026-05-27 00:02 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-27_28f73923
All acceptance criteria verified: test-writer priority=5 in registry (no collision), rationale wording correct, full ordering chain matches spec (status-checker(1)→adr-author(2)→architecture-diagram-author(3)→architect-review(4)→test-writer(5)→python-coder(6)→sql-coder/sql-query(7)→test-runner(9)→docs(10)→pr-reviewer(11)→user-surface-smoker(11.5)→commit(12)→pull-request(13)). Deployed ticket-supervisor table reflects new ordering. Change is minimal and reversible. Approve for commit.

## Implementation Tasks

### architect-review
- [x] Confirm that bumping test-writer to priority 5 does not create a conflict with any other agent that currently occupies priority 5 (verify registry — currently none do)
- [x] Confirm the `priority_rationale` wording for test-writer (new TDD-context rationale)

### python-coder
- [x] In `leafcutter-ai/config/agent_registry.json`: find the `test-writer` entry and change `"priority": 8` to `"priority": 5`; update `"priority_rationale"` to "Writes failing tests before coders implement; ensures tests exist and are red before any production code is written"
- [x] In `leafcutter-ai/templates/agents/ticket-supervisor.md`: update the Canonical Phase Ordering table — move test-writer row from priority 8 to priority 5, update rationale column (registry is the source of truth; {{agent_priority_table}} placeholder auto-generates from registry at build time)
- [x] In `.claude/agents/ticket-supervisor.md`: apply the identical table update (deployed copy — updated directly on disk)
- [x] Verify no other agent in the registry uses priority 5 (would be a collision)
- [x] Run `python leafcutter-ai/scripts/build.py --validate` (if available) to confirm no schema errors after the change

## Risk & Safety

- Touches money? No.
- Touches data? No — config/template files only.
- Reversibility? Fully reversible: revert the `priority` integer and `priority_rationale` string.
- Risk: If a second agent was already at priority 5, it would create an ambiguous ordering. The context table above confirms no collision exists at authoring time; implementer must re-verify at execution time.
