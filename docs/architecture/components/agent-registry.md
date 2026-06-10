---
title: "Agent Registry — Phase Agent Catalog"
description: "Central registry of all phase agents with is_ticket_phase flags, produces traits, and model tier assignments used by ticket-supervisor for dispatch and validation."
flight_level: L3-Component
status: active
type: reference
created: 2026-06-08
last_updated: 2026-06-08
components:
  - agent_registry
---

# Agent Registry

## Overview

The Agent Registry (`config/agent_registry.json`) is the authoritative catalog of all agents available to the leafcutter-ai harness. The ticket-supervisor reads it at dispatch time to validate agent names and load the `produces` trait for guardrail decisions.

## Key Fields

- `id` — unique agent identifier (matches the `agents:` map key in tickets)
- `is_ticket_phase` — if true, the agent may appear in a ticket's `agents:` map
- `produces` — trait that determines TDD guardrail applicability
- `model` — haiku, sonnet, or opus tier assignment

## Usage

- `ticket-supervisor` validates every `agents:` map key against this registry
- `check_agent_registry.py` pre-commit hook enforces registry consistency
- `generate_agent_cards.py` consumes the registry to produce agent documentation

## Entry Points

- `config/agent_registry.json` — the registry file
- `scripts/registry_validator.py` — validation utility
