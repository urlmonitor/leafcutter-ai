---
title: "Fast-lane claim reply judged against a contract it never declared"
date: "2026-09-23"
time: "16:15"
type: manual
components: 
  - build_orchestration
summary: "Fixed a bug where a fast-lane build run that successfully claimed all its work would incorrectly halt claiming the claim never happened, risking abandoned in-progress work."
description: "1 commit (57fef5a3): fast-lane-ship.js claim usability gate required excluded_claimed to be an array even though the claim dispatch never declared it required, so a fully-successful claim with nothing excluded was judged unusable and routed to the not-attempted halt. claimUsable now gates on claimed alone via a single excludedClaimed binding, mirroring the dispatch contract; 5 new behavioural tests added (workflows suite: 795 passed)."
commits: 
  - 57fef5a364c261dca38850c7e4f1cc60aec8c26f
breaking: false
---

## Entry

Commit `57fef5a3` (AC `BO-2400f-7-iv`, new L3 under `BO-2400f-7`, `work_status:
done`).

**What happened.** A fast-lane run aimed at BO-3500 reached the claim step,
claimed all 25 members of its connected set successfully, and then halted
saying "the claim was never attempted." The same reply payload carried all 25
ids in `claimed` and `target_refused: false`. The claim had in fact succeeded
completely.

**Cause.** In `templates/workflows-js/fast-lane-ship.js` the claim dispatch
declares its contract as `required: ["claimed", "target_refused"]`, leaving
`excluded_claimed` optional. The usability gate a few lines below demanded
that `excluded_claimed` also be an array. A performer that claims everything
and excludes nothing has no reason to send an empty optional array, and did
not — so a reply that satisfied the contract the run itself had asked for was
judged unusable and routed to the halt whose only purpose is to describe a
claim that never happened.

**Relationship to the previous fix.** This is BO-2400f-7-iii's defect
inverted. That record existed because a DECLINE was reported as CONTENTION;
this is an ATTEMPT THAT SUCCEEDED reported as AN ATTEMPT NEVER MADE. Both are
a consumer reading a reply differently from the contract it asked for.

**The fix.** `claimUsable` now gates on `claimed` alone, mirroring the
dispatch's own declared required list. An absent `excluded_claimed`
normalises to empty through a single `excludedClaimed` binding that both
downstream reads go through. The narrow direction was chosen deliberately —
adding `excluded_claimed` to the required list would make the contract
conform to the over-strict consumer and would begin rejecting replies that
are valid today, converting one false halt into another.

Also added: the block comment now cites the producer invariant the
decline/contention split rests on — `_fl_lifecycle.py` sets `target_refused =
len(to_build) == 0 and len(excluded_claimed) > 0`, so the gate can only ever
raise that flag alongside a non-empty excluded set. Nothing in the workflow
file referenced or enforced that before, so a change to that line would have
silently started misclassifying.

**Containment.** The halt happens after the claim has already flipped
records to `in_progress` in the run's own worktree, so a run failing this way
leaves its set claimed and abandons it. In the observed instance nothing was
stranded on the mainline, because the claim is written inside the lane's
worktree and that worktree was discarded uncommitted. That containment is
incidental rather than a defence.

**Tests.** 5 new behavioural tests in
`unit_tests/workflows/test_bo2400f_7_iv_claim_reply_contract_workflow.py`,
driven through the workflow engine harness (no grep tests). Three cover the
new behaviour; two are non-regression arms over BO-2400f-7-iii (a decline
still halts as not-attempted; genuine contention still reports contention
naming the held members). Mutation-proven: reverting `fast-lane-ship.js`
turns 3 of them red and reproduces the production halt message verbatim.
Full `unit_tests/workflows/` suite: 795 passed, 78 subtests passed.

**Size ratchet.** `fast-lane-ship.js` is over its 1000-line limit, so this
change reduces it — 1655 to 1654 content lines, by folding three `//` lines
into the block comment that now carries the rationale.
