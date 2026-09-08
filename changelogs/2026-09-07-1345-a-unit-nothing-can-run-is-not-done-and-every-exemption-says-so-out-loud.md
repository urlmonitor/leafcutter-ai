---
title: A unit nothing can run is not done, and every exemption says so out loud
date: "2026-09-07"
time: "13:45"
type: manual
components:
  - build_orchestration
  - commit_guardian
summary: "BO-2900d-1 and BO-2900d-2: the done-proof gate refuses a criterion whose code no entry point can reach, a recorded and reasoned exemption releases that refusal, and every exemption in force is listed on every run of the guard regardless of outcome."
description: "Built by a fast lane running concurrently with a second one. The lane halted on a test assertion that had become incompatible with its sibling AC's mandate — not a criteria conflict, but an assertion that checked the whole output where its own failure message said it meant finding lines only."
---

## Entry

Two criteria, one seam.

**`BO-2900d-1`** adds the reachability refusal: for an otherwise-eligible acceptance criterion, resolve the modules its covers-tagged tests import, and refuse when a resolved unit defines no entry point of its own *and* nothing outside the test tree imports it. A unit that only its own test can reach is not shipped code. A recorded, exact-match, **reasoned** exemption releases the refusal and is attached to the verdict, so the verdict shows its work.

**`BO-2900d-2`** makes the exemptions visible: every exemption in force is listed, with its reason, on **every** run of the guard regardless of outcome. `main()` was restructured so the previous early `return 0` on a clean run no longer skips the report — that early return was precisely the defect the criterion describes.

The shared seam lives in a new `templates/scripts/commit_guardian/_reachability_inventory.py`: `load_exemptions`, `exemptions_in_force` (which already excludes reasonless entries, per `BO-2900d-1-i`), and `is_exempt` — exact match only, no globs. A corrupt registry raises; a missing one is zero exemptions.

### The halt, and why it was the test rather than the specs

The lane stopped at its green gate with one failing test out of the family. `BO-2900d-1`'s third test asserted:

```python
assert "module_a" not in combined.replace("recorded exemption for module_a only", "")
```

with a failure message reading *"the exempted unit (module_a) must not itself be reported as a **finding**"*.

The intent was right. The implementation checked the **entire** combined output, while `BO-2900d-2` — landing in the same change — *requires* printing every exemption's item, and that item's path is `src/module_a/helpers/no_entry_unit.py`. The `.replace()` stripped the reason text but not the item.

So the two ACs looked irreconcilable and were not. `BO-2900d-1`'s own criteria already distinguish the exempted unit being *"not reported"* as a finding from the exemption *"appearing in the guard's output as an accepted exemption"*. Both clauses hold simultaneously. Only the assertion conflated them.

The fix narrows the assertion to the guard's real finding lines — `[check-done-proof] <ac_id>: <reason>` — which structurally cannot match the inventory lines, since those read `[check-done-proof] exemption in force: …` with a space rather than a colon after the leading word. No second `.replace()` was added; chained substring carving is how the defect arose.

**It was mutation-tested in both directions.** A fake finding line naming `module_a` was injected into the guard; the test went red. The implementation was then restored and confirmed byte-identical against its template. A narrowed assertion that had not been shown able to fail would have been worth nothing.

### Proof

8 tests green under `AC_ENFORCE_STRICT=1` across the three affected files. The wider suite the implementation touched ran 712 passed / 3 skipped with no regressions. Both criteria marked done through `mark_ac_done.py`'s own coverage gate rather than by assertion. `BO-2900d-3`, `-4` and `-5` came in as connected-set members, were not built, and remain `todo`.

This work also served as one half of the two-lane concurrency experiment recorded against `KI-BO-20260901-1450`; the two lanes did not interfere with each other's build state.
