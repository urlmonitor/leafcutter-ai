---
title: "TQ-600a-1 is merged, tested, documented — and still reads work_status todo"
description: "A second defect found in the same fast-lane failure. The resolver was right and the store lied to it: a fully implemented AC still carries todo, so every run depending on it re-drags merged work into its build set. The mirror image of phantom-done, and nothing currently catches it."
type: explanation
status: active
created: 2026-09-30
last_updated: 2026-09-30
components:
  - ac_store
  - build_orchestration
---

# `TQ-600a-1` is merged, tested, documented — and still reads `todo`

Part 3 of four. [Part 1](2026-09-30-fast-lane-claim-cost.md) has the verdict and
the growth curve. [Part 2](2026-09-30-fast-lane-claim-cost-2-where-the-time-goes.md)
locates the cost. [Part 4](2026-09-30-fast-lane-claim-cost-4-fix-directions.md)
gives the fix directions.

The failing fast-lane run resolved its build set as `["TQ-600a-1", "TQ-600a-3"]`.
That looked wrong — a-1 merged in PR #941 — and the first reading was that the
resolver had dragged in finished work. **That reading was backwards.**

## 1. The premise that was wrong

`TQ-600a-1` is **not** `work_status: done`. On disk, and on freshly fetched
`origin/main` at `894bff19`:

```
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-1.yaml
  id: TQ-600a-1
  work_status: todo        <- line 10
```

`git status --porcelain` over the store is clean, so this is not local drift.
No commit in the file's history ever set it to `done`: the implementing commit
`e2d9cd0d` (PR #941) added seven entries to `implemented_by` and **touched no
`work_status` line**.

So the scenario originally suspected — `filter_already_claimed` waving a `done`
AC through — did not happen, because there was no `done` AC.

## 2. The resolver behaved correctly

`TQ-600a-3.yaml` declares `depends_on: [TQ-600a, TQ-600a-1]`. Because a-1 reads
`work_status: todo`, the resolver classifies it as an **unmet prerequisite** and
pulls it in. Reproduced exactly:

```
$ fast_lane.py select_connected --ac TQ-600a-3 --ac-root /tmp/fl_store_copy \
      --exclude-structural-parent
["TQ-600a-1", "TQ-600a-3"]                                    (151.78 s)
```

**The resolution logic did what it documents. The store lied to it.**

## 3. a-1 is genuinely finished

- Implementation on `origin/main`: `scripts/suite_performance/{__init__.py,
  _shared_layout_producer.py, _shared_layout_coordination.py,
  pytest_shared_reference_layout.py, README.md}` plus `pytest.ini` and
  `requirements-dev.txt` — all seven files listed in its own `implemented_by`.
- Covering tests exist and are `# covers: TQ-600a-1` tagged:
  `unit_tests/suite_performance/test_tq_600a_1.py`,
  `test_tq_600a_1_multiworker.py`, `test_tq_600a_1_i.py`.
- `CLAUDE.md` on `main` documents the fixture as landed: *"The shared fixture
  landed under TQ-600a-1: `shared_reference_layout` …"*.

This is a **phantom-todo**: merged, tested, documented work still carrying
`work_status: todo`. It is the mirror image of the phantom-done failure the AC
store exists to prevent, and it is damaging in its own way — it makes finished
work re-enter the build queue.

## 4. The latent defect in `filter_already_claimed` is real anyway

Independent of a-1's status. `_fl_lifecycle.py:438-456`:

```python
if record.get("work_status") == "in_progress":
    excluded_claimed.append(ac_id)
else:
    to_build.append(ac_id)
```

`done` falls into the `else`. And `claim_build_set` (`:326-337`) only skips
`in_progress`, then calls `_update_ac_work_status(yaml_path, "in_progress")`.
So a `done` AC reaching this code **would** be flipped `done → in_progress`.

It is defence-in-depth rather than a live path today, because
`resolve_connected_build_set` filters `done` upstream (`exclude_done=True` in
the subtree walk, and `dep_rec.get("work_status") == "done": continue` in the
dependency closure). It becomes live if an id is named on `--ac-ids` directly,
or in the genuine time-of-check/time-of-use window between resolve and claim —
two separate processes, minutes apart in the lane.

## 5. Blast radius, had the claim succeeded

**Would a-1's `work_status` have been flipped "back"?** No — there is nothing to
flip back from. It would have gone `todo → in_progress` on claim, then either
`→ done` on success (the correct value, arrived at for the wrong reason) or
`→ todo` on failure via `release_claim`.

**Would the coder have re-implemented already-merged work?** It would have been
*instructed* to. The test-writer phase is handed a-1 and told to write one
failing test per declared `test_spec` descriptor. a-1 declares six, and all six
already exist and pass.

**The most likely actual outcome is a halt, not corruption.**
`verify_red_baseline` requires at least one newly-added covering test to be red.
Since a-1's tests are already written and green, the test-writer either produces
nothing new or produces duplicates of green tests, and the red-baseline gate
fails closed — after which `release_claim` returns a-1 to `todo`. Cost: wasted
agent time and tokens, a confusing halt, and a real risk of duplicate or
conflicting test files landing in `unit_tests/suite_performance/`.

**Worst case is not nil.** If the coder had run — e.g. the red gate satisfied by
a-3's own genuinely-new tests, which is exactly what a mixed batch makes
possible — it would have been handed a-1's `implemented_by` files as targets for
work already merged there. That is a live path to clobbering
`pytest_shared_reference_layout.py`.

## 6. Why nothing caught it

`check_done_proof` guards the opposite direction: an AC marked `done` without
proof. Nothing fails when a merged AC keeps `work_status: todo`.

The detectable shape is specific enough to automate: an AC with non-empty
`implemented_by` pointing at files that exist on `main`, with passing
`# covers:`-tagged tests, and still reading `todo`. That sweep would have caught
this. See Part 4, F5.

One caution for whoever reconciles a-1: its children `TQ-600a-1-i` and
`TQ-600a-1-ii` are also `todo` and must be assessed on their own evidence, not
flipped alongside the parent. This repo's own convention records that an L2 is
routinely marked done while its Roman-suffixed constraints stay `todo` — that is
the dominant phantom-done shape here, and reconciling a phantom-todo is not a
licence to create one.
