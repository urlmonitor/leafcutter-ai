---
title: "KI-BP-20261009-epic-worktree-install-goes-stale-per-ticket — every epic ticket that edits a hook or agent template leaves the epic worktree's .leafcutter install stale, check-build-drift then refuses every commit in that worktree until build.py is re-run, and each re-run dirties tracked files that must be restored by hand"
description: "medium — in the package's own repository an epic worktree's deployed install is a snapshot of its templates. When ticket 05 of EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace changed templates/scripts/commit_guardian/precommit_canary.py, check-build-drift refused commits until build.py --target-dir <worktree> was re-run. Each re-run rewrites tracked generated files (docs/agents/cards/*, LEAFCUTTER_VERSION, docs/INDEX.md); the coordinator counted about 60 per rebuild in the epic worktree, and a fresh worktree off origin/main c373b005e showed 8 cards plus INDEX.md on a second build."
type: reference
category: reference
status: active
created: '2026-10-09'
last_updated: '2026-10-09'
components:
  - build_pipeline
  - commit_guardian
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/build-pipeline/open-high-ki-bp-004.md
  - docs/known-issues/build-pipeline/open-low-ki-bp-002.md
  - docs/known-issues/build-pipeline/open-low-ki-bp-015.md
  - docs/known-issues/build-pipeline/open-high-ki-bp-20260831-1333.md
---

# KI-BP-20261009-epic-worktree-install-goes-stale-per-ticket — the drift gate and the rebuild that clears it both cost every template-editing ticket

> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** medium. The gate is correct to refuse: the deployed hooks really are stale. But
  the cost lands on every ticket that edits a template, the remedy is manual, and the remedy's
  side effects have to be undone by hand before every commit. On an unattended drive, a phase
  agent will either stop or sweep the generated files into the ticket's commit.
- **Status:** open, no AC.
- **Occurrences:** recurring through the BO-4300 drive (ticket 05's template changes, 2026-10-09).
  The rebuild churn reproduced on 2026-10-09 in a fresh worktree off `origin/main` `c373b005e`.
- **First seen:** during the BO-4300 drive · **Last seen:** 2026-10-09
- **Where:** `templates/scripts/commit_guardian/check_build_drift.py` (compares
  `templates/agents/*.md` and `templates/scripts/commit_guardian/*.py` against
  `.build_manifest.json`; module docstring, SCOPE); `scripts/build.py` (rewrites tracked generated
  files on every run).

## Symptom

1. A ticket changes a template inside `check-build-drift`'s scope. Ticket 05's commit `03a1e4cd4`
   changed `templates/scripts/commit_guardian/precommit_canary.py` and `commit_guardian.json`.
2. The next commit in the epic worktree is refused by `check-build-drift` until
   `python scripts/build.py --target-dir <worktree>` is run there. Ticket 05's python-coder
   records doing exactly that: "Build re-run, deployed canary matches template, check_build_drift
   drifted=0."
3. The rebuild rewrites tracked generated files, which then show as modified and must be restored
   (`git restore LEAFCUTTER_VERSION docs/agents/cards`) so they do not ride into the ticket's commit.
   The coordinator counted about 60 per rebuild in the epic worktree. Reproduced 2026-10-09 in a
   fresh worktree off `origin/main` `c373b005e`: the first build dirtied `LEAFCUTTER_VERSION`,
   `docs/agents/cards/*` and `docs/INDEX.md`. A second build dirtied 8 cards (430 lines) and
   `docs/INDEX.md`, where rows in two tables were re-ordered by letter case.
4. The rebuilt worktree also accumulates readme-marker caches
   (`.claude/.cache/readme_markers/*.json`), which `check-output-drift` flags as GAPs. See the
   2026-10-09 note on `KI-BP-20260831-1333`.

## Mechanism

- In the self-hosting layout the epic worktree is both the package source and an install of it.
  The install is copied from the templates at build time. Any ticket that edits a covered template
  makes the install stale, by definition, and `check-build-drift` is the gate that says so
  (`KI-BP-004` asked for exactly this check).
- `build.py` regenerates tracked outputs as a side effect of every run (`KI-BP-002`, `KI-BP-015`).
  So the rebuild that clears one gate creates a diff unrelated to the ticket.
- Nothing in the drive runs the rebuild. The commit agent's hook-failure path does not know that
  `check-build-drift` is cleared by a build, nor that the build's tracked side effects must be
  restored afterwards.

## Impact

A manual rebuild-and-restore cycle per template-editing ticket, and a standing risk that a phase
agent stages the regenerated cards or `docs/INDEX.md` into a ticket commit (compare `KI-BO-029`).

## Fix direction

- Have the drive rebuild the worktree's install after any phase that changes a covered template,
  and restore the build's tracked side effects as part of the same step.
- Stop `build.py` from writing tracked files that are not part of its target install, or make
  their output deterministic (stable sort, no version bump when nothing changed), so a rebuild of
  an up-to-date tree is a no-op.
- Teach `precommit-autofix` that `check-build-drift` maps to "re-run build.py, then restore
  generated tracked files", not to a code edit.

**Related.** `KI-BP-004` (stale deployed hooks after a merge, which this gate now catches).
`KI-BP-002` and `KI-BP-015` (cards dirtied by every build). `KI-BP-20260831-1333` (the readme-marker
GAP).
