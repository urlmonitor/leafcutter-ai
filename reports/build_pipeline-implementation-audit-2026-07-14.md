# build_pipeline — AC Implementation Audit (2026-07-14)

Evidence-based audit of every leaf AC under `docs/acceptance-criteria/build_pipeline/`
(prefixes `BP-*` and `FIN-*`), run via the `ac-audit` skill: mechanical evidence map →
green-test ground truth → 7 skeptical per-group verify agents → this synthesis.

**Definition of "done" used throughout:** an AC is `FULLY_IMPLEMENTED` only when real code
satisfies the criterion **and** a genuine, green unit test asserts it. Store fields
(`work_status`, `implemented_by`, `covered_by`) were read only as claims to be verified —
never as evidence.

## Executive summary

459 AC records → **355 leaf ACs** audited (L0/L1 composites roll up from children).

| Verdict | First-pass (grep) | **Verified (agents)** |
|---|---|---|
| FULLY_IMPLEMENTED | 21 | **80** |
| CODE_NO_TEST | 25 | **91** |
| TEST_NO_CODE | 15 | **1** |
| NOT_IMPLEMENTED | 294 | **183** |

The mechanical first pass massively under-counted implementation: it keys on the AC-id
string appearing in code/tests, and most build_pipeline work lives in **prompt templates,
config JSON, docs, and `*.js` workflows that never embed the AC id**. Deep verification
moved 111 ACs out of NOT_IMPLEMENTED. Net real state:

- **~48% has code** (80 fully tested + 91 code-without-test = 171 / 355).
- **Test coverage is the dominant gap:** 91 ACs have working code but no asserting test —
  concentrated in prose/config surfaces (BP-200 llm-expert, BP-600 quick-fix, BP-700
  frontend-coder, FIN-100 finalize logic).
- **183 ACs are genuinely greenfield** — whole unbuilt epics: BP-300 (workflow
  orchestration), BP-800 (adaptive specialists), BP-1000 (source↔shipped parity gate),
  FIN-200 (changelog-on-finalize), plus the BP-100e/f/g and BP-900e/g clusters.

## Green-test ground truth

Ran the 19 cited suites: **315 passed / 2 failed / 3 skipped**.
- `test_build_tracked_source_guard.py::…test_ac_bp900c3…` → **RED** (BP-900c-3, see phantom
  section). Note: this red only surfaced because the covering AC happens to be reachable;
  see the xfail-masking hazard below.
- `test_generate_ticket_from_ac.py::…test_bo510_2…` → RED (`sql-view-creator.md` missing
  `produces:`) — a BO-510 assertion, out of build_pipeline scope but means that suite is
  not fully green.

## ⚠ Phantom-done & opposite-behaviour risk

The highest-value, most-misleading findings — where the store/tests imply "done" but the
behaviour is wrong, masked, or reversed:

1. **Systemic xfail-masking (HIGH, systemic).** `scripts/ac_store/pytest_ac_enforcement.py`
   (wired via `pytest.ini`) **downgrades a genuinely-failing test to XFAIL whenever the
   covered AC's `work_status != "done"`.** A green suite therefore silently hides red tests.
   PASSED results remain trustworthy (the plugin only rewrites failures), but any not-yet-done
   AC's tagged test can be red without the suite going red. This mechanism actively
   manufactures phantom-green.
2. **BP-900c-3 — broken + xfail-masked RED.** `_suggest_action` has the correct
   `ACTION_COMMIT_UNDER_TEMPLATES` branch, but its allowlist check returns
   `ACTION_ADD_TO_ALLOWLIST` for `scripts/feedback/submit_feedback.py` — the exact scenario
   the AC targets. The genuine test is xfail-masked RED; only the non-allowlisted variant is
   green.
