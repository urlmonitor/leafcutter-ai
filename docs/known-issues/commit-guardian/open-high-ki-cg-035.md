---
title: "KI-CG-035 — `check-proof-promise-claim` is a done-time gate that fires at creation time, so no generated epic scaffold can be committed"
description: "KI-CG-035 — `check-proof-promise-claim` is a done-time gate that fires at creation time, so no generated epic scaffold can be committed"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-035 — `check-proof-promise-claim` is a done-time gate that fires at creation time, so no generated epic scaffold can be committed

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1 epic (27 tickets); structurally affects every generated epic
- **First seen:** 2026-08-31 · **Last seen:** 2026-08-31
- **Where:** `templates/scripts/commit_guardian/check_proof_promise_claim.py` — `main()`; rule is BP-1100g-4

**Symptom.** The hook reads each staged **ticket** file, extracts the proof kinds its AC
promises via `test_spec`, and refuses the commit unless a test already claims each one with a
matching `# covers:` / `# angle:` tag. It has no notion of *when* in a ticket's life it is
being asked.

A freshly generated epic cannot satisfy it, by construction. The tickets were written seconds
earlier by `goal_to_epic`; their tests are written **later**, during each ticket's own drive,
by `test-writer`, immediately before its coder runs — which is the TDD order this package
mandates everywhere else. So the gate demands, as a precondition of *creating* a ticket, the
very artefact the ticket exists to produce.

The effect is that **every generated epic scaffold is unlandable** until the hook is skipped.

**Evidence.** 2026-08-31, committing `EPIC-SuppressionNarrowsNeverDisables` (27 tickets, all
ACs `work_status: todo`, no test claiming any of them and none asserted to). The hook produced
one refusal per promised proof — 13 in the first screenful alone, across `GE-123d-3`,
`GE-123b-3` and `GE-123d-4-ii` — each instructing the committer to *"write a test tagged
'# covers: …'"* for work that has not been started. Committed with
`SKIP=check-proof-promise-claim`, recorded in the commit message.

This is not an argument against the gate. Its purpose — a promised proof that never arrives is
phantom-done — is exactly right, and it should keep full force at the commit that marks an AC
`done`. The defect is the trigger, not the rule.

**Detection.** Try to commit any freshly generated epic whose ACs carry a `test_spec`.

**Workaround.** `SKIP=check-proof-promise-claim` on the scaffold commit only, with the reason
recorded. Safe **only** while every AC in the commit is `work_status: todo` and nothing claims
coverage — state that explicitly, because a blanket habit of skipping this hook would restore
precisely the phantom-done hole it closes.

**Fix direction.** Key the check on lifecycle rather than on existence. A promise is due when
the AC is being marked `done` (or when the ticket has entered a drive), not when the ticket
file first appears. `work_status` is already on the record and already read by neighbouring
hooks.

**Related.** `KI-ACS-018` (the generator whose output this gate then refuses). `KI-SUP-1` (the
opposite failure: a driver that commits *past* its own recorded blockers).

---
