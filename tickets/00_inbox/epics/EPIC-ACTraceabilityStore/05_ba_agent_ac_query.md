---
title: "Update BA agent to query existing ACs before writing new ones"
status: todo
components:
  - build_pipeline
created: 2026-06-04
depends_on:
  - 02_ac_store_directory_scaffold.md
priority: medium
roadmap_phase: phase_2
advances_current_outcome: false
requires_diagram: false
requires_adr: false
files_touched:
  - templates/agents/business-analyst.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 05: Update BA agent to query existing ACs before writing new ones

## Actor / Goal

In order to prevent the BA from silently creating duplicate or contradictory
ACs, we need to update the `business-analyst` agent template to include an
AC query step at the start of its analysis, so that the BA sees all existing
active ACs for the relevant components before drafting acceptance criteria for
a new ticket.

## Context

Currently the BA writes ACs in ticket bodies from scratch on each ticket.
When the AC store exists (ticket 02), the BA must first read
`docs/acceptance-criteria/{component}/` and load all active ACs for
components the ticket touches.

The query informs three things:
1. **Avoid duplicates.** If `FIN-001` already captures "merge main before
   running tests," the new ticket should reference it rather than re-state it.
2. **Identify amendments.** If the ticket changes existing behaviour, the BA
   notes which ACs are amended and what the new Gherkin should be.
3. **Identify gaps.** If the ticket introduces genuinely new behaviour with
   no existing AC, the BA creates new AC YAML files.

### BA output additions

The BA output JSON gains two new optional fields:

```json
{
  "ac_amendments": [
    {
      "ac_id": "FIN-001",
      "change": "Add merge_conflict halt category to the Then clause.",
      "new_criteria": "Given ... When ... Then ... And ..."
    }
  ],
  "ac_creations": [
    {
      "proposed_id": "FIN-004",
      "title": "Triage agent classifies regression failures",
      "criteria": "Given ... When ... Then ..."
    }
  ]
}
```

These fields are consumed by the ticket-wiring skill (ticket 07) to
actually write or amend the AC YAML files as part of ticket creation.

### Fallback

If `docs/acceptance-criteria/` does not exist in the target project
(pre-ticket-02 install), the BA skips the AC query step and proceeds
as before (tickets are still created without AC file wiring).

## Acceptance Criteria

```gherkin
Given business-analyst.md is updated and docs/acceptance-criteria/finalize/ exists
When the BA analyzes a ticket touching the finalize component
Then the BA reads all .yaml files in docs/acceptance-criteria/finalize/
 And the BA output includes ac_amendments and ac_creations fields

Given the BA reads an existing AC that the new ticket does not change
When the BA outputs its analysis
Then ac_amendments does not include that AC
 And the ticket body references it with "implements AC-FIN-001"

Given docs/acceptance-criteria/ does not exist
When the BA runs
Then the AC query step is skipped
 And the BA output does not include ac_amendments or ac_creations
 And ticket creation proceeds normally
```

## Sign-offs

- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

- [ ] In `templates/agents/business-analyst.md`, add a new step before the
  existing analysis steps:
  - **Step 0: AC Store Query** — "Check if `docs/acceptance-criteria/`
    exists in the target project. If it exists, for each component in
    `components` from the ticket request, read all `.yaml` files in
    `docs/acceptance-criteria/{component}/` where `status: active`. Load
    the `id`, `title`, and `criteria` fields for each. Store in working
    context as `existing_acs`."
  - Update the analysis instructions to say: "When drafting ACs, compare
    against `existing_acs`. For each proposed AC: (a) if it matches an
    existing AC, reference it; (b) if it amends an existing AC, add to
    `ac_amendments`; (c) if it is new, add to `ac_creations`."
  - Update the output JSON block to include `ac_amendments` and
    `ac_creations` (both optional, default `[]` when AC store is absent).
- [ ] Ensure the fallback condition is explicit: "If
  `docs/acceptance-criteria/` does not exist, set `ac_amendments: []` and
  `ac_creations: []` and skip the query."

## Risk & Safety

- Touches money? No.
- Touches data? No. The BA agent is read-only in this ticket — it reads AC
  files but does not write them. Writing is handled by the wiring skill
  (ticket 07).
- Reversibility? Template edit. Reverting the business-analyst.md template
  restores prior behaviour. Existing AC files are not affected.
