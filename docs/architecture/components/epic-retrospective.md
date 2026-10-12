---
title: "Epic Retrospective — Post-Epic Fact Extraction"
description: "Post-epic fact extraction subsystem. Reads a completed epic's ticket frontmatter, git history, and comment stream to produce a structured, machine-readable facts blob that grounds the retrospective-agent's narrative in measured evidence rather than recollection."
flight_level: L3-Component
status: active
type: reference
created: 2026-08-13
last_updated: 2026-10-12
components:
  - epic_retrospective
---

# Epic Retrospective

## Overview

Epic Retrospective is the **read-side** of the epic lifecycle. After an epic
completes, `extract_epic_facts.py` walks the epic's ticket folder and emits a
single structured JSON blob describing what measurably happened: how many
tickets there were, how each phase agent fared per ticket, how many commits
landed and over what date range, and how many blocker and handoff comments were
raised.

The `retrospective-agent` consumes that blob (step 2b of its template) so the
retrospective narrative is anchored to counted facts. Without it the agent would
be summarising from prose recollection — the failure mode the component exists
to prevent.

This component is a **consumer** of the telemetry sink, not its owner. The sink
itself and the per-invocation emitter belong to `agent_telemetry`; the
epic-scoped aggregation and the ticket/git joins belong here.

## Responsibilities

- Enumerate the ticket files in an epic folder and count total vs. completed
- Parse each ticket's `agents` frontmatter map into per-agent sign-off status
  counts (`signed_off`, `needed`, `not_needed`, `failed`)
- Derive git commit count and first/last commit dates scoped to the epic
- Count `blocker` and `handoff` comments across the epic's tickets
- Optionally join the telemetry sink, filtered to the epic, into per-event-type
  counts
- Emit the whole result as one JSON object on stdout for a downstream agent

## Entry Points

- `scripts/retrospective/extract_epic_facts.py` — fact extractor
  - `extract_facts(epic_path: Path, telemetry_path: Path | None = None) -> dict`
    — the full facts blob
  - CLI: `python extract_epic_facts.py <epic_folder_path> [--telemetry PATH] [--format json]`
- `templates/agents/retrospective-agent.md` — the sole consumer; invokes the CLI
  at step 2b and renders the blob into the Epic Facts table

## Output Shape

`extract_facts` returns a single dict. Field-level summary:

| Field | Type | Description |
|---|---|---|
| `epic_name` | string | Folder name of the epic. |
| `epic_path` | string | Absolute path to the epic folder as supplied. |
| `extracted_at` | string (ISO-8601 UTC) | Extraction timestamp. |
| `ticket_count` | integer | Total ticket files found in the epic folder. |
| `completed_ticket_count` | integer | Tickets whose status is terminal. |
| `phase_agent_counts` | object | Per-agent map of sign-off status to count. |
| `git_commit_count` | integer | Commits attributed to the epic. |
| `git_first_commit_date` | string or null | Earliest commit date (short form). |
| `git_last_commit_date` | string or null | Latest commit date (short form). |
| `blocker_comment_count` | integer | Count of blocker-status comments. |
| `handoff_comment_count` | integer | Count of handoff-status comments. |
| `telemetry_events` | object | Event-type to count, filtered to this epic. Always present; `{}` when no telemetry is supplied or nothing matches. |

## Data Sources

The extractor joins four independent sources. Only the first two are load-bearing
for the current output:

1. **Ticket frontmatter** (PyYAML) — the `agents` map per ticket. This is the
   richest signal and drives `phase_agent_counts`.
2. **Ticket comment stream** — scanned for blocker and handoff status markers.
3. **Git log** (subprocess) — commit count and date range.
4. **Telemetry stream** (JSONL) — without `--telemetry`, the
   `operational_telemetry_stream` declared in the install's
   `config/knowledge_sink.json`, read through `sink_resolution.read_usable_stream`
   ([ADR-069](../adrs/ADR-069-durable-log-root-for-workspaces.md)). The extractor is a
   reader: it prints `read N records from <path>` on stderr, and with no usable
   declaration it prints an ERROR and exits 1 without printing facts. An explicit
   `--telemetry` is used as given.

## Known Limitations

- **The telemetry join matches only supervisor events.** `_read_telemetry` filters
  on `ticket_path` (what `emit_event.py` writes) or the older `ticket` field, and
  buckets by `event_type`. Records from `agent_telemetry`'s per-invocation cost
  emitter carry no ticket path, so they are never counted. Closing that requires a
  schema agreement with `agent_telemetry` on a ticket/unit identifier.

## Cross-links

- [Agent Telemetry](agent-telemetry.md) — owns the telemetry sink and the
  per-invocation emitter this component optionally reads
- [Feedback Collector](feedback-collector.md) — the other post-hoc quality
  signal source the retrospective-agent consults
- `templates/agents/retrospective-agent.md` — the consuming agent
