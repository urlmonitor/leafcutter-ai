---
title: "Agent Telemetry — Per-Invocation Cost and Time Tracking"
description: "Per-invocation metric emitter and lane comparison reporter. Appends structured JSONL records to the telemetry sink after each agent call, exposing duration, token volumes, and cache-hit counts for fast-lane vs heavy-pipeline cost comparison."
flight_level: L3-Component
status: active
type: reference
created: 2026-06-08
last_updated: 2026-07-22
components:
  - agent_telemetry
---

# Agent Telemetry

## Overview

Agent Telemetry is a per-invocation JSONL emit module. After each phase-agent call
completes, the calling harness (or the phase agent itself) invokes
`emit_agent_telemetry` to append one structured record to
`debugging/logs/agent_telemetry.jsonl`. Records carry the invocation's lane tag,
agent identifier, wall-clock duration, and token counts (input, output, and
cache-read). A companion report function (`build_lane_comparison_report`) reads the
sink and returns per-lane aggregates for the fast-lane vs heavy-pipeline comparison.

There is no separate event-based emission path. The earlier `emit_event.py` entry
point no longer exists; all telemetry flows through `scripts/agent-health/agent_telemetry.py`.

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
- `debugging/logs/agent_telemetry.jsonl` — telemetry sink (JSONL, one record per line, append-only)

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
probe in `CLAUDE.md` (§ "Feedback sink reachable") provides a pre-flight check.

## Cross-links

- [Reference: Build Telemetry Record Schema and Lane Report](../../reference/build-telemetry.md) —
  full field-level reference for the JSONL schema and all public API parameters
- [How to generate and read the build-lane comparison report](../../how-to/compare-build-lanes.md) —
  step-by-step usage guide for `build_lane_comparison_report`
- `scripts/agent-health/agent_telemetry.py` — emitter, counter, and reset implementation
- `scripts/agent-health/generate_health_report.py` — lane comparison report and
  per-agent quality table (invocations, success rate, top failure archetypes)