3. **BP-1300a-1 / -1-i / -1-ii — opposite behaviour.** The "unmaskable guardrail" AC requires
   skill_id resolution against the **canonical source**, but `build_phases.py:1867`
   (`in_project = (target_root/.claude/skills / skill_id).exists()`) resolves against the
   **deployed** tree — the exact thing the AC forbids. A stale deploy would mask a dangling
   pointer. The cited green test covers a different feature (`descriptive_only`).
4. **BP-100i-3 — opposite behaviour.** `check_hook_parity` intentionally downgraded
   missing-deployed-script findings to non-blocking INFO (decision-history M-3), and its test
   asserts `violations == []` — both contradict the AC's required "commit blocked, exit 1".
5. **FIN-100e-1 — opposite behaviour.** Auto-ticketing was deliberately disabled
   (EPIC-FinalizeFeatureHardening); `test_finalize_feature_step6a.py` locks in the *disabled*
   behaviour, i.e. code + test assert the opposite of the AC.
6. **BP-1200b-1 — non-blocking gate.** The CI `test` job carries `continue-on-error: true`,
   so the "CI test gate blocks merge" AC is not satisfied — the job is informational.
7. **BP-900g-1 — TEST_NO_CODE.** The green test asserts the *workaround* (command templates
   switched to name-based `Workflow("build-feature")`), not the build.py command-reference
   reachability guard the AC specifies — that guard does not exist.

## Per-group rollup

| Group | Fully | Code-no-test | Test-no-code | Not-impl | Total | State |
|---|---:|---:|---:|---:|---:|---|
| BP-006 | 9 | 0 | 0 | 0 | 9 | Done + tested |
| BP-100 (reliable-builds) | 32 | 7 | 0 | 23 | 62 | a/b/c/d/i/m built; e/f/g greenfield |
| BP-200 (llm-expert-agent) | 0 | 27 | 0 | 0 | 27 | Fully built, zero tests |
| BP-300 (workflow-orchestration) | 0 | 0 | 0 | 23 | 23 | Greenfield |
| BP-400 (drive-observability) | 5 | 1 | 0 | 9 | 15 | Only BP-400c (feedback-report) built |
| BP-600 (quick-fix-workflow) | 0 | 21 | 0 | 4 | 25 | Fully coded, zero tests |
| BP-700 (unified-frontend) | 3 | 19 | 0 | 0 | 22 | Shipped; mostly untested |
| BP-800 (adaptive-specialists) | 0 | 0 | 0 | 37 | 37 | Greenfield |
| BP-811 / BP-812 / BP-901 | 3 | 0 | 0 | 0 | 3 | Done + tested |
| BP-900 (deployment-completeness) | 10 | 2 | 1 | 16 | 29 | b/c/f built; a/e/g gaps + 1 broken |
| BP-1000 (source-template-parity) | 0 | 0 | 0 | 22 | 22 | Greenfield |
| BP-1100 (phantom-done-prevention) | 11 | 0 | 0 | 12 | 23 | Only the `e` reconciliation cluster |
| BP-1200 (ci-test-gate) | 3 | 0 | 0 | 9 | 12 | Build-guard exists; blocking gate absent |
| BP-1300 (unmaskable-guardrails) | 1 | 0 | 0 | 13 | 14 | Greenfield + 1 opposite-behaviour |
| FIN-100 (pre-merge-safety-gate) | 3 | 14 | 0 | 2 | 19 | Logic coded, mostly untested |
| FIN-200 (changelog-on-finalize) | 0 | 0 | 0 | 13 | 13 | Greenfield |
| **Total** | **80** | **91** | **1** | **183** | **355** | |

## Whole greenfield epics (183 NOT_IMPLEMENTED — Wave-2 candidates)

- **BP-300** workflow-orchestration — needs `templates/workflows-js/debug.js` (only prose
  SKILL exists); build-ticket planner has no drift/sign-off reconciliation.
- **BP-800** adaptive-specialists — no technology detector, agent generator, or language
  knowledge layer.
