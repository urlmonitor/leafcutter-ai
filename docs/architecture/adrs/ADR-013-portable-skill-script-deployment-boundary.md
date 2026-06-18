---
title: "ADR-013: Portable Skill Script Deployment Boundary — Consumer-Facing vs Package-Internal"
description: "Establishes that a skill is portable: true iff its SKILL.md and all referenced scripts deploy to consumer installs, and adds build_ac_store() to deploy the AC-pipeline scripts accordingly."
type: "adr"
status: "accepted"
created: "2026-06-17"
last_updated: "2026-06-17"
amended: "2026-06-17"
deciders:
  - architect-review
components:
  - skills_system
  - build_pipeline
  - ac_store
related_docs:
  - docs/architecture/adrs/ADR-001-self-hosting-boundary.md
  - docs/architecture/adrs/ADR-010-ac-store-as-authoritative-backlog.md
  - config/skill_registry.json
  - scripts/build_phases.py
  - tickets/00_inbox/epics/EPIC-AcPipelineDeployGaps/03_reconcile_ac_scanner_portability.md
---

# ADR-013: Portable Skill Script Deployment Boundary

## Status

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-06-17 |
| Deciders | architect-review |
| Author | architect-review |
| Supersedes | — |
| Amended | 2026-06-17 (ticket 05 — corrected stale `target_root`/`output_root` naming; updated deployment path descriptions to reflect actual `.leafcutter/scripts/ac_store/` layout) |

## Context

The leafcutter build pipeline deploys agents, skills, hooks, and supporting
scripts to consumer project installs. The `skill_registry.json` `portable`
field is the single canonical signal for whether a skill is consumer-facing
(`portable: true`) or package-development-only (`portable: false`).

A recurring gap has emerged: skills are marked `portable: true` in the registry
(meaning they will be deployed to consumers via the `build_skills` phase), but
the Python scripts those skills depend on are not deployed by any build phase.
The consumer receives the skill SKILL.md (which documents the script invocations)
but not the scripts themselves — a runtime failure guaranteed on every consumer
install that tries to use these skills.

This gap first surfaced for the AC pipeline skills:

- `ac-scanner` (portable: true) — depends on `scripts/ac_store/scan_ac_store.py`,
  `scripts/ac_store/generate_ticket_from_ac.py`, and `scripts/ac_store/ac_prioritizer.py`
- `build-ac` (portable: true) — depends on `scripts/ac_store/generate_ticket_from_ac.py`,
  `scripts/build_ac_mode_detection.py`, and `scripts/goal_to_epic.py`

Neither script set has a corresponding `build_<group>` phase in `build_phases.py`,
and no `templates/scripts/ac_store/` directory exists. The skills are semantically
broken on consumer installs.

The question is: should these skills be **Option (a) — made truly portable** by adding
a script deployment phase, or **Option (b) — marked package-internal** (`portable: false`)
because they are development-only tools?

## Decision

**Option (a): Add a `build_ac_store` deployment phase. The AC pipeline skills remain
`portable: true` and their scripts are deployed to consumer installs.**

The design rationale is:

1. **ADR-010 intent.** ADR-010 declares the AC store the "authoritative source of truth
   for the leafcutter-ai build backlog" and explicitly positions `scan_ac_store.py` and
   `generate_ticket_from_ac.py` as automation tools for the build pipeline. Nothing in
   ADR-010 limits the AC-driven pipeline to package developers — it describes a general
   mechanism for eliminating manual ticket transcription that applies equally to any
   project using leafcutter.

2. **ADR-001 portability posture.** ADR-001 explicitly rejects special modes for the
   package's own use. `build.py` works identically for any target project. The `build_ac_store_docs`
   phase (already present in `build_phases.py`) deploys AC store documentation to consumers,
   proving that the AC store is treated as a consumer-facing feature. Deploying the scripts
   that power those docs is logically required by the same decision.

3. **Skill registry semantics.** Both `ac-scanner` and `build-ac` are `portable: true`
   in `skill_registry.json`. The `portable` flag is the authoritative signal to downstream
   tooling (skill consistency checks, package audits, consumer-install verification). Setting
   `portable: false` on these skills after they have already shipped as `true` is a semantic
   regression. The correct fix for a skill that is `portable: true` but whose scripts are not
   deployed is to add the missing deployment phase — not to downgrade the skill's portability.

4. **Consumer value.** The AC-driven build loop (`/ac-scanner`, `/build-ac`) provides
   genuine value to any software project: it eliminates manual ticket authoring from an
   authoritative requirement backlog. Restricting it to package developers only would mean
   leafcutter's most powerful automation feature is unavailable to its users.

### What "portable: true" means (canonical definition)

A skill is **portable** iff:

1. Its SKILL.md is deployed to consumer installs via `build_skills`.
2. Every script the SKILL.md references is either:
   a. Deployed to the consumer's `scripts/` tree via a corresponding build phase, OR
   b. Part of the Python stdlib / a declared dependency (available without deployment).
3. The skill is self-contained and does not depend on package-internal paths that
   only exist in the leafcutter source tree.

