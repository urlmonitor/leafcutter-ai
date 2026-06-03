---
title: "Author ADR: Live Surface Tester — port registry, read-only constraint, and conditional dispatch"
status: todo
components:
  - build_pipeline
  - config_loader
created: 2026-06-03
depends_on: []
priority: high
phase: "Phase 1"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: true
files_touched:
  - docs/architecture/adrs/ADR-NNN-live-surface-tester.md
agents:
  architect-review: not_needed
  adr-author: signed_off
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
---

# 01: Author ADR — Live Surface Tester Design

## Actor / Goal

In order to give every subsequent implementation ticket a settled architectural
baseline, we need to author an Architecture Decision Record that documents the
port registry scheme, the read-only agent constraint, and the conditional
dispatch rules, so that implementers do not re-litigate these decisions during
coding.

## Context

The EPIC-LiveSurfaceTesting Master_Plan records five settled decisions:

1. **Read-only agent**: `live-surface-tester` has no Edit/Write tools.
2. **Port registry**: JSON file keyed by worktree name.
3. **Project-level toggle**: `skills_config.json → live_surface_testing.enabled`.
4. **Ticket-level toggle**: frontmatter field `live_surface_test` (bool).
5. **Phase priority 11.8**: after `user-surface-smoker` (11.5), before `commit` (12).

These are the decisions the ADR must formally record. No decisions are
delegated to the ADR author — the above is the canonical list. The ADR author's
job is to write the prose context, alternatives considered, and consequences.

This ticket is the dependency gate for all other EPIC-LiveSurfaceTesting
tickets. Nothing else should begin until this ADR is accepted.

### ADR numbering

The next available ADR number should be determined by inspecting
`docs/architecture/adrs/` at implementation time and incrementing from the
current highest number.

## Acceptance Criteria

```gherkin
Given docs/architecture/adrs/ is inspected
When the ADR file is created
Then it follows the standard ADR template (title, status: accepted, context,
  decision, alternatives, consequences)
 And it documents all five settled decisions from the Master_Plan
 And its slug contains "live-surface-tester"

Given the ADR file is committed
When the doc frontmatter hook validates it
Then the hook passes with no errors
```

## Sign-offs

- [x] adr-author — 2026-06-03 10:00
- [x] pr-reviewer — 2026-06-03 10:05
- [ ] commit
- [ ] pull-request

## Comments

### 2026-06-03 10:00 — adr-author (status: ok)
feedback-id: fb_2026-06-03_62768b53
completion_manifest:
  adr_file_created: true
  all_sections_present: true
  status_set: true
Authored ADR-007-live-surface-tester.md at docs/architecture/adrs/. All five settled decisions recorded: read-only constraint, port registry (JSON keyed by worktree name, file-locked), project-level toggle (skills_config.json), ticket-level toggle (live_surface_test frontmatter), and phase priority 11.8. Three alternatives captured with rejection rationale. Handoff JSON written to tickets/00_inbox/epics/EPIC-LiveSurfaceTesting/.pending/adr_handoff.json.

### 2026-06-03 10:05 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-03_b800ae0b
completion_manifest:
  diff_reviewed: true
  no_high_findings: true
  scope_verified: true
Review Report — Base: HEAD. Diff: 22 lines changed across 2 files (ticket + feedback.jsonl), plus 2 untracked (ADR-007, handoff JSON). No high-confidence findings. No medium findings. Suppressed: 0 low nits, 0 medium dropped. ADR-007 is well-formed and covers all five settled decisions from Master_Plan. Scope matches files_touched goal. Escalation: none (medium count = 0, threshold > 3).

## Implementation Tasks

- [x] Inspect `docs/architecture/adrs/` to determine next ADR number
- [x] Write `docs/architecture/adrs/ADR-NNN-live-surface-tester.md` using the
  standard ADR template (status: proposed → accepted after this ticket merges)
- [x] Record the five settled decisions as the `## Decision` section
- [x] Write `## Alternatives Considered`:
  - Extending `user-surface-smoker` with HTTP capabilities (rejected: couples
    two orthogonal concerns; smoker has no subprocess model)
  - Using a shared port range (8100–8199) without a registry (rejected: no
    collision detection across concurrent worktrees)
  - Giving the tester write access to self-repair issues (rejected: violates
    separation of concerns; tester must never fix its own findings)
- [x] Write `## Consequences`:
  - `live-surface-tester` can never self-repair; blocker payloads are the only
    escalation path
  - Port registry becomes a shared mutable state file; concurrent worktree
    writes must be atomic (file lock)
  - Projects without a runnable server surface (pure libraries, CLI tools) opt
    out via `live_surface_testing.enabled: false`

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? ADR is append-only by convention; the record stands even if
  the implementation is later revised.
