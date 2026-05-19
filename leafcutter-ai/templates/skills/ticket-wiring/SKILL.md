---
name: ticket-wiring
description: |
  Procedural skill for assembling a complete ticket file from collected
  business-analyst, refinement, and architect-review outputs. Handles wiring
  rules (files_touched, agents map, Sign-offs, Comments), error recovery when
  a payload is missing, and pre-write parity verification. Used by the
  create-ticket agent after gathering all upstream outputs.
allowed-tools: Bash, Read, Edit, Write
---

# ticket-wiring Skill

This skill owns the template assembly phase of ticket creation. It converts
structured outputs from upstream agents into a valid, guard-passing ticket file.

## Input Contract

You receive (at minimum) these collected payloads before invoking this skill:

```
ba_output:          structured JSON from business-analyst (may be absent — see
                    Error Recovery Path)
refinement_output:  structured JSON from refinement (may be absent — see
                    Error Recovery Path)
architect_output:   structured JSON from architect-review (optional; may be
                    absent without triggering the error recovery path)
registry_table:     {{registry_phase_agents_table}}
                    (injected at build time — lists all is_ticket_phase agents
                    with default_status and trigger_conditions)
ticket_path:        target path where the ticket file should be written
```

## Step 1 — Source Resolution (Priority Chain)

Resolve `files_touched` and `agents` from this priority chain:

1. **refinement** output — use when present and non-empty.
2. **business-analyst** output — fall back when refinement omitted them.
3. **Registry defaults** (error recovery, epic sub-tickets only) — apply when
   neither BA nor refinement provided an agents map.

The `agents` map values MUST be one of `needed` or `not_needed` at creation
time. If you see any other value (`signed_off`, `failed`, anything else), STOP
and re-run refinement — those are runtime-only transitions and would be
rejected by the parity guard downstream.

### Reading architect-review signals

When `architect_output` is present, also read these fields:

- `suggested_diagrams` — a list of `{"diagram_type": "<type>", "path": "<target path>", "parent": "<parent diagram path>"}` objects (may be absent or empty list).
- `suggested_adr` — a string ADR topic (may be absent or null).
- `requires_documentation` — a list of doc type strings from `doc_types.json` (may be absent or empty list).

Also read `ba_output.requires_documentation` when `architect_output` is absent or does not
include this field. Priority: architect-review wins over business-analyst when both supply the field.

These signals drive Step 2 wiring decisions below. If `architect_output` is
absent entirely, treat all three fields as empty (no Architecture Plan emitted,
no agents flipped).

## Step 2 — Build the Ticket File

Load and follow `.claude/skills/ticket-authoring/SKILL.md` for the canonical:
- Frontmatter schema (title, status, components, created, depends_on, priority,
  plus the optional `files_touched` and `agents` fields)
- Folder routing (00_inbox/ vs 01_todo/ vs epic subfolder)
- Naming convention (TICKET-YYYYMMDD-Name.md or NN_snake_case.md)
- Body structure (Goal, Context, Acceptance Criteria, Sign-offs, Comments,
  Implementation Tasks, Risk & Safety) — section ordering is **verbatim** from
  the skill skeleton; do not reorder

Wire the resolved fields as follows:

### Frontmatter

Write `files_touched` and `agents` into the ticket frontmatter exactly as they
appear in the upstream payload. Do not mutate keys, paths, or status values.

**`requires_diagram` and `requires_adr` are REQUIRED fields (tri-state, ADR-026):**

Both `requires_diagram` and `requires_adr` MUST be present in every ticket
frontmatter. Valid values are `true`, `false`, and `null` (YAML null). The
`ticket_frontmatter_guard` hook blocks any ticket that is missing either field.

- `true` — a diagram/ADR IS needed and must be produced.
- `false` — agent considered this and decided no diagram/ADR is needed.
- `null` — agent considered this and decided it is not applicable (e.g. diagram
  already exists from a prior dependency; ADR was authored in a parent ticket).

Emit these fields as part of every ticket wire-up, even when the
architect-review output is absent. Use `false` as the default when there is no
signal suggesting a diagram or ADR is needed.

**architect-review signal wiring (applies when `architect_output` is present):**

- When `architect_output.suggested_diagrams` is non-empty:
  - Set `architecture-diagram-author: needed` in the `agents` map.
  - Set `requires_diagram: true` in the frontmatter.
- When `architect_output.suggested_adr` is non-empty (non-null string) **or**
  when `architect_output.requires_adr == true`:
  - Set `adr-author: needed` in the `agents` map.
  - Set `requires_adr: true` in the frontmatter.
  - This rule **supersedes** any earlier BA/refinement payload that set
    `adr-author: not_needed`. The architect-review judgment is authoritative;
    a prior `not_needed` value from upstream must be overridden here.
- When `requires_documentation` (resolved from architect-review or business-analyst
  per the Priority Chain above) is non-empty:
  - For each entry in the list, look up `writer_agent` in `doc_types.json`. When
    `writer_agent` is non-null, set `<writer_agent>: needed` in the `agents` map.
  - Set `requires_documentation: [<entries>]` in the frontmatter.
  - See the Doc Type → Agent mapping: `how_to` → `how-to-author`,
    `reference` → `reference-author`, `explanation` → `explanation-author`,
    `adr` → `adr-author`, `architecture` → `architecture-diagram-author`,
    `retro` → `retrospective-agent`, `tutorial` → no writer agent (skip).
