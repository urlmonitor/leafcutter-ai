---
title: "Skill Registry — Available Skills Catalog"
description: "Registry of all available skills with metadata on usage context, allowed tools, and configuration constraints for agent invocation."
flight_level: L3-Component
status: active
type: reference
created: 2026-06-08
last_updated: 2026-06-08
components:
  - skill_registry
---

# Skill Registry

## Overview

The Skill Registry (`config/skill_registry.json`) catalogs all skills available to agents at invocation time. Skills provide reusable, focused behavior blocks (e.g. `signoff`, `building-epics`, `route-learning`) that agents load via the Skill tool.

## Key Fields

- `id` — unique skill identifier
- `description` — human-readable purpose statement
- `allowed_tools` — list of tools the skill permits
- `trigger_conditions` — when the skill should be invoked

## Usage

- Agents reference skills in their `## Your Available Skills` table
- The build pipeline compiles skills from `templates/skills/` into `.claude/skills/`
- `config/skill_registry.json` is the source of truth for skill availability

## Entry Points

- `config/skill_registry.json` — the registry file
- `templates/skills/` — skill template source directory
- `.claude/skills/` — compiled skill deployment directory
