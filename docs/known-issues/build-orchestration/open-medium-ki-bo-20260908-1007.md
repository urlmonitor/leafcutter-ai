---
title: "KI-BO-20260908-1007 — `files_touched` is scraped from AC prose and fed to the parallelism gate as fact, and no ticket declares its tests at all"
description: "KI-BO-20260908-1007 — `files_touched` is scraped from AC prose and fed to the parallelism gate as fact, and no ticket declares its tests at all"
type: reference
category: reference
status: active
created: '2026-09-28'
last_updated: '2026-09-28'
components:
  - build_orchestration
  - ac_store
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-20260908-1007 — `files_touched` is scraped from AC prose and fed to the parallelism gate as fact, and no ticket declares its tests at all

> Found 2026-09-07/08 while amending `GE-122d-1`. Filed 2026-09-28 after
> re-confirming against `origin/main` at `89613071`: `_extract_paths_from_prose`
> is still the derivation, and `documentation-expert`'s template still never
> mentions the format it must produce.

- **Severity:** medium — the prose-scraping half is confirmed; the collision-blindness
  half is structural and store-wide
- **Status:** open — no AC
- **Occurrences:** 1 confirmed wrong entry (`GE-122d-1`); the missing-tests condition is
  store-wide
- **First seen:** 2026-09-07 · **Last seen:** 2026-09-28 (re-verified present)
- **Where:** `scripts/ac_store/generate_ticket_from_ac.py` — `_build_files_touched()`,
  `_extract_paths_from_prose()`, `_EDIT_SURFACE_RELATIONSHIPS` ·
  `templates/workflows-js/build-feature.js` batching ·
  `templates/agents/python-coder.md` §"File-Size Limit"

**`files_touched` is not declared anywhere.** There is no `files:` field on an AC — the AC
schema sets `additionalProperties: false` over 44 named properties and none of them is
`files`. The ticket's list is DERIVED at generation time from two sources:

1. `doc_links` entries whose `relationship` is in `_EDIT_SURFACE_RELATIONSHIPS`
   (`constrains`, `creates`, `implements`, `modifies`, `specifies`); `describes` and
   `context` are informational and excluded.
2. **Path tokens regex-scraped out of `it_requirements` prose** by
   `_extract_paths_from_prose()`, existence-gated against the repo.

**Source 2 is the defect.** Any on-disk path mentioned in an it_requirement SENTENCE becomes
an edit-surface declaration, regardless of what the sentence says about it. `GE-122d-1` is the
worked example: every one of its `doc_links` carried `describes`/`context`, so source 1
contributed nothing, and its entire `files_touched` — the single entry
`scripts/build_phases.py` — existed because a regex lifted the string out of a sentence whose
actual claim was that the file might NOT need touching ("or be placed where both already
resolve"). Three agents independently confirmed the file needed no edit. The declaration was
never a declaration; it was a mention.

**Why that is not cosmetic.** `/build-feature` batches tickets whose `files_touched` are
DISJOINT and dispatches the batch in parallel into ONE shared worktree. The list is the input
to a concurrency decision, and its two failure directions are not symmetric:

- **Omitting a file** → two genuinely colliding tickets are dispatched together. There is no
  commit-phase lock in that worktree (`KI-BO-20260901-0920`), so the only thing preventing a
  cross-contaminated commit is the commit agent's pathspec convention.
- **Naming a file the ticket does not touch** → tickets that could safely run together are
  serialised. Cheap, and self-correcting.

The first is a correctness property; the second is a performance cost. Today the field is
treated identically for both.

**THE PROOF IS INVISIBLE TO THE GATE, STORE-WIDE — the larger half.** Zero records across the
whole `guardrail-engine` component put `unit_tests/` paths in `doc_links`. The store's
convention is that proof lives in `covered_by` and `test_spec`, neither of which
`_build_files_touched()` reads. So **no ticket in this store declares its test files as an
edit surface**, and the parallelism gate cannot see a test-file collision for ANY ticket — two
tickets editing the same test module batch as disjoint. The prose-scraping bug produces wrong
entries; this produces a whole missing CATEGORY of entries, silently, everywhere.

**And the file-size limit guarantees drift in the other direction.** `build.py` reads a Python
file-size limit from `commit_guardian.json` and injects it into agent templates as
`{{config.file_size_limit_py}}`. `python-coder` carries a behavioural pattern that fires when
a new `.py` would exceed it: the implementation splits into an additional file, chosen at
IMPLEMENTATION time — after generation, after batching. So the derived set is systematically
incomplete for exactly the tickets whose implementations grow. No split-caused instance has
been observed yet; the mechanism is certain and the consumer is a correctness gate, which is
why this is filed before a failure rather than after.

**Three candidate designs, none obviously right — which is why this wants an AC, not a patch:**

1. **The coder amends `files_touched` when it splits, and the gate re-checks.** Keeps the
   field authoritative, but makes a phase agent mutate the input to a decision already taken —
   the batch is formed before the coder runs.
2. **The gate treats `files_touched` as advisory and derives the real set from the diff at
   commit.** Honest about what is knowable when, but moves collision detection after the
   collision.
3. **Record the delta explicitly** — the prediction stays and any divergence is reported.
   `change-scope-reviewer` already does something close; the gap is that nothing feeds its
   finding back to batching.

**A caution against the tempting cheap fix.** Retro-editing `files_touched` on the TICKET to
match the diff makes every record look correct, destroys the signal that the derivation was
wrong, and — because the field is generated — puts the ticket permanently out of step with
what regenerating it from its AC would produce. Fix the AC side (`doc_links` relationships and
the it_requirement prose) and let the ticket derive; record the change via `amended_by`.

**Pattern:** a value that is inferred at write time and read as a declaration at decision time,
with no marker distinguishing the two.

**Related.** `KI-BO-20260901-0920` (the missing commit lock — why an over-optimistic batch is
dangerous rather than merely wasteful). User-memory `feedback_files_touched_drives_surface`
(wrong `files_touched` → phantom-done: the same field failing a different consumer).
