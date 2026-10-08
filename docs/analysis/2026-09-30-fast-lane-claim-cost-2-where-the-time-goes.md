---
title: "Where fast_lane.py claim spends its time, and which hypotheses survive"
description: "cProfile puts 98.8% of claim's runtime inside yaml.safe_load, using the pure-Python loader while libyaml is installed, over a store walked twice. Five hypotheses tested; two confirmed, three refuted. Plus mark_done, which really is O(ids x records)."
type: explanation
status: active
created: 2026-09-30
last_updated: 2026-09-30
components:
  - build_orchestration
  - ac_store
---

# Where `fast_lane.py claim` spends its time

Part 2 of four. [Part 1](2026-09-30-fast-lane-claim-cost.md) has the verdict,
the growth curve, and who owns the 2-minute cap.
[Part 3](2026-09-30-fast-lane-claim-cost-3-the-phantom-todo.md) covers a second
defect. [Part 4](2026-09-30-fast-lane-claim-cost-4-fix-directions.md) gives the
fix directions.

## 1. The profile

`python -m cProfile` over 223 records, 54.0 s under the profiler (≈2.6x
instrumentation overhead on the 20.6 s bare run). Cumulative sort, top frames:

```
16921012 function calls (16848026 primitive) in 54.043 seconds

ncalls  tottime  cumtime  filename:lineno(function)
     1    0.000   53.656  fast_lane.py:424(main)
     2    0.034   53.611  _fl_lifecycle.py:38(_build_ac_id_to_path_index)
   446    0.023   53.511  scan_ac_store.py:115(_load_ac)
   446    0.013   53.365  yaml/__init__.py:117(safe_load)
     1    0.000   26.930  _fl_lifecycle.py:405(filter_already_claimed)
     1    0.000   26.681  _fl_lifecycle.py:262(claim_build_set)
194142    0.778   47.829  yaml/parser.py:94(check_event)
504656    2.110   41.178  yaml/scanner.py:113(check_token)
717756    6.620    7.188  yaml/reader.py:99(forward)
```

Three facts fall straight out:

**98.8 % of runtime is YAML parsing.** `yaml.safe_load` is 53.365 s of 54.043 s.
Directory walking, `os.replace`, argparse and the actual claim logic are all
noise.

**The store is walked exactly twice.** `_build_ac_id_to_path_index` has
`ncalls = 2` and `_load_ac` runs `446 = 2 × 223` times. The two callers are
`filter_already_claimed` (26.93 s) and `claim_build_set` (26.68 s), each
building its own full id→path index at `_fl_lifecycle.py:434` and `:294`.
Neither shares the other's; `main()` calls them back to back at
`fast_lane.py:511-526`.

**The parser is the pure-Python one, and it needn't be.** Every frame resolves
to `yaml/parser.py`, `scanner.py`, `reader.py` — `reader.forward()` alone runs
717 756 times. Yet:

```
yaml.__with_libyaml__  ->  True      (PyYAML 6.0.1, Python 3.12.3)
```

libyaml is installed and unused, because `yaml.safe_load` is hardwired to
`SafeLoader` rather than `CSafeLoader`.

## 2. What the alternatives cost

One pass over all 4 458 records, measured:

| Approach | Time | vs. current (270.7 s) |
|---|---|---|
| current: 2 passes, pure-Python `safe_load` | 270.7 s | 1x |
| 2 passes, `CSafeLoader` | ~28.8 s | 9.4x |
| 1 shared pass, `CSafeLoader` | **14.41 s** | **18.8x** |
| 1 shared pass, line-scan for `^id:` | **0.79 s** | **343x** |

`CSafeLoader` and the line-scan each recovered 4 457 of 4 458 ids. The single
miss is `index.yaml`, the component registry, which has no `id` field — the
same result the current code produces.

## 3. The hypotheses

| # | Hypothesis | Verdict | Evidence |
|---|---|---|---|
| (a) | per-id full re-walk, O(ids × records) | **REFUTED for `claim`** | `ncalls = 2` regardless of id count; 20 ids ran no slower than 1. **But true for `mark_done`** — §4. |
| (b) | every record YAML-parsed for an id-only lookup | **CONFIRMED — the cause** | 53.365 s of 54.043 s in `yaml.safe_load`; a line-scan does the same job 343x faster. |
| (c) | O(n²) cross-reference re-scanning edges | **REFUTED** | `claim` resolves no edges — it reads `id` and `work_status` only. In `resolve_connected_build_set`, `traverse_ac_tree` receives a prebuilt `id_index` (`fast_lane.py:231`) and performs no read or parse of its own; the `depends_on` worklist guards with `if dep not in build_set`. |
| (d) | one pathological record, or a cycle walked without a visited-set | **REFUTED, both halves** | No record exceeds 77 KB (mean 5.0 KB), so no single file dominates a 270 s run. The traversal *is* bounded: `_dfs_collect_leaves` carries a `seen: set[str]` and returns on repeat visit; `resolve_connected_build_set` additionally calls `_drain_cycles`. The known AC dependency cycles (KI-ACD-20260929) cannot cause this — and `claim` never walks the graph. |
| (e) | honest linear cost that legitimately exceeds 2 minutes | **CONFIRMED as the shape** | s/KB constant across a 3 400x size range; bytes 3.83x → time 4.19x. |

So: linear, with a 20x constant that is pure waste, times 2 for the duplicate
pass. The fix is therefore both algorithmic *and* — because even a perfect
index is ~1 s and the lane makes many such calls — a budget that is honest
about what it allows.

## 4. `mark_done` really is O(ids × records)

`fast_lane.py:558-566`:

```python
for ac_id in ac_ids:
    verdict = verify_done_eligible(ac_id, ac_root=ac_root, test_root=test_root)
```

`verify_done_eligible` (`done_proof.py:2348`) opens with
`_build_ac_status_map(ac_root)` — a full `rglob("*.yaml")` walk with
pure-Python `yaml.safe_load` (`_done_proof_phase_helpers.py:102-105`). So the
store is re-walked **once per id**, then twice more by `mark_done_built_acs`
and `check_no_stale_todo`.

At ~135 s per pass, `mark_done` on a 2-AC build set costs roughly
`(2 + 2) × 135 s ≈ 9 minutes` of pure YAML parsing before a single pytest
process starts.

**The pattern is systemic, not local.** `_build_ac_id_to_path_index` has five
call sites in `_fl_lifecycle.py` alone (lines 294, 382, 434, 494, 545), plus
`_fl_producibility.py:97` and `_fl_changelog.py:124`, and roughly 25 more
independent `rglob("*.yaml")` loops elsewhere in `scripts/build_orchestration/`
and `scripts/ac_store/`. Every one builds its own index; none shares; all use
the pure-Python loader.
