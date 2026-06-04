---
title: "Create parallel /create-ticket-v2 command for testing new AC pipeline"
status: todo
components:
  - build_pipeline
created: 2026-06-03
depends_on: []
priority: critical
phase: "Phase 0"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
user_facing_surface: slash_command
actuation_contract: "Invokes the v2 ticket creation pipeline (Opus BA + IT PO + new AC format) and writes a ticket file to tickets/00_inbox/ with per-agent contracts and ac_coverage frontmatter."
files_touched:
  - templates/workflows/create-ticket-v2.md
  - templates/agents/business-analyst-v2.md
  - templates/agents/it-po.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  architecture-diagram-author: not_needed
  user-surface-smoker: needed
---

# 00: Parallel /create-ticket-v2 for Testing

## Business Intent

Before replacing the production ticket creation pipeline, we need a parallel
`/create-ticket-v2` command that runs the new BA (Opus) + IT PO flow and
produces tickets in the new AC format. This lets us test the pipeline on real
requests, compare output quality against v1, and iterate without breaking
existing workflows.

## Context

### Why Not Just Replace

The current `/create-ticket` pipeline works. It produces tickets that all
existing agents can process. If we replace it and the new format breaks
downstream agents, every in-flight epic is affected.

### The Testing Strategy

1. Ship `/create-ticket-v2` as a parallel command
2. Run it on 3-5 real feature requests alongside `/create-ticket` (v1)
3. Compare: Are the v2 ACs more specific? Do they catch ambiguity v1 missed?
   Are the contracts actually useful?
4. Fix issues found during testing
5. Once confident: promote v2 → v1 (rename, deprecate old)

### What v2 Does Differently

| Step | v1 (current) | v2 (new) |
|------|-------------|----------|
| BA model | Sonnet | Opus |
| BA knowledge | Minimal, rarely asks questions | Pulls from INDEX.md, elicitation framework |
| AC format | Gherkin prose | Numbered checklist with AC-N IDs |
| Multi-agent | Same ACs for everyone | Per-agent contracts with Delivers to / Depends on |
| Contract spec | None | IT PO produces exact data shapes, endpoints, types |
| Coverage tracking | None | ac_coverage frontmatter + AC Coverage table |

### Backward Compatibility

v2 tickets include ALL fields that v1 tickets have (status, agents map,
files_touched, Sign-offs, etc.) plus new fields (ac_coverage, Agent Contracts
section). This means:

- **v1 agents CAN process v2 tickets** — they ignore the new sections they
  don't understand, sign off on their phase as normal
- **v2 agents (ac-validator) SKIP v1 tickets** — no ac_coverage = no validation
- **Gradual migration**: once v2 is proven, new tickets use v2 format; old
  tickets continue to work as-is until they're done

## Agent Contracts

### python-coder

- [ ] AC-1: `/create-ticket-v2` command template exists at `templates/workflows/create-ticket-v2.md` and dispatches the v2 pipeline
- [ ] AC-2: `business-analyst-v2.md` agent template exists — identical to current BA but with:
  - model: opus
  - §1 pull-based research (reads INDEX.md, pulls relevant user-facing docs)
  - §2 elicitation framework (comprehensive question taxonomy, evaluate-don't-mechanically-ask)
  - §3 weasel word self-check
  - §4 assumption logging
  - §5 complexity assessment (trivial/simple/standard/novel)
- [ ] AC-3: v2 pipeline routes based on complexity:
  - trivial/simple → produces ticket with flat AC checklist (no IT PO)
  - standard/novel → spawns IT PO → produces ticket with per-agent contracts
- [ ] AC-4: v2-produced tickets include backward-compatible frontmatter (all existing required fields) plus new `ac_coverage: 0/N` field
- [ ] AC-5: v2-produced tickets include `## Agent Contracts` section (for multi-agent) OR `## Acceptance Criteria` with numbered checklist (for single-agent) — both formats use `- [ ] AC-N:` syntax
- [ ] AC-6: v2-produced tickets include `## AC Coverage` table (empty, to be filled by implementation agents)
- [ ] AC-7: The v2 command does NOT modify any v1 templates or workflows — complete isolation

## Sign-offs

- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request
- [ ] user-surface-smoker

## Smoke Fixture

```yaml
surface: create-ticket-v2
fixture_input: |
  (invoke /create-ticket-v2 with: "add a health check endpoint that returns 200")
assertion: "(?i)(AC-\\d|ac_coverage|Acceptance Criteria|Agent Contracts)"
placeholder_signature: "(?i)(TODO|PLACEHOLDER|not implemented)"
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |
| AC-6 | | | |
| AC-7 | | | |

## Risk & Safety

- Touches money? No.
- Touches data? No — creates new templates only, does not modify existing ones.
- Reversibility? Fully reversible — parallel command with no impact on v1.
- Risk: v2 tickets might confuse existing agents that don't know about AC Coverage tables.
  Mitigation: v2 tickets are backward-compatible — agents ignore sections they
  don't recognize. Sign-offs section still exists in the familiar format.
