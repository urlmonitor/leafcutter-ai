---
title: "Update agent_registry.json spawn topology for flattened chain"
status: todo
components:
  - build_pipeline
created: 2026-05-29
depends_on:
  - 01_update_ticket_supervisor_template.md
priority: high
requires_diagram: false
requires_adr: false
files_touched:
  - config/agent_registry.json
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: needed
roadmap_phase: phase_1
advances_current_outcome: true
---

# 03: Update agent_registry.json spawn topology for flattened chain

## Goal

In order to keep `config/agent_registry.json` as the accurate single source
of truth for the supervisor spawn topology, we need to update the
`spawned_by` and `spawn_allowlist` fields for `ticket-supervisor` and
`epic-supervisor` to reflect the flattened chain.

## Context

After ticket 01 (updated template) and ticket 02 (updated workflow), the
actual runtime topology is:

```
/build-feature (user)
  → ticket-supervisor  (depth 0, spawned by: user / build-feature)
    → phase agents     (depth 1, spawned by: ticket-supervisor)
```

The registry currently records:
- `ticket-supervisor.spawned_by: ["epic-supervisor"]`
- `epic-supervisor.spawn_allowlist: ["ticket-supervisor", ...]`

These need to be updated to match the new reality. `epic-supervisor` is also
flagged as deprecated.

## Acceptance Criteria

```gherkin
Given config/agent_registry.json is updated
When the ticket-supervisor entry is inspected
Then spawned_by contains "user" (or "build-feature") and not "epic-supervisor"

Given the epic-supervisor entry is inspected
When its status field is checked
Then it contains "deprecated: true" or a deprecation note

Given agent_registry.schema.json supports a deprecated field
When build.py --validate runs
Then it exits 0 with no schema violations

Given the registry is updated
When business-analyst reads it to build an agents: map
Then ticket-supervisor is not presented as an internal-only agent
```

## Sign-offs

- [x] python-coder — 2026-05-29 12:00
- [x] pr-reviewer — 2026-05-29 12:05
- [x] commit — 2026-05-29 12:10
- [ ] pull-request

## Comments

### 2026-05-29 12:00 — python-coder (status: ok)
feedback-id: fb_2026-05-29_371baeee
Updated config/agent_registry.json: added `"deprecated": true` to epic-supervisor entry; added `"user"` to ticket-supervisor.spawned_by (alongside retained "epic-supervisor" for backward compat); added `"description"` field to ticket-supervisor describing depth-0 direct dispatch via /build-feature. Schema already had `deprecated` field defined. build.py --validate exits 0, diff limited to epic-supervisor and ticket-supervisor entries only.

### 2026-05-29 12:05 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-29_b8b2d767
Changes reviewed and approved. Diff is minimal (7 lines, 2 entries only). epic-supervisor gets `deprecated: true`; ticket-supervisor gets `"user"` added to spawned_by and a description. Bidirectional consistency preserved (epic-supervisor.spawn_allowlist still lists ticket-supervisor). build.py --validate passes cleanly. No concerns.

### 2026-05-29 12:10 — commit (status: ok)
feedback-id: fb_2026-05-29_be546ea8
Committed 2 in-scope files (config/agent_registry.json, ticket file). Commit SHA 4339ca2. No pre-commit hook failures. Cross-ticket staged files (ticket 04, building-epics SKILL.md) were unstaged before commit to prevent cross-worktree pollution. Lock acquired and released cleanly.

## Implementation Tasks

- [x] Read `config/agent_registry.json` in full
- [x] Update `ticket-supervisor.spawned_by` from `["epic-supervisor"]` to `["user", "build-feature"]`
- [x] Update `ticket-supervisor` description/notes to reflect depth-0 direct dispatch
- [x] Update `epic-supervisor.spawned_by` — add deprecation marker (add `"deprecated": true` or a `"status": "deprecated"` field)
- [x] Check `agent_registry.schema.json` to see if a `deprecated` field is defined; if not, add it as an optional boolean
- [x] Verify `epic-supervisor.spawn_allowlist` still lists `ticket-supervisor` (for backward compat during deprecation window)
- [x] Run `python scripts/build.py --validate` to confirm no schema errors
- [x] Verify the registry diff is minimal — only `ticket-supervisor` and `epic-supervisor` entries change

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? JSON edit is fully reversible via git.
- The registry is read by `business-analyst` and `ticket-supervisor` at runtime.
  A malformed registry entry can cause agent validation failures in all running
  epics. Keep changes minimal.
