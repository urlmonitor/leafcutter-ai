---
title: "KI-KM-20260928-doc-index-order-depends-on-host-os — generate_doc_index.py sorts Path objects, which compare case-insensitively on Windows and case-sensitively on Linux, so every Windows commit that stages a docs/*.md re-sorts docs/INDEX.md and main flips between the two orders"
description: "medium — `sorted(dir_path.glob(...))` at scripts/generate_doc_index.py:296 orders WindowsPath objects case-insensitively and PosixPath objects case-sensitively. The transform-doc-index hook regenerates and re-stages docs/INDEX.md on any commit that stages a docs/*.md, so a Windows commit rewrites a Linux-ordered index and the reverse. The re-staged INDEX.md is not changelog-exempt, so a known-issues-only PR trips check_changelog_presence. Verified in code and on main history 2026-09-28 (main ae85a2a1). Tracked by AC KM-300b-1 (todo)."
type: reference
category: reference
status: active
created: '2026-09-28'
last_updated: '2026-09-28'
components:
  - knowledge_management
related_docs:
  - docs/known-issues/knowledge-management.md
  - docs/known-issues/README.md
  - docs/acceptance-criteria/knowledge-management/KM-300-docs-same-everywhere/KM-300b-1.yaml
  - docs/known-issues/build-pipeline/open-high-ki-bp-20260910-1240.md
---

# KI-KM-20260928-doc-index-order-depends-on-host-os — generate_doc_index.py sorts Path objects, which compare case-insensitively on Windows and case-sensitively on Linux, so every Windows commit that stages a docs/*.md re-sorts docs/INDEX.md and main flips between the two orders

