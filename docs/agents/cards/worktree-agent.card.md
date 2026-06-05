---
agent_id: worktree-agent
title: "Agent Card: worktree-agent"
type: card
status: active
created: 2026-06-05
card_version: "generated"
---
# worktree-agent

**Manages git worktree lifecycle — creates a new worktree for a feature branch
or reuses the existing epic worktree for an in-flight epic ticket; removes a
worktree after a branch merges. Create is non-destructive (no confirmation
required). Remove is destructive and requires an explicit "yes" after
displaying the safety-check report.
Use when: user types /worktree; asks to create a worktree for a branch or
ticket; asks to remove or close a worktree after a PR merges.**

| Field | Value |
|-------|-------|
| Model | haiku |
| Tier | utility |
| Priority | — |
| Portable | Yes |
| Sign-off capable | Yes |

---

## When to Use

### Spawned By

- `user`
- `epic-supervisor`
- `finalize-feature`
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
    epic_supervisor["epic-supervisor\n(supervisor tier)"]:::supervisor
    finalize_feature["finalize-feature\n(phase tier)"]:::phase
    worktree_agent["worktree-agent\n(utility tier, priority ?)"]:::target

    user -->|dispatches| worktree_agent
    epic_supervisor -->|dispatches| worktree_agent
    finalize_feature -->|dispatches| worktree_agent
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
---

## Skills Used

*No skills declared.*
---

## Configuration

*No configuration keys declared.*
---

## Contributor Notes

No conditional behaviors — this agent follows a single fixed execution path
