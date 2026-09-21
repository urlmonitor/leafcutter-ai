---
title: "KI-ACS-20260901-1730 — The done-proof oracle gives pytest 60 seconds and reports the timeout as \"linked test not run\", so a slow-but-passing test makes an AC nondeterministically ineligible for done"
description: "KI-ACS-20260901-1730 — The done-proof oracle gives pytest 60 seconds and reports the timeout as \"linked test not run\", so a slow-but-passing test makes an AC nondeterministically ineligible for done"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - ac_store
related_docs:
  - docs/known-issues/ac-store.md
  - docs/known-issues/README.md
---

# KI-ACS-20260901-1730 — The done-proof oracle gives pytest 60 seconds and reports the timeout as "linked test not run", so a slow-but-passing test makes an AC nondeterministically ineligible for done

> One known issue, split out of `docs/known-issues/ac-store.md` on
> 2026-09-14. Index: [ac-store.md](../ac-store.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 1
- **First seen:** 2026-09-01
- **Where:** `scripts/ac_store/done_proof.py:900` (`timeout=60`) and `:903-908` (the
  `TimeoutExpired` handler returning `{}`)

**Symptom.** `mark_ac_done.py --test-root ...` refused `TKT-600b-2`:

```
WARNING: done_proof: pytest timed out after 60 s
REFUSED: TKT-600b-2 is not eligible for done — linked test not run:
  ...test_tkt_600b_2.py::test_excluded_phase_holds_all_four_facts_at_generation;
  linked test not run: ...::test_signed_off_without_a_signoff_entry_is_rejected;
  linked test not run: ...::test_real_parity_guard_accepts_a_really_generated_ticket
```

All three tests exist, are `# covers:`-tagged, and pass. The file takes ~85-97 s because each
test drives the real generator (two of them through `subprocess` against the real CLI, which
is deliberate — they are the seam and real_artifact entries, and a faster in-process version
would not test the thing they exist to test). The oracle waits 60 s and gives up.

**It is nondeterministic, which is the part that makes it costly.** Two runs of the identical
command at the identical commit, minutes apart:

```
run 1   [dry-run] would mark TKT-600b-2 work_status=done
run 4   REFUSED ... linked test not run (timed out after 60 s, 83.6 s wall)
```

Nothing changed between them but filesystem cache warmth. So eligibility for `done` is a coin
flip for any covering test near the boundary, and the coin is weighted by whatever else the
machine was doing. Under the parallel-agent fleet this repo is built around, that is not a
rare edge.

**The message is wrong in the expensive direction.** On timeout the runner returns `{}` — an
empty outcome map — which is indistinguishable at the call site from "pytest ran and reported
nothing about this test". The refusal therefore says *no test ran*, when the truth is *the
oracle stopped waiting*. Those demand opposite responses: the first says "write a test", the
second says "your test is fine". A reader who trusts the message goes and writes a duplicate
of a test they already have.

**This exact message has already caused a false refusal on five real records**, from a
different cause — `_find_nodeid_for_test` not matching parametrized nodeids, fixed earlier the
same day (`done_proof.py:1461-1474`, ACS-200f). That is the finding underneath this one:
"linked test not run" is a collapsing point where several distinct causes — no test, wrong
nodeid shape, oracle timeout — all surface as the same sentence, and only one of them is the
one it names.

**The fail-closed direction is correct and should be preserved.** Returning `{}` and refusing
is right; an oracle that cannot get evidence must not grant `done`. The defect is the
diagnosis, not the verdict. Do NOT "fix" this by treating a timeout as a pass.

**One thing this is NOT.** `AC_ENFORCE_STRICT` is irrelevant here, and it is worth writing
down because it was my first hypothesis and it was wrong: `done_proof.py:894` forces
`AC_ENFORCE_STRICT=1` into the child environment unconditionally, so the oracle always sees
unmasked results regardless of the parent's env. The differing outcomes above were timing,
not enforcement mode.

**Fix direction.** Three separable pieces, in order of value:

1. **Distinguish timeout from absence.** Return a sentinel the caller can tell apart from an
   empty result, and word the refusal as "the covering test did not finish within N s" — so
   the reader is pointed at the runtime, not at a missing test.
2. **Raise and configure the limit.** 60 s is below the runtime of legitimate tests in this
   repo; a covering test that drives a real CLI through subprocess is exactly the shape the
   testing conventions ask for, and is exactly the shape that exceeds it. Make it an argument
   with a default well clear of observed runtimes.
3. **Consider per-test invocation.** The oracle runs the whole file, so one slow test can
   starve the budget for every AC covered by that file.

**Related.** `KI-ACS-20260901-1520` (the sibling `done_proof` defect: the proof oracle routed
by file extension). `ACS-200f` (the parametrized-nodeid false refusal — same message, third
cause).

**Pattern:** `docs/reference/false-green-mechanisms.md`, inverted — a gate that fails closed,
correctly, while naming a cause that is not the cause. The verdict is safe and the diagnosis
sends you to the wrong place, which costs more than a silent pass would in reader-hours.

---
