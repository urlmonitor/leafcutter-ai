---
title: "UXP-700a-3 and UXP-700a-4 finished by hand from a halted /build-feature run"
date: "2026-09-16"
time: "21:15"
type: manual
components:
  - ux_prototyping
  - build_pipeline
summary: "Completes two tickets left uncommitted by the interrupted /build-feature run wf_3d2879c1-2ae: a freshly installed project's product-truth record now carries none of the tooling's own example content by default, but the example product ('fern-and-fig') remains obtainable by asking for it by name (UXP-700a-3); and the build now proves a from-scratch product-truth record works — by installing one into a throwaway project and running its real checker against it, with the required-file set and count derived from what the checker actually reads rather than a hand-restated list (UXP-700a-4)."
description: "Run wf_3d2879c1-2ae drove EPIC-TruthfulProjectRecord and halted with tickets 07 (UXP-700a-3) and 08 (UXP-700a-4) staged but uncommitted. UXP-700a-3's AC-1/AC-2 (zero artifacts of every type by default, none of the tooling's own example or project-record content) already held via build_product_truth()'s existing write-if-absent empty scaffold; the actual gap was AC-3 (the example product must remain obtainable by name) — closed by a new scripts/seed_example_product.py, missing-only semantics, wired as an opt-in --seed-example-product NAME flag on scripts/build.py mirroring the shipped --seed-docs precedent. UXP-700a-4 replaced build_phases_product_truth.py's hand-restated _PRODUCT_TRUTH_REQUIRED_FILES tuple (six hand-named files, bare on-disk presence check, never ran the checker) with a new sibling module, scripts/build_phases_product_truth_smoke.py: every build now scaffolds a wholly empty product-truth record into its own throwaway tempdir and runs the real, just-deployed checker against it, with the checker's own declared I/O boundary instrumented to record every distinct file it reads — deriving both the required-file set and its stated count from what the checker actually needed, so a new checker start-up input extends the requirement with no second edit. Both tickets' work (implementation, tests, and — for UXP-700a-4 — a previously blocked documentation-coverage gate) were already complete in the halted run's saved patches; this entry records the hand takeover that verified, re-tested, and closed them rather than new production work. The documentation-verifier blocker recorded on UXP-700a-4 (its Agent Contract's AC-1 doc target pointed at BP-900a-1.yaml, an unrelated AC for a different guard, listed elsewhere in the same contract as context-only prior art) was confirmed as a mis-scoped contract, not a real doc gap — the target was already corrected in the halted run's own patch to point at build_phases_product_truth_smoke.py's own module docstring, which was verified to genuinely document AC-1/AC-2/AC-3/AC-4. The same mis-scoping pattern was found and recorded (not corrected, since documentation-expert has not yet run) on UXP-700a-3's Agent Contract, which points its own AC-1 doc target at ADR-022, also listed as context-only."
commits:
breaking: false
---

## Entry

Two tickets from the halted `/build-feature` epic run `wf_3d2879c1-2ae`
(EPIC-TruthfulProjectRecord) were finished by hand at the user's direction on
2026-09-16, on branch `feature/uxp-700a-3-a-4` off `origin/main`.

**UXP-700a-3 — a newly installed record carries none of another project's
content.** A fresh install's product-truth record already held zero
artifacts of every type and none of the tooling's own example or
project-record content by default (via the existing `build_product_truth()`
scaffold — no change needed there). The real gap was that the example
product ("fern-and-fig") had no way to be obtained at all: `scripts/
seed_example_product.py` closes it with a missing-only `seed_example_product()`
that copies the package's own `docs/product-truth/{flows,mock-data,mockups}/
<product>/` tree into a target project only when asked for by name, wired as
an opt-in `--seed-example-product NAME` flag on `scripts/build.py`
(`build_main_helpers.py`), exactly mirroring the shipped `--seed-docs`
precedent. Requesting an unknown product raises `ValueError` rather than
silently no-op'ing.

**UXP-700a-4 — the build proves a from-scratch record works before it ships
one.** `build_phases_product_truth.py`'s prior guard only checked six
hand-named files for bare on-disk presence and never actually ran the
checker — a deployed record could crash on its first real run and the build
would still exit green. The new `scripts/build_phases_product_truth_smoke.py`
scaffolds a wholly empty product-truth record into its own throwaway tempdir
every build and runs the real, just-deployed `validate_product_truth.py`
against it, with that checker's own declared I/O boundary instrumented to
record every distinct file it reads. Because the scratch record is wholly
empty, every file the checker opens is by construction one of its fixed
start-up inputs — so the recorded set both derives the required-file list
and its length is the count the build states, and a missing start-up input
now surfaces through the same by-name `record_deploy_failure` report every
other declared-deploy gap already uses.

Both tickets' implementation and tests were already complete in the halted
run's saved patches (`staged.patch` / `unstaged.patch`); this entry records a
hand takeover that re-applied only these two tickets' files, rebuilt, and
independently re-verified the work rather than trusting the prior run's own
sign-offs: read both ACs against the applied code, ran the full
`unit_tests/product_truth/` and `unit_tests/build_guards/` suites against a
disposable pristine `origin/main` baseline (no new failures — every
remaining failure is a pre-existing Windows-environment gap present on
`origin/main` too), and mutation-tested each AC's core behaviour (both went
red under a targeted no-op mutation and green again once restored).

UXP-700a-4 also carried a recorded `documentation-verifier` blocker: its
Agent Contract named `docs/acceptance-criteria/build_pipeline/BP-900-deployment-
completeness/BP-900a-1.yaml` — an unrelated AC for a different guard (`ac_store`
deploy completeness), already listed in the same contract as `relationship:
context` prior art — as the doc target to change. This was a mis-scoped
contract, not a real doc gap: the halted run's own patch had already
corrected the target to `scripts/build_phases_product_truth_smoke.py`, whose
module docstring was independently verified here to genuinely document what
AC-1 through AC-4 require. The same mis-scoping shape was found (and
recorded, not corrected) on UXP-700a-3's own Agent Contract, which points its
AC-1 doc target at ADR-022 — also listed as context-only in the same block;
`documentation-expert` has not yet run on that ticket.