- **BP-1000** source→shipped parity merge gate — `check_hook_parity.py` is a commit-time hook
  scoped to `commit_guardian`, not a generic mirror-pair / finalize-merge gate.
- **FIN-200** changelog-on-finalize — no changelog step, config key, field, or diagram
  anywhere in finalize.
- **BP-100e** signoff timestamps, **BP-100f** finalize git-guard, **BP-100g** SKILL-YAML
  validation — all absent.
- **BP-900a** ac_store package deploy (`__init__.py`/importability), **BP-900e** registry
  completeness, **BP-900g** command reachability — absent.
- **BP-1200b/c** blocking CI gate + branch-protection-as-code; **BP-1300b/c** canonical-source
  resolution rule + drive-context escalation.
- **BP-400a** agent-telemetry (`emit_event.py`), **BP-400b** rename-robust retrospective.

## Test-backfill gap (91 CODE_NO_TEST)

Working code, no asserting test — the store must not be flipped to `done` for these until a
green test is linked:
- **BP-200** (27) — llm-expert template/PROJECT_CONTEXT/prompt-audit skill/registry (prose/config).
- **BP-600** (21) — the entire quick-fix workflow (`quick-fix.js` + SKILL) — zero tests.
- **BP-700** (19) — frontend-coder template/docs/build-migration.
- **FIN-100** (14) — finalize safety-gate merge/triage/halt logic in `finalize-feature.js`
  (only a-4, e-3, g-1 tested).
- **BP-100** (7): b-5/b-5-i/b-6-i/b-8/b-9/b-10/c-4 (drift-hook + docs + compile passthrough).
- **BP-400c-1** (1), **BP-900c-1-1** (1).

---

## Merged per-AC verdicts

Verdicts below are the agents' verified results (they override the mechanical first pass).
Paths are repo-relative.

### BP-100 — reliable-builds (32 FULLY · 7 CODE_NO_TEST · 23 NOT_IMPL)

