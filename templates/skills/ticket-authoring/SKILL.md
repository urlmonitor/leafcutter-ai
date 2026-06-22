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
- The acceptance criteria need more than 6 numbered AC items

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
agents:                            # optional — set by the AC pipeline (business-analyst-v3 / it-po-v3);
  architect-review: needed         #   status ∈ {not_needed | needed | signed_off | failed}
  test-writer: needed              #   priority 5 — writes failing tests BEFORE coders;
  python-coder: needed             #   set test-writer: not_needed for docs-only / config-only tickets
  sql-coder: not_needed            #   (ticket-supervisor will also auto-skip when tests: [] or absent)
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
requires_documentation:            # optional — list of doc types from doc_types.json;
  - how_to                         #   ticket-wiring flips writer agents to needed
# artifact_checklist:              # optional — per-agent checklist overrides; map of
#   python-coder:                  #   agent-name → list of item names; merges with
#     - linting_clean              #   agent's default_artifact_checklist
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
| `files_touched` | optional | List of relative paths this ticket edits; used by `epic-supervisor` to detect file-touch overlap when scheduling parallel tickets. Populated by the AC pipeline (business-analyst-v3 / it-po-v3); omit until those agents run. |
| `agents` | optional | Map of `<agent-name>: <status>` where status ∈ `not_needed \| needed \| signed_off \| failed`. Populated by the AC pipeline (business-analyst-v3 / it-po-v3). The hook validates every value against the enum; invalid values block the write. Valid agent names come from `leafcutter/config/agent_registry.json` (entries with `is_ticket_phase: true`). See `.claude/skills/signoff/SKILL.md` for the full status lifecycle. **Canonical ordering**: architect-review (4) → test-writer (5) → python-coder (6) → sql-coder (7) → test-runner (9) → documentation-expert (10) → pr-reviewer (11) → commit (12) → pull-request (13). Set `test-writer: not_needed` when `## Test Requirements` → `tests: []` (docs-only / config-only tickets). The `ticket-supervisor` will also auto-skip based on the `tests:` array, but setting `not_needed` in the map avoids the unnecessary spawn check. |
| `requires_diagram` | **required** | Tri-state: `true` (diagram needed), `false` (considered, not needed), `null` (not applicable — pre-existing coverage). **Absent key is a hook failure** per ADR-026. |
| `requires_adr` | **required** | Tri-state: `true` (ADR needed), `false` (considered, not needed), `null` (not applicable — pre-existing coverage). **Absent key is a hook failure** per ADR-026. |
| `requires_documentation` | optional | List of doc type strings that must be produced for this ticket. Valid values come from `leafcutter/config/doc_types.json` (e.g. `[how_to, reference]`). When present, ticket-wiring flips the corresponding writer agents to `needed`. Omit when no doc deliverable is required. |
| `user_facing_surface` | optional | `slash_command \| pre_commit_hook \| agent_orchestrated \| cron \| null`. Identifies the production entrypoint this ticket introduces or modifies. Set by `business-analyst-v3`. When non-null: (a) `actuation_contract` is required; (b) `user-surface-smoker: needed` must appear in `agents`. Absent or `null` = ticket is internal; no smoker dispatch. |
| `actuation_contract` | optional (required when `user_facing_surface` != null) | One sentence describing the observable side effect when the surface is invoked in production with no parameter overrides. Example: `"Writes N entries to docs/glossary.md and exits 0 on success."`. Used by `user-surface-smoker` to build the `assertion:` regex for the Smoke Fixture. |
| `roadmap_phase` | optional | Phase ID from `docs/roadmap.json` that this ticket belongs to (e.g. `phase_1`). The hook prints a **warning** (not a block) when the value is not a known phase ID. Omit on tickets predating the roadmap or when the phase is unclear. |
| `advances_current_outcome` | optional | Boolean (`true` / `false`). Set `true` when this ticket directly advances the current must-achieve outcome in `docs/roadmap.json`. The hook prints a **warning** (not a block) when the value is not a boolean. Omit when not applicable. |
| `artifact_checklist` | optional | Per-agent checklist overrides. Map of agent-name → list of item names. Merges with agent's default_artifact_checklist; ticket items extend defaults, same key overrides. |
| `ac_coverage` | optional | Machine-readable AC completion ratio. Format: `N/M` where M = total AC count and N = number of validated ACs. Default `0/M` when first added. Updated by agents or the supervisor as ACs are confirmed green. Example: `ac_coverage: 3/6`. |

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
sibling tickets, related docs, ADRs. When the ticket touches a module
that mirrors an existing module's pattern, explicitly list all locations
where analogous or duplicate logic exists so duplication risks are
visible before implementation begins.

