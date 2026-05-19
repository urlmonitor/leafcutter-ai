---
title: "Tickets Lifecycle — Quick Reference"
type: reference
status: active
created: 2026-05-13
last_updated: 2026-05-14
components:
  - infrastructure
---

# Tickets Lifecycle — Quick Reference

This folder contains the canonical folder skeleton and lifecycle documentation for the
`tickets/` work-item system. Copy this entire `templates/` tree into any repo adopting
the portable dev workflow; then start creating tickets following the conventions below.

---

## Folder Tree

```
tickets/
  00_inbox/                  Proposed work — not yet committed to
    TICKET-YYYYMMDD-Name.md  Single ticket
    epics/
      EPIC-Name/             Proposed epic (multi-ticket body of work)
        Master_Plan.md
        01_first_sub.md
        02_second_sub.md
        ...
  01_todo/                   Actively in-flight work
    TICKET-YYYYMMDD-Name.md  Single ticket being worked on
    EPIC-Name/               Epic currently in progress (one git worktree per epic)
      Master_Plan.md
      01_*.md, 02_*.md, ...
      done/                  Completed sub-tickets within the live epic
        01_*.md
  99_done/                   Archived finished epics and single tickets
  99_rejected/               Decided-against work items (not deleted — kept for history)
```

The `templates/` subdirectories below are starter placeholders:

| Folder | Contents |
|--------|----------|
| `templates/00_inbox/` | Drop new ticket proposals here (`.gitkeep` placeholder) |
| `templates/01_todo/` | Move tickets here when actively in flight (`.gitkeep` placeholder) |
| `templates/99_done/` | Archive completed tickets here (`.gitkeep` placeholder) |
| `templates/epics/` | Place epic folders here under `00_inbox/epics/` (`.gitkeep` placeholder) |

---

## Naming Conventions

| Artifact | Pattern | Example |
|----------|---------|---------|
| Single ticket | `TICKET-YYYYMMDD-Name.md` | `TICKET-20260513-Add_retry_logic.md` |
| Epic folder | `EPIC-Name/` | `EPIC-PortableDevWorkflow/` |
| Sub-ticket | `NN_snake_case_slug.md` | `03_parameterise_skills.md` |
| Master plan | `Master_Plan.md` | — |

- `NN` is a zero-padded integer encoding intended execution order.
- Use `02a`, `02b` when a single step splits into parallel sub-tasks.
- Numbers may be sparse (`05`, `07`, `12`) to leave gaps for future sub-tickets.

---

## Frontmatter Contract

Every ticket file (excluding `README.md`) requires YAML frontmatter between `---` markers.

### Sub-ticket / Single ticket

```yaml
---
title: "Human-readable title"
status: todo                        # todo | in_progress | blocked | done | deferred
components:                         # at least one id from docs/components.json
  - infrastructure
created: 2026-05-13                 # YYYY-MM-DD
depends_on:                         # sibling filenames in the same epic, [] if none
  - 01_first_sub.md
priority: medium                    # critical | high | medium | low  (optional)
files_touched:                      # relative paths of files this ticket edits (optional)
  - src/some_module.py              #   used by epic-supervisor for parallel-safety gating
agents:                             # set by business-analyst / refinement agents (optional)
  python-coder: needed              #   status ∈ {not_needed | needed | signed_off | failed}
  pr-reviewer: needed
---
```

### Master_Plan.md (epic-level)

```yaml
---
title: "EPIC: My Epic Name"
type: epic
status: todo
components:
  - infrastructure
created: 2026-05-13
depends_on: []
priority: high
---
```

### Required vs optional fields

| Field | Required | Notes |
|-------|----------|-------|
| `title` | yes | Must match the H1 heading in the body |
| `status` | yes | One of: `todo`, `in_progress`, `blocked`, `done`, `deferred` |
| `components` | yes | List; IDs from `docs/components.json` (at least one) |
| `created` | yes | ISO date `YYYY-MM-DD` |
| `depends_on` | yes | List of sibling filenames; `[]` when none |
| `type` | optional | Only `epic` is valid; use only on `Master_Plan.md` |
| `priority` | optional | `critical` / `high` / `medium` / `low` |
| `files_touched` | optional | Populated by `business-analyst` / `refinement` agents |
| `agents` | optional | Populated by `business-analyst` / `refinement` agents |

---

## Lifecycle Transitions

```
[proposed]          tickets/00_inbox/
      ↓  (team commits to work)
[in-flight]         tickets/01_todo/
      ↓  (work complete + PR merged)
[archived]          tickets/99_done/
      ↓  (decided against)
[rejected]          tickets/99_rejected/
```

