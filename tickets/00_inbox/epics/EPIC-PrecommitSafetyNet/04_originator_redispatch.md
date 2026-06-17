---
title: "Originator re-dispatch: precommit-autofix reads capsule and re-dispatches originating agent"
status: todo
components:
  - precommit_hooks
  - supervisor_system
  - llm_authoring
created: 2026-06-17
depends_on:
  - 01_config_reconcile.md
  - 02_transform_tier.md
  - 03_context_capsule.md
priority: high
phase: "Phase 1"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: null
files_touched:
  - templates/skills/precommit-autofix/SKILL.md
  - templates/agents/commit.md
ac_traceability:
  - BO-210c
  - BO-210c-1
  - BO-210c-2
  - BO-210c-1-i
  - BO-210c-1-ii
  - BO-210c-1-iii
  - BO-210c-2-i
ac_coverage: 0/7
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  llm-expert: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
user_facing_surface: null
---

# 04: Originator re-dispatch: precommit-autofix reads capsule and re-dispatches originating agent

## Actor / Goal

In order to complete the safety-net loop, we need the `precommit-autofix`
SKILL.md to parse the `AUTOFIX_AGENT:` line from hook output, read the
`context_capsule` from the ticket, and re-dispatch the SAME agent type at
depth 2 with the capsule, so that judgment-tier hook failures are fixed by
the agent that has the original design context instead of a context-free
fresh fixer.

## Context

This ticket is the final and most complex deliverable of the safety-net epic.
It depends on all three prior tickets:

- **Ticket 01** provides `blocking_hook_ids` in `precommit-autofix.json` —
  the list of hooks that trigger originator re-dispatch vs the generic route.
- **Ticket 02** provides `tier: judgment` on hooks_manifest entries and the
  `AUTOFIX_AGENT:` line emitted by `check_exception_handling.py`.
- **Ticket 03** provides the `context_capsule` block in coder sign-off comments
  that this ticket reads and passes to the re-dispatched coder.

### Routing logic to implement in precommit-autofix SKILL.md

```
For each failing hook id:
  1. Is the hook id in blocking_hook_ids (from precommit-autofix.json)?
     No → non-gating, skip.
     Yes → proceed.
  2. What is the tier of this hook id in hooks_manifest?
     transform → should not reach here (transform hooks self-heal and exit 0).
     judgment → originator re-dispatch path.
  3. Parse AUTOFIX_AGENT: <agent-id> from the hook output.
  4. Read the latest context_capsule for that agent from the ticket sign-off.
     If absent: emit warning, proceed with empty capsule (warn-and-proceed).
  5. Dispatch the same agent type passing:
     {ticket_path, context_capsule, failing_hook_ids, raw_hook_output}
  6. Instruct the re-dispatched coder:
     - Fix only what satisfies the failing hooks.
     - Honor the capsule rationale.
     - Reuse capsule.consumers_checked — do NOT look up new consumers.
     - Spawn NO sub-agents (depth-2 constraint per ADR-006).
     - If fix requires cross-file information not in the capsule:
       return status: blocker describing the missing info.
  7. Retry commit once.
     If retry still fails: surface failure, stop.
```

Mechanical-tier failing hooks (tier not judgment, or not in blocking_hook_ids)
keep the existing generic light-model route — no capsule read, no
originator dispatch.

### Nesting depth constraint (ADR-006)

The dispatch chain is:
`ticket-supervisor (depth 0) → commit agent (depth 1) → re-dispatched coder (depth 2)`

No agent is spawned at depth 3. The re-dispatch prompt MUST explicitly instruct
the coder not to spawn sub-agents (including research-agent). The coder uses
`capsule.consumers_checked` instead of a fresh blast-radius lookup.

### Affected files

All changes in this ticket are to LLM-instruction surfaces — no Python module
owns this routing:
- `templates/skills/precommit-autofix/SKILL.md` — primary: re-dispatch logic
- `templates/agents/commit.md` — secondary: thread ticket_path into autofix call
  so the re-dispatch step can locate the ticket's sign-off section

### Shell convention

Every Bash command example in the edited templates must be a single simple
invocation — no `&&`, `;`, `||`, or `cd`-prefixed chains.

## AC References

- Implements BO-210c (auto-fix re-dispatches originating coder with capsule; mechanical keeps generic route; retry once)
- Implements BO-210c-1 (judgment-tier failure re-dispatches originating agent with capsule)
- Implements BO-210c-2 (mechanical-tier hooks keep generic light-model route; retry exactly once)
- Implements BO-210c-1-i (re-dispatched coder runs at depth 2; no sub-agents spawned)
- Implements BO-210c-1-ii (absent capsule: warn-and-proceed; re-dispatch still fires with empty capsule)
- Implements BO-210c-1-iii (every Bash command in new/edited templates is single simple command)
- Implements BO-210c-2-i (re-dispatched coder returns blocker rather than spawning sub-agent for fresh cross-file lookup)

## Acceptance Criteria

### llm-expert

