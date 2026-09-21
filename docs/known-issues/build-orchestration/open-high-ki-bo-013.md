---
title: "KI-BO-013 — A documentation-only AC anywhere in a resolved build set jams the fast lane at commit, because `test_required: false` is honoured by nothing"
description: "KI-BO-013 — A documentation-only AC anywhere in a resolved build set jams the fast lane at commit, because `test_required: false` is honoured by nothing"
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

# KI-BO-013 — A documentation-only AC anywhere in a resolved build set jams the fast lane at commit, because `test_required: false` is honoured by nothing

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-19
- **Where:** `scripts/build_orchestration/fast_lane.py` —
  `mark_done_built_acs` / `check_no_stale_todo`; `scripts/ac_store/done_proof.py`

**Symptom.** The lane resolves a connected build set, then at Phase 5 requires that
*every* built AC ends `work_status: done`. `mark_done_built_acs` only flips ACs whose
coverage gate passed, and the coverage gate needs at least one green `# covers:`-tagged
test. A documentation AC has no test and declares `test_required: false` — so it is never
in `covered_ac_ids`, never flipped, and `check_no_stale_todo` then reports it stale and
fails the run. The lane also has no documentation phase (it dispatches `test-writer` then
`python-coder` only), so the doc would not have been written either way.

**Evidence.** `grep -rn test_required` across `fast_lane.py`, `done_proof.py` and
`mark_ac_done.py` returns **nothing**. The field is part of the AC schema and is read by
the ticket-generation path, but the entire done-proof chain the fast lane depends on is
blind to it.

Reproduction, re-measured 2026-08-24 after the aiming fix (BO-2600b-1) landed in this
same branch — the originally-recorded repro (`--ac BO-2600b-1` resolving five ids) no
longer reproduces, because that command now carries `--exclude-structural-parent` and
because b-1/-1-i/-1-ii are now `done`; it returns `[]`. The current standing repro is:

```
select_connected --ac BO-2600b --exclude-structural-parent
  -> ["BO-2600b-2", "BO-2600b-3"]
```

`BO-2600b-3` is a how-to AC with `assigned_agent: documentation-expert` and
`test_required: false`, so that set still cannot be built by the lane as it stands. The
defect is unchanged; only the command that exhibits it moved. Worth noting the correction
itself: a known-issue whose repro line has quietly stopped reproducing is the same
stale-evidence failure this register exists to catch, one level up.

**Why it is worse than it first reads.** The operator cannot avoid it. Build sets are
resolved from the store, not chosen — so a single documentation child anywhere in a
subtree makes that whole subtree unbuildable by the lane, and the failure surfaces at
Phase 5, *after* the test-writer and coder have done all their work. Worse, the halt
message is `mark_done stale: <ids>`, which reads like a coverage failure in the code and
sends the reader looking for a missing test that was never supposed to exist.

**Note the failure is half-correct**, which is why it should not be "fixed" by loosening
the gate. Refusing to mark a doc AC done when no doc was written is right. The defect is
that the lane has no way to *produce* the doc and no way to *exclude* it, so a correct
refusal presents as an unexplained jam.

**Fix direction.** Three candidates, in preference order. (1) Give the lane a
documentation phase, so a resolved doc AC is built rather than tripped over — this is the
only option that makes the promise "point at an id, get a PR" true for a subtree that
includes docs. (2) Teach the done-proof chain to honour `test_required: false` with a
different proof obligation (the named doc file exists and changed in the diff), rather
than treating absence of a test as absence of proof. (3) At minimum, make the halt say
what actually happened: name the AC, its `assigned_agent`, and that the lane has no phase
for it. Do not simply skip untestable ACs — that reintroduces phantom-done through the
front door.

---