| AC | Verdict | Code | Test | Note |
|----|---------|------|------|------|
| BP-100a-1 | FULLY | scripts/build_precommit.py | unit_tests/commit_guardian/test_build_precommit.py | warn+continue on missing hook script |
| BP-100a-2 | FULLY | scripts/build_precommit.py | test_build_precommit.py | silent when all scripts present |
| BP-100a-4 | FULLY | scripts/build_precommit.py | test_build_precommit.py | helper asserts warning |
| BP-100a-5 | FULLY | scripts/build_precommit.py | test_build_precommit.py | helper asserts no warning |
| BP-100b-1 | FULLY | scripts/build_phases.py | test_build_workflow_output_paths.py; test_build_workflow_phase.py | JS→.claude/workflows shim |
| BP-100b-2 | FULLY | scripts/build_phases.py | test_build_workflow_phase.py | compare-before-write idempotency |
| BP-100b-3 | FULLY | scripts/build_phases.py (clean_stale_artifacts) | tests/test_build_clean.py | workflows cleaner wired |
| BP-100b-4 | FULLY | scripts/build.py (_build_source_manifests) | tests/test_build_artifact_parity.py | workflows manifest key asserted |
| BP-100b-5 | CODE_NO_TEST | templates/scripts/commit_guardian/check_output_drift.py | — | scans .claude/workflows; no drift test |
| BP-100b-5-i | CODE_NO_TEST | check_output_drift.py | — | never references .agents/workflows |
| BP-100b-6 | FULLY | build_phases.py; build.py; build_helpers.py | test_build_artifact_parity.py | 4-layer parity asserted |
| BP-100b-6-i | CODE_NO_TEST | test_build_artifact_parity.py | — | no synthetic-category test |
| BP-100b-7 | FULLY | templates/commit-guardian/commit_guardian.json | test_build_artifact_parity.py | precommit files pattern covers workflows |
| BP-100b-8 | CODE_NO_TEST | docs/build-pipeline.md | — | mermaid node present; docs untested |
| BP-100b-9 | CODE_NO_TEST | docs/explanation/consolidated-output-root.md | — | shimmed-outputs row present |
| BP-100b-10 | CODE_NO_TEST | docs/build-drift-hook.md | — | §5.4 four-layer checklist |
| BP-100b-11 | NOT_IMPL | — | — | no registry referential-integrity block |
| BP-100b-11-i | NOT_IMPL | — | — | dangling-entry block absent |
| BP-100c-1 | FULLY | build_phases.py (build_ticket_lifecycle) | tests/test_config_driven_build_paths.py | tickets_root from config parent |
| BP-100c-1-i | FULLY | build_phases.py | test_config_driven_build_paths.py | config-root scaffolding |
| BP-100c-2 | FULLY | build_phases.py | test_config_driven_build_paths.py | skip guard returns 0 |
| BP-100c-2-i | FULLY | build_phases.py | test_config_driven_build_paths.py | --force bypasses skip |
| BP-100c-3 | FULLY | scripts/injection_builders.py | test_config_driven_build_paths.py | config overlay over paths.json |
| BP-100c-3-i | FULLY | injection_builders.py | test_config_driven_build_paths.py | overlay only present keys |
| BP-100c-4 | CODE_NO_TEST | scripts/template_compiler.py; injection_builders.py | — | compile passthrough not e2e tested |
| BP-100c-5 | FULLY | build_phases.py; injection_builders.py | test_config_driven_build_paths.py | default path fallback |
| BP-100d-1 | FULLY | templates/scripts/commit_guardian/check_contract_shrinking.py | test_check_contract_shrinking.py | self-exclusion |
| BP-100d-1-i | FULLY | check_contract_shrinking.py | test_check_contract_shrinking.py | diff-scan + prod-file sanity |
| BP-100e-1..5-i | NOT_IMPL | — | — | signoff timestamp hooks absent (7 ACs) |
| BP-100f-1..3 | NOT_IMPL | — | — | finalize/changelog git-guard absent (5 ACs) |
| BP-100g-1..6 | NOT_IMPL | — | — | SKILL-YAML validation absent (7 ACs) |
| BP-100i-1 | FULLY | templates/scripts/commit_guardian/check_hook_parity.py | test_check_hook_parity.py | runtime-vs-canonical parity |
| BP-100i-1-i | FULLY | check_hook_parity.py | test_check_hook_parity.py | excluded_scripts honored |
| BP-100i-1-ii | FULLY | check_hook_parity.py | test_check_hook_parity.py | pattern-only comparison |
| BP-100i-2 | FULLY | check_hook_parity.py | test_check_hook_parity.py | legacy-vs-canonical manifest IDs |
| BP-100i-2-i | FULLY | check_hook_parity.py | test_check_hook_parity.py | disabled hooks still require parity |
| BP-100i-3 | NOT_IMPL (opposite) | check_hook_parity.py | test_check_hook_parity.py | missing-deployed downgraded to non-blocking |
| BP-100i-3-i | FULLY | check_hook_parity.py | test_check_hook_parity.py | deployed-dir absent → skip+exit0 |
| BP-100i-4 | FULLY | check_hook_parity.py; commit_guardian.json | test_check_hook_parity.py | manifest entry + exit 1 |
| BP-100i-5 | FULLY | check_hook_parity.py | test_check_hook_parity.py | all-in-sync silent exit 0 |
| BP-100m-1 | FULLY | build_phases.py; build.py | test_deploy_collision_guard.py | names both sources + target |
| BP-100m-1-i | FULLY | build_phases.py (detect_deploy_collisions) | test_deploy_collision_guard.py | byte-identical still collides |
| BP-100m-2 | FULLY | build_phases.py | test_deploy_collision_guard.py | N-way all sources named |
| BP-100m-2-i | FULLY | build_phases.py | test_deploy_collision_guard.py | cross-platform fan-out not flagged |
| BP-100m-3 | FULLY | build_phases.py; build.py | test_deploy_collision_guard.py | ordering-independent detection |

