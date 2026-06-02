---
title: "Enhance build-ticket.js planner to cross-validate frontmatter agents map against Sign-offs checklist"
status: todo
components:
  - build_pipeline
created: 2026-06-02
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/workflows-js/build-ticket.js
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
---

# Enhance build-ticket.js planner to cross-validate frontmatter agents map against Sign-offs checklist

## Actor / Goal

In order to prevent stale frontmatter from causing unnecessary re-runs of already-signed-off phases (or skipping phases the Sign-offs section still marks as needed), we need to teach the Step 1 planner agent to read BOTH the YAML `agents:` map AND the `## Sign-offs` checklist from the ticket body, cross-validate them, and use the `## Sign-offs` section as the authoritative source when they diverge.

## Context

`build-ticket.js` Step 1 dispatches a `status-checker` agent whose instructions (lines 168–184) tell it to read only the YAML frontmatter `agents:` map. The `## Sign-offs` checklist in the ticket body is the canonical runtime source of truth for sign-off state: checked boxes (`- [x] <agent> — YYYY-MM-DD HH:MM`) mean an agent has signed off; unchecked boxes (`- [ ] <agent>`) mean it has not. The frontmatter `agents:` map is set at ticket-authoring time and may drift from the Sign-offs section if:

- A phase agent ticks the Sign-offs box but a crash prevents the corresponding frontmatter update from being committed.
- A human manually edits one but not the other.
- A re-run starts from a partially-completed state where the frontmatter still says `needed` for an agent that already signed off.

The `check-ticket-signoff-parity` pre-commit hook enforces parity at commit time, but during an active `build-ticket.js` run the two can diverge in the working tree. The planner must reconcile them at plan-time so the `ordered_phases` array reflects actual current state, not stale frontmatter.

### Sign-off format reference

| State | Body format | Derived status |
|-------|-------------|----------------|
| Pending | `- [ ] <agent-name>` | `needed` |
| Signed-off | `- [x] <agent-name> — YYYY-MM-DD HH:MM` | `signed_off` |
| Failed | `- [ ] <agent-name> — failed YYYY-MM-DD HH:MM` | `failed` |

The em-dash separator is `—` (U+2014). The timestamp suffix is `YYYY-MM-DD HH:MM`.

### Relevant file location

`templates/workflows-js/build-ticket.js`, specifically the `instructions` string
passed in the `plannerResult = await agent(...)` call at lines 168–184.

## Acceptance Criteria

```gherkin
Given a ticket whose frontmatter says "python-coder: needed" but whose ## Sign-offs section has "- [x] python-coder — 2026-06-01 14:30"
When build-ticket.js Step 1 runs the planner agent
Then the planner returns ordered_phases with python-coder status "signed_off"
And a drift_warnings entry noting the frontmatter/Sign-offs discrepancy

Given a ticket whose frontmatter says "pr-reviewer: signed_off" but whose ## Sign-offs section has "- [ ] pr-reviewer"
When build-ticket.js Step 1 runs the planner agent
Then the planner returns ordered_phases with pr-reviewer status "needed"
And a drift_warnings entry noting the frontmatter/Sign-offs discrepancy

Given a ticket where frontmatter agents: map and ## Sign-offs section are fully consistent
When build-ticket.js Step 1 runs the planner agent
Then ordered_phases matches both sources with no drift_warnings emitted

Given the ## Sign-offs section is absent from the ticket body
When build-ticket.js Step 1 runs the planner agent
Then the planner falls back to frontmatter agents: map with no error
And a drift_warnings entry notes that ## Sign-offs was absent
```

## Sign-offs

- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

- [ ] Update the `instructions` string in the `plannerResult = await agent(...)` call (Step 1, lines 168–184 of `templates/workflows-js/build-ticket.js`) to instruct the `status-checker` agent to:
  1. Read the YAML `agents:` map from ticket frontmatter (existing behaviour).
  2. Locate and parse the `## Sign-offs` section in the ticket body. For each checkbox line:
     - `- [x] <agent> — YYYY-MM-DD HH:MM` → derive status `signed_off`
     - `- [ ] <agent> — failed YYYY-MM-DD HH:MM` → derive status `failed`
     - `- [ ] <agent>` (no timestamp) → derive status `needed`
  3. Cross-validate: for each agent present in either source, compare the frontmatter status against the Sign-offs-derived status. When they differ, log a warning entry in `drift_warnings` and use the Sign-offs value as the authoritative status in `ordered_phases`.
  4. Fall back to frontmatter-only when `## Sign-offs` is absent; include a `drift_warnings` entry noting the absence.
  5. Return the JSON object with an additional optional key: `"drift_warnings": ["<message>", ...]` (empty array when no drift detected).

- [ ] Update the JSON schema comment in the `instructions` string to document the new optional `drift_warnings` key:
  ```
  { "ticket_path": "<path>", "title": "<ticket title>",
    "files_touched": ["..."],
    "ordered_phases": [{"agent": "<name>", "status": "<status>"}, ...],
    "drift_warnings": ["<warning message>", ...] }
  ```

- [ ] After `plan = ...` is parsed (around line 190), surface `plan.drift_warnings` (if non-empty) as a console-level notice so the user sees the reconciliation log without stopping the workflow. No change to the `ordered_phases` filtering logic in Step 2 — that already filters on `status === "needed"` and will correctly skip reconciled `signed_off` phases.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? The change is limited to the instruction string passed to a sub-agent. Reverting is a one-commit rollback. No schema migrations, no public API changes.
- Correctness risk: if the Sign-offs parser regex is too broad or too narrow it may misclassify a phase. The status-checker agent already reads the raw file, so the fix is confined to the instruction prompt. Regression is caught by the planner's JSON output being observable in logs.
- No impact on the `check-ticket-signoff-parity` pre-commit hook — that hook operates at commit time on the file as written; this change only affects the runtime planner read path.
