---
title: "docs(known-issues): repair the KI-BO-019/020 duplicate that reached main, and file five findings from the session that found it"
date: "2026-08-25"
time: "17:30"
type: manual
components: 
  - ac_store
  - build_orchestration
  - build_pipeline
  - commit_guardian
summary: "Fixed a case where two different fixes accidentally got the same tracking number, and wrote down five other problems noticed while investigating it so they get fixed on purpose instead of by accident."
description: "No production code. origin/main carried two KI-BO-019 and two KI-BO-020: PR #538 landed its pair at 14:51 UTC, PR #539 landed its pair at 15:09 UTC having checked free numbers at ~14:40. #538 was first and keeps the numbers; #539's entries move to KI-BO-022 (CRLF record rewritten LF end-to-end) and KI-BO-023 (ValueError escapes all three call sites) -- KI-BO-021 unaffected. The rename carries the test file (test_ki_bo_020_... -> test_ki_bo_023_...) and its 21 internal references, plus a dated Correction paragraph appended to each of the two already-merged changelog entries whose pointers had gone stale (those two entries are not rewritten). Five findings filed: KI-BO-024 (the 'append the next free number' convention cannot work under concurrent agents -- 9 collisions in one day, this one landing inside the window between the final origin/main check and the merge; a duplicate-heading CI check is the cheapest fix and the only one that would have caught this before it landed); KI-CG-015 (declares_side_effect is hand-authored by the IT-PO pass and separately derived by check-ac-schema, and a read-only sweep of all 3,338 AC records found 38 carrying the field, 9 disagreeing, all nine in the same direction -- authored true, derives false -- naming all nine including BO-2900g-2, the AC that establishes the derive-never-author rule); KI-BP-013 (the mypy CI gate checks only changed files, so a 2-line chmod change in PR #541 inherited 22 pre-existing errors, confirmed via mypy against origin/main's unmodified copy of the same file); KI-BP-014 (the commit agent stalled ~76 minutes waiting on the autofix agent it dispatched, with staged state intact but no commit, no error, and no signal distinguishable from still-working); KI-BP-015 (docs/agents/cards/*.card.md are committed build outputs with no freshness gate -- running build.py into a clean worktree from origin/main added 63 lines across four cards, all criteria already merged in #529/#534/#536 whose PRs never regenerated them; filed rather than fixed). AC_ENFORCE_STRICT=1 pytest unit_tests/build_orchestration/ -> 158 passed, 4 xfailed, 4 subtests passed. No KI-BO number appears twice; no stale KI-BO-019/KI-BO-020 reference remains under unit_tests/."
breaking: false
---

## Entry

`origin/main` carried two `KI-BO-019` and two `KI-BO-020`. PR #538 landed its
pair at 14:51 UTC; PR #539 landed its own pair at 15:09 UTC, having checked
the free numbers against `origin/main` at roughly 14:40 — before #538 merged.
#538 was first, so it keeps the numbers. #539's entries move:

- `KI-BO-019` ("a CRLF-encoded AC record is rewritten LF end-to-end by a
  single `work_status` flip") → **`KI-BO-022`**.
- `KI-BO-020` (`_update_ac_work_status` can raise `ValueError`, and all three
  call sites catch only `OSError`) → **`KI-BO-023`**.
- `KI-BO-021` is unaffected.

The rename carried a test file
(`test_ki_bo_020_valueerror_escapes_call_sites.py` →
`test_ki_bo_023_valueerror_escapes_call_sites.py`) and its 21 internal
references, plus two already-merged changelog entries whose pointers had
gone stale. Those two entries are **not** rewritten — each gets a dated
"Correction" paragraph stating the mapping, so the text as published stands
and the trail from old id to new id is followable without editing history
out from under a reader.

### Four findings, filed rather than fixed

- **`KI-BO-024`** — "append the next free number" is not a workable id
  convention under concurrent agents. Nine collisions in one day, one of
  which reached `main`. The timeline shows the collision landing *inside the
  window between the final `origin/main` check and the merge* — the
  documented defence (re-read against `origin/main` at the moment of
  landing) is a time-of-check-to-time-of-use race, and narrowing the window
  does not close it. Three fix directions are named, cheapest first; a
  duplicate-heading check in CI is the only one of the three that would have
  caught this specific collision before it landed.
- **`KI-CG-015`** — `declares_side_effect` is hand-authored by the IT-PO
  enrichment pass and separately derived by `check-ac-schema`, and on
  records about durable writes the two systematically disagree. A read-only
  sweep of the whole store (3,338 records) found 38 carrying the field, 9
  disagreeing, and all nine in the same direction: authored `true`, derives
  `false`. That one-directional result is what turns this from "the pattern
  is too narrow" into "the authoring step is writing a derived field by
  opinion" — a too-narrow regex would produce disagreements in both
  directions. Nine live landmines are named, each waiting to block the next
  commit that happens to touch that file. `BO-2900g-2` — the AC that
  establishes the derive-never-author rule this violates — is itself one of
  the nine.
- **`KI-BP-013`** — the mypy CI gate type-checks only the files a PR
  changed, so debt in an untouched file is invisible until an unrelated edit
  inherits it whole. A 2-line `chmod` change in PR #541 produced 22 mypy
  errors scattered across a 1,300-line file; confirmed pre-existing by
  running mypy against `origin/main`'s unmodified copy of the same file —
  same 22 errors, same file, mypy green on `main` only because `main` never
  touches it.
- **`KI-BP-014`** — the commit agent can stall indefinitely waiting on the
  autofix agent it dispatched. Observed at roughly 76 minutes: the staged
  state was intact and nothing was lost, but there was no commit, no error,
  and nothing in the agent's own status message that a caller could
  distinguish from "still working."
- **`KI-BP-015`** — `docs/agents/cards/*.card.md` are committed build
  outputs with no freshness gate. Running `build.py` into a clean worktree
  taken from `origin/main`, changing nothing else, produced 63 added lines
  across four cards: acceptance criteria already merged in #529, #534 and
  #536 whose PRs never regenerated the cards. `Check Agent Diagrams`
  validates card *structure*, not card *currency*, so nothing noticed. These
  cards are a knowledge-plane surface — an agent reads its own card to learn
  which criteria it owns — so a stale card is quietly wrong exactly when it
  is being trusted. Filed rather than fixed: regenerating is one command,
  but doing it here would bury a 63-line generated diff in an unrelated
  review and would repair this instance without preventing the next.

### The through-line

Four of these five findings are the same shape: **a check that only
inspects what a commit touched cannot see debt in what it doesn't.** The
AC-schema disagreements, the mypy errors, the stale agent cards, and the
stale `KI-BO` references all sat unnoticed for the same reason and all
surfaced on the same day — the day something happened to touch those
specific files. `KI-BO-024` is the odd one out: it is not a blind spot in a
gate but a race in the authoring convention itself, and it is the one that
reached `main`.

### Verification

- `AC_ENFORCE_STRICT=1 pytest unit_tests/build_orchestration/` → 158 passed,
  4 xfailed, 4 subtests passed.
- No `KI-BO` number appears twice in `docs/known-issues/`; no stale
  `KI-BO-019` / `KI-BO-020` reference remains anywhere under `unit_tests/`.
