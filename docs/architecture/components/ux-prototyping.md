---
title: "UX Prototyping — Component-Aware Mockups"
description: "The UX prototyping agent: component-aware static mockups, user validation gates, and design-to-implementation handoff."
flight_level: L3-Component
status: active
type: reference
created: 2026-07-10
last_updated: 2026-07-10
components:
  - ux_prototyping
---

# UX Prototyping

## Overview

UX Prototyping covers the agent class that produces component-aware static mockups ahead of implementation, gates them through explicit user validation, and hands the approved design off to the implementation agents. It exists so visual direction is agreed before frontend code is written, reducing rework at the coding phase.

## Responsibilities

- Produce component-aware static mockups from a feature or UI request
- Gate mockups through a user validation step before implementation begins
- Hand the approved design off to the frontend implementation flow

## Entry Points

- `docs/acceptance-criteria/ux-prototyping/` — the AC namespace defining this component's behavior (UXP-prefixed ACs)

## Integration

UX Prototyping feeds validated designs into the frontend implementation path (see the `frontend_coding` component). Its behavior is currently specified by its acceptance criteria; entry-point code paths will be added here as the agent is implemented.
