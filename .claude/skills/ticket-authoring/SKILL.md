---
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(ls *), Bash(mkdir *)
description: Use when creating, splitting, or moving anything under tickets/ (epics,
  sub-tickets, single tickets) — required before any Write to tickets/**/*.md, since
  the ticket_frontmatter_guard hook will block invalid frontmatter.
name: ticket-authoring
---

# Ticket Authoring

Authoring guide for everything under `tickets/`. The `ticket_frontmatter_guard` PostToolUse hook **will block your write** if the frontmatter is missing or wrong, so build it correctly the first time.

## When to Use

- The user asks for a new ticket, sub-ticket, or epic
- You are about to write anything under `tickets/` (except `README.md`)
- You need to split a large request into actionable work
- You are moving an existing ticket between status folders (`00_inbox` → `01_todo` → `99_done`)

## Granularity Rule (Read This First)

**One ticket = one independently-deliverable change.** Be aggressive about splitting — when in doubt, split.

**A ticket is too big when any of these are true:**
- It would produce a PR you cannot describe in one sentence
- It mixes schema + logic + docs in a single file
- It has more than ~5 implementation tasks at the leaf level
- It touches more than one component without a clear seam
- It cannot be reviewed end-to-end in under 30 minutes
- The acceptance criteria need more than 3 Gherkin scenarios

**Axes to split along:**
- **By layer** — schema → SQL procedure → Python service → live trader integration → tests/docs
- **By verb** — introduce X, populate X, validate X, hook X into Y (each gets its own ticket)
- **By data slice** — backfill historical first, then live; one symbol/timeframe at a time when possible
- **By "ships alone, still useful?"** — if yes, you've found a split point

## Decision: Single Ticket vs Epic

| Situation | Use |
|-----------|-----|
| 1–3 hours of work, one component, one PR | **Single ticket** in `tickets/00_inbox/TICKET-YYYYMMDD-Name.md` |
| 4+ tickets, multi-day, has a `Master_Plan` | **Epic** folder `tickets/00_inbox/epics/EPIC-Name/` with sub-tickets and a `Master_Plan.md` |
| Spans schema + logic + dashboards | Almost always an **epic** — split per layer |
| User says "let's plan this out" | **Epic** |

## Folder Routing

```
tickets/
  00_inbox/                        proposed work, not yet committed-to
    TICKET-YYYYMMDD-Name.md        single tickets
    epics/EPIC-Name/               proposed epics
      Master_Plan.md
      01_first_ticket.md
      ...
  01_todo/                         actively in flight
    EPIC-Name/                     epic-in-progress (matches a worktree)
      Master_Plan.md
      01_*.md, 02_*.md, ...
      done/                        completed sub-tickets within the live epic
        00_*.md
  99_done/                         finished epics/tickets, archived
  99_rejected/                     decided against
```

Move tickets between folders by renaming/relocating the file — never duplicate.

## Naming Convention

- **Single ticket**: `TICKET-YYYYMMDD-Name.md` — date = creation date, `Name` is `snake_case` or `PascalCase` (the project mixes both; match the surrounding folder rather than enforcing one)
- **Epic folder**: `EPIC-Name` or `EPIC-YYYYMMDD-Name` (same naming flexibility as above)
- **Sub-ticket**: `NN_snake_case_name.md` where `NN` is a zero-padded execution-order number (`01_`, `02_`, …, `02a_` for splits)
- **Master plan**: `Master_Plan.md` (some epics use `MASTER_PLAN.md` — match siblings)

The `NN` prefix encodes intended execution order. Use `02a`, `02b` when a single step splits into parallel sub-tasks. Numbers can be sparse (`05`, `07`, `12`) if you reserve gaps for future work.

## Frontmatter Schema (Enforced by the Hook)

Every ticket file (except `README.md`) needs YAML frontmatter at the top.

### Sub-ticket / Single ticket

