# BO-* Acceptance-Criteria Implementation Audit

**Date:** 2026-07-14
**Scope:** All BO-* leaf ACs (L2/L3) whose store fields mark them **not** done / in-progress / implemented
(`work_status: todo` **and** empty `implemented_by`) — 301 ACs across 15 epics.
**Method:** Each AC's `criteria` was read, then the repo was searched **independently** of the stale
store fields to locate real implementing code and a unit test that genuinely exercises the behavior.

## Verdict legend

- **FULLY_IMPLEMENTED** — real implementing code exists AND a unit test genuinely exercises the behavior.
- **CODE_NO_TEST** — implementing code (often prompt/config) exists but no test meaningfully covers it.
- **NOT_IMPLEMENTED** — behavior absent, OR only dead/unwired code exists, OR shipped code implements a
  *different/opposite* design than the AC specifies (phantom-done).
- **TEST_NO_CODE** — a test references it but the code is absent/stub. (None found.)

## Executive summary

| Verdict | Count | % of 301 |
|---|---|---|
| FULLY_IMPLEMENTED | 107 | 36% |
| CODE_NO_TEST | 28 | 9% |
| NOT_IMPLEMENTED | 166 | 55% |
| TEST_NO_CODE | 0 | 0% |

**Headline:** the AC store's own bookkeeping is unusable — every one of these 301 ACs is marked
`work_status: todo` with empty `implemented_by`, yet **107 are fully built and tested** and another 28
have real code. Conversely, "green tests" do **not** mean built: several epics ship unit-tested Python
libraries or helper functions that **nothing calls** (orphaned/dead code) — the classic phantom-done
pattern this repo was created to prevent.

## Per-epic rollup

| Epic | ACs | Fully | Code-no-test | Not-impl | State |
|---|---|---|---|---|---|
| BO-100 smart-sequencing | 20 | 0 | 0 | 20 | Unbuilt — graph/cycle/batching delegated to LLM planner prose |
| BO-1000 live-automation-progress | 17 | 0 | 0 | 17 | Unbuilt — no step-narration / journal / relay |
| BO-1100 smart-commit-routing | 36 | 14 | 1 | 21 | **Orphaned lib** — classifier/learner green but commit agent never calls it |
| BO-1400 trustworthy-pre-pr-review | 5 | 0 | 0 | 5 | Unbuilt — `scripts/pr_review/` helpers absent |
| BO-1600 safe-concurrent-dispatch (a/b/c) | 12 | 0 | 0 | 12 | Unbuilt — `epic_lock.py` absent; only sibling d (recovery) built |
| BO-1700 worktree-quality-gate-guard | 39 | 24 | 5 | 10 | Mostly built; **dead-helper cluster** (g/h/b-4/e-3) |
| BO-200 atomic-delivery | 10 | 0 | 0 | 10 | Unbuilt — no work-envelope / atomic-stage / rollback |
| BO-2000 correct-prompts-by-construction | 35 | 33 | 0 | 2 | **Strongest epic** — only c-3/c-3-i phantom-covered |
| BO-210 precommit-safety-net | 12 | 0 | 12 | 0 | Prompt/config built, no tests; deployed-stub parity drift |
| BO-400 ticket-status-source-of-truth | 20 | 17 | 1 | 2 | Strong; c-3 family phantom (xfail-masked, wrong import) |
| BO-500 computed-quality-gates | 28 | 12 | 7 | 9 | Engine built+wired; BO-520 change_type branch superseded |
| BO-600 change-driven-guardrails | 30 | 7 | 2 | 21 | Partial under different vocab; abstract gate-set absent |
| BO-700 auto-versioning | 19 | 0 | 0 | 19 | Unbuilt — existing versioning is a different (non-AC-lineage) design |
| BO-800 self-describing-prs | 12 | 0 | 0 | 12 | Unbuilt — PR agent drafts from git log (opposite of AC) |
| BO-900 mid-epic-sync | 6 | 0 | 0 | 6 | Unbuilt — no between-batch divergence/merge |

## Highest phantom-done risks (green-but-not-really)

1. **BO-1100** — `scripts/commit_classifier.py` + `commit_pattern_learner.py` (150 passing tests) are
   **never invoked**; `templates/agents/commit.md` drafts messages free-hand. All `change_target: prompt`
   ACs are unwired. Config also diverges from spec (object vs array).
