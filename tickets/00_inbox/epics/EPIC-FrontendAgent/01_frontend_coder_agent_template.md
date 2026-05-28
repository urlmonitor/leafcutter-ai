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
  architect-review: needed
  python-coder: not_needed
  sql-coder: not_needed
  test-writer: not_needed
  test-runner: not_needed
  documentation-expert: needed
  adr-author: needed
  pr-reviewer: needed
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

- [ ] architect-review
- [ ] documentation-expert
- [ ] adr-author
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### adr-author

- [ ] Author ADR-NNN — `frontend-coder as a first-class sibling implementation agent` at `docs/architecture/adrs/ADR-NNN-frontend-coder-agent.md`. Cover: rationale for sibling (vs sub-agent) design, optional-skill integration contract (conditional on installed skill), stop-and-ask delegation boundaries (Python → python-coder, SQL → sql-coder).

### documentation-expert

- [ ] Create `leafcutter-ai/templates/agents/frontend-coder.md` following the python-coder/sql-coder skeleton. Sections required: YAML frontmatter (name: frontend-coder, model: sonnet, tools: Bash Read Edit Write Agent), Pre-Flight Reads (ticket body, PROJECT_CONTEXT.md, ADRs), Tool Allowlist Reminder (no Grep/Glob), Research Delegation, Stop-and-Ask Rule for Python/SQL, Optional-Skill Integration (webapp-testing → screenshot after implementation; frontend-design → apply design guidance before writing), File-Size Limit, Implementation Sequence, Pre-Completion Checks, Response Payload, Sign-off section, Constraints, Available Sub-Agents (research-agent).

## Risk & Safety

- Touches money? No.
- Touches data? No — this is a new markdown template file only.
- Reversibility? Fully reversible. A new template file has no side effects until build.py is run; it can be deleted without consequence.
- Shared contract? The agent template becomes part of the public leafcutter package surface once shipped. The design decisions captured in the ADR are binding for downstream integrations (e.g. the onboard wizard, agent_registry).