```yaml
---
title: "Human-readable Title"
status: todo                       # todo | in_progress | blocked | done | deferred
components:                        # at least one; ids from docs/components.json
  - candle_context
  - live_trader
created: 2026-05-06                # YYYY-MM-DD
depends_on:                        # sibling filenames in the same epic, [] if none
  - 01_schema_migration.md
priority: medium                   # critical | high | medium | low (optional)
phase: "Phase 2"                   # optional, free-form epic phase label
tags:                              # optional, free-form
  - schema
  - backfill
last_updated: 2026-05-06           # optional, bump when you edit substantively
files_touched:                     # optional — relative paths of files this ticket edits;
  - live_trader/main.py            #   used by epic-supervisor for parallelism gating
  - models/candle_context.py
agents:                            # optional — set by business-analyst / refinement;
  python-coder: needed             #   status ∈ {not_needed | needed | signed_off | failed}
  pr-reviewer: needed
requires_documentation:            # optional — list of doc types from doc_types.json;
  - how_to                         #   ticket-wiring flips writer agents to needed
---
```

### Master_Plan.md (epic-level)

```yaml
---
title: "EPIC: Candle Context Unified Enrichment"
type: epic                         # only allowed type value; signals this is a master plan
status: in_progress                # epics typically open as in_progress
components:
  - candle_context
created: 2026-05-06
depends_on: []                     # epics are top-level
---
```

### Required vs Optional

| Field | Required | Notes |
|-------|----------|-------|
| `title` | yes | Match the H1 in the body |
| `status` | yes | `todo` / `in_progress` / `blocked` / `done` / `deferred` |
| `components` | yes | List, ids from `docs/components.json` (at least one) |
| `created` | yes | ISO date |
| `depends_on` | yes | List of sibling filenames, `[]` when none |
| `type` | optional | Only `epic` is valid (use on `Master_Plan.md`) |
| `priority` | optional | `critical` / `high` / `medium` / `low` |
| `phase`, `tags`, `last_updated` | optional | Free-form helpers |
| `files_touched` | optional | List of relative paths this ticket edits; used by `epic-supervisor` to detect file-touch overlap when scheduling parallel tickets. Populated by `business-analyst` / `refinement`; omit until those agents run. |
| `agents` | optional | Map of `<agent-name>: <status>` where status ∈ `not_needed \| needed \| signed_off \| failed`. Populated by `business-analyst` / `refinement`. The hook validates every value against the enum; invalid values block the write. Valid agent names come from `leafcutter/config/agent_registry.json` (entries with `is_ticket_phase: true`); fall back to the hardcoded table in `.claude/agents/business-analyst.md` §"Default agents map by ticket archetype" when the registry is absent. See `.claude/skills/signoff/SKILL.md` for the full status lifecycle. |
| `requires_diagram` | **required** | Tri-state: `true` (diagram needed), `false` (considered, not needed), `null` (not applicable — pre-existing coverage). **Absent key is a hook failure** per ADR-026. |
| `requires_adr` | **required** | Tri-state: `true` (ADR needed), `false` (considered, not needed), `null` (not applicable — pre-existing coverage). **Absent key is a hook failure** per ADR-026. |
| `requires_documentation` | optional | List of doc type strings that must be produced for this ticket. Valid values come from `leafcutter/config/doc_types.json` (e.g. `[how_to, reference]`). When present, ticket-wiring flips the corresponding writer agents to `needed`. Omit when no doc deliverable is required. |
| `user_facing_surface` | optional | `slash_command \| pre_commit_hook \| agent_orchestrated \| cron \| null`. Identifies the production entrypoint this ticket introduces or modifies. Set by `business-analyst`. When non-null: (a) `actuation_contract` is required; (b) `user-surface-smoker: needed` must appear in `agents`. Absent or `null` = ticket is internal; no smoker dispatch. |
| `actuation_contract` | optional (required when `user_facing_surface` != null) | One sentence describing the observable side effect when the surface is invoked in production with no parameter overrides. Example: `"Writes N entries to docs/glossary.md and exits 0 on success."`. Used by `user-surface-smoker` to build the `assertion:` regex for the Smoke Fixture. |
| `roadmap_phase` | optional | Phase ID from `docs/roadmap.json` that this ticket belongs to (e.g. `phase_1`). The hook prints a **warning** (not a block) when the value is not a known phase ID. Omit on tickets predating the roadmap or when the phase is unclear. |
| `advances_current_outcome` | optional | Boolean (`true` / `false`). Set `true` when this ticket directly advances the current must-achieve outcome in `docs/roadmap.json`. The hook prints a **warning** (not a block) when the value is not a boolean. Omit when not applicable. |

