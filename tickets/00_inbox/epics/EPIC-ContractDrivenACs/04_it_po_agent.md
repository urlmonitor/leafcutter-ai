---
title: "Create IT PO agent — translates business ACs into per-agent technical contracts"
status: todo
components:
  - build_pipeline
created: 2026-06-03
depends_on:
  - 01_adr_contract_driven_acs.md
  - 02_ac_format_and_frontmatter.md
priority: high
phase: "Phase 2"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
user_facing_surface: null
files_touched:
  - templates/agents/it-po.md
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
  architecture-diagram-author: not_needed
  user-surface-smoker: not_needed
---

# 04: Create IT PO Agent

## Business Intent

We need an agent that sits between business-analyst and implementation agents,
translating "what the user wants" into "exactly what each agent must build" —
with explicit interface contracts between agents so they produce compatible code
without guessing.

## Context

The IT PO (Information Technology Product Owner) is a new Opus-tier agent that:

1. Receives business ACs from the business-analyst
2. Reads architecture-level documentation (NOT raw code) to understand the system
3. Asks the user questions when requirements are ambiguous
4. Produces per-agent technical ACs with explicit "Delivers to" / "Depends on"
   contract blocks specifying exact data shapes, endpoint signatures, and response types

### Knowledge Sources (What the IT PO reads)

The IT PO operates at the **technical architecture level** — distinct from the BA
which reads user-facing docs:

| Agent | Reads | Understands |
|-------|-------|-------------|
| BA (Opus) | User flows, how-tos, component pages, glossary | What the app *does* — user's perspective |
| IT PO (Opus) | Architecture diagrams, JSON schemas, conventions | How the system *connects* — interfaces between components |

**IT PO pulls from `docs/INDEX.md` (on-demand, not injected):**
- Architecture diagrams (C4 containers, components, data flow, sequence diagrams)
- `db_schema.json` (table structure, column types, FKs, constraints)
- `api_conventions.json` (error shapes, auth patterns, pagination, naming)
- `routes_manifest.json` (endpoint inventory — path, method, handler file)
- `PROJECT_CONTEXT.md` (project-wide technical conventions)
- Sibling tickets in the same epic (cross-ticket contract continuity)

**IT PO does NOT read:**
- Individual source files (`.py`, `.ts`, `.tsx`, `.sql`, `.vue`) — coders own these
- User-facing docs (how-tos, glossary) — BA already covered this
- Test files — test-writer/test-planner own these

### Why Opus