2. **BO-1700 g/h/b-4/e-3/h-1** — `validate_hook_name`, `validate_canary_stage`, `check_hook_freshness`,
   `resolve_hooks_path`, `remove_canary_from_manifest` are unit-tested but **never called by
   `run_checks()`**; some implement the *opposite* behavior (e-3 fail-open vs required fail-closed).
   Prompt gates parse JSON keys (`all_pass`/`results`) the probe never emits.
3. **BO-600 610-3-i / 610-4 / 610-4-i** — the frontmatter guard makes the fields optional and accepts
   null/empty; the tests assert exactly the behavior the AC says to **reject**. BO-630 model-tier helpers
   are dead code.
4. **BO-400 c-3 family** — `_check_done_folder_prohibition` is presence-based (not staged-path-change),
   its tests are silently converted to XFAIL by `pytest_ac_enforcement.py`, and they import from a path
   the module isn't deployed to — so no assertion ever runs.
5. **BO-2000 c-3 / c-3-i** — `# covers:` labels sit on an unrelated dispatch test; no reference-pattern
   resolution exists.

## Cross-cutting notes

- **Source SSOT is `templates/`, not `scripts/`.** `scripts/` and `.claude/` are build outputs of
  `build.py`. Several tests resolve their target via the parent-workspace deploy, so a fresh
  `leafcutter-ai/` checkout can show subprocess-test failures that are environment artifacts, not logic bugs.
- **`implemented_by` records the generating *ticket*, not code.** It is not evidence of implementation.
- **`work_status` is uniformly stale** across all 301 ACs (all `todo`) — do not trust it.

---

# Per-AC detail

Below, code/test paths are repo-relative. `—` means none found.

## BO-100 smart-sequencing — 0/20 built (all NOT_IMPLEMENTED)

Grep for `BO-100` returns zero hits in scripts/templates/tests. `build-epic.js` delegates the entire
dependency graph, cycle detection, ready-set, and files_touched-disjoint batching to an **LLM planner
prompt** (no deterministic code). `BATCH_SIZE=12` is a concurrency chunk, not the AC's configurable
batch-cap-of-3. The closest real graph code, `scripts/ticket_prioritizer.py`, is the BO-400 surface and
has *opposite* unknown-dependency semantics. BO-100d telemetry-sink gate exists only as operator prose in
CLAUDE.md. ACs: BO-100a-1..5, BO-100b-1..4, BO-100c-1..2, BO-100d-1/-1-i/-1-ii/-1a/-1b/-2/-2-i/-2a/-2b.

## BO-1000 live-automation-progress — 0/17 built (all NOT_IMPLEMENTED)

`finalize-feature.js` uses `phase('Step 0')` engine markers, not the required "Step X of N" human
narration; no `N`, no per-step outcome record, no run-progress journal, no over-time relay. Planned
sequence diagrams absent. ACs: BO-1000a-1/-1-i/-2/-2-i/-3/-4, b-1/-1-i/-2/-2-i/-3, c-1/-1a/-1b/-2/-2-i/-3.

## BO-1100 smart-commit-routing — 14 fully / 1 code-no-test / 21 not-impl

Python library real & green but **orphaned** (commit agent never calls it). FULLY: a-1, a-6, a-6-i, c-4,
d-1, d-1-i, d-5, d-6, e-1, e-1-i, e-2, e-2-i, e-4, e-4-i → `scripts/commit_classifier.py` /
`scripts/commit_pattern_learner.py` with tests `unit_tests/test_commit_classifier.py`,
`test_commit_pattern_learner.py`, `test_history_filter.py`, `test_defect_fixes.py`. CODE_NO_TEST: a-2-i
(`templates/agents/commit.md`). NOT_IMPLEMENTED (unwired prompt layer / config divergence): a-1-i, a-2,
a-3, a-4, a-5, b-1, b-1-i, b-2, b-3, b-3-i, c-1, c-1-i, c-2, c-3, c-3-i, d-2, d-2-i, d-3, d-3-i, d-4, e-3.

## BO-1400 trustworthy-pre-pr-review — 0/5 built (all NOT_IMPLEMENTED)

`scripts/pr_review/realdata_verifier.py` and `install_reachability.py` do not exist; `pr-reviewer.md`
lacks real-data verification, bulk-claim detection, INCONCLUSIVE outcome, reachability check. ACs:
BO-1400a-1/-1-i/-2/-2-i/-3.

## BO-1600 safe-concurrent-dispatch (a/b/c) — 0/12 built (all NOT_IMPLEMENTED)

