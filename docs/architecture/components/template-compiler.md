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

## CI and Fresh-Clone Test Requirements

The full test suite requires the build step to run **before** `pytest` on any
fresh checkout (including CI). The build step's `install_shims()` phase creates
symlinks at `scripts/commit_guardian/`, `scripts/doc_compliance/`, and
`scripts/feedback/` pointing into `.leafcutter/scripts/`. Test files add those
`scripts/<name>/` paths to `sys.path` at import time; without the shims, ~36
tests fail at import on a clean checkout.

The documented CI test command is:

```bash
# 1. Install development dependencies
pip install -r requirements-dev.txt

# 2. Run the build step to deploy shims and artifacts
python scripts/build.py --target-dir .

# 3. Run the full test suite
python -m pytest tests/ unit_tests/ -x -q
```

See [ADR-016](../adrs/ADR-016-ci-fresh-clone-test-dependencies.md) for the
full decision record on this design.
