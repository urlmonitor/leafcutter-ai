---
agent_id: feedback-analyst
title: "Agent Card: feedback-analyst"
type: card
status: active
created: 2026-06-05
card_version: "generated"
---
# feedback-analyst

**Read-only analyst agent that loads the feedback-analysis skill, invokes trend_report.py against the full feedback corpus (or a filtered date window), interprets findings across all nine feedback categories, and returns a structured Markdown report with prioritized recommendations. Never modifies any file. Never creates tickets automatically — all recommendations are presented as a list for the user to act on. Dispatch via /feedback-report or invoke directly with optional --since, --until, --category, --trend, --format flags in $ARGUMENTS.**

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
    feedback_analyst["feedback-analyst\n(utility tier, priority ?)"]:::target

    user -->|dispatches| feedback_analyst
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

| Skill | Mode | Condition |
|-------|------|-----------|
| `feedback-analysis` | — | — |
---

## Configuration

*No configuration keys declared.*
---

## Contributor Notes

No conditional behaviors — this agent follows a single fixed execution path