Within an active epic, completed sub-tickets move to `tickets/01_todo/EPIC-Name/done/`
while the epic is still in-flight. The epic folder itself moves to `99_done/` when
every sub-ticket is done and the epic PR is merged.

---

## Epic Structure

An epic is a multi-ticket body of work that shares a single git worktree and one PR.

```
tickets/00_inbox/epics/EPIC-PortableDevWorkflow/
  Master_Plan.md          — overall goal, key design decisions, sub-ticket table
  01_first_sub.md         — first sub-ticket (no dependencies)
  02_second_sub.md        — second sub-ticket (depends_on: [01_first_sub.md])
  03_third_sub.md         — third sub-ticket
```

The `Master_Plan.md` must include:

1. A `## Key Design Decisions` section (required by `epic-supervisor` pre-flight gate).
2. A sub-ticket table listing every `NN_*.md` file with description and status.

---

## Agent-Driven Workflow

Tickets are driven through phases by the supervisor agent stack:

```
/build-feature EPIC-Name
      ↓
epic-supervisor   reads all sub-tickets, builds dependency graph, batches
      ↓
ticket-supervisor drives one ticket through its declared phase agents
      ↓
phase agents      (architect-review, python-coder, test-runner, pr-reviewer, commit, pull-request)
      each calls the `signoff` skill as its final action
```

Phase agents populate the `agents:` map and `## Sign-offs` section. Do not edit
these sections manually — let the agent pipeline update them.

---

## Per-Agent Implementation Task Sections

Tickets written in the new format include an `## Implementation Tasks` body section divided into `### <agent-name>` sub-sections. Each sub-section belongs to one phase agent and holds a checklist of concrete deliverables for that agent to complete before signing off.

### Which agents get task sections

Task sections are controlled by the `requires_ticket_section: true` field in `leafcutter/config/agent_registry.json`. The current set of agents that receive task sections:

| Agent | Rationale |
|-------|-----------|
| `adr-author` | Authors a new ADR; tasks enumerate the decision sections to write. |
| `architecture-diagram-author` | Authors a C4 mermaid diagram; tasks list the diagram views required. |
| `python-coder` | Primary implementation agent; tasks are the concrete coding deliverables. |
| `sql-coder` | Database implementation agent; tasks enumerate SQL objects to create or modify. |
| `test-writer` | Writes the test suite; tasks list the test cases to implement. |
| `documentation-expert` | Updates documentation; tasks list the docs files to touch. |

Agents without `requires_ticket_section: true` (e.g. `architect-review`, `pr-reviewer`, `commit`, `test-runner`) do not get task sections. The field defaults to `false` when absent — backward compatibility is preserved for older tickets that predate this convention.

### Sub-heading structure

```markdown
## Implementation Tasks

### python-coder
- [ ] Implement X following the pattern in Y
- [ ] Add unit test stubs under `unit_tests/` (handed off to test-writer)

### test-writer
- [ ] Write test_X covering the happy path
- [ ] Write test_X_edge covering the edge case documented in the spec
```

The `- [ ]` / `- [x]` checkbox syntax is load-bearing: the pre-commit parity guard (`check-ticket-signoff-parity`) reads these checkboxes. An agent with `requires_ticket_section: true` that signs off with unchecked items in its own section triggers a hard pre-commit error.

### Handoff workflow

When a `python-coder` completes coding but defers test writing to `test-writer`, it:

1. Checks off its own tasks under `### python-coder`.
2. Populates tasks under `### test-writer` (these may remain unchecked — they are the next agent's tasks).
3. Signs off with `(status: handoff)` naming `test-writer` as the recipient.

The supervisor receives the `handoff` status tag and spawns `test-writer` next, skipping natural order if needed.

### Blocker path

If an agent cannot complete a task — because a dependency is not met, a prerequisite is missing, or the required information is unavailable — it MUST NOT soft-pass by checking the box anyway. Instead:

1. Leave the task unchecked with a comment explaining the block.
2. Emit `(status: blocker)` to the supervisor with a one-sentence explanation and a suggested remediation (e.g. which sibling agent to respawn or what user input is needed).
3. Update the `agents:` frontmatter entry to `failed` and the `## Sign-offs` row accordingly.

The supervisor's failure-adjudication ladder (`building-epics` §3) decides whether to respawn the agent, escalate to `brainstorm-lead`, or surface to the user. An agent never decides unilaterally to skip or fake completion.

---

## Authoritative Reference

- **Ticket authoring guide**: `.claude/skills/ticket-authoring/SKILL.md`
- **Sign-off protocol**: `.claude/skills/signoff/SKILL.md`
- **Epic supervisor runbook**: `.claude/skills/building-epics/SKILL.md`
- **Adoption guide**: `BOOTSTRAP.md` (written by this epic's ticket 10)
