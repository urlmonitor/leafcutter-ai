---
agent_id: business-analyst
title: 'Agent Card: business-analyst'
description: 'Business Analyst — L2/L3 behavioral decomposition agent. Receives L1
  feature ACs from the Product Owner and decomposes them into testable Gherkin behaviors
  (L2) and edge-case specifications (L3). Produces individual AC YAML files as its
  primary output.  Use when: the PO has produced L0/L1 ACs and the pipeline needs
  behavioral specifications before implementation agents can begin work.  This agent
  operates exclusively at L2/L3 and produces AC YAML files.'
type: card
status: active
created: 2026-08-13
card_version: generated
last_updated: '2026-08-13'
---
# business-analyst

**Business Analyst — L2/L3 behavioral decomposition agent. Receives L1 feature
ACs from the Product Owner and decomposes them into testable Gherkin behaviors
(L2) and edge-case specifications (L3). Produces individual AC YAML files as
its primary output.

Use when: the PO has produced L0/L1 ACs and the pipeline needs behavioral
specifications before implementation agents can begin work.

This agent operates exclusively at L2/L3 and produces AC YAML files.**

| Field | Value |
|-------|-------|
| Model | opus |
| Tier | utility |
| Priority | — |
| Portable | Yes |
| Sign-off capable | No |

---

## When to Use
---

## Knowledge Flow

| Channel | Source | Injection Mode | Description |
|---------|--------|----------------|-------------|
| 1 | template description field | — | — |
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

    business_analyst["business-analyst\n(utility tier, priority ?)"]:::target
    research_agent["research-agent\n(utility tier)"]:::utility

    business_analyst -->|spawns| research_agent
```
---

## Input / Output Contract

### Outputs

| Name | Type | Description |
|------|------|-------------|
| `completion_report` | structured_response | Structured completion payload or sign-off comment |

### Mutates (Side Effects)

| Name | Type | Description |
|------|------|-------------|
| `none` | — | Read-only agent — no filesystem mutations |
---

## Tools Available

| Tool |
|------|
| `Read` |
| `Write` |
| `Edit` |
| `Bash` |
| `Skill` |
---

## Skills Used

| Skill | Mode | Condition |
|-------|------|-----------|
| `ac-tree-split` | — | — |
| `knowledge-query` | — | — |
---

## Configuration

*No configuration keys declared.*
---

## Contributor Notes

### Key Behavioral Patterns

| Pattern | Trigger | Behavior | Related Agent |
|---------|---------|----------|---------------|
| Conditional Behavior | a file is absent | unreadable, binary, or exceeds 50 KB | `None` |
| Conditional Behavior | it exists and is ≤ 50 KB of readable text | absorb its contents into your | `None` |
---

## AC Assignments

### business-analyst

- ACS-500g-6: The first pattern produced is the three-round seeded-gap agent-evaluation protocol
- ACS-500g-6-i: An agent passes evaluation only when it catches every seeded item in all three rounds
- ACS-500g-6-ii: The agent under test is never told which items are seeded, or how many
- ACS-500g-7: The first pattern gets its first consumer, closing the producer-to-consumer loop
- UXP-402: On approval, acceptance criteria are generated from the flow's steps
- UXP-402a: If the person rejects the drafted flow at review, no acceptance criteria are generated
