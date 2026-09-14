---
title: "KI-TQ-010 — Nothing in the build pipeline asks whether a passing test is able to fail, and for a negative control that is the only question that matters"
description: "KI-TQ-010 — Nothing in the build pipeline asks whether a passing test is able to fail, and for a negative control that is the only question that matters"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
---

# KI-TQ-010 — Nothing in the build pipeline asks whether a passing test is able to fail, and for a negative control that is the only question that matters

> One known issue, split out of `docs/known-issues/testing-quality.md` on
> 2026-09-14. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 2
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-31
- **Where:** `templates/agents/test-writer.md` (red-baseline protocol);
  `templates/agents/test-runner.md`; `templates/workflows-js/build-feature.js` `phaseOrder`;
  `CLAUDE.md` → "TDD Order — test-writer Must Precede python-coder"
- **2026-08-31: a second occurrence, in a different shape and with a shipped consequence** —
  see the end of this entry. Four green tests, an AC marked `done`, and the behaviour never
  worked; found only when the unfixed code broke a live 27-ticket build.

**Symptom.** The pipeline's only evidence that a test constrains anything is the **red baseline**:
the suite must fail before the coder runs. That check is structurally unavailable to a whole class
of test, and for that class nothing replaces it — a test that can never fail passes every phase,
every gate, and CI.

**The class.** A *negative control* asserts an **absence**: that some new input changes no
outcome. If the implementation is correct, the test is **green on arrival by construction**. There
is no red phase to capture. `CLAUDE.md`'s rule that a green `test-writer` phase is a TDD-order
violation inverts here — green is the expected pass — so the one mechanism that would have asked
"can this fail?" is not merely absent, it is documented to mean the opposite.

**Evidence.** `BP-1100g-3-i` (merged 2026-08-26, `8f55fd25`), four tests asserting that the
`# angle:` proof-kind tag feeds no pass, done, or eligibility decision. `test-writer` reported
all four green; `test-runner` re-ran and confirmed; `python-coder` signed off a correct no-op.
All three were accurate and none had reason to ask the next question.

A mutation proof run afterwards injected the exact leak the AC forbids — plumb `angles` through
`_scan_single_test_file`, then treat angle-carrying records as passing in `_classify_outcomes` —
and one of the four did not notice:

| test | angle | consumption leak | + plumbing leak | deployed leak |
|---|---|---|---|---|
| 1 | `criterion` | RED | RED | — |
| 2 | `seam` | green | RED | — |
| 3 | `real_artifact` | green | **GREEN** | — |
| 4 | `reachability` | green *(correct — deployed path)* | green *(correct)* | RED |

Test 3 carried **AC-5, the AC's headline clause** (*"removing every kind tag from the suite
changes no run outcome and no completion decision anywhere"*). Its only *failing* fixture test
carried no angle tag, and the likeliest real leak — "an angle-tagged test proves what it claims,
so count it passing" — is observable **only** on a test that is both tagged and failing. The
whole-suite strip test could not observe the leak it existed to forbid. Fixed in-flight by tagging
that fixture; the point of recording it is that nothing in the pipeline would have found it.

