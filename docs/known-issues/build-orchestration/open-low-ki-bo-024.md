---
title: "KI-BO-024 — \"Append the next free number\" is not a workable id convention under concurrent agents, and on 2026-08-25 it finally shipped a duplicate to `main`"
description: "KI-BO-024 — \"Append the next free number\" is not a workable id convention under concurrent agents, and on 2026-08-25 it finally shipped a duplicate to `main`"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-024 — "Append the next free number" is not a workable id convention under concurrent agents, and on 2026-08-25 it finally shipped a duplicate to `main`

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open — the immediate duplicates are repaired; the convention that produced them is not
- **Occurrences:** 10 in a single day (2026-08-25), of which 1 reached `main`
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-25

**Tenth occurrence, 2026-08-25 — this entry predicted it and then it happened here.** A triage
authored `KI-BO-025` against an `origin/main` that had no 025; by the time that branch rebased,
another session had landed 025, 026 and 027. Renumbered to `KI-BO-028` with four inbound
references updated. Caught by a git merge conflict, which is luck rather than a check: the two
sides appended to the same region of the same file. Had they appended to *different* registers,
or had either landed via a path that auto-merges cleanly, the duplicate would have reached
`main` exactly as the 019/020 pair did. This is the fourth id space to collide in one day
(`KI-BO`, `GE-120`, `BP-900h-4/-5`, and the AC store's own `ACD-1200a`), which is the argument
for option 3 below — a duplicate-heading check is cheap and is the only one of the three that
fires without depending on where the collision happens to land.
- **Where:** the "Adding an issue" instruction at the top of every `docs/known-issues/*.md`

**Symptom.** The convention says to append using "the next free number". A branch reads the
file, picks the next number, and by the time it lands that number is taken. There is no
reservation, no allocator, and no check — the number is chosen against a snapshot and
validated by nothing.

**This is no longer a near-miss.** Every prior occurrence was caught by re-reading
`origin/main` immediately before landing. On 2026-08-25 that defence failed for the first
time, because the collision landed *inside the window between the final check and the merge*:

| | |
|---|---|
| PR #539 renumbered 017/018/019 → **019/020/021**, checked against `origin/main` at `eed3601c` | ~14:40 UTC |
| PR #538 merged, publishing **its own** KI-BO-019 and KI-BO-020 | 14:51 UTC |
| PR #539 merged | 15:09 UTC |
| `main` now carries two KI-BO-019 and two KI-BO-020 | — |

Repaired by this entry's PR: #538 was first and keeps the numbers; #539's entries moved to
`KI-BO-022` and `KI-BO-023`, taking a test filename and its 21 internal references with them,
plus two published changelog entries whose pointers had gone stale.

**Nine occurrences in one day.** `KI-BO-008 → 014 → 015`; `KI-CG-010 → 012`; `KI-BO-016/017/018
→ 017/018/019 → 019/020/021 → 022/023`. Three of those were *second* renumbers — the file moved
again while the first renumber was being written.

**Why the current defence cannot be made to work.** "Re-read the free number against
`origin/main` at the moment of landing" is already written into this file (under KI-BO-014) and
was followed. It is a time-of-check-to-time-of-use race, and the window is the merge queue.
Narrowing it does not close it. There is also no way to see numbers reserved in a *branch* or
in someone's uncommitted working copy — while writing this entry, two candidate numbers had to
be skipped because a concurrent session held them uncommitted, which no amount of checking
`origin/main` would have revealed.

**The cost is not the renumbering.** It is that every reference goes stale at once: section
headings, `# covers:` tags, test filenames, cross-references between entries, commit messages,
and already-merged changelog entries. The 019 → 022 move above touched four files and 20-odd
references, and a missed one silently points a reader at someone else's defect.

**Fix directions, cheapest first.**

1. **Make the number non-sequential.** A date-plus-slug id (`KI-BO-20260825-crlf-rewrite`) cannot
   collide, needs no allocator, and no coordination. Loses ordering, which the file does not
   currently preserve anyway — `main` today lists 016 between 013 and 014.
2. **Allocate at merge, not at authoring.** Author with a placeholder and have a hook or the
   merge queue assign the number. Removes the race but needs tooling and rewrites references.
3. **Detect rather than prevent.** A pre-commit hook and CI check that fails on a duplicate
   `### KI-XX-NNN` heading in any known-issues file. This does not stop the collision, but it
   turns a silent duplicate on `main` into a blocked merge, and it is a few lines. **Worth doing
   regardless of which of the above is chosen** — it is the only one of the three that would
   have caught 2026-08-25 before it landed.

---
