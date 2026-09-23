---
title: "KI-ACD-005 — User approval gates are dispatched to a `status-checker` agent, whose out-of-scope refusal is parsed as \"the user chose cancel\""
description: "KI-ACD-005 — RESOLVED 2026-09-14: user approval gates were dispatched to a status-checker agent whose out-of-scope refusal was parsed as cancel; resolveGate() no longer dispatches a live gate and a non-person answer now pauses rather than discards."
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-09-14'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/README.md
---

# KI-ACD-005 — User approval gates are dispatched to a `status-checker` agent, whose out-of-scope refusal is parsed as "the user chose cancel"

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`blocker`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** blocker
- **Status:** fixed (2026-09-14 — landed via `ACD-2100c-1`, the outgoing half: no decision
  point ever dispatches an agent to obtain an answer, and `ACD-2100c-4`, the incoming half:
  an answer is honoured only when `resume_answer.channel === "person"`; anything else,
  including its absence, leaves the run paused with a provenance-worded reason rather than
  resolving to `cancel`). See "Fix landed" below.
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/workflows-js/plan-feature.js` — the PT-phase approve/edit/cancel gate (`pt-gate-mockdata`); `resolveGate()` / gate answer parsing. **Caveat on this line:** the exact
  line numbers this register cites for `resolveGate()` elsewhere had already drifted out of
  date before today (see the `KI-ACD-019` cross-reference note on this component); the "Fix
  landed" section below cites line numbers re-verified against the current file rather than
  carried forward from this entry's original filing.

**Symptom.** The gates that the skill documents as *user* decision points are not
presented to a user at all. They are dispatched as prompts to a `status-checker` agent.
That agent — correctly — replies that approving product-truth artifacts is not its job.
Its reply is then parsed as a gate answer of `action: cancel`, and the pipeline
discards the run. **No human was involved at any point.**

**Evidence.** The final agent result in the run journal for `wf_1969bd0b-43f`:

```json
{"action": "cancel",
 "feedback": "This request is outside status-checker's defined scope (ticket-state
  verification and closing per docs/agents/conventions.md). status-checker has no
  defined process for reviewing or approving mock-data-author's product-truth
  artifacts, and no ticket_path or sign-off context was provided for this dispatch.
  Recommend routing this approval gate to the agent/role actually responsible for
  product-truth review ... not status-checker."}
```

The agent diagnosed the defect and named the fix in its own refusal.

**Why this is worse than a hang.** A gate that cannot reach a user should **pause and
persist** a resumable state. Instead the failure mode resolves to `cancel`, which is the
one answer that throws work away. Any agent reply the parser cannot map to
`approve`/`edit` becomes a destructive default.

**Fix direction.** Gates must not be answered by an agent. Either surface them to the
real user, or persist a pause record and exit with a status that says "awaiting input"
— and re-enter via `args.resume_answer`, which the script already supports (ADR-024).
Separately, harden the answer parser: an unrecognised or refusal-shaped reply must
never resolve to `cancel`; fail to `pause`, never to `discard`.

**Fix landed 2026-09-14 (`ACD-2100c-1` / `ACD-2100c-4`).** Verified directly against the
current `templates/workflows-js/plan-feature.js`, not taken on the epic's own say-so:

- `resolveGate()` (`:1563`) checks `args.resume_answer` before ever considering a live
  dispatch. When no valid, person-attributed answer is present, it discards `liveGateFn`
  entirely — `void liveGateFn; return pauseAtGate(gateId, runId, context, descriptor);`
  (`:1726-1727`) — rather than dispatching an agent to answer on the user's behalf. This
  closes the specific defect this entry describes: there is no code path left in which a
  `status-checker` (or any other agent)'s reply can be parsed as the user's decision, because
  no such dispatch is made.
- The incoming half (`ACD-2100c-4`) checks provenance as a property of the answer, never
  its content: `if (args.resume_answer.channel !== "person") { return { status:
  "paused_awaiting_input", run_id: runId, gate_id: gateId, reason: "This answer did not come
  from the person running the route, so it was not treated as their decision..." }; }`
  (`:1590-1600`). An unrecognised, malformed, or non-person-channel reply now resolves to
  `paused_awaiting_input`, never to `cancel` — exactly the "fail to pause, never to discard"
  fix direction named above.
- All five decision points named in `ACD-2100c-1`'s own criteria (product-truth,
  mid-pipeline, final, covered-route, orphan-resolution) route through this same
  `resolveGate()` — confirmed at each of the five call sites (`:2559`, `:2648`, `:2819`,
  `:3182`, `:3322`) — so this is the class-wide mechanism the criteria required, not a
  per-site patch that could leave a sixth gate unrouted.
- Covered by `unit_tests/workflows/test_acd_2100c_1.py` (re-run 2026-09-14: 4 passed, 15
  subtests passed) and `unit_tests/workflows/test_acd_2100c_4.py` (re-run 2026-09-14: 6
  passed).

---