- When all three fields are empty/absent: leave `architecture-diagram-author`,
  `adr-author`, and all doc-writer agents at their default (`not_needed`).
  Still emit `requires_diagram: false` and `requires_adr: false` in frontmatter
  (explicitly marking "considered, not needed") — do not emit `requires_documentation`.

### Architecture Plan Section

When `architect_output.suggested_diagrams` is non-empty OR
`architect_output.suggested_adr` is non-empty, insert a `## Architecture Plan`
section **after `## Context`** and **before `## Acceptance Criteria`** with the
following structure:

```markdown
## Architecture Plan

### Diagrams

- `{diagram_type}` diagram at `{path}` (parent: `{parent}`)
  _(One bullet per entry in suggested_diagrams.)_

### ADRs

- `{suggested_adr}` — new ADR to be authored before coding begins.

### Documentation

- `{doc_type}` doc at `{default_path}` — {description}
  _(One bullet per entry in requires_documentation; path from doc_types.json default_path.)_
```

Omit the `### Diagrams` subsection entirely when `suggested_diagrams` is empty.
Omit the `### ADRs` subsection entirely when `suggested_adr` is empty.
Omit the `### Documentation` subsection entirely when `requires_documentation` is empty.
Omit `## Architecture Plan` entirely when all three are empty.

### Sign-offs Section

Place this section **after `## Acceptance Criteria`** (or after
`## Architecture Plan` when that section exists) and **before `## Comments`**,
matching the canonical skeleton.

- For every entry in the `agents` map whose status is `needed`, emit one
  line: `- [ ] <agent-name>` (bare unchecked checkbox; no timestamp, no
  extra text).
- Entries with status `not_needed` MUST NOT appear under `## Sign-offs`.
- The result is a 1-to-1 mirror of the `needed` subset of `agents:`. The
  parity guard will reject any divergence.
- When `architecture-diagram-author: needed` was flipped by an
  architect-review signal, its sign-off line MUST appear in `## Sign-offs`.
  The parity guard will reject omissions.

**Sign-off format reference (for the agent that will tick the box later):**

| Status      | Format                                                  |
|-------------|---------------------------------------------------------|
| Pending     | `- [ ] <agent-name>`                                    |
| Signed-off  | `- [x] <agent-name> — YYYY-MM-DD HH:MM`                 |
| Failed      | `- [ ] <agent-name> — failed YYYY-MM-DD HH:MM`          |

The `check-ticket-signoff-parity` pre-commit hook enforces the timestamped
form for any `signed_off` agent in frontmatter — a checked box without the
`— YYYY-MM-DD HH:MM` suffix will block the commit. The em-dash separator
is `—` (U+2014), not a hyphen. See
`.claude/skills/signoff/SKILL.md` §2 and §4 for the full sign-off recipe.

### Comments Section

Place immediately after `## Sign-offs`. Emit only the heading followed by
a single blank line. Do NOT add a placeholder, italic note, or comment entry.

## Step 3 — Error Recovery Path

**When this fires:** BA always runs before this skill, and refinement always
runs for standard tickets. This path fires only when one of them crashes or
returns no usable payload. It is NOT a normal invocation mode — it is a
defensive guard.

**Two known entry conditions:**

- **BA crash guard**: `business-analyst` failed or returned an empty/malformed
  payload. Log the failure and surface a warning to the user.
- **Direct invocation on an existing stub**: a user manually invokes
  `create-ticket` pointing at a pre-written stub file without any BA payload.
  The user is responsible for supplying the context.

**Note:** When `create-epic` calls `create-ticket` with `stub_path`, BA
**still runs** at Step 1. This path does NOT apply to stub hardening.

Apply this recovery logic:

- **For standalone tickets** (in `00_inbox/` root, not inside an epic folder):
  **OMIT** the optional `files_touched` and `agents` frontmatter fields
  entirely. Also **OMIT** the `## Sign-offs` and `## Comments` body sections.

- **For epic sub-tickets** (inside an `EPIC-*/` folder): you MUST still emit
  a default `agents` map. Infer the archetype from the ticket title / file
  path and use the injected `registry_table` above to select agents and their
  `default_status` values. Include matching `## Sign-offs` checkboxes and an
  empty `## Comments` section. Without `agents:`, `ticket-supervisor` will
  block the ticket as un-driveable when `/build-feature` runs.

## Step 4 — Verify

After writing the ticket file, verify it passes the
`ticket_frontmatter_guard` PostToolUse hook (which fires automatically on
Write). If the hook reports an error:

- Re-read the error message, fix the offending field, and re-Write the file.
- Do not return success until the guard accepts the file.
- If the guard accepts but you suspect parity issues (a `needed` agent missing
  from `## Sign-offs`), fix it now — the parity guard will block the commit
  phase later.

After the file is clean, cross-link it in the epic's `Master_Plan.md`
sub-ticket table if this ticket belongs to an in-progress epic.
