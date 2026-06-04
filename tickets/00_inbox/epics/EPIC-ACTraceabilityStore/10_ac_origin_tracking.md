---
title: "AC origin tracking — ACs must record which agent created them"
status: todo
components:
  - build_pipeline
created: 2026-06-04
depends_on:
  - done/01_ac_store_schema.md
priority: medium
roadmap_phase: phase_2
advances_current_outcome: false
requires_diagram: false
requires_adr: false
files_touched:
  - config/ac_store_schema.json
  - templates/agents/business-analyst.md
  - templates/skills/debug/SKILL.md
agents:
  architect-review: needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
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

# 10: AC origin tracking — ACs must record which agent created them

## Actor / Goal

In order to give every AC file a clear provenance record, we need to
extend the AC YAML schema with an `origin_agent` field and update each
AC-authoring code path (BA agent, debug skill, and human manual workflow)
to stamp the field at creation time, so that operators can audit which
agent or workflow introduced an AC and whether it was reviewed before
entering the store.

## Context

The schema defined in ticket 01 (`config/ac_store_schema.json`) already
captures `created_by` as the ticket-path reference that first introduced
the criterion. That field answers "which ticket?" — but not "which agent
inside that ticket workflow?".

Three distinct authoring paths create AC YAML files today:

1. **BA agent** (`templates/agents/business-analyst.md` + ticket-wiring
   skill, ticket 07) — the most common path; the BA proposes new ACs via
   `ac_creations` in its JSON output and the wiring skill writes the YAML.
2. **Debug skill** (`templates/skills/debug/SKILL.md`) — when the debug
   investigation results in a fix ticket, the `create-ticket` sub-agent
   inside debug may spawn a BA agent that also writes ACs.
3. **Human manual** — an operator hand-writes an AC YAML file directly
   (documented in the `how-to` from ticket 09).

Without an `origin_agent` field, a compliance audit cannot distinguish
machine-generated ACs (which should be reviewed) from human-authored ones
(which are presumed intentional), nor can it identify which automated
workflow wrote the file.

### Schema amendment

Add `origin_agent` as an optional field to `config/ac_store_schema.json`:

```json
"origin_agent": {
  "type": "string",
  "description": "Identity of the agent or workflow that created this AC file. Enum: business-analyst | debug | human | ticket-wiring. Free-form string to allow future agents.",
  "minLength": 1
}
```

The field is optional (not added to `required`) to remain backward
compatible with AC files written by ticket 01 before this ticket lands.
The validator script (`check_ac_schema.py`) already handles
`additionalProperties: false` — adding the field here unlocks it without
breaking existing valid files.

### Stamping rules per authoring path

| Path | Value to write |
|------|----------------|
| BA agent JSON output → ticket-wiring | `origin_agent: business-analyst` |
| Debug skill → create-ticket → BA agent | `origin_agent: debug` |
| Human manual | `origin_agent: human` |
| ticket-wiring acting on `ac_creations` with no explicit source | `origin_agent: ticket-wiring` |

### Relationship to existing fields

- `created_by` (ticket path): unchanged — still records the ticket that
  introduced the criterion.
- `origin_agent` (new): records the authoring workflow. The two fields are
  complementary: `created_by` answers "what was being built?" and
  `origin_agent` answers "who wrote the AC?".

### Dependency note

This ticket amends `config/ac_store_schema.json`, which was written and
merged by ticket 01. The `depends_on` points at the done/ location of
ticket 01 to make the dependency explicit without blocking on the ticket's
in-folder presence.

## Acceptance Criteria

```gherkin
Given config/ac_store_schema.json is updated with the origin_agent property
When check_ac_schema.py validates an AC YAML file that omits origin_agent
Then validation passes (field is optional; existing ACs are not broken)

Given config/ac_store_schema.json is updated with the origin_agent property
When check_ac_schema.py validates an AC YAML file that includes origin_agent: "business-analyst"
Then validation passes

Given config/ac_store_schema.json is updated with the origin_agent property
When check_ac_schema.py validates an AC YAML file with an empty string origin_agent: ""
Then validation fails with a message citing the minLength constraint

Given templates/agents/business-analyst.md is updated
When the BA agent produces an ac_creations entry
Then each entry in ac_creations includes origin_agent: "business-analyst"
 And the ticket-wiring skill writes that value into the YAML file

Given templates/skills/debug/SKILL.md is updated
When the debug skill spawns create-ticket as part of its Step 4 workflow
Then the prompt passed to create-ticket includes the instruction
 "Set origin_agent: debug for any AC YAML files written during this ticket"

Given an operator writes an AC YAML file manually
When the file omits origin_agent
Then check_ac_schema.py still exits 0 (field is optional)
 And the how-to documentation recommends setting origin_agent: "human"
```

## Sign-offs

- [ ] architect-review
- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### architect-review
- [ ] Confirm `origin_agent` as an optional (not required) field — verify
  backward compatibility: existing valid AC files produced by ticket 01
  must still pass `check_ac_schema.py` after the schema update. Approve
  before python-coder amends the schema.

### python-coder
- [ ] In `config/ac_store_schema.json`: add `origin_agent` to `properties`
  as a `type: string, minLength: 1` field with the description from the
  Context section above. Do NOT add it to `required`.
- [ ] In `templates/commit-guardian/check_ac_schema.py`: no logic changes
  required — `additionalProperties: false` in the schema already unlocks
  the new field for existing-file validation. Verify by running the
  existing test suite; all tests must still pass.
- [ ] In `templates/agents/business-analyst.md`: in the `ac_creations`
  output JSON block, add `"origin_agent": "business-analyst"` as a
  required field in each creation entry. Update the description text
  ("Each `ac_creations` entry must include an `origin_agent` field set to
  `\"business-analyst\"`").
- [ ] In `templates/skills/debug/SKILL.md`: in Step 4 ("Create Fix Ticket"),
  add an explicit instruction to the `create-ticket` prompt template:
  "Instruct the BA/wiring step to set `origin_agent: debug` on any AC
  YAML files created as part of this fix ticket."

### test-writer
- [ ] In `unit_tests/commit_guardian/test_check_ac_schema.py`, add:
  - `test_origin_agent_optional` — AC YAML without `origin_agent`
    validates successfully.
  - `test_origin_agent_valid_string` — AC YAML with
    `origin_agent: "business-analyst"` validates successfully.
  - `test_origin_agent_empty_string_blocked` — AC YAML with
    `origin_agent: ""` exits 1 (minLength violation).

## Risk & Safety

- Touches money? No.
- Touches data? No. Schema extension is additive; existing AC files are
  not modified by this ticket.
- Reversibility? Removing the `origin_agent` property from the JSON Schema
  and reverting the template edits fully restores prior behaviour. Any AC
  files in a target project that already have `origin_agent` set would
  need the field removed or `additionalProperties: false` relaxed — a
  one-time migration that is straightforward with a find-and-sed pass.
- Blast radius: small. Three template files and one config file. No
  Alembic migration, no public API change, no ADR contract modification.
  The schema change is a pure addition to `properties`; no existing `required`
  list changes.
