---
title: "fix: harden the twin build drivers against phantom-done completion writes"
date: "2026-08-25"
time: "07:58"
type: manual
components:
  - build_orchestration
summary: "A ticket could be recorded done without a single phase having run, a gate could report success and leave no sign-off with nobody noticing, and an unfinished epic could return status: ok. The twin drivers now take every completion decision from the ticket's own record, refuse to decide anything from an empty required set, hold back on an unusable plan reply, and emit a machine status that agrees with their own verdict."
description: "Four HIGH defects were found in the build-feature.js / build-ticket.js twins during a live EPIC-DeploymentCompleteness drive, and fixing them exposed three more that the fixes themselves introduced — all seven are addressed here across four review rounds, each round mutation-verified. (1) Completion is now decided by reading the ticket's own record back after every dispatch and adjudicating the sign-offs actually present, never from the drive's in-memory tally of phases it believes it ran; a gate that returns success and leaves no sign-off entry is a FAILED phase (BO-2900f-1-i/-ii/-iii). (2) The completion write itself was missing, so finished tickets stayed todo and blocked their epic while naming nothing to fix; it is added and bounded — held back, blocked, unrecorded and UNREADABLE all read as not done, and an unreadable record is its own case rather than being folded into the empty-list path (BO-400a-2-ii/-iii). (3) A completion decision taken over an EMPTY required set said yes to every ticket: a ticket whose agents map is absent, empty or entirely not_needed was written status: done having dispatched nothing and proved nothing. The refusal now lives inside the decision, not on the one route that reached it, so no caller can arrive at a done write through an empty required set however it got there (BO-400a-2-iv). (4) `ticketPlan || {}` swallowed a dead or truncated planner reply and turned an infrastructure failure into that same vacuous completion; an unusable reply now holds the ticket back naming the planning failure, while a usable reply whose phases are all settled still flows through (BO-1900a-4-ii). (5) The per-ticket payload returned status: ok while carrying ticket_completed: false; and the epic returns did the same one level up, reporting status: ok beside epic_complete: false and a message reading 'Epic X is NOT complete'. Both now agree with their own verdict, and a genuinely complete verified epic states epic_complete affirmatively (BO-300a-5-ii). (6) That affirmative verdict then made the removals-only branch authoritative, producing a payload that named one ticket as both completed and not built; removals are now partitioned against the drive's own completed set at all four recheck call sites — removed-and-completed reports success, removed-and-not-completed withholds (BO-300a-5-iii). (7) Phase dispatches never sent the ticket_path token that 8-30 agent templates gate their sign-off protocol on, which is why sign-offs went missing in the first place (BO-1900a-4/-4-i). Every AC is covered behaviorally: each test executes a real driver through a node harness and asserts on the ticket .md left on disk and the payload returned, because a source-grepping test passes on a guard that is computed and then ignored. Twin parity verified mechanically rather than asserted."
---

## Entry

A live `EPIC-DeploymentCompleteness` drive recorded tickets as complete that had
gates which never left a sign-off. Four HIGH defects were found, and each round
of fixes introduced another — the same shape every time: **a remedy makes a
previously inert path active or authoritative without extending the guard to
that path.** Seven defects, four review rounds, all mutation-verified.

The through-line of the fix is one rule: **absence of evidence must never read
as success.**

- The drive's own tally of phases it thinks it ran is no longer admissible.
  Completion is adjudicated against sign-off entries present in the ticket's
  record, read back after every dispatch.
- An empty required set is *"we learned nothing"*, not *"everything passed"*.
  The refusal sits inside `completionVerdictFromRecord`, so it covers every
  route into the decision rather than the one that happened to reach it.
- A planner reply the drive cannot use is a hold-back, not an empty plan.
- An unreadable record outranks every other diagnosis: *"could not look"* and
  *"nothing outstanding"* must never produce the same answer.
- `status` agrees with the verdict beside it, per ticket and per epic.

Two defects here were the purest form of the failure this repository exists to
prevent: the anti-phantom-done batch shipped, in its own diff, a path that wrote
`status: done` on a ticket for which zero phases were required, zero were
dispatched and zero sign-offs existed.

Coverage is behavioral throughout. A grep-only test cannot tell a wired gate
from a defined-and-ignored one, so every test drives a real workflow script and
asserts on artifacts. Where the harness could not reach a case, the harness was
extended additively and default-off, so no pre-existing scenario changed
meaning.

Known follow-ups, none blocking: `completed_batches[].ticket_path` carries the
planner's spelling while the recheck fields are normalized (cosmetic — the
partition itself normalizes both sides); the `suggested_action` on the
newly-reachable unreadable-with-empty-required path is still the generic
sign-off advice; and `parseRecord`'s agents-map regex uses `\Z`, which
JavaScript does not support — a test-harness fidelity bug, worked around
default-off and deliberately not fixed here to avoid changing the input every
pre-existing scenario presents.
