---
title: "JS/TypeScript tests count as proof-of-done (BO-2500e) + mock-mode hardening (UXP-607–610)"
date: "2026-08-13"
time: "11:50"
type: feature
components: 
  - ac_store
  - commit_guardian
  - testing_quality
  - infrastructure
  - frontend_coding
  - ux_prototyping
summary: "Teaches the proof-of-done oracle to recognise vitest tests as valid done-proof, so JavaScript/TypeScript acceptance criteria can be mechanically proven like Python ones, and hardens Atlas mock mode with a production default-deny, a truthful mock/live badge, a fail-loud drift guard, and CI-only routes that are absent in production."
description: "Two related changes. (1) BO-2500e — the done-proof oracle in scripts/ac_store/done_proof.py now discovers '// covers: <AC-id>' tags in .ts/.tsx test files in addition to '# covers:' in Python, via a single shared COVERS_TAG_RE seam moved into scripts/ac_store/test_enforcement.py and reused by templates/scripts/commit_guardian/check_done_proof.py. A new run_vitest_and_parse() seam invokes vitest scoped to the linked test files and maps each to PASSED/FAILED; a new JsRunnerUnavailable exception makes an uninvokable runner fail CLOSED rather than silently pass or skip. Eligibility is the logical AND across both languages, and the Python path is untouched when an AC has no linked .ts test. node_modules/, .next/ and dist/ are excluded from scanning. test_enforcement.py was added to the build_ac_store deploy_map because done_proof.py now imports it at module level. The CI done-proof job installs Node and leafcutter-web dependencies and runs with --test-root . so one gate sees both Python and JS proofs. (2) UXP-607–610 — mock-mode resolution now follows lock > production-default-deny > runtime override > env default: a production deployment ignores an anonymous visitor's ?mock override unless LEAFCUTTER_MOCK_ALLOW_OVERRIDE=1 is set, while dev and preview keep honouring overrides with no configuration. Production detection is a single server-side isProductionRuntime() in the new leafcutter-web/lib/data/runtime.ts, shared by the default-deny gate and by the CI-only /api/drift-guard and /api/mock-toggle-check routes, which return a bodyless 404 in production before importing any loader. The sidebar badge now calls isMockActive() instead of the build-time NEXT_PUBLIC_LEAFCUTTER_MOCK constant, so badge and data layer can never disagree; active-link highlighting moved to a client component so the shell could become a Server Component. The drift guard now asserts mock mode is active and that fixtures returned a non-zero record count before evaluating, so 'no drift' can never be a vacuous pass. 36 acceptance criteria were reconciled to work_status: done, each gated on a genuinely passing test with covered_by populated."
breaking: false
---

## Entry
