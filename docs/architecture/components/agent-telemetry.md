---
title: "Agent Telemetry — Supervisor Event Tracking"
description: "Event emission and tracking system for recording supervisor dispatch, agent sign-offs, retries, and failure events to JSONL logs for retrospective analysis."
flight_level: L3-Component
status: active
type: reference
created: 2026-06-08
last_updated: 2026-06-08
components:
  - agent_telemetry
---

# Agent Telemetry

## Overview

Agent Telemetry provides structured event emission for the supervisory layer. Events like `agent_start`, `agent_signoff`, `agent_retry`, `agent_failure`, and `epic_complete` are emitted to `debugging/logs/agent_telemetry.jsonl` before and after each phase agent runs.

## Responsibilities

- Emit structured events at dispatch, sign-off, retry, and failure points
- Persist events to a sink reachable before the epic drive begins
- Enable retrospective analysis of agent quality metrics

## Entry Points

- `.claude/skills/agent-telemetry/scripts/emit_event.py` — event emission script
- `debugging/logs/agent_telemetry.jsonl` — event log sink

## Failure Behavior

Telemetry emission is always non-blocking. A failed emit (non-zero exit) logs a warning and proceeds. The sink reachability pre-flight (building-epics §1.0) validates the sink is writable before any epic drive begins.
