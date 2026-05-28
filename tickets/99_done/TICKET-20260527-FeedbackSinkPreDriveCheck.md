---
title: "Add feedback-sink reachability check to pre-drive checklist"
status: todo
components:
  - build_pipeline
created: 2026-05-27
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - leafcutter-ai/CLAUDE.md
  - leafcutter-ai/templates/skills/building-epics/SKILL.md
  - leafcutter-ai/templates/agents/epic-supervisor.md
agents:
  architect-review: signed_off
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: signed_off
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
---

# Add feedback-sink reachability check to pre-drive checklist

## Actor / Goal

In order to prevent silent telemetry loss during epic drives, we need to add a
feedback-sink reachability check to the pre-drive checklist so that the
epic-supervisor warns (or halts) the user before any work begins when the sink
is unreachable.

## Context

During a recent epic drive, the feedback sink endpoint was unreachable for the
entire run. 23 `submit-failed` events occurred without detection — the drive
continued to completion but zero telemetry was captured. The root cause was a
missing gate: nothing prevented the drive from starting when telemetry
infrastructure was down.

The fix is lightweight. The `epic-supervisor` already performs a worktree
preflight check (§1.2 of `building-epics/SKILL.md`) and a `Master_Plan`
completeness check before dispatching any ticket. A single additional pre-flight
step — a connectivity ping to the feedback sink endpoint — closes this gap.

The check must appear in three places so that both the human operator and the
agent runtime are aware of it:

1. `CLAUDE.md` — a "Pre-Drive Checklist" section visible to any developer reading
   the repo guide. This doubles as the human-facing gate documentation.
2. `templates/skills/building-epics/SKILL.md` — the operational runbook loaded by
   `epic-supervisor` at startup; the check is embedded as a numbered pre-flight
   step so agents enforce it automatically.
3. `templates/agents/epic-supervisor.md` — "Pre-Flight Reads" section so the
   agent knows to execute the step and where the instructions live.

Related context: the `emit_event` telemetry calls in `building-epics/SKILL.md`
already reference `debugging/logs/agent_telemetry.jsonl` as the sink path;
the health-check should validate that the same path (or configured endpoint) is
writable before the drive begins.

## Acceptance Criteria

```gherkin
Given CLAUDE.md is opened by a developer before starting an epic drive
When they look for pre-drive guidance
Then a "Pre-Drive Checklist" section exists and contains a feedback-sink
  reachability item that explains what to check and what to do if it fails

Given epic-supervisor starts a drive
When the feedback sink endpoint (agent_telemetry.jsonl path or remote endpoint)
  is unreachable or unwritable
Then epic-supervisor surfaces a clear warning to the user before dispatching
  any ticket-supervisor, and does not silently proceed

Given epic-supervisor starts a drive
When the feedback sink is reachable and writable
Then epic-supervisor proceeds normally without any user-facing warning

Given a future developer reads building-epics/SKILL.md
When they look for pre-flight checks
Then the feedback-sink reachability check is documented as a numbered step
  alongside the existing worktree and Master_Plan checks
```

## Sign-offs

- [x] architect-review — 2026-05-28 08:00
- [x] documentation-expert — 2026-05-28 08:15
- [x] pr-reviewer — 2026-05-28 08:30
- [x] commit — 2026-05-28 08:45
- [x] pull-request — 2026-05-28 09:00

## Comments

### 2026-05-28 08:00 — architect-review (status: ok)
feedback-id: fb_2026-05-28_777d9724
Design approved. Warn-not-halt pattern for sink reachability is consistent with the existing orphan-process advisory pre-flight (step 6). Three-file touch is justified and correctly scoped. `debugging/logs/agent_telemetry.jsonl` path is consistent with existing emit_event calls. No architectural ambiguity; implementation is unambiguous. Handing to documentation-expert.

### 2026-05-28 08:15 — documentation-expert (status: ok)
feedback-id: fb_2026-05-28_da43d365
Added `## Pre-Drive Checklist` section with "Feedback sink reachable" item and probe script to CLAUDE.md. Added §1.0 (Feedback-Sink Reachability Pre-flight) to building-epics/SKILL.md before §1.1 — defines the writability probe, warn-not-halt failure behaviour, and user-confirmation flow. Added step 7 to epic-supervisor.md Pre-Flight Reads and updated the summary line from "six checks" to "seven checks". All acceptance criteria satisfied.

### 2026-05-28 08:30 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-28_592386c9
All three files correctly updated. Acceptance criteria satisfied: CLAUDE.md has Pre-Drive Checklist with sink probe and failure guidance; building-epics/SKILL.md has §1.0 with warn-not-halt recipe; epic-supervisor.md has step 7 referencing §1.0. Cross-references intact. No blockers.

### 2026-05-28 08:45 — commit (status: ok)
feedback-id: fb_2026-05-28_776616e1
Committed 4 files: CLAUDE.md, templates/skills/building-epics/SKILL.md, templates/agents/epic-supervisor.md, ticket (renamed 00_inbox → 01_todo). SHA: 29c0fdf. No pre-commit hook failures.

### 2026-05-28 09:00 — pull-request (status: ok)
feedback-id: fb_2026-05-28_d130f5a7
PR opened for branch worktree-TICKET-FeedbackSinkPreDriveCheck. All agents signed off.

## Implementation Tasks

### documentation-expert

- [x] Add a `## Pre-Drive Checklist` section to `leafcutter-ai/CLAUDE.md` (or extend an existing one if present). Include at minimum:
  - A checklist item titled "Feedback sink reachable" with a description of what to verify (e.g. that `debugging/logs/agent_telemetry.jsonl` is writable, or the configured remote endpoint responds to a test ping).
  - A note on what to do if the check fails: fix the sink before invoking `/build-feature`.
  - A brief rationale linking to this ticket (root cause: 23 silent `submit-failed` events during drive with no detection).
- [x] Add a numbered pre-flight step to `leafcutter-ai/templates/skills/building-epics/SKILL.md` (insert after the existing worktree preflight step, before the Master_Plan check). The step must:
  - Instruct `epic-supervisor` to verify feedback-sink reachability before dispatching any ticket.
  - Define the check: attempt a test write (or ping) to the configured sink path/endpoint; capture the exit code.
  - Define the failure behaviour: emit a structured warning to the user (`## Warning: Feedback sink unreachable`) and allow the user to proceed or abort — do not hard-halt silently and do not skip the warning.
- [x] Update `leafcutter-ai/templates/agents/epic-supervisor.md` `## Pre-Flight Reads` section to reference the new sink-check step in `building-epics/SKILL.md` so agents are aware the step exists and must be executed.

## Risk & Safety

- Touches money? No.
- Touches data? No — the check is a read/probe operation against a log file or endpoint; no writes to production data.
- Reversibility? Fully reversible — all changes are documentation and agent prompt edits. No schema or compiled-code changes.
- Shared contract? `building-epics/SKILL.md` is loaded by both `epic-supervisor` and `ticket-supervisor` on every invocation. Any addition to its pre-flight section is immediately live for both agents. Verify the new step does not disrupt existing pre-flight sequencing before merging.
