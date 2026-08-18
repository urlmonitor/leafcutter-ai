---
title: "fix(ac-driven-dev): the AC fulfillment gate can no longer pass having verified nothing"
date: "2026-08-18"
time: "13:20"
type: manual
components:
  - ac_driven_dev
  - build_orchestration
summary: "The pre-commit AC fulfillment gate returned ok on every generator-produced ticket because it read a traceability shape the generator never emits, making its pass condition vacuously true over an empty AC list. Adds a shared coverage resolver that accepts both shapes and makes an ok verdict impossible without at least one AC actually verified."
description: "ACD-1900b-5-i. The ac-fulfillment-gate runs at priority 11.7, immediately before commit, and is the mechanical check that an AC's work_status, implemented_by and covered_by are accurate. Its Step 1 extracted an l2 list, an l3 list and an ac_path from the ticket's ac_traceability block; the ticket generator emits a two-key form instead (id plus the store path). On every generated ticket the resulting working list was empty, and Step 5's rule -- ok when every AC in the working list is passed or skipped -- is vacuously true over an empty list. The gate signed off green having verified nothing, in the pre-commit path of every AC-generated ticket. Adds scripts/ac_store/ac_coverage_resolver.py, an importable and side-effect-free resolver exposing resolve_coverage, verify_ticket_coverage and compute_verdict, and rewires Steps 1 and 5 of the gate template to call it. Both traceability shapes now resolve: the two-key form is authoritative when interpretable, the list form is preserved unchanged, and source_ac is an ordered fallback that never silently rescues an unrecognised block -- the verdict still names the keys it found, so the next shape drift is visible rather than invisible. An ok verdict now structurally requires at least one resolved AC. ADR-026 rule 5's deliberate silent-skip for tickets with NO traceability block is preserved verbatim; only the present-but-unresolvable case became blocking. The producer is deliberately unchanged, because the two-key form is already on disk in tickets that have reached 99_done. Registers the new module in build_ac_store's deploy_map so the deployed hook layout carries it, and corrects a false claim in the generator's _build_frontmatter docstring that ac-validator reads ac_traceability -- it does not; the gate is the sole consumer. Proven by five behavioral tests that invoke the generator to produce a real ticket and then execute resolution, asserting the verified-AC count (1 for a two-key ticket, 0 for an uninterpretable block, 3 for a three-entry list-form block) rather than only the verdict string; a grep over either file could not have distinguished the fixed gate from the broken one. A post-review pass closed the same defect class one level down inside the new module: all() over the per-AC results is also vacuously true when that list is shorter than the resolved list, so three resolved ACs with zero results returned ok with a verified count of three. Guarded, with verified_count now reporting what was actually checked. Also reconciles the AC store: ACD-1900b-5-i carried work_status done with an empty covered_by despite five passing covers-tagged tests, and BO-201 gains its first executing coverage via the list-form regression test, as its own it_requirements required."
pr: null
commits:
  - 84549ddba
  - 1702b9409
  - 8680db04c
---

## Entry

A gate built to catch unevidenced "done" was itself signing off on nothing.

`ac-fulfillment-gate` sits at priority 11.7, one step before commit, and its job
is to confirm that an AC's `work_status`, `implemented_by` and `covered_by` are
accurate before the work lands. It looked for `l2`, `l3` and `ac_path` in the
ticket's traceability block. The generator writes `id` and `path`. So on every
generated ticket the list of ACs to check came out empty — and "every AC in the
list passed" is trivially true of an empty list.

The producer and the consumer had disagreed since the generator gained the
block, and nothing noticed, because the gate's own spec AC (`BO-201`) was
covered only by a `read_text()` + regex suite over the template. A grep-shaped
test cannot tell a wired gate from an ignored one.

The fix accepts both shapes rather than picking a winner — the two-key form is
already on disk in tickets that have reached `99_done`, so changing the writer
would retroactively invalidate them — and makes `ok` conditional on having
resolved at least one AC. The absent-block silent-skip that ADR-026 rule 5
deliberately retains is untouched.

The tests assert the *count* of ACs verified, not the verdict, because a verdict
can be made to pass for unrelated reasons. An implementation still reading only
the list form returns zero on a generated ticket and fails.

One postscript worth recording: review found the new module reproducing the same
vacuous-truth shape internally — `all()` over a per-AC result list shorter than
the resolved list. Unreachable through today's only caller, but this module is
the seed for a shared resolver that will gain more. A module whose whole purpose
is to make vacuous truth structurally impossible should not rely on its callers
being careful.
</content>
