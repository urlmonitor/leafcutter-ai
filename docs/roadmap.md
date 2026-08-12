---
title: Project Roadmap
type: reference
status: active
created: 2026-08-12
last_updated: 2026-08-12
components:
- infrastructure
description: Overview of Project Roadmap.
---
<!-- AUTO-GENERATED — do not edit by hand. Source: docs/roadmap.json -->
<!-- Regenerate manually: python portable-dev-workflow/scripts/commit_guardian/regenerate_roadmap_mirror.py --manual -->
<!-- Generated: 2026-08-12T10:37:09Z -->

# Project Roadmap

> **Source of truth**: `docs/roadmap.json`  
> To update the roadmap, edit `docs/roadmap.json` and commit — this file regenerates automatically.

## Current Focus

**Current Phase**: `phase_1`
**Current Outcome**: Stable MVP that installs into any project and helps the user build good software — portable, self-onboarding, and reliable enough to use across multiple repos.

## Phases

| Phase | Title | Status |
|-------|-------|--------|
| `phase_1` | Stable Portable MVP | **ACTIVE** ← current |
| `phase_acbuild_1_foundation` | AC-Driven Build v2 — Foundation & Read-Side | Planned |
| `phase_acbuild_2_cutover` | AC-Driven Build v2 — Thin Tickets & AC-as-Unit-of-Work (dogfooded) | Planned |
| `phase_acbuild_3_migration` | AC-Driven Build v2 — Consumer Migration & Legacy Removal | Planned |
| `phase_2` | Ecosystem Hardening | Planned |
| `phase_3` | Distribution and Community | Planned |

## Phase Details

### phase_1: Stable Portable MVP (Current)

**Status**: **ACTIVE**

A reliable package that installs into any project via build.py, self-onboards the user via interactive config, and produces correct agents/skills/hooks without manual fixup.

**Exit Criteria**:

- Clean install succeeds on a blank project with only skills_config.json present
- build.py --validate-only returns 0 with no template injection errors
- Consecutive builds produce zero git diff (idempotent)
- Self-hosting parity: leafcutter development uses its own compiled agents

### phase_acbuild_1_foundation: AC-Driven Build v2 — Foundation & Read-Side

**Status**: Planned

Make the AC store the single source of truth WITHOUT changing behaviour. Additive-only: optional deliverable-checklist and per-deliverable sign-off fields plus a per-AC schema_version in ac_store_schema.json; a productionised effective-prompt render tool; canonical-source path resolution; and universal agent/gate dual-read (store-or-ticket-body). All new gates run advisory/warn-mode behind a two-stage ac_unit_of_work flag ({emit:false, enforce:false}). Read-side lands before any write-side change so the build can never go green while verifying nothing.

**Exit Criteria**:

- New AC fields are OPTIONAL in ac_store_schema.json; schema_version present (default 1); whole-store validation passes on both legacy and new shapes
- render_effective_prompt.py productionised and in the build deploy-manifest; a fresh agent rendered purely from the store passes the comprehension test
- All phase agents and gates dual-read spec from the store with ticket-body fallback; enrichment / canonical-path / surface-to-craft / consistency gates run in warn mode
- No required CI gate references a new field; ac_unit_of_work flag introduced with a documented one-commit kill-switch

### phase_acbuild_2_cutover: AC-Driven Build v2 — Thin Tickets & AC-as-Unit-of-Work (dogfooded)

**Status**: Planned

Flip the model on leafcutter itself FIRST (dogfood). The generator emits thin tickets that reference their AC; each AC carries a deliverable checklist with per-deliverable sign-offs recorded ON THE AC; the ticket becomes a grouping container. Sign-offs move off the ticket body in the single atomic cutover, gated behind ac_unit_of_work.emit; the store is backfilled; new gates are promoted to required only after a green self-host window.

**Exit Criteria**:

- Generator emits thin tickets behind ac_unit_of_work.emit; sign-offs dual-recorded (AC + ticket) then moved to AC-only
- A full self-host epic built end-to-end thin + AC-sign-off, behaviorally spot-checked on a real on-disk ticket in a fresh process
- Store backfilled to 100% (strict schema validation = 0 errors); already-done ACs grandfathered, not regressed
- ac-fulfillment-gate flips 'absent ac_traceability -> blocker' and any new done-accounting gate is promoted to required (diff-scoped) only after >=10 consecutive green self-host merges; ACD-400b family superseded via governance

### phase_acbuild_3_migration: AC-Driven Build v2 — Consumer Migration & Legacy Removal

**Status**: Planned

Bring existing consumers across safely, then retire the old path. build.py deploys the new artifacts (all hook deps in the deploy-manifest) and warns/refuses on schema_version skew; consumers run an opt-in, idempotent backfill; dual-readers remain for >=2 minor releases while in-flight fat tickets drain; only then are fat-ticket generation and the legacy-derive path removed.

**Exit Criteria**:

- build.py deploys new hooks with all deps in the deploy-manifest and warns/refuses on schema_version skew
- Opt-in idempotent backfill ships (dry-run, --ac-store-dir, preserves notes blocks); >=1 consumer (or consumer-sim) migrated green
- Dual-readers retained >=2 minor releases; in-flight fat tickets allowed to drain; legacy fat-ticket generation and dual-read/derive removed in a dedicated release with one full green cycle
- Rollback rehearsed: ac_unit_of_work.enforce=false restores green within one commit

### phase_2: Ecosystem Hardening

**Status**: Planned

Handle version upgrades gracefully with template migrations and config schema evolution. Support multiple concurrent consumer projects and document the contribution workflow for new agents and skills.

**Exit Criteria**:

- Version upgrade path tested: old config + new templates produces valid output with migration warnings
- Documented contribution workflow for adding agents and skills to the package
- Config schema validation rejects unknown keys with actionable error messages

### phase_3: Distribution and Community

**Status**: Planned

Installable via a standard package manager with versioned releases, changelogs, and a documented extension mechanism for community-contributed agents and skills.

**Exit Criteria**:

- Package installable via a standard package manager (pip or npm)
- Versioned releases with auto-generated changelogs
- Extension mechanism documented and tested with at least one community-contributed agent

---

*Last regenerated: 2026-08-12T10:37:09Z. Do not edit this file directly — edit `docs/roadmap.json` instead.*
