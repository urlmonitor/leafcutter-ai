---
agent_id: epic-supervisor
title: "Agent Card: epic-supervisor"
type: card
status: active
created: 2026-06-05
card_version: "generated"
---
# epic-supervisor

**[DEPRECATED — see ADR-006] User-facing supervisor — the entry agent of `/build-feature` (slash
command shipped by ticket 09 of EPIC-AgentSupervisor). Drives a whole
epic ticket-by-ticket: reads `Master_Plan.md` plus every sub-ticket,
builds a dependency graph from `depends_on` (logical) and
`files_touched` (physical), computes a maximal next-ready batch where
every member is parallel-safe under both edges, and dispatches one
`ticket-supervisor` per ticket via parallel `Agent` tool calls.
Halts only on structural blockers; per-ticket blockers are surfaced to
the user without halting independent siblings. Primary instruction set:
`.claude/skills/building-epics/SKILL.md`. Use when: user types
`/build-feature <epic>`, asks to "drive epic X to completion", or asks
to "walk EPIC-Y ticket-by-ticket".**

| Field | Value |
|-------|-------|
| Model | sonnet |
| Tier | supervisor |
| Priority | — |
| Portable | Yes |
| Sign-off capable | No |

---

## When to Use

### Spawned By

- `user`
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

    user["user\n(phase tier)"]:::phase
    epic_supervisor["epic-supervisor\n(supervisor tier, priority ?)"]:::target
    ticket_supervisor["ticket-supervisor\n(phase tier)"]:::phase
    retrospective_agent["retrospective-agent\n(phase tier)"]:::phase
    worktree_agent["worktree-agent\n(phase tier)"]:::phase
    changelog_agent["changelog-agent\n(phase tier)"]:::phase

    user -->|dispatches| epic_supervisor
    epic_supervisor -->|spawns| ticket_supervisor
    epic_supervisor -->|spawns| retrospective_agent
    epic_supervisor -->|spawns| worktree_agent
    epic_supervisor -->|spawns| changelog_agent
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
| `building-epics` | — | — |
| `signoff` | — | — |
---

## Configuration

*No configuration keys declared.*
---

## Contributor Notes

No conditional behaviors — this agent follows a single fixed execution path
