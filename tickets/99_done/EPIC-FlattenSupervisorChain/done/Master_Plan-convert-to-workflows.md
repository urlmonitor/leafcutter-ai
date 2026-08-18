---
title: "EPIC: Convert Supervisor Chain to Claude Code Workflows"
type: epic
status: done
change_target: pipeline
risk_surface: internal
components:
  - build_pipeline
created: 2026-06-01
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: true
requires_adr: null
---

# EPIC: Convert Supervisor Chain to Claude Code Workflows

> **TWO EPICS SHARE THE `EPIC-FlattenSupervisorChain/` FOLDER. This is the second
> one.** Read this before assuming any ticket here belongs to the plan one level up.
>
> | | Epic | Created | Plan | Its tickets |
> |---|---|---|---|---|
> | Round 1 | "Flatten Supervisor Chain" — move `ticket-supervisor` to depth 0, write ADR-006 | 2026-05-29 | `../Master_Plan.md` | `../01`–`../07` |
> | Round 2 | "Convert Supervisor Chain to Claude Code Workflows" — this file | 2026-06-01 | this file | `01`–`10` in this `done/` folder |
>
> Round 2 reused round 1's folder name rather than opening its own. Nothing
> distinguished the two plans except their `title:`, and both were called
> `Master_Plan.md` in sibling directories — so the round-2 plan was read as a
> stale duplicate of round 1 and swept into `tickets/99_rejected/` by PR #275,
> taking the only copy with it. This file was recovered from there on 2026-08-18
> and renamed to `Master_Plan-convert-to-workflows.md` so the two are no longer
> distinguishable only by their contents.
>
> `status:` was `in_progress` when recovered. It is set to `done` here: every
> ticket this plan governs is complete and its deliverables were verified live in
> the tree (`build-epic.js` / `build-ticket.js` worktree guards at
> `worktree_required: true`, and `finalize-feature.js` as a leaf workflow). The
> `in_progress` value is stale bookkeeping from the point the epic stopped being
> driven ticket-by-ticket, not evidence of outstanding work.
>
> Recovered by branch `chore/epic-duplicate-repair`.

## Goal

In order to eliminate the depth-1 sub-agent nesting violation that silently
prevents phase agents from running, we need to convert leafcutter's supervisor
agent chain to Claude Code Workflows (deterministic JavaScript scripts), so
that the agentic build pipeline is reliable across all Claude Code v2.1.154+
installations.

## Context

Claude Code imposes a hard depth-1 limit on Agent-tool nesting. The current
supervisor chain violates this in two places:

- `epic-supervisor → ticket-supervisor → phase agents` (3 tiers; fails at depth 2)
- `create-ticket → business-analyst → test-planner` (3 tiers; fails at depth 2)

ADR-006 (accepted 2026-05-29) acknowledged the problem and documented a
short-term mitigation (inlining batching logic into `/build-feature` so
`ticket-supervisor` runs at depth 0). That mitigation is not a full fix: the
chain still relies on LLM prose for control flow, is not testable in isolation,
and does not survive a crash mid-epic without ad-hoc state recovery.

Claude Code Workflows (available since v2.1.154) solve this structurally.
Each `agent()` call inside a workflow JS script is a flat depth-1 spawn.
The JS script owns loops, conditionals, fan-out, and failure routing —
replacing what supervisor agents currently do with LLM reasoning.

This epic converts the three supervisor chains to JS workflows, updates
`build.py` to install them, deprecates the legacy templates, and ships a
permissive `settings.json` allowlist to reduce permission prompts during
workflow execution.

### Key design decisions (already settled — do not reopen)

- **Planner pattern**: workflow scripts cannot read files directly, so a
  dedicated agent reads frontmatter/plans and returns structured JSON for the
  script to orchestrate.
- **Failure adjudication stays as AI**: the only decision requiring LLM
  reasoning is classifying blockers (mechanical / cross-agent / design / halt).
  Everything else becomes JS code.
- **Dual-path build**: `build.py` gates workflow installation on Claude Code
  version detection (>= 2.1.154). The legacy agent path remains for older
  versions.
- **Ticket-file state as resume mechanism**: if a workflow crashes,
  re-running `/build-feature` picks up from the last non-done ticket (same
  as current behaviour).

### ADR cross-reference

- ADR-006 (`docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md`) —
  the accepted architectural decision this epic implements.

## Architecture Plan

### Diagrams

- `agent_flow` diagram at `docs/architecture/components/workflow-dispatch-topology.md` (parent: `docs/architecture/components/`)

### ADRs

- ADR-006 already covers the flattening decision. A supplemental ADR entry
  may be needed to document the Workflows-specific planner pattern if the
  implementation deviates materially.

## Sub-ticket Table

| # | File | Description | Status |
|---|------|-------------|--------|
| 01 | [01_build_workflow_phase.md](./01_build_workflow_phase.md) | Add `build_workflow_scripts()` phase to build.py with version detection | `[ ]` |
| 02 | [02_build_ticket_workflow.md](./02_build_ticket_workflow.md) | Write `build-ticket.js` — replaces ticket-supervisor | `[ ]` |
| 03 | [03_build_epic_workflow.md](./03_build_epic_workflow.md) | Write `build-epic.js` — replaces epic-supervisor / /build-feature fan-out | `[ ]` |
| 04 | [04_create_ticket_workflow.md](./04_create_ticket_workflow.md) | Write `create-ticket.js` — replaces the BA → refinement chain | `[ ]` |
| 05 | [05_onboarding_docs.md](./05_onboarding_docs.md) | Update onboarding wizard and docs for workflow version requirement | `[ ]` |
| 06 | [06_deprecate_supervisors.md](./06_deprecate_supervisors.md) | Mark epic-supervisor and ticket-supervisor as legacy_only in agent_registry | `[ ]` |
| 07 | [07_settings_allowlist.md](./07_settings_allowlist.md) | Ship comprehensive git/gh/python/npm allowlist in settings.json template | `[ ]` |
| 08 | [08_enable_agent_teams.md](./08_enable_agent_teams.md) | Enable experimental Agent Teams via settings.json env var + constraints doc | `[ ]` |
| 10 | [10_finalize_feature_workflow.md](./10_finalize_feature_workflow.md) | Convert finalize-feature to a JS workflow script (leaf workflow, 6 steps, prompt gates) | `[ ]` |

## Risk & Safety

- Parallelism note (updated): tickets 01, 07, and 08 can run immediately (08
  depends on 07 for the settings.json file but not for logic). Tickets 02, 03,
  04 depend on 01. Tickets 05 and 06 can run after 02–04 are drafted.

- Touches money? No.
- Touches data? No.
- Reversibility? High — the dual-path build gate means legacy agent templates
  remain functional for sub-v2.1.154 installs. JS workflow files are additive;
  removing them restores prior behaviour.
