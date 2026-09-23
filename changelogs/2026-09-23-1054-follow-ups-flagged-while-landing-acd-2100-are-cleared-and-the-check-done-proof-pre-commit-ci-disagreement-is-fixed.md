---
title: "Follow-ups flagged while landing ACD-2100 are cleared, and the check-done-proof pre-commit/CI disagreement is fixed"
date: "2026-09-23"
time: "10:54"
type: manual
components: 
  - ac_driven_dev
  - ac_store
  - build_orchestration
  - build_pipeline
  - commit_guardian
  - knowledge_management
  - testing_quality
  - documentation_system
summary: "Cleared six follow-up items deferred while landing the ACD-2100 epic (a type-checking cleanup, a dead-code removal, retrospective conventions, known-issue paperwork, and a documentation split), and fixed a bug that let the pre-commit hook and the required CI gate disagree about which acceptance criteria still need a test, which had been keeping main's required test gate red."
description: "Two commits on chore/flagged-followups. 3778f8a7 clears six independent follow-ups from PRs #864/#865: mypy annotated to zero errors across six test files (no suppressions, no weakened tests); dead code classifyWorkspaceSetupPermission removed from templates/workflows-js/plan-feature.js (-112 lines, filed as ACD-2100b-5-i with a new 3-test file); two retrospective conventions added to CLAUDE.md (KI-2, KI-3); four known-issues entries filed and a 34-file resolved/-index backlink depth fix; and docs/build-drift-hook.md's Direction B section extracted verbatim into docs/2b_direction_b_output_drift_detection.md. A second change fixes the most significant item: check-done-proof's pre-commit path carried its own inline `test_required is False` short-circuit above the shared is_covers_tag_waived() call, making that predicate dead code for the records it governs and leaving the pre-commit hook and the required CI gate disagreeing -- introduced when BO-2500a-1-ii (PR #861) hardened the two CI paths to require test_required:false AND a non-blank test_rationale but left this copy behind, which had put main's required pytest gate red. The duplicate short-circuit is removed so the single shared predicate governs all three paths."
pr: 873
commits: 
  - 3778f8a7
breaking: false
---

## Entry

Branch `chore/flagged-followups`, PR #873. Clears six follow-ups flagged while
landing the ACD-2100 epic (PRs #864, #865), plus one defect found while doing
so.

**1. mypy.** The informational CI job that failed on #864 went from 7 errors
to 0 across six test files. Every fix is an annotation, not a suppression: no
new `# type: ignore`, and no test deleted, renamed, skipped, or weakened. Two
annotations deliberately use the bare `list` / `list[dict]` rather than the
precise parameterised forms — each precise form needed an extra import line,
and both files are already over the `check-file-size` ratchet, which refuses
further growth. The element types are documented in the docstring instead.

**2. Dead code removed.** `classifyWorkspaceSetupPermission` in
`templates/workflows-js/plan-feature.js` (-112 lines) was orphaned when
`ACD-2100b-5` moved the permission check into the
`check_workspace_setup_permission.py` pre-flight. Recorded as new AC
`ACD-2100b-5-i` and covered by a new test file,
`unit_tests/workflows/test_acd_2100b_5_i.py` (3 tests: one asserts the removed
symbol is absent, two drive the real pre-flight subprocess through the
surviving granted/denied paths).

**3. CLAUDE.md.** Two conventions from the ACD-2100 retrospective: KI-2 —
guard-tool *failures* need the same working-directory / deployment-freshness
scepticism the file already prescribes for clean results; KI-3 — ticket-
authored sequential resource paths (diagram ids, etc.) must be re-verified at
execution time on long-lived branches, not trusted from authoring time.

**4. Known-issues registers.** Four entries filed
(`KI-BO-20260907-0803`, `KI-BO-20260907-0804`,
`KI-ACS-20260923-doc-links-status-not-reconciled`,
`KI-ACD-20260923-provenance-producer-unverified`), and 34 per-issue files
under `<component>/resolved/` had a broken index backlink corrected
(`../` → `../../`).

**5. `docs/build-drift-hook.md`.** Its Direction B section was extracted
verbatim into `docs/2b_direction_b_output_drift_detection.md`, cross-linked
both ways. The parent drops from 524 to 388 lines.

**6. A main-breaking defect fixed.** `check-done-proof`'s
pre-commit path carried its own inline `test_required is False` short-circuit
placed ABOVE the shared `is_covers_tag_waived()` call, making that predicate
dead code for exactly the records it governs. `BO-2500a-1-ii` (PR #861)
hardened the two CI paths to require the conjunction of `test_required:
false` AND a non-blank `test_rationale`, but left this copy behind — so the
pre-commit hook and the required CI gate disagreed, and `main` went red on
the required pytest gate. The duplicate is removed; the single shared
predicate now governs all three paths
(`templates/scripts/commit_guardian/check_done_proof.py`).

Verified (commit 3778f8a7): `unit_tests/workflows` + `unit_tests/ac_driven_dev`
gave 815 passed before the new test file was added (matching the pre-change
count, so neither the removal nor the annotations cost a test) and 818 with
it; mypy clean under CI's own invocation; ruff clean on `scripts` and
`unit_tests`; AC store valid, 493 files in `ac-driven-dev`.
