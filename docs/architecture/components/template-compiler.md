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

## AC Store Script Deployment

The `build_ac_store_scripts` phase (AC BP-900a-1) deploys the following 13 files from `scripts/ac_store/` to `{consumer}/.leafcutter/scripts/ac_store/`:

- `ac_prioritizer.py` — ranks unimplemented ACs by priority
- `generate_ticket_from_ac.py` — scaffolds a ticket file from an AC store entry
- `scan_ac_store.py` — scans the AC YAML store for entries
- `mark_ac_done.py` — marks an AC as implemented in the store
- `validate_ac_schema.py` — validates AC YAML against schema
- `ac_triage.py` — fast triage agent for /plan-feature workflow
- `create_ac_workflow.py` — creates AC workflow scaffolds
- `cross_reference_audit.py` — audits cross-references between ACs
- `backfill_readiness.py` — checks readiness for AC backfill
- `ac_parent_id.py` — resolves parent AC IDs
- `scan_ac_orphans.py` — finds ACs without parent linkage
- `fix_ac_orphans.py` — repairs orphaned AC entries
- `__init__.py` — makes the directory a valid Python package

Each deployed file is byte-identical to its source (no template compilation). The phase runs in `internal_phases` so output goes into `.leafcutter/scripts/ac_store/` under the consumer project's output root.

The `__init__.py` is included in the deployed directory, making `scripts/ac_store/` a valid Python package.

## AC Store Script Importability (BP-900a-3)

After deployment, a directory shim is installed by `install_shims()` in `build_helpers.py`:

```
{consumer}/scripts/ac_store  →  {consumer}/.leafcutter/scripts/ac_store/
```

This shim means that any process running from `{consumer}/` can add `scripts/ac_store` to `sys.path` and import `ac_prioritizer`, `generate_ticket_from_ac`, and `scan_ac_store` without error. Agent templates (e.g. `build-ac.md`) and skills (e.g. `ac-scanner/SKILL.md`) rely on this importability contract.
