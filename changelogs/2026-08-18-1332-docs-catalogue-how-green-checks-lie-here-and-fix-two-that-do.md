---
title: "docs: catalogue how green checks lie here, and fix two that do"
date: "2026-08-18"
time: "13:32"
type: manual
components: 
  - ac_store
  - commit_guardian
  - testing_quality
  - documentation_system
  - build_orchestration
summary: "Catalogued the recurring ways a passing check in this codebase can look green while proving nothing, opened four known-issue registers naming the specific defects behind them, and corrected two AC-store instructions in CLAUDE.md, one of which had been silently checking nothing since 2026-08-10."
description: "Adds docs/reference/false-green-mechanisms.md (M1-M8: grep-only structural tests, a hook dependency missing from the build deploy-manifest, AC hooks scoped to the git index rather than the store, biased synthetic fixtures, a validator that exits 0 having checked nothing, an eval scorer that treats a missing answer as a negative, a module invoked as a CLI that has no CLI, and a countable proxy reported as a verdict), plus four new docs/known-issues/ registers (ac-store, commit-guardian, testing-quality, documentation-system) recording the specific open defects behind those mechanisms -- including the pt-classifier eval floor matching its gold set's all-negative fraction (4 of 18 rows, 22.22%, the exact figure CI reports) and a store-wide sweep finding 20 composite ACs marked done with an unfinished child, out of 3,146 records. Also fixes two CLAUDE.md instructions: the AC-store bulk-validation pre-flight command, a documented defence against store rot that had been a silent no-op against a bare directory since 2026-08-10 (a corrected run surfaced 288 real, pre-existing schema violations store-wide), and a new convention requiring the parent AC to be staged alongside a changed child. No production code changed and no defect was repaired -- these are records of open issues, not fixes to them, apart from the two CLAUDE.md instruction corrections themselves."
commits: 
  - 2806dc27c
breaking: false
---

## Entry

This is a documentation and instruction-correction change. No production code
changed, and no open defect was repaired — the seven surfaces below *record*
defects so they are not lost, they do not fix them.

**`docs/reference/false-green-mechanisms.md` (new).** A catalogue of eight
recurring ways a passing check in this repo carries no information (M1..M8),
each with a tell, what defeats it, and a verified citation: grep-only
structural tests; a hook dependency missing from the build deploy-manifest;
AC hooks scoped to the git index rather than the store; synthetic fixtures
that reproduce the author's own bias; a validator that exits 0 having checked
nothing; an eval scorer that treats "no answer" as an all-negative answer; a
module invoked as a CLI that defines no CLI; and a check that measures a
countable proxy and reports it as a verdict. M1-M4 were already normative
rules in `CLAUDE.md`; M5, M6 and M8 were previously undocumented.

**Four new `docs/known-issues/` registers** (`ac-store`, `commit-guardian`,
`testing-quality`, `documentation-system`), using the register surface added
in #470, recording the specific open defects behind those mechanisms:

- The AC-schema validator exits 0 and prints "No YAML files to validate."
  when handed a bare directory instead of file paths. Running it correctly
  across the whole store instead found **288** real, pre-existing schema
  violations — mostly legacy list-form `it_requirements`.
- `--verify`'s `[PASS]` on `files_touched` only checks that the count is
  greater than zero, not that the paths are correct.
- The AC hooks derive their file list from `git diff --cached`, never from
  the store, so parent-level drift on a composite AC is structurally
  unreachable by them. A store-wide sweep of all **3,146** records found
  **20** composite ACs marked `done` with at least one unfinished child.
- The pt-classifier eval's credential-less floor equals its gold set's
  all-negative fraction: **4 of 18** rows, so a run with no credentials
  scores **22.22%** — exactly the figure CI reports as if it were a quality
  measurement.
- Four of the five Diataxis authoring conventions (`write-how-to`,
  `write-adr`, `write-explanation`, `write-architecture-doc`) have never
  actually been committed; only `write-reference` exists in `git log --all`.

**Two `CLAUDE.md` corrections.** The "AC-store hygiene" pre-flight command
prescribed running the schema validator against a bare component directory —
which, per KI-ACS-001 above, silently checks nothing. That has been the
documented (and wrong) defence against store rot since 2026-08-10; it is
replaced with a `find -exec` form (a fixed-depth glob is rejected in the same
note, since AC YAML sits at more than one depth). A new Implementation
Convention, "AC-store commits — stage the parent alongside the child",
records why the index-scoped AC hooks (M3 above) can never catch stale
`covered_by` links or a falsely-`done` composite unless the parent file is
staged in the same commit.

**Also:** a new section in `docs/how-to/ac-traceability-store.md` on making
`/build-ac` name the correct `files_touched`, and the one-line `docs/INDEX.md`
update from the doc-index transform hook.
