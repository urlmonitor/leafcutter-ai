---
agent_id: onboard
title: "Agent Card: onboard"
type: card
status: active
created: 2026-06-05
card_version: "generated"
---
# onboard

**Portable guided installation wizard. Auto-discovers the repo structure, fans out onboard-config-section Haiku sub-agents per config section, assembles a proposed skills_config.json, presents a diff for sign-off, and runs build.py on approval. Invoked via /onboard or auto-fired on SessionStart when skills_config.json is absent or all values are defaults.**

| Field | Value |
|-------|-------|
| Model | sonnet |
| Tier | utility |
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
    onboard["onboard\n(utility tier, priority ?)"]:::target
    onboard_config_section["onboard-config-section\n(phase tier)"]:::phase

    user -->|dispatches| onboard
    onboard -->|spawns| onboard_config_section
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
| `Write` |
| `Edit` |
| `Agent` |
---

## Skills Used

*No skills declared.*
---

## Configuration

*No configuration keys declared.*
---

## Contributor Notes

No conditional behaviors — this agent follows a single fixed execution path
