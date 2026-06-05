---
agent_id: finalize-feature
title: "Agent Card: finalize-feature"
type: card
status: active
created: 2026-06-05
card_version: "generated"
---
# finalize-feature

**Supervisor agent that orchestrates the 6-step post-merge feature finalization sequence by dispatching existing specialists. Confirmation-gated on all destructive steps. Use when: user types /finalize-feature; asks to "finish this feature", "merge and close", or "finalize the branch".**

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
    finalize_feature["finalize-feature\n(supervisor tier, priority ?)"]:::target
    pull_request["pull-request\n(phase tier)"]:::phase
    test_runner["test-runner\n(phase tier)"]:::phase
    test_failure_triage["test-failure-triage\n(phase tier)"]:::phase
    status_checker["status-checker\n(phase tier)"]:::phase
    worktree_agent["worktree-agent\n(phase tier)"]:::phase

    user -->|dispatches| finalize_feature
    finalize_feature -->|spawns| pull_request
    finalize_feature -->|spawns| test_runner
    finalize_feature -->|spawns| test_failure_triage
    finalize_feature -->|spawns| status_checker
    finalize_feature -->|spawns| worktree_agent
```
---

## Input / Output Contract

*No structured I/O contract declared.*
---

## Tools Available

| Tool |
|------|
| `Bash` |
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