### BP-200 — llm-expert-agent (27 CODE_NO_TEST)

All 27 implemented as real artifact content — `templates/agents/llm-expert.md`,
`docs/agents/llm-expert/PROJECT_CONTEXT.md`, `config/agent_registry.json`,
`templates/skills/prompt-audit/SKILL.md`, `docs/agents/README.md` — with **no dedicated
tests** (normal for prompt/doc/config surfaces). Store `work_status: done` is accurate for
content, overstates coverage. Minor: BP-200a-2 items 5,6 lack a "Correct form" line.

### BP-006 (9 FULLY — tests ran green)

| AC | Verdict | Code | Test |
|----|---------|------|------|
| BP-006a-1 | FULLY | config/skill_registry.json | tests/test_skill_registry.py |
| BP-006a-2 | FULLY | skill_registry.json; scripts/build_helpers.py | test_skill_registry.py::test_no_orphaned_directories |
| BP-006a-3 | FULLY | tests/test_skill_registry.py | test_skill_registry.py |
| BP-006b-1 | FULLY | tests/test_install_hooks.py; build_helpers.py | test_install_hooks.py |
| BP-006b-2 | FULLY | tests/test_install_hooks.py | test_install_hooks.py |
| BP-006c-1 | FULLY | scripts/build_phases.py | unit_tests/test_build_workflow_phase.py |
| BP-006c-2 | FULLY | scripts/build_phases.py | test_build_workflow_phase.py |
| BP-006c-3 | FULLY | build_phases.py; templates/workflows-js/plan-feature.js | tests/test_build_phases.py |
| BP-006d-1 | FULLY | scripts/setup_ticket_worktree.py | tests/test_setup_ticket_worktree.py |

### BP-400 — drive-observability (5 FULLY · 1 CODE_NO_TEST · 9 NOT_IMPL)

Only the **BP-400c feedback-report** cluster shipped (under
`TICKET-20260603-FeedbackAnalysisPipeline`; AC store back-refs empty → grep-missed).

| AC | Verdict | Code | Test |
|----|---------|------|------|
| BP-400c-1 | CODE_NO_TEST | templates/skills/feedback-analysis/scripts/trend_report.py + agent/workflow/SKILL | — |
| BP-400c-2 | FULLY | trend_report.py (`_compute_trend`) | unit_tests/test_trend_report.py |
| BP-400c-2-i | FULLY | trend_report.py (empty→no-data) | test_trend_report.py |
| BP-400c-3 | FULLY | trend_report.py | test_trend_report.py |
| BP-400c-4 | FULLY | trend_report.py (`--since` pass-through) | test_trend_report.py |
| BP-400c-5 | FULLY | trend_report.py (`_build_action_items`) | test_trend_report.py |
| BP-400a-* / BP-400b-* | NOT_IMPL | — | — | agent-telemetry + rename-robust retro absent (9 ACs) |

### BP-600 — quick-fix-workflow (21 CODE_NO_TEST · 4 NOT_IMPL)

Whole workflow in `templates/workflows-js/quick-fix.js` + `templates/skills/quick-fix/SKILL.md`.
**Zero BP-600 tests exist.** Real gaps: **BP-600b-1-i** (duplicate/overlap detection),
**BP-600c-2-i** (ERROR-vs-FAILED distinction), **BP-600c-3-i** (related/importer regression
scan), **BP-600e-1-i** (pre/post diff to exclude autoformat) — all NOT_IMPLEMENTED. The other
21 leaves (a-1/a-2/a-3/a-3-i, b-1/b-2/b-2-i/b-3, c-1/c-2/c-3, d-1/d-1-i/d-2/d-3/d-4/d-4-i,
e-1/e-2/e-3/e-3-i) are CODE_NO_TEST.

