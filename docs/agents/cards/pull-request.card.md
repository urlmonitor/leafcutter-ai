---
agent_id: pull-request
title: "Agent Card: pull-request"
type: card
status: active
created: 2026-06-05
card_version: "generated"
---
# pull-request

**Confirmation-gated PR creation agent. Reads recent commits on the current
branch, drafts a title (<=70 chars) and body (Summary + Test plan), shows
the draft to the user, and waits for an explicit "yes" before pushing the
branch and running gh pr create. Spawns conflict-resolver on any merge
conflict detected before the push, then retries once after resolution.
Use when: user types /pull-request; is in the commit->push->PR flow via
/commit-push-pr; or asks to "open a PR", "create a pull request", or
"push and open a PR for this branch".**

| Field | Value |
|-------|-------|
| Model | sonnet |
| Tier | phase |
| Priority | 13 |
| Portable | Yes |
| Sign-off capable | Yes |

---

## When to Use

### Spawned By

- `ticket-supervisor`
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

    ticket_supervisor["ticket-supervisor\n(supervisor tier)"]:::supervisor
    finalize_feature["finalize-feature\n(phase tier)"]:::phase
    pull_request["pull-request\n(phase tier, priority 13)"]:::target
    conflict_resolver["conflict-resolver\n(phase tier)"]:::phase

    ticket_supervisor -->|dispatches| pull_request
    finalize_feature -->|dispatches| pull_request
    pull_request -->|spawns| conflict_resolver
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
| `signoff` | — | — |
---

## Configuration

*No configuration keys declared.*
---

## Contributor Notes

No conditional behaviors — this agent follows a single fixed execution path
