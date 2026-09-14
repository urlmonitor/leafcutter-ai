---
title: "KI-ACD-022 — Conditional phase agents are written into the agents map without the frontmatter fields they are conditional on, and one of the two fields is written under a different name"
description: "KI-ACD-022 — Conditional phase agents are written into the agents map without the frontmatter fields they are conditional on, and one of the two fields is written under a different name"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/README.md
---

# KI-ACD-022 — Conditional phase agents are written into the agents map without the frontmatter fields they are conditional on, and one of the two fields is written under a different name

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** `scripts/ac_store/generate_ticket_from_ac.py` → `_build_agents_map`;
  `templates/agents/user-surface-smoker.md` (reads `user_facing_surface`);
  `templates/agents/documentation-verifier.md` (reads `requires_documentation_verification`)

**Symptom.** The generator marks `user-surface-smoker` and `documentation-verifier` as `needed`
in a generated ticket's `agents:` map while writing **neither** of the frontmatter fields those
agents key on. Both templates state the contract explicitly — *"Only emitted in agents: map when
`<field>` != null"* — so the generator produces exactly the state each agent is documented never
to be dispatched in.

**Evidence.** `generate_ticket_from_ac.py --ac BP-1100g-4`, 2026-08-26. Generated frontmatter:

```yaml
agents:
  documentation-verifier: needed      # reads requires_documentation_verification
  user-surface-smoker: needed         # reads user_facing_surface
documentation_required: true          # <- the only field written
```

`grep` for `user_facing_surface` and `requires_documentation_verification` in the generated
ticket returns nothing. Both had to be added by hand before dispatch.

**The near-miss is the interesting part.** The generator writes `documentation_required: true`.
The agent reads `requires_documentation_verification`. These are **different fields**, and the
first is close enough to the second that a grep for "documentation" in the frontmatter looks
satisfied while the condition is unset. A reviewer scanning for "did the generator wire the doc
verifier" sees a plausible field and moves on.

**Consequence.** `documentation-verifier` is documented fail-closed — *"an ambiguous parse or
exception emits `status: blocker`, never `status: ok`"* — so the likely outcome is a halted
drive. The milder outcome is worse: a phase that cannot complete leaves itself `needed`, which is
exactly the outstanding-phase blocker the `BP-1100g-3` drive hit after nine hours of work, and
which reports as a build failure rather than as a generator defect. Either way the cost is paid
at the end of a long drive, by which time the cause is far away.

**The routing lever cannot express the case it is being used for.** `user-surface-smoker` is
selected from the AC's `declares_side_effect`, which `check-ac-schema` derives from the Then
clause via a durable-effect phrase list (*written to disk*, *persisted*, *leaves the system in a
different state*). `BP-1100g-4`'s deliverable is a commit-time **refusal**, whose entire point is
that the system is left **unchanged** — so the derivation correctly returns `False`, and the
authored `true` had to be corrected to match. But the AC's own note says the refusal message is
*"exactly the kind of user-facing output user-surface-smoker's placeholder negative control
exists to check."* Both statements are right: it is user-facing output, and it is not a durable
effect. `declares_side_effect` is the only lever the generator has, and it cannot distinguish
"produces no user-facing surface" from "produces a user-facing surface that is a refusal".

**Fix direction.** Two separable pieces; do the first even if the second is deferred.

1. **Never emit a conditional agent without its condition.** When `_build_agents_map` adds
   `user-surface-smoker` or `documentation-verifier`, write the field the agent reads in the same
   step, and derive the field name from one place so the `documentation_required` /
   `requires_documentation_verification` split cannot recur. A generated ticket that names a
   conditional phase and omits its condition should fail the generator's own `--verify`, not the
   drive nine hours later.
2. **Give the smoker its own routing signal.** `user_facing_surface` is the field it actually
   reads and it already has a vocabulary (`slash_command | pre_commit_hook | agent_orchestrated |
   cron`). Route on an AC-level equivalent rather than borrowing `declares_side_effect`, whose
   derivation is deliberately narrow and calibrated for a different question. Overloading it
   would either widen the durable-effect phrase list until it marks everything — which the
   BO-2900g-2 constraints reject as indistinguishable from marking nothing — or keep mis-routing
   gates whose output is a refusal.

**Related.** `KI-ACD-002` (documentation-verifier fail-closing on every generated ticket for a
different generator-shape reason — same agent, same fail-closed posture, and the two should be
fixed together). `KI-ACS-009` (the `declares_side_effect` derivation and where its rule actually
lives).

**Pattern:** a dispatcher that selects a conditional consumer on one field while the consumer
reads another, with a similarly-named third field present to make the omission look handled.

---