### BP-700 — unified-frontend (3 FULLY · 19 CODE_NO_TEST)

Genuinely shipped: `templates/agents/frontend-coder.md`, `config/agent_registry.json`,
build-migration in `scripts/build.py`/`build_phases.py`, plus how-to/reference/upgrade docs.
FULLY: **BP-700b-1, b-2, b-2-i** (all by `unit_tests/test_frontend_coder_llm_trigger.py`,
5/5 pass). Remaining 19 (a-1..a-5, b-3, c-1..c-5, d-1..d-4) CODE_NO_TEST. Note: the one test
tags all three sibling ACs `# covers: BP-700b-2-i`; `skill_registry.json` still lists
`frontend-design` as installable (stale, but deploy is gated by `deprecated: true`).

### BP-900 — deployment-completeness + singletons (13 FULLY · 2 CODE_NO_TEST · 1 TEST_NO_CODE · 16 NOT_IMPL)

| AC | Verdict | Code | Test | Note |
|----|---------|------|------|------|
| BP-900a-1 / a-1-1 / a-2 / a-3 | NOT_IMPL | build_phases.py (partial) | — | ac_store package deploy/importability absent (4) |
| BP-900b-1 | FULLY | scripts/build_referential_integrity.py | test_build_guard_real_package.py | |
| BP-900b-1-1 | FULLY | scripts/build_propagation_audit.py | test_build_guard_real_package.py | allowlist load-bearing |
| BP-900b-2 | FULLY | build.py; build_propagation_audit.py | test_build_guard_real_package.py | cross-check present+tested |
| BP-900b-3 | FULLY | build.py (main) | test_build_guard_real_package.py | guard returns 1, wired |
| BP-900c-1 | FULLY | build_propagation_audit.py | test_build_tracked_source_guard.py | three-field entry asserted |
| BP-900c-1-1 | CODE_NO_TEST | build_propagation_audit.py | — | no multi-template test |
| BP-900c-2 | FULLY | build_propagation_audit.py | test_build_guard_real_package.py | JSONL-to-stderr+nonzero |
| BP-900c-3 | CODE_NO_TEST (broken) | build_propagation_audit.py | test_build_tracked_source_guard.py | allowlist masks feedback case; test xfail-masked RED |
| BP-900c-3-i | FULLY | build_propagation_audit.py | test_build_tracked_source_guard.py | dir-absent → add-deploy |
| BP-900e-1..5 | NOT_IMPL | — | — | registry-completeness absent (6 ACs) |
| BP-900f-1 | FULLY | build.py (_classify_untracked_sources) | test_build_tracked_source_guard.py; test_build_guard_real_package.py | git-index classifier |
| BP-900f-2 | FULLY | build.py (_check_tracked_source_guard) | (same) | nonzero+stderr, wired |
| BP-900f-3 | FULLY | build.py | test_build_tracked_source_guard.py | directory-agnostic |
| BP-900g-1 | TEST_NO_CODE | — | test_deploy_collision_guard.py | test checks template name-form, not reachability guard |
| BP-900g-1-i..g-3-i | NOT_IMPL | — | — | reachability resolver absent (5 ACs) |
| BP-811 | FULLY | build_phases.py (build_workflow_scripts) | tests/test_build_shims.py | writes to output_root/workflows/ |
| BP-812 | FULLY | templates/scripts/commit_guardian/check_secrets.py | test_check_secrets_template_prose_prefixes.py | prose prefix present+tested |
| BP-901 | FULLY | scripts/goal_to_epic.py | tests/test_goal_to_epic_worktree_skip.py; unit_tests/test_goal_to_epic.py | lazy worktree resolution |

### BP-1100 — phantom-done-prevention (11 FULLY · 12 NOT_IMPL)

