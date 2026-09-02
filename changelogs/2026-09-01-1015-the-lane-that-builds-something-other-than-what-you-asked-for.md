---
title: "The lane that builds something other than what you asked for"
date: "2026-09-01"
time: "10:15"
type: manual
components:
  - build_orchestration
  - build_pipeline
breaking: false
summary: "Two register entries, neither in the change being made when they were found. KI-BO-032 (new, high): /fast-lane-build takes no AC argument at all, so naming an AC that is not readiness: approved silently builds a different batch and reports success — measured, five unrelated ACs against the one requested, zero overlap. KI-BP-016 gains a second occurrence and loses its rotted line citations."
description: "KI-BO-032 — fast-lane-build.js hardcodes select_batch --ac-root --limit N and never receives the AC id an operator names. select_batch filters on _is_approved, so any AC that is not readiness: approved is invisible to it and the lane quietly builds whatever the store offers instead. Measured on the real store at 931b4beb4: select_batch --limit 5 returned ACS-500g-6-i, BP-900b-3, BP-900g-10-i, BP-900g-10-ii, BP-900g-8-ii while select_connected --ac TKT-600a-1 returned TKT-600a-1. Zero overlap, and nothing in the run reports that the requested AC was dropped, because nothing in the run ever received it. The readiness field cannot be relied on to prevent this: TKT-600a-1 has been readiness: draft for its entire history INCLUDING the whole period it was work_status: done, so draft here does not mean not-ready, it means nobody ran the approval gate — every AC that reached done outside /plan-feature is in the same state and equally invisible while looking perfectly buildable in the store. Fix direction has two independent halves, both cheap: give fast-lane-build.js the ac argument its sibling already has (fast-lane-ship.js accepts args.ac and resolves via select_connected, which is dependency-ordered and readiness-agnostic — the correct behaviour already exists one file over), or make the silence impossible by refusing when the caller names an AC that select_batch did not return. A workaround with the two pre-flight commands to run before dispatching is recorded, since an empty select_connected result is a clean no-op in the lane and checking first is the difference between a diagnosis and a wasted run. KI-BP-016 — second occurrence, still live at 931b4beb4, hit during a routine pre-drive build.py sync, which is the context this defect will keep appearing in: the standing instruction is to rebuild before every drive, so every drive re-arms it. 178 table rows deleted, 0 added, all nine sections No docs found., sole working-tree modification on an otherwise clean tree, build exit 0. Its line citations had drifted by roughly 350 lines and would have sent a fixer to the wrong function; they are replaced with symbol names, which do not rot. Filed rather than fixed, deliberately: neither belongs in the change that was being made when they were found. The index count for build-orchestration is corrected from 37 to 38 by grep, per that file's own instruction to re-run the count rather than trust the table."
---

## Entry

Two entries, neither of them in the change being made when they were found.

### KI-BO-032 — the lane builds something else and calls it success

`/fast-lane-build` takes **no AC argument**. It hardcodes `select_batch`, which filters to `readiness: approved`. Name an AC that isn't approved and the lane builds whatever the store offers instead:

```
select_batch     --limit 5        -> ACS-500g-6-i, BP-900b-3, BP-900g-10-i,
                                     BP-900g-10-ii, BP-900g-8-ii
select_connected --ac TKT-600a-1  -> TKT-600a-1
```

Zero overlap. Nothing in the run says the requested AC was dropped, because nothing in the run ever received it.

**Readiness cannot be relied on to catch this.** `TKT-600a-1` has been `readiness: draft` for its entire history — *including the whole period it was `work_status: done`*. So "draft" here does not mean unready; it means nobody ran the approval gate. Every AC that reached done outside `/plan-feature` is in the same state, invisible to the lane while looking perfectly buildable in the store.

The fix already exists one file over: `fast-lane-ship.js` accepts `args.ac` and resolves through `select_connected`, which is dependency-ordered and readiness-agnostic.

### KI-BP-016 — second occurrence, and its citations had rotted

Hit again during a routine pre-drive `build.py` sync. That is the context this will keep appearing in: the standing instruction is to rebuild before every drive, so **every drive re-arms it**.

```
178 table rows deleted, 0 added, all nine sections "No docs found.", exit 0
```

Its line citations had drifted ~350 lines and would have sent a fixer to the wrong function. Replaced with symbol names, which do not rot.

### Filed, not fixed

Deliberately. Neither belongs in the change that was being made when they surfaced.

The `build-orchestration` index count is corrected 37 → 38 by `grep -c '^### KI-'`, per that file's own instruction to re-run the count rather than trust the table.
