---
title: "Spec only: a refusal that asks for a craft now summons one (BO-3800)"
date: "2026-09-14"
time: "17:09"
type: manual
components: 
  - build_orchestration
  - ac_store
summary: "Specified (but did not build) a handoff so that when an automated size gate refuses a commit for an oversized file, a restructuring specialist is brought in to fix it properly instead of the original author shuffling lines to squeeze under the limit."
description: "New L0 BO-3800 records the supervisor-side half of a capability whose guardrail half is GE-127f: a commit-time gate can only refuse, it cannot summon anyone, so without a handoff the author does its own restructuring under time pressure and tends to move lines to a sibling file to satisfy the quota rather than genuinely restructure. Five L1s: (a) the change is held, not lost or forced through, and re-offered afterwards; (b) the restructuring is done by a specialist craft, never the author mid-change; (c) the specialist is given the file and the size demand rather than reconstructing it; (d) a tidy-up that still cannot meet the demand stops, bounded, and accounts for itself; (e) everything a standard does not ask a specialist for behaves exactly as today. BO-3800e is the load-bearing negative: it adds no new behaviour, making it the obvious thing to cut, yet it is the only record standing between this tree and an implementation that summons a specialist on every refusal, colliding with BO-210's whole population. The tree is a new L0 rather than a child of BO-210 — the nearest neighbour with room under the cap — because BO-210's own Then clause promises the fixer is the same agent type that authored the work, the opposite of this tree's point; the carve-out is instead recorded forward onto BO-210 via an amended_by entry and a doc_links note, with BO-210's criteria left untouched. A finding verified against ADR-019 constrains the whole design: an agent at depth 1 cannot itself invoke the Agent tool, and the commit-agent delivery step runs at depth 1, so it can never be the party that holds a refused change and summons the specialist — that must be the depth-0 driver. Every arm of BO-3800a-1 therefore opens 'Given a ticket is being driven,' and the record carries an explicit open-question section flagging that the out-of-drive case (a hand-run commit at a terminal) is an amendment to BO-3800a still needing a product decision, rather than silently narrowing its parent. The tree also states what it does not claim: separation of duties is invisible at delivery time (one change, one identity) and anti-shuffling is invisible in a diff (moving new work out is desired, moving existing content out to make a number fall is the failure, and the two look identical) — what is promised is sequencing, that the specialist is actually asked before the retry, with the demand intact. BO-3800 carries a hard precondition, INF-800f: the restructuring craft is a slash command today, reachable only by hand, and nothing in BO-3800 is buildable until that lands. Also updates the build-orchestration PROJECT_CONTEXT with the placement rationale and corrects its 'next free L0' pointer to BO-3900, recording that loose BO-NNNN.yaml records at the component root reserve their hundred exactly as a folder does (the prior line had gone stale three times, having claimed BO-1900, BO-2300 and BO-3300 in turn), and files two known-issue entries found while doing the work. Spec-only: no code changed in this commit; the only verification performed was the AC schema validator."
commits: 
  - 3dd7b8ad9
breaking: false
---

## Entry

### What was missing

`GE-127f` — merged earlier today — says a change to an already-oversized file must leave it
smaller. That is a rule a commit-time gate can enforce. What a commit-time gate **cannot**
do is summon anyone: it can only refuse.

So on its own, the rule hands the restructuring back to whoever was mid-change. And the
entire reason for wanting a specialist is that an agent racing a gate moves lines to a
sibling file until the number falls, while a specialist optimises for structure. Shipping
the arithmetic without the handoff is not a partial delivery — it causes the failure the
rule was tightened to prevent.

`BO-3800` is the supervisor-side half. Specification only; no code.

### The five promises

| | |
|---|---|
| **a** | the change is **held** — not lost, not forced through — and re-offered afterwards |
| **b** | the restructuring is done by a craft that **specialises in it**, never the author mid-change |
| **c** | the specialist arrives knowing **which file and how much** — the brief is carried, not reconstructed |
| **d** | a tidy-up that still cannot meet the demand **stops**, bounded, and accounts for itself |
| **e** | everything a standard does **not** ask a specialist for behaves exactly as today |

