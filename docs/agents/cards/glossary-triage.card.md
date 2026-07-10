---
agent_id: glossary-triage
title: "Agent Card: glossary-triage"
description: "Pinned-haiku agent that classifies a jargon candidate term and returns a structured JSON decision. Accepts a candidate term plus up to 5 context windows from glossary_detector.py and returns one of three actions: add_to_glossary, add_to_blacklist, or false_positive. Never modifies files — only returns decisions. Invoked by glossary-bootstrap, check_glossary_coverage pre-commit hook, and documentation-expert coverage-lint step."
type: card
status: active
created: 2026-07-01
card_version: "generated"
components:
  - glossary
---
# glossary-triage

**Pinned-haiku agent that classifies a jargon candidate term and returns a structured JSON decision. Accepts a candidate term plus up to 5 context windows from glossary_detector.py and returns one of three actions: add_to_glossary, add_to_blacklist, or false_positive. Never modifies files — only returns decisions. Invoked by glossary-bootstrap, check_glossary_coverage pre-commit hook, and documentation-expert coverage-lint step.**

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

- `documentation-expert`
---

## Knowledge Flow

| Channel | Source | Injection Mode | Description |
|---------|--------|----------------|-------------|
| 1 | template description field | — | — |
| 4 | pre-flight file reads | — | — |
| 6 | project files read during execution | — | — |
| 7 | bash command output (git, build, tests) | — | — |
| 8 | PROJECT_CONTEXT.md | — | — |
---

## Spawn and Dependency

```mermaid
flowchart TD
    classDef supervisor fill:#dbeafe,stroke:#2563eb,stroke-width:2px
    classDef phase fill:#d1fae5,stroke:#059669,stroke-width:2px
    classDef utility fill:#f3f4f6,stroke:#4b5563,stroke-width:2px
    classDef target fill:#fee2e2,stroke:#dc2626,stroke-width:3px

    documentation_expert["documentation-expert\n(phase tier)"]:::phase
    glossary_triage["glossary-triage\n(utility tier, priority ?)"]:::target

    documentation_expert -->|dispatches| glossary_triage
```
---

## Input / Output Contract

### Outputs

| Name | Type | Description |
|------|------|-------------|
| `action` | structured_response | Output field: action |
| `reason` | structured_response | Output field: reason |
| `draft_entry` | structured_response | Output field: draft_entry |

### Mutates (Side Effects)

| Name | Type | Description |
|------|------|-------------|
| `none` | — | Read-only agent — no filesystem mutations |
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

### Key Behavioral Patterns

| Pattern | Trigger | Behavior | Related Agent |
|---------|---------|----------|---------------|
| Conditional Behavior | `action == "add_to_glossary"` | provide a complete markdown | `None` |
| Conditional Behavior | classifying `add_to_glossary` | write `draft_entry` as: | `None` |
