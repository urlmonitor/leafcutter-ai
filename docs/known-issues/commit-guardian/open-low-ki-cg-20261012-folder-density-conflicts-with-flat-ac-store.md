---
title: "KI-CG-20261012-folder-density-conflicts-with-flat-ac-store — check-folder-density (GE-120h-3) conflicts with the flat AC-store layout, so every business-analyst stage commit of a normal-sized AC tree is refused"
description: "medium — the AC store keeps every AC of one L0 tree flat in one folder, an L0 tree routinely holds far more than the 15-file density cap, and check-folder-density has no exemption for docs/acceptance-criteria/. So the commit that first takes a tree past 15 ACs is refused, and has needed a user-authorized SKIP=check-folder-density. Tree size is already governed by check_ac_limits, so the generic cap adds no protection there."
type: reference
category: reference
status: active
created: '2026-10-12'
last_updated: '2026-10-12'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
  - docs/known-issues/commit-guardian/resolved/resolved-high-ki-cg-20261010-folder-density-refuses-merges-of-main.md
  - docs/known-issues/commit-guardian/open-low-ki-cg-20260909-gate-folder-density.md
---

# KI-CG-20261012-folder-density-conflicts-with-flat-ac-store — check-folder-density conflicts with the flat AC-store layout

> Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below.

- **Severity:** medium. The refusal is loud and nothing wrong lands, but the normal authoring path
  for any AC tree larger than 15 records cannot commit without a user-authorized
  `SKIP=check-folder-density`, and that skip is a habit that hides real density refusals elsewhere.
- **Status:** open, no AC.
- **Occurrences:** 2 BA-stage commits (see Evidence). · **First seen:** 2026-10-09 · **Last seen:** 2026-10-09
- **Where:** `templates/scripts/commit_guardian/check_folder_density.py` (deployed as
  `scripts/commit_guardian/check_folder_density.py`), configured by the `folder_density` section
  of `templates/scripts/commit_guardian/commit_guardian.json`.

## The conflict

1. **The hook caps every directory at 15 non-markdown files.** `folder_density.max_files_per_folder`
   is `15`. `excluded_dirs` is name-based (`__pycache__`, `.git`, `.venv`, `node_modules`,
   `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `_legacy`), matched against each path part by
   `is_excluded_path`. There is no path-based exclusion and nothing exempts
   `docs/acceptance-criteria/`. AC records are `.yaml`, so every one of them counts.
2. **The AC store is flat per L0 tree.** Every AC of one L0 tree lives directly in one folder,
   `docs/acceptance-criteria/<component>/<L0-slug>/`. No AC anywhere lives in a nested sub-folder,
   and the AC loaders, scanners and generators have never been verified against nesting.
3. **An L0 tree routinely exceeds 15 ACs.** `BO-4300-one-way-workspaces` holds 68 and
   `BO-4400-nothing-accumulates` holds 49. `check_ac_limits` itself permits a tree far larger than 15:
   up to 7 L1 per L0 and 5 L2 per L1 is 43 records at L0 to L2 alone, before any L3.
4. **So the commit that takes a tree past 15 is refused.** Since GE-120h-3 the hook refuses a folder
   that CROSSES the cap in one commit; a folder already over the cap before the commit only warns.
   A business-analyst stage commit adds the whole L2/L3 layer at once, so for any normal-sized tree
   it is exactly the crossing commit.

## Evidence

- `46c81167b` (on `ac-authoring/build-orchestration`, merged via PR #1098): the BO-4400 BA-stage
  commit, adding 42 new AC files to `BO-4400-nothing-accumulates/`. It needed a user-authorized
  `SKIP=check-folder-density`.
- `e6228a0e6`: the BO-4300 BA-stage commit added 56 new AC files to
  `BO-4300-one-way-workspaces/` (63 files changed), so it also took one folder well past 15 in a
  single commit.

## Why the cap adds nothing here

AC tree size is already governed by the AC-specific hooks: `check_ac_limits` hard-caps at 7 L1 per
L0 and 5 L2 per L1 (ACS-100c-1). A tree that passes those limits is the shape the store intends;
the generic density cap refuses it anyway and offers no remedy the AC tooling supports.

## Workaround

A user-authorized `SKIP=check-folder-density` on the BA-stage commit, stating in the message that the
flagged folder is an AC tree and the store is flat per L0. All other hooks still run.

## Fix direction (not implemented)

- **Preferred:** exempt `docs/acceptance-criteria/` from `check_folder_density` with a path-based
  exclusion (the current `excluded_dirs` matches directory names only, so this needs a new
  config key or a prefix match), and rely on `check_ac_limits` for AC tree size.
- **If nesting is preferred instead:** first verify that every AC loader, scanner and generator walks
  nested folders, then teach `/plan-feature` to write per-L1 sub-folders. Do not nest before that
  verification; a loader that only reads one level would silently drop ACs.

**Related.**

- `KI-CG-20261010-folder-density-refuses-merges-of-main`: the same hook refusing merges of main for
  dense folders, including AC-tree folders; its "A layout conflict underneath" section first noted
  this conflict. This entry files the conflict on its own.
- `KI-CG-20260909-gate-folder-density`: the earlier defect where the hook could never refuse;
  GE-120h-3 fixed it, which is what made this refusal reachable.

**Pattern:** a generic structural gate applied to a store whose layout is governed by its own,
more specific gate.
