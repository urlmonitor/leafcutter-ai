---
title: "Feedback Collector — Structured Agent Quality Signals"
description: "Structured feedback collection system that aggregates agent quality signals into JSONL logs for retrospective analysis and continuous improvement."
flight_level: L3-Component
status: active
type: reference
created: 2026-06-08
last_updated: 2026-06-08
components:
  - feedback_collector
---

# Feedback Collector

## Overview

The Feedback Collector captures structured quality signals from phase agents and supervisors via the `submit_feedback.py` script. Each signal records a category, tags, and a one-sentence note, keyed to a ticket path and agent phase.

## Responsibilities

- Accept feedback submissions from phase agents during sign-off
- Assign unique `feedback_id` values (e.g. `fb_2026-06-08_a1b2c3d4`)
- Persist entries to `debugging/logs/feedback.jsonl`
- Support aggregation and retrospective queries via `aggregate.py`

## Entry Points

- `scripts/feedback/submit_feedback.py` — main submission script
- `scripts/feedback/aggregate.py` — aggregation and reporting
- `scripts/feedback/list_tags.py` — tag discovery utility
- `scripts/feedback/link_feedback.py` — links feedback entries to tickets

## Integration

Every phase agent calls `submit_feedback.py` before appending their sign-off comment. The returned `feedback_id` appears as the first line of the comment body per the signoff skill §2a protocol.