A skill is **package-internal** (`portable: false`) iff it is only valid to invoke
inside the leafcutter package source tree (e.g. build-time tooling that operates on
`templates/`, `config/`, or `scripts/` as package artifacts rather than as consumer
scripts).

### Script deployment rule (binding)

For every skill with `portable: true` whose SKILL.md references scripts:

- If the scripts are in `scripts/ac_store/`, a `build_ac_store` phase MUST copy them
  to `templates/scripts/ac_store/` and deploy them to
  `<output_root>/scripts/ac_store/` (i.e. `.leafcutter/scripts/ac_store/` on a
  default consumer build). The deployed paths are referenced in agent templates and
  SKILL.md files via the `{{config.output_root}}/scripts/ac_store/<name>` placeholder,
  which `template_compiler.py` substitutes at build time.
- If the scripts are in `scripts/<other_group>/`, an equivalent `build_<group>` phase
  MUST exist or be created before the skill is published as `portable: true`.

> **Naming note (ticket 05 — BP-811 family):** The `build_ac_store()` function
> signature uses `target_root` as its parameter name, while `build.py` passes the
> value via `output_root`. Both refer to the same `.leafcutter/` directory on a
> default consumer build. Earlier revisions of this ADR and the `build_ac_store()`
> docstring used `<target_root>/scripts/` to describe the deploy destination; this
> was incorrect — the actual destination is `<output_root>/scripts/ac_store/` (i.e.
> `.leafcutter/scripts/ac_store/`), not a project-root `scripts/` directory.
> All stale `<target_root>` references in this ADR and the `build_phases.py`
> docstring have been corrected in ticket 05 of EPIC-AcPipelineDeployGaps.

This rule is mechanically enforceable by the `test_skill_portability_consistency` test
required by EPIC-AcPipelineDeployGaps ticket 03 (AC-6).

## Consequences

### Positive

- **Runtime correctness on consumer installs.** Skills advertised as portable will
  function without modification on any project that runs `build.py`.
- **Consistent developer experience.** A leafcutter consumer can rely on `/ac-scanner`
  and `/build-ac` working the same way the package developers use them internally.
- **Mechanical enforcement.** The `test_skill_portability_consistency` test (AC-6) can
  now be implemented as a general policy test: every `portable: true` skill must have
  all its scripts present in the build output. Failures are caught before release.
- **Clarity for future skill authors.** This ADR provides a canonical definition of
  `portable: true` vs `portable: false` so skill authors know what they are committing
  to when they set the field.

### Negative

- **Deployment surface grows.** Adding `build_ac_store` deploys six additional scripts
  to every consumer install, regardless of whether the consumer uses the AC pipeline.
  This is a minor footprint increase (all files are small Python scripts).
- **Consumer must have PyYAML.** The AC store scripts depend on PyYAML. Consumers who
  do not have PyYAML installed will encounter an import error at runtime. This is an
  existing implicit dependency (the AC store docs mention YAML) that becomes explicit.
  Mitigation: add a dependency note to the how-to documentation.

### Neutral

- The `build_ac_store` phase follows the identical pattern as `build_commit_guardian`,
  `build_feedback`, and `build_sync_platforms` — copy scripts verbatim from source to
  `templates/scripts/<group>/` and deploy to `<output_root>/scripts/<group>/` (i.e.
  `.leafcutter/scripts/<group>/` on a default consumer build). No new infrastructure
  is required.
- Skills with `portable: false` are unaffected. This ADR does not retroactively change
  the semantics of existing package-internal skills.

## Alternatives

### Alternative B — Mark ac-scanner and build-ac portable: false

Set `"portable": false` on both skills in `skill_registry.json` and reserve the
AC pipeline for package developers only.

**Rejected.** This contradicts ADR-010's intent, contradicts the existing
`build_ac_store_docs` phase (which already treats the AC store as consumer-facing),
and removes a high-value feature from consumer installs. It also sets a bad precedent:
any skill whose scripts happen to not be deployed yet would be silently downgraded
rather than having its deployment gap fixed.

### Alternative C — Lazy deployment (deploy scripts only if AC store is detected)

Add a conditional gate: deploy ac_store scripts only if the target project already
has a `docs/acceptance-criteria/` directory.

**Rejected.** This adds complexity to the build phase (a conditional that is hard to
test), creates a surprising user experience (skills appear portable but silently
fail on fresh installs), and does not align with how other build phases work
(all phases deploy unconditionally; the user's skills_config.json controls which
features are active, not the presence of data directories).

## References

- [ADR-001 — Self-Hosting Boundary](ADR-001-self-hosting-boundary.md) — established that `build.py` works identically for any consumer; no special modes for package-internal use.
- [ADR-010 — AC Store as Authoritative Backlog](ADR-010-ac-store-as-authoritative-backlog.md) — established the AC pipeline as the driver of the build backlog, applicable to any leafcutter project.
- [EPIC-AcPipelineDeployGaps ticket 03](../../tickets/00_inbox/epics/EPIC-AcPipelineDeployGaps/03_reconcile_ac_scanner_portability.md) — commissioning ticket for this ADR; implementation gated on this decision.
- [config/skill_registry.json](../../../config/skill_registry.json) — single source of truth for skill portability declarations.
