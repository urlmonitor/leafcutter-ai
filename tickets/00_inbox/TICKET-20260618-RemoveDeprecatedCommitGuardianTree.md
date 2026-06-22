---
title: "Migrate orphaned scripts off the deprecated templates/commit-guardian/ tree, then remove it"
status: todo
components:
  - build_pipeline
  - commit_guardian
created: 2026-06-18
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: false
requires_diagram: false
requires_adr: false
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
---

# Migrate orphaned scripts off the deprecated templates/commit-guardian/ tree, then remove it

## Actor / Goal

In order to eliminate the duplicate-template defect class (a guard fix landing in the
wrong tree — see GE-108c, GE-109a/GE-110), we need to migrate the scripts that live
**only** in the deprecated `templates/commit-guardian/` tree to the canonical
`templates/scripts/commit_guardian/` tree, drop the legacy build fallbacks, and then
delete the deprecated directory — so there is exactly one source of truth for
commit-guardian templates.

## Context

`templates/commit-guardian/` was deprecated on 2026-05-18 by
EPIC-PortableInstallHardening T03 (see [DEPRECATED.md](../../templates/commit-guardian/DEPRECATED.md)).
The canonical location is `templates/scripts/commit_guardian/`. The builder reads the
canonical path first with a **legacy fallback** to the deprecated path.

This duplication has now caused two confirmed wrong-tree defects:
- **GE-108c** — tuple-rendering fix landed in the deprecated tree.
- **GE-109a** — the `is_test_file` test-file exemption landed in the deprecated tree;
  fixed by porting to the canonical tree under **GE-110**
  ([GE-110.yaml](../../docs/acceptance-criteria/guardrail-engine/GE-100-code-quality-hooks/GE-110.yaml),
  PR #115).

**The deprecated directory is NOT safely deletable as-is.** Three scripts exist *only*
there and are still deployed via the build union (`_manifest_commit_guardian_scripts`
in [scripts/build.py](../../scripts/build.py) unions both trees specifically to keep
deploying them):

- `check_v2_ac_store_alignment.py`
- `transform_description_field.py`
- `transform_doc_frontmatter.py`

Deleting the directory before migrating these would silently drop three active hooks
from every consumer build. (Note: `transform_description_field.py` /
`transform_doc_frontmatter.py` also relate to
[TICKET-20260617-TrackMissingTransformHookScripts.md](TICKET-20260617-TrackMissingTransformHookScripts.md),
whose TDD stubs assume these are missing — reconcile with that ticket: they are not
missing, they are orphaned in the deprecated tree.)

### Build-system references to the deprecated path (all must be updated)

| File | Lines | What |
|------|-------|------|
| `scripts/build.py` | 255, 289 | `commit_guardian.json` legacy-fallback path |
| `scripts/build.py` | 351, 365 | `_manifest_commit_guardian_scripts` unions both trees |
| `scripts/build_precommit.py` | 318 | `cg_dir = TEMPLATES_DIR / "commit-guardian"` |
| `scripts/build_phases.py` | 941 | `cg_dir = _canonical if _canonical.exists() else legacy` |

Also referenced (verify before delete): `config/paths.json`, `config/package_boundary.json`,
`config/components.json`, `unit_tests/test_build_guard_real_package.py`,
`unit_tests/commit_guardian/test_check_exception_handling.py` (the GE-109a tests target the
deprecated tree via `_HOOK_SCRIPT`), and assorted docs/ADRs.

## Acceptance Criteria

- [ ] AC-1: `check_v2_ac_store_alignment.py`, `transform_description_field.py`, and
  `transform_doc_frontmatter.py` exist in `templates/scripts/commit_guardian/` (canonical),
  byte-identical to (or a reviewed supersession of) the deprecated copies.
- [ ] AC-2: `commit_guardian.json` is present in the canonical tree and is the only copy the
  builder reads (no remaining legacy-fallback read of `templates/commit-guardian/commit_guardian.json`).
- [ ] AC-3: All four build-system legacy fallbacks (build.py x2 sites, build_precommit.py,
  build_phases.py) are removed or repointed; `build.py --target-dir` produces a build whose
  deployed commit-guardian script set is identical to the pre-change build (no hook dropped).
- [ ] AC-4: The GE-109a test suite (`test_check_exception_handling.py`) targets the canonical
  tree; no test references `templates/commit-guardian/`.
- [ ] AC-5: `templates/commit-guardian/` is deleted, and a repo-wide grep for
  `templates/commit-guardian` returns only historical references (changelogs, done tickets,
  retrospectives) — no live code/config/test references.
- [ ] AC-6: Full test suite passes with no net-new regressions vs the pre-change baseline.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |
| AC-6 | | | |

## Comments

### 2026-06-18 — BrainCandy (status: ok)

Tracking ticket created while addressing the GE-110 follow-ups. Scoped but NOT
implemented inline — this is a multi-file build-system migration (4 fallback sites +
3 orphaned scripts + test repointing), too large and too risky for an in-place edit.
Drive via /build-feature when pulled. The metadata half of the follow-up (GE-109a
implemented_by reconciliation) was done separately.

## Implementation Tasks

- [ ] Move the 3 orphaned scripts to the canonical tree (git mv); diff to confirm identical.
- [ ] Ensure `commit_guardian.json` lives canonically; remove legacy-fallback reads.
- [ ] Remove the legacy fallback in build.py (255, 289), build_precommit.py (318),
  build_phases.py (941); simplify `_manifest_commit_guardian_scripts` to the canonical tree only.
- [ ] Repoint `test_check_exception_handling.py` `_HOOK_SCRIPT` to the canonical tree (the
  GE-110 tests already target canonical via `_CANONICAL_HOOK_SCRIPT`; collapse the duplication).
- [ ] Audit config/paths.json, config/package_boundary.json, config/components.json for
  deprecated-path references; update.
- [ ] Delete `templates/commit-guardian/`.
- [ ] Run `build.py` + full test suite; diff deployed hook set against the pre-change baseline.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Fully reversible via git revert; the directory and all moves are tracked.
- Scope: build-system + template layout only. The **primary risk** is silently dropping a
  deployed hook (the legacy fallback exists precisely to prevent this). AC-3 and AC-5's
  baseline-diff gate are the guardrails — do not delete the directory until the deployed
  script set is proven identical.

## Out of Scope

- Implementing genuinely-missing `transform_*` hooks (that is
  [TICKET-20260617-TrackMissingTransformHookScripts.md](TICKET-20260617-TrackMissingTransformHookScripts.md));
  this ticket only relocates the copies that already exist in the deprecated tree.
