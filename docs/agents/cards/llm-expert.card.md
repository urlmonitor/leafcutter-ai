---
agent_id: llm-expert
title: "Agent Card: llm-expert"
type: card
status: active
created: 2026-06-05
card_version: "generated"
---
# llm-expert

**LLM-instructions specialist that owns the craft of writing, auditing, and
maintaining LLM instructions inside agent templates, skill files, and
slash-command prompts. Writes and edits agent templates
(templates/agents/*.md), writes and edits skill bodies
(templates/skills/*/SKILL.md), and audits prompts for convention violations
(shell rules, nesting limits, tool allowlists, signoff protocol adherence).
Use when: a ticket's agents: map is marked as requiring prompt-engineering or
template work; user asks to "write an agent template", "audit a skill", or
"create a slash-command prompt".**

| Field | Value |
|-------|-------|
| Model | sonnet |
| Tier | phase |
| Priority | 6 |
| Portable | Yes |
| Sign-off capable | Yes |

---

## When to Use

### Spawned By

- `ticket-supervisor`
---

## Knowledge Flow

*No knowledge channels declared.*

---

## Spawn and Dependency

```mermaid
flowchart TD
    classDef supervisor fill:#dbeafe,stroke:#2563eb,stroke-width:2px
    classDef phase fill:#d1fae5,stroke:#059669,stroke-width:2px
    classDef utility fill:#f3f4f6,stroke:#4b5563,stroke-width:2px
    classDef target fill:#fee2e2,stroke:#dc2626,stroke-width:3px

    ticket_supervisor["ticket-supervisor\n(supervisor tier)"]:::supervisor
    llm_expert["llm-expert\n(phase tier, priority 6)"]:::target
    research_agent["research-agent\n(utility tier)"]:::utility

    ticket_supervisor -->|dispatches| llm_expert
    llm_expert -->|spawns| research_agent
```
---

## Input / Output Contract

*No structured I/O contract declared.*
---

## Tools Available

| Tool |
|------|
| `Bash` |
| `Read` |
| `Edit` |
| `Write` |
| `Agent` |
---

## Skills Used

| Skill | Mode | Condition |
|-------|------|-----------|
| `add-agent-to-package` | — | — |
| `add-skill-to-package` | — | — |
| `signoff` | — | — |
---

## Configuration

*No configuration keys declared.*
---

## Contributor Notes

No conditional behaviors — this agent follows a single fixed execution path
