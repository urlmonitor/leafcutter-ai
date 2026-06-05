---
agent_id: onboard-config-section
title: "Agent Card: onboard-config-section"
type: card
status: active
created: 2026-06-05
card_version: "generated"
---
# onboard-config-section

**Haiku sub-agent spawned in parallel by the onboard wizard. Receives a discovery payload (folder structure, file excerpts, owned keys, confirmed values) and returns a JSON config fragment covering only the keys it owns. One instance is spawned per skills_config.json section (testing, packages, tickets, commands, project).**

| Field | Value |
|-------|-------|
| Model | haiku |
| Tier | utility |
| Priority | — |
| Portable | Yes |
| Sign-off capable | No |

---

## When to Use

### Spawned By

- `onboard`
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

    onboard["onboard\n(phase tier)"]:::phase
    onboard_config_section["onboard-config-section\n(utility tier, priority ?)"]:::target

    onboard -->|dispatches| onboard_config_section
```
---

## Input / Output Contract

*No structured I/O contract declared.*
---

## Tools Available

| Tool |
|------|
| `Read` |
---

## Skills Used

*No skills declared.*
---

## Configuration

*No configuration keys declared.*
---

## Contributor Notes

No conditional behaviors — this agent follows a single fixed execution path