### Why a new L0 rather than a child of BO-210

`BO-210` is the nearest neighbour — identical trigger, room under the cap — and was
rejected as the host. Its central Then clause promises that *"the agent that fixes the
violation is the SAME agent type that authored the work"*, while this tree's whole point is
that for one class of refusal the author is the wrong party. A child contradicting its
parent's own clause makes the parent false on that arm and hands an implementer a pair it
can satisfy by building whichever half is cheaper.

`BO-210` is also `readiness: approved` with three approved children. The carve-out is
therefore recorded **forward** onto it — an `amended_by` audit entry plus a `doc_links`
note, `criteria` untouched. A live approved record should not learn about a narrowing from
a red test. Same shape `GE-127b` carries for `GE-127f`.

### `BO-3800e` is the load-bearing negative

It promises no new behaviour, which makes it the obvious record to cut. It is also the only
thing between this tree and an implementation that summons a specialist on **every**
refusal — a build that passes every positive arm of a–d while triggering a specialist for a
typo, colliding with `BO-210`'s whole population, and breaking `GE-127f`'s load-bearing
"zero addition costs nothing".

Its second arm covers the population nobody would think to test: every standard in the repo
that refuses today states no disposition at all, because the disposition is a new fact
`GE-127f-3` introduces for one rule. An implementation reading the field's *absence* as the
specialist case passes the first arm and is caught only by the second.

### A depth-1 finding that constrains the whole design

The hold and the re-offer both need a party that outlives the refusal **and** can engage
another party. The commit agent cannot be it. Verified against `ADR-019`:

> an agent running at depth 1 cannot itself invoke the Agent tool. Any call beyond depth 1
> is silently dropped — no error is raised.

`ADR-019` exists because this already happened once, when `ticket-supervisor` at depth 1
tried to spawn phase agents and no phase templates ever applied. The delivery step *is* a
depth-1 agent, so the holder must be the depth-0 driver — and a hand-run commit at a
terminal has no actor at all.

Every arm of `BO-3800a-1` therefore opens *"Given a ticket is being driven"*, and the record
carries a headed open-question section stating that the out-of-drive case is an **amendment
to `BO-3800a`** and not its child's to declare. No clause claims that case is in scope or
out of it; `BO-3800a`'s criteria currently promise something its only child does not cover,
and that gap is left visible rather than papered over. **It needs a product decision.**

### What is not claimed

Separation of duties is invisible at delivery time — one change, one identity. Anti-shuffling
is invisible in a diff — moving *new* work out is desired, moving *existing* content out to
make a number fall is the failure, and the two look identical. The L0 forbids any descendant
asserting the restructuring *was* performed by the specialist.

What the tree does promise is **sequencing**: on the refusal path the specialist is actually
asked, before the retry, with the demand intact. Reachability-shaped, observable, and not
satisfiable by a system that does nothing. `BO-3800b-1`'s mandatory injection is *the inert
ask* — print the name and the demand, engage nobody — which is the `fast-lane-build.js`
shape this record exists to catch.

### Nothing here is buildable yet

`INF-800f` is a hard precondition: the restructuring craft is a slash command today,
reachable by hand and by nothing else. Until that lands, `BO-3800` is a specification
waiting on a capability.

### Also in this change

The build-orchestration `PROJECT_CONTEXT` gains the placement rationale and the `BO-210`
seam, and its "next free L0" pointer is corrected to `BO-3900`. That line had gone stale for
the **third** time — it previously claimed `BO-1900`, `BO-2300` and `BO-3300` while the store
had already moved past each. The reason is now recorded: loose `BO-NNNN.yaml` records sitting
at the component root reserve their hundred exactly as a folder does, so listing folders
alone undercounts.

Two known issues found while doing the work are filed: a workflow run made permanently
unresumable by a cached bad path, and test fixtures that hand-enumerate their production
dependencies.
