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

Appends structured events to the install's declared telemetry stream so an epic
drive can be reconstructed afterwards: which supervisors were dispatched, which
tickets halted, how many retries a phase took. The stream is chosen at build time
and outlives the workspace; to see where it is, run
`python3 {{config.output_root}}/scripts/knowledge/sink_resolution.py --print-location telemetry`.

Invoked as a shell command, not read as instructions:

```bash
python .claude/skills/agent-telemetry/scripts/emit_event.py \
  --agent "ticket-supervisor" --event agent_start \
  --ticket "tickets/00_inbox/epics/EPIC-Foo/01_schema.md" \
  --phase "python-coder" || true
```

## Arguments

| Flag | Required | Meaning |
|------|----------|---------|
| `--event` | yes | Event type — `agent_start`, `supervisor_dispatch`, `epic_halted`, `epic_complete`, … |
| `--agent` | yes | Name of the emitting agent |
| `--ticket` | no | Ticket path, when the event is scoped to one |
| `--phase` | no | Phase name, e.g. `python-coder` |
| `--outcome` | no | `ok`, `blocked`, `failed`, … free text. For `--event capture_attempt` it is required and must be one of `recorded`, `nothing-to-record`, `failed`; anything else writes nothing, warns on stderr and exits 0. |
| `--missing-target` | no | Literal path of the script that could not run. Required for `capture_attempt` with outcome `failed` (otherwise refused the same way); `null` in every other record. |
| `--retry-count` | no | Attempt number, when the event is a retry |
| `--log` | no | Sink path override. Do not pass it: the default is the install's declared telemetry stream. |

## Record shape

One JSON line per invocation. Optional values are written as `null` rather than
omitted, so every line carries the same keys and a reader never has to test for
key presence:

```json
{"event_type": "agent_start", "timestamp": "2026-08-19T12:00:00+00:00",
 "agent_name": "ticket-supervisor", "ticket_path": "tickets/…/01_schema.md",
 "payload": {"phase": "python-coder", "outcome": null, "retry_count": null,
             "missing_target": null}}
```

`missing_target` is present on every record of every event type (`null` unless
given). The `capture_attempt` event is the capture-attempt ledger (ADR-034
Amendment 2): one record per run that reached the knowledge-capture step, with
outcome `recorded` (written by `emit_knowledge.py` itself after a successful
append), `nothing-to-record`, or `failed` (with `missing_target`).

## Nothing-to-record capture attempt

An agent runs this when its knowledge-capture step found no learning to record.
Agents never write a `recorded` attempt themselves; the emit helper does that
after a successful capture (ADR-034 Amendment 2).

```bash
python3 {{config.output_root}}/skills/agent-telemetry/scripts/emit_event.py --agent <agent> --event capture_attempt --phase knowledge-capture --outcome nothing-to-record --ticket <ticket> || true
```

Fill the angle-bracket values, and do not add `--log` or `--sink`.

## Failed capture attempt

An agent runs this only when the Yes-path `emit_knowledge.py` command it just
ran exited non-zero (a missing script exits 2, a crash or import error exits
1). A helper that exits 0, even with a warning on stderr, has handled its own
failure, so add no record: each failure leaves at most one `failed`
attempt (ADR-034 Amendment 2 A2.8).

```bash
python3 {{config.output_root}}/skills/agent-telemetry/scripts/emit_event.py --agent <agent> --event capture_attempt --phase knowledge-capture --outcome failed --missing-target '<missing target>' --ticket <ticket> || true
```

Fill the angle-bracket values. `<missing target>` is the first path after
`python3` in the `emit_knowledge.py` command you just ran, copied verbatim, and
it is never a category or a skill name. If the path contains a single quote,
write each `'` as `'\''` (ADR-034 A1.1). Include `--ticket` only when you have
a ticket path in hand, otherwise leave it out. Do not add `--log` or `--sink`.

Do not retry or work around the failure; finish your sign-off. If this section
cannot be read, or the command's script above is absent, no record is possible and the
failure stays on stderr and in your comment (ADR-034 A2.6).

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
