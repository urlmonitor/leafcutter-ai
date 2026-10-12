---
agent_id: restructuring-specialist
title: 'Agent Card: restructuring-specialist'
description: 'Restructuring specialist. Brought in by a run, as a party separate from
  the coder that wrote the change, when a commit-guardian check refuses a change and
  its declaration names restructuring as the remedy (a function over the complexity
  limit, a file over the size limit). Restructures the named code to meet the stated
  demand without changing behaviour, and returns a machine-readable report of the
  skills it applied and how the engagement ended. Use when: a refusal declaration
  names restructuring-specialist; NOT for writing new behaviour (that is the coder)
  and NOT for SQL or frontend files.'
type: card
status: active
created: 2026-10-12
card_version: generated
last_updated: '2026-10-12'
---
# restructuring-specialist

**Restructuring specialist. Brought in by a run, as a party separate from the coder that wrote the change, when a commit-guardian check refuses a change and its declaration names restructuring as the remedy (a function over the complexity limit, a file over the size limit). Restructures the named code to meet the stated demand without changing behaviour, and returns a machine-readable report of the skills it applied and how the engagement ended. Use when: a refusal declaration names restructuring-specialist; NOT for writing new behaviour (that is the coder) and NOT for SQL or frontend files.**

| Field | Value |
|-------|-------|
| Model | sonnet |
| Tier | phase |
| Priority | 8.5 |
| Portable | Yes |
| Sign-off capable | Yes |

---

## When to Use

### Spawned By

- `ticket-supervisor`
---

## Knowledge Flow

| Channel | Source | Injection Mode | Description |
|---------|--------|----------------|-------------|
| 1 | template description field | — | — |
| 3 | brief carrying the refusing check's demand | — | — |
| 4 | pre-flight file reads | — | — |
| 7 | bash command output (tests, complexity and size checkers) | — | — |
---

## Spawn and Dependency

```mermaid
flowchart TD
    classDef supervisor fill:#dbeafe,stroke:#2563eb,stroke-width:2px
    classDef phase fill:#d1fae5,stroke:#059669,stroke-width:2px
    classDef utility fill:#f3f4f6,stroke:#4b5563,stroke-width:2px
    classDef target fill:#fee2e2,stroke:#dc2626,stroke-width:3px

    ticket_supervisor["ticket-supervisor\n(supervisor tier)"]:::supervisor
    restructuring_specialist["restructuring-specialist\n(phase tier, priority 8.5)"]:::target

    ticket_supervisor -->|dispatches| restructuring_specialist
```
---

## Input / Output Contract

### Inputs

| Name | Type | Description |
|------|------|-------------|
| `demand` | structured_payload | The refusing check's demand: file, function and score with the allowed limit, or file and measured lines to leave |
| `ticket_path` | file_path | Path to the ticket markdown file, when engaged inside a ticket drive |

### Outputs

| Name | Type | Description |
|------|------|-------------|
| `restructured_files` | file | Edited and newly extracted source files that meet the demand |
| `skills_applied_report` | structured_response | JSON report with outcome (demand_met | attempted_short | could_not_act) and the skills_applied object |
| `sign_off_comment` | sign_off_comment | Sign-off comment with status: ok | blocker, when a ticket_path was given |

### Mutates (Side Effects)

| Name | Type | Description |
|------|------|-------------|
| `ticket_frontmatter_agents_status` | — | Sets agents.restructuring-specialist to signed_off or failed |
| `sign_offs_checklist` | — | Checks the restructuring-specialist checkbox with timestamp |
---

## Tools Available

| Tool |
|------|
| `Bash` |
| `Read` |
| `Edit` |
| `Write` |
---

## Skills Used

| Skill | Mode | Condition |
|-------|------|-----------|
| `signoff` | always | — |
| `complexity-reduction` | conditional | — |
---

## Configuration

*No configuration keys declared.*
---

## Contributor Notes

### Key Behavioral Patterns

| Pattern | Trigger | Behavior | Related Agent |
|---------|---------|----------|---------------|
| Demand-Chosen Skill | Brief carries a complexity demand (function, score, allowed limit) | Loads and applies complexity-reduction, and reports it true in skills_applied | `None` |
| File-Size Approach | Brief carries a file-size demand (measured lines to leave a file) | Uses its own split-by-responsibility approach; does not load complexity-reduction and reports it false | `None` |
| Stop-and-Ask | Demand is neither complexity nor file-size, or the work needs new behaviour or non-Python files | Halts and hands back to the coder, workflow-architect, or the user | `python-coder` |
