# BA — a `work_status: done` parent is not an available host, whatever its child count

Captured 2026-10-09 while authoring GE-118g and GE-127g (guardrail-engine).

## The rule

**Check `work_status` on a candidate parent BEFORE you check its child count.**

A `done` L1 with four free L2 slots is NOT a usable parent for a new `todo` L2.
`check_done_proof` proves a done L0/L1 composite by its `covered_by` children
being themselves done-and-covered (`_composite_child_ids`,
`scripts/ac_store/_done_proof_composite.py`). Adding a `todo` child makes the
parent a done composite with an unfinished child — the ACD-400a defect class, 20
live instances found in one store sweep — and because the AC-store commit rule
requires the parent to be staged in the same commit as the child, the violation
is **staged with it** rather than lying latent. So the hook fires on your own
commit.

## Measured consequence in GE-127 (2026-10-09)

| parent | level | work_status | children | cap |
|---|---|---|---|---|
| GE-127  | L0 | todo | 7 | 7 |
| GE-127a | L1 | **done** | 1 | 5 |
| GE-127b | L1 | **done** | 2 | 5 |
| GE-127c | L1 | **done** | 1 | 5 |
| GE-127d | L1 | **done** | 2 | 5 |
| GE-127e | L1 | **done** | 4 | 5 |
| GE-127f | L1 | todo | 4 | 5 |

GE-127c was the semantically correct parent for a scope decision (it owns REACH:
"which kinds of file are in scope is a stated, reviewable decision") and held
1 of 5. It was still unavailable. The L0's last free L1 slot was the correct
home, not the residual one — say so explicitly in the new L1's notes, or the next
author re-litigates it.

## Both guardrail goals are now structurally full at L1

- **GE-118: 7/7**, no `child_limit_override`.
- **GE-127: 7/7**, no `child_limit_override`.

Any further record in either family needs a new L0 or a split. Do not read
GE-127's five done L1s with free L2 slots as headroom — see above.

## GE-118's tree is not shaped like its ids suggest

GE-118a is L1; **GE-118b, c, d, e, f are all level L2 hanging directly off the
L0**. `derive_parent_id` attributes them to GE-118, so `check_ac_limits` applies
the L0's 7-cap to them regardless of their declared level. Count children by
`derive_parent_id` over the whole store, never by reading `level` fields or
listing folders.

## Decomposition pattern worth reusing

When the dispatcher asks you to SETTLE a design question rather than inherit it,
encode the answer as a **named mutation on a sibling record**, not as prose. The
directory-versus-suffix question for the doc-length exclusion is settled by
GE-127g-3's first arm going red under a suffix rule — the suffix option is not
rejected by argument, it is rejected because a stated criterion fails under it.
That makes the decision falsifiable and stops an implementer re-deciding it.

Corollary from the same run: a record that only delivers what was asked for
(stop refusing generated files) is satisfiable by an exclusion that swallows the
whole directory tree. The boundary record — "the exemption does not leak" —
is the one nobody asks for and the one that makes the fix narrower than the
problem. Write it, and state in its notes that it was unasked-for, so it is not
dropped as scope creep.

## Context-resolution vs truthfulness — a parent-choice distinction

A guard that reports "could not read X" from the wrong directory is **honest and
wrong**. Do not file it under a truthfulness goal (GE-126 here): a truthfulness
criterion is already satisfied by the defective code, which is the test that it
is the wrong home. File it with the resolution point-fixes (GE-118 here) and
write the criteria about resolving the context, not about saying so. Keep one
clause requiring that no-answer is never presented as a clean answer — that is
what stops the fix being implemented as "swallow the failure".
