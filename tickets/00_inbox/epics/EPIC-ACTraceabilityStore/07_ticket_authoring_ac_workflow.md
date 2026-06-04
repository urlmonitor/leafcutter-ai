---
title: "Update ticket-authoring skill: tickets reference ACs; BA creates/amends AC files"
status: todo
components:
  - build_pipeline
created: 2026-06-04
depends_on:
  - 01_ac_store_schema.md
  - 02_ac_store_directory_scaffold.md
  - 05_ba_agent_ac_query.md
priority: medium
roadmap_phase: phase_2
advances_current_outcome: false
requires_diagram: false
requires_adr: false
files_touched:
  - leafcutter-ai/templates/skills/ticket-authoring/SKILL.md
  - leafcutter-ai/templates/skills/ticket-wiring/SKILL.md
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

# 07: Update ticket-authoring skill: tickets reference ACs; BA creates/amends AC files

## Actor / Goal

In order to make the ticket-authoring workflow consistent with the AC store
model, we need to update the `ticket-authoring/SKILL.md` and
`ticket-wiring/SKILL.md` templates to describe how tickets reference ACs
rather than own them, and to specify that the wiring phase must write
AC YAML files when the BA's `ac_creations` and `ac_amendments` fields are
non-empty.

## Context

With the AC store in place (tickets 01 and 02) and the BA querying it (ticket 05),
the wiring phase now has two AC-related responsibilities:

1. **Write new AC files** for each entry in `ba_output.ac_creations`. Place
   the file at `docs/acceptance-criteria/{component}/{id}.yaml`, populated
   from the BA's proposed content.
2. **Amend existing AC files** for each entry in `ba_output.ac_amendments`.
   Update the `criteria` field, append the current ticket ref to `amended_by`,
   and leave `id`, `title`, `component`, and `status` unchanged.

The ticket body should reference ACs by ID: "This ticket implements
AC-FIN-003 and amends AC-FIN-001." The Gherkin in the ticket body is
retained for human readability but the AC YAML is the source of truth.

The `ticket-authoring/SKILL.md` updates document the referencing convention.
The `ticket-wiring/SKILL.md` updates add AC file writing as a wiring step
(between Step 2 and Step 3 of the existing skill).

### Wiring order

1. Resolve `files_touched` and `agents` (existing Step 1).
2. Build ticket frontmatter and body (existing Step 2).
3. **New: Write/amend AC YAML files** from `ba_output.ac_creations` and
   `ba_output.ac_amendments`. Run `check_ac_schema.py` against each new file
   before writing.
4. Verify ticket via `ticket_frontmatter_guard` (existing Step 3 → now Step 4).

## Acceptance Criteria

```gherkin
Given ticket-wiring/SKILL.md is updated
When the wiring skill executes with ba_output.ac_creations non-empty
Then each entry in ac_creations is written as a YAML file at the correct path
 And the file validates against the AC schema
 And the ticket body references the new AC ID

Given ticket-wiring/SKILL.md is updated
When the wiring skill executes with ba_output.ac_amendments non-empty
Then each amended AC file has its criteria field updated
 And the current ticket ref is appended to the amended_by list
 And no other fields are changed

Given ba_output.ac_creations and ba_output.ac_amendments are both empty
When the wiring skill executes
Then no AC YAML files are written or modified
 And the wiring proceeds as before

Given ticket-authoring/SKILL.md is reviewed
When the AC referencing convention section is read
Then it explains that Gherkin in ticket body is for human readability
 And it states the AC YAML is the canonical source of truth
 And it shows the referencing format "implements AC-FIN-003"
```

## Sign-offs

- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

- [ ] In `templates/skills/ticket-authoring/SKILL.md`:
  - Add a new section "AC Referencing Convention" (after the Frontmatter
    schema section):
    - Explain: "Tickets do not own ACs. They reference them. Use the format
      `implements AC-FIN-003` in the `## Context` section or a dedicated
      `## AC References` section."
    - Explain: "When a ticket amends existing behaviour, state which AC is
      amended: `amends AC-FIN-001 (adds merge_conflict halt category)`."
    - The Gherkin in `## Acceptance Criteria` remains for human readability;
      it mirrors (does not replace) the AC YAML content.
- [ ] In `templates/skills/ticket-wiring/SKILL.md`:
  - Add a new Step 2.5 between Step 2 (build ticket) and Step 3 (verify):
    - "If `ba_output.ac_creations` is non-empty: for each entry, write
      `docs/acceptance-criteria/{component}/{id}.yaml` populated from the
      entry's fields. Validate against `check_ac_schema.py` before writing.
      On validation failure: abort with an error listing the failing field."
    - "If `ba_output.ac_amendments` is non-empty: for each entry, read the
      existing AC file, update `criteria` with the new value, append the
      current ticket path to `amended_by`. Write back."
    - "If both are empty: skip this step."

## Risk & Safety

- Touches money? No.
- Touches data? No. Template edits plus new AC YAML files (additive).
- Reversibility? Skill template edits are in the template source; reverting
  them stops the new behaviour on the next build. Existing AC YAML files in
  a target project remain but are inert without the hooks.
- The schema validation guard before writing new AC files (Step 2.5) prevents
  malformed YAML from entering the store.