This is the hardest reasoning step in the pipeline. The IT PO must:
- Decompose a business requirement into agent-scoped deliverables
- Design API contracts (request/response shapes, error formats, status codes)
- Anticipate integration failure modes and specify them away
- Catch second-order questions ("if the frontend shows an error toast, which
  exact field does it read from the 422 response?")

Sonnet produces plausible-looking contracts that miss edge cases — the exact
source of integration failures this epic solves.

### When IT PO Runs vs When Refinement Runs

- **Multi-agent ticket** (>1 coder in the agents map): IT PO runs, refinement skipped
- **Single-agent ticket** (1 coder): refinement runs as today, IT PO skipped
- Determined by `create-ticket` based on business-analyst's routing output

## Agent Contracts

### python-coder

- [ ] AC-1: Agent template file exists at `templates/agents/it-po.md` with valid frontmatter (name, model: opus, tools: Bash/Read, portable: true)
- [ ] AC-2: Agent prompt includes a "Question Protocol" section requiring the IT PO to ask the user at least one clarifying question before producing contracts (blocks on zero questions)
- [ ] AC-3: Agent prompt includes a "Knowledge Acquisition" section listing which architecture-level docs to read (diagrams, component docs, PROJECT_CONTEXT.md) and explicitly prohibiting raw source file reads
- [ ] AC-4: Agent prompt includes a "Contract Output Format" section specifying the per-agent AC structure with `Delivers to` / `Depends on` blocks and exact data shape notation
- [ ] AC-5: Agent prompt includes "Scope Classification" logic — reads the agents map and only produces contracts when >1 coder agent is `needed`; for single-coder tickets, falls through to refinement
- [ ] AC-6: Agent prompt includes integration test AC generation — for each boundary crossing between agents, produces at least one AC scoped as `<!-- scope: integration -->` that exercises the contract end-to-end
- [ ] AC-7: Agent prompt includes a "Split Protocol" (§7) that activates when re-invoked after `check_ac_limits` hook failure — splits the oversized ticket into sibling tickets, updates depends_on, updates Master_Plan.md

**Delivers to ticket-supervisor (via ticket file):**
```
## Agent Contracts section in ticket body with:
- Per-agent AC blocks (numbered, checklist format)
- "Delivers to" blocks with exact data shapes (JSON examples, types)
- "Depends on" blocks referencing upstream agent deliverables
- Integration-scoped ACs for cross-agent boundaries
- ac_coverage: 0/N in frontmatter (N = total AC count)
```

**Note:** ticket-authoring skill updates (documenting the Agent Contracts format)
are covered by ticket 02_ac_format_and_frontmatter.md — not duplicated here.

## Sign-offs

- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |
| AC-6 | | | |
| AC-7 | | | |

## Implementation Tasks

### python-coder — create IT PO agent template

- [ ] Create `templates/agents/it-po.md` with the following structure:

  **Frontmatter:**
  ```yaml
  name: it-po
  model: opus
  tools: Bash, Read
  portable: true
  signoff: true
  ```

  **Agent Body Sections:**

  1. **Role** — Technical product owner. Translates business requirements into
     per-agent implementation contracts. Never writes code. Never reads source
     files directly.

  2. **§1 Question Protocol** — MUST ask the user at least one question before
     producing contracts. Questions should target:
     - Ambiguous business terms ("what does 'recent' mean — 7 days? 30?")
     - Unstated constraints ("is there a file size limit? auth required?")
     - Behavioral edge cases ("what happens if the upload fails midway?")
     - Priority/scope ("is delete in scope for v1 or a follow-up?")

     **Rule:** If the BA output contains zero open questions AND the IT PO
     cannot identify any ambiguity, it may proceed. But this should be rare.

  3. **§2 Knowledge Acquisition** — Pull-based, using `docs/INDEX.md` as directory:
     1. Read `docs/INDEX.md` to locate relevant architecture docs
     2. Pull only what's needed for the touched components:
        - Architecture diagrams (C4 containers, components, data flow, sequence)
        - `db_schema.json` (table structure, column types, FKs, constraints)
        - `api_conventions.json` (error shapes, auth patterns, pagination, naming)
        - `routes_manifest.json` (endpoint inventory — path, method, handler file)
        - `PROJECT_CONTEXT.md` (project-wide technical conventions)
        - Sibling tickets in the same epic (for cross-ticket contract continuity)

     **Prohibited:** Do NOT read source files (`.py`, `.ts`, `.tsx`, `.sql`, `.vue`).
     Do NOT read user-facing docs (how-tos, glossary) — the BA already covered those.
     Coders own code. BA owns user context. You own the interfaces between components.

  4. **§3 Contract Output Format** — For each coder agent in the `agents:` map,
     produce an "Agent Contracts" block:

     ```markdown
     ### <agent-name>

     - [ ] AC-N: <single testable outcome with specific data shapes>
     - [ ] AC-N+1: ...

     **Delivers to <downstream-agent>:**
     ​```
     <exact interface spec — endpoint + method + request shape + response shape>
     ​```

     **Depends on <upstream-agent>:** <what must exist before this agent runs>
     ```

  5. **§4 Contract Precision Rules:**
     - JSON response shapes must include field names, types, and nullability
     - Endpoint specs must include method, path, content-type, status codes
     - DB columns must include type, nullability, default, and FK if any
     - Error responses must include the exact shape the consumer will parse
     - When in doubt, be MORE specific — coders can always simplify
     - **Max 7 ACs per agent** (enforced by pre-commit hook). If you need
       more, split the ticket. This is a hard limit, not a guideline.
     - **Max 20 ACs per ticket total.** If you exceed this, you're writing
       an epic — stop and recommend splitting to the user.

  6. **§5 Scope Classification** — Read the `agents:` frontmatter map:
     - Count coder agents with status `needed` (python-coder, sql-coder, frontend-coder)
     - If count <= 1: sign off immediately with `(status: not_needed)` — single-agent
       tickets use refinement, not IT PO
     - If count > 1: proceed with contract design

  7. **§6 Integration ACs** — For each boundary crossing (agent A delivers to agent B),
     produce at least one AC tagged `<!-- scope: integration -->` that exercises the
     contract end-to-end. These become the ac-validator's primary focus.

  8. **§7 Split Protocol** — Triggered when `check_ac_limits` hook blocks the commit
     (routed back via precommit-autofix). The IT PO must:
     1. Read the hook's violation output (which agent, how many ACs)
     2. Identify a natural split boundary in the oversized agent's ACs
        (by sub-feature, by endpoint, by data flow step)
     3. Create a new sibling ticket file with the split-off ACs
     4. Update `depends_on` if the split creates a dependency (ticket B
        needs ticket A's endpoint to exist first)
     5. Update `Delivers to` / `Depends on` contracts to reference the
        new ticket's deliverables
     6. Update `Master_Plan.md` sub-ticket table if inside an epic
     7. If splitting would create worse coupling than keeping together
        (rare — e.g., 8 ACs that all touch the same function), set
        `ac_limit_override: true` with a comment explaining why

     **Split heuristics:**
     - Split by endpoint (POST /avatar + DELETE /avatar → two tickets)
     - Split by data flow (write path + read path → two tickets)
     - Split by error handling (happy path ticket + error handling ticket)
     - Never split a single endpoint's request/response across tickets

### python-coder — update ticket-authoring skill

- [ ] Add "Agent Contracts" section documentation to `templates/skills/ticket-authoring/SKILL.md`
- [ ] Document the multi-agent vs single-agent routing decision
- [ ] Add contract format spec to the body structure template

## Risk & Safety

- Touches money? No.
- Touches data? No — creates a new agent template and updates a skill doc.
- Reversibility? Fully reversible — new file + additive edit to existing skill.

## Open Questions

1. Should the IT PO have access to `research-agent` as a tool for bounded codebase
   questions (capped at 3 round-trips), or should it strictly only read docs?
   → Recommendation: start without it; add if we see knowledge gaps in practice.

2. How does the IT PO handle tickets where no architecture docs exist yet for the
   touched components?
   → Recommendation: IT PO flags this as a blocker and suggests creating the arch
   doc first (which becomes a preceding ticket).
