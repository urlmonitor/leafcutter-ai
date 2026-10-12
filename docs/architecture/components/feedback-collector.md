---
title: "Feedback Collector — Structured Agent Quality Signals"
description: "Structured feedback collection system that aggregates agent quality signals into JSONL logs for retrospective analysis and continuous improvement."
flight_level: L3-Component
status: active
type: reference
created: 2026-06-08
last_updated: 2026-10-12
components:
  - feedback_collector
related_docs:
  - docs/architecture/feedback-lifecycle.md
  - docs/architecture/adrs/ADR-069-durable-log-root-for-workspaces.md
  - docs/known-issues/feedback-collector.md
---

# Feedback Collector

## Overview

The Feedback Collector captures structured quality signals from phase agents and supervisors via the `submit_feedback.py` script. Each signal records a category, tags, and a one-sentence note, keyed to a ticket path and agent phase.

## Responsibilities

- Accept feedback submissions from phase agents during sign-off
- Assign unique `feedback_id` values (e.g. `fb_2026-06-08_a1b2c3d4`)
- Persist entries to the install's declared `feedback_sink` (see below)
- Support aggregation and retrospective queries via `aggregate.py`

## Where entries are written and read

The sink is the `feedback_sink` value in the build-time declaration
`<output_root>/config/knowledge_sink.json`, i.e. `<operational_log_root>/feedback.jsonl`.
Every worktree of an install shares it, and it outlives the worktree
([ADR-069](../adrs/ADR-069-durable-log-root-for-workspaces.md)). How the root is chosen,
the location query, and the refusal wording are described in
[Feedback Lifecycle — Where every log is kept](../feedback-lifecycle.md#where-every-log-is-kept--one-declared-log-root-adr-069).

| Script | Role | Without an explicit path |
|---|---|---|
| `submit_feedback.py` | writer | Appends to `feedback_sink` (via `feedback_sink.py`). If the declaration is unusable, prints one `destination could not be written` line, exits 1, and creates nothing. |
| `emit_hook_finding.py` | writer (through `submit_feedback.py`) | Same as `submit_feedback.py`. |
| `aggregate.py`, `list_tags.py`, `link_feedback.py`, `resolve_feedback.py`, `trend_report.py`, `generate_health_report.py` | readers | Read `feedback_sink` (and `operational_telemetry_stream` where used) through `feedback_reader.py`. Print `read N records from <path>` on stderr. Exit 1 with no stdout when nothing is declared. |

An explicit `--jsonl` is still honoured. `link_feedback.py` and `resolve_feedback.py` hold
the same exclusive lock as `submit_feedback.py` for the whole read-modify-write.
`feedback_categories.yaml` is still resolved separately, from the script's own
`.leafcutter/config/` (rule (a)).

## Entry Points

- `scripts/feedback/submit_feedback.py` — main submission script
- `scripts/feedback/feedback_sink.py` — resolves the declared sink or builds the refusal line
- `scripts/feedback/feedback_reader.py` — shared reader resolution and the `read N records` line
- `scripts/feedback/aggregate.py` — aggregation and reporting
- `scripts/feedback/list_tags.py` — tag discovery utility
- `scripts/feedback/link_feedback.py` — links feedback entries to tickets
- `.leafcutter/scripts/knowledge/sink_resolution.py --print-location feedback` — prints the sink without writing

## Integration

Every phase agent calls `submit_feedback.py` before appending their sign-off comment. The returned `feedback_id` appears as the first line of the comment body per the signoff skill §2a protocol. Shipped prompts no longer pass a `--jsonl` path of their own (INF-500d-4-vi).