`scripts/epic_lock.py` (the serialization primitive) does not exist; `build-epic.js` has no commit lock,
integrity probe, or corruption halt. Only sibling family BO-1600d (`templates/scripts/git_recovery.py` +
`tests/test_git_recovery.py`, human-invoked recovery — out of audit scope) is built, and it *presupposes*
the BO-1600c halt that was never implemented. ACs: BO-1600a-1..4, b-1..4, c-1..4.

## BO-1700 worktree-quality-gate-guard — 24 fully / 5 code-no-test / 10 not-impl

FULLY: a-1, a-2, a-3, a-3-i, a-3-ii, a-10, a-11, b-1, b-2, c-1, c-1-i, c-1-ii, c-1-iv, c-2, c-3, d-1, d-4,
e-1, e-2, e-4, e-5, f-1, f-1-i, h-2 → `templates/scripts/commit_guardian/verify_precommit_active.py` /
`ensure_precommit_config.py` / `precommit_canary.py`, `scripts/setup_ticket_worktree.py`, `scripts/build.py`,
plus docs/diagrams; tests in `unit_tests/commit_guardian/`, `unit_tests/setup/`, `unit_tests/portability/`.
CODE_NO_TEST: b-3, d-2, d-3, d-3-i, e-1-i (prompt gates / layout). NOT_IMPLEMENTED (dead-helper or
wrong-behavior): b-4, c-1-iii, d-1-i, e-3 (fail-open vs required fail-closed), f-1-ii, g-1, g-2, g-3, h-1,
h-3. Prompt gates parse `all_pass`/`results` keys the probe never emits.

## BO-200 atomic-delivery — 0/10 built (all NOT_IMPLEMENTED)

No "work envelope" dict, no atomic staging + rollback + 3-retry mechanism anywhere. Existing commit infra
(commit.md, commit_classifier, enforce_commit_delegation) belongs to BO-1100/BO-1700 and only incidentally
overlaps; retry cap is 1 not 3 (contradicts b-3). ACs: BO-200a-1..3, b-1..3, c-1..4.

## BO-2000 correct-prompts-by-construction — 33 fully / 2 not-impl

FULLY (33): all of a-*, b-*, c-1/-1-i/-2/-4, d-*, e-*, f-* → `templates/agents/_signoff_block.md`,
`python-coder.md`, `it-po.md`, `scripts/ac_store/generate_ticket_from_ac.py`, `config/ac_store_schema.json`,
`scripts/ac_store/validate_ac.py`, `templates/scripts/commit_guardian/check_ticket_test_requirements.py`,
`templates/workflows-js/build-feature.js`/`build-ticket.js`; tests all in `unit_tests/prompt_assembly/`
(34 passing). NOT_IMPLEMENTED: **c-3, c-3-i** — no reference-pattern-to-path resolution; `# covers:` labels
placed on an unrelated dispatch test (phantom coverage).

## BO-210 precommit-safety-net — 12 code-no-test (0 tested)

All 12 are config/prompt surfaces present in `templates/scripts/precommit-autofix.json`,
`scripts/build_config_scaffolds.py`, the coder templates, `templates/skills/signoff/SKILL.md`,
`precommit-autofix/SKILL.md`, `commit.md` — but **no dedicated test** asserts any BO-210 AC. Live parity
drift: the checked-in deployed `.claude/precommit-autofix.json` is still the dead stub `{"routes":{}}`
(build is write-if-absent, never overwrites). ACs: a-1/-1-i/-2, b-1/-1-i/-2, c-1/-1-i/-1-ii/-1-iii/-2/-2-i.

## BO-400 ticket-status-source-of-truth — 17 fully / 1 code-no-test / 2 not-impl

FULLY (17): a-1, a-1-i, a-2, a-2-i, a-3, a-4, a-5, b-1, b-1-i, b-2, b-2-i, b-3, c-1, c-1-i, c-2, c-2-i,
c-4 → `scripts/set_ticket_status.py`, `scripts/ticket_prioritizer.py`,
`templates/skills/building-epics/SKILL.md`, `finalize-feature-archive-check/SKILL.md`,
`templates/agents/status-checker.md`; tests `unit_tests/commit_guardian/test_set_ticket_status.py`,
`unit_tests/test_ticket_prioritizer_status_filter.py`. CODE_NO_TEST: c-3
(`_signoff_parity_checks.py` — tests XFAIL-masked + wrong import path). NOT_IMPLEMENTED: c-3-i (false
positive persists), c-3-ii (`/done/` substring misses `tickets/99_done/`; no env-flag carve-out).