### `depends_on` Resolution

The hook resolves each entry against:
1. `<ticket_dir>/<entry>` — sibling in the same epic
2. `<ticket_dir>/done/<entry>` — sibling already moved to done/
3. If the ticket itself is in `done/`: `<ticket_dir>/../<entry>` — back up to the epic root

If the file does not exist at any of these, the hook blocks with `'depends_on' references missing file`. Add the dependency file first, then reference it.

### Status ↔ Folder Consistency

A ticket physically inside a `done/` folder must have `status: done`. The hook blocks any other combination.

## Body Structure

Inspect a sibling ticket in the target folder before writing — most epics have a house style. The skeleton below is the canonical baseline; deviate only to match siblings.

~~~markdown
# NN: Title (matches frontmatter `title`)

## Actor / Goal
In order to <outcome>, we need to <change> so that <user-facing benefit>.

## Context
Why now, what changed, and what existing piece this builds on. Link
sibling tickets, related docs, ADRs.

## Acceptance Criteria
```gherkin
Given <precondition>
When <action>
Then <observable outcome>
```
## Comments

Append-only log. Each entry uses a parser-strict heading (three hashes):

```
### YYYY-MM-DD HH:MM — <agent-name> (status: ok|blocker|question|handoff)
```

Leave blank when authoring. Phase agents append here as their final action.

## Implementation Tasks
- [ ] Concrete step 1
- [ ] Concrete step 2 (one PR-sized chunk)
- [ ] Tests
- [ ] Doc updates

## Risk & Safety
- Touches money? <yes/no — explain>
- Touches data? <yes/no — explain>
- Reversibility?
~~~

Sections to add when relevant: `Design Decisions`, `Out of Scope`, `Open Questions`, `Migration Plan`, `Rollback`. Skip anything that would be empty.

### Smoke Fixture Block (required when `user_facing_surface` != null)

When `user_facing_surface` is non-null in the frontmatter, the ticket body MUST include
a `## Smoke Fixture` block. This block is consumed by the `user-surface-smoker` phase agent
(priority 11.5, runs after `pr-reviewer` and before `commit`).

The block contains one YAML stanza per surface being verified:

~~~markdown
## Smoke Fixture

```yaml
surface: <slash_command_or_hook_name>
fixture_input: |
  <arguments, stdin, or synthetic ticket body to pass to the surface>
assertion: "<regex that the observable output MUST match>"
placeholder_signature: "<regex that the output MUST NOT match — optional but recommended>"
```
~~~

**Field semantics:**
- `surface` — the entrypoint name (e.g. `glossary-bootstrap`, `check_placeholder_defaults`).
- `fixture_input` — what to pass as input (arguments, stdin, synthetic config, etc.).
- `assertion` — a regex applied to the observable output (stdout + stderr + `git status`
  side effects). The surface MUST produce output matching this regex.
- `placeholder_signature` — a regex the output MUST NOT match. If matched, it means the
  surface is still wired to a placeholder and the smoker emits `(status: blocker)`.

**Self-application requirement**: a ticket introducing a new user-facing surface (e.g.
the `user-surface-smoker` agent itself) MUST include a Smoke Fixture block that the smoker
would pass once shipped. This prevents the "the new agent is exempt from its own gate"
exception.

### Optional: Out-of-Repo Outputs Block

