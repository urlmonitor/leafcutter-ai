---
title: "Resolve package audit gaps: undeployed hooks, uninstalled partials, stale domain entries, and orphan commands"
status: done
components:
  - commit_guardian
  - build_pipeline
  - agent_registry
created: 2026-05-22
depends_on: []
priority: medium
tags:
  - package-hygiene
  - build-pipeline
  - registry-cleanup
last_updated: 2026-05-22
files_touched:
  - templates/commit-guardian/commit_guardian.json
  - templates/commit-guardian/check_glossary_coverage.py
  - templates/commit-guardian/check_mermaid_drift.py
  - templates/commit-guardian/check_mermaid_parent_link.py
  - templates/commit-guardian/check_output_drift.py
  - templates/commit-guardian/check_placeholder_defaults.py
  - templates/commit-guardian/check_doc_types_agents.py
  - templates/commit-guardian/check_schema_ddl_drift.py
  - templates/commit-guardian/regenerate_roadmap_mirror.py
  - templates/agents/_post_edit_verification.md
  - templates/agents/_signoff_block.md
  - config/agent_registry.json
  - config/skill_registry.json
  - scripts/build.py
agents:
  architect-review: not_needed
  python-coder: needed
  test-writer: not_needed
  test-runner: needed
  sql-coder: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
requires_diagram: false
requires_adr: false
---

# Resolve package audit gaps: undeployed hooks, uninstalled partials, stale domain entries, and orphan commands

## Actor / Goal

As the leafcutter maintainer, I need to resolve all items flagged by the package
audit so that `build.py` produces a clean, complete deployment with no leftover
project-local artifacts, no uninstalled partials, and no stale domain-specific
entries polluting the registries.

## Problem Statement

Running a package audit surfaces four categories of issues:

### 1. Commit Guardian Hooks reported as "Left Over" (project-local, not leafcutter)

These 5 hooks exist in `templates/scripts/commit_guardian/` AND are registered in
`hooks_manifest` of `commit_guardian.json`, but are **missing** from the canonical
`templates/commit-guardian/` directory. Build.py may be sourcing from the wrong
template location, or the two template directories are out of sync:

| Hook | Status |
|------|--------|
| `check_glossary_coverage` | In `templates/scripts/commit_guardian/` + manifest, missing from `templates/commit-guardian/` |
| `check_mermaid_drift` | Same |
| `check_mermaid_parent_link` | Same |
| `check_output_drift` | Same |
| `check_placeholder_defaults` | Same |

**Root cause hypothesis**: These hooks were added to `templates/scripts/commit_guardian/`
(the build output template) and the `hooks_manifest`, but never copied to
`templates/commit-guardian/` (the source-of-truth template directory). The package
audit script likely checks `templates/commit-guardian/` to determine what's "in the
package".

### 2. In leafcutter but NOT installed (hooks + partials)

These items exist somewhere in the leafcutter repo but don't get deployed by `build.py`:

| Item | Location | Issue |
|------|----------|-------|
| `check_commit_scope` | `templates/commit-guardian/` + manifest | Should be deploying — investigate why audit says "not installed" |
| `check_doc_types_agents` | `scripts/commit_guardian/` only | Missing from both template dirs AND hooks_manifest |
| `check_roadmap_schema` | In manifest, in `templates/scripts/` | Missing from `templates/commit-guardian/` |
| `check_schema_ddl_drift` | `scripts/commit_guardian/` only | Missing from both template dirs AND hooks_manifest |
| `_post_edit_verification.md` | `templates/agents/` | Agent partial — needs explicit install step or documentation that it's template-only |
| `_signoff_block.md` | `templates/agents/` | Agent partial — same as above |

### 3. Orphan commands (project-local, not in leafcutter)

| Command | Notes |
|---------|-------|
| `/finish-ticket-phase` | No matching file found anywhere in the repo — ghost reference from a prior consumer |
| `/refine-next-ticket` | Same — no file found; functionally replaced by `/pick-next-ticket` |

