---
title: "Untrack build-shim symlinks committed with absolute local paths (BP-016)"
date: "2026-08-14"
time: "02:36"
type: manual
components: 
  - build_pipeline
  - commit_guardian
  - doc_compliance
  - feedback_collector
summary: "Fixed a repository hygiene bug where five build-generated shortcut files had been accidentally saved into the repository pointing at one developer's own computer, which silently turned off safety checks for everyone else who downloaded the project."
description: "Untracked five build-shim symlinks (scripts/commit_guardian, scripts/doc_compliance, scripts/feedback, .claude/workflows, .env) that were committed as dangling absolute-path symlinks pointing into a worktree that no longer exists. The dangling links made guardian-dependent gates silently take their script-absent skip path, producing false-green local runs that then failed in CI once build.py regenerated the shims; .env was tracked as a symlink pointing at itself, leaving git status permanently showing a T .env typechange. Root cause was two independent .gitignore defects: the two existing entries had a trailing slash, which matches a directory pattern and never matches a mode-120000 symlink entry, and three of the five paths had no .gitignore entry at all. Corrected .gitignore (dropped trailing slashes, added the three missing entries, documented why the bare form is required) and added a generic test that scans the git index for any tracked mode-120000 entry whose blob is an absolute path, so future occurrences are caught automatically."
adrs: 
  - ADR-016
tickets: 
  - BP-016
breaking: false
---

## Entry

### Correction (added 2026-08-18 — read before trusting the title above)

A customer audit at pin `54356a92` found that the build was still generating
every symlink shim with an absolute, machine-local target, and traced the gap
back to this entry. They are right, and the record needs to say so explicitly
rather than being silently rewritten.

**What BP-016 actually fixed:** tracking only. It stopped five already-committed
symlinks — `scripts/commit_guardian`, `scripts/doc_compliance`,
`scripts/feedback`, `.claude/workflows`, and the self-referential `.env` — from
being present in the git index, and corrected the two `.gitignore` defects
(trailing slashes that only match directories, plus three missing entries)
that had let them get committed in the first place. That is a complete fix
*for this repo*, where build output is untracked by design.

**What BP-016 did NOT fix:** generation. `install_shims()` — both
`_create_shim` (directory shims) and `_create_file_shim` (file shims) —
continued to build `source_path` as an absolute path and pass it straight into
`Path.symlink_to()`, exactly as before this ticket. Nothing in BP-016 touched
that code path.

**The title is misleading on exactly this point.** "Untrack build-shim
symlinks committed with absolute local paths" names the absolute-path hazard
in its own title while describing a fix to *tracking*, not to *generation*. A
reader — including, evidently, a downstream auditor — can reasonably infer
from that title that the absolute-path problem itself was resolved. It was
not. Do not read this entry as having closed the absolute-path hazard; it
closed only the committed-symlink symptom of it.

**Who was exposed in the interval:** any consumer who vendors, copies, or
otherwise ships this repo's *build output* (as opposed to cloning the repo
itself) inherited machine-specific absolute symlink targets from BP-016
(2026-08-14) until BP-017 landed (2026-08-18) — four days.

**The generation gap was closed by BP-017** (PR #477, squashed to
`967f37fbc` on main), which added `_relative_symlink_target()` so shim targets
are computed with `os.path.relpath` and no longer bake in a build-time
absolute path. See the BP-017 changelog entry for detail:
`changelogs/2026-08-18-1352-symlink-shims-now-record-relative-targets-closes-the-generation-gap-bp-016-left-open-bp-017.md`.