## Acceptance Criteria
- [ ] AC-1: <description of first acceptance criterion>
- [ ] AC-2: <description of second acceptance criterion>

<!-- For multi-agent tickets, use the Agent Contracts section instead:

## Agent Contracts

### <agent-name>
- [ ] AC-1: <deliverable this agent must produce>
- [ ] AC-2: <deliverable this agent must produce>

**Delivers to**: <next agent or "end user">
**Depends on**: <prior agent or "none">

-->

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |

## Comments

Append-only log. Each entry uses a parser-strict heading (three hashes):

```
### YYYY-MM-DD HH:MM — <agent-name> (status: ok|blocker|question|handoff)
```

Leave blank when authoring. Phase agents append here as their final action.

## Sign-offs
- [ ] architect-review
- [ ] test-writer
- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

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

### Deployment tickets: require reachability ACs, not only copy ACs

When a ticket's primary deliverable is a file that must be **callable at runtime** on a
consumer install (workflow `.js` script, deployed script, agent template, skill SKILL.md,
pre-commit hook), the acceptance criteria MUST include a **reachability** scenario in
addition to any copy/presence check. The two tiers are distinct:

- **Copy tier** — "file is present in the build output directory" (e.g. `templates/workflows-js/`).
- **Reachability tier** — "the canonical entry point resolves and executes through the
  deployed shim path without file-not-found or import-resolution error."

A copy AC passes even when the artifact is unreachable. Both of these shipped green on
copy ACs and were caught only by post-sign-off manual angle-testing:
- The build phase wrote to a path the shim does not map (workflow `.js` written to
  `.claude/workflows/` while the shim sources `output_root/workflows/` — BP-811).
- The agent template invoked the script at a bare `scripts/ac_store/...` path that
  resolves nowhere on a consumer install (EPIC-AcPipelineDeployGaps ticket 05).

Reachability ACs catch both failure modes; copy ACs catch neither. Template:

```gherkin
Scenario: consumer-facing reachability
  Given a simulated consumer install with <component> deployed
  When the canonical entry point is invoked at <deployed-shim-path>/<name>
  Then the invocation exits without file-not-found or import-resolution error
  And the output matches the expected command signature
```

Add this scenario to every deployment-artifact ticket.
(Source: EPIC-AcPipelineDeployGaps retrospective, 2026-06-17)

### Agent Contracts Block (required for multi-coder tickets)

When a ticket's `agents:` map has **more than one coder agent** (`python-coder`,
`sql-coder`, or `frontend-coder`) with status `needed`, the ticket body MUST include
an `## Agent Contracts` section instead of a plain `## Acceptance Criteria` section.
The `it-po-v3` phase agent authors this section; ticket authors SHOULD leave it blank and
let `it-po-v3` populate it.

#### Routing decision: multi-coder vs single-coder

| Ticket type | Routing | Who writes ACs |
|---|---|---|
| **Single-coder** (1 coder agent needed) | `it-po-v3: not_needed`, AC authoring by BA v3 | business-analyst-v3 agent |
| **Multi-coder** (>1 coder agent needed) | `it-po-v3: needed`, IT PO v3 writes per-agent contracts | it-po-v3 agent |

The `/plan-feature` pipeline determines the routing at AC authoring time based on the BA v3's output.
For multi-coder tickets, `it-po-v3` is added to the `agents:` map at priority 3.5 (after
architecture-diagram-author, before architect-review).

#### Agent Contracts section format

