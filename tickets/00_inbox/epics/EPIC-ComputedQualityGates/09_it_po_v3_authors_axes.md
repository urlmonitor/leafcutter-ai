---
title: "it-po-v3 authors change_target + risk_surface during enrichment"
status: blocked
components:
  - product_ownership
created: 2026-07-07
depends_on:
  - 08_ac_axes_schema_and_generator_emit.md
priority: medium
requires_adr: false
requires_diagram: false
change_target: prompt
risk_surface: internal
files_touched:
  - templates/agents/it-po-v3.md
  - templates/skills/create-ac/SKILL.md
  - templates/skills/plan-feature/SKILL.md
agents:
  llm-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 09: it-po-v3 authors change_target + risk_surface during enrichment

## Actor / Goal

In order for *newly authored* ACs to carry the two-axis classification automatically (not just backfilled ones), we need the `it-po-v3` technical-enrichment agent to classify and set `change_target` + `risk_surface` on each AC it enriches — making the AC store self-sustaining as the source of truth for computed quality gates.

## Context

Tickets 07 + 08 make the generator consume and emit the axes, and ticket 10 backfills the existing store. But without this ticket, every AC authored *after* the backfill would again lack the axes and fall back to the legacy agent map — reopening the phantom-done hole for new work.

**BLOCKED — do not start until unblocked.** `it-po-v3`'s source template is not on `origin/main` or the `EPIC-ComputedQualityGates` branch. It exists only as a deployed build artifact (`.leafcutter/agents/it-po-v3.md`, not repo-tracked) and on the unmerged `EPIC-QuickFixWorkflow` branch (`templates/agents/it-po-v3.md`). This is package-boundary drift: the agent was deployed without its source being promoted into the package. This ticket cannot edit `templates/agents/it-po-v3.md` until that source lands on `main`.

**Unblock condition:** `templates/agents/it-po-v3.md` exists on `origin/main` (via the EPIC-QuickFixWorkflow merge or a dedicated promotion ticket). When it does, flip `status: blocked` → `todo` and drive.

## AC References

- Depends on 08_ac_axes_schema_and_generator_emit.md (axes must be valid AC fields first).
- Blocked-on: `templates/agents/it-po-v3.md` present on `origin/main`.

## Acceptance Criteria

- [ ] AC-1: The `it-po-v3` agent template instructs the agent to set `change_target` (one or more of the 10 blast-radius values) and `risk_surface` (one of the 6 values) on every AC it enriches, deriving them from the AC's criteria + technical landscape.
- [ ] AC-2: The agent's output is validated against the canonical enum before write (invalid value is a self-correction, not a store write).
- [ ] AC-3: `create-ac` and `plan-feature` skill docs describe the axes as part of the it-po-v3 enrichment contract.
- [ ] AC-4: A prompt-audit of the updated template passes (shell rules, tool allowlist, signoff protocol).

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |

## Comments

## Sign-offs
- [ ] llm-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### llm-expert
- [ ] (After unblock) Extend `templates/agents/it-po-v3.md` with the axis-authoring instruction + canonical enum + derivation guidance.
- [ ] Update `create-ac` and `plan-feature` SKILL docs to document the axis-enrichment step.
- [ ] Run prompt-audit on the updated template.

## Risk & Safety
- Touches money? No.
- Touches data? No — modifies an agent template + skill docs. Reversible.
- Reversibility? Revert the commit.
