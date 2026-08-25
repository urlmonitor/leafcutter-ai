---
agent_id: ac-fulfillment-gate
title: 'Agent Card: ac-fulfillment-gate'
description: 'AC fulfillment gate. Runs at priority 11.7 (after ac-validator at 11.5,
  before commit at 12). Resolves AC coverage via the shared ac_coverage_resolver module
  (accepts both the two-key ac_traceability form the generator emits and the legacy
  l2/l3/ac_path list form), then verifies AC YAML store fields (work_status, implemented_by,
  covered_by) are accurate and up-to-date before any commit is made. When verification
  fails but diff evidence exists, auto-fixes the YAML store fields (append-only, idempotent).
  Returns status: ok only when at least one AC was resolved and every resolved AC
  passes, or when ac_traceability is absent entirely; status: blocker with per-AC
  details if any AC fails after auto-fix attempt, or if a present ac_traceability
  block resolves to zero ACs. Use when: ticket-supervisor dispatches at priority 11.7
  for any ticket that has ac_traceability frontmatter referencing L2/L3 AC YAML files.
  Skips silently for L0/L1 ACs (composite — fulfillment derived from children).'
type: card
status: active
created: 2026-08-13
card_version: generated
last_updated: '2026-08-13'
---
# ac-fulfillment-gate

**AC fulfillment gate. Runs at priority 11.7 (after ac-validator at 11.5, before commit at 12). Resolves AC coverage via the shared ac_coverage_resolver module (accepts both the two-key ac_traceability form the generator emits and the legacy l2/l3/ac_path list form), then verifies AC YAML store fields (work_status, implemented_by, covered_by) are accurate and up-to-date before any commit is made. When verification fails but diff evidence exists, auto-fixes the YAML store fields (append-only, idempotent). Returns status: ok only when at least one AC was resolved and every resolved AC passes, or when ac_traceability is absent entirely; status: blocker with per-AC details if any AC fails after auto-fix attempt, or if a present ac_traceability block resolves to zero ACs. Use when: ticket-supervisor dispatches at priority 11.7 for any ticket that has ac_traceability frontmatter referencing L2/L3 AC YAML files. Skips silently for L0/L1 ACs (composite — fulfillment derived from children).**

| Field | Value |
|-------|-------|
| Model | sonnet |
| Tier | phase |
| Priority | 11.7 |
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
| 3 | ticket_path from ticket-supervisor | — | — |
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

    ticket_supervisor["ticket-supervisor\n(supervisor tier)"]:::supervisor
    ac_fulfillment_gate["ac-fulfillment-gate\n(phase tier, priority 11.7)"]:::target

    ticket_supervisor -->|dispatches| ac_fulfillment_gate
```
---

## Input / Output Contract

### Inputs

| Name | Type | Description |
|------|------|-------------|
| `ticket_path` | file_path | Absolute path to the ticket markdown file |

### Outputs

| Name | Type | Description |
|------|------|-------------|
| `sign_off_comment` | sign_off_comment | Sign-off comment with status: ok | blocker | handoff |

### Mutates (Side Effects)

| Name | Type | Description |
|------|------|-------------|
| `ticket_frontmatter_agents_status` | — | Sets agents.ac-fulfillment-gate to signed_off or failed |
| `sign_offs_checklist` | — | Checks the ac-fulfillment-gate checkbox with timestamp |
---

## Tools Available

| Tool |
|------|
| `Bash` |
| `Read` |
| `Edit` |
---

## Skills Used

| Skill | Mode | Condition |
|-------|------|-----------|
| `signoff` | always | — |
---

## Configuration

*No configuration keys declared.*
---

## Contributor Notes

### Key Behavioral Patterns

| Pattern | Trigger | Behavior | Related Agent |
|---------|---------|----------|---------------|
| Conditional Behavior | the file is absent | treat as L2/L3 (check it) | `None` |
| Conditional Behavior | `level` equals `L0` or `L1` | skip this AC entirely | `None` |