Only the **`e` reconciliation cluster** is built and wired into `.pre-commit-config.yaml`:
BP-1100e-1, e-1-i..e-1-vii, e-2, e-2-a, e-3 (11 FULLY, code
`templates/scripts/commit_guardian/hooks/check_files_touched_reconciliation.py`, tests
`unit_tests/commit_guardian/test_check_files_touched_reconciliation*.py`; e-3 is a doc AC).
BP-1100a-1..a-2, b-1..b-2, c-1..c-2, d-1..d-2 (12) NOT_IMPLEMENTED — refinement scope lens,
test-writer skip suppression, finalize spot-check, commit-delegation guard all absent.

### BP-1200 — ci-test-gate (3 FULLY · 9 NOT_IMPL)

FULLY: BP-1200a-1-ii/-1-iii/-1-iv (build-guard package integrity, `test_build_guard_real_package.py`).
NOT_IMPL: a-1 (suite not green in ci.yml), a-1-i, a-2 (no authoritative CI command), **b-1/b-1-i/b-1-ii
(blocking gate — ci `test` job is `continue-on-error`)**, b-2 (diagram), c-1/c-1-i
(branch-protection-as-code).

### BP-1300 — unmaskable-guardrails (1 FULLY · 13 NOT_IMPL)

FULLY: BP-1300a-2 (resolvable-pointer positive case). **BP-1300a-1/-1-i/-1-ii opposite-behaviour**
(resolves via deployed `.claude/skills`, not canonical). a-3, b-1..b-3, c-1..c-4 NOT_IMPLEMENTED
(canonical-source resolution rule + drive-context escalation + reference docs absent).

### FIN-100 — pre-merge-safety-gate (3 FULLY · 14 CODE_NO_TEST · 2 NOT_IMPL)

Safety-gate logic fully coded in `templates/workflows-js/finalize-feature.js` +
`templates/agents/test-failure-triage.md`, but mostly untested. FULLY: a-4 (build.py both
steps), e-3 (null-guard), g-1 (pre-flight branch detection). CODE_NO_TEST: a-1/a-2/a-3, b-1/b-2/b-3,
c-1/c-2/c-3, d-1/d-2/d-3, f-1/f-2 (14). **NOT_IMPL: e-1 (auto-ticketing DISABLED — code+test assert
opposite), e-2** (no ticket creation to be non-fatal).

### FIN-200 — changelog-on-finalize (13 NOT_IMPL)

Entire group greenfield — no changelog step, config key (`changelog_blocks_merge`), return
field (`missing_changelog`), how-to mention, or sequence diagram anywhere in finalize. Only
`changelog_folder` exists in config. Store `work_status: todo` is accurate.

---

## Recommended next steps (Stage 5 — not yet executed)

1. **Fix the xfail-masking hazard first** — it undermines every other verdict. Until
   `pytest_ac_enforcement.py` stops rewriting real failures, "green" is not trustworthy.
2. **Remediation tickets** for the 7 phantom/opposite findings (§ Phantom-done risk) —
   cluster by root-cause file (BP-1300a + BP-900c-3 + BP-100i-3 are guard-logic corrections;
   FIN-100e is a policy/AC-reconciliation decision).
3. **Test-backfill epic** for the 91 CODE_NO_TEST ACs — biggest single lever; BP-600 (21) and
   FIN-100 (14) are the highest-risk untested surfaces.
4. **Wave-2 greenfield epics** for the 183 NOT_IMPLEMENTED (BP-300/800/1000, FIN-200,
   BP-100e/f/g, BP-900a/e/g, BP-1200b/c, BP-1300b/c, BP-400a/b) — promote ACs to
   `readiness: approved` before the scanner will surface them.
5. **Evidence-anchored reconciliation** — for the 80 verified-FULLY ACs, write `covered_by`
   with the concrete green test and `mark_ac_done.py`. Never flip a CODE_NO_TEST to done.

All audit work was read-only; the store was not modified.