**Why the usual defences do not cover this.** The test had every mark of quality: real on-disk
fixtures, `yaml.safe_dump` rather than hand-typed YAML, the real production entry point, and
explicit anti-vacuity assertions (*"otherwise the equality assertion above is vacuous"*, *"otherwise
this test proves nothing"*). Those assertions guard against the fixture being empty or trivial.
**None of them can detect that the fixture, while non-trivial, does not span the failure mode.**
Self-certified non-vacuity is not falsifiability.

**Why high.** The repository's founding concern is work marked done that never runs. A negative
control that cannot fail is that defect *inside the instrument built to detect it*, and it is
self-concealing in the worst way: it is green, it stays green, and its greenness is later cited
as proof the invariant holds. `BP-1100g-4` will shortly consume this same axis in a commit-time
refusal, so the invariant `g-3-i` asserts is about to become load-bearing for merges.

**Fix direction.** Do not try to detect the class automatically from the AC text — `n_location_rule:
0`, an absence-shaped Then clause, and the word "negative control" in the notes are all
suggestive and none is reliable. Instead:

1. **Make the obligation explicit at the contract layer.** Where a red baseline is structurally
   unavailable, require a **mutation proof** in its place: name the mutation, show the test red
   under it, show it green after revert. That is the same evidence a red baseline provides —
   *this test discriminates* — obtained the only way available for an absence.
2. **Have `test-writer` say which it captured**, red baseline or mutation proof, and treat "green
   on arrival, no mutation proof" as an incomplete phase rather than a pass. It already records
   `red_baseline_verified: false` for these; that field currently means "correctly not applicable"
   and should mean "and here is what replaced it".
3. **Prefer per-mutation results over a single pass/fail.** The table above is what located the
   defect — three tests caught the leak and the aggregate looked fine. A mutation proof reported
   as one boolean would have said "the suite catches it" and test 3 would still be inert today.

**2026-08-31 — second occurrence: a fixture made vacuous by the very gate the code was supposed
to stop relying on. `TKT-600a-1` was marked `done` on a test that would pass on entirely
unfixed code.**

`TKT-600a-1` says *"files_touched contains only real edit-surface paths … and NOT illustrative
file paths that merely appear inside prose it_requirements bullets"*. It carries four tagged
tests. All four pass. It is `work_status: done`. The behaviour was never implemented.

The mechanism is worth stating precisely, because it is not the usual "the test asserts the
wrong thing" — the test asserts exactly the right thing, on inputs that cannot exercise it:

```
the test's own fixture — src/foo.py, deploy/foo.py (do not exist on disk)
   _build_files_touched(...)  ->  []                                    PASSES

the same narrative shape, naming paths that DO exist
   -> ['docs/acceptance-criteria', 'docs/retrospectives', 'templates/skills']

a real file mentioned only in order to say DO NOT edit it
   "Do not edit templates/skills/security-scanner/SKILL.md here; it is context only."
   -> ['templates/skills/security-scanner/SKILL.md']
```

`_build_files_touched` still harvests every slash-bearing token from prose. What removes the
fixture's paths is the **on-disk existence gate** — not the fix. The test therefore passes
identically before and after the change it was written to prove, which is this entry's question
("can this test fail?") answered *no*, arrived at by a route the red-baseline protocol cannot
see: the test was green on arrival because its inputs were unreachable, not because the
assertion was weak.

The third line is the sharpest consequence. An `it_requirement` whose entire purpose is to say
*"this file is context, do not edit it"* makes that file the ticket's declared edit surface.

**The consequence was not hypothetical.** The unfixed extractor produced the surfaces for
`EPIC-SuppressionNarrowsNeverDisables`: 10 of 27 tickets unusable, three carrying nothing but
bare directories, and two pointed at `docs/known-issues/commit-guardian.md` — a live document —
as the file to modify. The build was stopped mid-drive. Five days and one "done" AC after the
test was written, the first thing to actually detect the defect was a production run.

**What this adds to the fix direction above.** The three prescriptions there are about negative
controls with no red phase. This case adds a fourth, for tests that DO have a red phase on
paper: **a fixture must be capable of reaching the code under test.** A path-filtering test
whose fixture paths do not exist is filtered by the existence gate before the filter under test
ever runs. The cheap general form is the mutation proof this entry already recommends — reverting
the fix must turn the test red, and here it would not have.

**Related.** `KI-ACD-023` (the `files_touched` defect this test was supposed to prevent, now at
two occurrences). `KI-ACS-004` (`TKT-600a-1` is already cited there for a *different* failure —
`done` with an empty `implemented_by` — so the same record has now produced two distinct
done-quality defects).

**Related.** `KI-TQ-009` (a test-local oracle reproducing the production bug — same family: the
test agrees with the code instead of constraining it). `KI-TQ-005` (fixtures that never built the
collection they assert over).

**Pattern:** a quality bar enforced by one mechanism, applied to the class of work that mechanism
cannot see, where the absence of the check is documented as correct.

---
