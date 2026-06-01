---
title: "Reference: Feedback Client Concurrency Limitation"
type: reference
status: active
created: 2026-05-29
last_updated: 2026-05-29
components:
  - agent_telemetry
related_docs:
  - "docs/ticket-lifecycle.md"
---

# Feedback Client Concurrency Limitation

## Limitation

When multiple ticket-supervisors are dispatched in parallel (e.g. during a
bulk backlog flush), the feedback sink (`agent_telemetry.jsonl`) may record
`submit-failed` events. Some agent feedback writes are silently dropped.

Observed during: `EPIC-FlattenSupervisorChain` (parallel ticket-supervisor
batch, 2026-05-29).

## Root Cause

The feedback writer appends to `agent_telemetry.jsonl` with no file lock. Two
agents appending at the same moment produce a write collision; one write is
discarded and logged as `submit-failed`. No retry is performed.

## Workaround

Do not use `agent_telemetry.jsonl` as an authoritative audit record during
parallel batches. Use the following sources instead:

| Authoritative source | How to query |
|---|---|
| `git log --oneline` | Lists every commit landed; agent work that reached sign-off is present |
| Ticket `## Comments` block | Each ticket's sign-off step appends a timestamped comment; these are written atomically to individual files with no contention |

If a ticket is missing from `agent_telemetry.jsonl` but its file exists with
`status: done` and a sign-off comment, the work completed successfully.

## Future Fix

Add an exclusive file lock (e.g. `fcntl.flock` on POSIX,
`msvcrt.locking` on Windows) to the feedback writer before each append.
A future ticket should be opened against the `agent_telemetry` component to
implement this. Until then, treat `agent_telemetry.jsonl` as best-effort
telemetry only.
