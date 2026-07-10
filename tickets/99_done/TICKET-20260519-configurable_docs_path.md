---
title: "Make docs directory path configurable in skills_config.json"
status: done
components:
  - build_pipeline
created: 2026-05-19
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
---

# Make docs directory path configurable in skills_config.json

## Actor / Goal

In order to support projects where documentation lives somewhere other than `docs/`,
we need the docs directory path to be configurable in skills_config.json so that
build.py, commit guardian scripts, and doc compliance tooling resolve the correct location.

## Context

Multiple scripts and agents have a hardcoded assumption that documentation lives at `docs/`.
The paths config in `leafcutter/config/paths.json` defines `docs.root` as `docs/` but
scripts that reference documentation directories (commit guardian checks, doc compliance
generator, build phases that scaffold docs) often use the literal string rather than
reading from config. If a project keeps docs at `documentation/`, `wiki/`, or a monorepo
subpath like `packages/core/docs/`, the tooling breaks silently or writes to the wrong place.

## Acceptance Criteria

```gherkin
Given skills_config.json has a custom docs_root value (e.g. "documentation/")
When build.py runs
Then all output paths for docs-related scaffolding use the configured value

Given a custom docs_root is configured
When commit guardian scripts check for documentation
Then they resolve paths relative to the configured docs_root

Given no docs_root is configured in skills_config.json
When any script resolves the docs path
Then it falls back to "docs/" (backward compatible)
```

## Implementation Tasks

- [ ] Add `docs_root` field to skills_config.json schema (with default `docs/`)
- [ ] Update `leafcutter/config/paths.json` to derive `docs.*` paths from the configured root
- [ ] Audit build_phases.py for hardcoded `docs/` references and replace with config lookup
- [ ] Audit commit_guardian scripts for hardcoded `docs/` paths
- [ ] Audit doc_compliance scripts for hardcoded `docs/` paths
- [ ] Update agent templates that reference `docs/` to use the `paths.docs.root` variable
- [ ] Add config schema validation for the new field
- [ ] Tests: build with custom docs_root, verify all outputs land in the right place

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Default value preserves existing behaviour; only explicit config changes the path.
