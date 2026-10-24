---
title: "The wrong-version gate will test the same wrong version every run (specified, approved and scaffolded)"
date: "2026-10-24"
time: "11:00"
type: manual
components:
  - testing_quality
  - build_orchestration
summary: "Specifies how the wrong-version gate stops testing a different guess on every run: a prepared and validated wrong version is pinned and reused, re-checked against the current code each run, and re-prepared only when needed. Includes the measured analysis behind it, nine new acceptance criteria (eight approved), and the epic that builds them. No code changes."
description: "Analysis docs/analysis/2026-10-23-the-wrong-version-gate-tests-a-different-guess-each-run.md, measured from four live /build-feature drives on 2026-10-23: the test-breaker turns each must_catch name into code afresh every run; on one ticket 6 of 13 preparable names got behaviourally different code across three rounds, so a test proven to catch a name in one round was judged a survivor against a different guess in the next and the gate could not converge (gate steps 0.3-0.6M tokens per round, ~3.5M per drive). The writer deleted each earlier manifest, so nothing was reused. New ACs: TQ-500g-1-xi (pin validated {path, old, new} replacements per work key), -xii (re-prepare only when the name is new, its old text no longer matches, or its wording changed), -xiii (re-validate every pin each run before anything runs), -xiv (effect check: a test that runs none of the changed lines reads not_executed, unfinished, never a survivor), -xv (every verdict row names the alteration and its source; earlier manifests kept), -xvi (operator reset), -xvii (an AC may declare a replacement; declared > pinned > prepared), TQ-500f-2-iii (test designer names the code-side wrong version, not a test defect); all eight approved by BrainCandy 2026-10-24 with four recorded decisions (pins under the workspace git directory; a failed pin write fails the gate; the load check executes the module; import-time lines count for every test). TQ-500g-1-xviii (llm-expert: /build-epic's prompt-side reader and to_prepare dispatch) authored, readiness draft. Siblings reconciled without changing their status: TQ-500g-1-i (not_executed), -ix (history instead of deletion), -v/-vi/-vii (dispatch only to_prepare; criteria wording amended), TQ-500g-5 (reference page additions). Epic EPIC-OnceANamedWrongVersionIsPreparedAnd generated from the eight approved ACs (8 tickets)."
commits: []
breaking: false
---

## Entry
