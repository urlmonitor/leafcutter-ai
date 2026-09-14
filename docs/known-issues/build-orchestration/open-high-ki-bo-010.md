---
title: "KI-BO-010 — `/quick-fix`'s divergence gate is a first-token substring match, and its own remedy loops"
description: "KI-BO-010 — `/quick-fix`'s divergence gate is a first-token substring match, and its own remedy loops"
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

# KI-BO-010 — `/quick-fix`'s divergence gate is a first-token substring match, and its own remedy loops

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/workflows-js/quick-fix.js:292-306` (the BP-600e-2 divergence check)

**Symptom.** After a confirmed red baseline, the workflow halts with "The test failure
suggests the root cause may differ from your diagnosis" — on diagnoses the tests
unanimously confirm. The whole check is:

```js
const divergenceCheck = failureMsg.length > 0 &&
  !failureMsg.toLowerCase().includes(root_cause.toLowerCase().split(' ')[0])
```

It takes the **first whitespace-delimited token** of a prose diagnosis and asks whether
that literal string appears in the pytest output. Any leading markdown defeats it: a
`root_cause` beginning `` `handoff` `` yields the token `` `handoff` ``, backticks
included, which never appears in test output that says `handoff`. A leading article
("The adjudication branch…" → `the`) inverts the failure the other way — `the` appears in
essentially every pytest output, so the gate silently passes regardless of whether the
diagnosis is right. It is a coin flip decided by the first word's punctuation.

**Evidence.** Observed 2026-08-18 fixing the handoff-routing defect. The red phase
produced three failures that reproduced the diagnosis precisely — `test-writer` dispatched
once instead of twice in both drivers, and an unparseable handoff target advancing to
`pr-reviewer` instead of failing closed. The gate halted anyway on the backtick mismatch.
Re-running with the identical diagnosis reworded to open with a bare `handoff` cleared it.
Nothing about the analysis changed; one word lost two backticks.

**The stated remedy does not work.** The halt message reads *"To continue, re-run
/quick-fix with the same args."* The check is a pure function of `root_cause` and the
failure text, with no confirmation flag and no persisted state, so re-running with the
same args recomputes the same verdict and halts identically. The only exits are to reword
the diagnosis until the first token happens to match, or to abandon the workflow — and the
message advises neither.

**Why this matters more than it looks.** A gate this coarse trains people to defeat it.
The reliable way past it is to open `root_cause` with a common English word, which makes
the check pass unconditionally — so the failure mode it converges on is not false halts
but a permanently green gate that never reads the diagnosis at all.

**Fix direction.** Delete it or make it real. A first-token substring match cannot assess
whether a failure corroborates a diagnosis, so it should not be shaped like a verdict — at
minimum downgrade it to an advisory `log()` that never halts. If a genuine check is wanted,
it belongs with an agent that reads the failure and the diagnosis and judges them, and it
needs a confirmation path so an operator who has looked at both can proceed. Whatever
replaces it must make its own remedy reachable.

Filed as KI-BO-008 while this work sat uncommitted; renumbered to 010 on landing, main
having published a different KI-BO-008 and a KI-BO-009 in the interim.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M8 (a check that cannot assess
correctness reporting a verdict anyway), in its fail-closed form.

---
