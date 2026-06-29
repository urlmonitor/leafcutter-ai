---
agent_id: test-writer
title: "Agent Card: test-writer"
description: "TDD test-first authoring agent. Spawned by ticket-supervisor at priority 5, BEFORE python-coder or sql-coder run. Reads the ## Test Requirements section from the ticket body and writes the specified failing test stubs, runs the suite to confirm all new tests are RED (non-zero exit), captures a structured red_baseline block in its sign-off comment, and hands off to coders whose job is to make the red-baseline green. Classifies test failures before touching production code, enumerates consumers via blast-radius query, and blocks contract-shrinking changes without explicit authorization. Emits a completion report and signs off the ticket phase. Use when: ticket has a non-empty test_requirements.tests array. Skip (sign off immediately, zero file writes) when tests array is empty or block is absent."
type: card
status: active
created: 2026-06-29
card_version: "generated"
---
# test-writer

**TDD test-first authoring agent. Spawned by ticket-supervisor at priority 5,
BEFORE python-coder or sql-coder run. Reads the ## Test Requirements section
from the ticket body and writes the specified failing test stubs, runs the suite
to confirm all new tests are
RED (non-zero exit), captures a structured red_baseline block in its sign-off
comment, and hands off to coders whose job is to make the red-baseline green.
Classifies test failures before touching production code, enumerates consumers
via blast-radius query, and blocks contract-shrinking changes without explicit
authorization. Emits a completion report and signs off the ticket phase.
Use when: ticket has a non-empty test_requirements.tests array. Skip (sign off
immediately, zero file writes) when tests array is empty or block is absent.**

| Field | Value |
|-------|-------|
| Model | sonnet |
| Tier | phase |
| Priority | 5 |
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
| 4 | pre-flight file reads | — | — |
| 5 | skills_config.json config_keys | — | — |
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
    test_writer["test-writer\n(phase tier, priority 5)"]:::target
    research_agent["research-agent\n(utility tier)"]:::utility
    test_runner["test-runner\n(phase tier)"]:::phase

    ticket_supervisor -->|dispatches| test_writer
    test_writer -->|spawns| research_agent
    test_writer -->|spawns| test_runner
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
| `ticket_frontmatter_agents_status` | — | Sets agents.test-writer to signed_off or failed |
| `sign_offs_checklist` | — | Checks the test-writer checkbox with timestamp |
| `implementation_artifacts` | — | Files created or modified during phase execution |
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
| `signoff` | conditional | — |
---

## Configuration

| Key | Required | Description |
|-----|----------|-------------|
| `testing_context` | No | Test infrastructure context: directories, frameworks, constraints |
| `test_command_live_trader` | No | Command to run the fast unit test suite |
| `test_output_dir` | No | Temp directory for test output files |
---

## Contributor Notes

### Key Behavioral Patterns

| Pattern | Trigger | Behavior | Related Agent |
|---------|---------|----------|---------------|
| Stop-and-Ask | condition requiring user decision or out-of-scope action | Do not proceed without human review. | `None` |
| Delegation to research-agent | task requiring research-agent capabilities | Delegates to research-agent via Agent tool | `research-agent` |
| Conditional Behavior | an AC is untestable | write `(not testable: <reason>)` in the Test column | `None` |
| Conditional Behavior | `## Agent Contracts` is absent from the ticket body | skip all AC-aware | `None` |
