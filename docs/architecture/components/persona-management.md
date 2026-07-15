---
title: "Persona Management — Persona Definitions & Targeting"
description: "Persona definitions, AC targeting by persona, and persona knowledge-graph queries."
flight_level: L3-Component
status: active
type: reference
created: 2026-07-10
last_updated: 2026-07-10
components:
  - persona_management
---

# Persona Management

## Overview

Persona Management covers the definition of product personas, the targeting of acceptance criteria by persona, and persona-scoped queries against the knowledge graph. It lets product work be framed and filtered by who it serves, so ACs and value propositions can be traced to the personas they benefit.

## Responsibilities

- Define and maintain persona records
- Associate acceptance criteria with the personas they target
- Answer persona-scoped queries over the knowledge graph (which ACs / value serve persona X)

## Entry Points

- `docs/acceptance-criteria/persona-management/` — the AC namespace defining this component's behavior (PER-prefixed ACs)

## Integration

Persona Management provides the persona axis consumed by product-ownership authoring and stakeholder delivery. Its behavior is currently specified by its acceptance criteria; entry-point code paths will be added here as the capability is implemented.
