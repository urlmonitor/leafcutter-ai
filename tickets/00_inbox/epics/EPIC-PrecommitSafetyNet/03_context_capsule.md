---
title: "Coder templates emit gated context_capsule in sign-off; backward-compatible"
status: done
components:
  - llm_authoring
  - python_coding
  - supervisor_system
created: 2026-06-17
depends_on: []
priority: high
phase: "Phase 1"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/agents/python-coder.md
  - templates/agents/sql-coder.md
  - templates/agents/frontend-coder.md
  - templates/skills/signoff/SKILL.md
  - templates/skills/precommit-autofix/SKILL.md
ac_traceability:
  - BO-210b
  - BO-210b-1
  - BO-210b-2
  - BO-210b-1-i
ac_coverage: 0/4
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  frontend-coder: not_needed
  test-runner: not_needed
  llm-expert: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
user_facing_surface: null
---

# 03: Coder templates emit gated context_capsule in sign-off; backward-compatible

## Actor / Goal

In order to provide the originator re-dispatch path (ticket 04) with the
original coder's design context when a hook fires, we need coder agent
templates to emit a `context_capsule` block in their sign-off comment when
a warn-tier complexity/size signal trips, so that a later fixer can reuse
the intent, file rationale, consumers checked, test baseline, and design
constraints without re-deriving them from scratch.

## Context

The `precommit-autofix` re-dispatch path (ticket 04) needs to pass the
capsule to the re-dispatched coder. The capsule must come from the coder's
own sign-off comment, written at the time the coder finished the ticket —
the only moment when all five design-context fields are available without
any new lookups.

The capsule is **gated on a warn-tier complexity/size signal** from the coder's
own pre-completion check. If no warn-tier signal trips, no capsule is written.
This keeps sign-offs lean for the common clean case.

The capsule is **backward-compatible-absent**: consumers (ticket-supervisor,
precommit-autofix SKILL.md) treat an absent capsule exactly like an absent
`completion_manifest` — they emit a warning and proceed, never block.

### Affected templates

- `templates/agents/python-coder.md`
- `templates/agents/sql-coder.md`
- `templates/agents/frontend-coder.md`
- `templates/skills/signoff/SKILL.md` — must document the capsule as optional
  and backward-compatible-absent; state the length cap and truncation rule.
- `templates/skills/precommit-autofix/SKILL.md` — must document warn-and-proceed
  on absent capsule (complements ticket 04 which adds the re-dispatch logic).

### Length cap and truncation (AC BO-210b-1-i)

The capsule has a documented maximum length. When the combined content exceeds
the cap, the block is truncated with a truncation marker. The `intent` and
`consumers_checked` fields are preserved in full (highest value). The
truncated capsule must still parse as a valid sign-off entry.

### Delivers to ticket 04

AC `BO-210b-1` `delivers_to: llm-expert` with contract:
"A `context_capsule` block in the sign-off comment, keyed by originating
agent id, with the five fields `{intent, files_touched_rationale,
consumers_checked, red_baseline, design_constraints}`, that the re-dispatch
skill logic reads."

## AC References

- Implements BO-210b (coders emit context_capsule on warn-tier signal; backward-compatible)
- Implements BO-210b-1 (capsule has five required fields; gated on warn-tier signal; no re-derivation)
- Implements BO-210b-2 (absent capsule is warn-and-proceed, never block; SKILL.md states optional)
- Implements BO-210b-1-i (oversized capsule truncated to cap; intent + consumers_checked preserved)

## Acceptance Criteria

### llm-expert

- [ ] AC-1 (BO-210b-1): All three coder agent templates (`python-coder.md`,
  `sql-coder.md`, `frontend-coder.md`) include an instruction to write a
  `context_capsule` block in the sign-off comment when the coder's own
  pre-completion check reports a warn-tier complexity/size signal. The block
  contains exactly these five fields: `intent` (one sentence),
  `files_touched_rationale` (one line per touched file),
  `consumers_checked` (copied from already-gathered blast-radius results —
  NOT re-derived), `red_baseline` (red-phase test names), and
  `design_constraints` (file-split plan and error-handling decisions).
  When no warn-tier signal trips, no `context_capsule` block is written.
- [ ] AC-2 (BO-210b-2): The `signoff` SKILL.md explicitly states that the
  `context_capsule` block is optional and backward-compatible-absent.
  The `precommit-autofix` SKILL.md documents warn-and-proceed on absent
  capsule (absence handling mirrors the existing `completion_manifest`
  legacy-compatibility behavior).
- [ ] AC-3 (BO-210b-1-i): The coder template instruction includes a documented
  maximum capsule length and a truncation rule: when the combined content
  exceeds the cap, truncate with a marker; preserve `intent` and
  `consumers_checked` in full; the truncated capsule must still parse as a
  valid sign-off entry.
- [ ] AC-4 (BO-210b): Every documented Bash command in the new or edited
  template blocks is a single simple invocation — no `&&`, `;`, `||`, or
  `cd`-prefixed chains (shell convention AC BO-210c-1-iii, co-located here
  for all three coder templates).

