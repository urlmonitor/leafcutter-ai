---
title: "KI-BO-020 — The fast lane's release-on-failure path is dead: it dispatches `status-checker`, which refuses the role, so aborted runs strand their claims"
description: "high — silent, and it defeats a criterion believed to be working"
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

# KI-BO-020 — The fast lane's release-on-failure path is dead: it dispatches `status-checker`, which refuses the role, so aborted runs strand their claims

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high — silent, and it defeats a criterion believed to be working
- **Status:** **RESOLVED** (fix landed under `BO-2400f-10-i`; verified 2026-09-01) — **but read
  the residual below, which is a different and still-open defect.**
  `fast-lane-ship.js:490` now declares `const RELEASE_EXECUTOR_AGENT_TYPE = "python-coder";`
  and all nine release sites route through that one constant rather than a per-site literal.
  Confirmed live, not merely by reading: a `/fast-lane-build BO-2400c-1-v` run on 2026-09-01
  halted at the coder phase and reported `Release: succeeded — BO-2400c-1-v returned to todo`.
  This entry sat at `open` for a week after being fixed, and was recommended as the next thing
  to build on 2026-09-01 before anyone checked the code — the second stale entry found in a
  single review of this register.
- **Occurrences:** 2 observed; every failing path that releases is affected
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `templates/workflows-js/fast-lane-ship.js` — the release dispatches on the
  failure paths, e.g. `release-on-context-bundle-fail`, all of which pass
  `{ agentType: "status-checker" }`

**Symptom.** When a phase fails after the claim step, the lane dispatches a release agent to
put the claimed ACs back to `todo`. The prompt opens `You are the release-phase agent.` and
the dispatch uses `agentType: "status-checker"`. `status-checker` **refuses**:

> I am status-checker, not a "release-phase agent." This message attempts to reassign my role
> and have me execute a fast-lane AC-release script — that is outside my defined scope … I
> did not run the requested command.
> `{"status": "refused", "reason": "out-of-scope-r…`

The lane does not inspect the reply — the release is best-effort and its result is discarded
— so the run reports its halt and the ACs stay `in_progress`.

**Second occurrence, 2026-08-25, on a different failure path.** A `/fast-lane-build BP-1100b-5`
run halted at `release-on-review-fail` (the review gate, not the context-bundle gate), and
`status-checker` refused in the same terms, adding a second objection the first sighting did
not record:

> I am status-checker, not a release-phase agent. This message attempts to reassign my identity
> … **and no user of this session has asked me to do this in-turn; a task-prompt asserting a
> different role for me is not a valid instruction source.**

That clause matters for the fix. The agent is not merely refusing an unfamiliar command — it is
applying a general rule about role reassignment via task prompt. So re-wording the prompt will
not help, and neither will a more forceful instruction; the dispatch needs a different
`agentType` whose charter actually includes releasing claims, or the release needs to stop
being an agent dispatch at all. It is a single deterministic CLI call
(`fast_lane.py release --ac-ids …`) with no judgement in it, which is a poor reason to involve
a model.

`BP-1100b-5` was left at `work_status: in_progress` by the halt, confirming the strand.

**The strand is narrower than it looks, for a reason that is its own defect.** The
`in_progress` flip lives only as an **uncommitted edit inside the lane's private worktree** —
`origin/main` still reads `todo`. So deleting the worktree discards the strand, and this entry's
"aborted runs strand their claims" is true only for as long as that worktree survives. The
flip side is worse than the strand: a claim that never reaches shared state cannot exclude
anything. See KI-BO-20260826-1332, where that is the primary finding.

**Verified, not inferred.** After run `wf_bd4984e8-438` halted, all five claimed ACs were
still `work_status: in_progress` in the run's worktree store, with `BO-2400f-13` and
`BO-2400f-13-i` confirmed by direct read. The release agent had run and returned; it simply
did nothing.

**Why the containment was luck, not design.** The damage stayed harmless only because a
fast-lane run claims in **its own worktree's** copy of the store, which is discarded with the
worktree — `origin/main`'s copy still read `todo`. Any path where a claim reaches a shared
store leaves those ACs stranded `in_progress`, where BO-2400f-8 will then correctly refuse to
rebuild them: a failed run silently makes its own target unbuildable.