### 4. Stale domain entries in leafcutter registries (16 total from bybit-trader)

These entries have `domain: bybit-trader` and `portable: false` — they belong in the
consumer project, not in the leafcutter package registries:

**Agents (5 clearly domain-specific):**
- `database-agent`
- `prod-deploy`
- `reporting-agent`
- `strategy-builder`
- `rollback-agent`

**Agents marked portable but with bybit-trader domain (review):**
- `adr-author` (domain=bybit-trader, portable=True)
- `explanation-author` (domain=bybit-trader, portable=True)
- `how-to-author` (domain=bybit-trader, portable=True)

**Non-portable domain agents (also remove):**
- `architect-review-deep`
- `architecture-author`
- `architecture-diagram-author`
- `conflict-resolver-deep`
- `onboarding-agent`

**Skills (9 domain-specific, remove from registry):**
- `hypertable-build`
- `postgres`
- `schema-check`
- `script`
- `sql-test`
- `strategy-builder`
- `strategy-check`
- `trade-analysis`
- `create-ticket` (domain=bybit-trader skill entry — conflicts with the portable create-ticket agent)

**Skills with empty template_path (portable but possibly stale — verify):**
- `agent-telemetry`
- `fix-file-output`
- `impact-analysis`
- `security-scanner`
- `write-c4-diagram`
- `roadmap-steward`

## Acceptance Criteria

1. **Hooks sync**: All hooks in `hooks_manifest` have their `.py` file present in
   `templates/commit-guardian/` (the source-of-truth template dir). The duplicate
   `templates/scripts/commit_guardian/` tree is either removed or documented as the
   build output location (not source of truth).

2. **Missing hooks decision**: For `check_doc_types_agents` and `check_schema_ddl_drift`:
   either add to manifest + templates (if they're portable) or remove from
   `scripts/commit_guardian/` (if they're consumer-specific).

3. **Partials documented**: `_post_edit_verification.md` and `_signoff_block.md` are
   either registered in a partials manifest that the audit recognizes, or the audit
   script is updated to ignore `_`-prefixed files as intentional partials.

4. **Orphan commands removed**: No references to `/finish-ticket-phase` or
   `/refine-next-ticket` remain in any consumer-facing config.

5. **Domain entries purged**: All `domain: bybit-trader` entries removed from
   `config/agent_registry.json` and `config/skill_registry.json`. Portable agents
   that were incorrectly tagged with a domain (`adr-author`, `explanation-author`,
   `how-to-author`) have their domain cleared to `null`.

6. **Stale portable skills resolved**: Skills with `portable: true` but empty
   `template_path` are either given a valid template path or removed if truly unused.

7. **Clean audit**: Running `package-audit` after all fixes reports zero "Left Over",
   zero "Not installed", and zero stale domain entries.

## Out of Scope

- Rewriting build.py's hook deployment logic (just sync the templates)
- Adding new hooks or features
- Changing hook behavior

## Implementation Notes

- The two template directories (`templates/commit-guardian/` and
  `templates/scripts/commit_guardian/`) appear to be an artifact of the build pipeline:
  one is source, one is the "deployed output" template. Clarify which is which before
  syncing. The `templates/commit-guardian/` dir has a README.md, INTEGRATION.md, and
  hooks_docs.md suggesting it's the canonical source.
- `regenerate_roadmap_mirror.py` is in `templates/commit-guardian/` but NOT in
  `templates/scripts/commit_guardian/` — add it there if the scripts dir is the
  build output, or delete it from there if commit-guardian is the only source.
- The `create-ticket` skill entry with `domain=bybit-trader` conflicts with the
  portable `create-ticket` agent — likely a consumer override that leaked into the
  package registry. Remove the skill entry; the agent handles this function.

## Sign-offs

- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
