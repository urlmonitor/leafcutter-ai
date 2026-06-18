---
title: "Knowledge System — Cross-Session Learning Persistence"
description: "Knowledge harvesting and context file maintenance system that persists learnings across agent sessions for improved future-invocation quality."
flight_level: L3-Component
status: active
type: reference
created: 2026-06-08
last_updated: 2026-06-08
components:
  - knowledge_system
---

# Knowledge System

## Overview

The Knowledge System captures learnings discovered during ticket execution and routes them to persistent storage so future agent invocations benefit from prior experience. It is the implementation of the post-execution knowledge capture described in the Agent Knowledge System architecture.

## Responsibilities

- Harvest learnings from agent sign-off sessions via `harvest_learnings.py`
- Maintain context files that agents receive at invocation time
- Route new learnings to the appropriate knowledge surface

## Entry Points

- `scripts/knowledge/harvest_learnings.py` — learning harvester
- `scripts/knowledge/context_file_maintenance.py` — context file updater
- `scripts/knowledge/init_component_readme.py` — component README seeder

## Integration

The signoff skill §7 Knowledge Capture Step invokes the `route-learning` and `capture-learning` skills, which ultimately persist entries that `harvest_learnings.py` consolidates across sessions.
