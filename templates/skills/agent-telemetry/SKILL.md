---
allowed-tools: Bash
description: Append one agent-drive telemetry event to the JSONL sink. Use when a
  supervisor or runbook needs to record a dispatch, halt, completion, retry, or
  phase transition during an epic or ticket drive. Emission is best-effort — a
  write failure warns and exits 0 so an unreachable sink never halts a build.
name: agent-telemetry
portable: true
---

# agent-telemetry — record what a drive actually did

Appends structured events to `debugging/logs/agent_telemetry.jsonl` so an epic
drive can be reconstructed afterwards: which supervisors were dispatched, which
tickets halted, how many retries a phase took.

Invoked as a shell command, not read as instructions:

```bash
python .claude/skills/agent-telemetry/scripts/emit_event.py \
  --agent "ticket-supervisor" --event agent_start \
  --ticket "tickets/00_inbox/epics/EPIC-Foo/01_schema.md" \
  --phase "python-coder" \
  --log debugging/logs/agent_telemetry.jsonl || true
```

## Arguments

| Flag | Required | Meaning |
|------|----------|---------|
| `--event` | yes | Event type — `agent_start`, `supervisor_dispatch`, `epic_halted`, `epic_complete`, … |
| `--agent` | yes | Name of the emitting agent |
| `--ticket` | no | Ticket path, when the event is scoped to one |
| `--phase` | no | Phase name, e.g. `python-coder` |
| `--outcome` | no | `ok`, `blocked`, `failed`, … |
| `--retry-count` | no | Attempt number, when the event is a retry |
| `--log` | no | Sink path. Defaults to `debugging/logs/agent_telemetry.jsonl` |

## Record shape

One JSON line per invocation. Optional values are written as `null` rather than
omitted, so every line carries the same keys and a reader never has to test for
key presence:

```json
{"event_type": "agent_start", "timestamp": "2026-08-19T12:00:00+00:00",
 "agent_name": "ticket-supervisor", "ticket_path": "tickets/…/01_schema.md",
 "payload": {"phase": "python-coder", "outcome": null, "retry_count": null}}
```

## Emission is best-effort

A sink that cannot be written produces a stderr warning and **exit 0**. This is
deliberate (`BP-400a-1-i`): a drive must not fail because the thing observing it
failed. Call sites still append `|| true` as belt-and-braces.

The corollary matters when reading the log: **absence of an event is not
evidence the step did not run.** An unwritable sink drops lines silently from
the log's point of view. If a drive's telemetry looks empty, check the sink is
writable before concluding the drive misbehaved — that exact confusion has
already cost one retrospective.

## Not to be confused with

`scripts/agent-health/agent_telemetry.py` records a different thing: per-invocation
cost metrics (lane, duration, token counts) for fast-lane comparison. Same word,
different record. Do not merge the two.
