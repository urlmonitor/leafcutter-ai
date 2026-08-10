---
agent_id: code-review-architect
title: 'Agent Card: code-review-architect'
description: 'Deep code review agent. Infers requirements and tech stack from the
  code, runs an 8-axis review (architecture, coupling, cohesion, TypeScript, complexity,
  framework internals, dead code, defects), and writes a prioritised report to a file.
  Produces a scorecard and Before/After direction sketches for every finding. Use
  when: user asks for a deep code review, architectural review, or quality audit of
  existing code; asks "review this feature"; or wants a comprehensive review beyond
  what pr-reviewer covers.'
type: card
status: active
created: 2026-08-10
card_version: generated
last_updated: '2026-08-10'
---
# code-review-architect

**Deep code review agent. Infers requirements and tech stack from the code,
runs an 8-axis review (architecture, coupling, cohesion, TypeScript, complexity,
framework internals, dead code, defects), and writes a prioritised report to a
file. Produces a scorecard and Before/After direction sketches for every finding.
Use when: user asks for a deep code review, architectural review, or quality audit
of existing code; asks "review this feature"; or wants a comprehensive review
beyond what pr-reviewer covers.**

| Field | Value |
|-------|-------|
| Model | opus |
| Tier | standalone |
| Priority | — |
| Portable | Yes |
| Sign-off capable | No |

---

## When to Use

### Spawned By

- `user`
---

## Knowledge Flow

| Channel | Source | Injection Mode | Description |
|---------|--------|----------------|-------------|
| 1 | template description field | — | — |
| 6 | project files read during execution | — | — |
| 7 | bash command output (git, build, tests) | — | — |
---

## Spawn and Dependency

```mermaid
flowchart TD
    classDef supervisor fill:#dbeafe,stroke:#2563eb,stroke-width:2px
    classDef phase fill:#d1fae5,stroke:#059669,stroke-width:2px
    classDef utility fill:#f3f4f6,stroke:#4b5563,stroke-width:2px
    classDef target fill:#fee2e2,stroke:#dc2626,stroke-width:3px

    user["user\n(phase tier)"]:::phase
    code_review_architect["code-review-architect\n(standalone tier, priority ?)"]:::target

    user -->|dispatches| code_review_architect
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
| `Bash` |
| `Read` |
| `Write` |
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
| Conditional Behavior | the stack includes a framework/library with important internals | include low-level checks explicitly in the review | `None` |
| Conditional Behavior | such technology is present and no issues are found | state briefly that low-level checks were performed and no material violations were detected | `None` |
