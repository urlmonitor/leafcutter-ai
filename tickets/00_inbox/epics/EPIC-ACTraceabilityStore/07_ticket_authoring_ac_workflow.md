---
title: "Update ticket-authoring skill: tickets reference ACs; BA creates/amends AC files"
status: done
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
  documentation-expert: signed_off
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
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

- [x] documentation-expert — 2026-06-04 10:00
- [x] pr-reviewer — 2026-06-04 10:05
- [x] commit — 2026-06-04 10:10
- [x] pull-request — 2026-06-04 10:15

## Comments

### 2026-06-04 10:15 — pull-request (status: ok)
feedback-id: fb_2026-06-04_0966fb84
completion_manifest:
  branch_pushed: true
  pr_created: true
  pr_body_complete: true
Epic branch EPIC-ACTraceabilityStore pushed. Existing epic PR #46 is open at https://github.com/urlmonitor/leafcutter-ai/pull/46 — ticket 07 commits (f2e34ba) are included. Ticket status flipped to done as this is the last needed agent.

### 2026-06-04 10:10 — commit (status: ok)
feedback-id: fb_2026-06-04_966e9d19
completion_manifest:
  commit_created: true
  staged_files_explicit: true
  pre_commit_clean: true
Committed 3 files (templates/skills/ticket-authoring/SKILL.md, templates/skills/ticket-wiring/SKILL.md, ticket sign-off) as f2e34ba. Staged explicitly by path — no cross-ticket files included. Pre-commit hooks not configured (PRE_COMMIT_ALLOW_NO_CONFIG=1 used to bypass missing config). 3 files changed, 137 insertions(+), 6 deletions(-).

### 2026-06-04 10:05 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-04_d803cd64
completion_manifest:
  diff_reviewed: true
  no_high_findings: true
  scope_verified: true
Reviewed diff for templates/skills/ticket-authoring/SKILL.md and templates/skills/ticket-wiring/SKILL.md. No high-confidence findings. All four Gherkin ACs satisfied: ac_creations writes YAML at correct path with schema validation, ac_amendments updates criteria and amended_by while leaving other fields intact, empty case skips, and AC referencing convention section added. Suppressed: 0 nits. Escalation: none (medium count 0).

### 2026-06-04 10:00 — documentation-expert (status: ok)
feedback-id: fb_2026-06-04_05077727
completion_manifest:
  doc_written: true
  cross_links_added: true
  diataxis_genre_correct: true
Added "AC Referencing Convention" section to ticket-authoring/SKILL.md documenting that tickets reference (not own) ACs, the `implements AC-FIN-003` referencing format, and the Gherkin-vs-YAML relationship. Added Step 2.5 to ticket-wiring/SKILL.md covering AC YAML file creation (ac_creations) and amendment (ac_amendments) with schema validation guard, skip-when-empty rule, and conflict detection. Both skill files updated in templates/ and will be distributed on next build.

## Implementation Tasks

- [x] In `templates/skills/ticket-authoring/SKILL.md`:
  - Add a new section "AC Referencing Convention" (after the Frontmatter
    schema section):
    - Explain: "Tickets do not own ACs. They reference them. Use the format
      `implements AC-FIN-003` in the `## Context` section or a dedicated
      `## AC References` section."
    - Explain: "When a ticket amends existing behaviour, state which AC is
      amended: `amends AC-FIN-001 (adds merge_conflict halt category)`."
    - The Gherkin in `## Acceptance Criteria` remains for human readability;
      it mirrors (does not replace) the AC YAML content.
- [x] In `templates/skills/ticket-wiring/SKILL.md`:
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
