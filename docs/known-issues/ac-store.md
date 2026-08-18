---
title: "Known issues — ac-store"
description: "Open, observed defects in the ac-store component: the AC YAML store, its truth fields, the done-proof oracle, and the lifecycle scripts that transition an acceptance criterion to done. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-08-18
components:
  - ac_store
related_docs:
  - docs/how-to/prove-ac-done.md
  - docs/known-issues/build-orchestration.md
---

# Known issues — ac-store

Observed defects in this component that are **not yet fixed**. This file exists so a
defect noticed in passing can be recorded in seconds, without authoring a full
acceptance criterion for something nobody has decided to build yet.

## How to use this file

**Read it before adding new capability to this component.** Fixing what is already
broken takes precedence over building more.

**Adding an issue.** Append a new `### KI-ACS-NNN` section using the next free number.
Nothing here is generated — edit it by hand. Fill in what you actually know; an issue
recorded with a thin `Evidence` line is far better than one not recorded.

**Hitting an existing issue.** Increment `Occurrences` and update `Last seen`. Do not
add a duplicate entry. Occurrences is an escalator, not the score — a blocker seen once
outranks an annoyance seen ten times.

**Severity** is `blocker` (work cannot land) / `high` (silent wrong behaviour) /
`medium` (real but survivable) / `low` (noise, dead code, cosmetics).

**Closing an issue.** When the fix lands, delete the section and reference the issue id
in the commit message. If it earns real work, author an AC for it and note the AC id in
`Status` — this file is a capture surface, not a replacement for the AC store.

---

### KI-ACS-001 — An AC is marked `done` with no link to the code implementing it

- **Severity:** high
- **Status:** open — no AC authored yet; the semantics question below is the reason
- **Occurrences:** 12
- **First seen:** 2026-08-17 · **Last seen:** 2026-08-18
- **Where:** `scripts/ac_store/mark_ac_done.py`; also reached from
  `scripts/build_orchestration/fast_lane.py` — `_update_ac_work_status`, used by
  `mark_done_built_acs`

**Symptom.** Every automated path to `work_status: done` is status-only. Nothing
writes `implemented_by`, so an AC can assert completion with no traceable link to the
code that satisfied it — the reader has no way to check the claim.

**Evidence.** TKT-600a-1 after its fast-lane build: `work_status: done`,
`implemented_by: []`; populated by hand in `b3124ff25`. Same gap on 2026-08-17 when
the BO-2400a-3 family was marked done via `mark_ac_done.py`, which also only sets
`work_status` — so this is not specific to the fast lane.

Reproduced ten more times on 2026-08-18 (PR #485). Every one of BO-2400f-4, its six
children, BO-2400f-11, and BO-2400c-1-ii/-iii/-iv was marked done through
`mark_ac_done.py --test-root`, passed the coverage gate, and landed with
`implemented_by: []`. All ten were filled in by hand in the same commit. The
count is what makes the shape clear: this is not an occasional miss, it is the
guaranteed outcome of every automated done-transition, and the only thing
currently preventing a store full of unprovenanced dones is somebody noticing.

Worth recording precisely because the gate did its job. Coverage was verified, a
passing covers-tagged test existed for each — so the failure is not "done was
claimed falsely", it is "done was claimed truthfully and left untraceable".

**Fix direction.** Write `implemented_by` at mark-done time from the evidence already
in hand (the coder phase reports `files_modified`; `done_proof` already resolves the
covering test). Note this is a **provenance-semantics decision, not a mechanical
one** — what `implemented_by` must contain for a claim of done to be trustworthy is
the owning question, and it should be settled here rather than in each call site.

**Provenance.** Originally recorded as KI-BO-002 in
`docs/known-issues/build-orchestration.md` because it was found during a fast-lane
run. Refiled here on 2026-08-18: the call site is in `fast_lane.py`, but the
semantics of `implemented_by` and of what "done" must prove belong to this
component, not to the lane that happens to invoke it.
