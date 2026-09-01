---
title: The overlap rule gets a host, and it is the claim path
date: "2026-09-01"
time: "13:40"
type: manual
components:
  - ac_driven_dev
  - build_orchestration
summary: "ACD-2000b-4 contradicted itself — doc_links said the surface question was open while it_requirements still named the dormant select_batch. The IT PO resolved it by answering the question: the live lane invokes fast_lane.py claim on every run, and filter_already_claimed is where the footprint comparison is missing."
description: "The contradiction was expected to be settled by softening one bullet. Instead the IT PO found a fact the brief had wrong — fast-lane-ship.js calls claim as well as select_connected — which makes clause four of the criterion buildable today on a path that already runs. It also found that the chosen host already contains the exact inversion the criterion's own bullet 2 warns about. Clauses one to three remain hostless and that asymmetry is now recorded in the fields an implementer reads."
---

## Entry

`ACD-2000b-4` — *"Requirements whose change footprints overlap never build at the same time, and an unknown footprint conflicts with everything"* — was contradicting itself across two of its own technical fields.

Its `doc_links` note (added the previous day) said the surface question was open and warned that implementing on `select_batch` would produce a rule that never fires. Its `it_requirements` bullet 8 still told the implementer to "preserve `select_batch`'s documented guarantee". `it_requirements` is the field an implementer actually obeys, and it was the one still pointing at the dormant surface.

### The brief was wrong, and the correction is the finding

The expectation was that bullet 8 would be softened and the record left honestly non-committal. The IT PO instead answered the question, because the brief had understated the facts: it named `select_connected` as the live lane's only relevant call.

**`fast-lane-ship.js:818` also invokes `python3 fast_lane.py claim` — on every run.** Its handler reaches `filter_already_claimed`, which already walks the whole store, already reads every candidate, and already decides admit-or-refuse — on `work_status` alone. A footprint comparison is *missing* there; it is not a place that has to be invented.

So clause four of the criterion — *"two separate efforts, running at the same time and choosing independently, likewise never end up building two requirements whose footprints overlap"* — describes a real, unguarded defect on a path that runs today. Two fast-lane runs can hold AC sets that are disjoint by id and collide by file.

### The chosen host already contains the predicted defect

`it_requirements` bullet 2 warns that the rule's single most likely defect is treating an unknown footprint as safe: *"the empty set intersects nothing, so 'unknown footprint' reads as 'safe to parallelise'… invisible in code review because the wrong implementation is the shorter one."*

`filter_already_claimed` already does exactly that on its own axis. At `fast_lane.py:525-536` a candidate is routed to `to_build` both when its id is absent from the index and when its YAML cannot be read — the second with a logged warning, the first with a comment reading "treat as buildable (conservative; caller resolves)".

That matters for how the work is done, not just where: bullet 2 **changes** behaviour at that call site rather than adding to a blank one, so the test must be red before the change.

### Also corrected

- `_build_ac_id_to_path_index` is at **line 123**, not `~line 71` as the record claimed. The precedent survives and now argues the other way: `claim_build_set`, `release_claim`, `filter_already_claimed`, `mark_done_built_acs` and `check_no_stale_todo` each take one index and reuse it, while `select_batch` does not use it at all.
- `test_spec` entries 1–4 presupposed a batch-returning function ("returned in the same batch", "offered together") and now assert concurrent *holding* through the live path.
- `delivers_to` split into the pure `conflicts(a, b)` test and its take-time application, with an explicit note that a contention test wired only into `select_batch` is delivered to nobody.
- `select_batch`'s own docstring said `ACD-2000b-4` names it as the rule's target. As of this change that is false, so it was rewritten — carefully, because that docstring is also the anti-deletion guard from `KI-BO-006`. The do-not-delete case is retained and strengthened, since it is now the *whole* case rather than half of it.

### What was deliberately not done

Clauses one to three still have no host: nothing at requirement grain chooses N things to run at once, and no AC in the store builds a requirement-grain dispatcher. That is now stated in `it_requirements` rather than only in a doc link.

The record was **not** split, though roughly a quarter of it is buildable today. The product owner settled that question earlier the same day — `ACD-2000b`'s L2 cap is 5 and is filled exactly — so the asymmetry lives in `it_requirements` instead. `readiness: draft` remains the correct gate and was left alone, as were `criteria`, `depends_on`, `work_status` and `covered_by`.
