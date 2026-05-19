---
title: "Schema-diff CI gate: fail on backwards-incompatible skills_config.schema.json change without breaking entry"
status: todo
components:
  - infrastructure
  - documentation_system
created: 2026-05-19
last_updated: 2026-05-19
depends_on:
  - 01_frontmatter_schema_extension.md
  - 02_release_script.md
priority: medium
phase: "Phase 2"
requires_diagram: false
requires_adr: false
files_touched:
  - leafcutter/config/skills_config.schema.json
  - .github/workflows/schema_diff.yml
agents:
  architect-review: needed
  python-coder: needed
  test-writer: needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  status-checker: not_needed
  sql-coder: not_needed
---

# 05: Schema-diff CI gate — fail on backwards-incompatible schema change without breaking entry

## Goal

In order to close the "silent omission" gap mechanically, we need a CI check that compares `leafcutter/config/skills_config.schema.json` against the previous `v*` tag and fails when a backwards-incompatible change (removed key, new required key, type narrowing) is present in the PR without a corresponding `breaking: true` changelog entry — so that the `breaking` flag is enforced at merge time, not just at write time.

## Context

This is a **Phase 2** ticket and the primary mechanical mitigation for the residual risk documented in the Master_Plan: a developer who introduces a genuinely breaking schema change but omits `breaking: true` from their changelog entry will produce an incorrect MINOR or PATCH bump. Sub-ticket 01's `emit_entry.py` validation only catches entries that *declare* `breaking: true` without `migration_steps`; it cannot catch silent omission. This gate catches the omission at CI time.

**Backwards-incompatible changes** (the set this gate checks):
1. A key present in the previous-tag schema is absent in the PR schema (removed key).
2. A key that was previously `"required": false` or absent from `"required"` is now in `"required"` (new required key).
3. A key's `"type"` is narrowed (e.g. `["string", "null"]` → `"string"`).

Type *widening* (adding null to a type union), adding optional keys, and adding new enum values are NOT breaking — the gate ignores them.

**Extraction dependency**: like sub-ticket 03, this CI gate lives in the upstream repo's `.github/workflows/`. The script that does the comparison (`scripts/release/check_schema_diff.py` or similar) can be authored in the embedded copy and tested independently.

Cross-links:
- `leafcutter/config/skills_config.schema.json` — the schema being compared.
- Sub-ticket 01 (`01_frontmatter_schema_extension.md`) — provides the `breaking` field that the gate checks for.
- Sub-ticket 02 (`02_release_script.md`) — establishes the `v*` tag convention the gate compares against.
- Sub-ticket 04 (`04_build_halt_guard.md`, Phase 2) — complementary consumer-side gate; together they close the silent-omission gap from both sides.

`architect-review` is requested because the definition of "backwards-incompatible" for JSON Schema is subtle (draft-07 semantics, `additionalProperties`, `oneOf`/`anyOf` interactions) and the gate's false-positive rate depends on getting this right.

## Acceptance Criteria

```gherkin
Given a PR that removes a key from skills_config.schema.json and has no breaking=true changelog entry
When the schema-diff CI check runs
Then the check exits non-zero with a message naming the removed key and the missing breaking entry

Given a PR that removes a key from skills_config.schema.json AND has a breaking=true changelog entry with migration_steps
When the schema-diff CI check runs
Then the check exits 0 (breaking change is properly declared)

Given a PR that adds an optional key to skills_config.schema.json (non-breaking widening)
When the schema-diff CI check runs
Then the check exits 0 (no breaking change; no breaking entry required)

Given a PR that makes a previously-optional key required
When the schema-diff CI check runs
Then the check exits non-zero with a message identifying the newly-required key
```

## Sign-offs

- [ ] architect-review
- [ ] python-coder
- [ ] test-writer
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

- [ ] Author `leafcutter/scripts/release/check_schema_diff.py`:
  - Accepts `--previous-tag` and `--schema-path` (defaults to `leafcutter/config/skills_config.schema.json`)
  - Fetches the previous-tag version of the schema via `git show <tag>:<path>`
  - Compares: removed keys, newly-required keys, type narrowings
  - Reads `changelogs/` for entries committed after previous tag; checks any has `breaking: true`
  - Exit 0 if no breaking change found OR if breaking change found AND a `breaking: true` entry exists
  - Exit 1 with structured message if breaking change found AND no `breaking: true` entry
- [ ] Author `.github/workflows/schema_diff.yml` (or `leafcutter/.github/workflows/schema_diff.yml` pre-extraction):
  - Trigger: `on: pull_request: branches: [main]`
  - Run `check_schema_diff.py --previous-tag $(git describe --match "v*" --abbrev=0)`
- [ ] Unit tests: all four Gherkin scenarios; cover removed-key, new-required-key, type-narrowing; cover false-positive guard for additive changes
- [ ] Stdlib-only script (no external JSON Schema library)

## Risk & Safety

- Touches money? No.
- Touches data? Read-only except for the CI workflow file. The script reads git history and schema files.
- Reversibility? The CI check is a gate — it blocks merges. If it produces false positives, it can be temporarily bypassed via `[skip ci]` commit message convention while a fix is authored.
