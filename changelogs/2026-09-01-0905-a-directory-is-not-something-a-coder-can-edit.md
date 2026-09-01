---
title: "A directory is not something a coder can edit"
date: "2026-09-01"
time: "09:05"
type: manual
components:
  - ticket_creation_pipeline
summary: "The prose-path gate in generate_ticket_from_ac asks `is_file()` instead of `exists()`, so a bare directory named in an it_requirements bullet is no longer written into a generated ticket's files_touched. Across the 32 real GE-123 records this removes every bare directory and every nonexistent path, while a real source file named only in prose is still kept — preserving TKT-500f-8-i, which the previously-attempted fix would have falsified."
description: "TKT-600a-1, whose files_touched half had been marked done since 2026-08-11 while never being implemented. The original covering test passed on unfixed code because its fixture paths (src/foo.py, deploy/foo.py) do not exist on disk, so the pre-existing on-disk existence gate — not the restriction the AC asked for — is what removed them. The consequence was observed rather than predicted: the unfixed extractor produced the surfaces for EPIC-SuppressionNarrowsNeverDisables and 10 of its 27 tickets were unusable, stopping a /build-feature drive mid-run before any coder phase executed. THE FIX IS ONE LINE. _is_real_prose_path gated on Path.exists(), which is True for directories, so a bullet naming docs/acceptance-criteria or templates/skills to describe WHERE a rule applies made those directories the declared edit surface. It now gates on is_file(). The discrimination stays mechanical — it asks a property of the filesystem, never of the sentence's intent. Measured against the 32 real on-disk GE-123 records: zero bare directories, zero nonexistent paths, down from three bare directories on the single bullet that stopped the drive. Mutation-proved: restoring exists() turns two tests red. WHAT WAS REJECTED, AND WHY IT MATTERS MORE THAN THE FIX. Two earlier attempts are recorded in the AC rather than left in workflow transcripts. (1) A nine-pattern English cue blocklist skipping a bullet on phrases like 'do not edit' or 'context only'. It fires on no cue in the real failing bullet — a plain instruction — so the output was unchanged, and it introduced new false exclusions that dropped real surfaces. (2) Dropping prose harvesting entirely, so files_touched comes only from structured sources. This made TKT-600a-1 pass and falsified TKT-500f-8-i — readiness approved, work_status done, priority high — whose criteria require the opposite: that a source path named in a prose bullet IS extracted. Its covering test went red, and the proposed remedy was to retire that test, which would have left an approved AC claiming done for behaviour the code no longer had: phantom-done produced by the fix for a phantom-done defect. THE AC'S CRITERIA WERE NARROWED, not quietly reinterpreted. They now ask a filesystem question rather than an intent question, and they state what is given up: an illustrative path that both has an extension and exists on disk is still harvested. The one test asserting that case is retained as xfail(strict) citing the amendment, not deleted — a deleted test is an invisible gap, and strict means the run goes red if it ever starts passing. The parent TKT-600a stays todo with its only child done, with a note saying why, because the L1's broader promise is not yet met. This fix removes the garbage from files_touched; it does not invent surfaces for records that never declared one — seven GE-123 leaves still resolve empty, which is the honest answer and is fixed separately by adding structured doc_links upstream."
breaking: false
---

## Entry

`_is_real_prose_path` gated on `Path.exists()`. That is `True` for directories.

So an `it_requirements` bullet naming `docs/acceptance-criteria` or `templates/skills` to describe *where* a rule applies made those directories the ticket's declared edit surface. The gate meant to filter illustrative paths waved them through **precisely because they exist**.

```diff
-    return (worktree_root / token).exists()
+    return (worktree_root / token).is_file()
```

A directory is not something a coder can edit. The discrimination stays mechanical — it asks a property of the filesystem, never of the sentence's intent.

### Measured against the real records, not fixtures

All 32 on-disk `GE-123` records:

```
BARE DIRECTORIES   : none
NONEXISTENT PATHS  : none
```

The single bullet that stopped the `EPIC-SuppressionNarrowsNeverDisables` drive went from three bare directories to the one real file. Mutation-proved: restoring `exists()` turns two tests red.

### Why the AC had been "done" since 11 August without being implemented

Its covering test used fixture paths — `src/foo.py`, `deploy/foo.py` — that **do not exist on disk**. So the pre-existing existence gate removed them, not the restriction the AC asked for. The test passed identically on unfixed code.

The cost was not hypothetical: 10 of 27 tickets in a real epic were unusable, and the drive halted before any coder phase ran.

### Two rejected approaches, recorded in the AC

| Attempt | Outcome |
|---|---|
| Nine-pattern cue blocklist (`do not edit`, `context only`, …) | Fires on **no cue** in the real failing bullet. Output unchanged. Added new false exclusions that dropped real surfaces. |
| Drop prose harvesting entirely | Passed this AC and **falsified `TKT-500f-8-i`** — approved, done, high — which requires the opposite. |

The second is the instructive one. Its covering test went red, and the proposed remedy was to retire that test — which would have left an approved AC claiming `done` for behaviour the code no longer had. Phantom-done, produced by the fix for a phantom-done defect.

### What was given up, said out loud

The criteria were **narrowed**, not quietly reinterpreted. They now ask a filesystem question instead of an intent question, and they name the case that escapes: an illustrative path that *both* has an extension *and* exists is still harvested.

That test is kept as `xfail(strict=True)` citing the amendment rather than deleted. A deleted test is an invisible gap; `strict` means the run goes red if it ever starts passing, forcing the note to be revisited rather than quietly outlived.

The parent `TKT-600a` stays `todo` with its only child `done`, with a note saying why — its broader L1 promise is not yet met.

### What this does not fix

Seven `GE-123` leaves still resolve to an empty surface. That is the **honest** answer: those records never declared one. Removing the garbage and supplying the missing structured `doc_links` are two different repairs, and only the first is here.