## BO-500 computed-quality-gates — 12 fully / 7 code-no-test / 9 not-impl

Engine (`produces` trait + `config/guardrail_gates.yaml` chain in
`scripts/ac_store/generate_ticket_from_ac.py::_build_agents_map`) is real, wired, and covered by
anti-phantom-done e2e tests (`unit_tests/test_generate_ticket_from_ac.py`,
`test_agent_produces_validation.py`). FULLY: 510-1, 510-2, 510-3, 510-3-i, 510-4, 530-1, 530-2, 540-1,
540-2, 560-1, 560-2, 560-3. CODE_NO_TEST: 510-4-i, 510-5, 530-1-i, 530-3, 530-3-i, 540-1-i, 550-1-i
(prompt-only surfaces). NOT_IMPLEMENTED: entire **BO-520 change_type branch** (520-1/-1-i/-2/-3/-3-i —
superseded by change_target per ADR-017), 550-1 & 550-2 (test_constraints emitted as string-list, no
structured schema, no consumer), 560-1-i (spec wants hard blocker; impl warns+continues), 560-3-i (no
audit-comment-on-replace). Locus note: chain computed at ticket-**generation** time, not supervisor
dispatch time as the ACs word it.

## BO-600 change-driven-guardrails — 7 fully / 2 code-no-test / 21 not-impl

Partially realized under a **different design** (`guardrail_gates.yaml` maps to *agent names*, not the
abstract gate identifiers the ACs specify; vocab differs: `infrastructure`/`contract_boundary` vs
`infra`/`contract`). FULLY: 610-1, 610-2, 610-3, 610-5, 630-1, 630-2, 660-1 →
`templates/hooks/ticket_frontmatter_guard.py`, `scripts/ac_store/generate_ticket_from_ac.py`; tests
`unit_tests/test_ticket_frontmatter_guard.py`, `test_generate_ticket_from_ac.py`. CODE_NO_TEST: 650-2
(`adr-author.md`), 650-3 (`architecture-diagram-author.md` + write-c4-diagram) — agents exist, no engine
trigger. NOT_IMPLEMENTED (21): 610-3-i, 610-4, 610-4-i (guard accepts null/empty; tests assert the
opposite of the AC — phantom), all BO-620 gate-set (1/1-i/2/3/4/5), 630-1-i, 640-1/-1-i/-2/-3, 650-1/-1-i
/-4/-5/-5-i, 660-2/-2-i. BO-630 model-tier helpers are dead code (never called, no frontmatter emission).

## BO-700 auto-versioning — 0/19 built (all NOT_IMPLEMENTED)

Existing versioning (`scripts/release/compute_next_version.py`, `emit_entry.py`,
`scripts/ac_store/mark_ac_done.py`) is the earlier EPIC-LeafcutterVersioning design (JSON payload +
type/breaking flags), **not** BO-700's AC-lineage design. `_compute_bump` keys on type/breaking and
auto-majors on breaking (directly violates 700b-3 "never major without override"); `mark_ac_done.py`
emits no changelog at closure; no AC-lineage grouping, no CHANGELOG renderer, no release manifest. ACs:
BO-700a-1..3(+ -i), b-1..3(+ -i), c-1/-1-i/-2, d-1/-1-i/-2, e-1/-1-i/-2.

## BO-800 self-describing-prs — 0/12 built (all NOT_IMPLEMENTED)

`templates/agents/pull-request.md` implements the **opposite** of the ACs: title from git log/commits,
body from generic LLM `## Summary`/`## Test plan`. It never reads `source_ac`, never resolves L0/L1/L2/L3
lineage, never emits a Goal link, never reads AC YAML at PR time. `source_ac` appears only in ticket
generation, unrelated. ACs: BO-800a-1/-1-i/-1-ii, b-1/-1-i, c-1/-1-i, d-1/-1-i/-2, e-1/-1-i.

## BO-900 mid-epic-sync — 0/6 built (all NOT_IMPLEMENTED)

`build-epic.js`/`build-feature.js` batch loops have no divergence count, no origin/main fetch/merge, no
sync prompt between batches, no divergence-threshold config. The only sync/divergence code
(`finalize-feature.js` pre-step-4 sync, `quick-fix.js` root-cause divergence) belongs to other features.
ACs: BO-900a-1/-1-i/-2/-3/-3-i/-4.
