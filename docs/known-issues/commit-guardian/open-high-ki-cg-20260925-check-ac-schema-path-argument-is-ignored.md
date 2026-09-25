---
title: "KI-CG-20260925-check-ac-schema-path-argument-is-ignored — prompts run 'check_ac_schema.py <path>' to validate a record, but the hook ignores argv and checks only the staged set, so those checks are vacuous passes"
description: "high — ac-fulfillment-gate step 3d and ticket-wiring's draft check pass a path; main() reads the index, finds nothing staged, and exits 0. 'pre-commit run check-ac-schema --all-files' is equally vacuous (pass_filenames: false)."
type: reference
category: reference
status: active
created: '2026-09-25'
last_updated: '2026-09-25'
components:
  - commit_guardian
  - ac_store
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/commit-guardian/open-high-ki-cg-012-check-ac-schema-reports-a-clean-pass-on.md
  - docs/known-issues/ac-store/open-high-ki-acs-20260907-the-validator-everyone-runs-is-weaker-than-the-gate-that-blocks.md
  - docs/analysis/2026-09-25-duplication-clusters-that-produce-known-issues.md
---

# KI-CG-20260925-check-ac-schema-path-argument-is-ignored — prompts run 'check_ac_schema.py <path>' to validate a record, but the hook ignores argv and checks only the staged set, so those checks are vacuous passes

- **Severity:** high. Agent-side validation steps that look like real checks inspect zero files.
- **Status:** open — no AC. `main()` read 2026-09-25.
- **Where:** `templates/scripts/commit_guardian/check_ac_schema.py:662-686`; callers `templates/agents/ac-fulfillment-gate.md:270`, `templates/skills/ticket-wiring/SKILL.md:261-264`; `docs/how-to/ac-traceability-store.md:224,655` (`--all-files`).

## Mechanism

`main()` derives its file list from `git diff --cached` (or `HOOK_TEST_FILES`); positional arguments are not read.
With nothing staged, Phase 1 validates an empty set and exits 0 — the KI-CG-012 "clean pass on empty" behaviour.
The hook is registered `pass_filenames: false`, so `pre-commit run --all-files` hands it nothing either. CI works
only because `ac-store-valid` stages the whole store first.

## Why prompts do this

Three validators are named across prompts and docs: `validate_ac_schema.py` (CLAUDE.md, plan-feature, quick-fix,
four how-tos), `check_ac_schema.py <path>` (the two sites above) and `validate_ac.py` (`it-po.md:359`, see
KI-ACS-20260925-validate-ac-bare-directory-exits-0). The standalone and hook validators enforce disjoint rule sets
(KI-ACS-20260907). Authors reached for the hook because it is the stricter one.

## Fix direction

One `validate_record(rec, ctx)` in `_ac_schema_validators`, called by the hook (staged set) and a CLI (explicit
paths/directories) — only the scope differs. Until then, make `check_ac_schema.py` either honour explicit paths or
exit non-zero when given arguments it will not read. Cluster 9 of the 2026-09-25 duplication analysis.