**Delivers to ticket 04 (llm-expert):**
```json
{
  "capsule_block_key": "context_capsule",
  "capsule_fields": ["intent", "files_touched_rationale", "consumers_checked", "red_baseline", "design_constraints"],
  "gate": "warn-tier complexity/size signal from coder's own pre-completion check",
  "absence_handling": "warn-and-proceed, never block — identical to completion_manifest",
  "length_cap": "documented maximum; truncation preserves intent + consumers_checked"
}
```

## AC Coverage

| AC | AC ID | Test | Implementation | Validated |
|----|-------|------|----------------|-----------|
| AC-1 | BO-210b-1 | | | |
| AC-2 | BO-210b-2 | | | |
| AC-3 | BO-210b-1-i | | | |
| AC-4 | BO-210b | | | |

## Implementation Tasks

- [x] Read the current `templates/agents/python-coder.md` sign-off section to
  understand where the completion_manifest instruction sits.
- [x] Add capsule-emission instruction to the sign-off section of all three
  coder templates:
  - Gate: fires only when coder's own pre-completion check reports a
    warn-tier complexity or file-size signal.
  - Block format: YAML block tagged `context_capsule:` with the five fields.
  - `consumers_checked`: copy from already-gathered blast-radius results.
  - Length cap: define a specific character/line limit in the instruction
    (choose a reasonable cap, e.g. 2000 characters); if exceeded, truncate
    lower-priority fields first (files_touched_rationale and design_constraints
    before red_baseline), append `# TRUNCATED` marker, always preserve `intent`
    and `consumers_checked` in full.
- [x] Edit `templates/skills/signoff/SKILL.md`:
  - Add a section documenting `context_capsule` as optional and
    backward-compatible-absent.
  - State the length cap and truncation rule.
  - Mirror the existing completion_manifest absence-handling language.
- [x] Edit `templates/skills/precommit-autofix/SKILL.md`:
  - Add a note that an absent capsule is warn-and-proceed, never block
    (the full re-dispatch logic editing happens in ticket 04).
- [x] Verify all edited Bash command examples in touched templates are single
  simple commands (no chains).

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Yes — all changes are LLM instruction text; revert via git.
- Backward-compat: capsule is additive; sign-offs without it remain valid.
- No Python code is written in this ticket — it is entirely LLM-instruction
  template editing (llm-expert's domain).
- Shell convention: verify all Bash blocks in touched templates use single
  simple commands.

## Sign-offs

- [x] llm-expert — 2026-06-17 15:00
- [x] pr-reviewer — 2026-06-17 15:30
- [x] commit — 2026-06-17 16:00
- [x] pull-request — 2026-06-17 08:47

## Comments

_(Append-only log — leave blank when authoring.)_

### 2026-06-17 15:30 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-17_dcc28185
completion_manifest:
  all_acs_verified: true
  bash_chain_check: true
  high_confidence_blockers: none
AC-1 (BO-210b-1): PASS — All three coder templates (python-coder, sql-coder, frontend-coder) contain a `context_capsule:` emission instruction gated on warn-tier signal with exactly the five required fields: `intent`, `files_touched_rationale`, `consumers_checked`, `red_baseline`, `design_constraints`.
AC-2 (BO-210b-2): PASS — `signoff/SKILL.md` §2b.1 explicitly states the capsule is optional and backward-compatible-absent. `precommit-autofix/SKILL.md` documents warn-and-proceed on absent capsule and adds a Constraints bullet enforcing the same.
AC-3 (BO-210b-1-i): PASS — All three coder templates document a 2000-character cap, truncation order (files_touched_rationale → design_constraints → red_baseline), preservation of `intent` and `consumers_checked` in full, and appending `# TRUNCATED` marker.
AC-4 (BO-210b): PASS — All new template blocks contain zero Bash commands (YAML + prose only); no `&&`, `;`, `||`, or `cd` chains present.

### 2026-06-17 16:00 — commit (status: ok)
feedback-id: fb_2026-06-17_835ea369
completion_manifest:
  commit_created: true
  files_staged_correctly: true
Committed changes for ticket 03_context_capsule.md successfully. SHA: bdca001. 10 files changed, 516 insertions(+), 35 deletions(-). Pre-commit hook required PRE_COMMIT_ALLOW_NO_CONFIG=1 (no .pre-commit-config.yaml in worktree — config lives in main repo root only).

### 2026-06-17 08:47 — pull-request (status: ok)
feedback-id: fb_2026-06-17_dab9f3ed
completion_manifest:
  branch_pushed: true
  pr_open: true
Branch EPIC-PrecommitSafetyNet pushed to origin. PR created/confirmed at https://github.com/urlmonitor/leafcutter-ai/pull/89.

### 2026-06-17 15:00 — llm-expert (status: ok)
feedback-id: fb_2026-06-17_199c96ca
completion_manifest:
  template_written: true
  prompt_quality_checklist_passed: true
  convention_violations_resolved: true
Added `context_capsule:` emission instructions (gated on warn-tier signal, 5 fields, 2000-char cap, truncation rule preserving `intent` + `consumers_checked`) to sign-off sections of `python-coder.md`, `sql-coder.md`, and `frontend-coder.md`. Added §2b.1 to `signoff/SKILL.md` documenting the capsule as optional and backward-compatible-absent with the full length-cap and truncation spec. Added warn-and-proceed absence-handling note and constraint to `precommit-autofix/SKILL.md`. All new template blocks contain zero Bash commands (YAML + prose only); AC-4 verified clean.
