---
title: "Author the frontend-coder agent template"
status: todo
components:
  - build_pipeline
created: 2026-05-28
depends_on: []
priority: high
requires_diagram: false
requires_adr: true
files_touched:
  - leafcutter-ai/templates/agents/frontend-coder.md
agents:
  architect-review: signed_off
  python-coder: not_needed
  sql-coder: not_needed
  test-writer: not_needed
  test-runner: not_needed
  documentation-expert: signed_off
  adr-author: signed_off
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
---

# 01: Author the frontend-coder agent template

## Actor / Goal

In order to support frontend/UI implementation tasks in the ticket pipeline, we need a `frontend-coder` agent template so that ticket-supervisor can dispatch frontend work to a specialised agent the same way it dispatches to `python-coder` and `sql-coder`.

## Context

The leafcutter-ai package already has `python-coder.md` and `sql-coder.md` as implementation-phase agents. Both follow a consistent pattern:
- YAML frontmatter with `name`, `model`, `tools`, optional flags (`portable`, `domain`, `config_keys`, `spawn_allowlist`)
- Pre-flight reads section (PROJECT_CONTEXT.md, ADRs, conventions)
- Tool allowlist reminder (no Grep/Glob/MCP — delegate to research-agent)
- Research delegation protocol
- Implementation sequence
- Pre-completion checks (linting, style)
- Response payload format
- Sign-off section

`frontend-coder` should follow the same skeleton but adapted for frontend/UI work:
- Pre-flight: reads `PROJECT_CONTEXT.md` for the frontend sub-agent (if present), loads any frontend conventions, reads the ticket body
- Stop-and-ask rules for backend code (defer Python to python-coder, SQL to sql-coder)
- Optional skill integration: when `webapp-testing` skill is installed, run it to screenshot the result after implementation; when `frontend-design` skill is installed, apply design guidance before writing markup/CSS
- File-size limit awareness for JS/TS/CSS files
- Sign-off via the signoff skill

The ADR needed here captures the decision to model `frontend-coder` as a sibling implementation agent (rather than a sub-agent of python-coder) and to keep optional skill integration conditional on installed skills.

## Architecture Plan

### ADRs

- `frontend-coder as a first-class sibling implementation agent` — new ADR to be authored before coding begins, capturing the decision to treat frontend-coder as a peer to python-coder/sql-coder rather than a sub-agent, and the optional-skill integration contract.

## Acceptance Criteria

```gherkin
Given leafcutter-ai/templates/agents/frontend-coder.md is created
When build.py --target-dir . is run
Then .claude/agents/frontend-coder.md exists with valid YAML frontmatter and the canonical agent skeleton

Given frontend-coder.md exists
When it is read
Then it has a Pre-Flight Reads section referencing PROJECT_CONTEXT.md
And it has a Stop-and-Ask rule for Python and SQL files
And it has conditional optional-skill integration for webapp-testing and frontend-design
And it has a Response Payload / Completion Report section

Given an ADR is authored for this decision
When it is committed
Then docs/architecture/adrs/ADR-NNN-frontend-coder-agent.md exists and passes the doc frontmatter guard
```

## Sign-offs

- [x] architect-review — 2026-05-28 11:50
- [x] documentation-expert — 2026-05-28 12:00
- [x] adr-author — 2026-05-28 11:45
- [x] pr-reviewer — 2026-05-28 12:10
- [ ] commit
- [ ] pull-request

## Comments

### 2026-05-28 11:45 — adr-author (status: ok)
feedback-id: fb_2026-05-28_5eb81f32
Authored ADR-005-frontend-coder-agent.md at docs/architecture/adrs/. Covers: sibling vs sub-agent rationale (depth-3 cap, overloading concerns, dispatch log clarity), optional-skill file-existence detection contract, priority-8 slot rationale, and delegation boundaries. README index updated to include ADR-004 entries and ADR-005.

### 2026-05-28 11:50 — architect-review (status: ok)
feedback-id: fb_2026-05-28_18bf6147
Classified as SMALL: 1 file touched (leafcutter-ai/templates/agents/frontend-coder.md), 1 component (build_pipeline), no always-large triggers (no migration, no hypertable, no public API change). ADR-005 has been authored and covers the design rationale. Acceptance-criteria note: the template body must reference ADR-005 explicitly so readers can trace the sibling-agent decision. No escalation needed.

### 2026-05-28 12:00 — documentation-expert (status: ok)
feedback-id: fb_2026-05-28_4fc0369b
Created templates/agents/frontend-coder.md (234 lines) following the python-coder/sql-coder skeleton. All required sections present: YAML frontmatter (name, model, tools, portable, config_keys, spawn_allowlist), Pre-Flight Reads (ticket, PROJECT_CONTEXT.md via config injection, ADRs, optional-skill detection), Tool Allowlist Reminder, Research Delegation, Optional-Skill Integration (frontend-design → read before writing; webapp-testing → screenshot after edits; Antigravity skip note), Stop-and-Ask rules for Python and SQL, File-Size Limit, Implementation Sequence, Pre-Completion Checks, Response Payload, Constraints, Sub-Agents table, Sign-off section. ADR-005 is referenced explicitly in the preamble and in frontmatter description.

### 2026-05-28 12:10 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-28_c5e9dbee
Reviewed all three deliverables: ADR-005-frontend-coder-agent.md (frontmatter valid, all 3 spec items covered), README.md (correctly updated), templates/agents/frontend-coder.md (all required sections present, ADR-005 referenced, no .py or .sql file references, optional-skill integration and Antigravity skip note correct). All acceptance criteria verified. No regressions to existing agent templates. build.py glob pattern picks up frontend-coder.md automatically — no build script changes needed.

## Implementation Tasks

### adr-author

- [x] Author ADR-NNN — `frontend-coder as a first-class sibling implementation agent` at `docs/architecture/adrs/ADR-NNN-frontend-coder-agent.md`. Cover: rationale for sibling (vs sub-agent) design, optional-skill integration contract (conditional on installed skill), stop-and-ask delegation boundaries (Python → python-coder, SQL → sql-coder).

### documentation-expert

- [x] Create `leafcutter-ai/templates/agents/frontend-coder.md` following the python-coder/sql-coder skeleton. Sections required: YAML frontmatter (name: frontend-coder, model: sonnet, tools: Bash Read Edit Write Agent), Pre-Flight Reads (ticket body, PROJECT_CONTEXT.md, ADRs), Tool Allowlist Reminder (no Grep/Glob), Research Delegation, Stop-and-Ask Rule for Python/SQL, Optional-Skill Integration (webapp-testing → screenshot after implementation; frontend-design → apply design guidance before writing), File-Size Limit, Implementation Sequence, Pre-Completion Checks, Response Payload, Sign-off section, Constraints, Available Sub-Agents (research-agent).

## Risk & Safety

- Touches money? No.
- Touches data? No — this is a new markdown template file only.
- Reversibility? Fully reversible. A new template file has no side effects until build.py is run; it can be deleted without consequence.
- Shared contract? The agent template becomes part of the public leafcutter package surface once shipped. The design decisions captured in the ADR are binding for downstream integrations (e.g. the onboard wizard, agent_registry).