```markdown
## Agent Contracts

### <agent-name>

- [ ] AC-N: <single testable outcome — include specific data shapes, types, status codes>
- [ ] AC-N+1: <another testable outcome>
- [ ] AC-N+2: <integration AC> <!-- scope: integration -->

**Delivers to <downstream-agent>:**
\`\`\`json
{
  "endpoint": "POST /api/resource",
  "content-type": "application/json",
  "status_codes": [201, 400, 422, 500],
  "request": {
    "field_name": "string (required)",
    "optional_field": "integer | null"
  },
  "response_201": {
    "id": "uuid (non-null)",
    "created_at": "ISO 8601 string"
  },
  "response_422": {
    "error": "string",
    "field": "string | null"
  }
}
\`\`\`

**Depends on <upstream-agent>:** <what must exist — table name, endpoint path, shared type>
```

#### Contract precision requirements

1. **JSON shapes**: include field names, types, and nullability (`"id": "uuid (non-null)"`).
2. **Endpoint specs**: include method, path, content-type, and all expected status codes.
3. **DB column specs**: include type, nullability, default, and FK if applicable.
4. **Error shapes**: include the exact shape the consumer parses (`response.error.field`).
5. **Integration ACs**: at least one AC per agent boundary must be tagged `<!-- scope: integration -->`.
6. **Limits**: max 7 ACs per agent (enforced by `check_ac_limits` pre-commit hook); max 20 ACs per ticket.

When a ticket exceeds these limits, the `it-po-v3` §7 Split Protocol splits the ticket into
sibling tickets rather than exceeding the cap.

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
- [ ] AC-1: After alembic upgrade head, candle_context table has ctx_cme_gaps column of type JSONB NULL
- [ ] AC-2: alembic downgrade reverses the migration without data loss

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |

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

## AC Referencing Convention

Tickets do **not own** acceptance criteria. They **reference** them. ACs are first-class
entities stored in the AC store at `docs/acceptance-criteria/{component}/{id}.yaml`
(see `ticket-wiring` §Step 2.5 and `ac-store-schema`).

### Referencing format

Use the format `implements AC-FIN-003` in the `## Context` section or a dedicated
`## AC References` section:

```markdown
## AC References

- Implements AC-FIN-003 (settlement amount validation)
- Amends AC-FIN-001 (adds merge_conflict halt category)
```

When a ticket introduces a **new** AC, the BA proposes it via `ac_creations`; the
wiring phase writes the YAML file. State the new AC in the ticket:

```markdown
## Context
This ticket introduces AC-FIN-005 and amends AC-FIN-001.
```

When a ticket **amends** existing behaviour, state which AC is amended:

```markdown
amends AC-FIN-001 (adds merge_conflict halt category)
```

### Gherkin and AC YAML relationship

The `## Acceptance Criteria` section in the ticket body retains its **Gherkin scenarios
for human readability**. These mirror the AC YAML content but do not replace it.
The AC YAML at `docs/acceptance-criteria/{component}/{id}.yaml` is the canonical
source of truth:

- Code review and CI tooling read the YAML.
- The ticket body Gherkin is for developer/reviewer comprehension during the PR.
- When Gherkin in the ticket body diverges from the YAML, the YAML wins.

### Summary

| Surface | Purpose | Source of truth? |
|---|---|---|
| `## Acceptance Criteria` (Gherkin) | Human readability, PR review context | No |
| `docs/acceptance-criteria/{id}.yaml` | Machine-readable, canonical | **Yes** |

---

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

## Ticket Quality Checklist

Before a ticket is considered complete, the ticket author MUST verify all of the following:

- **files_touched completeness**: all affected files are listed; paths are correct relative to the project root; the list is not too broad.
- **agent assignment accuracy**: the `agents` map reflects what the ticket actually requires; selection criteria from `agent_registry.json` are applied.
- **AC coverage check**: for each `- [ ] AC-N:` item in the Acceptance Criteria block, confirm that at least one Implementation Task explicitly addresses it. If an AC has no corresponding task, either add a task or narrow the AC. A task list narrower than the AC list is a scope inconsistency — it will cause a Step 5 residual.

  Lesson: TICKET-20260513's acceptance criteria demanded `git status --porcelain returns empty` but no Implementation Task explicitly covered the supervisor's `status: done` flip. The gap was not caught during the authoring phase.

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
| `artifact_checklist` keyed by item name instead of agent name | Must be a map of agent-name → list |

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
