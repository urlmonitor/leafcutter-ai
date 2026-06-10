---
title: "Template Compiler — Build-Time Artifact Generation"
description: "Build-time template compilation system that transforms Jinja-style agent and skill templates into deployed artifacts during the leafcutter build phase."
flight_level: L3-Component
status: active
type: reference
created: 2026-06-08
last_updated: 2026-06-08
components:
  - template_compiler
---

# Template Compiler

## Overview

The Template Compiler transforms templates from `templates/agents/`, `templates/skills/`, and `templates/hooks/` into deployed artifacts in `.claude/agents/`, `.claude/skills/`, and `.claude/hooks/` respectively. It runs as part of the `build.py` build pipeline.

## Responsibilities

- Interpolate template variables with project-specific values
- Validate template outputs against schema constraints
- Stage compiled artifacts for the consumer project's `.claude/` directory

## Entry Points

- `scripts/template_compiler.py` — core compilation logic
- `scripts/build.py` — main build entry point
- `scripts/build_phases.py` — phase-by-phase build orchestration

## Integration

The `build-self.sh` script invokes the compiler for local development. Consumer installs run `python leafcutter-ai/scripts/build.py --target-dir .` to deploy compiled artifacts.
