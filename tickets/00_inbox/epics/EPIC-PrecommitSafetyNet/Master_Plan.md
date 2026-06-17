---
title: "EPIC: Pre-commit Safety Net"
type: epic
status: in_progress
components:
  - precommit_hooks
  - commit_guardian
  - supervisor_system
  - llm_authoring
  - python_coding
  - documentation_system
created: 2026-06-17
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: null
---

# EPIC: Pre-commit Safety Net

## Goal

In order to eliminate the pre-commit cold-start fixer rework loop, we need a
safety net that reuses the original coder's design context when a commit-phase
hook fires, so that the SAME agent type that authored the work fixes its own
violations with full context instead of a context-free fresh fixer deriving
everything from scratch.

## Context

Today when a coder agent signs off and the commit agent's `git commit` later
fails a pre-commit hook, the `precommit-autofix` skill spawns a FRESH fixer
agent that has none of the original coder's context. That agent must re-derive
the design intent, re-look up consumers, and re-read the test baseline —
pure rework that could have been avoided.

This epic adds four interrelated components:

1. **CONFIG RECONCILE** — Populate the currently-dead `.claude/precommit-autofix.json`
   stub to its documented schema and add a `blocking_hook_ids` gating array.

2. **TRANSFORM TIER** — Two new pure-Python self-healing hooks
   (`transform_doc_frontmatter.py`, `transform_description_field.py`) that fix
   mechanical doc-field violations in place, stage the fix, and exit clean.
   The `commit_guardian.json` hooks_manifest gains a `tier` field
   (`transform | judgment`), with each transform hook ordered before its
   matching validator. The exception-handling check gains `AUTOFIX_AGENT`
   emission on violation.

3. **CONTEXT CAPSULE** — Coder agent templates emit a `context_capsule` block
   in the sign-off comment when a warn-tier complexity/size signal trips,
   carrying `{intent, files_touched_rationale, consumers_checked,
   red_baseline, design_constraints}`. Absence is backward-compatible (degrades
   exactly like a missing `completion_manifest`).

4. **ORIGINATOR RE-DISPATCH** — The `precommit-autofix` SKILL.md parses the
   `AUTOFIX_AGENT:` line from hook output, reads the capsule from the ticket,
   and re-dispatches the originating agent type at depth 2 with the capsule.
   Mechanical-tier hooks keep the generic light-model route. One retry.
   Re-dispatched coder spawns no sub-agents (ADR-006 depth cap).

### Locked design decisions

- **Max nesting depth: 3** (ticket-supervisor → commit → re-dispatched coder).
  No agent is spawned below depth 2; re-dispatched coders use capsule's
  `consumers_checked` instead of a fresh research-agent call.
- **Portability**: transform hooks fail-open/no-op on absent docs layout;
  capsule readers degrade gracefully on absent capsule.
- **Single-simple-command shell convention**: every Bash command in new or
  edited templates is a single simple invocation — no `&&`, `;`, `||`, or
  `cd`-prefixed chains.
- **Template + deployed file parity**: every file edited in both the
  deployed location and its packaged template source must be verified via
  the `build.py` round-trip.

### AC source-of-truth folders

- `docs/acceptance-criteria/build-orchestration/BO-210-precommit-safety-net/`
  (BO-210 root + BO-210a/b/c families)
- `docs/acceptance-criteria/guardrail-engine/GE-102-transform-tier-autofix/`
  (GE-102 root + GE-102a/b/c/d/e)

### Dependency order

```
ticket 1 (config reconcile)  ─┐
ticket 2 (transform tier)     ├──▶ ticket 4 (originator re-dispatch)
ticket 3 (context capsule)   ─┘
ticket 2 ──▶ ticket 5 (docs)
```

Tickets 1, 2, and 3 are parallelisable. Ticket 4 waits on all three.
Ticket 5 waits on ticket 2.

## Sub-ticket Table

| # | File | Description | Agent | Status |
|---|------|-------------|-------|--------|
| 01 | [01_config_reconcile.md](./01_config_reconcile.md) | Reconcile precommit-autofix.json stub to documented schema + blocking_hook_ids | python-coder | `[ ]` |
| 02 | [02_transform_tier.md](./02_transform_tier.md) | New transform hooks, tier field in hooks_manifest, AUTOFIX_AGENT emission | python-coder | `[ ]` |
| 03 | [03_context_capsule.md](./03_context_capsule.md) | Coder templates emit gated context_capsule in sign-off; backward-compatible | llm-expert | `[ ]` |
| 04 | [04_originator_redispatch.md](./04_originator_redispatch.md) | precommit-autofix SKILL.md reads capsule + re-dispatches originating agent | llm-expert | `[ ]` |
| 05 | [05_docs.md](./05_docs.md) | Update managing-pre-commit-hooks.md for transform tier | documentation-expert | `[ ]` |

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? High — transform hooks fail-open; capsule emission is additive;
  re-dispatch is a skill edit with no schema migration.
- Template parity risk: both sides (deployed + template source) must be edited
  together for every file that has a template counterpart. Verified via
  build.py round-trip on each ticket.
