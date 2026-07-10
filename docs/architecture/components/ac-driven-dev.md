---
title: "AC-Driven Development — AC-First Build Pipeline"
description: "The AC-driven development pipeline: /plan-feature authoring, /build-ac selection and ticket generation, and the AC-first build loop that treats the AC store as the authoritative backlog."
flight_level: L3-Component
status: active
type: reference
created: 2026-07-10
last_updated: 2026-07-10
components:
  - ac_driven_dev
---

# AC-Driven Development

## Overview

AC-Driven Development is the pipeline that treats the acceptance-criteria store as the authoritative backlog. Feature intent is first authored as ACs via `/plan-feature` (PO → BA → IT-PO), then `/build-ac` selects the next highest-priority ready AC, generates a fully-wired ticket from it, and hands off to the build loop. This replaces ad-hoc ticket creation with an AC-first flow where every unit of work traces back to a criterion in the store (per ADR-010).

## Responsibilities

- Author ACs from a feature request through the PO/BA/IT-PO stages (`/plan-feature`)
- Rank ready ACs and generate implementable tickets with back-references (`/build-ac`)
- Maintain the AC store as the single authoritative backlog for what ships next

## Entry Points

- `templates/workflows-js/plan-feature.js` — AC authoring workflow
- `templates/skills/build-ac/SKILL.md` — AC selection and ticket generation

## Integration

AC-Driven Development produces the tickets that Build Orchestration dispatches. It reads and writes the `ac_store` component (`docs/acceptance-criteria/`) as its backing store. See ADR-010 (AC store as authoritative backlog) for the design rationale.
