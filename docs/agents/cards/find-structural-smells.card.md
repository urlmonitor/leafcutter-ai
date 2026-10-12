---
agent_id: find-structural-smells
title: 'Agent Card: find-structural-smells'
description: 'Reviews code for the six local / mechanical Fowler code smells — Mysterious
  Name, Duplicated Code, Long Function, Long Parameter List, Loops, Repeated Switches
  — and points each at its named refactoring. Runs on Sonnet: these are near-lint,
  mostly-within-a-function smells. Loads the review-for-code-smells core skill plus
  the structural bucket skill and RETURNS its findings (it does not write a file).
  Usually dispatched in parallel by the code-smell-review orchestration alongside
  find-design-smells; also runnable standalone. Use when: the structural half of a
  code-smell review is needed, or the user wants a quick mechanical smell pass.'
type: card
status: active
created: 2026-08-13
card_version: generated
last_updated: '2026-08-13'
---
# find-structural-smells

**Reviews code for the six local / mechanical Fowler code smells — Mysterious Name,
Duplicated Code, Long Function, Long Parameter List, Loops, Repeated Switches — and points
each at its named refactoring. Runs on Sonnet: these are near-lint, mostly-within-a-function
smells. Loads the review-for-code-smells core skill plus the structural bucket skill and
RETURNS its findings (it does not write a file). Usually dispatched in parallel by the
code-smell-review orchestration alongside find-design-smells; also runnable standalone.
Use when: the structural half of a code-smell review is needed, or the user wants a quick
mechanical smell pass.**

| Field | Value |
|-------|-------|
| Model | sonnet |
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
    find_structural_smells["find-structural-smells\n(standalone tier, priority ?)"]:::target

    user -->|dispatches| find_structural_smells
```
---

## Input / Output Contract

### Outputs

| Name | Type | Description |
|------|------|-------------|
| `findings` | structured_response | Structural-bucket findings sections in the review-for-code-smells format |

### Mutates (Side Effects)

| Name | Type | Description |
|------|------|-------------|
| `none` | — | Read-only reviewer — no filesystem mutations |
---

## Tools Available

| Tool |
|------|
| `Bash` |
| `Read` |
| `Skill` |
---

## Skills Used

| Skill | Mode | Condition |
|-------|------|-----------|
| `review-for-code-smells` | — | — |
| `review-for-structural-code-smells` | — | — |
---

## Configuration

*No configuration keys declared.*
---

## Contributor Notes

### Key Behavioral Patterns

| Pattern | Trigger | Behavior | Related Agent |
|---------|---------|----------|---------------|
| Conditional Behavior | invoked as part of an orchestrated code-smell-review | return only the findings sections (Summary rows, HIGH/MEDIUM/LOW findings, Scorecard rows) for the orchestrator to merge | `find-design-smells` |
| Conditional Behavior | invoked standalone with no orchestrator | emit the full standalone report instead of findings-only sections | `None` |
| Delegation | a cross-cutting design smell is spotted while scanning the structural bucket | note the smell in one line for the design reviewer and do not fully work it up | `find-design-smells` |
