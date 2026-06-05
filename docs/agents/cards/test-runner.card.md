---
agent_id: test-runner
title: "Agent Card: test-runner"
type: card
status: active
created: 2026-06-05
card_version: "generated"
---
# test-runner

**Picks the right test suite based on what has changed, runs it, and returns a
structured failure report (file, test name, stacktrace excerpt, rerun command)
instead of a raw stdout dump.
Use when: user types /test; asks "run the tests"; asks "did I break anything?";
asks "run the SQL tests"; or any implementation agent (python-coder, sql-coder)
invokes this agent for its inner-loop test cycle.**

| Field | Value |
|-------|-------|
| Model | sonnet |
| Tier | phase |
| Priority | 9 |
| Portable | Yes |
| Sign-off capable | Yes |

---

## When to Use

### Spawned By

- `ticket-supervisor`
- `python-coder`
- `test-writer`
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

    ticket_supervisor["ticket-supervisor\n(supervisor tier)"]:::supervisor
    python_coder["python-coder\n(phase tier)"]:::phase
    test_writer["test-writer\n(phase tier)"]:::phase
    finalize_feature["finalize-feature\n(phase tier)"]:::phase
    test_runner["test-runner\n(phase tier, priority 9)"]:::target

    ticket_supervisor -->|dispatches| test_runner
    python_coder -->|dispatches| test_runner
    test_writer -->|dispatches| test_runner
    finalize_feature -->|dispatches| test_runner
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
| `signoff` | — | — |
---

## Configuration

| Key | Required | Description |
|-----|----------|-------------|
| `test_command_live_trader` | No | Command to run the fast unit test suite |
| `test_output_dir` | No | Temp directory for test output files |
---

## Contributor Notes

No conditional behaviors — this agent follows a single fixed execution path
