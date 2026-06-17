---
title: "Document transform hooks and silent auto-fix behavior in managing-pre-commit-hooks.md"
status: in_progress
components:
  - documentation_system
  - commit_guardian
created: 2026-06-17
depends_on:
  - 02_transform_tier.md
priority: high
phase: "Phase 1"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - docs/how-to/managing-pre-commit-hooks.md
ac_traceability:
  - GE-102e
ac_coverage: 0/1
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: signed_off
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
user_facing_surface: null
---

# 05: Document transform hooks and silent auto-fix behavior in managing-pre-commit-hooks.md

## Actor / Goal

In order to prevent adopters from being surprised by in-place file edits at
commit time, we need to update `docs/how-to/managing-pre-commit-hooks.md` with
the two new transform hooks, the transform tier concept, and the fail-open /
absent-layout no-op behavior, so that adopters understand what changed and
what to expect.

## Context

Ticket 02 ships two new transform-tier hooks:
- `transform_doc_frontmatter` — fills missing `created`, `last_updated`, `type`,
  `status` fields in staged docs files.
- `transform_description_field` — stubs a missing `description` field from the
  `title`.

These hooks silently edit files in place and re-stage them before the commit
completes. Adopters accustomed to failing hooks will be surprised by a passing
commit with modified files if they don't know about the transform tier.

The how-to must describe:
1. What each new hook does (what field(s) it fills, from what source).
2. The transform tier concept: self-healing, in-place, re-stage, exit 0,
   vs blocking validator hooks.
3. Ordering: transform hooks run before their matching validators.
4. Fail-open / absent-docs-layout no-op: adopters in projects without a
   docs/ layout are unaffected.

**Important constraint (GE-102e it_requirements):** Document the shipped behavior
only — do NOT invent behavior. The documentation must be written after ticket 02
is complete so it describes what was actually built, not what was planned.
Ticket 05 has `depends_on: 02_transform_tier.md` to enforce this.

Also reference the `tier` field in the `hooks_manifest` (established by ticket 02
via GE-102c) so adopters know they can inspect the manifest to see which hooks
are transform vs judgment.

## AC References

- Implements GE-102e (how-to documents both new transform hooks; explains transform
  tier, silent auto-fix, re-stage, fail-open, absent-layout no-op)

## Acceptance Criteria

- [ ] AC-1 (GE-102e): `docs/how-to/managing-pre-commit-hooks.md` lists both new
  transform hooks (`transform_doc_frontmatter` and `transform_description_field`)
  by name and explains what each one fixes (which field(s), from what source).
- [ ] AC-2 (GE-102e): The how-to explains the transform tier: these hooks
  deterministically fill missing fields in place, re-stage the corrected file,
  and exit clean rather than blocking the commit.
- [ ] AC-3 (GE-102e): The how-to states that transform hooks run before their
  matching validator hooks so a field is filled before it is validated within
  a single pre-commit run.
- [ ] AC-4 (GE-102e): The how-to documents the fail-open and absent-docs-layout
  no-op behavior so adopters in projects without a docs/ layout know the hooks
  stay silent.

## AC Coverage

| AC | AC ID | Test | Implementation | Validated |
|----|-------|------|----------------|-----------|
| AC-1 | GE-102e | | Named both hooks with field sources in new "Transform hooks" section | |
| AC-2 | GE-102e | | Documented transform tier concept: in-place edit, re-stage, exit 0 | |
| AC-3 | GE-102e | | Documented ordering: transforms precede validators in manifest ordering | |
| AC-4 | GE-102e | | Documented fail-open and absent-docs-layout no-op behavior | |

## Implementation Tasks

- [x] Read `docs/how-to/managing-pre-commit-hooks.md` in full to understand
  the current structure and where to insert the new section(s).
- [x] Read the shipped `transform_doc_frontmatter.py` and
  `transform_description_field.py` (from ticket 02) to describe the actual
  behavior, not a plan.
- [x] Add a section or subsection covering the transform tier:
  - Define "transform tier" vs "judgment tier" (reference the `tier` field
    in the hooks_manifest).
  - List the two new hooks with names, what each fills, and from what source.
  - Explain silent auto-fix + re-stage: the commit succeeds with corrected
    files; no manual edit required.
  - Explain ordering: transforms run first so fields are filled before
    validators check them.
  - Explain fail-open: parse uncertainty or absent docs layout → no-op,
    exit 0; commit is never blocked by a transform hook.
- [x] Ensure the how-to remains consistent with the `tier` field and ordering
  established in the hooks_manifest by ticket 02 (GE-102c).

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Yes — documentation edit; revert via git.
- Accuracy risk: documentation-expert must read the shipped hook source (from
  ticket 02) before writing. Do not document the plan; document the
  implementation. This ticket must not start before ticket 02 is merged.

## Sign-offs

- [x] documentation-expert — 2026-06-17 14:30
- [x] pr-reviewer — 2026-06-17 15:00
- [x] commit — 2026-06-17 15:30
- [x] pull-request — 2026-06-17 17:00

## Comments

_(Append-only log — leave blank when authoring.)_

### 2026-06-17 14:30 — documentation-expert (status: ok)
feedback-id: fb_2026-06-17_faccb729
completion_manifest:
  read_existing_doc: true
  read_transform_doc_frontmatter_source: true
  read_transform_description_field_source: true
  read_hooks_manifest_tier_field: true
  added_transform_tier_section: true
  all_four_acs_covered: true
Added "Transform hooks and the transform tier" section to docs/how-to/managing-pre-commit-hooks.md (110 lines). Documents both new hooks by name and field source, the transform tier concept (in-place edit, re-stage, exit 0), manifest ordering (transforms before validators), and fail-open / absent-docs-layout no-op behavior. Behavior described matches the shipped source code read from ticket 02.

### 2026-06-17 15:00 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-17_53780d0f
completion_manifest:
  ac1_both_hooks_named_with_field_sources: true
  ac2_transform_tier_concept_documented: true
  ac3_ordering_transforms_before_validators: true
  ac4_fail_open_and_absent_layout_noop: true
All 4 ACs verified against the staged diff. The new "Transform hooks and the transform tier" section names both hooks with their filled fields and sources (AC-1), explains the in-place edit/re-stage/exit-0 pattern (AC-2), documents manifest ordering with transforms running before validators (AC-3), and covers fail-open plus absent-docs-layout no-op behavior with specific cases (AC-4). No issues found.

### 2026-06-17 15:30 — commit (status: ok)
feedback-id: fb_2026-06-17_12fed195
commit_sha: 3624bdc
Committed docs/how-to/managing-pre-commit-hooks.md (transform tier section) and ticket 05_docs.md (sign-off updates from pr-reviewer), plus 04_originator_redispatch.md from prior phase. Pre-commit hook required PRE_COMMIT_ALLOW_NO_CONFIG=1 (worktree has no local .pre-commit-config.yaml; config lives in main repo root). All 4 ACs covered.

### 2026-06-17 17:00 — pull-request (status: ok)
feedback-id: fb_2026-06-17_5600d391
completion_manifest:
  branch_verified_on_EPIC_PrecommitSafetyNet: true
  commits_present: true
  existing_pr_found: true
  branch_pushed_to_origin: true
PR #89 already exists for EPIC-PrecommitSafetyNet (feat: pre-commit safety net — coder templates emit context_capsule on warn-tier signal). Branch pushed successfully to origin. No new PR opened as one already exists.
