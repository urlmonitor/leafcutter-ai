---
title: "KI-BO-20260930 — /finalize-feature Step 3.5 flips every inbox ticket and AC to done store-wide, not just the branch's"
description: "KI-BO-20260930 — /finalize-feature Step 3.5 flips every inbox ticket and AC to done store-wide, not just the branch's"
type: reference
category: reference
status: active
created: '2026-09-30'
last_updated: '2026-09-30'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-20260930 — /finalize-feature Step 3.5 flips every inbox ticket and AC to done store-wide, not just the branch's

- **Severity:** blocker — it writes `done` onto work that was never built, and the
  falsification is silent, durable, and indistinguishable from real completion
  afterwards. Indexed `blocker` per the register's worst-reading rule.
- **Status:** open
- **Occurrences:** 1 observed directly; the defect is in the closure step every epic
  finalization runs, so every prior finalization is a candidate
- **Where:** `.claude/workflows/finalize-feature.js`, Step 3.5 (cross-epic closure)

**Symptom.** Step 3.5 is meant to close the tickets and ACs the finalizing branch
actually delivered. It instead walks the whole inbox and sets **every** ticket and AC it
finds to `done` — including records belonging to unrelated, unstarted epics. The commit
it produces looks routine; the damage is visible only in `git show <sha> --stat`, which
is not something a finalize run prompts anyone to read.

**Why this is worse than a wrong status field.** `done` is load-bearing in this repo,
not descriptive. `ticket-prioritizer` treats a `done` ticket as satisfying other
tickets' `depends_on`, so falsely-closed records unblock work whose prerequisites do not
exist. `ac_prioritizer` stops surfacing a `done` AC, so the work silently leaves the
backlog rather than failing loudly. And nothing downstream re-derives the truth: once
written, a false `done` is indistinguishable from a real one, so the error is not
self-correcting and compounds with every subsequent planning pass.

**Detection.** Before finalizing, record the status of every sibling record you are
*not* closing. After the closure commit, re-read them. Any that changed were changed by
Step 3.5. `git show <sha> --stat` on the closure commit is the fast version: a closure
for one ticket that touches dozens of AC files under `docs/acceptance-criteria/` is the
signature.

**Workaround — close by hand, with a sibling baseline.** This is a workaround for a
defect that should be fixed, not a procedure worth promoting: it exists because Step 3.5
cannot currently be trusted to scope itself, and it should disappear when Step 3.5 is
fixed. Do not build tooling around it.

Capture the statuses of the sibling records before touching anything, close the one
ticket and its ACs by hand, then re-read the same list and diff. The check has to be a
*captured* before-state, not a recollection — the whole failure mode is a write nobody
noticed. Used for `TQ-600a-5` on 2026-09-30: `TQ-600a-2/3/4/6/7/8` were recorded `todo`
beforehand and verified still `todo` afterwards, which is what established that the
hand closure leaked nothing. An unverified hand closure proves nothing that the
automated one does not.

**Two further finalize defects hit on the same drive**, recorded here because together
they are why the hand path was taken rather than a retry:

- Step 3 false-halts on the build layer — deploy-dependent tests read as regressions
  when the step skips `build.py`.
- The environment bootstrap runs `poetry`, but this repo installs from
  `requirements-dev.txt`, so the bootstrap fails before the step does anything.

**Remediation.**

1. Scope Step 3.5 to the records the finalizing branch actually touched — derive the set
   from the branch diff, not from an inbox scan. An inbox scan has no way to know which
   records this branch delivered, so there is no safe filter to add to the current shape.
2. Until that lands, have Step 3.5 print the records it is about to close and require
   confirmation. The step already runs behind prompt gates for destructive git
   operations; writing `done` across the store is destructive in the same sense.

**Related.** `KI-BO-20260927-finalize-triage-baseline-predates-merged-main` (a different
finalize defect, in the test-triage step rather than the closure step).

**Pattern:** a closure step that infers "what this branch delivered" from a store-wide
scan rather than from the branch, so its blast radius is the store and not the branch.

---
