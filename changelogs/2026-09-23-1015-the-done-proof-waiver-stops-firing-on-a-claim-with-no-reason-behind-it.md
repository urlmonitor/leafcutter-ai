---
title: "The done-proof waiver stops firing on a claim with no reason behind it"
date: "2026-09-23"
time: "10:15"
type: manual
components:
  - commit_guardian
  - build_orchestration
summary: "main went red because the fix that taught the done-proof gate to require both test_required: false AND a recorded reason added the new check without deleting the old one two lines above it. The old check fired first, so the new one was unreachable for exactly the case it existed to close — and an acceptance criterion claiming to need no test, with no reason given, was silently waived."
description: "Removes a bare `if data.get('test_required') is False: continue` from check_staged_done_proofs's leaf path in templates/scripts/commit_guardian/check_done_proof.py. It predated the BO-2500a-1-ii conjunction predicate by two weeks and was left in place beside it rather than replaced by it. Also completes 01601fbbc's own fixture updates: that commit updated two of the three stale test classes in test_done_proof_test_required_exemption.py and missed the pre-commit one — the same overlooked layer that left the bare check in place."
commits:
  - 0120224b
breaking: false
---

## Entry

### What broke

Two tests failing on `main`, and they are the regression **fences** from the very
commit that introduced the feature:

```
test_ac_refuse_test_required_false_missing_rationale
test_ac_refuse_test_required_false_whitespace_rationale
  AssertionError: 0 != 1 ... Got exit 0.
```

Exit 0 where 1 was required. The gate was **waiving** an uncovered criterion that
declared `test_required: false` with no recorded reason — a fail-open guardrail,
which is worse than the gap the original change set out to close.

### The cause, which is not subtle

`check_staged_done_proofs` carried two sequential, non-exclusive checks:

```python
if data.get("test_required") is False:      # bare, from 2026-09-09
    continue
if ac_id_str not in all_covered_ids:
    if is_covers_tag_waived(data):          # conjunction, from 01601fbbc
        continue
    violations.append(...)
```

The conjunction predicate was added in the right place. The bare check two lines
above it was never removed. It fires first — so the new predicate was
**unreachable dead code for precisely the case it exists to close**. The
predicate itself was always correct; nothing reached it.

### Why `test_required: true` still passed

The bare check only fires on `is False`. For `true` or absent it is skipped
entirely and control reaches the working predicate. So this was never "the hook
cannot see its input" — it was one dead branch on one value. That asymmetry is
what ruled out the first theory.

### A wrong theory, recorded so nobody re-derives it

The leading hypothesis was deployed-layout divergence: CI runs `build.py` first,
a bare worktree does not, and the tests passed locally while failing in CI. It
fit the evidence and it was wrong.

The failure reproduces in a plain source tree with **no build step**:

| state | result |
|---|---|
| fix reverted in place | 2 failed, 8 passed — byte-identical to CI's report |
| fix restored | 10 passed |
| restore byte-compared | `diff -q`, identical |

### The third stale fixture

`01601fbbc`'s own message records updating two pre-existing tests whose fixtures
pinned the old "`test_required` alone exempts" rule. There were **three**. It
updated the two CI-layer classes and missed
`TestCheckStagedDoneProofsExemption` — the one exercising the same exemption on
the **pre-commit** path.

That is the same blind spot that left the bare check in
`check_staged_done_proofs`: one commit, one overlooked layer, surfacing in the
code and in its tests simultaneously. The third fixture now carries a real
`test_rationale`, with a comment naming the pattern. The assertion is untouched —
the fixture was incomplete, not the assertion wrong.

### What was deliberately not added

A standing deployed-layout smoke test was considered and rejected **for this
change**. The bug is not deployment-dependent, so such a test would not have
caught it, and adding one here would file the cause under the wrong heading. The
real gap was accepting a relayed "10 passed" without re-running the suite — a
habit, not a missing test.

### Verification

| check | result |
|---|---|
| `test_done_proof_test_required_rationale_gate.py` | 10 passed |
| `test_done_proof_test_required_exemption.py` | 8 passed |
| both together | **18 passed** |
| `check_done_proof.py` content lines | 596 → **594** |
| `ruff`, both touched files | clean |

All under `AC_ENFORCE_STRICT=1`.
