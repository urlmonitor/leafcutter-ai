---
title: "Two dead ends in the build pipeline: a failed phase no drive will retry, and a module name nobody decides"
date: "2026-09-07"
time: "18:00"
type: manual
components:
  - build_orchestration
  - ac_driven_dev
  - knowledge_management
  - commit_guardian
summary: "Files KI-BO-20260907-1555 (a phase recorded failed is filtered out of the dispatch set, so no later drive can ever re-run it) and KI-ACD-20260907-1555 (nothing in the pipeline binds a module or symbol name, so whichever agent needs one first invents it), each with a fix direction. Also converts two known-issues registers off the retired next-free-number id convention and re-measures the register-wide sweep."
description: "Both entries were found while driving EPIC-TrustThatAGreenCheckActuallyChecked, and both are documented against the line of code or the ticket that demonstrates them rather than against a recollection. KI-BO-20260907-1555 records that build-ticket.js computes its dispatch set with a single filter on status === 'needed' while the planner's own schema enum reports four states including 'failed' — so a phase that exhausted the failure-adjudication ladder is enumerated and then discarded, and nothing anywhere transitions it back to needed. GE-120 ticket 36 reached that state with four failed phases and zero needed ones; re-driving it dispatched no phase agent at all, and the implementation was produced only by abandoning the workflow and calling python-coder directly. The entry is explicit about what is NOT wrong, because the completion side is sound and was clearly designed with this hazard in mind: with an empty dispatch set the driver still bases its verdict on claimedPhasesForCompletion, which includes the failed phases, so the ticket is correctly held not-done. The defect is the gap between an accurate diagnosis and a remedy the driver has no mechanism to perform. The identical filter in build-feature.js was verified rather than assumed, and is named so the twin is not left behind. KI-ACD-20260907-1555 records that an AC's test_spec pins each test's name, target_dir, framework and type while no field anywhere — not in the AC schema, not in ticket frontmatter — names the module to create or the symbols it must expose. test-writer runs before any coder and is told to import the module the ticket says should exist; the ticket routinely says no such thing, with files_touched a bare package directory on most of this epic's tickets and literally empty on ticket 36. Three naming divergences resulted in one epic, and the direction was not consistent: in one the test was authoritative and pr-reviewer blocked the coder's divergent names, in the other two the implementation was authoritative and the tests were reconciled afterwards. There is no rule about who wins because there is no binding. The entry notes why the red baseline cannot catch this — ImportError is a legitimate red state for code that does not exist yet, so a misnamed import and an unimplemented AC produce the identical signal, which makes the red baseline evidence of nothing in precisely the case it is meant to cover. The fix direction is that architect-review, which already runs first and already performs the analysis, should bind the names as a deliverable rather than discarding that half; that the binding should land in a structured code-contract subsection of the Agent Contracts block rather than in prose; that test-writer and the coders should read it and refuse rather than invent when it is absent; and that it should be verified the way documentation already is, by an analogue of documentation-verifier. Separately, the id-convention sweep in KI-KM-20260826 was re-measured and its count of eleven registers was confirmed exact thirteen days on. Two were converted here — ac-driven-dev.md and commit-guardian.md, each to whichever form its own entries already use — leaving nine, which are named. A timestamp form was drafted for commit-guardian.md and corrected to date-and-slug before commit after checking that its entries run ten to two the other way. The entry also records that the grep which finds the remaining nine must match the prescription and not the phrase, since the two converted registers quote the retired wording inside the rationale that argues against it."
breaking: false
---

## Entry

### Filed

| Entry | What |
|---|---|
| `KI-BO-20260907-1555` | `failed` is a terminal phase state — `build-ticket.js:1293` filters the dispatch set to `needed` only, and nothing transitions `failed` back |
| `KI-ACD-20260907-1555` | no field binds a module or symbol name, so whichever agent needs one first invents it |

Both carry a fix direction. Both name `build-feature.js` / the `Agent Contracts` block as the
place the fix belongs, and both were verified against code or a ticket rather than recalled.

### The part worth reading

A red baseline cannot distinguish **"not implemented yet"** from **"named something the coder
will never create"** — `ImportError` is a legitimate red state for both. The mechanism this
pipeline relies on to prove that tests constrain the implementation is, in exactly this case,
proof of nothing.

### Register hygiene

`KI-KM-20260826-id-convention-diverged-across-registers` re-measured: **eleven confirmed exact**
after thirteen days, two converted here, **nine remain** and are named in the entry. The
matching grep must be the prescription (`section using the next free number`), not the phrase —
a converted register quotes the old wording in the rationale arguing against it.