If any file produced by this ticket must be written **outside** the git worktree (e.g. `~/.claude/projects/<hash>/memory/`, `~/.claude/hooks/`, `~/.claude/agents/`), add this block **after `## Risk & Safety`** and before any `## Comments` section:

~~~markdown
## Out-of-Repo Outputs (if any)
<!-- Delete this section if all outputs are within the git repo. -->
<!-- If any file must be written outside the worktree, describe it here. -->
<!-- Sub-agent harness CANNOT write outside the worktree root. -->
<!-- Parent context or a human must create these files manually. -->

| File path | Who creates it | Content description |
|-----------|----------------|---------------------|
| <example: ~/.claude/projects/<hash>/memory/feedback_xyz.md> | parent context | <one-line description> |
~~~

**Warning**: Sub-agents (documentation-expert, python-coder, sql-coder, etc.) running under the harness cannot write files outside the worktree root. The Write tool and Bash-write variants are both denied for out-of-worktree paths. See `building-epics` §8 for the full constraint description, failure signature, and design guidance.

This block introduces **no new frontmatter field** and does not affect the `ticket_frontmatter_guard`. Tickets that omit this section are valid. Delete the entire block when all outputs live inside the repo.

For `Master_Plan.md`, replace `Implementation Tasks` with a sub-ticket table:

```
| # | File | Description | Status |
|---|------|-------------|--------|
| 01 | [01_schema.md](./01_schema.md) | Add column X | `[ ]` |
| 02 | [02_populate.md](./02_populate.md) | Backfill X | `[ ]` |
```

## Complete Example (Sub-Ticket)

A minimal valid ticket that the hook will accept and that fits inside one PR:

~~~markdown
---
title: "Add ctx_cme_gaps column to candle_context"
status: todo
components:
  - candle_context
created: 2026-05-06
depends_on: []
priority: medium
---

# 01: Add ctx_cme_gaps column to candle_context

## Goal
In order to attach CME gap context to 1-minute candles, we need a JSONB
column on `candle_context` so downstream populators can write to it.

## Context
First ticket of EPIC-CMEGapContext. Schema only — populator logic lives
in 03_populate_ctx_cme_gaps.md. See [docs/logic/candle_context.md].

## Acceptance Criteria
```gherkin
Given the alembic head is upgraded
When I describe candle_context
Then ctx_cme_gaps exists as JSONB NULL
```
## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks
- [ ] Add Alembic migration adding `ctx_cme_gaps JSONB`
- [ ] Update `models/candle_context.py`
- [ ] `alembic upgrade head` on local DB

## Risk & Safety
- Touches money? No.
- Touches data? Adds nullable column; reversible via downgrade.
~~~

## Architecture Plan diagram_type Validation (mandatory before Write)

When a ticket being authored includes an `## Architecture Plan` section with one or more
`diagram_type:` values, the authoring agent MUST validate each value against
`leafcutter/config/diagram_types.json` **before writing the ticket file**.

**Why:** The pre-commit hook (`check_doc_frontmatter.py`) validates architecture doc
frontmatter against the same JSON source. Catching a bad `diagram_type` at authoring
time prevents the doc-author → rejection → re-author round-trip.

**Validation procedure:**

1. Extract all `diagram_type:` values from `## Architecture Plan` bullets in the draft.
2. Read `leafcutter/config/diagram_types.json` and extract the set of valid keys.
3. For each extracted value:
   - If NOT in the JSON key set: **ABORT** with:
     ```
     diagram_type '<value>' is not in the canonical enum (diagram_types.json).
     Valid values: <comma-separated list from JSON>.
     Fix the Architecture Plan before writing the ticket.
     ```
     Do NOT write the ticket file.
   - If in the set: continue.
4. After all values pass: proceed to Write.

**Valid values** (read from `diagram_types.json` at runtime — this list is illustrative):
`context`, `container`, `component`, `sequence`, `erd`, `state`, `dataflow`,
`data_flow`, `user_flow`, `agent_flow`, `none`.

