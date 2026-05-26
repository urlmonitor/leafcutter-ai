---
title: "Improve agent compliance with DECISION HISTORY format spec"
status: todo
components:
  - build_pipeline
created: 2026-05-26
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
roadmap_phase: phase_1
advances_current_outcome: true
files_touched:
  - templates/agents/commit.md
  - templates/skills/signoff/SKILL.md
  - templates/skills/doc-enforcer/SKILL.md
  - templates/skills/building-epics/SKILL.md
  - templates/agents/adr-author.md
agents:
  architect-review: not_needed
  python-coder: not_needed
  test-writer: not_needed
  test-runner: not_needed
  documentation-expert: needed
  change-scope-reviewer: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  sql-coder: not_needed
  sql-query: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
---

# Improve agent compliance with DECISION HISTORY format spec

## Actor / Goal

In order to reduce the transformer hook's workload and produce cleaner commit
pipelines, we need to add explicit DECISION HISTORY format examples to agent
templates and skill instructions so that agents produce compliant entries
without relying on `transform_decision_history.py` to fix them.

## Context

EPIC-CommitSignoffHardening ticket 02
(`tickets/99_done/EPIC-CommitSignoffHardening/02_fix_decision_history_autofix_loop.md`)
identified that agents consistently write DECISION HISTORY entries with date-only
timestamps (`YYYY-MM-DD` without `HH:MM`) and missing tail-tags. A mechanical
transformer hook (`scripts/commit_guardian/transform_decision_history.py`) was
built to catch and correct these errors before the validator runs, eliminating
the autofix loop.

The transformer is a safety net, not a substitute for correct agent behavior.
The root cause is that agent templates and skill instructions do not clearly
enough specify the required format, or bury it in prose without a worked
example. Agents skip the time component and omit the tail-tag because neither
is emphasized at the point of authorship.

The `templates/agents/commit.md` template already has a DECISION HISTORY
section (added in ticket 02's documentation-expert pass), but:

- `templates/skills/signoff/SKILL.md` has no dedicated DH format block.
- `templates/skills/doc-enforcer/SKILL.md` has the formal grammar but lacks
  a copy-paste "correct example" that agents can scan quickly.
- `templates/skills/building-epics/SKILL.md` §5.6 references the transformer
  but does not show the ideal pre-transformer entry format.
- `templates/agents/adr-author.md` references DH tail-tags for ADR back-links
  without showing the full entry format with `HH:MM`.

**Required format** (for reference when authoring this ticket's changes):

```
- YYYY-MM-DD HH:MM [Author]: <description>. (#EPIC-Name/NN)
```

or for standalone / ticketless work:

```
- YYYY-MM-DD HH:MM [Author]: <description>. (#TICKETLESS reason=<10+ char reason>)
```

`HH:MM` is 24-hour clock, UTC, zero-padded. The tail-tag is mandatory on every
new entry written from EPIC-DocTraceability onward.

## Acceptance Criteria

```gherkin
Given an agent reads templates/skills/signoff/SKILL.md before writing a DH entry
When it authors a new DECISION HISTORY line
Then the entry includes HH:MM (not date-only) and a tail-tag without any transformer intervention

Given an agent reads templates/skills/doc-enforcer/SKILL.md
When it looks for the canonical DH entry format
Then it finds a clearly labelled "correct example" block showing YYYY-MM-DD HH:MM and tail-tag

Given an agent reads templates/agents/commit.md before staging a file with a DH section
When it authors the DH entry
Then the entry matches the mandatory format: - YYYY-MM-DD HH:MM [Author]: <description>. (#TAG)

Given an agent reads templates/agents/adr-author.md
When it writes a DH entry referencing an ADR back-link
Then the entry includes HH:MM timestamp alongside the (ADR-NNN) back-link tag

Given the transformer hook runs after all changes ship
When an agent-produced commit is staged
Then the transformer reports zero timestamp corrections and zero tail-tag injections
```

## Sign-offs

- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### documentation-expert

- [ ] Audit `templates/agents/commit.md` §DECISION HISTORY: verify the
  mandatory format `- YYYY-MM-DD HH:MM [Author]: <description>. (#TAG)` is
  shown as a fill-in-the-blank example, not just described in prose. If
  example is missing or date-only, add a correct worked example inline.
- [ ] Add a `### DECISION HISTORY format` subsection to
  `templates/skills/signoff/SKILL.md` (place after the existing Sign-off
  format table, before the Comments section). The subsection must:
  - Show a single "correct entry" code block with a real timestamp and
    tail-tag filled in (not a template placeholder).
  - Explicitly state "date-only entries (`YYYY-MM-DD` with no `HH:MM`) are
    invalid and will be corrected by the transformer — write the time
    component upfront to avoid transformer churn."
  - Show both tail-tag variants: `(#EPIC-Name/NN)` and
    `(#TICKETLESS reason=<10+ char reason>)`.
- [ ] In `templates/skills/doc-enforcer/SKILL.md`, add a "Quick reference —
  correct entry format" callout box (or fenced code block) near the top of
  the §3 DECISION HISTORY Block Structure section. The callout must show the
  full canonical entry in one line so agents can locate it at a glance
  without reading through the grammar BNF.
- [ ] In `templates/skills/building-epics/SKILL.md` §5.6 (or wherever the
  transformer is referenced), add one sentence instructing agents to write the
  full `HH:MM` and tail-tag proactively: "Do not rely on the transformer —
  write entries in the required format from the start."
- [ ] In `templates/agents/adr-author.md`, update the DECISION HISTORY
  back-link guidance to include a worked example that shows `HH:MM` alongside
  the `(ADR-NNN)` tag, e.g.:
  `- 2026-05-26 14:30 [hh]: Adopted ADR-027 for X. (#EPIC-Foo/03)(ADR-027)`
- [ ] Run `python scripts/build.py --target-dir ..` to deploy updated
  templates to `.claude/agents/` and `.claude/skills/` in the workspace.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Fully reversible — all changes are additive edits to
  template/skill markdown files. Reverting any file restores prior behavior.
  The transformer safety net remains in place regardless.
- Risk of over-specification: examples must not conflict with the existing
  BNF grammar in `doc-enforcer/SKILL.md`. Verify any new examples would pass
  the regex defined in §4 of that skill.
