# Retrospective: EPIC-TDDWorkflowEnforcement

**Date**: 2026-05-27
**Epic**: EPIC-TDDWorkflowEnforcement
**Tickets**: 8
**Status**: Complete

---

## What Was Built

This epic flipped the leafcutter build pipeline to true Test-Driven Development
by enforcing a "test-first" ordering for all agentic Python code tickets:

1. **Ticket 01** — `test-writer` priority bumped from 8 to 5 in `agent_registry.json`
2. **Ticket 02** — `test-writer` agent rewritten: test-FIRST role, `red_baseline` capture contract, docs-only skip rule
3. **Ticket 03** — `python-coder` and `sql-coder` updated with TDD success gate (read `red_baseline`, make it green) and contract-shrinking prohibition
4. **Ticket 04** — `check_contract_shrinking.py` pre-commit hook: blocks commits with test weakening + production code changes concurrent
5. **Ticket 05** — `building-epics` SKILL.md and `ticket-supervisor` updated: phase-order, docs-only skip rule, post-coder contract-shrinking warn
6. **Ticket 06** — `ticket-authoring` SKILL.md updated: agents map ordering, Sign-offs skeleton, `not_needed` guidance for `test-writer`
7. **Ticket 07** — ADR-004, `docs/explanation/tdd-workflow.md`, `docs/how-to/writing-a-tdd-ticket.md` authored
8. **Ticket 08** — `EPIC-SQLTDDEnforcement` stub created in `tickets/00_inbox/epics/`

---

## What Went Well

### Batch parallelism worked correctly

Tickets 04, 05, and 06 were identified as parallel-safe (disjoint `files_touched`
sets) and executed together in batch 2a. Ticket 02 ran serially in batch 2b
(missing `files_touched` = conservative default). No file conflicts occurred.

### Pre-flight fix caught early

The `Master_Plan.md` was missing the `## Key Design Decisions` heading required
by the epic-supervisor pre-flight gate. This was caught and fixed before any ticket
was dispatched — the gate is working as intended.

### Red-baseline TDD loop validated in ticket 04

Ticket 04 demonstrated the TDD flow it was introducing: `test-writer` first wrote
7 failing tests (`red_baseline` captured), then `python-coder` created
`check_contract_shrinking.py` and made all 7 tests green. The TDD loop proved itself
by being used to build the enforcement layer.

### Three-layer contract-shrinking guard is complete

All three layers are now in place and consistent:
- Hook (`check_contract_shrinking.py`) — blocking
- Supervisor warn (post-coder check) — advisory
- Agent definitions (`python-coder.md`, `sql-coder.md`) — honor-system

### Docs-only skip rule covers both layers

The skip rule is implemented in both `test-writer` agent definition AND in the
`ticket-supervisor` dispatch loop. Whichever fires first takes precedence, and they
agree on the detection logic (empty `tests:` array or absent block).

---

## Friction Points

### Context window compaction mid-drive (ticket 04 → 05 handoff)

The supervisor's context was compacted between ticket 04's completion and the start
of ticket 05/06. The summary was accurate and the session resumed correctly, but
the compaction boundary created a brief handoff moment. No work was lost.

### `Master_Plan.md` missing required heading

The `## Key Design Decisions` heading was required by the pre-flight gate but absent
in the initial `Master_Plan.md`. All decisions were documented in prose but lacked
the required `##`-level heading. This is a gap in `create-epic` — it should scaffold
the heading automatically.

**Action item**: `create-epic` should include a `## Key Design Decisions` heading
scaffold in the `Master_Plan.md` template by default.

### Deployed copy vs. template source distinction

Several tickets updated both `templates/...` (git-tracked source) and
`.claude/worktrees/.claude/...` (deployed copy outside the worktree's git). The
deployed copies are not tracked by the worktree's git, only by the main repo's git.
This means `git diff --stat` only shows the template files, not the deployed copies.

**Recommendation**: Consider a `build.py` deployment step that compiles templates
→ deployed copies as part of the commit hook, making the deployed state always
derivable from the templates.

### Ticket 05 `depends_on 02` was a late-stage dependency

Ticket 05 (`building-epics` skill update) listed `depends_on: [02_test_writer_rewrite.md]`
in its frontmatter. This meant it could not run in parallel with ticket 04 (which
had no dependency on 02). In practice, ticket 05's content did not actually depend
on the test-writer agent being complete — it only depended on the priority decision
(ticket 01). The dependency could have been tightened to `depends_on: [01]` to
allow an earlier parallel run.

---

## Metrics

| Metric | Value |
|---|---|
| Tickets completed | 8 of 8 |
| Tickets blocked | 0 |
| User escalations | 0 |
| Phase retries | 0 |
| Commits | 7 (one per ticket or ticket batch) |
| Files modified | ~15 (templates + deployed copies + docs + tests) |
| New files created | 7 (hook script, tests, ADR-004, explanation doc, how-to guide, sql-epic stub, retro) |

---

## Follow-on Epics

- **EPIC-SQLTDDEnforcement** (`tickets/00_inbox/epics/EPIC-SQLTDDEnforcement/`) —
  extend TDD enforcement to SQL: flip `sql-test-writer` to run before `sql-coder`,
  `red_baseline` contract for SQL tests.
