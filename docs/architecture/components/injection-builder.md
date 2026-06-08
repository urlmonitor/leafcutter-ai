---
title: "Injection Builder — Agent Context Assembly"
description: "Context injection payload assembler that delivers structured knowledge to agents at invocation time via the 11-channel agent knowledge plane."
flight_level: L3-Component
status: active
type: reference
created: 2026-06-08
last_updated: 2026-06-08
components:
  - injection_builder
---

# Injection Builder

## Overview

The Injection Builder assembles the context payloads that agents receive when they are invoked. It operationalizes the Agent Knowledge Plane by gathering data from all 11 channels (ticket body, skills, prior comments, registry state, etc.) and packaging them for agent consumption.

## Responsibilities

- Gather context from all knowledge plane channels
- Assemble a structured injection payload for each agent invocation
- Ensure agents receive the minimum context needed to execute their phase

## Entry Points

- `scripts/injection_builders.py` — payload assembly logic

## Integration

The injection builder is invoked by supervisors before spawning a phase agent. Its output forms the `input` parameter of the Agent tool call. The 11 knowledge plane channels are documented in `docs/architecture/agent_knowledge_plane.md`.
