---
title: "Agent Telemetry — Per-Invocation Cost and Time Tracking"
description: "Per-invocation metric emitter and lane comparison reporter. Appends structured JSONL records to the telemetry sink after each agent call, exposing duration, token volumes, and cache-hit counts for fast-lane vs heavy-pipeline cost comparison."
flight_level: L3-Component
status: active
type: reference
created: 2026-06-08
last_updated: 2026-10-12
components:
  - agent_telemetry
related_docs:
  - docs/architecture/adrs/ADR-069-durable-log-root-for-workspaces.md
  - docs/architecture/feedback-lifecycle.md
---

# Agent Telemetry

## Overview

Agent Telemetry is a per-invocation JSONL emit module. After each phase-agent call
completes, the calling harness (or the phase agent itself) invokes
`emit_agent_telemetry` to append one structured record to the sink path it is given.
Records carry the invocation's lane tag,
agent identifier, wall-clock duration, and token counts (input, output, and
cache-read). A companion report function (`build_lane_comparison_report`) reads the
sink and returns per-lane aggregates for the fast-lane vs heavy-pipeline comparison.

## Where the telemetry stream is kept

The install's telemetry stream is the `operational_telemetry_stream` value in the
build-time declaration `<output_root>/config/knowledge_sink.json`, i.e.
`<operational_log_root>/agent_telemetry.jsonl`. It sits beside the feedback sink in one
directory that outlives per-drive worktrees
([ADR-069](../adrs/ADR-069-durable-log-root-for-workspaces.md); full description in
[Feedback Lifecycle — Where every log is kept](../feedback-lifecycle.md#where-every-log-is-kept--one-declared-log-root-adr-069)).

- **A usable stream.** The stream counts only when the declaration also records an absolute
  `operational_log_root` and the stream sits directly under it
  (`sink_resolution.read_usable_stream`). A build with `--no-log-root` records an empty
  declaration, so there is no stream and every writer refuses.
- **Stale versus first write.** Stale means the enduring root is gone: the directory holding
  `operational_log_root` (its parent, or the project above `debugging`). A log directory
  missing under a live root is a fresh install, and the first write creates it.
- **Event writer.** The supervisor-event emitter
  `.claude/skills/agent-telemetry/scripts/emit_event.py` writes to the stream named by
  its own deployed workspace's declaration when `--log` is omitted. It finds that
  declaration from its own resolved location, never from the caller's directory; the
  `.gemini` copy steps out of the `gemini` directory and reads the same install's
  declaration. It stays standard-library only, so `_declared_stream` carries an inline copy
  of the usable-stream and staleness rules. If the declaration is unusable or stale, it
  warns on stderr naming it, writes and creates nothing, and exits 0. Otherwise it creates
  only up to the log directory and appends the record as one `os.write` on an `O_APPEND`
  descriptor. Shipped prompts no longer pass `--log` (INF-500d-4-vi).
- **Other writers.** `inline_work_guard.py` (and its `.gemini` copy) appends its audit record
  to `<operational_log_root>/inline_work_guard.jsonl`. It applies the same staleness rule
  inline and creates only up to the log directory under a live root; otherwise it warns and
  writes nothing, and the block/warn exit code is unchanged. `plan-feature.js` gets the
  stream from `sink_resolution.py --print-location telemetry`, creates the log directory
  only when the enduring root is live, and does not compose a path itself.
- **Readers.** `generate_health_report.py` defaults `--telemetry` and `--feedback` to the
  declared values. `weekly_health.py` defaults `--telemetry` the same way, through
  `generate_health_report.resolve_telemetry_stream`. `extract_epic_facts.py` defaults
  `--telemetry` to the declared stream through `sink_resolution.read_usable_stream`. Each
  prints `read N records from <path>` per stream, and exits 1 when no usable declaration
  exists and no explicit path was given. An explicit path is used as given.
- **Location query.**
  `python3 .leafcutter/scripts/knowledge/sink_resolution.py --print-location telemetry`
  prints the stream without writing, or refuses with exit 1 when it is not usable.

## Responsibilities

- Append one JSONL record per agent invocation to the telemetry sink
- Auto-inject a UTC timestamp (`ts`) when the caller does not supply one
- Log a `WARNING` and increment a module-level failed-write counter when an
  `OSError` prevents a sink write — never propagate the error to the caller
- Expose `get_failed_write_count()` so operators can detect dropped records after a drive
- Expose `reset_failed_write_count()` for test isolation (`setUp()` only)
- Provide `build_lane_comparison_report` to aggregate per-lane metrics (count,
  duration, token volumes) from the sink for retrospective cost comparison

## Entry Points

- `scripts/agent-health/agent_telemetry.py` — emitter module
  - `emit_agent_telemetry(record: dict, *, sink_path: Path) -> None` — appends one record
  - `get_failed_write_count() -> int` — returns failed-write count since last reset
  - `reset_failed_write_count() -> None` — resets counter to 0 (test isolation only)
- `scripts/agent-health/generate_health_report.py` — report module
  - `build_lane_comparison_report(sink_path: Path) -> dict` — per-lane aggregate report
  - CLI: `python generate_health_report.py [--telemetry PATH] [--feedback PATH] [--agent AGENT_ID] [--format markdown|json]`
  (`--telemetry` / `--feedback` default to the declared stream and sink)
- `templates/skills/agent-telemetry/scripts/emit_event.py` — supervisor-event emitter (see above)
- declared `operational_telemetry_stream` — telemetry sink (JSONL, one record per line, append-only)

## JSONL Record Schema

Each line in the sink is a JSON object. The emitter adds `ts` automatically when the
caller omits it. All other fields are the caller's responsibility.

| Field | Type | Required | Description |
|---|---|---|---|
| `ts` | string (ISO-8601 UTC) | Auto-added | UTC timestamp injected by the emitter when absent from the caller-supplied dict. |
| `lane` | string | Yes | Pipeline lane tag (e.g. `"fast"`, `"heavy"`). Groups records in the lane comparison report. |
| `agent` | string | Yes | Agent identifier (e.g. `"python-coder"`, `"test-writer"`). Must match the registered agent id. |
| `duration_ms` | integer | Yes | Wall-clock invocation duration in milliseconds. Measured and supplied by the caller. |
| `tokens_in` | integer | Yes | Input (prompt) tokens consumed. Measured and supplied by the caller. |
| `tokens_out` | integer | Yes | Output tokens generated. Measured and supplied by the caller. |
| `cache_read_tokens` | integer | Yes | Tokens served from the prompt-cache. Measured and supplied by the caller. |
| `unit_id` | string | No | Ticket or AC identifier (e.g. `"BO-2400d-1"`). Written through unchanged when present. |

Additional caller-supplied keys are written to the JSONL line without modification.

## Failure Behavior

Telemetry emission is **fail-loud-not-fatal**. When `emit_agent_telemetry` catches an
`OSError` (for example: the sink path is a directory, the filesystem is full, or write
permission is denied):

1. A `WARNING` is logged via the module-level logger with the sink path and exception message.
2. The module-level `_failed_write_count` counter is incremented by 1.
3. The exception is **not** re-raised — the calling harness continues normally.

After a drive, inspect `get_failed_write_count()` to detect dropped records. A non-zero
value means the sink was unreachable for some invocations. The pre-drive sink-reachability
probe in `CLAUDE.md` (§ "Feedback sink reachable") provides a read-only pre-flight check
of the declared stream.

## Cross-links

- [Reference: Build Telemetry Record Schema and Lane Report](../../reference/build-telemetry.md) —
  full field-level reference for the JSONL schema and all public API parameters
- [How to generate and read the build-lane comparison report](../../how-to/compare-build-lanes.md) —
  step-by-step usage guide for `build_lane_comparison_report`
- `scripts/agent-health/agent_telemetry.py` — emitter, counter, and reset implementation
- `scripts/agent-health/generate_health_report.py` — lane comparison report and
  per-agent quality table (invocations, success rate, top failure archetypes)
