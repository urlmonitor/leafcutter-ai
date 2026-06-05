---
agent_id: test-failure-triage
title: "Agent Card: test-failure-triage"
type: card
status: active
created: 2026-06-05
card_version: "generated"
---
# test-failure-triage

**Classifies post-merge test failures into structured categories before any
remediation work begins. Receives a post-merge failure list, a baseline
failure list, and the set of files changed by the feature branch, then
emits a triage report so downstream finalize-feature.js steps can route
each failure to the correct handler without re-running LLM reasoning.
(internal — spawned by finalize-feature only)**

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

    finalize_feature["finalize-feature\n(phase tier)"]:::phase
    test_failure_triage["test-failure-triage\n(utility tier, priority ?)"]:::target

    finalize_feature -->|dispatches| test_failure_triage
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
