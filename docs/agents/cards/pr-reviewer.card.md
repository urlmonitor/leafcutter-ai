---
agent_id: pr-reviewer
title: "Agent Card: pr-reviewer"
type: card
status: active
created: 2026-06-05
card_version: "generated"
---
# pr-reviewer

**Pre-PR self-review against the working diff. Classifies every finding from
the underlying pr-review-toolkit:review-pr skill into high / medium / low
confidence, surfaces only high-confidence issues, suppresses low-confidence
noise, and escalates a medium-confidence cluster to Opus when more than 3
medium findings are returned.
Use when: user types /pr-review; asks "review my changes before I open a PR";
wants a sanity check on the working diff; or types "is there anything wrong
with this diff?". Also invoked by pull-request as a pre-open step.**

| Field | Value |
|-------|-------|
| Model | sonnet |
| Tier | phase |
| Priority | 11 |
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
    pr_reviewer["pr-reviewer\n(phase tier, priority 11)"]:::target

    ticket_supervisor -->|dispatches| pr_reviewer
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
