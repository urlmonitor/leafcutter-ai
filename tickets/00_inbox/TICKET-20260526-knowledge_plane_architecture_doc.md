---
title: "Architecture Doc: Agent Knowledge Plane"
status: todo
components:
  - build_pipeline
  - config_loader
created: 2026-05-26
depends_on: []
priority: high
requires_diagram: true
requires_adr: false
requires_documentation:
  - architecture
files_touched:
  - leafcutter-ai/docs/architecture/agent_knowledge_plane.md
  - leafcutter-ai/CLAUDE.md
agents:
  architect-review: needed
  architecture-diagram-author: needed
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  python-coder: not_needed
  sql-coder: not_needed
  test-writer: not_needed
  test-runner: not_needed
  adr-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  status-checker: not_needed
  change-scope-reviewer: not_needed
  user-surface-smoker: not_needed
roadmap_phase: phase_1
advances_current_outcome: true
---

# Architecture Doc: Agent Knowledge Plane

## Actor / Goal

In order to give downstream agents (and any future knowledge-routing skill) a
single canonical reference for context distribution, we need to author an
architecture document that maps every channel through which a leafcutter agent
receives knowledge at invocation time, so that agents can cite it instead of
inlining the layout into individual SKILL.md files.

## Context

Today there is no single document that answers "where does an agent's context
window come from?" Agents currently have to infer this from scattered sources:
the `CLAUDE.md` conventions, skill-loading hints in individual `SKILL.md` files,
frontmatter schema docs, and the `agent_delivery_workflows.md` diagram. The
`agent_knowledge_system.md` doc covers post-execution knowledge _capture_ but
not pre-execution knowledge _injection_.

The knowledge-routing skill (sibling ticket, depends on this doc) cites the
knowledge plane as its normative reference. Without this document the routing
skill would have to inline the channel layout into its own `SKILL.md`, causing
the two sources to drift as new channels are added.

The user-framing driving this ticket:

> "we also need to have architecture docs to describe how we distribute
> knowledge … showing that an agent gets claude.md, that it gets readme of
> folder injected, that it gets project context, that it gets skills, that it
> knows what to do based on json/frontmatter, etc etc."

This ticket is **documentation-only** — no code or configuration changes. The
sibling "knowledge-routing skill" ticket covers the Skill deliverable that will
cite this doc.

### Existing docs to read before authoring

- `leafcutter-ai/docs/architecture/agent_delivery_workflows.md` — L3 agent
  orchestration flows; the new doc is a sibling at L2 covering knowledge
  injection rather than execution topology.
- `leafcutter-ai/docs/architecture/agent_knowledge_system.md` — covers
  knowledge _capture_ after execution; the new doc covers knowledge _injection_
  before execution. Cross-link both ways.
- `leafcutter-ai/config/skills_config.default.json` and
  `leafcutter-ai/config/paths.json` — config sources consumed by the harness.

## Architecture Plan

### Diagrams

- `data_flow` diagram at `leafcutter-ai/docs/architecture/agent_knowledge_plane.md` (parent: `leafcutter-ai/docs/architecture/agent_delivery_workflows.md`)

### Documentation

- `architecture` doc at `leafcutter-ai/docs/architecture/agent_knowledge_plane.md` — C4-flavoured architecture document enumerating every knowledge-injection channel with writer / loader / format / target-agents table

## Acceptance Criteria

```gherkin
Given the leafcutter repo is checked out
When I navigate to leafcutter-ai/docs/architecture/agent_knowledge_plane.md
Then the file exists and has valid frontmatter with diagram_type set to a canonical enum value

Given the knowledge plane doc exists
When I read it
Then it contains at least one mermaid diagram showing knowledge sources flowing into an agent context window
And each knowledge source listed in the ticket scope is present in the doc
And the doc includes a table with columns: Source | Written by | Loaded when | Format | Target agents

Given the knowledge plane doc exists
When I check leafcutter-ai/CLAUDE.md
Then it contains a cross-link to the new doc under an "Architecture" or "Reference Docs" TOC heading

Given the knowledge plane doc exists
When I look for the sibling doc agent_knowledge_system.md
Then both docs cross-reference each other (injection doc links to capture doc and vice versa)
```

## Knowledge Sources to Enumerate

The following sources MUST be covered in the doc. Each entry needs: WHO writes
it, WHEN it is loaded, WHAT format it has, and INTO WHICH agents it is injected.

| # | Source | Notes |
|---|--------|-------|
| 1 | Root `CLAUDE.md` | Project-wide instructions; injected by Claude Code harness into every agent |
| 2 | Per-folder `README.md` | Auto-injected by the harness when the agent's cwd overlaps the folder |
| 3 | Agent `PROJECT_CONTEXT.md` | Worker-specific domain context co-located with `SKILL.md` |
| 4 | Skill loading — auto-loaded | Skills declared in `skills_config.json` loaded automatically at spawn |
| 5 | Skill loading — on-demand | Skills invoked via the Skill tool; available-skills list in system reminder |
| 6 | Agent frontmatter | `model`, `tools`, `signoff`, `config_keys`, `portable`, `adopter_notes`, etc. |
| 7 | `skills_config.json` and `settings.json` | Harness behaviour configuration |
| 8 | Ticket frontmatter | `agents` map, `files_touched`, `depends_on` |
| 9 | Auto-memory | `memory/*.md` files loaded into the harness context |
| 10 | MCP server prompts and tool descriptions | Injected by Claude Code from registered MCP servers |
| 11 | Glossary injection | `docs/glossary.md` content or summary injected via CLAUDE.md or system reminder |

## Sign-offs

- [ ] architect-review
- [ ] architecture-diagram-author
- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

- [ ] Read `agent_delivery_workflows.md` and `agent_knowledge_system.md` for
      house style and cross-link targets
- [ ] Author `leafcutter-ai/docs/architecture/agent_knowledge_plane.md` with:
  - Valid frontmatter (`diagram_type: data_flow`, `flight_level: L2-Container`
    or `L3-Component` at the architecture-diagram-author's discretion)
  - Intro paragraph explaining the knowledge plane concept
  - At least one mermaid `flowchart` or `C4Context`/`C4Container` diagram
    mapping sources → agent context window
  - Knowledge-source enumeration table (Source / Written by / Loaded when /
    Format / Target agents)
  - Cross-link to `agent_knowledge_system.md` (capture side) and
    `agent_delivery_workflows.md` (execution side)
- [ ] Update `leafcutter-ai/CLAUDE.md` to add a cross-link to the new doc
      (under an "Architecture Reference" or existing TOC heading)
- [ ] Verify the new doc's `diagram_type` value is in `leafcutter-ai/config/diagram_types.json`
      before writing (pre-commit hook validates this)

## Risk & Safety

- Touches money? No
- Touches data? No — documentation only
- Reversibility? Fully reversible; deleting the new file and reverting CLAUDE.md
  restores prior state with no functional side-effects
- The sibling "knowledge-routing skill" ticket `depends_on` this doc; it must
  land before that ticket progresses past the authoring phase
