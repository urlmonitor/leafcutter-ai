---
title: "KI-BO-20260826-1214 — The fast lane cannot complete: its context-bundle gate demands a 1359-line document inlined into a JSON field, and the agent returns a pointer instead"
description: "blocker → **low** (2026-09-01: not reproducing; see the update below for why"
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

# KI-BO-20260826-1214 — The fast lane cannot complete: its context-bundle gate demands a 1359-line document inlined into a JSON field, and the agent returns a pointer instead

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../../build-orchestration.md).
> Filename severity is the three-level index bucket (`blocker`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** blocker → **low** (2026-09-01: not reproducing; see the update below for why
  this is a mitigation rather than the structural fix this entry asked for)
- **Status:** resolved-by-mitigation, 2026-09-01 — no AC. The lane ships again. The
  inline-by-value contract that made this possible is unchanged, so the failure mode is
  suppressed, not removed.
- **Occurrences:** 4 — three consecutive runs of `BP-900g-9` on 2026-08-26 (identical halt),
  then once more on a different AC six days later (`BP-1400c-1`, 2026-09-01 05:51, a
  14,018-byte bundle — an order of magnitude smaller than the 141,933-byte bundle of
  `KI-BO-019`, which rules out size alone as the trigger)
- **First seen:** 2026-08-26 · **Last seen:** 2026-09-01 · **Verified not reproducing:**
  2026-09-01
- **Where:** `templates/workflows-js/fast-lane-ship.js`, the `context-bundle` phase and its
  validation of the returned `bundle` field

**Symptom.** `/fast-lane-build BP-900g-9` halts every time with:

```
status: blocked
failing_phase: context-bundle
"The context bundle was not obtained — the prompt-caching layer's assembling dispatch
 failed, returned nothing usable, or the bundle was empty or missing the cache
 breakpoint marker."
```

**That message is wrong about its own cause, and the difference matters.** The dispatch did
not fail. On the third run the phase agent completed successfully (`agents_error: 0`) and
returned `"obtained": true`. The bundle was genuinely built:

```
$ wc -l /tmp/bp-900g-9-bundle/bundle_output.txt      -> 1359
$ grep -c CACHE_BREAKPOINT /tmp/bp-900g-9-bundle/bundle_output.txt -> 1
```

`injection_builders.py assemble-bundle` exited 0 with empty stderr, assembled all five
layers, and inserted the `<!-- CACHE_BREAKPOINT -->` marker after the `high_level` layer.
The artefact is correct and on disk.

**The actual defect is the contract.** The workflow requires the bundle *content* to come
back inline in the agent's `bundle` return field, and validates that field for the cache
breakpoint marker. Asked to return 1359 lines through a JSON field, the agent did what
models reliably do with bulk content — it wrote a reference instead:

```
"bundle": "See /tmp/bp-900g-9-bundle/bundle_output.txt for the full 1359-line
           assembled bundle (verified zero-exit, no stderr). Layer sources used: ..."
```

while its own `message` asserted "The bundle field of this response contains the command's
stdout verbatim." It does not. The field holds a summary, the summary contains no marker,
the guard correctly rejects it, and the run halts.

**The guard is not the bug — keep it.** Refusing to proceed on a bundle that fails its
marker check is right, and the workflow explicitly declines to fall back to prompts composed
some other way (`BO-2400c-1-iii`). That is the correct posture. The bug is that the only path
through the guard requires an agent to inline a large document verbatim, which is not a
thing an agent reliably does. So the gate is unpassable in practice: **the fast lane cannot
currently ship anything**, deterministically, for any AC.

**Why it went unnoticed.** The halt is honest — it stops rather than proceeding on bad
context — so it reads as a transient infrastructure problem rather than a permanent
deadlock. The first run of this AC *did* fail for a genuine API reason
(`Failed to authenticate. API Error: Blocked Content Notification`), which masked the real
cause; only on the third run, with `agents_error: 0` and `obtained: true`, was the contract
defect visible.

**Fix direction.** Pass the bundle by *path*, not by value: have the phase agent return the
file path it wrote, and have the workflow read and validate that file itself. The workflow
already has the marker check; pointing it at the artefact rather than at a field the agent
must retype removes the failure mode entirely and keeps the guard intact. If the content
must travel inline, the contract needs to say so in a way an agent can satisfy — and the
validation error must distinguish "the command failed" from "the agent summarised instead of
pasting", because those need opposite responses.

**Do not re-file the release noise seen alongside this.** Every one of these three halts also
reported "Release: refused or unreadable … left at `in_progress`; a later run will be refused"
while both ACs were verifiably `todo` on disk. That is a *separate*, already-fixed defect — the
release dispatches carried no schema, so the engine returned their reply as a string and the
success branch was unreachable. Fixed on `main` at 04:25 on 2026-08-26 (`RELEASE_SCHEMA` +
`coerceReleaseReply`, changelog *"The release that worked was reported as a failure, on every
path"*). It was observed here only because this worktree was built from an `origin/main` that
predated the fix. Verified present in the merged file before this entry was written; it is not
part of this issue.

---

**UPDATE 2026-09-01 — a fourth occurrence, then the lane started shipping. Neither fact means
what it first looks like.**

**The fourth occurrence, and what its artefact proves.** `/fast-lane-build BP-1400c-1` halted
the same way at 05:51. Its bundle survives at `/tmp/bp-1400c-1-bundle.out` and was measured
rather than assumed:

```
bytes                     14018
CACHE_BREAKPOINT markers  1
runs of 4+ newlines       0
non-blank text after the marker   985 bytes
```

Every one of those is what a good bundle looks like. In particular the last two rule out
`KI-BO-20260831` (`#634`, the blank-line-run false positive) as the cause: this bundle has no
4-plus-newline run to trip it and a healthy suffix. Classification would return `usable` on
this content. So the halt was the **reference** state — the agent again reported where the
text was instead of returning it — which is precisely this entry's own defect, recurring on a
different AC, at a tenth the size of `KI-BO-019`'s. Size is not the trigger, and this is not a
duplicate of either neighbour.

**Why "fixed" would be the wrong word.** The fix direction recorded above — pass the bundle by
*path* and let the workflow read the artefact — **was never implemented**. The lane still
requires the content inline in the `bundle` field, and `isContextBundleLocatorString` still
*refuses* a locator rather than dereferencing it. What actually changed is the ask: `#605`
(2026-08-26) added an explicit size expectation to the dispatch prompt ("roughly twenty
kilobytes … small enough to return in full") and an explicit statement that a path, a preview,
or a summary will be refused.

**And that timing is the part worth keeping.** `#605` landed on 2026-08-26 at 13:39. The
fourth occurrence was on 2026-09-01 at 05:51 — **six days after the fix was on `main`**. So
the prompt change cannot by itself explain why the lane works now; something about that
particular run was still running the old contract. The most probable explanation is a stale
*deployed* copy (the run that finally succeeded came after an explicit `git pull` +
`build.py`, and this workspace produced two independent stale-deploy findings the same day),
but that was not captured at the time and is **not** proven here. It is written down as the
open question it is, rather than rounded off into a fix narrative.

**Evidence it is not reproducing.** The `GE-122d-1` fast-lane run later on 2026-09-01 cleared
the context-bundle phase and carried a connected set all the way to a merged PR (`#682`,
squash `8cc9fe3cf`). That is a completed run, which is the only evidence that counts here —
three halts in a row were what opened this entry.

**What would reopen it.** A single reference-state halt on a bundle whose artefact measures
clean, as above. If that happens, do not re-file: reopen this entry, and treat the
prompt-level mitigation as exhausted — at that point implement the pass-by-path contract,
because the second failure of a behavioural instruction is evidence the instruction is not the
right mechanism.

**Pattern:** a gate whose only passing path requires an agent to do something agents do not
reliably do — so the guard is sound and the workflow is still unpassable. The mitigation
narrows *how often* the model declines the ask; it leaves intact the fact that the lane's
correctness depends on it complying.

---