> Filed in `knowledge-management` because the generator's platform behaviour is owned there:
> the AC tree `KM-300` ("Your project's documentation map works and reads the same, whoever
> built it") holds the separator fix (`KM-300a-1`, done) and the ordering requirement
> (`KM-300b-1`, todo). Index: [knowledge-management.md](../knowledge-management.md).

- **Severity:** medium. It never loses content, but it produces a spurious `docs/INDEX.md` diff
  in unrelated commits, conflicts between branches built on different hosts, and a false CI
  failure on docs-only pull requests (see Consequences).
- **Status:** open. Covered by AC `KM-300b-1` ("Entries in the documentation map appear in the
  same order on every operating system", `readiness: approved`, `work_status: todo`), which is
  the fix's acceptance test. No ticket yet.
- **Occurrences:** 3 reports plus the main history below. Reported first by session
  leafcutter-6d (Windows 11, 2026-09-27/28; closed PR #928, carried over with its user's
  approval). Seen again by the operator on 2026-09-28: two rows swapped in a docs-only merge
  commit. Main's own history flips three times in four days (see Evidence).
- **First seen:** 2026-09-25 (first flip on main, `9363f4a2`) · **Last seen:** 2026-09-28
- **Where:** `scripts/generate_doc_index.py:296` (`files = sorted(dir_path.glob(glob_pattern))`),
  called for every multi-file category. Reached through
  `scripts/commit_guardian/transform_doc_index.py` (the `transform-doc-index` pre-commit hook,
  `.pre-commit-config.yaml:57-63`, `files: ^docs/.*\.md$`), which writes and `git add`s
  `docs/INDEX.md` (`:295`, `:206`), and through `scripts/build_phases_doc_index.py:80-85` on every
  `build.py` run.

## Mechanism (verified in code, main `ae85a2a1`)

`dir_path.glob()` yields concrete `Path` objects: `WindowsPath` on Windows, `PosixPath` on Linux.
`sorted()` uses their own comparison. `PureWindowsPath` compares case-folded strings, and
`PurePosixPath` compares the strings as they are. Checked on this Windows host:

```text
>>> sorted([Path('docs/Zeta.md'), Path('docs/alpha.md')])
[WindowsPath('docs/alpha.md'), WindowsPath('docs/Zeta.md')]
>>> sorted([PurePosixPath('docs/Zeta.md'), PurePosixPath('docs/alpha.md')])
[PurePosixPath('docs/Zeta.md'), PurePosixPath('docs/alpha.md')]
```

So a category containing both upper- and lower-case names is ordered differently depending on
the host. `docs/conventions/` (`PROJECT_CONTEXT-injection.md` next to `adr-numbering.md`) and
`docs/retrospectives/` (`EPIC-ACTraceabilityStore.md` next to `EPIC-AcPipelineDeployGaps.md`) are
the two sections where the orders differ today.

The hook's idempotency guard (write only when the content differs) does not help. Content from
the other host's order always differs, so the hook rewrites and re-stages the file.

## Evidence: main flips between the two orders

Each `docs/INDEX.md` on main was classified by checking, section by section, whether its rows are
in case-sensitive (`sorted(paths)`) or case-insensitive (`sorted(paths, key=str.lower)`) order:

| commit | date | order |
|---|---|---|
| up to `34f00d5f` (KM-300a-2) | to 2026-09-25 | case-sensitive |
| `9363f4a2` (forward-slash fix, regenerated the whole index) | 2026-09-25 | **case-insensitive** |
| through `e370636f` | 2026-09-27 | case-insensitive |
| `d4339620` (docs-only merge of two known-issues audits) | 2026-09-28 | **case-sensitive** |
| `b8d1cd16` (PR #943) | 2026-09-28 | **case-insensitive** (moves `PROJECT CONTEXT injection` below `adr numbering`, and `EPIC ACTraceabilityStore` below `EPIC AcPipelineDeployGaps`) |
| `ae85a2a1` (current main) | 2026-09-28 | case-insensitive |

The report named `e370636f` as a flip. Its `docs/INDEX.md` is in the same order as its first
parent's; that commit changed descriptions, not order. The flips are `9363f4a2`, `d4339620` and
`b8d1cd16`.

## Consequences

1. **Spurious diffs.** Every commit made on the host whose order is not main's current one, and
   which stages any `docs/*.md`, carries a re-sorted `docs/INDEX.md`. The operator saw this on
   2026-09-28 as two swapped rows in a docs-only merge commit.
2. **False changelog-presence failures.** `scripts/release/check_changelog_presence.py` exempts
   `changelogs/`, `tickets/`, `docs/acceptance-criteria/` and `docs/known-issues/`
   (`EXEMPT_PREFIXES`, `:38-43`) but not `docs/INDEX.md`. A pull request that only touches
   known-issues entries gets the hook's re-staged `docs/INDEX.md`, which counts as releasable, so
   CI asks for a changelog entry the change does not need.
3. **Merge noise.** Two branches regenerated on different hosts conflict on rows neither changed.
   The same file is also rewritten with CRLF on Windows (`KI-BP-20260910-1240`), which is a
   separate defect with the same effect.

## Detection

- `git diff docs/INDEX.md` after a docs commit shows rows moving but no row text changing.
- Compare the order of the `docs/conventions/` rows: `PROJECT CONTEXT injection` before
  `adr numbering` is the case-sensitive (Linux) order; after it is the case-insensitive (Windows)
  order.

## Workaround

Before pushing a docs-only branch, compare `docs/INDEX.md` with `origin/main`. If the only
difference is row order, restore it (`git checkout origin/main -- docs/INDEX.md`) in a final
commit that stages nothing else. The hook ignores a staged `docs/INDEX.md` on its own (it
triggers only on other `docs/*.md` files), so it does not re-sort that commit. This removes the
spurious diff from the pull request. It does not help with consequence 2 when the branch also
changes other docs, because `docs/INDEX.md` is then legitimately changed.

## Suggested fix

1. Sort by a host-independent key: `sorted(dir_path.glob(glob_pattern), key=lambda p: p.relative_to(dir_path).as_posix())`
   for byte order, or add `.casefold()` for case-insensitive order. Either is fine. `KM-300b-1`
   asks for one fixed rule, stated in the generator's documentation.
2. Pick the rule that keeps the diff smallest against current main (case-insensitive today), and
   regenerate `docs/INDEX.md` once in the fixing commit.
3. Test it the way `KM-300a-1` tested separators: substitute `PureWindowsPath` and
   `PurePosixPath` over the four file names in `KM-300b-1`'s criteria and assert one order.
4. Consider adding `docs/INDEX.md` to the changelog-presence exemptions. It is generated from the
   other docs and carries no releasable change of its own. That is a separate decision about
   `check_changelog_presence.py` and needs its own DECISION HISTORY entry.

**Pattern:** a sort that delegates to the platform's own comparison. The output is deterministic on
each host and different between hosts, and a hook that regenerates the file on every commit makes
each host undo the other's work.
