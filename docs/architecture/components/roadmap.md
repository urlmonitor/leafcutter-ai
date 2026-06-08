---
title: "Roadmap — Phase-Based Outcome Tracking"
description: "Phase-based roadmap that tracks current outcomes, exit criteria, and the tickets advancing each outcome toward the stable MVP target."
flight_level: L3-Component
status: active
type: reference
created: 2026-06-08
last_updated: 2026-06-08
components:
  - roadmap
---

# Roadmap

## Overview

The Roadmap component provides a structured JSON-based roadmap (`docs/roadmap.json`) that defines the current development phase, its target outcome, exit criteria, and the tickets contributing to that outcome.

## Responsibilities

- Track the current phase (e.g. `phase_1`) and its human-readable outcome
- List tickets advancing the current outcome with their status
- Support programmatic querying via `roadmap_query.py`
- Enforce schema compliance via `check-roadmap-schema` pre-commit hook

## Entry Points

- `docs/roadmap.json` — the roadmap data file
- `scripts/roadmap_query.py` — query and reporting utility
- `scripts/commit_guardian/check_roadmap_schema.py` — schema enforcement hook

## Schema

The roadmap JSON is validated against `config/roadmap.schema.json`. The schema enforces required fields and valid phase/status values.
