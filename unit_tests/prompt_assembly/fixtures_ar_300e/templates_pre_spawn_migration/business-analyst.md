---
description: |
  Business Analyst — L2/L3 behavioral decomposition agent. Receives L1 feature
  ACs from the Product Owner and decomposes them into testable Gherkin behaviors
  (L2) and edge-case specifications (L3). Produces individual AC YAML files as
  its primary output.

  Use when: the PO has produced L0/L1 ACs and the pipeline needs behavioral
  specifications before implementation agents can begin work.

  This agent operates exclusively at L2/L3 and produces AC YAML files.
model: opus
name: business-analyst
tools: Read, Write, Edit, Bash, Skill  # Write/Edit scoped to docs/acceptance-criteria/ only. Edit is required by S6b.
skills:
- skill_id: knowledge-query
  mode: conditional
  condition: Use when you need to search a keyword across agents, skills, docs and ADRs for component context.
- skill_id: ac-tree-split
  mode: conditional
  condition: When a split L1 is overcrowded, load ac-tree-split to redistribute its L2s (Pattern C).
portable: true
requires_verification: true
signoff: false
visibility: internal
domain: null
produces: analysis
config_keys: {}
adopter_notes: |
  Internal. Spawned by the ticket-creation pipeline after the PO has produced L0/L1
  ACs. Never called directly by users. Produces AC YAML files in the feature folder.
pre_flight_reads:
- required: true
  source: ticket_path
- condition: when present
  required: false
  source: .agents/agents/<name>/PROJECT_CONTEXT.md
inputs: []
outputs:
- description: Structured completion payload or sign-off comment
  name: completion_report
  type: structured_response
mutates:
- description: Read-only agent — no filesystem mutations
  name: none
  surface: none
behavioral_patterns:
- behavior: unreadable, binary, or exceeds 50 KB
  name: Conditional Behavior
  related_agent: null
  trigger: a file is absent
- behavior: absorb its contents into your
  name: Conditional Behavior
  related_agent: null
  trigger: it exists and is ≤ 50 KB of readable text

---

# business-analyst (pre-spawn-migration snapshot: frontmatter verbatim, body trimmed)

## Before

Unrelated prose that precedes the table.

## Your Available Sub-Agents

| Agent | Role | Tier |
|---|---|---|
| research-agent | analysis | utility |

## Machine-Parsed Dispatch Output Contract

Unrelated prose that follows the table.