**Note:** `dataflow` is a deprecated alias for `data_flow`. Both are accepted. Use
`data_flow` in new tickets.

## Workflow

1. **Confirm scope with the user** before writing — clarify whether this is one ticket or an epic, and the granularity. Brainstorm splits aloud.
2. **Pick the path** using the Folder Routing tree above.
3. **Read 1–2 sibling tickets** in the target folder to match house style (section names, depth, granularity).
4. **Author the file**: frontmatter first, then body. Use today's date (the value in `currentDate` from your context, not training-data dates).
5. **Resolve `components`** against `docs/components.json` — invalid component IDs do not currently block but will once the doc-frontmatter validator extends to tickets. Do it right anyway.
6. **Verify dependencies exist** before listing them in `depends_on` — the hook checks file existence.
7. **Validate Architecture Plan `diagram_type` values** against `diagram_types.json` (see §Architecture Plan diagram_type Validation above) before Write.
8. **Cross-link**: if this ticket is part of an epic, also update the `Master_Plan.md` sub-ticket table.
9. **For epics**: write the `Master_Plan.md` first with `type: epic`, then create sub-tickets one by one.

## Refinement Checklist

Before a `refinement` agent returns its payload, it MUST verify all of the following:

- **files_touched completeness**: all affected files are listed; paths are correct relative to the project root; the list is not too broad.
- **agent assignment accuracy**: the `agents` map reflects what the ticket actually requires; selection criteria from `agent_registry.json` are applied.
- **Gherkin coverage check**: for each `Then` clause in the Acceptance Criteria Gherkin block, confirm that at least one Implementation Task explicitly addresses it. If a `Then` clause has no corresponding task, either add a task or narrow the Gherkin. A task list narrower than the Gherkin is a scope inconsistency — it will cause a Step 5 residual.

  Lesson: TICKET-20260513's Gherkin demanded `git status --porcelain returns empty` but no Implementation Task explicitly covered the supervisor's `status: done` flip. The gap was not caught during refinement.

- **dependency detection**: does this ticket depend on another ticket or epic being completed first? List any `depends_on` entries if applicable.
- **risk identification**: any irreversible changes (schema migrations, data deletes, prod deploys)? Any shared contracts being modified?

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| One mega-ticket touching schema + logic + UI | Split per layer, one ticket each |
| `depends_on` referencing a file that doesn't exist | Create the dependency first, or use `[]` |
| `status: in-progress` (hyphen) | Use `in_progress` (underscore) |
| File in `done/` with `status: todo` | Hook blocks; flip status to `done` when moving |
| Frontmatter missing entirely | Hook blocks the Write/Edit; paste the template at the top |
| `components: documentation_system` (string) | Must be a list: `components:\n  - documentation_system` |
| Picking a date from your training-data sense of "now" | Always use today's date from context |
| Master plan without `type: epic` | Add `type: epic` so tooling can distinguish epics from sub-tickets |

## Quick Reference

```bash
# Find similar tickets to mimic style
ls tickets/01_todo/EPIC-*/01_*.md | head -3

# Look up valid component IDs (components is a dict keyed by id)
python -c "import json; print('\n'.join(sorted(json.load(open('docs/components.json',encoding='utf-8'))['components'])))"
```

Manual validation isn't wired up yet on `main` — `check_doc_frontmatter.py` skips ticket paths. The PostToolUse hook fires automatically on every Write/Edit, so trust the loop and fix what it reports.

## Related

- Schema source of truth (when EPIC-DocTraceability merges): `scripts/commit_guardian/frontmatter_validators.py::validate_ticket_file`
- Config: `scripts/commit_guardian/commit_guardian.json` → `ticket_frontmatter` section
- Hook: `.claude/hooks/ticket_frontmatter_guard.py` (PostToolUse on Edit|Write)
- Spec ticket: `tickets/01_todo/EPIC-DocTraceability/15_ticket_frontmatter.md`