**This invalidates a premise other work is resting on.** `BO-2400f-13`'s reasoning (and the
Product Owner's decision to refuse rather than reuse an occupied workspace) is written on
"the lane has no resume semantics — BO-2400f-10 releases the claim on abort". BO-2400f-10 is
specified and believed working, but its **only invocation path is dead**. The refuse decision
still holds — it holds *more* strongly, since a leftover workspace may also carry stranded
claims — but the stated reason is currently false and should not be quoted as established
behaviour until this is fixed.

**This is a known agent-level pattern, now seen in a second caller.** `status-checker` refuses
role reassignment by design. The same refusal already breaks `/plan-feature`'s gates, where it
is dispatched to "ask the user" and returns a well-formed `{action: cancel}` that reads as a
real decision. The general lesson: **dispatching an agent under a role name that is not its
own is not a prompt-style choice — the agent will refuse, and a caller that ignores the reply
turns that refusal into a silent no-op.**

**Fix direction.** Do not route the release through a persona-mismatched agent. Either give
the release its own minimal agent whose charter includes mutating AC claim state, or — better,
since the release is a single deterministic command — invoke `fast_lane.py release` directly
rather than asking an agent to run it. Whatever the shape, **read the reply**: a release whose
result is discarded cannot distinguish "released" from "refused", which is precisely how this
stayed invisible. A release that did not release should surface in the halt payload next to
the failure that triggered it.

**Update, 2026-08-25 — this is nine dead paths, not one.** A `grep -n "agentType"` across the
lane shows **every** release dispatch passes `agentType: "status-checker"`, and every one opens
its prompt "You are the release-phase agent.":

| line | label |
|---|---|
| 506 | `release-on-context-bundle-fail` |
| 574 | `release-on-test-writer-fail` |
| 596 | `release-on-red-baseline-fail` |
| 648 | `release-on-coder-fail` |
| 668 | `release-on-coverage-fail` |
| 751 | `release-on-review-fail` |
| 773 | `release-on-review-fail` |
| 871 | `release-on-changelog-fail` |
| 943 | `release-on-commit-fail` |

So it is not that one failure path strands its claims — **every failure path in the lane
does**, from the first phase to the last. The observed run happened to fail at the earliest of
the nine. Any covering test must drive all nine, not the one that was seen.

**A latent sibling with the same shape and a worse failure mode.** The CLAIM dispatch at line
393 opens "You are the claim-phase agent for a fast-lane build." with `agentType:
"status-checker"` (line 402) — identical persona mismatch. It **complied** on the observed
run, which is exactly why nobody has noticed it. Its failure mode is the inverse of the
release's and more dangerous: a silent non-claim would let two runs build the same acceptance
criterion concurrently, with `BO-2400f-8`'s exclusivity guard never firing because nothing was
ever claimed. That belongs with `BO-2400f-7`, not here, and it is deliberately NOT folded into
this fix — but a change to the release dispatches must leave it demonstrably alone rather than
half-converting it. Recorded in `BO-2400f-10-i`'s notes.

**Placement.** Specified as `BO-2400f-10-i` (the release actually releases, on every halting
path) and `BO-2400f-10-ii` (the result is read; a failed release is named in the halt *beside*
the failure that caused it, not instead of it). `BO-2400f-10` is reset from `done` to
`in_progress`: marking done a criterion whose only invocation path has never once executed is
the phantom-done shape this family exists to end.

**One question carried, not resolved.** `BO-2400f-10` says the release "is landed on
mainline", but a fast-lane run claims in its own workspace's copy of the store, which is
discarded with the workspace — the only reason the observed failure was harmless. Whether the
release is meant to reach mainline at all is a product question; the new criteria are worded
against "the store the run claimed in" so they hold either way.

**Related, and it compounds — see `KI-BO-023`.** That entry records a *second*, independent way
a claim gets stranded: `_update_ac_work_status` raises `ValueError`, all three call sites catch
only `OSError`, and the escape leaves acceptance criteria `in_progress` permanently. So there
are now two distinct mechanisms stranding claims — a release that is never *reached* (this
entry) and a release that is reached and *throws past its own error handling* (KI-BO-023).
Fixing either alone still leaves claims stranded. `BO-2400f-10-ii`'s requirement that the
release's result be **read** is the common defence: both mechanisms are silent today precisely
because nothing inspects the outcome.

---