- [ ] AC-1 (BO-210c-1): The `precommit-autofix` SKILL.md contains logic that,
  for a judgment-tier gating hook failure whose output includes an
  `AUTOFIX_AGENT: <agent-id>` line, reads the `context_capsule` for that
  agent from the ticket sign-off, then dispatches the SAME agent type passing
  `{ticket_path, context_capsule, failing_hook_ids, raw_hook_output}`. The
  dispatched agent is instructed to fix only what satisfies the hooks, honor
  the capsule rationale, reuse `consumers_checked`, and spawn no sub-agents.
- [ ] AC-2 (BO-210c-2): The SKILL.md routes mechanical-tier failures (hooks
  not in `blocking_hook_ids`, or whose manifest `tier` is not `judgment`) to
  the existing generic light-model route. No capsule read or originator
  dispatch is performed for mechanical-tier hooks. After any fixer (mechanical
  or originator re-dispatch) returns, the commit is retried exactly once. A
  second failure is surfaced, never retried again.
- [ ] AC-3 (BO-210c-1-i): The re-dispatch prompt in the SKILL.md explicitly
  forbids the re-dispatched coder from spawning sub-agents (including
  research-agent). The prompt instructs it to use `capsule.consumers_checked`
  instead of fresh lookups. No agent is dispatched below depth 2.
- [ ] AC-4 (BO-210c-1-ii): When a judgment-tier gating hook fires but the ticket
  contains no `context_capsule` for the originating agent, the SKILL.md emits
  a warning, does NOT block, and still dispatches the originating agent with
  an empty capsule. Absence is handled exactly like a missing
  `completion_manifest` — warn-and-proceed.
- [ ] AC-5 (BO-210c-1-iii): Every Bash command block in `precommit-autofix`
  SKILL.md (new and pre-existing), `signoff` SKILL.md, and `commit.md`
  (all files touched by this feature) is a single simple invocation — no
  `&&`, `;`, `||`, or `cd`-prefixed chains.
- [ ] AC-6 (BO-210c-2-i): The re-dispatch prompt instructs the coder that when
  fixing the violation would require cross-file information not present in
  `capsule.consumers_checked`, it MUST return `status: blocker` describing the
  missing information — it must NOT spawn a research-agent and must NOT guess.
  The commit is not retried on that pass; the blocker is surfaced to the user.
- [ ] AC-7 (BO-210c): The `commit.md` template is updated to thread `ticket_path`
  into the autofix invocation so the re-dispatch step can locate the ticket's
  sign-off section to read the capsule.

## AC Coverage

| AC | AC ID | Test | Implementation | Validated |
|----|-------|------|----------------|-----------|
| AC-1 | BO-210c-1 | | | |
| AC-2 | BO-210c-2 | | | |
| AC-3 | BO-210c-1-i | | | |
| AC-4 | BO-210c-1-ii | | | |
| AC-5 | BO-210c-1-iii | | | |
| AC-6 | BO-210c-2-i | | | |
| AC-7 | BO-210c | | | |

## Implementation Tasks

- [ ] Read `templates/skills/precommit-autofix/SKILL.md` in full to understand
  the current dispatch logic (where the hook failure is parsed, where the fixer
  is chosen, and where retry happens).
- [ ] Read `templates/agents/commit.md` to understand how the autofix skill is
  invoked today and where `ticket_path` must be threaded in.
- [ ] Edit `precommit-autofix` SKILL.md to add the originator re-dispatch routing:
  - For each gating hook failure: check `blocking_hook_ids` list (from ticket 01).
  - Look up the hook's `tier` in hooks_manifest (from ticket 02).
  - `judgment` tier: parse `AUTOFIX_AGENT:` line from hook output; read capsule
    from ticket sign-off at `ticket_path`; dispatch originating agent with
    `{ticket_path, context_capsule, failing_hook_ids, raw_hook_output}`.
  - `transform` or non-blocking: keep existing generic light-model route.
  - Re-dispatch prompt: explicitly forbid sub-agent spawning; instruct to use
    `capsule.consumers_checked`; instruct to return `status: blocker` when
    cross-file info is needed that is absent from the capsule.
  - Absent capsule: warn-and-proceed, dispatch with empty capsule.
  - Single retry after any fixer; surface on second failure.
- [ ] Edit `commit.md` to thread `ticket_path` into the autofix call.
- [ ] Verify every Bash command example in all touched files is a single simple
  command (no chains, no `cd`-prefix).

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Yes — all changes are LLM instruction text; revert via git.
- Depth-cap risk: the re-dispatch instruction MUST be explicit that depth 2 is
  the floor. A vague instruction could lead a coder to spawn research-agent at
  depth 3, violating ADR-006.
- Backward-compat: absent capsule must never block (AC-4). Existing pre-capsule
  tickets remain functional — the re-dispatch fires with empty capsule.
- Shell convention: all Bash blocks in touched templates (precommit-autofix
  SKILL.md, signoff SKILL.md, commit.md, and the three coder templates if
  re-touched) must be single simple commands.

## Comments

_(Append-only log — leave blank when authoring.)_
