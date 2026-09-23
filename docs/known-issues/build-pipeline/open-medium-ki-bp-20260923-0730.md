---
title: "KI-BP-20260923-0730 — BP-1100e-1 is a composite marked done whose seven children are unproven, invisible until the parent is staged"
description: "KI-BP-20260923-0730 — BP-1100e-1 is a composite marked done whose seven children are unproven, invisible until the parent is staged"
type: reference
category: reference
status: active
created: '2026-09-23'
last_updated: '2026-09-23'
components:
  - build_pipeline
  - commit_guardian
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/README.md
---

# KI-BP-20260923-0730 — `BP-1100e-1` is a composite marked done whose seven children are unproven, invisible until the parent is staged

- **Severity:** medium — the parent's `work_status: done` is not currently supported by its
  children. No behaviour is wrong; the store's own claim is.
- **Status:** open — no AC
- **Occurrences:** 1 (surfaced 2026-09-23; the underlying state is older)
- **First seen:** 2026-09-23 · **Last seen:** 2026-09-23
- **Where:** `docs/acceptance-criteria/build_pipeline/BP-1100-phantom-done-prevention/BP-1100e-1.yaml`

**Symptom.** Staging `BP-1100e-1.yaml` in any commit produces:

```
[check-done-proof] BP-1100e-1: composite BP-1100e-1 is marked done but its covered_by
children are not all done-and-covered — unproven: BP-1100e-1-i, BP-1100e-1-ii,
BP-1100e-1-iii, BP-1100e-1-iv, BP-1100e-1-v, BP-1100e-1-vi, BP-1100e-1-vii
```

All seven children carry `work_status: done`; what they lack is the covers-tag proof the
gate requires. The parent has claimed `done` on top of that since before this branch —
confirmed with `git show HEAD:...BP-1100e-1.yaml`, which already reads `work_status: done`.

**Why it stayed hidden.** Exactly the mechanism CLAUDE.md's "AC-store commits — stage the
parent alongside the child" section describes: these hooks validate only the files in the
commit's index, never the store. Children get edited and committed constantly; the parent
is almost never staged, so the one check that would look at it is never handed it. Its
silence was never a pass — it had not been given the file. This surfaced only because
`BP-1100e-1-viii` was added and the parent was staged to carry the `covered_by` back-link,
which is the first time in this branch's history that the parent entered an index.

It is the same shape as the store-wide sweep recorded in that section, which found 20
composites marked `done` with unfinished children.

**Not caused by the change that surfaced it.** The parent's `work_status: done` and its
children's missing proof both predate this branch.

**A back-link is owed.** `BP-1100e-1-viii` was added on this branch and is deliberately NOT
listed in this parent's `covered_by`. Adding it put the parent into `check-done-proof`'s
`ci-changed` scope, where it fails on the debt above and blocks the merge — and adding an
entry to a composite that is already failing its own proof gate decorates a record that is
already wrong rather than making it accurate. The child records the relationship in its own
`depends_on: [BP-1100e-1]`, so the link is not lost. **Add `BP-1100e-1-viii` to this
parent's `covered_by` as part of clearing the debt below**, not before: the two changes have
to land together or the parent goes straight back to blocking.

Note that until `BO-2500a-6-ii` landed on the same branch, this failure was reported as
"composite BP-1100e-1 has no coverable children" — a misclassification that hid the real
state. The message quoted above is the accurate one.

**Fix direction.** Either supply the missing covers-tag proof for the seven children — the
honest route, since they are genuinely implemented — or demote the parent's `work_status`
until that proof exists. Do not resolve it by removing children from `covered_by`: that
makes the claim true by shrinking what it is a claim about, which is the failure this whole
BP-1100 family exists to prevent.

Worth pairing with a store-wide sweep rather than fixing this one composite, since the
mechanism guarantees there are others in the same state that nobody has staged recently.

**Related.** `BP-1100e-1-viii` (the change that surfaced it), `check-done-proof`,
CLAUDE.md's "AC-store commits — stage the parent alongside the child".

**Pattern:** a check that only ever sees what a commit hands it, guarding a fact that lives
in files commits rarely touch — so its silence measures staging habits, not correctness.
