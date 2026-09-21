---
title: "KI-BO-20260831-1930 — The driver deliberately drops the `pull-request` phase for an epic member, the generator emits it as `needed`, and nothing reconciles them — so every epic ticket halts the drive at completion"
description: "KI-BO-20260831-1930 — The driver deliberately drops the `pull-request` phase for an epic member, the generator emits it as `needed`, and nothing reconciles them — so every epic ticket halts the drive at completion"
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

# KI-BO-20260831-1930 — The driver deliberately drops the `pull-request` phase for an epic member, the generator emits it as `needed`, and nothing reconciles them — so every epic ticket halts the drive at completion

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`blocker`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** blocker
- **Status:** open — no AC
- **Occurrences:** 3 (three consecutive drives of EPIC-StartingNewWorkTheProperWayAlways,
  each halting on a different ticket as it became the first to finish)
- **First seen:** 2026-08-31 · **Last seen:** 2026-08-31
- **Where:** `templates/workflows-js/build-feature.js:406`
  (`phases.filter((p) => p.agent !== "pull-request")`) and `:1384`
  (`deferredPhases = isEpicMember ? ["pull-request"] : []`), against
  `scripts/ac_store/generate_ticket_from_ac.py`, which emits `pull-request: needed` on every
  generated ticket

**Symptom.** An epic ticket completes every phase, then the drive halts:

```
Ticket "..." was NOT recorded complete.
0 needed phase(s) are outstanding in the ticket's own record: .
The completion write failed: Refusing to set status: done. The ticket's own
frontmatter still lists `pull-request: needed` (not among the 8 agents the
request asked me to check)...
```

Note the shape: **zero outstanding phases, and a refusal anyway.** The driver's own list is
complete; the ticket's list has one more entry.

**Cause.** Both halves are individually correct and they were never introduced to each other.

The driver *deliberately* removes `pull-request` from an epic member's phase list, because a
single epic-level PR covers every ticket on the branch. That is intentional, documented in
the source, and right. The generator, which does not know or care whether its output will
land in an `EPIC-*/` folder, writes `pull-request: needed` into every ticket it produces. So
the phase is never dispatched, no sign-off is ever written, and the completion writer — which
reads the ticket rather than the driver's phase list — correctly refuses to mark done with a
`needed` phase outstanding.

**Why blocker.** It is not one ticket, it is every ticket in every epic. Measured on the
current tree, `grep -rl "pull-request: needed" tickets/00_inbox/epics/` returns **333**
tickets spanning **23** epic folders, **316** of which are not yet done. The observed epic
contributed 25 of those 333 — it was the first to hit the halt, not the size of the problem.
The drive halts on whichever ticket finishes first, so fixing that one ticket by hand just
moves the halt to the next, which is exactly what three consecutive drives did before the
pattern was visible.

**It also cannot be diagnosed from the halt message.** The message names the ticket and the
phase, so the natural reading is "this ticket is missing a sign-off" — and the natural
response, re-running the drive, reproduces it identically because the phase the ticket wants
is the one the driver has decided not to run.

**Fix direction.** Make the generator emit `pull-request: not_needed` when the target path is
inside an `EPIC-*/` folder — the ticket then states what the system actually does, and the
Sign-offs row is omitted with it (a `not_needed` agent must not appear there). The runtime
alternative — having the driver reconcile the frontmatter when it defers a phase — is worse:
it means an agent rewriting the record to match its own behaviour, which is the shape that
makes a record stop being independent evidence.

**Workaround in use — on one unmerged branch, and nowhere else.** The 25 tickets of
EPIC-StartingNewWorkTheProperWayAlways were set to `pull-request: not_needed` by hand
(`9682d6adf`). That commit is reachable from exactly one branch:
`git branch --contains 9682d6adf -a` returns `EPIC-StartingNewWorkTheProperWayAlways` and its
remote, and nothing else. On `main` not one of those 25 is corrected and the other 308 were
never touched, so anyone reading from `main` has the defect live in full. Do not read
"workaround in use" as "the pain is handled" — it is handled on a branch that has not landed.

The reasoning behind that hand-correction is worth preserving, and holds for the branch it was
made on: it is a correction, not a suppression, because `not_needed` means "explicitly
excluded from this ticket", which is precisely what the driver does. They were NOT set
`signed_off` — no per-ticket PR phase ran, and saying one did would be false.

**Sequencing warning — the 316 must be repaired BEFORE the completion guard is unified.** A
fix is being specified that makes the completion guard consistent (`KI-BO-20260831-1932`).
Today that guard has two doors and only one of them reads the ticket, so roughly two in three
of these tickets slip past it into a phantom `done` instead of halting. That leniency is the
only reason a population of 316 is survivable at all. Once the guard is consistent **all 316
halt reliably** — which is the correct behaviour, and a large immediate operational cost that
has to be paid deliberately rather than discovered. The mechanical repair of the 316 (fix the
generator, then sweep the tickets that already exist) has to land first. Unify the guard first
and the next drive halts on ticket one of 316, with 315 behind it.

**Related.** `KI-BO-20260831-1931` (the sibling record-vs-driver disagreement, on comment
status rather than phase membership).

**Pattern:** `docs/reference/false-green-mechanisms.md` — the inverse: a gate that blocks
correctly on a record the rest of the system has already decided to ignore.

---
