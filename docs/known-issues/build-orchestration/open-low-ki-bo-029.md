---
title: "KI-BO-029 — The fast lane stages with `git add -A` into a worktree its own bootstrap already dirtied, so every fast-lane PR silently carries unrelated generated diff"
description: "KI-BO-029 — The fast lane stages with `git add -A` into a worktree its own bootstrap already dirtied, so every fast-lane PR silently carries unrelated generated diff"
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

# KI-BO-029 — The fast lane stages with `git add -A` into a worktree its own bootstrap already dirtied, so every fast-lane PR silently carries unrelated generated diff

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open — no AC
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `templates/workflows-js/fast-lane-ship.js:916-920` (Commit phase, Step 2) interacting with `scripts/setup_ticket_worktree.py`'s bootstrap `build.py` run

**Symptom.** A fast-lane worktree is dirty from birth. `setup_ticket_worktree.py` runs
`build.py` as part of bootstrap, which regenerates `docs/agents/cards/*.card.md` (the drift
recorded as **`KI-BP-015`**). No agent has run yet and the tree already has modified tracked
files. The Commit phase then stages with `git add -A`, so that churn lands inside the pull
request the lane opens.

**Evidence.** Three independent worktrees created on 2026-08-25, all off `origin/main`, all
dirty immediately after bootstrap with no agent having touched anything:

```
worktrees/knowledge-harvest-wiring   4 cards modified
worktrees/fastlane-ki-findings       4 cards modified
worktrees/inf-400c-2-ii              7 files: docs/INDEX.md + 6 cards   (+119 / -4)
```

The third is a real `/fast-lane-build INF-400c-2-ii` run. At the point that run halted in
review, `git status` showed the seven unrelated files alongside the three the build actually
authored. The lane halted before Step 2, so **the `add -A` sweep specifically** is not observed
in a landed commit — but the code path is unconditional, so a run that reaches commit will
include them.

**A second, independent path produces the same outcome, and this entry's own commit hit it.**
The commit that added this section staged exactly three `docs/known-issues/` files; four landed.
The `transform-doc-index` pre-commit hook regenerated `docs/INDEX.md` and added it to the index
mid-commit. The regenerated line was an unrelated doc's description
(`adopt-consolidated-output-root`: `"How to adopt…"` → `"Overview of How to adopt…"`), nothing to
do with the change being committed.

That is worth more than a footnote, because `docs/INDEX.md` is **not** in
`check_changelog_presence.py`'s `EXEMPT_PREFIXES`. A PR consisting solely of exempt
known-issues edits was therefore failed by the required `Changelog entry present` gate, naming
`docs/INDEX.md` as the sole releasable file — a gate failure caused entirely by a hook's own
output. So the family has two mechanisms, not one:

| Mechanism | Stages | Reaches |
|---|---|---|
| bootstrap `build.py` + fast lane `add -A` | agent cards, `docs/INDEX.md` | fast-lane PRs |
| `transform-doc-index` hook auto-add | `docs/INDEX.md` | **any** commit touching docs |

The second affects every commit, not just fast-lane ones, and converts an exempt PR into a
non-exempt one. Workaround used here: `git restore docs/INDEX.md` and re-commit with
`SKIP=transform-doc-index`. Either add `docs/INDEX.md` to `EXEMPT_PREFIXES` or stop the hook
auto-staging a file the author did not touch.

**`add -A` is deliberate, which is why this is not a one-line fix.** The comment at
`fast-lane-ship.js:796-802` explains it: the Changelog phase writes `emit_entry.py` output to
disk uncommitted, and relies on the Commit phase's `add -A` to pick it up so the entry lands in
the PR's own diff rather than a follow-up commit. Narrowing the stage to the coder's
`files_modified` would drop the changelog entry. The fix has to stage a computed set —
`files_modified` ∪ the changelog path ∪ the claimed AC files — not simply narrow `add -A`.

**Why it matters more than the diff size.** The commit message is a fixed template:
`"feat: fast-lane build of ${targetAc} connected set (N ACs)"`, immediately followed by the
instruction *"Every claim in the commit message must be verifiable in the staged diff."* The
message cannot describe card regeneration because it is generated before the diff is known, so
every affected PR ships a diff its own message does not account for — the failure this repo
codifies as a hard rule in `CLAUDE.md` → "Commit messages must match the diff", and the same
shape as the `EPIC-PhantomDoneFilesTouched` KI-4 postmortem that rule came from.

It also silently launders `KI-BP-015`. That entry is rated **low** on the reasoning that the
cards merely drift; if the fast lane regenerates and commits them as a side effect of unrelated
work, the drift is repaired at random intervals by PRs that never mention it, which makes the
drift harder to reason about rather than easier.

**Fix direction.** Either (a) stage a computed path set in Step 2 and drop `add -A`, or
(b) have the bootstrap leave a clean tree — `git restore docs/agents/cards/` after the
bootstrap `build.py`, which is already the manual workaround prescribed at
`build-pipeline.md:162`. (b) is smaller and also fixes the same sweep for `/build-feature`
worktrees; (a) is the one that makes the lane's staging honest regardless of what dirtied the
tree. They are complementary, not alternatives.

**Related:** `KI-BP-015` (the card churn itself, occurrence count raised to 3 by this run),
`KI-BP-016` (the `docs/INDEX.md` case, which is destructive rather than additive and also
appeared in the `inf-400c-2-ii` worktree; `KI-BP-001` describes the same defect but is marked a
duplicate of 016, so 016 is the one to fix).

---

> **Entries `KI-BO-030` and `KI-BO-031` are recovered from an unmerged branch** — PR #495's
> parallel known-issues register, discarded during reconciliation. See the equivalent note in
> `commit-guardian.md` for the full provenance. Both were re-verified against `main` at
> `37655862` before filing. A third entry from that set was **dropped as fixed**: it reported
> `docs/agents/cards/*.card.md` failing `check-doc-frontmatter` with *"unknown doc type: card"*,
> and `card` is now a valid type in `config/doc_types.json` — running the hook against
> `docs/agents/cards/ac-validator.card.md` exits 0. A fourth (card drift on every build) is
> already covered by `build-pipeline.md`'s `KI-BP-002` and was folded in there as an occurrence
> rather than duplicated here.

---
