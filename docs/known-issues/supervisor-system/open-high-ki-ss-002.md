---
title: "KI-SS-002 — A gate adjudicated `failed` does not stop the drive, so the commit phase still runs"
description: "high — a phantom-done defect one level up from the ones the package exists to"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - supervisor_system
related_docs:
  - docs/known-issues/supervisor-system.md
  - docs/known-issues/README.md
---

# KI-SS-002 — A gate adjudicated `failed` does not stop the drive, so the commit phase still runs

> One known issue, split out of `docs/known-issues/supervisor-system.md` on
> 2026-09-14. Index: [supervisor-system.md](../supervisor-system.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high — a phantom-done defect one level up from the ones the package exists to
  prevent
- **Status:** open — code is on `main` and live, **but by a different mechanism than the one
  originally recorded** (see the correction below)
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-26 (re-verified against `37655862`)
- **Where:** `templates/workflows-js/build-feature.js:1757-1772` (the `!verdict.verified`
  branch) and `:305-328` (`phaseOrder`, `commit` at priority 12)

**Symptom as observed.** During the epic drive, `pr-reviewer` and `documentation-verifier` both
returned `status: blocker` on ticket `01_TICKET-20260818-GE-122a-1.md`. Neither blocker was
remediated. The drive nevertheless proceeded to the `commit` phase, which committed and set
`commit: signed_off` while the frontmatter still read:

```yaml
documentation-verifier: failed
pr-reviewer: failed
```

The commit message did name both open blockers, so the record is not dishonest — but a gate that
reports a blocker and is then committed past provides no enforcement. The two blockers were real:
one was a performance regression that would have shipped a commit-time gate slow enough to be
routinely bypassed, the other a malformed contract line.

**CORRECTION — the mechanism named on the branch is closed; the defect is not.** The branch
recorded the cause as *"the precondition check is missing, not the ordering"*, implying an
agent-reported blocker walks straight past `commit`. On `main` that specific path is **shut**:
`build-feature.js:1656` intercepts `resultStatus === "blocker" || "failed"`, and every
classification outcome either returns `status: "blocked"` (mechanical-retries-exhausted, design,
halt, unknown) or `break`s out of the phase loop (`cross_agent`). `commit` cannot be reached that
way. Filing the original text unchanged would have pointed the fix at code that already does the
right thing.

**What is actually live.** The same shape survives one branch over, on the *verification* path.
When a phase reports success but its sign-off record cannot be confirmed, the drive adjudicates
it failed — and then continues:

```js
if (!verdict.verified) {
  unverifiedPhases.push({ agent: phaseName, reason: verdict.reason });
  unverifiedReasons[phaseName] = verdict.reason;
  log(`VERIFICATION FAILED for '${phaseName}' ... The gate is adjudicated failed and is
       NOT counted as completed.`);
} else { ... }
```

There is no `break` and no `return`. `unverifiedPhases` is collected, threaded into the payload
at `:1792` and reported at `:955-956` — and consumed by nothing that stops the loop. So the
iteration advances to the next entry in `phaseOrder`, and `commit` sits at priority 12, last.
A gate the drive itself has just declared failed is followed by a commit.

The comment above that branch states the intent honestly — *"The drive continues so the remaining
gates still run and are reported, but the ticket can no longer be recorded complete"* — which is
right for a *reporting* gate and wrong when the remaining phase is `commit`. Withholding the
completion claim is not the same as withholding the commit.

**Detection.** After any drive, check for a ticket where `commit: signed_off` coexists with any
phase in state `failed`, and check the payload for a non-empty `unverified_phases`:

```bash
grep -n "failed" <ticket>.md
```

**Workaround.** Do not treat drive completion as evidence. Read the frontmatter `agents:` map
directly and confirm no phase is `failed` before merging.

**Fix direction.** Gate the `commit` phase specifically on `unverifiedPhases.length === 0` —
the collection already exists and is already correct, it is simply never consulted. Everything
before `commit` should keep running and reporting, which is what the current comment argues for
and what makes the narrow fix the right one.

**Pattern:** a signal computed correctly and then not consumed — the same shape as
`commit-guardian.md`'s `KI-CG-007` and `KI-CG-026`, here at the orchestration layer.

---
