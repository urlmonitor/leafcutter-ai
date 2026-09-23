---
title: "Plan-feature entry point unblocked and decision gates made honest — EPIC-StartingNewWorkTheProperWayAlways complete (ACD-2100, 25 of 25 tickets)"
date: "2026-09-14"
time: "22:18"
type: manual
components: 
  - ac_driven_dev
  - worktree_manager
  - build_pipeline
  - commit_guardian
summary: "Finished the epic that makes /plan-feature reliable: it now starts correctly from the self-hosting layout, its startup errors say what actually went wrong, and a paused run's decision gate can no longer be misread, spoofed, or answered out of order."
description: "65 commits (63 non-merge plus 2 merges of an advancing origin/main) complete all 25 ACD-2100 tickets. This entry lists the 50 most recent; the remaining 15 are the earlier ACD-2100a/b foundational fixes already recorded in the 2026-09-07 partial entry for PR #652. Closes KI-ACD-004 (self-hosting layout) and KI-ACD-005 (decision-gate correctness); narrows but does not close KI-ACD-009."
pr: 652
commits: 
  - a7f5e5a9a
  - 3881e9039
  - 6378f4dd8
  - c8704a1ac
  - 3404352e0
  - b328b874d
  - d4146f162
  - fff85d67c
  - 15f745bb1
  - 29b214589
  - f5cf4a166
  - e5eae49a6
  - 092a096a1
  - dfead4260
  - bf0c80d14
  - 4a047ccc0
  - 8d5779cbf
  - f76af10b0
  - 38b9e54d5
  - a13444eba
  - 45ad83414
  - f7c6d1723
  - be66f095f
  - 2ed6fc231
  - dc23fa138
  - 33908f8a3
  - a8b0c75e9
  - 0a221ed77
  - 319e6ff9a
  - f9ee688c0
  - fcaef7afd
  - e3aa88c2a
  - e89c8b33a
  - e4ee392db
  - e55521a0e
  - f41c23146
  - d908e5bcc
  - 0570c9dc8
  - 65a80bce2
  - 46def2668
  - f64a6318f
  - f1c595659
  - fcadb4375
  - 484efdfe7
  - ccc88542d
  - 295bc47c5
  - 3a0f673d2
  - 779627ba6
  - 2d50ca47b
  - 57c1ef374
breaking: false
---

## Entry

EPIC-StartingNewWorkTheProperWayAlways implements `ACD-2100` — "the entry point is
unblocked" — end to end: all 25 tickets are now `done`. A prior partial entry
(2026-09-07, PR #652, 13 of 25 tickets) already recorded the earliest ACD-2100a/b
foundational work in detail; this entry covers the epic's completion and is not a
duplicate of that one. The branch merges an advancing `origin/main` into itself twice
(`f41c23146`, first catch-up; `a7f5e5a9a`, second catch-up); neither merge carries
ACD-2100 behavior beyond what is described below.

**Self-hosting layout unblocked (ACD-2100a family; closes `KI-ACD-004`).** `/plan-feature`
now starts correctly when run from inside this repository's own self-hosting layout, not
just from a consumer project. Worktree setup, agent-registry reads, and pause-record
writes all resolve their paths from the repository itself — via `git rev-parse
--show-toplevel` with a bounded, repo-anchored fallback — instead of the untracked
workspace directory that sits above it. `docs/known-issues/ac-driven-dev.md` now records
`KI-ACD-004` as fixed, with re-run test evidence checked against the current code rather
than taken on the epic's own say-so.

**Startup permission check moved to a real pre-flight script (ACD-2100b family).** The
workspace-setup permission check that gates `/plan-feature`'s startup previously lived
inside the workflow body and collapsed every non-`ok` outcome into one generic
permission-denied verdict. It is now a standalone pre-flight script
(`scripts/worktree/check_workspace_setup_permission.py`), invoked from
`templates/skills/plan-feature/SKILL.md`, whose verdict is passed into the route rather
than recomputed inline — so a broken or unreadable registry is no longer mistaken for a
real access-control decision, and the route no longer halts blaming a registry field that
was correct all along. This narrows (does not close) `KI-ACD-009`: the epic's own
ACD-2100a/b siblings are genuinely re-pointed at the new script and pass, but a sibling
ticket outside this epic (`BO-1500f-1`, still `todo`) has two test files that still assert
the retired in-workflow dispatch path — four real `AssertionError`s under
`AC_ENFORCE_STRICT=1`, currently masked only by that ticket's own `todo` status.

**Paused runs behave correctly in every direction (ACD-2100c family; closes
`KI-ACD-005`).** A run that stops to ask a person previously had four distinct ways to
misbehave on the way back in; all four are fixed:

- An agent's own out-of-scope refusal is no longer read as "the user chose cancel" — all
  three reachable `status: "cancelled"` terminal payloads in `plan-feature.js` now carry
  `cancelled_by: "person"`, set only via a `resolveGate()` decision object already gated on
  `resume_answer.channel === "person"`, so a legitimate discard is distinguishable from a
  fallback discard after the fact (`e5eae49a6`).
- An answer is honoured only when it genuinely came from the person: `resolveGate()` now
  checks provenance, not just shape — a well-formed `resume_answer` is accepted only when
  its `channel` is exactly `"person"`; anything else is treated as an unanswered gate
  (`dfead4260`).
- An answer naming a different decision than the one the run is actually paused at is
  refused without discarding drafted work: a new `peekPausedGateId()` helper reads the
  durable pause record before the workflow decides whether to skip re-authoring, closing a
  gap where a naive resume check would wrongly skip a later stage's authoring dispatch
  (`bf0c80d14`).
- A resumed run picks up at its real paused decision point rather than the wrong one
  (`45ad83414`), and a missing or falsy final-gate result now fails closed to `status:
  "undetermined"` as a standing invariant over the exit path, rather than relying on a
  since-removed destructive default line (`e5eae49a6`).

**Where the route stops, and how to answer it, are now written down (ACD-2100d/e
families).** A sequence diagram
(`docs/architecture/diagrams/c3-008-plan-feature-decision-gate-sequence.md`) and an
operator how-to (`docs/how-to/resume-a-paused-plan-feature-run.md`) document the pause/
resume flow end to end. A reference page
(`docs/architecture/plan-feature-layout-and-startup-checks.md`) documents the layout and
startup checks from the `a`/`b` families above. The installed route now reaches the same
first question as the source route (`dc23fa138`), and `build.py`/`build_phases.py` gained
a before/after regression check that runs on install to catch a route-start divergence
between source and deployed copies (`f76af10b0`).

**Other closeout work.** `templates/scripts/commit_guardian/frontmatter_validators.py`
and `templates/hooks/ticket_frontmatter_guard.py` now accept the repo-relative
`depends_on` path form used by this epic's tickets. All 25 tickets' `pull-request` phase
was reconciled to `not_needed` (`9682d6adf`) — `build-feature.js` deliberately defers the
`pull-request` phase for every epic member since one epic-level PR (#652) covers the whole
branch, but the ticket generator was emitting `pull-request: needed` regardless; the
durable fix belongs in the generator and is not part of this epic. Closing the epic's
known-issues review also filed one new entry in `docs/known-issues/ac-store.md`:
`mark_ac_done.py --test-root` cannot pass any `test_required: false` leaf AC, because
`done_proof.py::verify_done_eligible` has no leaf-level exemption for that field (only a
composite-level one), which forced hand-edited `work_status` bypasses for docs-only ACs in
this epic.
